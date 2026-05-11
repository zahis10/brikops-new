from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
import uuid
import logging
import time
import httpx
from contractor_ops.router import get_db, get_current_user, _get_project_role, _is_super_admin, _now, _audit, MANAGEMENT_ROLES, get_notification_engine, get_public_base_url
from contractor_ops.msg_logger import mask_phone
from contractor_ops.upload_safety import validate_upload, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES
from contractor_ops.projects_router import _natural_sort_key

logger = logging.getLogger(__name__)

# #503 — QC → Matrix continuous sync (one-way). Module-level import so
# tests can `patch.object(qcr, "sync_qc_stage_to_matrix", ...)` for T9
# (sync-failure-protection). Sync is gated by MATRIX_QC_SYNC_ENABLED
# env var (default OFF) — see qc_to_matrix_sync.py.
from contractor_ops.qc_to_matrix_sync import sync_qc_stage_to_matrix


async def _resolve_unit_ids_for_sync(db, run, items, stage_scope):
    """Resolve the list of unit_ids for matrix-cell upserts.

    #503-followup-2 — fixes the floor-scope silent no-op (Bug 2 from
    Zahi smoke 2026-05-06): items are template-level for floor stages
    (no unit_id field), and the run itself has no unit_id either, so
    the previous `list({i.get("unit_id") ...})` aggregation iterated 0
    times and the sync silently did nothing.

    Resolution order:
      1. Unit-scope: just [run.unit_id] (single cell).
      2. Floor-scope items.unit_id distinct (handles per-item activity
         where the item carries unit_id).
      3. Floor-scope fallback: query units by floor_id from the run
         (handles approve/reject on template-level items).
      4. Empty list (no-op — caller's loop iterates 0 times safely).
    """
    if stage_scope != "floor":
        uid = run.get("unit_id")
        return [uid] if uid else []

    unit_ids = list({i.get("unit_id") for i in items if i.get("unit_id")})
    if unit_ids:
        return unit_ids

    floor_id = run.get("floor_id")
    if not floor_id:
        return []
    units = await db.units.find(
        {"floor_id": floor_id, "archived": {"$ne": True}},
        {"_id": 0, "id": 1},
    ).to_list(500)
    return [u["id"] for u in units if u.get("id")]


router = APIRouter(prefix="/api/qc", tags=["qc"])
notif_router = APIRouter(prefix="/api/qc-notifications", tags=["qc-notifications"])

FLOOR_TEMPLATE_ID = "tpl_floor_execution_v1"

QC_ALLOWED_ROLES = MANAGEMENT_ROLES

PM_ROLES = {'project_manager', 'owner'}

NOTIFY_ELIGIBLE_ROLES = {'project_manager', 'owner', 'management_team'}

VALID_STAGE_STATUSES_FULL = {"draft", "ready", "pending_review", "approved", "rejected", "reopened"}


def _actor_name(user):
    return user.get("name") or user.get("full_name") or ""


def _stage_label(tpl, stage_id):
    for s in tpl["stages"]:
        if s["id"] == stage_id:
            return s["title"]
    return stage_id


async def _create_qc_notification(db, recipients, *, project_id, stage_id, floor_id, building_id,
                                   stage_code, stage_label_he, actor_id, actor_name_str,
                                   action, reason=None, run_id=None):
    now = _now()
    docs = []
    for uid in recipients:
        if uid == actor_id:
            continue
        docs.append({
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "project_id": project_id,
            "stage_id": stage_id,
            "floor_id": floor_id,
            "building_id": building_id,
            "run_id": run_id,
            "stage_code": stage_code,
            "stage_label_he": stage_label_he,
            "actor_id": actor_id,
            "actor_name": actor_name_str,
            "action": action,
            "reason": reason,
            "created_at": now,
            "read_at": None,
        })
    if docs:
        await db.qc_notifications.insert_many(docs)
    return docs


async def _get_stage_recipients(db, project_id, stage_id, action, submitter_id=None):
    pm_ids = set()
    memberships = await db.project_memberships.find(
        {"project_id": project_id, "role": {"$in": list(PM_ROLES)}},
        {"_id": 0, "user_id": 1}
    ).to_list(50)
    for m in memberships:
        pm_ids.add(m["user_id"])

    approver_ids = set()
    approvers = await db.project_approvers.find(
        {"project_id": project_id, "active": True},
        {"_id": 0, "user_id": 1, "mode": 1, "stages": 1}
    ).to_list(200)
    for a in approvers:
        if a.get("mode") == "all":
            approver_ids.add(a["user_id"])
        elif a.get("mode") == "stages" and stage_id in (a.get("stages") or []):
            approver_ids.add(a["user_id"])

    if action == "submitted":
        return pm_ids | approver_ids
    elif action in ("approved", "rejected", "reopened"):
        recipients = pm_ids.copy()
        if submitter_id:
            recipients.add(submitter_id)
        return recipients
    return pm_ids

UPLOADS_DIR = Path(__file__).parent.parent / "uploads" / "qc"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

FLOOR_TEMPLATE = {
    "id": FLOOR_TEMPLATE_ID,
    "name": "ביצוע – קומה",
    "version": 6,
    "stages": [
        {
            "id": "stage_ceiling_prep",
            "title": "הכנה ליציקת תקרה",
            "order": 1,
            "scope": "floor",
            "items": [
                {"id": "cp_1", "title": "בדיקת תבניות וטפסנות", "order": 1, "required_photo": True, "required_note": False},
                {"id": "cp_2", "title": "בדיקת ברזל זיון", "order": 2, "required_photo": True, "required_note": False},
                {"id": "cp_3", "title": "בדיקת מיקום פתחים", "order": 3, "required_photo": False, "required_note": False},
                {"id": "cp_4", "title": "ניקיון תחתית טפסנות", "order": 4, "required_photo": True, "required_note": False},
                {"id": "cp_5", "title": "בדיקת גבהים ומפלסים", "order": 5, "required_photo": False, "required_note": True},
                {"id": "cp_6", "title": "אישור מהנדס קונסטרוקציה", "order": 6, "required_photo": True, "required_note": True},
                {"id": "cp_7", "title": "בדיקת עוגנים ושרוולים", "order": 7, "required_photo": True, "required_note": False},
                {"id": "cp_complete", "title": "סיום קומה — הכנה ליציקה", "order": 8, "required_photo": True, "required_note": False},
            ],
        },
        {
            "id": "stage_blocks_row1",
            "title": "בלוקים — שורה ראשונה",
            "order": 2,
            "scope": "floor",
            "items": [
                {"id": "br_pw1", "title": "פתיחת מלאכה - בלוקים", "order": 0, "required_photo": True, "required_note": False, "pre_work_documentation": True},
                {"id": "br_pw2", "title": "הערות לפני עבודה", "order": 0, "required_photo": False, "required_note": False, "pre_work_documentation": True},
                {"id": "br_1", "title": "בדיקת קו ייחוס וסימון", "order": 1, "required_photo": True, "required_note": False},
                {"id": "br_2", "title": "הנחת שורה ראשונה יבשה", "order": 2, "required_photo": True, "required_note": False},
                {"id": "br_3", "title": "בדיקת מפלס ואופקיות", "order": 3, "required_photo": False, "required_note": True},
                {"id": "br_4", "title": "מילוי דבק/טיט בין בלוקים", "order": 4, "required_photo": False, "required_note": False},
                {"id": "br_5", "title": "בדיקת פתחי חלונות ודלתות", "order": 5, "required_photo": True, "required_note": False},
                {"id": "br_6", "title": "חיבור ברזל אנכי", "order": 6, "required_photo": True, "required_note": False},
                {"id": "br_complete", "title": "סיום קומה — בלוקים", "order": 7, "required_photo": True, "required_note": False},
            ],
        },
        {
            "id": "stage_plumbing",
            "title": "הכנות אינסטלציה בקומה",
            "order": 3,
            "scope": "floor",
            "items": [
                {"id": "pl_pw1", "title": "פתיחת מלאכה - אינסטלציה", "order": 0, "required_photo": True, "required_note": False, "pre_work_documentation": True},
                {"id": "pl_pw2", "title": "הערות לפני עבודה", "order": 0, "required_photo": False, "required_note": False, "pre_work_documentation": True},
                {"id": "pl_1", "title": "סימון נקודות ניקוז", "order": 1, "required_photo": False, "required_note": False},
                {"id": "pl_2", "title": "התקנת צנרת ביוב", "order": 2, "required_photo": True, "required_note": False},
                {"id": "pl_3", "title": "התקנת צנרת מים קרים/חמים", "order": 3, "required_photo": True, "required_note": False},
                {"id": "pl_4", "title": "בדיקת לחץ צנרת", "order": 4, "required_photo": False, "required_note": True},
                {"id": "pl_5", "title": "בידוד צנרת", "order": 5, "required_photo": True, "required_note": False},
                {"id": "pl_6", "title": "תיעוד מיקומים לפני סגירה", "order": 6, "required_photo": True, "required_note": True},
                {"id": "pl_7", "title": "בדיקת שיפועי ניקוז", "order": 7, "required_photo": False, "required_note": True},
                {"id": "pl_8", "title": "אישור מפקח אינסטלציה", "order": 8, "required_photo": False, "required_note": True},
                {"id": "pl_complete", "title": "סיום קומה — אינסטלציה", "order": 9, "required_photo": True, "required_note": False},
            ],
        },
        {
            "id": "stage_electrical",
            "title": "הכנות חשמל בקומה",
            "order": 4,
            "scope": "floor",
            "items": [
                {"id": "el_pw1", "title": "פתיחת מלאכה - חשמל", "order": 0, "required_photo": True, "required_note": False, "pre_work_documentation": True},
                {"id": "el_pw2", "title": "הערות לפני עבודה", "order": 0, "required_photo": False, "required_note": False, "pre_work_documentation": True},
                {"id": "el_1", "title": "סימון נקודות חשמל", "order": 1, "required_photo": False, "required_note": False},
                {"id": "el_2", "title": "התקנת קופסאות חשמל", "order": 2, "required_photo": True, "required_note": False},
                {"id": "el_3", "title": "משיכת כבלים ראשיים", "order": 3, "required_photo": True, "required_note": False},
                {"id": "el_4", "title": "בדיקת הארקה", "order": 4, "required_photo": False, "required_note": True},
                {"id": "el_5", "title": "חיבור ללוח חשמל קומתי", "order": 5, "required_photo": True, "required_note": False},
                {"id": "el_6", "title": "תיעוד מיקומים לפני טיח", "order": 6, "required_photo": True, "required_note": True},
                {"id": "el_complete", "title": "סיום קומה — חשמל", "order": 7, "required_photo": True, "required_note": False},
            ],
        },
        {
            "id": "stage_plaster",
            "title": "טיח בקומה",
            "order": 5,
            "scope": "floor",
            "items": [
                {"id": "pt_pw1", "title": "פתיחת מלאכה - טיח", "order": 0, "required_photo": True, "required_note": False, "pre_work_documentation": True},
                {"id": "pt_pw2", "title": "הערות לפני עבודה", "order": 0, "required_photo": False, "required_note": False, "pre_work_documentation": True},
                {"id": "pt_1", "title": "הכנת משטחים — ניקיון ושטיפה", "order": 1, "required_photo": False, "required_note": False},
                {"id": "pt_2", "title": "התקנת פסי טיח (מאסטרים)", "order": 2, "required_photo": True, "required_note": False},
                {"id": "pt_3", "title": "שכבת ביטון — בדיקת עובי", "order": 3, "required_photo": True, "required_note": True},
                {"id": "pt_4", "title": "טיח גמר — בדיקת ישרות", "order": 4, "required_photo": True, "required_note": False},
                {"id": "pt_5", "title": "בדיקת פינות ומפגשים", "order": 5, "required_photo": False, "required_note": False},
                {"id": "pt_6", "title": "ריפוי (Curing) — בדיקת לחות", "order": 6, "required_photo": False, "required_note": True},
                {"id": "pt_7", "title": "אישור מפקח טיח", "order": 7, "required_photo": False, "required_note": True},
                {"id": "pt_complete", "title": "סיום קומה — טיח", "order": 8, "required_photo": True, "required_note": False},
            ],
        },
        {
            "id": "stage_waterproof",
            "title": "הצפה/אטימות",
            "order": 6,
            "scope": "floor",
            "items": [
                {"id": "wp_1", "title": "ניקיון משטח לפני איטום", "order": 1, "required_photo": False, "required_note": False},
                {"id": "wp_2", "title": "מריחת פריימר", "order": 2, "required_photo": True, "required_note": False},
                {"id": "wp_3", "title": "שכבת איטום ראשונה", "order": 3, "required_photo": True, "required_note": False},
                {"id": "wp_4", "title": "שכבת איטום שנייה", "order": 4, "required_photo": True, "required_note": False},
                {"id": "wp_5", "title": "בדיקת הצפה (48 שעות)", "order": 5, "required_photo": True, "required_note": True},
                {"id": "wp_6", "title": "תיקון נקודות דליפה", "order": 6, "required_photo": True, "required_note": True},
                {"id": "wp_7", "title": "בדיקת הצפה חוזרת", "order": 7, "required_photo": True, "required_note": False},
                {"id": "wp_8", "title": "אישור מפקח איטום", "order": 8, "required_photo": False, "required_note": True},
                {"id": "wp_complete", "title": "סיום קומה — הצפה/איטום", "order": 9, "required_photo": True, "required_note": False},
            ],
        },
        {
            "id": "stage_acoustic",
            "title": "אישור סומסום אחרי איטום/אקוסטיקה",
            "order": 7,
            "scope": "floor",
            "items": [
                {"id": "ac_1", "title": "בדיקת שכבת אקוסטיקה", "order": 1, "required_photo": True, "required_note": False},
                {"id": "ac_2", "title": "בדיקת חיבורים בין קירות לרצפה", "order": 2, "required_photo": True, "required_note": False},
                {"id": "ac_3", "title": "בדיקת מעברי צנרת דרך קירות", "order": 3, "required_photo": True, "required_note": False},
                {"id": "ac_4", "title": "בדיקת אטימות פתחים", "order": 4, "required_photo": False, "required_note": True},
                {"id": "ac_5", "title": "אישור סומסום — חתימת מפקח", "order": 5, "required_photo": False, "required_note": True},
                {"id": "ac_complete", "title": "סיום קומה — אקוסטיקה", "order": 6, "required_photo": True, "required_note": False},
            ],
        },
        {
            "id": "stage_tiling",
            "title": "ריצוף דירה",
            "order": 8,
            "scope": "unit",
            "items": [
                {"id": "tl_1", "title": "פתיחת מלאכה — תמונת מצב לפני ריצוף", "order": 1, "required_photo": True, "required_note": False, "pre_work_documentation": True},
                {"id": "tl_2", "title": "התאמת ריצוף — תעודת משלוח מול תיק דייר", "order": 2, "required_photo": True, "required_note": False},
                {"id": "tl_3", "title": "התאמה לפריסת קרמיקה לפי תוכנית", "order": 3, "required_photo": False, "required_note": False},
                {"id": "tl_4", "title": "בדיקת מפלסים", "order": 4, "required_photo": True, "required_note": True},
                {"id": "tl_5", "title": "יישור ופילוס לפני הדבקה", "order": 5, "required_photo": True, "required_note": False},
                {"id": "tl_6", "title": "בדיקת הדבקת קרמיקה", "order": 6, "required_photo": True, "required_note": False},
                {"id": "tl_7", "title": "חיתוכים וגמרים", "order": 7, "required_photo": True, "required_note": False},
                {"id": "tl_8", "title": "בדיקת שיפועים — מקלחונים ומרפסות", "order": 8, "required_photo": True, "required_note": True},
                {"id": "tl_9", "title": "סיום דירה — ריצוף", "order": 9, "required_photo": True, "required_note": False},
            ],
        },
    ],
}




_template_version_cache = {}
_default_template_cache = {"tpl": None, "ts": 0}
_DEFAULT_CACHE_TTL = 60


async def _get_template(db=None, *, project_id=None, run=None):
    if run:
        vid = run.get("template_version_id")
        if vid:
            if vid in _template_version_cache:
                return _template_version_cache[vid]
            if db is not None:
                doc = await db.qc_templates.find_one({"id": vid}, {"_id": 0})
                if doc:
                    _template_version_cache[vid] = doc
                    return doc
            logger.warning(f"[QC-TPL] run template_version_id={vid} not found, continuing fallback chain")
        if not project_id:
            project_id = run.get("project_id")

    if db is not None and project_id:
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "qc_template_version_id": 1})
        vid = proj.get("qc_template_version_id") if proj else None
        if vid:
            if vid in _template_version_cache:
                return _template_version_cache[vid]
            doc = await db.qc_templates.find_one({"id": vid}, {"_id": 0})
            if doc:
                _template_version_cache[vid] = doc
                return doc
            logger.warning(f"[QC-TPL] project qc_template_version_id={vid} not found in DB")

    if db is not None:
        now_ts = time.time()
        if _default_template_cache["tpl"] and (now_ts - _default_template_cache["ts"]) < _DEFAULT_CACHE_TTL:
            return _default_template_cache["tpl"]
        doc = await db.qc_templates.find_one(
            {"is_default": True, "is_active": True},
            {"_id": 0}
        )
        if doc:
            _default_template_cache["tpl"] = doc
            _default_template_cache["ts"] = now_ts
            _template_version_cache[doc["id"]] = doc
            return doc

    return FLOOR_TEMPLATE


def _template_ids(tpl):
    if tpl.get("family_id"):
        return tpl["family_id"], tpl["id"]
    return FLOOR_TEMPLATE_ID, None


async def _resolve_run_template_with_upgrade(
    db,
    run: dict,
    project_id: str,
    actor: dict | None,
) -> dict:
    """Load the CURRENT template for the project. If `run` is pinned to
    an older template_version_id, upgrade the run doc in DB AND in the
    in-memory dict, then return the current template.

    Idempotent: if run is already on current, no DB write.

    #601 — fixes the case where admin edits qc_template AFTER existing
    runs were created. The OLD pinning made _backfill_missing_items
    blind to new stages/items. After this helper runs, the run points
    to the current template and _backfill_missing_items can add the
    new items.

    NOTE: Only called from get_or_create_floor_run and
    get_or_create_unit_run. The other 17 mutation endpoints
    (approve/reject/override/submit/update_item/reject_item) keep
    using `_get_template(db, run=run, ...)` — by the time they fire,
    the run was already upgraded by the get_or_create call that
    loaded it. Race window: if admin edits the template while a
    user has the page open, the next mutation uses the old template
    until the page reloads. Acceptable.
    """
    current = await _get_template(db, project_id=project_id)
    current_id = (current or {}).get("id")
    run_version_id = run.get("template_version_id")

    if not current_id or run_version_id == current_id:
        return current  # No-op — already current OR no project template

    now = _now()
    actor_id = actor.get("id") if actor else None
    new_template_id = current.get("template_id") or current_id

    await db.qc_runs.update_one(
        {"id": run["id"]},
        {"$set": {
            "template_version_id": current_id,
            "template_id": new_template_id,
            "template_upgraded_at": now,
            "template_upgraded_by": actor_id,
            "template_upgraded_from": run_version_id,
        }},
    )
    # Refresh local copy so caller sees upgraded fields without re-fetch
    run["template_version_id"] = current_id
    run["template_id"] = new_template_id
    run["template_upgraded_at"] = now
    run["template_upgraded_by"] = actor_id
    run["template_upgraded_from"] = run_version_id

    try:
        await _audit("qc_run", run["id"], "template_upgraded", actor_id, {
            "from": run_version_id,
            "to": current_id,
            "project_id": project_id,
        })
    except Exception as e:
        logger.warning(f"[#601] audit failed for run={run['id']}: {e}")

    logger.info(
        f"[#601] upgraded run={run['id']} "
        f"template {run_version_id} → {current_id}"
    )
    return current


def _build_item_map(tpl):
    m = {}
    for stage in tpl["stages"]:
        for item in stage["items"]:
            m[item["id"]] = {**item, "stage_id": stage["id"]}
    return m


def _get_prework_stages(tpl):
    stages = set()
    for s in tpl["stages"]:
        for item in s["items"]:
            if item.get("pre_work_documentation"):
                stages.add(s["id"])
                break
    return stages


def _get_valid_stage_codes(tpl):
    return {s["id"] for s in tpl["stages"]}


def _get_stage_labels_from_tpl(tpl):
    return [
        {"code": s["id"], "label_he": s["title"]}
        for s in tpl["stages"]
    ]


def _get_stage_icon(tpl, stage_id):
    for s in tpl["stages"]:
        if s["id"] == stage_id:
            if s.get("icon"):
                return s["icon"]
            break
    return STAGE_ICONS.get(stage_id, "📋")


async def _ensure_inline_prework_items(run_id, run_items, db, tpl, run_scope="floor"):
    prework_stages = _get_prework_stages(tpl)
    existing_ids = {(it["stage_id"], it["item_id"]) for it in run_items}
    to_insert = []
    for stage in tpl["stages"]:
        if stage.get("scope", "floor") != run_scope:
            continue
        if stage["id"] not in prework_stages:
            continue
        for item in stage["items"]:
            if not item.get("pre_work_documentation"):
                continue
            if (stage["id"], item["id"]) in existing_ids:
                continue
            to_insert.append({
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "stage_id": stage["id"],
                "item_id": item["id"],
                "status": "pending",
                "note": "",
                "photos": [],
                "updated_by": None,
                "updated_at": None,
            })
    if not to_insert:
        return run_items
    try:
        await db.qc_items.insert_many(to_insert, ordered=False)
    except Exception:
        pass
    updated = await db.qc_items.find({"run_id": run_id}, {"_id": 0}).to_list(500)
    created_ids = [f"{d['stage_id']}/{d['item_id']}" for d in to_insert]
    logger.info(f"[QC:BACKFILL] run={run_id} created {len(to_insert)} inline prework items: {created_ids}")
    return updated


async def _backfill_missing_items(run_id, run_items, db, tpl, run_scope="floor"):
    existing_ids = {(it["stage_id"], it["item_id"]) for it in run_items}
    to_insert = []
    for stage in tpl["stages"]:
        if stage.get("scope", "floor") != run_scope:
            continue
        for item in stage["items"]:
            if (stage["id"], item["id"]) in existing_ids:
                continue
            to_insert.append({
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "stage_id": stage["id"],
                "item_id": item["id"],
                "status": "pending",
                "note": "",
                "photos": [],
                "updated_by": None,
                "updated_at": None,
            })
    if not to_insert:
        return run_items
    try:
        await db.qc_items.insert_many(to_insert, ordered=False)
    except Exception:
        pass
    run_items = await db.qc_items.find({"run_id": run_id}, {"_id": 0}).to_list(500)
    created_ids = [f"{d['stage_id']}/{d['item_id']}" for d in to_insert]
    logger.info(f"[QC:BACKFILL] run={run_id} scope={run_scope} created {len(to_insert)} missing items: {created_ids}")
    return run_items


VALID_STAGE_STATUSES = {"draft", "ready", "pending_review", "approved", "rejected", "reopened"}


async def _check_qc_access(user, project_id):
    role = await _get_project_role(user, project_id)
    if role not in QC_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="אין הרשאה לצפות בבקרת ביצוע")
    return role


def _compute_stage_status(stage_items, stage_id, stage_statuses, tpl=None):
    stored = stage_statuses.get(stage_id)
    if stored in ("pending_review", "approved", "rejected", "reopened"):
        return stored

    src = tpl if tpl else FLOOR_TEMPLATE
    tpl_stage = None
    for s in src["stages"]:
        if s["id"] == stage_id:
            tpl_stage = s
            break
    if not tpl_stage:
        return "draft"

    if not stage_items:
        return "draft"

    all_marked = all(i.get("status") in ("pass", "fail") for i in stage_items)
    if not all_marked:
        any_marked = any(i.get("status") in ("pass", "fail") for i in stage_items)
        return "draft" if not any_marked else "draft"

    tpl_items_map = {ti["id"]: ti for ti in tpl_stage["items"]}
    for item in stage_items:
        tpl_item = tpl_items_map.get(item.get("item_id"), {})
        if tpl_item.get("required_photo") and not item.get("photos"):
            return "draft"
        if item.get("status") == "fail" and not (item.get("note") or "").strip():
            return "draft"

    return "ready"


def _compute_floor_badge(stages_data, stage_statuses):
    if not stages_data:
        return "not_started"

    has_any_marked = False
    all_approved = True
    any_approved = False
    any_rejected = False
    all_pending_review = True
    any_pending_review = False

    for stage in stages_data:
        stage_id = stage["id"]
        status = stage.get("computed_status", "draft")
        if status == "approved":
            any_approved = True
        else:
            all_approved = False
        if status == "rejected":
            any_rejected = True
        if status == "pending_review":
            any_pending_review = True
        else:
            all_pending_review = False
        if stage.get("done", 0) > 0 or status != "draft":
            has_any_marked = True

    if all_approved and has_any_marked:
        return "approved"
    if any_rejected:
        return "rejected"
    if all_pending_review and has_any_marked:
        return "submitted"
    if any_pending_review:
        return "pending_review"
    if has_any_marked:
        return "in_progress"
    return "not_started"


# ──────────────────────────────────────────────────────────────────────
# BATCH E (2026-05-11) — Unit-scope stage aggregation helpers
# Per-floor and batch helpers compute per-stage status by aggregating
# across unit runs on a floor. Used by /qc/floors/{floor_id}/run and
# /qc/floors/batch-status to include unit-scope stages in floor badge
# computation.
#
# Status priority: rejected > approved > in_progress > not_started.
# Rejected = work failed QC, NOT progress; ANY rejection on ANY unit
# propagates to the stage's badge and from there to the floor badge
# via _compute_floor_badge (which already treats "rejected" as winning).
# ──────────────────────────────────────────────────────────────────────

def _aggregate_unit_stages_in_memory(project_tpl, unit_ids, runs_by_unit):
    """Pure function — given units and their unit-scope runs (already
    fetched), compute per-stage aggregated status. No DB access.

    Shared between per-floor and batch versions so the logic stays
    single-sourced. Output shape mirrors floor-scope `stages_data` so
    `_compute_floor_badge` can consume the combined list directly.
    """
    unit_stages = [s for s in project_tpl["stages"]
                   if s.get("scope") == "unit"
                   and len(s.get("items", [])) > 0]

    total_units = len(unit_ids)
    stages_data = []

    for stage in unit_stages:
        stage_id = stage["id"]
        approved = 0
        in_progress = 0
        not_started = 0
        rejected = 0

        for unit_id in unit_ids:
            run = runs_by_unit.get(unit_id)
            if not run:
                not_started += 1
                continue
            stage_status = run.get("stage_statuses", {}).get(stage_id, "draft")
            if stage_status == "approved":
                approved += 1
            elif stage_status == "rejected":
                rejected += 1
            elif stage_status in ("draft", "not_started"):
                not_started += 1
            else:
                # in_progress, ready, submitted, pending_review — actively in flight
                in_progress += 1

        if rejected > 0:
            computed = "rejected"
        elif approved == total_units and total_units > 0:
            computed = "approved"
        elif approved == 0 and in_progress == 0:
            computed = "not_started"
        else:
            computed = "in_progress"

        stages_data.append({
            "id": stage_id,
            "done": approved + in_progress + rejected,
            "computed_status": computed,
            "_scope": "unit",
            "_approved_units": approved,
            "_in_progress_units": in_progress,
            "_not_started_units": not_started,
            "_rejected_units": rejected,
            "_total_units": total_units,
        })

    return stages_data


async def _compute_unit_scope_stage_statuses(db, project_tpl, floor_id, floor=None):
    """Per-floor version. 2 DB queries (units + unit-runs). Returns []
    when the floor has no units (overlaps with Batch D's empty-stage
    filter — both sides safe).
    """
    if floor is None:
        floor = await db.floors.find_one(
            {"id": floor_id, "archived": {"$ne": True}},
            {"_id": 0}
        )
        if not floor:
            return []

    units = await db.units.find(
        {"floor_id": floor_id, "archived": {"$ne": True}},
        {"_id": 0, "id": 1}
    ).to_list(500)
    unit_ids = [u["id"] for u in units]

    if not unit_ids:
        return []

    unit_runs = await db.qc_runs.find(
        {"unit_id": {"$in": unit_ids}, "scope": "unit"},
        {"_id": 0, "id": 1, "unit_id": 1, "stage_statuses": 1}
    ).to_list(1000)
    runs_by_unit = {r["unit_id"]: r for r in unit_runs}

    return _aggregate_unit_stages_in_memory(project_tpl, unit_ids, runs_by_unit)


async def _compute_unit_scope_stage_statuses_batch(db, project_tpl, floor_ids):
    """Batch version. 2 DB queries TOTAL regardless of N floors:
      1. All units across all floors via single $in.
      2. All unit-scope runs for those units via single $in.
    Then aggregate per-floor in memory. Replaces what would have been
    N*2 round trips inside the per-floor loop in batch-status.
    """
    if not floor_ids:
        return {}

    all_units = await db.units.find(
        {"floor_id": {"$in": floor_ids}, "archived": {"$ne": True}},
        {"_id": 0, "id": 1, "floor_id": 1}
    ).to_list(2000)

    units_by_floor = {}
    all_unit_ids = []
    for u in all_units:
        units_by_floor.setdefault(u["floor_id"], []).append(u["id"])
        all_unit_ids.append(u["id"])

    runs_by_unit = {}
    if all_unit_ids:
        all_runs = await db.qc_runs.find(
            {"unit_id": {"$in": all_unit_ids}, "scope": "unit"},
            {"_id": 0, "id": 1, "unit_id": 1, "stage_statuses": 1}
        ).to_list(2000)
        runs_by_unit = {r["unit_id"]: r for r in all_runs}

    result = {}
    for fid in floor_ids:
        unit_ids = units_by_floor.get(fid, [])
        if not unit_ids:
            result[fid] = []
            continue
        result[fid] = _aggregate_unit_stages_in_memory(project_tpl, unit_ids, runs_by_unit)

    return result


def _build_stage_summary(floor_stages_data, unit_stages_data):
    """Combine floor-scope + unit-scope stages_data into a single
    summary dict for the frontend. Counts of each computed_status.
    `pending_review_stages` rolls up both `pending_review` and
    `submitted` (UI treats them as one bucket).
    """
    all_stages = floor_stages_data + unit_stages_data
    return {
        "total_stages": len(all_stages),
        "approved_stages": sum(1 for s in all_stages if s["computed_status"] == "approved"),
        "in_progress_stages": sum(1 for s in all_stages if s["computed_status"] == "in_progress"),
        "not_started_stages": sum(1 for s in all_stages if s["computed_status"] == "not_started"),
        "pending_review_stages": sum(1 for s in all_stages if s["computed_status"] in ("pending_review", "submitted")),
        "rejected_stages": sum(1 for s in all_stages if s["computed_status"] == "rejected"),
    }


def _resolve_photo_url(raw_url):
    if raw_url and raw_url.startswith("s3://"):
        from services.object_storage import generate_url as obj_generate_url
        return obj_generate_url(raw_url)
    return raw_url


def _enrich_items(stage_items, tpl_stage, viewer_id=None, viewer_role=None):
    tpl_item_map = {ti["id"]: ti for ti in tpl_stage["items"]}
    is_pm = viewer_role in PM_ROLES if viewer_role else False
    enriched = []
    for si in sorted(stage_items, key=lambda x: tpl_item_map.get(x.get("item_id"), {}).get("order", 99)):
        tpl_item = tpl_item_map.get(si.get("item_id"), {})

        photos = si.get("photos", [])
        enriched_photos = []
        for p in photos:
            photo_out = {
                "id": p.get("id"),
                "url": _resolve_photo_url(p.get("url")),
                "uploaded_at": p.get("uploaded_at"),
                "uploaded_by": p.get("uploaded_by"),
            }
            if is_pm or p.get("uploaded_by") == viewer_id:
                photo_out["uploaded_by_name"] = p.get("uploaded_by_name", "")
            else:
                photo_out["uploaded_by_name"] = None
            enriched_photos.append(photo_out)

        rejection = si.get("reviewer_rejection")
        rejection_out = None
        if rejection:
            rejection_out = {
                "at": rejection.get("at"),
                "reason": rejection.get("reason", ""),
            }
            if is_pm or rejection.get("by") == viewer_id:
                rejection_out["by_name"] = rejection.get("by_name", "")
            else:
                rejection_out["by_name"] = None

        item_out = {
            "id": si["id"],
            "item_id": si.get("item_id"),
            "title": tpl_item.get("title", si.get("item_id")),
            "status": si.get("status", "pending"),
            "note": si.get("note", ""),
            "photos": enriched_photos,
            "required_photo": tpl_item.get("required_photo", False),
            "required_note": tpl_item.get("required_note", False),
            "updated_by": si.get("updated_by"),
            "updated_at": si.get("updated_at"),
            "reviewer_rejection": rejection_out,
        }
        if tpl_item.get("pre_work_documentation"):
            item_out["pre_work_documentation"] = True
        if is_pm or si.get("updated_by") == viewer_id:
            item_out["updated_by_name"] = si.get("updated_by_name", "")
        else:
            item_out["updated_by_name"] = None

        enriched.append(item_out)
    return enriched


class QCItemUpdate(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = None


@router.get("/templates")
async def list_templates(user: dict = Depends(get_current_user)):
    db = get_db()
    tpl = await _get_template(db)
    return [{"id": tpl["id"], "name": tpl["name"], "stages_count": len(tpl["stages"])}]


@router.get("/floors/{floor_id}/run")
async def get_or_create_floor_run(floor_id: str, user: dict = Depends(get_current_user)):
    db = get_db()

    floor = await db.floors.find_one({"id": floor_id, "archived": {"$ne": True}}, {"_id": 0})
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")

    building = await db.buildings.find_one({"id": floor["building_id"], "archived": {"$ne": True}}, {"_id": 0})
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")

    project_id = building["project_id"]
    role = await _check_qc_access(user, project_id)
    can_edit = role in MANAGEMENT_ROLES

    run = await db.qc_runs.find_one(
        {"floor_id": floor_id, "scope": {"$ne": "unit"}},
        {"_id": 0}
    )

    if not run:
        tpl = await _get_template(db, project_id=project_id)
        tpl_id, tpl_version_id = _template_ids(tpl)
        run_id = str(uuid.uuid4())
        now = _now()
        items = []
        for stage in tpl["stages"]:
            if stage.get("scope", "floor") != "floor":
                continue
            for item in stage["items"]:
                items.append({
                    "id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "stage_id": stage["id"],
                    "item_id": item["id"],
                    "status": "pending",
                    "note": "",
                    "photos": [],
                    "updated_by": None,
                    "updated_at": None,
                })

        run = {
            "id": run_id,
            "project_id": project_id,
            "building_id": building["id"],
            "floor_id": floor_id,
            "template_id": tpl_id,
            "template_version_id": tpl_version_id,
            "scope": "floor",
            "stage_statuses": {},
            "created_at": now,
            "created_by": user["id"],
        }
        await db.qc_runs.insert_one(run)
        if items:
            await db.qc_items.insert_many(items)

        run.pop("_id", None)
        logger.info(f"[QC] Created run {run_id} for floor {floor_id} tpl_version={tpl_version_id} with {len(items)} items")

    # #601 — upgrade stale runs to current template before backfill,
    # so admin's recent template additions actually create items.
    tpl = await _resolve_run_template_with_upgrade(db, run, project_id, user)
    stage_statuses = run.get("stage_statuses", {})
    run_items = await db.qc_items.find({"run_id": run["id"]}, {"_id": 0}).to_list(500)
    run_items = await _ensure_inline_prework_items(run["id"], run_items, db, tpl)
    run_items = await _backfill_missing_items(run["id"], run_items, db, tpl, run_scope="floor")
    stages_out = []
    items_by_stage = {}
    for it in run_items:
        items_by_stage.setdefault(it.get("stage_id"), []).append(it)

    effective_stages = [s for s in tpl["stages"] if s.get("scope", "floor") == "floor"]

    total_pass = 0
    total_fail = 0
    total_pending = 0

    for stage in effective_stages:
        stage_items = items_by_stage.get(stage["id"], [])
        enriched = _enrich_items(stage_items, stage, viewer_id=user["id"], viewer_role=role)

        done_count = sum(1 for i in enriched if i["status"] in ("pass", "fail"))
        pass_count = sum(1 for i in enriched if i["status"] == "pass")
        fail_count = sum(1 for i in enriched if i["status"] == "fail")
        pending_count = sum(1 for i in enriched if i["status"] == "pending")
        total_pass += pass_count
        total_fail += fail_count
        total_pending += pending_count

        computed_status = _compute_stage_status(stage_items, stage["id"], stage_statuses, tpl=tpl)

        all_marked = len(enriched) > 0 and all(i["status"] in ("pass", "fail") for i in enriched)
        stage_out = {
            "id": stage["id"],
            "title": stage["title"],
            "order": stage["order"],
            "scope": stage.get("scope", "floor"),
            "items": enriched,
            "total": len(enriched),
            "done": done_count,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pending_count": pending_count,
            "computed_status": computed_status,
            "is_completable": all_marked,
        }
        if stage.get("pre_work_documentation"):
            stage_out["pre_work_documentation"] = True
        has_prework_items = any(item.get("pre_work_documentation") for item in stage.get("items", []))
        if has_prework_items:
            stage_out["has_prework_items"] = True
        stages_out.append(stage_out)

    total_items = total_pass + total_fail + total_pending

    # BATCH E (2026-05-11) — include unit-scope stages in floor badge
    # and add stage_summary block. Existing `floor_badge` field becomes
    # CORRECT for free; consumers reading it get the fix automatically.
    floor_stages_data = [
        {"id": s["id"], "done": s.get("done", 0),
         "computed_status": s.get("computed_status", "draft"),
         "_scope": "floor"}
        for s in stages_out
    ]
    unit_stages_data = await _compute_unit_scope_stage_statuses(
        db, tpl, floor_id, floor=floor
    )
    combined_stages_data = floor_stages_data + unit_stages_data
    floor_badge = _compute_floor_badge(combined_stages_data, stage_statuses)
    stage_summary = _build_stage_summary(floor_stages_data, unit_stages_data)

    return {
        "run": {
            "id": run["id"],
            "project_id": run["project_id"],
            "building_id": run["building_id"],
            "floor_id": run["floor_id"],
            "template_id": run["template_id"],
            "stage_statuses": stage_statuses,
            "created_at": run.get("created_at"),
        },
        "template_name": tpl["name"],
        "stages": stages_out,
        "can_edit": can_edit,
        "role": role,
        "building_name": building.get("name", ""),
        "floor_name": floor.get("name", ""),
        "summary": {
            "total": total_items,
            "pass": total_pass,
            "fail": total_fail,
            "pending": total_pending,
        },
        "stage_summary": stage_summary,
        "floor_badge": floor_badge,
    }


@router.get("/units/{unit_id}/run")
async def get_or_create_unit_run(unit_id: str, user: dict = Depends(get_current_user)):
    db = get_db()

    unit = await db.units.find_one({"id": unit_id}, {"_id": 0})
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    floor = await db.floors.find_one({"id": unit["floor_id"], "archived": {"$ne": True}}, {"_id": 0})
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")

    building = await db.buildings.find_one({"id": floor["building_id"], "archived": {"$ne": True}}, {"_id": 0})
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")

    project_id = building["project_id"]
    role = await _check_qc_access(user, project_id)
    can_edit = role in MANAGEMENT_ROLES

    run = await db.qc_runs.find_one(
        {"unit_id": unit_id, "scope": "unit"},
        {"_id": 0}
    )

    if not run:
        tpl = await _get_template(db, project_id=project_id)
        tpl_id, tpl_version_id = _template_ids(tpl)
        unit_stages = [s for s in tpl["stages"] if s.get("scope") == "unit"]
        run_id = str(uuid.uuid4())
        now = _now()
        items = []
        for stage in unit_stages:
            for item in stage["items"]:
                items.append({
                    "id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "stage_id": stage["id"],
                    "item_id": item["id"],
                    "status": "pending",
                    "note": "",
                    "photos": [],
                    "updated_by": None,
                    "updated_at": None,
                })

        run = {
            "id": run_id,
            "project_id": project_id,
            "building_id": building["id"],
            "floor_id": floor["id"],
            "unit_id": unit_id,
            "template_id": tpl_id,
            "template_version_id": tpl_version_id,
            "scope": "unit",
            "stage_statuses": {},
            "created_at": now,
            "created_by": user["id"],
        }
        await db.qc_runs.insert_one(run)
        if items:
            await db.qc_items.insert_many(items)

        run.pop("_id", None)
        logger.info(f"[QC] Created unit run {run_id} for unit {unit_id} tpl_version={tpl_version_id} with {len(items)} items")

    # #601 — upgrade stale runs to current template before backfill.
    tpl = await _resolve_run_template_with_upgrade(db, run, project_id, user)
    unit_stages = [s for s in tpl["stages"] if s.get("scope") == "unit"]

    stage_statuses = run.get("stage_statuses", {})
    run_items = await db.qc_items.find({"run_id": run["id"]}, {"_id": 0}).to_list(500)

    existing_stage_item_ids = {(it["stage_id"], it["item_id"]) for it in run_items}
    backfill = []
    for stage in unit_stages:
        for item in stage["items"]:
            if (stage["id"], item["id"]) not in existing_stage_item_ids:
                backfill.append({
                    "id": str(uuid.uuid4()),
                    "run_id": run["id"],
                    "stage_id": stage["id"],
                    "item_id": item["id"],
                    "status": "pending",
                    "note": "",
                    "photos": [],
                    "updated_by": None,
                    "updated_at": None,
                })
    if backfill:
        await db.qc_items.insert_many(backfill)
        run_items.extend(backfill)
        logger.info(f"[QC] Backfilled {len(backfill)} items for unit run {run['id']}")

    run_items = await _ensure_inline_prework_items(run["id"], run_items, db, tpl, run_scope="unit")

    stages_out = []
    items_by_stage = {}
    for it in run_items:
        items_by_stage.setdefault(it.get("stage_id"), []).append(it)

    total_pass = 0
    total_fail = 0
    total_pending = 0

    for stage in unit_stages:
        stage_items = items_by_stage.get(stage["id"], [])
        enriched = _enrich_items(stage_items, stage, viewer_id=user["id"], viewer_role=role)

        done_count = sum(1 for i in enriched if i["status"] in ("pass", "fail"))
        pass_count = sum(1 for i in enriched if i["status"] == "pass")
        fail_count = sum(1 for i in enriched if i["status"] == "fail")
        pending_count = sum(1 for i in enriched if i["status"] == "pending")
        total_pass += pass_count
        total_fail += fail_count
        total_pending += pending_count

        computed_status = _compute_stage_status(stage_items, stage["id"], stage_statuses, tpl=tpl)

        all_marked = len(enriched) > 0 and all(i["status"] in ("pass", "fail") for i in enriched)
        stage_out = {
            "id": stage["id"],
            "title": stage["title"],
            "order": stage["order"],
            "scope": "unit",
            "items": enriched,
            "total": len(enriched),
            "done": done_count,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pending_count": pending_count,
            "computed_status": computed_status,
            "is_completable": all_marked,
        }
        if stage.get("pre_work_documentation"):
            stage_out["pre_work_documentation"] = True
        has_prework_items = any(item.get("pre_work_documentation") for item in stage.get("items", []))
        if has_prework_items:
            stage_out["has_prework_items"] = True
        stages_out.append(stage_out)

    total_items = total_pass + total_fail + total_pending

    return {
        "run": {
            "id": run["id"],
            "project_id": run["project_id"],
            "building_id": run["building_id"],
            "floor_id": run["floor_id"],
            "unit_id": unit_id,
            "template_id": run["template_id"],
            "scope": "unit",
            "stage_statuses": stage_statuses,
            "created_at": run.get("created_at"),
        },
        "template_name": tpl["name"],
        "stages": stages_out,
        "can_edit": can_edit,
        "role": role,
        "building_name": building.get("name", ""),
        "floor_name": floor.get("name", ""),
        "unit_name": unit.get("name", unit.get("unit_no", "")),
        "summary": {
            "total": total_items,
            "pass": total_pass,
            "fail": total_fail,
            "pending": total_pending,
        },
    }


@router.get("/floors/{floor_id}/units-status")
async def get_floor_units_status(floor_id: str, user: dict = Depends(get_current_user)):
    """Per-stage rollup of unit-scope progress for a floor.

    Returns a list of unit-scope stages (in template `order`), each with
    per-unit breakdown of completion. Replaces the old single-stage
    behavior that ignored all but the first unit-scope stage.

    Used by FloorDetailPage to render one card per unit-scope stage in
    the floor's stage grid.
    """
    db = get_db()

    floor = await db.floors.find_one({"id": floor_id, "archived": {"$ne": True}}, {"_id": 0})
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")

    building = await db.buildings.find_one({"id": floor["building_id"], "archived": {"$ne": True}}, {"_id": 0})
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")

    project_id = building["project_id"]
    await _check_qc_access(user, project_id)

    units = await db.units.find(
        {"floor_id": floor_id, "archived": {"$ne": True}},
        {"_id": 0}
    ).to_list(200)
    units.sort(key=lambda u: _natural_sort_key(u.get("unit_no") or u.get("name") or ""))
    unit_ids = [u["id"] for u in units]

    unit_runs = {}
    if unit_ids:
        runs_cursor = db.qc_runs.find(
            {"unit_id": {"$in": unit_ids}, "scope": "unit"},
            {"_id": 0}
        )
        async for r in runs_cursor:
            unit_runs[r["unit_id"]] = r

    run_ids = [r["id"] for r in unit_runs.values()]

    # Template — all unit-scope stages, IN TEMPLATE ORDER.
    # AMENDMENT (Replit feedback 2026-05-04): explicit sort by `order`
    # field instead of relying on Python list insertion order. The
    # `order` field is admin-controlled via the template editor and is
    # the authoritative source of stage sequence. Defensive against any
    # future change to template editor save behavior.
    tpl = await _get_template(db, project_id=project_id)
    unit_stages_list = sorted(
        [s for s in tpl["stages"] if s.get("scope") == "unit"],
        key=lambda s: s.get("order", 999)
    )

    if not unit_stages_list:
        return {
            "floor_id": floor_id,
            "floor_name": floor.get("name", ""),
            "building_id": building["id"],
            "building_name": building.get("name", ""),
            "stages": [],
        }

    unit_stage_ids = [s["id"] for s in unit_stages_list]

    # Single query — fetch ALL items for ALL unit-scope stages on these runs.
    items_by_run_and_stage = {}  # {(run_id, stage_id): [items]}
    if run_ids:
        all_items = await db.qc_items.find(
            {"run_id": {"$in": run_ids}, "stage_id": {"$in": unit_stage_ids}},
            {"_id": 0, "run_id": 1, "stage_id": 1, "status": 1}
        ).to_list(50000)
        for item in all_items:
            key = (item["run_id"], item["stage_id"])
            items_by_run_and_stage.setdefault(key, []).append(item)

    # Build per-stage rollup, in template order.
    stages_out = []
    for stage in unit_stages_list:
        stage_id = stage["id"]
        stage_items_count = len(stage.get("items", []))

        units_breakdown = []
        for unit in units:
            uid = unit["id"]
            run = unit_runs.get(uid)

            if not run:
                units_breakdown.append({
                    "unit_id": uid,
                    "unit_name": unit.get("name", ""),
                    "unit_no": unit.get("unit_no", ""),
                    "status": "not_started",
                    "pass_count": 0,
                    "fail_count": 0,
                    "handled_count": 0,
                    "total": stage_items_count,
                })
                continue

            key = (run["id"], stage_id)
            stage_items = items_by_run_and_stage.get(key, [])
            pass_count = sum(1 for i in stage_items if i.get("status") == "pass")
            fail_count = sum(1 for i in stage_items if i.get("status") == "fail")
            handled_count = pass_count + fail_count

            stage_statuses = run.get("stage_statuses", {})
            stored_status = stage_statuses.get(stage_id, "draft")

            if stored_status == "approved":
                unit_status = "approved"
            elif handled_count > 0 or stored_status not in ("draft", "not_started"):
                unit_status = "in_progress"
            else:
                unit_status = "not_started"

            units_breakdown.append({
                "unit_id": uid,
                "unit_name": unit.get("name", ""),
                "unit_no": unit.get("unit_no", ""),
                "status": unit_status,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "handled_count": handled_count,
                "total": stage_items_count,
            })

        total_units = len(units)
        approved_units = sum(1 for u in units_breakdown if u["status"] == "approved")
        in_progress_units = sum(1 for u in units_breakdown if u["status"] == "in_progress")
        not_started_units = sum(1 for u in units_breakdown if u["status"] == "not_started")

        total_items_handled = sum(u["handled_count"] for u in units_breakdown)
        total_items_possible = total_units * stage_items_count
        pct = int((total_items_handled / total_items_possible) * 100) if total_items_possible > 0 else 0

        stages_out.append({
            "stage_id": stage_id,
            "stage_title": stage.get("title", ""),
            "stage_order": stage.get("order", 0),
            "items_per_unit": stage_items_count,
            # AMENDMENT (Replit feedback 2026-05-04): is_empty flag for
            # stages with no items. Frontend shows a friendly
            # "אין פריטי בדיקה" message instead of misleading "0/X".
            "is_empty": stage_items_count == 0,
            "total_units": total_units,
            "approved_units": approved_units,
            "in_progress_units": in_progress_units,
            "not_started_units": not_started_units,
            "total_items_handled": total_items_handled,
            "total_items_possible": total_items_possible,
            "completion_pct": pct,
            "units": units_breakdown,
        })

    return {
        "floor_id": floor_id,
        "floor_name": floor.get("name", ""),
        "building_id": building["id"],
        "building_name": building.get("name", ""),
        "stages": stages_out,
    }


@router.get("/run/{run_id}")
async def get_run_detail(run_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    role = await _check_qc_access(user, run["project_id"])
    can_edit = role in MANAGEMENT_ROLES

    stage_statuses = run.get("stage_statuses", {})
    run_items = await db.qc_items.find({"run_id": run_id}, {"_id": 0}).to_list(500)
    run_scope = run.get("scope", "floor")
    tpl = await _get_template(db, run=run, project_id=run.get("project_id"))
    run_items = await _ensure_inline_prework_items(run_id, run_items, db, tpl, run_scope=run_scope)
    run_items = await _backfill_missing_items(run_id, run_items, db, tpl, run_scope=run_scope)
    items_by_stage = {}
    for it in run_items:
        items_by_stage.setdefault(it.get("stage_id"), []).append(it)

    effective_stages = [s for s in tpl["stages"] if s.get("scope", "floor") == run_scope]

    stages_out = []
    total_pass = 0
    total_fail = 0
    total_pending = 0

    for stage in effective_stages:
        stage_items = items_by_stage.get(stage["id"], [])
        enriched = _enrich_items(stage_items, stage, viewer_id=user["id"], viewer_role=role)

        done_count = sum(1 for i in enriched if i["status"] in ("pass", "fail"))
        pass_count = sum(1 for i in enriched if i["status"] == "pass")
        fail_count = sum(1 for i in enriched if i["status"] == "fail")
        pending_count = sum(1 for i in enriched if i["status"] == "pending")
        total_pass += pass_count
        total_fail += fail_count
        total_pending += pending_count

        computed_status = _compute_stage_status(stage_items, stage["id"], stage_statuses, tpl=tpl)

        all_marked = len(enriched) > 0 and all(i["status"] in ("pass", "fail") for i in enriched)
        stage_out = {
            "id": stage["id"],
            "title": stage["title"],
            "order": stage["order"],
            "scope": stage.get("scope", "floor"),
            "items": enriched,
            "total": len(enriched),
            "done": done_count,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pending_count": pending_count,
            "computed_status": computed_status,
            "is_completable": all_marked,
        }
        if stage.get("pre_work_documentation"):
            stage_out["pre_work_documentation"] = True
        has_prework_items = any(item.get("pre_work_documentation") for item in stage.get("items", []))
        if has_prework_items:
            stage_out["has_prework_items"] = True
        stages_out.append(stage_out)

    total_items = total_pass + total_fail + total_pending

    run_out = {
        "id": run["id"],
        "project_id": run["project_id"],
        "building_id": run["building_id"],
        "floor_id": run["floor_id"],
        "template_id": run["template_id"],
        "scope": run.get("scope", "floor"),
        "stage_statuses": stage_statuses,
        "stage_actors": run.get("stage_actors", {}),
        "created_at": run.get("created_at"),
    }
    if run.get("unit_id"):
        run_out["unit_id"] = run["unit_id"]

    return {
        "run": run_out,
        "template_name": tpl["name"],
        "stages": stages_out,
        "can_edit": can_edit,
        "role": role,
        "summary": {
            "total": total_items,
            "pass": total_pass,
            "fail": total_fail,
            "pending": total_pending,
        },
    }


@router.get("/run/{run_id}/team-contacts")
async def get_team_contacts(run_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    project_id = run["project_id"]
    role = await _check_qc_access(user, project_id)

    is_approver = False
    if role not in MANAGEMENT_ROLES:
        approver_doc = await db.project_approvers.find_one(
            {"project_id": project_id, "user_id": user["id"], "active": True},
            {"_id": 0, "user_id": 1}
        )
        if not approver_doc:
            raise HTTPException(status_code=403, detail="אין הרשאה לצפות באנשי קשר")
        is_approver = True

    memberships = await db.project_memberships.find(
        {"project_id": project_id, "role": {"$in": list(NOTIFY_ELIGIBLE_ROLES)}},
        {"_id": 0, "user_id": 1, "role": 1}
    ).to_list(200)

    if not memberships:
        return {"contacts": []}

    user_ids = [m["user_id"] for m in memberships]
    users = await db.users.find(
        {"id": {"$in": user_ids}},
        {"_id": 0, "id": 1, "name": 1, "full_name": 1, "phone_e164": 1}
    ).to_list(len(user_ids))
    user_map = {u["id"]: u for u in users}

    contacts = []
    for m in memberships:
        u = user_map.get(m["user_id"])
        if not u:
            continue
        contacts.append({
            "user_id": m["user_id"],
            "name": u.get("name") or u.get("full_name") or "",
            "role": m.get("role", ""),
            "has_whatsapp": bool(u.get("phone_e164")),
        })

    return {"contacts": contacts}


VALID_QC_STATUSES = {"pending", "pass", "fail"}


@router.patch("/run/{run_id}/item/{item_id}")
async def update_qc_item(
    run_id: str,
    item_id: str,
    update: QCItemUpdate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    db = get_db()

    if update.status is None and update.note is None:
        raise HTTPException(status_code=400, detail="יש לשלוח לפחות שדה אחד לעדכון (status או note)")

    if update.status is not None and update.status not in VALID_QC_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(VALID_QC_STATUSES)}")

    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    role = await _check_qc_access(user, run["project_id"])
    if role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Only management can update QC items")

    item = await db.qc_items.find_one({"id": item_id, "run_id": run_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="QC item not found")

    stage_statuses = run.get("stage_statuses", {})
    stage_status = stage_statuses.get(item["stage_id"])
    if stage_status in ("pending_review", "approved"):
        raise HTTPException(status_code=403, detail="שלב זה נעול לאחר שליחה לאישור")

    effective_status = update.status if update.status is not None else item.get("status", "pending")
    effective_note = update.note if update.note is not None else (item.get("note") or "")

    tpl = await _get_template(db, run=run, project_id=run.get("project_id"))
    item_map = _build_item_map(tpl)

    if effective_status in ("pass", "fail"):
        tpl_item = item_map.get(item.get("item_id"), {})
        if tpl_item.get("required_photo") and not item.get("photos"):
            raise HTTPException(status_code=422, detail="חובה לצרף תמונה לפני סימון סעיף זה")

    if effective_status == "fail" and not effective_note.strip():
        raise HTTPException(status_code=422, detail={
            "error_code": "FAIL_REQUIRES_NOTE",
            "message": "סעיף מסומן לא תקין — חובה להוסיף הערה",
            "field": "note"
        })

    now = _now()
    actor = _actor_name(user)
    old_status = item.get("status", "pending")

    update_fields = {
        "updated_by": user["id"],
        "updated_by_name": actor,
        "updated_at": now,
    }
    if update.status is not None:
        update_fields["status"] = update.status
    if update.note is not None:
        update_fields["note"] = update.note

    update_ops = {"$set": update_fields}

    if item.get("reviewer_rejection"):
        has_status_change = update.status is not None and update.status != item.get("status", "pending")
        has_note_change = update.note is not None and update.note != (item.get("note") or "")
        if has_status_change or has_note_change:
            update_ops["$unset"] = {"reviewer_rejection": ""}

    result = await db.qc_items.update_one(
        {"id": item_id, "run_id": run_id},
        update_ops
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="QC item not found")

    tpl_item_id = item.get("item_id", "")
    await _audit("qc_item", item_id, "update", user["id"], {
        "run_id": run_id,
        "stage_id": item["stage_id"],
        "item_id": tpl_item_id,
        "item_title": item_map.get(tpl_item_id, {}).get("title", tpl_item_id),
        "from_status": old_status,
        "to_status": effective_status,
        "note": effective_note,
        "actor_name": actor,
    })

    updated = await db.qc_items.find_one({"id": item_id}, {"_id": 0})

    # #503 — best-effort matrix sync via FastAPI BackgroundTasks. Runs
    # AFTER the HTTP response is sent → QC client doesn't block on
    # sync's 2-3 DB ops (~100-300ms saved per item update). Wrapped in
    # try/except so any sync failure is logged-only and never affects
    # the QC write. T9 verifies this protection.
    stage_id_for_sync = item["stage_id"]
    project_id_for_sync = run["project_id"]
    actor_for_sync = {"id": user["id"], "name": _actor_name(user)}

    async def _run_sync():
        try:
            tpl_stage = next(
                (s for s in tpl["stages"] if s["id"] == stage_id_for_sync), {}
            )
            stage_scope = tpl_stage.get("scope", "floor")
            # #503-followup-2 — stage-level mapping. Pass stage_status
            # (None means "no decision yet" → mapping falls back to
            # item-level activity check). update_qc_item is per-item
            # activity, so for floor-scope we sync ONLY the affected
            # unit's cell (not all units on the floor) — that's the
            # narrow drift-C case where item carries unit_id.
            stage_status = run.get("stage_statuses", {}).get(stage_id_for_sync)
            # #503-followup-3 Bug B fix — fetch ALL items for the stage
            # (not just the one we updated). For floor-shared template
            # items (no unit_id field), every unit on the floor inherits
            # the same item list and must be synced together.
            items_all = await db.qc_items.find(
                {"run_id": run_id, "stage_id": stage_id_for_sync},
                {"_id": 0},
            ).to_list(2000)
            unit_ids = await _resolve_unit_ids_for_sync(
                db, run, items_all, stage_scope
            )
            items_have_unit_id = any(i.get("unit_id") for i in items_all)
            for uid in unit_ids:
                # If items carry unit_id (unit-scope), filter per-unit.
                # Otherwise (floor-shared template items), all units
                # share the same items list — Bug B fix.
                items_for_uid = (
                    [i for i in items_all if i.get("unit_id") == uid]
                    if items_have_unit_id
                    else items_all
                )
                await sync_qc_stage_to_matrix(
                    db,
                    project_id=project_id_for_sync,
                    unit_id=uid,
                    stage_id=stage_id_for_sync,
                    actor=actor_for_sync,
                    qc_items=items_for_uid,
                    stage_status=stage_status,
                    stage_scope=stage_scope,
                )
        except Exception as e:
            logger.warning(
                f"[#503] QC→matrix sync failed for stage_id={stage_id_for_sync}: {e}"
            )

    background_tasks.add_task(_run_sync)
    return updated


class ItemRejectBody(BaseModel):
    reason: str


async def _send_qc_rejection_wa(
    wa_client, to_phone: str, *,
    project_name: str, floor_name: str, stage_name: str,
    item_name: str, rejection_reason: str, button_path: str,
) -> bool:
    from config import WA_QC_REJECT_TEMPLATE_HE, WA_QC_REJECT_TEMPLATE_LANG

    if not wa_client or not wa_client.enabled:
        logger.info(f"[QC-REJECT-WA] Skipped — WhatsApp disabled")
        return False

    tpl_name = WA_QC_REJECT_TEMPLATE_HE
    tpl_lang = WA_QC_REJECT_TEMPLATE_LANG

    location_parts = [p for p in [floor_name] if p]
    location = " - ".join(location_parts) or ""

    components = [
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": project_name, "parameter_name": "project_name"},
                {"type": "text", "text": location, "parameter_name": "location"},
                {"type": "text", "text": stage_name, "parameter_name": "stage_name"},
                {"type": "text", "text": item_name, "parameter_name": "item_name"},
                {"type": "text", "text": rejection_reason, "parameter_name": "rejection_reason"},
            ],
        }
    ]
    if button_path:
        components.append({
            "type": "button",
            "sub_type": "url",
            "index": "0",
            "parameters": [{"type": "text", "text": f"{button_path}?src=wa"}],
        })

    body = {
        "messaging_product": "whatsapp",
        "to": to_phone.lstrip("+"),
        "type": "template",
        "template": {
            "name": tpl_name,
            "language": {"code": tpl_lang},
            "components": components,
        },
    }

    headers = {
        "Authorization": f"Bearer {wa_client.access_token}",
        "Content-Type": "application/json",
    }

    logger.info(
        f"[QC-REJECT-WA] template={tpl_name} lang={tpl_lang} to={mask_phone(to_phone)} "
        f"params=[project_name={project_name}, location={location}, stage_name={stage_name}, "
        f"item_name={item_name}, rejection_reason={rejection_reason[:60]}] "
        f"button_path={button_path}"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(wa_client.api_url, json=body, headers=headers)

    resp_text = resp.text[:500]
    if resp.status_code in (200, 201):
        data = resp.json()
        mid = data.get("messages", [{}])[0].get("id", "")
        logger.info(f"[QC-REJECT-WA] SUCCESS wamid={mid} to={mask_phone(to_phone)}")
        return True
    else:
        logger.warning(
            f"[QC-REJECT-WA] FAILED status={resp.status_code} to={mask_phone(to_phone)} "
            f"template={tpl_name} body={resp_text}"
        )
        return False


@router.post("/run/{run_id}/item/{item_id}/reject")
async def reject_qc_item(
    run_id: str,
    item_id: str,
    body: ItemRejectBody,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    db = get_db()

    if not (body.reason or "").strip():
        raise HTTPException(status_code=400, detail="יש לציין סיבת דחייה")

    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    item = await db.qc_items.find_one({"id": item_id, "run_id": run_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="QC item not found")

    tpl = await _get_template(db, run=run, project_id=run.get("project_id"))
    item_map = _build_item_map(tpl)
    stage_id = item["stage_id"]
    stage_statuses = run.get("stage_statuses", {})
    if stage_statuses.get(stage_id) != "pending_review":
        raise HTTPException(status_code=400, detail="ניתן לדחות סעיף רק כשהשלב ממתין לאישור")

    await _check_approver_authorization(user, run["project_id"], stage_id)

    now = _now()
    actor = _actor_name(user)

    old_status = item.get("status", "pending")

    returned_to_user_id = item.get("updated_by")
    returned_to_user_name = None
    stage_actors = run.get("stage_actors", {}).get(stage_id, {})
    if not returned_to_user_id or returned_to_user_id == user["id"]:
        returned_to_user_id = stage_actors.get("submitted_by")
    if returned_to_user_id and returned_to_user_id == user["id"]:
        returned_to_user_id = None
    if returned_to_user_id:
        target_user = await db.users.find_one({"id": returned_to_user_id}, {"_id": 0, "name": 1, "phone_e164": 1})
        if target_user:
            returned_to_user_name = target_user.get("name", "")
        else:
            returned_to_user_id = None

    rejection_obj = {
        "by": user["id"],
        "by_name": actor,
        "at": now,
        "reason": body.reason.strip(),
        "previous_status": old_status,
    }
    if returned_to_user_id:
        rejection_obj["returned_to_user_id"] = returned_to_user_id
        rejection_obj["returned_to_user_name"] = returned_to_user_name

    await db.qc_items.update_one(
        {"id": item_id, "run_id": run_id},
        {"$set": {
            "status": "fail",
            "reviewer_rejection": rejection_obj,
        }}
    )

    await db.qc_runs.update_one(
        {"id": run_id},
        {"$set": {
            f"stage_statuses.{stage_id}": "reopened",
            f"stage_actors.{stage_id}.reopened_by": user["id"],
            f"stage_actors.{stage_id}.reopened_by_name": actor,
            f"stage_actors.{stage_id}.reopened_at": now,
            f"stage_actors.{stage_id}.reopened_reason": f"דחיית סעיף: {body.reason.strip()}",
        }}
    )

    audit_data = {
        "run_id": run_id,
        "stage_id": stage_id,
        "item_id": item.get("item_id"),
        "item_title": item_map.get(item.get("item_id"), {}).get("title", item_id),
        "reason": body.reason.strip(),
        "actor_name": actor,
        "previous_status": old_status,
        "new_status": "fail",
    }
    if returned_to_user_id:
        audit_data["returned_to_user_id"] = returned_to_user_id
        audit_data["returned_to_user_name"] = returned_to_user_name
    await _audit("qc_item", item_id, "item_rejected", user["id"], audit_data)

    returned_to = None
    notified = False
    if returned_to_user_id:
        try:
            await _create_qc_notification(
                db, [returned_to_user_id],
                project_id=run["project_id"], stage_id=stage_id,
                floor_id=run.get("floor_id"), building_id=run.get("building_id"),
                stage_code=stage_id, stage_label_he=_stage_label(tpl, stage_id),
                actor_id=user["id"], actor_name_str=actor,
                action="item_rejected", reason=body.reason.strip(), run_id=run_id,
            )
            notified = True
        except Exception as e:
            logger.warning(f"[QC-REJECT] Failed to create in-app notification: {e}")

        if target_user and target_user.get("phone_e164"):
            try:
                engine = get_notification_engine()
                if engine and engine.wa_client:
                    project = await db.projects.find_one({"id": run["project_id"]}, {"_id": 0, "name": 1})
                    project_name = project.get("name", "") if project else ""
                    floor = await db.floors.find_one({"id": run.get("floor_id")}, {"_id": 0, "name": 1})
                    floor_name = floor.get("name", "") if floor else ""
                    stage_title = _stage_label(tpl, stage_id)
                    tpl_item_title = item_map.get(item.get("item_id"), {}).get("title", "")

                    button_path = (
                        f"projects/{run['project_id']}/qc/floors/{run.get('floor_id')}"
                        f"/run/{run_id}/stage/{stage_id}"
                    )

                    wa_sent = await _send_qc_rejection_wa(
                        engine.wa_client, target_user["phone_e164"],
                        project_name=project_name,
                        floor_name=floor_name,
                        stage_name=stage_title,
                        item_name=tpl_item_title or item_id,
                        rejection_reason=body.reason.strip(),
                        button_path=button_path,
                    )
                    if wa_sent:
                        notified = True
            except Exception as e:
                logger.warning(f"[QC-REJECT-WA] Failed: {e}")

        returned_to = {"user_id": returned_to_user_id, "user_name": returned_to_user_name, "notified": notified}

    # #503-followup-3 STOP-GATE 0.6 — reject_qc_item was unhooked.
    # Per-item rejection cascades stage_statuses[stage_id]="reopened"
    # (set earlier in this handler). Sync to matrix so the cell flips
    # away from any prior approved/pending state to in_progress (or
    # empty if no items remain touched).
    project_id_for_sync = run["project_id"]
    actor_for_sync = {"id": user["id"], "name": actor}

    async def _run_sync_reject_item():
        try:
            tpl_stage = next(
                (s for s in tpl["stages"] if s["id"] == stage_id), {}
            )
            stage_scope = tpl_stage.get("scope", "floor")
            items_all = await db.qc_items.find(
                {"run_id": run_id, "stage_id": stage_id},
                {"_id": 0},
            ).to_list(2000)
            unit_ids = await _resolve_unit_ids_for_sync(
                db, run, items_all, stage_scope
            )
            items_have_unit_id = any(i.get("unit_id") for i in items_all)
            for uid in unit_ids:
                items_for_uid = (
                    [i for i in items_all if i.get("unit_id") == uid]
                    if items_have_unit_id
                    else items_all
                )
                await sync_qc_stage_to_matrix(
                    db,
                    project_id=project_id_for_sync,
                    unit_id=uid,
                    stage_id=stage_id,
                    actor=actor_for_sync,
                    qc_items=items_for_uid,
                    stage_status="reopened",
                    stage_scope=stage_scope,
                )
        except Exception as e:
            logger.warning(
                f"[#503] QC→matrix sync (reject_item) failed for stage_id={stage_id}: {e}"
            )

    background_tasks.add_task(_run_sync_reject_item)
    return {"ok": True, "message": "הסעיף נדחה — השלב נפתח מחדש לתיקון", "returned_to": returned_to}


ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_PHOTO_SIZE = 10 * 1024 * 1024


@router.post("/run/{run_id}/item/{item_id}/photo")
async def upload_qc_photo(
    run_id: str,
    item_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    db = get_db()

    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    role = await _check_qc_access(user, run["project_id"])
    if role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Only management can upload QC photos")

    item = await db.qc_items.find_one({"id": item_id, "run_id": run_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="QC item not found")

    stage_statuses = run.get("stage_statuses", {})
    stage_status = stage_statuses.get(item["stage_id"])
    if stage_status in ("pending_review", "approved"):
        raise HTTPException(status_code=403, detail="שלב זה נעול לאחר שליחה לאישור")

    validate_upload(file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES)
    content_type = file.content_type or ""
    if content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(status_code=400, detail="סוג קובץ לא נתמך. נתמכים: JPEG, PNG, WebP, HEIC")

    ext = content_type.split("/")[-1]
    if ext == "jpeg":
        ext = "jpg"
    photo_id = str(uuid.uuid4())
    filename = f"{photo_id}.{ext}"

    content = await file.read()
    if len(content) > MAX_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="הקובץ גדול מדי (מקסימום 10MB)")

    from services.object_storage import save_bytes as obj_save_bytes, generate_url as obj_generate_url
    stored_ref = obj_save_bytes(content, f"qc/{filename}", content_type)

    actor = _actor_name(user)
    photo_meta = {
        "id": photo_id,
        "url": stored_ref,
        "uploaded_at": _now(),
        "uploaded_by": user["id"],
        "uploaded_by_name": actor,
    }

    photo_update_ops = {"$push": {"photos": photo_meta}}
    if item.get("reviewer_rejection"):
        photo_update_ops["$unset"] = {"reviewer_rejection": ""}

    await db.qc_items.update_one(
        {"id": item_id, "run_id": run_id},
        photo_update_ops
    )

    tpl = await _get_template(db, run=run, project_id=run.get("project_id"))
    photo_item_map = _build_item_map(tpl)
    tpl_item_id = item.get("item_id", "")
    await _audit("qc_photo", photo_id, "upload", user["id"], {
        "run_id": run_id,
        "item_id": tpl_item_id,
        "stage_id": item["stage_id"],
        "item_title": photo_item_map.get(tpl_item_id, {}).get("title", tpl_item_id),
        "filename": filename,
        "actor_name": actor,
    })

    logger.info(f"[QC] Photo {photo_id} uploaded for item {item_id} in run {run_id}")
    return {**photo_meta, "url": _resolve_photo_url(stored_ref)}


@router.post("/run/{run_id}/stage/{stage_id}/submit")
async def submit_stage(
    run_id: str,
    stage_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    db = get_db()

    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    role = await _check_qc_access(user, run["project_id"])
    if role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Only management can submit stages")

    stage_statuses = run.get("stage_statuses", {})
    current = stage_statuses.get(stage_id)
    if current == "pending_review":
        raise HTTPException(status_code=400, detail="שלב זה כבר הוגש לאישור")
    if current == "approved":
        raise HTTPException(status_code=400, detail="שלב זה כבר אושר")
    if current not in (None, "draft", "ready", "rejected", "reopened"):
        raise HTTPException(status_code=400, detail="לא ניתן לשלוח שלב במצב הנוכחי")

    tpl = await _get_template(db, run=run, project_id=run.get("project_id"))
    tpl_stage = None
    for s in tpl["stages"]:
        if s["id"] == stage_id:
            tpl_stage = s
            break
    if not tpl_stage:
        raise HTTPException(status_code=404, detail="Stage not found in template")

    stage_items = await db.qc_items.find(
        {"run_id": run_id, "stage_id": stage_id}, {"_id": 0}
    ).to_list(100)

    if not stage_items:
        raise HTTPException(status_code=400, detail="לא נמצאו סעיפים בשלב זה")

    tpl_items_map = {ti["id"]: ti for ti in tpl_stage["items"]}
    items_by_item_id = {item["item_id"]: item for item in stage_items}

    rejected_items = [item for item in stage_items if item.get("reviewer_rejection")]
    if rejected_items:
        rejected_ids = [item["id"] for item in rejected_items]
        rejected_titles = [
            tpl_items_map.get(item.get("item_id"), {}).get("title", item.get("item_id", ""))
            for item in rejected_items
        ]
        raise HTTPException(status_code=422, detail={
            "error_code": "QC_REJECTED_ITEMS_PENDING",
            "message": "לא ניתן לשלוח לאישור: קיימים סעיפים שנדחו בביקורת וטרם תוקנו",
            "rejected_items_count": len(rejected_items),
            "rejected_item_ids": rejected_ids,
            "rejected_item_titles": rejected_titles,
        })

    errors = []

    for item in stage_items:
        tpl_item = tpl_items_map.get(item.get("item_id"), {})
        item_title = tpl_item.get("title", item.get("item_id", ""))

        if item.get("status") == "pending":
            errors.append({
                "stage_id": stage_id,
                "item_id": item["id"],
                "field": "status",
                "reason": f"סעיף '{item_title}' לא סומן (תקין/לא תקין)"
            })

        if tpl_item.get("required_photo") and not item.get("photos"):
            errors.append({
                "stage_id": stage_id,
                "item_id": item["id"],
                "field": "photo",
                "reason": f"סעיף '{item_title}' דורש תמונה"
            })

        if item.get("status") == "fail" and not (item.get("note") or "").strip():
            errors.append({
                "stage_id": stage_id,
                "item_id": item["id"],
                "field": "note",
                "reason": f"סעיף '{item_title}' מסומן לא תקין — חובה הערה"
            })

    if errors:
        raise HTTPException(status_code=422, detail={
            "error_code": "QC_VALIDATION_FAILED",
            "message": "לא ניתן לשלוח — יש שדות חסרים",
            "errors": errors
        })

    actor = _actor_name(user)
    now = _now()

    stage_statuses[stage_id] = "pending_review"
    await db.qc_runs.update_one(
        {"id": run_id},
        {"$set": {
            f"stage_statuses.{stage_id}": "pending_review",
            f"stage_actors.{stage_id}.submitted_by": user["id"],
            f"stage_actors.{stage_id}.submitted_by_name": actor,
            f"stage_actors.{stage_id}.submitted_at": now,
        }}
    )

    await _audit("qc_stage", stage_id, "submit_for_review", user["id"], {
        "run_id": run_id,
        "floor_id": run.get("floor_id"),
        "project_id": run.get("project_id"),
        "stage_id": stage_id,
        "actor_name": actor,
        "stage_label": _stage_label(tpl, stage_id),
    })

    try:
        recipients = await _get_stage_recipients(db, run["project_id"], stage_id, "submitted")
        await _create_qc_notification(
            db, recipients,
            project_id=run["project_id"], stage_id=stage_id,
            floor_id=run.get("floor_id"), building_id=run.get("building_id"),
            stage_code=stage_id, stage_label_he=_stage_label(tpl, stage_id),
            actor_id=user["id"], actor_name_str=actor,
            action="submitted", run_id=run_id,
        )
    except Exception as e:
        logger.error(f"[QC] Failed to create notifications for submit: {e}")

    logger.info(f"[QC] Stage {stage_id} submitted for review in run {run_id}")

    # #503-followup-3 Bug C — submit_stage hook (was missing entirely).
    # When PM submits a stage to senior, matrix should turn ORANGE
    # "ממתין לאישור". Mirrors approve/reject pattern.
    project_id_for_sync = run["project_id"]
    actor_for_sync = {"id": user["id"], "name": actor}

    async def _run_sync_submit():
        try:
            stage_scope = tpl_stage.get("scope", "floor")
            items_all = await db.qc_items.find(
                {"run_id": run_id, "stage_id": stage_id},
                {"_id": 0},
            ).to_list(2000)
            unit_ids = await _resolve_unit_ids_for_sync(
                db, run, items_all, stage_scope
            )
            items_have_unit_id = any(i.get("unit_id") for i in items_all)
            for uid in unit_ids:
                items_for_uid = (
                    [i for i in items_all if i.get("unit_id") == uid]
                    if items_have_unit_id
                    else items_all
                )
                await sync_qc_stage_to_matrix(
                    db,
                    project_id=project_id_for_sync,
                    unit_id=uid,
                    stage_id=stage_id,
                    actor=actor_for_sync,
                    qc_items=items_for_uid,
                    stage_status="pending_review",
                    stage_scope=stage_scope,
                )
        except Exception as e:
            logger.warning(
                f"[#503] QC→matrix sync (submit) failed for stage_id={stage_id}: {e}"
            )

    background_tasks.add_task(_run_sync_submit)
    return {"status": "pending_review", "stage_id": stage_id}


@router.get("/floors/batch-status")
async def get_floors_qc_status(
    floor_ids: str,
    project_id: str = None,
    user: dict = Depends(get_current_user)
):
    db = get_db()
    ids = [fid.strip() for fid in floor_ids.split(",") if fid.strip()]
    if not ids:
        return {}

    if project_id:
        await _check_qc_access(user, project_id)
        owned_floors = await db.floors.find(
            {"id": {"$in": ids}, "project_id": project_id},
            {"_id": 0, "id": 1}
        ).to_list(len(ids))
        owned_ids = {f["id"] for f in owned_floors}
        rogue = [fid for fid in ids if fid not in owned_ids]
        if rogue:
            logger.warning(f"[QC:BATCH_STATUS:SCOPE_VIOLATION] user={user['id']} project={project_id} rogue_floor_count={len(rogue)}")
            raise HTTPException(status_code=400, detail="floor_ids contain floors not belonging to the specified project")
        logger.info(f"[QC:BATCH_STATUS] user={user['id']} project={project_id} floors={len(ids)}")
    else:
        first_floor = await db.floors.find_one({"id": ids[0]}, {"_id": 0, "project_id": 1})
        if first_floor:
            project_id = first_floor.get("project_id")
        if not project_id:
            raise HTTPException(status_code=400, detail="Cannot determine project for floors")
        await _check_qc_access(user, project_id)
        owned_floors = await db.floors.find(
            {"id": {"$in": ids}, "project_id": project_id},
            {"_id": 0, "id": 1}
        ).to_list(len(ids))
        owned_ids = {f["id"] for f in owned_floors}
        rogue = [fid for fid in ids if fid not in owned_ids]
        if rogue:
            logger.warning(f"[QC:BATCH_STATUS:SCOPE_VIOLATION] user={user['id']} derived_project={project_id} rogue_floor_count={len(rogue)}")
            raise HTTPException(status_code=400, detail="floor_ids contain floors not belonging to the same project")
        logger.warning(f"[QC:BATCH_STATUS:DEPRECATION] user={user['id']} project_id=derived:{project_id} floors={len(ids)} — callers should provide project_id for scoping")

    runs = await db.qc_runs.find(
        {"floor_id": {"$in": ids}, "scope": {"$ne": "unit"}},
        {"_id": 0, "id": 1, "floor_id": 1, "stage_statuses": 1}
    ).to_list(500)

    runs_by_floor = {r["floor_id"]: r for r in runs}

    project_tpl = await _get_template(db, project_id=project_id)

    # BATCH E (2026-05-11) — pre-fetch unit-scope stage statuses for
    # ALL floors in 2 DB queries (vs N*2 in the per-floor loop). Returns
    # {floor_id: stages_data}.
    unit_stages_by_floor = await _compute_unit_scope_stage_statuses_batch(
        db, project_tpl, ids
    )

    # BATCH E (2026-05-11) — pre-fetch qc_items for ALL floor-scope runs
    # in a single $in query (vs N queries inside the per-floor loop).
    # Same optimization pattern as unit_stages_by_floor above.
    run_ids = [r["id"] for r in runs]
    items_by_run_and_stage = {}
    if run_ids:
        all_items = await db.qc_items.find(
            {"run_id": {"$in": run_ids}},
            {"_id": 0, "run_id": 1, "stage_id": 1, "status": 1, "photos": 1, "note": 1, "item_id": 1}
        ).to_list(5000)
        for it in all_items:
            key = (it.get("run_id"), it.get("stage_id"))
            items_by_run_and_stage.setdefault(key, []).append(it)

    result = {}
    for fid in ids:
        run = runs_by_floor.get(fid)
        unit_stages_data = unit_stages_by_floor.get(fid, [])

        if not run:
            # No floor-scope run yet — but unit-scope stages might still
            # have progress (e.g. tile work started before any floor run
            # was created). Compute badge from unit stages alone.
            badge = _compute_floor_badge(unit_stages_data, {}) if unit_stages_data else "not_started"
            stage_summary = _build_stage_summary([], unit_stages_data)
            result[fid] = {
                "badge": badge,
                "pass_count": 0,
                "fail_count": 0,
                "total": 0,
                "stage_summary": stage_summary,
            }
            continue

        # Read pre-fetched items (no DB call inside loop).
        items_by_stage = {}
        for stage_id_iter in (s["id"] for s in project_tpl["stages"]):
            items_by_stage[stage_id_iter] = items_by_run_and_stage.get(
                (run["id"], stage_id_iter), []
            )

        stage_statuses = run.get("stage_statuses", {})
        tpl = project_tpl
        floor_stages = [s for s in tpl["stages"] if s.get("scope", "floor") == "floor"]
        floor_stages_data = []
        total_pass = 0
        total_fail = 0
        total_items = 0
        for stage in floor_stages:
            stage_items = items_by_stage.get(stage["id"], [])
            done_count = sum(1 for i in stage_items if i.get("status") in ("pass", "fail"))
            computed = _compute_stage_status(stage_items, stage["id"], stage_statuses, tpl=tpl)
            s_pass = sum(1 for i in stage_items if i.get("status") == "pass")
            s_fail = sum(1 for i in stage_items if i.get("status") == "fail")
            total_pass += s_pass
            total_fail += s_fail
            total_items += len(stage_items)
            floor_stages_data.append({
                "id": stage["id"],
                "done": done_count,
                "computed_status": computed,
                "_scope": "floor",
            })

        # BATCH E (2026-05-11) — combine floor + unit stages_data so
        # _compute_floor_badge sees the full picture. Rejected priority
        # propagates from unit-stage rejection up to floor badge.
        combined_stages_data = floor_stages_data + unit_stages_data
        badge = _compute_floor_badge(combined_stages_data, stage_statuses)
        stage_summary = _build_stage_summary(floor_stages_data, unit_stages_data)

        result[fid] = {
            "badge": badge,
            "pass_count": total_pass,
            "fail_count": total_fail,
            "total": total_items,
            "stage_summary": stage_summary,
        }

    return result


@router.get("/meta/stages")
async def get_qc_stage_meta(user: dict = Depends(get_current_user)):
    db = get_db()
    tpl = await _get_template(db)
    return _get_stage_labels_from_tpl(tpl)


class ApproverCreateBody(BaseModel):
    user_id: str
    mode: str
    stages: Optional[List[str]] = None


async def _check_pm_or_admin(user, project_id):
    if _is_super_admin(user):
        return
    role = await _get_project_role(user, project_id)
    if role not in PM_ROLES:
        raise HTTPException(status_code=403, detail="רק מנהל פרויקט יכול לנהל מאשרים")


QC_VIEW_ROLES = PM_ROLES | {'management_team'}

async def _check_qc_approvers_view_permission(user, project_id):
    if _is_super_admin(user):
        return
    role = await _get_project_role(user, project_id)
    if role not in QC_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="אין הרשאה לצפות במאשרי QC")


@router.get("/projects/{project_id}/approvers")
async def list_approvers(project_id: str, user: dict = Depends(get_current_user)):
    await _check_qc_approvers_view_permission(user, project_id)
    db = get_db()
    approvers = await db.project_approvers.find(
        {"project_id": project_id, "active": True},
        {"_id": 0}
    ).to_list(200)

    user_ids = list({a["user_id"] for a in approvers})
    users = {}
    memberships = {}
    if user_ids:
        user_docs = await db.users.find(
            {"id": {"$in": user_ids}},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1}
        ).to_list(200)
        users = {u["id"]: u for u in user_docs}
        membership_docs = await db.project_memberships.find(
            {"project_id": project_id, "user_id": {"$in": user_ids}},
            {"_id": 0, "user_id": 1, "role": 1}
        ).to_list(200)
        memberships = {m["user_id"]: m.get("role") for m in membership_docs}

    tpl = await _get_template(db, project_id=project_id)
    stage_map = {s["code"]: s["label_he"] for s in _get_stage_labels_from_tpl(tpl)}
    result = []
    for a in approvers:
        u = users.get(a["user_id"], {})
        user_role = memberships.get(a["user_id"])
        invalid_role = user_role == "contractor"
        stages_display = None
        if a.get("mode") == "stages" and a.get("stages"):
            stages_display = [
                {"code": sc, "label_he": stage_map.get(sc, sc)}
                for sc in a["stages"]
            ]
        result.append({
            "id": a["id"],
            "user_id": a["user_id"],
            "user_name": u.get("name", ""),
            "user_email": u.get("email", ""),
            "user_role": user_role or "",
            "mode": a.get("mode", "all"),
            "stages": a.get("stages"),
            "stages_display": stages_display,
            "created_at": a.get("created_at"),
            "created_by": a.get("created_by"),
            "invalid_role": invalid_role,
        })
    return result


@router.post("/projects/{project_id}/approvers")
async def add_approver(project_id: str, body: ApproverCreateBody, user: dict = Depends(get_current_user)):
    await _check_pm_or_admin(user, project_id)
    db = get_db()

    if body.mode not in ("all", "stages"):
        raise HTTPException(status_code=400, detail="mode חייב להיות 'all' או 'stages'")

    if body.mode == "stages":
        if not body.stages or len(body.stages) == 0:
            raise HTTPException(status_code=400, detail="יש לבחור לפחות שלב אחד")
        tpl = await _get_template(db, project_id=project_id)
        valid_codes = _get_valid_stage_codes(tpl)
        invalid = set(body.stages) - valid_codes
        if invalid:
            raise HTTPException(status_code=400, detail=f"שלבים לא חוקיים: {', '.join(invalid)}")

    target_user = await db.users.find_one({"id": body.user_id}, {"_id": 0, "id": 1})
    if not target_user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא")

    target_membership = await db.project_memberships.find_one({
        "project_id": project_id,
        "user_id": body.user_id,
    }, {"_id": 0, "role": 1})
    if target_membership and target_membership.get("role") == "contractor":
        await _audit("project_approver", project_id, "approver_add_blocked_invalid_role", user["id"], {
            "project_id": project_id,
            "target_user_id": body.user_id,
            "target_role": "contractor",
            "reason": "contractor_not_allowed",
        })
        logger.warning(f"[QC] Blocked attempt to add contractor {body.user_id} as approver in project {project_id} by {user['id']}")
        raise HTTPException(status_code=400, detail="לא ניתן להגדיר קבלן כמאשר QC")

    existing = await db.project_approvers.find_one({
        "project_id": project_id,
        "user_id": body.user_id,
        "active": True,
    })
    if existing:
        raise HTTPException(status_code=409, detail="המשתמש כבר מוגדר כמאשר בפרויקט זה")

    approver_doc = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "user_id": body.user_id,
        "mode": body.mode,
        "stages": body.stages if body.mode == "stages" else None,
        "active": True,
        "created_by": user["id"],
        "created_at": _now(),
        "revoked_at": None,
    }
    await db.project_approvers.insert_one(approver_doc)

    await _audit("project_approver", approver_doc["id"], "approver_granted", user["id"], {
        "project_id": project_id,
        "target_user_id": body.user_id,
        "mode": body.mode,
        "stages": body.stages if body.mode == "stages" else None,
    })

    logger.info(f"[QC] Approver {body.user_id} added to project {project_id} mode={body.mode}")
    return {"id": approver_doc["id"], "status": "created"}


@router.delete("/projects/{project_id}/approvers/{target_user_id}")
async def revoke_approver(project_id: str, target_user_id: str, user: dict = Depends(get_current_user)):
    await _check_pm_or_admin(user, project_id)
    db = get_db()

    existing = await db.project_approvers.find_one({
        "project_id": project_id,
        "user_id": target_user_id,
        "active": True,
    })
    if not existing:
        raise HTTPException(status_code=404, detail="מאשר לא נמצא בפרויקט זה")

    await db.project_approvers.update_one(
        {"id": existing["id"]},
        {"$set": {"active": False, "revoked_at": _now()}}
    )

    await _audit("project_approver", existing["id"], "approver_revoked", user["id"], {
        "project_id": project_id,
        "target_user_id": target_user_id,
        "mode": existing.get("mode"),
        "stages": existing.get("stages"),
    })

    logger.info(f"[QC] Approver {target_user_id} revoked from project {project_id}")
    return {"status": "revoked"}


STAGE_ICONS = {
    "stage_ceiling_prep": "🏗️",
    "stage_blocks_row1": "🧱",
    "stage_plumbing": "🔧",
    "stage_electrical": "⚡",
    "stage_plaster": "🪣",
    "stage_waterproof": "💧",
    "stage_acoustic": "🔇",
    "stage_tiling": "🟫",
}


@router.get("/projects/{project_id}/execution-summary")
async def get_execution_summary(project_id: str, user: dict = Depends(get_current_user)):
    await _check_qc_access(user, project_id)
    db = get_db()

    buildings = await db.buildings.find(
        {"project_id": project_id, "archived": {"$ne": True}},
        {"_id": 0, "id": 1, "name": 1}
    ).to_list(200)
    if not buildings:
        return {"stages": [], "overall": {"total": 0, "completed": 0, "completion_pct": 0}}

    building_ids = [b["id"] for b in buildings]
    building_map = {b["id"]: b["name"] for b in buildings}

    floors = await db.floors.find(
        {"building_id": {"$in": building_ids}, "archived": {"$ne": True}},
        {"_id": 0, "id": 1, "building_id": 1, "name": 1}
    ).to_list(2000)
    floor_ids = [f["id"] for f in floors]
    floors_by_building = {}
    for f in floors:
        floors_by_building.setdefault(f["building_id"], []).append(f)

    units = await db.units.find(
        {"floor_id": {"$in": floor_ids}, "archived": {"$ne": True}},
        {"_id": 0, "id": 1, "floor_id": 1, "unit_no": 1, "building_id": 1}
    ).to_list(5000)
    units_by_floor = {}
    for u in units:
        units_by_floor.setdefault(u["floor_id"], []).append(u)

    runs = await db.qc_runs.find(
        {"project_id": project_id},
        {"_id": 0, "id": 1, "floor_id": 1, "unit_id": 1, "scope": 1, "stage_statuses": 1}
    ).to_list(5000)

    floor_runs = {}
    unit_runs = {}
    for r in runs:
        scope = r.get("scope", "floor")
        if scope == "unit" and r.get("unit_id"):
            unit_runs[r["unit_id"]] = r.get("stage_statuses", {})
        elif scope != "unit":
            floor_runs[r["floor_id"]] = r.get("stage_statuses", {})

    tpl = await _get_template(db, project_id=project_id)
    overall_total = 0
    overall_completed = 0
    stages_out = []

    for stage in tpl["stages"]:
        stage_id = stage["id"]
        scope = stage.get("scope", "floor")
        icon = _get_stage_icon(tpl, stage_id)

        completed = 0
        in_progress = 0
        not_started = 0
        failed = 0
        building_details = []

        for bld in buildings:
            bld_id = bld["id"]
            bld_floors = floors_by_building.get(bld_id, [])
            children = []

            if scope == "floor":
                for fl in bld_floors:
                    ss = floor_runs.get(fl["id"], {})
                    st = ss.get(stage_id)
                    if st == "approved":
                        status = "completed"
                        completed += 1
                    elif st == "rejected":
                        status = "failed"
                        failed += 1
                    elif st in ("pending_review", "reopened", "ready"):
                        status = "in_progress"
                        in_progress += 1
                    else:
                        status = "not_started"
                        not_started += 1

                    children.append({
                        "id": fl["id"],
                        "name": fl.get("name", ""),
                        "type": "floor",
                        "status": status,
                    })
            else:
                for fl in bld_floors:
                    fl_units = units_by_floor.get(fl["id"], [])
                    for unit in fl_units:
                        ss = unit_runs.get(unit["id"], {})
                        st = ss.get(stage_id)
                        if st == "approved":
                            status = "completed"
                            completed += 1
                        elif st == "rejected":
                            status = "failed"
                            failed += 1
                        elif st in ("pending_review", "reopened", "ready"):
                            status = "in_progress"
                            in_progress += 1
                        else:
                            status = "not_started"
                            not_started += 1

                        children.append({
                            "id": unit["id"],
                            "name": unit.get("unit_no", ""),
                            "type": "unit",
                            "floor_name": fl.get("name", ""),
                            "status": status,
                        })

            if children:
                building_details.append({
                    "building_id": bld_id,
                    "building_name": building_map.get(bld_id, ""),
                    "children": children,
                })

        total = completed + in_progress + not_started + failed
        completion_pct = round(completed / total * 100) if total > 0 else 0
        overall_total += total
        overall_completed += completed

        stages_out.append({
            "stage_id": stage_id,
            "title": stage["title"],
            "scope": scope,
            "icon": icon,
            "order": stage["order"],
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "not_started": not_started,
            "failed": failed,
            "completion_pct": completion_pct,
            "entity_label": "קומות" if scope == "floor" else "דירות",
            "buildings": building_details,
        })

    overall_pct = round(overall_completed / overall_total * 100) if overall_total > 0 else 0

    alerts = []

    floor_stages = [s for s in stages_out if s["scope"] == "floor"]
    for i in range(len(floor_stages) - 1):
        prev = floor_stages[i]
        nxt = floor_stages[i + 1]
        if prev["completed"] >= 3 and prev["completion_pct"] > 40 and nxt["completion_pct"] < 20:
            gap = prev["completion_pct"] - nxt["completion_pct"]
            if gap > 25:
                severity = "high" if gap > 40 else "medium"
                alerts.append({
                    "type": "bottleneck",
                    "severity": severity,
                    "stage_id": nxt["stage_id"],
                    "message": f"{nxt['title']} מפגרת משמעותית — {nxt['completion_pct']}% לעומת {prev['title']} ב-{prev['completion_pct']}%",
                    "detail": f"{nxt['completed']}/{nxt['total']} {nxt['entity_label']} לעומת {prev['completed']}/{prev['total']} בשלב הקודם",
                })

    stuck_candidates = []
    for stage in floor_stages:
        for bld in stage.get("buildings", []):
            bld_children = bld["children"]
            if len(bld_children) < 2:
                continue
            statuses = [c["status"] for c in bld_children]
            has_completed = "completed" in statuses
            if not has_completed:
                continue
            later_stages = [ls for ls in floor_stages if ls["order"] > stage["order"]]
            for child in bld_children:
                if child["status"] != "not_started":
                    continue
                for ls in later_stages:
                    ls_bld = next((b for b in ls.get("buildings", []) if b["building_id"] == bld["building_id"]), None)
                    if not ls_bld:
                        continue
                    peer = next((c for c in ls_bld["children"] if c["id"] == child["id"]), None)
                    if peer and peer["status"] in ("completed", "in_progress"):
                        continue
                    sibling_ids = {c["id"] for c in bld_children if c["id"] != child["id"]}
                    ls_siblings = [c for c in ls_bld["children"] if c["id"] in sibling_ids]
                    siblings_ahead = sum(1 for c in ls_siblings if c["status"] in ("completed", "in_progress"))
                    if siblings_ahead >= 2:
                        stuck_candidates.append({
                            "type": "stuck",
                            "severity": "medium",
                            "stage_id": stage["stage_id"],
                            "entity_id": child["id"],
                            "building_id": bld["building_id"],
                            "message": f"{bld['building_name']} {child['name']} — {stage['title']} לא התחיל, קומות סמוכות כבר ב{ls['title']}",
                        })
                        break
    seen_entities = set()
    for sc in stuck_candidates[:5]:
        key = (sc["building_id"], sc["entity_id"], sc["stage_id"])
        if key not in seen_entities:
            seen_entities.add(key)
            alerts.append(sc)

    for bld in buildings:
        bld_id = bld["id"]
        bld_floors_list = floors_by_building.get(bld_id, [])
        if len(bld_floors_list) < 2:
            continue
        has_any = False
        for stage in stages_out:
            stage_bld = next((b for b in stage.get("buildings", []) if b["building_id"] == bld_id), None)
            if stage_bld:
                for child in stage_bld["children"]:
                    if child["status"] != "not_started":
                        has_any = True
                        break
            if has_any:
                break
        if not has_any:
            alerts.append({
                "type": "no_progress",
                "severity": "low",
                "message": f"{building_map.get(bld_id, '')} — 0% התקדמות בכל השלבים",
            })

    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda a: severity_order.get(a.get("severity"), 3))
    alerts = alerts[:10]

    return {
        "stages": stages_out,
        "overall": {
            "total": overall_total,
            "completed": overall_completed,
            "completion_pct": overall_pct,
        },
        "alerts": alerts,
    }


async def _check_approver_authorization(user, project_id, stage_id):
    if _is_super_admin(user):
        return True

    role = await _get_project_role(user, project_id)
    if role == "contractor":
        raise HTTPException(status_code=403, detail="קבלן לא יכול לאשר שלבי QC")
    if role in PM_ROLES:
        return True

    db = get_db()
    approver = await db.project_approvers.find_one({
        "project_id": project_id,
        "user_id": user["id"],
        "active": True,
    })
    if not approver:
        raise HTTPException(status_code=403, detail="אין לך הרשאת אישור בפרויקט זה")

    if approver.get("mode") == "all":
        return True

    if approver.get("mode") == "stages":
        if stage_id in (approver.get("stages") or []):
            return True
        raise HTTPException(status_code=403, detail="אין לך הרשאת אישור לשלב זה")

    raise HTTPException(status_code=403, detail="אין לך הרשאת אישור בפרויקט זה")


class ApproveRejectBody(BaseModel):
    note: Optional[str] = None
    reason: Optional[str] = None


@router.post("/run/{run_id}/stage/{stage_id}/approve")
async def approve_stage(
    run_id: str,
    stage_id: str,
    body: ApproveRejectBody,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    db = get_db()

    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    stage_statuses = run.get("stage_statuses", {})
    if stage_statuses.get(stage_id) != "pending_review":
        raise HTTPException(status_code=400, detail="ניתן לאשר רק שלב שממתין לאישור")

    await _check_approver_authorization(user, run["project_id"], stage_id)

    tpl = await _get_template(db, run=run, project_id=run.get("project_id"))
    item_map = _build_item_map(tpl)

    stage_items = await db.qc_items.find(
        {"run_id": run_id, "stage_id": stage_id}, {"_id": 0, "item_id": 1, "status": 1, "reviewer_rejection": 1}
    ).to_list(200)
    blocked_items = []
    for si in stage_items:
        if si.get("status") == "fail" or si.get("reviewer_rejection"):
            tpl_item = item_map.get(si.get("item_id"), {})
            blocked_items.append({
                "item_id": si.get("item_id"),
                "title": tpl_item.get("title", si.get("item_id", "")),
                "status": si.get("status"),
            })
    if blocked_items:
        await _audit("qc_stage", stage_id, "qc_approval_blocked_failed_items", user["id"], {
            "run_id": run_id,
            "project_id": run.get("project_id"),
            "stage_id": stage_id,
            "fail_count": len(blocked_items),
            "blocked_item_ids": [b["item_id"] for b in blocked_items],
            "actor_name": _actor_name(user),
        })
        raise HTTPException(status_code=422, detail={
            "message": f"לא ניתן לאשר שלב עם פריטים שנכשלו ({len(blocked_items)} פריטים)",
            "blocked_items": blocked_items,
        })

    actor = _actor_name(user)
    now = _now()

    await db.qc_runs.update_one(
        {"id": run_id},
        {"$set": {
            f"stage_statuses.{stage_id}": "approved",
            f"stage_actors.{stage_id}.approved_by": user["id"],
            f"stage_actors.{stage_id}.approved_by_name": actor,
            f"stage_actors.{stage_id}.approved_at": now,
        }}
    )

    await _audit("qc_stage", stage_id, "qc_approved", user["id"], {
        "run_id": run_id,
        "floor_id": run.get("floor_id"),
        "project_id": run.get("project_id"),
        "stage_id": stage_id,
        "note": body.note,
        "actor_name": actor,
        "stage_label": _stage_label(tpl, stage_id),
    })

    try:
        stage_actors = run.get("stage_actors", {}).get(stage_id, {})
        submitter_id = stage_actors.get("submitted_by")
        recipients = await _get_stage_recipients(db, run["project_id"], stage_id, "approved", submitter_id=submitter_id)
        await _create_qc_notification(
            db, recipients,
            project_id=run["project_id"], stage_id=stage_id,
            floor_id=run.get("floor_id"), building_id=run.get("building_id"),
            stage_code=stage_id, stage_label_he=_stage_label(tpl, stage_id),
            actor_id=user["id"], actor_name_str=actor,
            action="approved", run_id=run_id,
        )
    except Exception as e:
        logger.error(f"[QC] Failed to create notifications for approve: {e}")

    logger.info(f"[QC] Stage {stage_id} approved in run {run_id} by user {user['id']}")

    # #503-followup-2 — multi-cell matrix sync via BackgroundTasks.
    # Stage decision affects every unit-scope item AND every unit on
    # the floor (for floor-scope). _resolve_unit_ids_for_sync handles
    # both: items.unit_id distinct first, falling back to floor's
    # units when items lack unit_id (template-level items).
    project_id_for_sync = run["project_id"]
    actor_for_sync = {"id": user["id"], "name": actor}

    async def _run_sync_approve():
        try:
            tpl_stage = next(
                (s for s in tpl["stages"] if s["id"] == stage_id), {}
            )
            stage_scope = tpl_stage.get("scope", "floor")
            items_all = await db.qc_items.find(
                {"run_id": run_id, "stage_id": stage_id},
                {"_id": 0},
            ).to_list(2000)
            unit_ids = await _resolve_unit_ids_for_sync(
                db, run, items_all, stage_scope
            )
            # #503-followup-3 Bug B fix — floor-shared items pass items_all
            items_have_unit_id = any(i.get("unit_id") for i in items_all)
            for uid in unit_ids:
                items_for_uid = (
                    [i for i in items_all if i.get("unit_id") == uid]
                    if items_have_unit_id
                    else items_all
                )
                await sync_qc_stage_to_matrix(
                    db,
                    project_id=project_id_for_sync,
                    unit_id=uid,
                    stage_id=stage_id,
                    actor=actor_for_sync,
                    qc_items=items_for_uid,
                    stage_status="approved",
                    stage_scope=stage_scope,
                )
        except Exception as e:
            logger.warning(
                f"[#503] QC→matrix sync (approve) failed for stage_id={stage_id}: {e}"
            )

    background_tasks.add_task(_run_sync_approve)
    return {"status": "approved", "stage_id": stage_id}


@router.post("/run/{run_id}/stage/{stage_id}/reject")
async def reject_stage(
    run_id: str,
    stage_id: str,
    body: ApproveRejectBody,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    db = get_db()

    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    stage_statuses = run.get("stage_statuses", {})
    if stage_statuses.get(stage_id) != "pending_review":
        raise HTTPException(status_code=400, detail="ניתן לדחות רק שלב שממתין לאישור")

    if not body.reason:
        raise HTTPException(status_code=400, detail="יש לציין סיבת דחייה")

    await _check_approver_authorization(user, run["project_id"], stage_id)

    tpl = await _get_template(db, run=run, project_id=run.get("project_id"))
    actor = _actor_name(user)
    now = _now()

    await db.qc_runs.update_one(
        {"id": run_id},
        {"$set": {
            f"stage_statuses.{stage_id}": "rejected",
            f"stage_actors.{stage_id}.rejected_by": user["id"],
            f"stage_actors.{stage_id}.rejected_by_name": actor,
            f"stage_actors.{stage_id}.rejected_at": now,
            f"stage_actors.{stage_id}.rejected_reason": body.reason,
        }}
    )

    await _audit("qc_stage", stage_id, "qc_rejected", user["id"], {
        "run_id": run_id,
        "floor_id": run.get("floor_id"),
        "project_id": run.get("project_id"),
        "stage_id": stage_id,
        "reason": body.reason,
        "actor_name": actor,
        "stage_label": _stage_label(tpl, stage_id),
    })

    try:
        stage_actors = run.get("stage_actors", {}).get(stage_id, {})
        submitter_id = stage_actors.get("submitted_by")
        recipients = await _get_stage_recipients(db, run["project_id"], stage_id, "rejected", submitter_id=submitter_id)
        await _create_qc_notification(
            db, recipients,
            project_id=run["project_id"], stage_id=stage_id,
            floor_id=run.get("floor_id"), building_id=run.get("building_id"),
            stage_code=stage_id, stage_label_he=_stage_label(tpl, stage_id),
            actor_id=user["id"], actor_name_str=actor,
            action="rejected", reason=body.reason, run_id=run_id,
        )
    except Exception as e:
        logger.error(f"[QC] Failed to create notifications for reject: {e}")

    logger.info(f"[QC] Stage {stage_id} rejected in run {run_id} by user {user['id']}: {body.reason}")

    # #503-followup-2 — reject hook (Bug 1 from Zahi smoke 2026-05-06).
    # Mirrors approve/override pattern: enumerate affected unit_ids
    # via _resolve_unit_ids_for_sync and flip every cell to not_done.
    project_id_for_sync = run["project_id"]
    actor_for_sync = {"id": user["id"], "name": actor}

    async def _run_sync_reject():
        try:
            tpl_stage = next(
                (s for s in tpl["stages"] if s["id"] == stage_id), {}
            )
            stage_scope = tpl_stage.get("scope", "floor")
            items_all = await db.qc_items.find(
                {"run_id": run_id, "stage_id": stage_id},
                {"_id": 0},
            ).to_list(2000)
            unit_ids = await _resolve_unit_ids_for_sync(
                db, run, items_all, stage_scope
            )
            # #503-followup-3 Bug B fix — floor-shared items pass items_all
            items_have_unit_id = any(i.get("unit_id") for i in items_all)
            for uid in unit_ids:
                items_for_uid = (
                    [i for i in items_all if i.get("unit_id") == uid]
                    if items_have_unit_id
                    else items_all
                )
                await sync_qc_stage_to_matrix(
                    db,
                    project_id=project_id_for_sync,
                    unit_id=uid,
                    stage_id=stage_id,
                    actor=actor_for_sync,
                    qc_items=items_for_uid,
                    stage_status="rejected",
                    stage_scope=stage_scope,
                )
        except Exception as e:
            logger.warning(
                f"[#503] QC→matrix sync (reject) failed for stage_id={stage_id}: {e}"
            )

    background_tasks.add_task(_run_sync_reject)
    return {"status": "rejected", "stage_id": stage_id}


class NotifyRejectionBody(BaseModel):
    recipient_user_id: str
    item_id: Optional[str] = None
    message: Optional[str] = None


@router.post("/run/{run_id}/stage/{stage_id}/notify-rejection")
async def notify_rejection_whatsapp(run_id: str, stage_id: str, body: NotifyRejectionBody, user: dict = Depends(get_current_user)):
    db = get_db()

    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    project_id = run["project_id"]
    role = await _get_project_role(user, project_id)

    is_pm = role in PM_ROLES
    is_approver = False
    if not is_pm and not _is_super_admin(user):
        approver_doc = await db.project_approvers.find_one({
            "project_id": project_id,
            "user_id": user["id"],
            "active": True,
        })
        if approver_doc:
            is_approver = True

    if not is_pm and not is_approver and not _is_super_admin(user):
        raise HTTPException(status_code=403, detail="אין הרשאה לשלוח הודעת דחייה")

    if role == "contractor":
        raise HTTPException(status_code=403, detail="קבלן לא יכול לשלוח הודעת דחייה")

    tpl = await _get_template(db, run=run, project_id=run.get("project_id"))
    wa_item_map = _build_item_map(tpl)

    stage_statuses = run.get("stage_statuses", {})
    rejection_reason = None
    item_title = None
    first_photo_url = None

    if body.item_id:
        item = await db.qc_items.find_one({"run_id": run_id, "id": body.item_id}, {"_id": 0})
        if not item:
            item = await db.qc_items.find_one({"run_id": run_id, "item_id": body.item_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="סעיף לא נמצא בשלב זה")
        if item.get("stage_id") != stage_id:
            raise HTTPException(status_code=400, detail="הסעיף לא שייך לשלב הנבחר")
        reviewer_rejection = item.get("reviewer_rejection")
        if not reviewer_rejection and item.get("status") != "fail":
            raise HTTPException(status_code=400, detail="הסעיף לא נדחה — לא ניתן לשלוח הודעת דחייה")
        rejection_reason = (reviewer_rejection or {}).get("reason", "")
        tpl_item_key = item.get("item_id") or body.item_id
        tpl_item = wa_item_map.get(tpl_item_key, {})
        item_title = tpl_item.get("title", tpl_item_key)
        photos = item.get("photos", [])
        if photos:
            first_photo_url = _resolve_photo_url(photos[0].get("url"))
    else:
        current_stage_status = stage_statuses.get(stage_id)
        if current_stage_status != "rejected":
            raise HTTPException(status_code=400, detail="השלב לא נדחה — לא ניתן לשלוח הודעת דחייה")
        stage_actors = run.get("stage_actors", {}).get(stage_id, {})
        rejection_reason = stage_actors.get("rejected_reason", "")
        stage_items = await db.qc_items.find({"run_id": run_id, "stage_id": stage_id}, {"_id": 0}).to_list(100)
        for si in stage_items:
            photos = si.get("photos", [])
            if photos:
                first_photo_url = _resolve_photo_url(photos[0].get("url"))
                break

    membership = await db.project_memberships.find_one({
        "project_id": project_id,
        "user_id": body.recipient_user_id,
    })
    if not membership:
        raise HTTPException(status_code=400, detail="הנמען אינו חבר בפרויקט")

    recipient_role = membership.get("role", "unknown")
    recipient_user = await db.users.find_one({"id": body.recipient_user_id}, {"_id": 0})
    recipient_is_sa = recipient_user and recipient_user.get("platform_role") == "super_admin" if recipient_user else False
    if recipient_role not in NOTIFY_ELIGIBLE_ROLES and not recipient_is_sa:
        await _audit("qc_stage", stage_id, "qc_rejection_whatsapp_blocked_recipient_role", user["id"], {
            "project_id": project_id,
            "run_id": run_id,
            "stage_id": stage_id,
            "recipient_user_id": body.recipient_user_id,
            "recipient_role": recipient_role,
            "sender_user_id": user["id"],
        })
        raise HTTPException(status_code=403, detail="לא ניתן לשלוח הודעה לתפקיד זה")

    recipient = recipient_user
    if not recipient:
        raise HTTPException(status_code=400, detail="משתמש לא נמצא")

    recipient_phone = recipient.get("phone_e164")
    if not recipient_phone:
        raise HTTPException(status_code=400, detail="לנמען אין מספר טלפון — לא ניתן לשלוח הודעה ב-WhatsApp")

    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "name": 1})
    project_name = project.get("name", "") if project else ""

    floor = await db.floors.find_one({"id": run.get("floor_id")}, {"_id": 0, "name": 1})
    floor_name = floor.get("name", "") if floor else ""

    stage_title = _stage_label(tpl, stage_id)

    base_url = get_public_base_url()
    direct_link = ""
    if base_url:
        direct_link = f"{base_url}/projects/{project_id}/qc/floors/{run.get('floor_id')}/run/{run_id}/stage/{stage_id}"

    audit_payload = {
        "project_id": project_id,
        "run_id": run_id,
        "stage_id": stage_id,
        "item_id": body.item_id,
        "recipient_user_id": body.recipient_user_id,
        "recipient_role": recipient_role,
        "has_image": first_photo_url is not None,
    }

    try:
        engine = get_notification_engine()
        if engine and engine.wa_client:
            button_path = ""
            if direct_link:
                from urllib.parse import urlparse
                parsed = urlparse(direct_link)
                button_path = parsed.path

            success = await _send_qc_rejection_wa(
                engine.wa_client, recipient_phone,
                project_name=project_name,
                floor_name=floor_name,
                stage_name=stage_title,
                item_name=item_title or stage_title,
                rejection_reason=rejection_reason or body.message or "",
                button_path=button_path,
            )

            await _audit("qc_stage", stage_id, "qc_rejection_whatsapp_sent_manual", user["id"], {
                **audit_payload,
                "result_status": "success" if success else "failed",
                "dry_run": False,
            })

            if success:
                logger.info(f"[QC-WA] Rejection WhatsApp sent for run={run_id} stage={stage_id} to user={body.recipient_user_id}")
                return {"ok": True, "message": "הודעת דחייה נשלחה בהצלחה", "dry_run": False}
            else:
                raise RuntimeError("WhatsApp send returned false")
        else:
            raise RuntimeError("WhatsApp client not available")

    except Exception as e:
        logger.error(f"[QC-WA] Failed to send rejection WhatsApp: {e}")
        await _audit("qc_stage", stage_id, "qc_rejection_whatsapp_sent_manual", user["id"], {
            **audit_payload,
            "result_status": "failed",
            "error": str(e)[:200],
        })
        raise HTTPException(status_code=500, detail=f"שליחת ההודעה נכשלה: {str(e)[:100]}")


@router.get("/run/{run_id}/my-approver-status")
async def get_my_approver_status(run_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    project_id = run["project_id"]
    role = await _get_project_role(user, project_id)
    is_super = _is_super_admin(user)
    is_pm = role in PM_ROLES
    can_manage = is_pm or is_super

    approver_doc = None
    if not is_pm and not is_super:
        approver_doc = await db.project_approvers.find_one({
            "project_id": project_id,
            "user_id": user["id"],
            "active": True,
        })

    is_approver = is_pm or is_super or (approver_doc is not None)
    is_pm_implicit = is_pm and approver_doc is None

    if is_super:
        my_mode = "all"
        my_stages = None
        reason_code = "ok_super_admin"
    elif is_pm:
        my_mode = "all"
        my_stages = None
        reason_code = "ok_pm_default"
    elif approver_doc:
        my_mode = approver_doc.get("mode", "all")
        my_stages = approver_doc.get("stages")
        reason_code = "ok_explicit"
    else:
        my_mode = None
        my_stages = None
        if role == "contractor":
            reason_code = "role_not_allowed"
        else:
            reason_code = "not_configured"

    active_approvers_for_stage = []
    if can_manage or role in QC_VIEW_ROLES:
        pm_memberships = await db.project_memberships.find(
            {"project_id": project_id, "role": {"$in": list(PM_ROLES)}},
            {"_id": 0, "user_id": 1}
        ).to_list(50)
        pm_user_ids = [m["user_id"] for m in pm_memberships]
        pm_users = []
        if pm_user_ids:
            pm_user_docs = await db.users.find(
                {"id": {"$in": pm_user_ids}},
                {"_id": 0, "id": 1, "name": 1}
            ).to_list(50)
            pm_users = [{"user_id": u["id"], "name": u.get("name", ""), "source": "pm_default"} for u in pm_user_docs]

        explicit_approvers = await db.project_approvers.find(
            {"project_id": project_id, "active": True},
            {"_id": 0, "user_id": 1, "mode": 1, "stages": 1}
        ).to_list(200)
        explicit_user_ids = [a["user_id"] for a in explicit_approvers]
        explicit_users = {}
        if explicit_user_ids:
            eu_docs = await db.users.find(
                {"id": {"$in": explicit_user_ids}},
                {"_id": 0, "id": 1, "name": 1}
            ).to_list(200)
            explicit_users = {u["id"]: u for u in eu_docs}

        explicit_list = []
        for a in explicit_approvers:
            eu = explicit_users.get(a["user_id"], {})
            explicit_list.append({
                "user_id": a["user_id"],
                "name": eu.get("name", ""),
                "source": "explicit",
                "mode": a.get("mode", "all"),
                "stages": a.get("stages"),
            })

        active_approvers_for_stage = pm_users + explicit_list
    else:
        pm_count_cursor = await db.project_memberships.count_documents(
            {"project_id": project_id, "role": {"$in": list(PM_ROLES)}}
        )
        explicit_count = await db.project_approvers.count_documents(
            {"project_id": project_id, "active": True}
        )
        active_approvers_for_stage = {"pm_count": pm_count_cursor, "explicit_count": explicit_count}

    return {
        "is_approver": is_approver,
        "is_pm_implicit": is_pm_implicit,
        "mode": my_mode,
        "stages": my_stages,
        "reason_code": reason_code,
        "can_manage_approvers": can_manage,
        "active_approvers_for_stage": active_approvers_for_stage,
    }


class ReopenBody(BaseModel):
    reason: str


class OverrideApproveBody(BaseModel):
    """Body for stage override-approve. Reason mandatory."""
    reason: str = Field(..., min_length=10, max_length=500)


@router.post("/run/{run_id}/stage/{stage_id}/reopen")
async def reopen_stage(
    run_id: str,
    stage_id: str,
    body: ReopenBody,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    db = get_db()

    if not (body.reason or "").strip():
        raise HTTPException(status_code=400, detail="יש לציין סיבת פתיחה מחדש")

    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    role = await _get_project_role(user, run["project_id"])
    if role not in PM_ROLES and not _is_super_admin(user):
        raise HTTPException(status_code=403, detail="אין לך הרשאה לפתוח מחדש שלב זה")

    stage_statuses = run.get("stage_statuses", {})
    current = stage_statuses.get(stage_id)
    if current not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="לא ניתן לפתוח מחדש את השלב במצב הנוכחי")

    tpl = await _get_template(db, run=run, project_id=run.get("project_id"))
    actor = _actor_name(user)
    now = _now()

    await db.qc_runs.update_one(
        {"id": run_id},
        {"$set": {
            f"stage_statuses.{stage_id}": "reopened",
            f"stage_actors.{stage_id}.reopened_by": user["id"],
            f"stage_actors.{stage_id}.reopened_by_name": actor,
            f"stage_actors.{stage_id}.reopened_at": now,
            f"stage_actors.{stage_id}.reopened_reason": body.reason,
        }}
    )

    await _audit("qc_stage", stage_id, "qc_reopened", user["id"], {
        "run_id": run_id,
        "floor_id": run.get("floor_id"),
        "project_id": run.get("project_id"),
        "stage_id": stage_id,
        "from_status": current,
        "to_status": "reopened",
        "reason": body.reason,
        "actor_name": actor,
        "stage_label": _stage_label(tpl, stage_id),
    })

    try:
        stage_actors = run.get("stage_actors", {}).get(stage_id, {})
        submitter_id = stage_actors.get("submitted_by")
        recipients = await _get_stage_recipients(db, run["project_id"], stage_id, "reopened", submitter_id=submitter_id)
        await _create_qc_notification(
            db, recipients,
            project_id=run["project_id"], stage_id=stage_id,
            floor_id=run.get("floor_id"), building_id=run.get("building_id"),
            stage_code=stage_id, stage_label_he=_stage_label(tpl, stage_id),
            actor_id=user["id"], actor_name_str=actor,
            action="reopened", reason=body.reason, run_id=run_id,
        )
    except Exception as e:
        logger.error(f"[QC] Failed to create notifications for reopen: {e}")

    logger.info(f"[QC] Stage {stage_id} reopened in run {run_id} by user {user['id']}: {body.reason}")

    # #503-followup-3 STOP-GATE 0.6 — reopen_stage was unhooked.
    # stage_status="reopened" falls through in the mapping to
    # item-level activity (in_progress if any item touched, else None).
    project_id_for_sync = run["project_id"]
    actor_for_sync = {"id": user["id"], "name": actor}

    async def _run_sync_reopen():
        try:
            tpl_stage = next(
                (s for s in tpl["stages"] if s["id"] == stage_id), {}
            )
            stage_scope = tpl_stage.get("scope", "floor")
            items_all = await db.qc_items.find(
                {"run_id": run_id, "stage_id": stage_id},
                {"_id": 0},
            ).to_list(2000)
            unit_ids = await _resolve_unit_ids_for_sync(
                db, run, items_all, stage_scope
            )
            items_have_unit_id = any(i.get("unit_id") for i in items_all)
            for uid in unit_ids:
                items_for_uid = (
                    [i for i in items_all if i.get("unit_id") == uid]
                    if items_have_unit_id
                    else items_all
                )
                await sync_qc_stage_to_matrix(
                    db,
                    project_id=project_id_for_sync,
                    unit_id=uid,
                    stage_id=stage_id,
                    actor=actor_for_sync,
                    qc_items=items_for_uid,
                    stage_status="reopened",
                    stage_scope=stage_scope,
                )
        except Exception as e:
            logger.warning(
                f"[#503] QC→matrix sync (reopen) failed for stage_id={stage_id}: {e}"
            )

    background_tasks.add_task(_run_sync_reopen)
    return {"status": "reopened", "stage_id": stage_id}


@router.post("/run/{run_id}/stage/{stage_id}/override-approve")
async def override_approve_stage(
    run_id: str,
    stage_id: str,
    body: OverrideApproveBody,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """PM Override — close a stage WITHOUT per-item validation.

    Use case: PM joins existing project mid-construction; old stages
    physically done but no in-app documentation. Normal submit/approve
    flow blocks because items have no photos/notes/status.

    Restricted to:
      - membership.role == 'project_manager' on this project
      - OR super_admin
    Junior management_team CANNOT override. 'owner' role is also blocked
    (per spec D4 — override is PM-scoped only).

    Side effects:
      - All items in the stage marked 'pass' with marked_via_override=true
      - stage_statuses[stage_id] = 'approved'
      - stage_actors[stage_id] populated with override metadata
      - Audit log entry: 'qc_stage_override_approved'
      - Notifications: action='approved_via_override' (actor filtered out)
    """
    db = get_db()

    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    project_id = run["project_id"]

    role = await _get_project_role(user, project_id)
    if role != "project_manager" and not _is_super_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Override close requires project manager role",
        )

    reason = (body.reason or "").strip()
    if len(reason) < 10:
        raise HTTPException(status_code=400, detail="סיבה חייבת להכיל לפחות 10 תווים")

    stage_statuses = run.get("stage_statuses", {})
    if stage_statuses.get(stage_id) == "approved":
        raise HTTPException(status_code=400, detail="שלב זה כבר אושר")

    tpl = await _get_template(db, run=run, project_id=project_id)
    tpl_stage = next((s for s in tpl["stages"] if s["id"] == stage_id), None)
    if not tpl_stage:
        raise HTTPException(status_code=404, detail="Stage not found in template")

    actor = _actor_name(user)
    now = _now()

    await db.qc_items.update_many(
        {"run_id": run_id, "stage_id": stage_id},
        {"$set": {
            "status": "pass",
            "marked_via_override": True,
            "updated_by": user["id"],
            "updated_at": now,
        }},
    )

    await db.qc_runs.update_one(
        {"id": run_id},
        {"$set": {
            f"stage_statuses.{stage_id}": "approved",
            f"stage_actors.{stage_id}.approved_by": user["id"],
            f"stage_actors.{stage_id}.approved_by_name": actor,
            f"stage_actors.{stage_id}.approved_at": now,
            f"stage_actors.{stage_id}.via_override": True,
            f"stage_actors.{stage_id}.override_reason": reason,
        }},
    )

    await _audit("qc_stage", stage_id, "qc_stage_override_approved", user["id"], {
        "run_id": run_id,
        "floor_id": run.get("floor_id"),
        "project_id": project_id,
        "stage_id": stage_id,
        "override_reason": reason,
        "actor_name": actor,
        "stage_label": _stage_label(tpl, stage_id),
    })

    try:
        recipients = await _get_stage_recipients(db, project_id, stage_id, "approved")
        recipients = [r for r in recipients if r.get("user_id") != user["id"]]
        if recipients:
            await _create_qc_notification(
                db, recipients,
                project_id=project_id, stage_id=stage_id,
                floor_id=run.get("floor_id"), building_id=run.get("building_id"),
                stage_code=stage_id, stage_label_he=_stage_label(tpl, stage_id),
                actor_id=user["id"], actor_name_str=actor,
                action="approved_via_override", run_id=run_id,
            )
    except Exception as e:
        logger.error(f"[QC] Failed to create notifications for override: {e}")

    logger.info(
        f"[QC] Stage {stage_id} OVERRIDE APPROVED in run {run_id} "
        f"by user {user['id']}, reason: {reason[:50]}"
    )

    # #503 — multi-cell matrix sync (override path). Same pattern as
    # approve_stage but stage_closed=True regardless of item statuses
    # (override-close marks every item "pass" via update_many above,
    # so the mapping yields "completed" for all affected cells).
    project_id_for_sync = project_id
    actor_for_sync = {"id": user["id"], "name": actor}

    async def _run_sync_override():
        try:
            stage_scope = tpl_stage.get("scope", "floor")
            items_all = await db.qc_items.find(
                {"run_id": run_id, "stage_id": stage_id},
                {"_id": 0},
            ).to_list(2000)
            unit_ids = await _resolve_unit_ids_for_sync(
                db, run, items_all, stage_scope
            )
            # #503-followup-3 Bug B fix — floor-shared items pass items_all
            items_have_unit_id = any(i.get("unit_id") for i in items_all)
            for uid in unit_ids:
                items_for_uid = (
                    [i for i in items_all if i.get("unit_id") == uid]
                    if items_have_unit_id
                    else items_all
                )
                await sync_qc_stage_to_matrix(
                    db,
                    project_id=project_id_for_sync,
                    unit_id=uid,
                    stage_id=stage_id,
                    actor=actor_for_sync,
                    qc_items=items_for_uid,
                    stage_status="approved_via_override",
                    stage_scope=stage_scope,
                )
        except Exception as e:
            logger.warning(
                f"[#503] QC→matrix sync (override) failed for stage_id={stage_id}: {e}"
            )

    background_tasks.add_task(_run_sync_override)
    return {"status": "approved", "stage_id": stage_id, "via_override": True}


STAGE_TIMELINE_ACTIONS = {"submit_for_review", "qc_approved", "qc_rejected", "qc_reopened"}
ITEM_TIMELINE_ACTIONS = {"update", "item_rejected", "upload"}
ACTION_LABELS = {
    "submit_for_review": "נשלח לאישור שלב",
    "qc_approved": "אושר שלב",
    "qc_rejected": "נדחה שלב",
    "qc_reopened": "נפתח מחדש שלב",
    "item_rejected": "סעיף נדחה",
    "update": "סומן סעיף",
    "upload": "הועלתה תמונה",
}


@router.get("/run/{run_id}/stage/{stage_id}/timeline")
async def get_stage_timeline(run_id: str, stage_id: str, user: dict = Depends(get_current_user)):
    db = get_db()

    run = await db.qc_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="QC run not found")

    role = await _check_qc_access(user, run["project_id"])
    is_pm = role in PM_ROLES or _is_super_admin(user)

    is_scoped_approver = False
    if not is_pm:
        approver = await db.project_approvers.find_one({
            "project_id": run["project_id"],
            "user_id": user["id"],
            "active": True,
        })
        if approver:
            if approver.get("mode") == "all":
                is_scoped_approver = True
            elif approver.get("mode") == "stages" and stage_id in (approver.get("stages") or []):
                is_scoped_approver = True

    can_see_full = is_pm or is_scoped_approver

    stage_events = await db.audit_events.find(
        {
            "entity_type": "qc_stage",
            "entity_id": stage_id,
            "action": {"$in": list(STAGE_TIMELINE_ACTIONS)},
            "payload.run_id": run_id,
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)

    item_events = await db.audit_events.find(
        {
            "entity_type": {"$in": ["qc_item", "qc_photo"]},
            "action": {"$in": list(ITEM_TIMELINE_ACTIONS)},
            "payload.stage_id": stage_id,
            "payload.run_id": run_id,
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(30)

    all_events = stage_events + item_events
    events = sorted(all_events, key=lambda e: (e.get("created_at", ""), e.get("id", "")), reverse=True)[:30]

    tpl = await _get_template(db, run=run, project_id=run.get("project_id"))
    timeline_item_map = _build_item_map(tpl)

    timeline = []
    for ev in events:
        payload = ev.get("payload", {})
        action = ev.get("action", "")
        item_title = payload.get("item_title") or timeline_item_map.get(payload.get("item_id"), {}).get("title", "")

        if action == "item_rejected" and item_title:
            action_label = f'סעיף נדחה: {item_title}'
        elif action == "update" and item_title:
            to_status = payload.get("to_status") or payload.get("new_status", "")
            if to_status == "pass":
                action_label = f'סומן תקין: {item_title}'
            elif to_status == "fail":
                action_label = f'סומן לא תקין: {item_title}'
            else:
                action_label = f'עודכן סעיף: {item_title}'
        elif action == "upload" and item_title:
            action_label = f'הועלתה תמונה: {item_title}'
        else:
            action_label = ACTION_LABELS.get(action, action)

        event_at = ev.get("created_at", "")
        entry = {
            "id": ev.get("id"),
            "action": action,
            "action_label": action_label,
            "created_at": event_at,
            "event_at": event_at,
            "event_type": "stage" if ev.get("entity_type") == "qc_stage" else "item",
            "reason": payload.get("reason") or payload.get("note"),
        }

        meta = {}
        for mk in ("item_title", "item_id", "previous_status", "new_status", "from_status", "to_status"):
            if mk in payload:
                meta[mk] = payload[mk]
        if meta:
            entry["meta"] = meta

        if can_see_full:
            entry["actor_name"] = payload.get("actor_name", "")
            entry["actor_id"] = ev.get("actor_id")
        elif ev.get("actor_id") == user["id"]:
            entry["actor_name"] = payload.get("actor_name", "")
            entry["actor_id"] = ev.get("actor_id")
        else:
            entry["actor_name"] = None
            entry["actor_id"] = None

        timeline.append(entry)

    stage_actors = run.get("stage_actors", {}).get(stage_id, {})
    audit_summary = {}
    if can_see_full:
        audit_summary = stage_actors
    else:
        for key_prefix in ("submitted", "approved", "rejected", "reopened"):
            by_key = f"{key_prefix}_by"
            if stage_actors.get(by_key) == user["id"]:
                audit_summary[by_key] = stage_actors.get(by_key)
                audit_summary[f"{key_prefix}_by_name"] = stage_actors.get(f"{key_prefix}_by_name")
                audit_summary[f"{key_prefix}_at"] = stage_actors.get(f"{key_prefix}_at")

    return {
        "timeline": timeline,
        "audit_summary": audit_summary,
        "can_see_full": can_see_full,
    }


@notif_router.get("")
async def list_notifications(
    limit: int = Query(20, le=50),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user)
):
    db = get_db()

    total_unread = await db.qc_notifications.count_documents({
        "user_id": user["id"],
        "read_at": None,
    })

    raw = await db.qc_notifications.find(
        {"user_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)

    # Stream C1 2026-05-01 — verbs/codes for QC events (existing) + defect events (new).
    action_verbs = {
        # QC events (existing — used by qc_notifications without notification_type field)
        "submitted": "שלח לאישור",
        "approved": "אישר",
        "rejected": "דחה",
        "reopened": "פתח מחדש",
        # Defect lifecycle events (new in C1)
        "close_request": "ביקש לסגור",
        "approve": "אישר",
        "reject": "דחה",
    }
    action_to_frontend = {
        # QC events (existing — emit qc_* codes for backward compat with NotificationBell)
        "submitted": "submit_for_review",
        "approved": "qc_approved",
        "rejected": "qc_rejected",
        "reopened": "qc_reopened",
        # Defect lifecycle events (new — emit defect_* codes)
        "close_request": "defect_close_request",
        "approve": "defect_approved",
        "reject": "defect_rejected",
    }

    notifications = []
    for n in raw:
        raw_action = n.get("action", "")
        ntype = n.get("notification_type", "qc")  # legacy docs default to 'qc'

        # Build body — defect notifications carry a pre-built body field;
        # QC notifications synthesize from actor + verb + stage_label.
        if ntype in ("defect_close_request", "defect_status_change_by_pm") and n.get("body"):
            body = n["body"]
        else:
            # Legacy QC body composition (preserved verbatim).
            actor = n.get("actor_name", "")
            stage_label = n.get("stage_label_he", n.get("stage_code", ""))
            verb = action_verbs.get(raw_action, raw_action)
            body = f"{actor} {verb} את שלב \"{stage_label}\"" if actor else f"שלב \"{stage_label}\" {verb}"
            if n.get("reason"):
                body += f" — {n['reason']}"

        # Build link — defect notifications point to /tasks/{id};
        # QC notifications point to the existing run/stage URL.
        link = None
        if ntype in ("defect_close_request", "defect_status_change_by_pm"):
            if n.get("task_id"):
                link = f"/tasks/{n['task_id']}?src=bell"
        elif n.get("project_id") and n.get("floor_id") and n.get("run_id") and n.get("stage_id"):
            link = f"/projects/{n['project_id']}/floors/{n['floor_id']}/qc/{n['run_id']}/stage/{n['stage_id']}"

        notifications.append({
            "id": n["id"],
            "action": action_to_frontend.get(raw_action, raw_action),
            "body": body,
            "link": link,
            "read": n.get("read_at") is not None,
            "created_at": n.get("created_at"),
        })

    return {
        "notifications": notifications,
        "unread_count": total_unread,
    }


@notif_router.get("/unread-count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    db = get_db()
    count = await db.qc_notifications.count_documents({
        "user_id": user["id"],
        "read_at": None,
    })
    return {"unread_count": count}


@notif_router.patch("/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    result = await db.qc_notifications.update_one(
        {"id": notification_id, "user_id": user["id"]},
        {"$set": {"read_at": _now()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="התראה לא נמצאה")
    return {"status": "read"}


@notif_router.patch("/read-all")
async def mark_all_notifications_read(user: dict = Depends(get_current_user)):
    db = get_db()
    result = await db.qc_notifications.update_many(
        {"user_id": user["id"], "read_at": None},
        {"$set": {"read_at": _now()}}
    )
    return {"status": "read_all", "count": result.modified_count}
