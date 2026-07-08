"""
Work Diary (יומן עבודה) — Batch diary-d1 (D1 of 4: backend only, no UI).

Implements the 9 locked concept decisions (2026-07-08):
  (1) one diary per project per day (unique active index)
  (2) work-manager signature mandatory; second_signature RESERVED (no setter)
  (3) one-tap no-work day
  (4) retro-fill allowed, honestly marked entered_late (server-derived, immutable)
  (5) signed = immutable forever; additions via addendum only
  (6) worker counts DERIVED with manual override + visible per-item source
  (7) online-first — the draft lives on the server from creation
  (8) entry point is project-level (D2 concern)
  (9) every derived section fully manual-editable; the safety module
      ENHANCES, never gates — derivation is fail-soft and works (as empty)
      for projects that never touched the safety module.

Registration in server.py is GATED by ENABLE_WORK_DIARY env flag.
When the flag is off, this module is never imported and endpoints 404.

NO DELETE endpoint by design (evidence posture — the diary is a legal
record; a future admin batch may add soft-delete with retention).
"""
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pymongo.errors import DuplicateKeyError

from services.object_storage import generate_url

from contractor_ops.router import (
    get_current_user, get_db, _now, _audit,
    _check_project_access, require_roles,
)
from contractor_ops.schemas import (
    WorkDiaryEntry, WorkDiaryCreate, WorkDiaryUpdate, WorkDiaryAddendumCreate,
)
# The diary is a work-manager instrument — same writer roles as safety.
# Import of the ROLE TUPLE only; no route/flag coupling (the safety package
# registers routes on ITS OWN router, which server.py includes separately).
from contractor_ops.safety._shared import SAFETY_WRITERS, _new_id
from contractor_ops.upload_rate_limit import check_upload_rate_limit, check_upload_bytes
from contractor_ops.upload_quota import check_storage_quota, record_upload
from contractor_ops.upload_safety import (
    validate_upload, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES,
)
from contractor_ops.utils.timezone import israel_today

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/work-diary", tags=["work-diary"])

# Sections the derivation engine owns. Lists merge per-item by source;
# defect_counts is a dict replaced only when still source=="derived".
DERIVED_LIST_SECTIONS = (
    "workers_by_company", "equipment_list", "subcontractors",
    "incidents_summary", "tours_summary", "trainings_summary",
)


# =====================================================================
# Derivation (decisions 6+9) — ALL fail-soft: a failed source yields an
# empty section, never a 500. Zero dependency on ENABLE_SAFETY_MODULE —
# for non-safety projects the collections are simply empty.
# =====================================================================
async def _derive_sections(db, project_id: str, diary_date: str) -> dict:
    date_prefix = {"$regex": f"^{re.escape(diary_date)}"}

    workers_by_company = []
    try:
        # ONE aggregation: non-deleted workers grouped by company_id.
        groups = await db.safety_workers.aggregate([
            {"$match": {"project_id": project_id, "deletedAt": None}},
            {"$group": {"_id": "$company_id", "count": {"$sum": 1}}},
        ]).to_list(200)
        if groups:
            companies = await db.project_companies.find(
                {"project_id": project_id, "deletedAt": None},
                {"_id": 0, "id": 1, "name": 1},
            ).to_list(500)
            name_by_id = {c["id"]: c.get("name", "") for c in companies}
            for g in groups:
                cid = g["_id"]
                workers_by_company.append({
                    "company_id": cid,
                    "company_name": name_by_id.get(cid) or ("ללא חברה" if cid is None else "ללא חברה"),
                    "count": g["count"],
                    "source": "derived",
                })
            workers_by_company.sort(key=lambda w: -w["count"])
    except Exception as e:
        logger.warning(f"[DIARY] workers derivation failed (fail-soft): {e}")
        workers_by_company = []

    equipment_list = []
    try:
        items = await db.safety_equipment.find(
            {"project_id": project_id, "deletedAt": None, "status": "active"},
            {"_id": 0, "internal_code": 1, "category": 1},
        ).to_list(500)
        equipment_list = [
            {"internal_code": it.get("internal_code"), "category": it.get("category"),
             "source": "derived"}
            for it in items
        ]
    except Exception as e:
        logger.warning(f"[DIARY] equipment derivation failed (fail-soft): {e}")
        equipment_list = []

    subcontractors = []
    try:
        comps = await db.project_companies.find(
            {"project_id": project_id, "deletedAt": None},
            {"_id": 0, "id": 1, "name": 1},
        ).to_list(500)
        subcontractors = [
            {"company_id": c["id"], "name": c.get("name", ""), "source": "derived"}
            for c in comps
        ]
    except Exception as e:
        logger.warning(f"[DIARY] subcontractors derivation failed (fail-soft): {e}")
        subcontractors = []

    incidents_summary = []
    try:
        incs = await db.safety_incidents.find(
            {"project_id": project_id, "deletedAt": None, "occurred_at": date_prefix},
            {"_id": 0, "id": 1, "incident_type": 1, "description": 1},
        ).to_list(200)
        incidents_summary = [
            {"incident_id": i.get("id"), "incident_type": i.get("incident_type"),
             "description": i.get("description"), "source": "derived"}
            for i in incs
        ]
    except Exception as e:
        logger.warning(f"[DIARY] incidents derivation failed (fail-soft): {e}")
        incidents_summary = []

    tours_summary = []
    try:
        tours = await db.safety_tours.find(
            {"project_id": project_id, "deletedAt": None, "tour_date": diary_date},
            {"_id": 0, "id": 1, "tour_type": 1, "status": 1},
        ).to_list(200)
        tours_summary = [
            {"tour_id": t.get("id"), "tour_type": t.get("tour_type"),
             "status": t.get("status"), "source": "derived"}
            for t in tours
        ]
    except Exception as e:
        logger.warning(f"[DIARY] tours derivation failed (fail-soft): {e}")
        tours_summary = []

    defect_counts = None
    try:
        # DOCUMENTED CHOICE (per batch): opened = defects created that date;
        # closed = cheap heuristic — same-day updated_at with a terminal
        # status (resolved/verified). NO audit-log scan for exact flips.
        opened = await db.safety_documents.count_documents({
            "project_id": project_id, "kind": "defect", "deletedAt": None,
            "created_at": date_prefix,
        })
        closed = await db.safety_documents.count_documents({
            "project_id": project_id, "kind": "defect", "deletedAt": None,
            "updated_at": date_prefix, "status": {"$in": ["resolved", "verified"]},
        })
        defect_counts = {"opened": opened, "closed": closed, "source": "derived"}
    except Exception as e:
        logger.warning(f"[DIARY] defect counts derivation failed (fail-soft): {e}")
        defect_counts = None

    trainings_summary = []
    try:
        # Same-day trainings are ALL real events — newest-per-group logic
        # (fix1/fix2) is intentionally irrelevant here.
        trs = await db.safety_trainings.find(
            {"project_id": project_id, "deletedAt": None, "trained_at": diary_date},
            {"_id": 0, "id": 1, "worker_id": 1, "training_type": 1},
        ).to_list(500)
        worker_ids = list({t["worker_id"] for t in trs if t.get("worker_id")})
        names = {}
        if worker_ids:
            ws = await db.safety_workers.find(
                {"id": {"$in": worker_ids}}, {"_id": 0, "id": 1, "full_name": 1},
            ).to_list(len(worker_ids))
            names = {w["id"]: w.get("full_name", "") for w in ws}
        trainings_summary = [
            {"training_id": t.get("id"), "worker_name": names.get(t.get("worker_id"), ""),
             "training_type": t.get("training_type"), "source": "derived"}
            for t in trs
        ]
    except Exception as e:
        logger.warning(f"[DIARY] trainings derivation failed (fail-soft): {e}")
        trainings_summary = []

    return {
        "workers_by_company": workers_by_company,
        "equipment_list": equipment_list,
        "subcontractors": subcontractors,
        "incidents_summary": incidents_summary,
        "tours_summary": tours_summary,
        "defect_counts": defect_counts,
        "trainings_summary": trainings_summary,
    }


def _with_display_url(entry: dict) -> dict:
    """3c pattern: signature key at rest, presigned display URL per-GET only."""
    s = entry.get("worker_signature")
    if s and s.get("signature_ref"):
        try:
            s["signature_display_url"] = generate_url(s["signature_ref"])
        except Exception:
            s["signature_display_url"] = None
    return entry


async def _get_entry_or_404(db, project_id: str, entry_id: str) -> dict:
    entry = await db.work_diary_entries.find_one(
        {"id": entry_id, "project_id": project_id, "deletedAt": None}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="diary entry not found")
    return entry


# =====================================================================
# 2.1 CREATE
# =====================================================================
@router.post("/{project_id}/entries")
async def create_diary_entry(
    project_id: str,
    payload: WorkDiaryCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    existing = await db.work_diary_entries.find_one(
        {"project_id": project_id, "diary_date": payload.diary_date, "deletedAt": None},
        {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(status_code=409, detail="כבר קיים יומן לתאריך זה")

    now = _now()
    today_il = israel_today()
    # Decision 4 — honest retro-fill marker, server-derived, IMMUTABLE.
    entered_late = payload.diary_date < today_il

    doc = {
        "id": _new_id(),
        "project_id": project_id,
        "diary_date": payload.diary_date,
        "status": "draft",
        "no_work": payload.no_work,
        "no_work_reason": (payload.no_work_reason or None),
        "entered_late": entered_late,
        "workers_by_company": [],
        "equipment_list": [],
        "subcontractors": [],
        "work_description": None,
        "materials": [],
        "special_instructions": None,
        "incidents_summary": [],
        "tours_summary": [],
        "defect_counts": None,
        "trainings_summary": [],
        "inspector_visit": None,
        "photo_refs": [],
        "weather": None,
        "worker_signature": None,
        "second_signature": None,   # reserved (decision 2) — no setter in D1
        "addendums": [],
        "created_at": now,
        "created_by": user["id"],
        "updated_at": None,
        "signed_at": None,
        "deletedAt": None,
        "deletedBy": None,
        "deletion_reason": None,
        "retention_until": None,
    }

    if payload.no_work:
        # Decision 3 — one-tap no-work day: skip derivation entirely.
        reason = (payload.no_work_reason or "").strip()
        doc["work_description"] = "לא בוצעה עבודה" + (f" — {reason}" if reason else "")
    else:
        doc.update(await _derive_sections(db, project_id, payload.diary_date))

    try:
        await db.work_diary_entries.insert_one(doc)
    except DuplicateKeyError:
        # Unique index closes the pre-check race window.
        raise HTTPException(status_code=409, detail="כבר קיים יומן לתאריך זה")

    await _audit("work_diary", doc["id"], "created", user["id"], {
        "project_id": project_id, "diary_date": payload.diary_date,
        "no_work": payload.no_work, "entered_late": entered_late,
    })
    doc.pop("_id", None)
    return WorkDiaryEntry(**doc)


# =====================================================================
# 2.2 LIST + GET
# =====================================================================
@router.get("/{project_id}/entries")
async def list_diary_entries(
    project_id: str,
    month: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    q = {"project_id": project_id, "deletedAt": None}
    if month:
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            raise HTTPException(status_code=422, detail="חודש לא תקין (נדרש YYYY-MM)")
        q["diary_date"] = {"$regex": f"^{re.escape(month)}"}

    total = await db.work_diary_entries.count_documents(q)
    items = await db.work_diary_entries.find(q, {"_id": 0}).sort(
        "diary_date", -1).to_list(400)
    return {"items": [_with_display_url(i) for i in items], "total": total}


@router.get("/{project_id}/entries/{entry_id}")
async def get_diary_entry(
    project_id: str,
    entry_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)
    entry = await _get_entry_or_404(db, project_id, entry_id)
    return _with_display_url(entry)


# =====================================================================
# 2.3 PATCH — DRAFT ONLY (decision 5)
# =====================================================================
@router.patch("/{project_id}/entries/{entry_id}")
async def update_diary_entry(
    project_id: str,
    entry_id: str,
    payload: WorkDiaryUpdate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    entry = await _get_entry_or_404(db, project_id, entry_id)
    if entry["status"] == "signed":
        raise HTTPException(status_code=409, detail="היומן חתום — ניתן להוסיף תוספת בלבד")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return _with_display_url(entry)
    updates["updated_at"] = _now()
    # ATOMIC draft re-assert: closes the read→write race against a
    # concurrent signer (decision 5 — signed is immutable, no exceptions).
    upd = await db.work_diary_entries.update_one(
        {"id": entry_id, "project_id": project_id, "deletedAt": None,
         "status": "draft"},
        {"$set": updates})
    if upd.matched_count == 0:
        raise HTTPException(status_code=409, detail="היומן חתום — ניתן להוסיף תוספת בלבד")
    await _audit("work_diary", entry_id, "updated", user["id"], {
        "project_id": project_id, "fields": sorted(k for k in updates if k != "updated_at"),
    })
    after = await _get_entry_or_404(db, project_id, entry_id)
    return _with_display_url(after)


# =====================================================================
# 2.4 REFRESH DERIVED — DRAFT ONLY; manual data survives
# =====================================================================
@router.post("/{project_id}/entries/{entry_id}/refresh-derived")
async def refresh_derived_sections(
    project_id: str,
    entry_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    entry = await _get_entry_or_404(db, project_id, entry_id)
    if entry["status"] == "signed":
        raise HTTPException(status_code=409, detail="היומן חתום — ניתן להוסיף תוספת בלבד")

    fresh = await _derive_sections(db, project_id, entry["diary_date"])
    updates = {}
    for section in DERIVED_LIST_SECTIONS:
        manual_items = [i for i in (entry.get(section) or [])
                        if isinstance(i, dict) and i.get("source") == "manual"]
        updates[section] = manual_items + (fresh.get(section) or [])
    # defect_counts is a dict — overwrite only while still derived (or empty).
    existing_dc = entry.get("defect_counts")
    if existing_dc is None or (isinstance(existing_dc, dict) and existing_dc.get("source") == "derived"):
        updates["defect_counts"] = fresh.get("defect_counts")
    updates["updated_at"] = _now()

    # ATOMIC draft re-assert (same race-closure as PATCH).
    upd = await db.work_diary_entries.update_one(
        {"id": entry_id, "project_id": project_id, "deletedAt": None,
         "status": "draft"},
        {"$set": updates})
    if upd.matched_count == 0:
        raise HTTPException(status_code=409, detail="היומן חתום — ניתן להוסיף תוספת בלבד")
    await _audit("work_diary", entry_id, "derived_refreshed", user["id"], {
        "project_id": project_id, "diary_date": entry["diary_date"],
    })
    after = await _get_entry_or_404(db, project_id, entry_id)
    return _with_display_url(after)


# =====================================================================
# 2.5 SIGNATURE — mirrors sign_training's 3c chain EXACTLY + atomic claim
# =====================================================================
@router.post("/{project_id}/entries/{entry_id}/signature")
async def sign_diary_entry(
    project_id: str,
    entry_id: str,
    signer_name: str = Form(...),
    signature_type: str = Form(...),
    typed_name: str = Form(None),
    signature_image: UploadFile = File(None),
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    entry = await _get_entry_or_404(db, project_id, entry_id)
    if entry["status"] == "signed" or entry.get("worker_signature"):
        raise HTTPException(status_code=409, detail="היומן כבר חתום")
    if not entry.get("no_work") and not (entry.get("work_description") or "").strip():
        raise HTTPException(status_code=422, detail="יש למלא תיאור עבודות לפני חתימה")
    name = (signer_name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="יש להזין שם")

    signature_ref = None
    if signature_type == "canvas":
        if signature_image is None:
            raise HTTPException(status_code=422, detail="חסרה תמונת חתימה")
        # Upload-hardening mirror of sign_training — same helpers, same order.
        check_upload_rate_limit(user["id"])
        validate_upload(signature_image, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES)
        img_bytes = await signature_image.read()
        if len(img_bytes) == 0:
            raise HTTPException(status_code=400, detail="קובץ ריק")
        check_upload_bytes(user["id"], len(img_bytes))
        _proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "org_id": 1})
        _org_id = (_proj or {}).get("org_id")
        await check_storage_quota(_org_id, len(img_bytes))
        from services.object_storage import save_bytes as _save_bytes
        s3_key = f"diaries/{project_id}/{entry_id}/sig_{_new_id()}.png"
        signature_ref = _save_bytes(img_bytes, s3_key, "image/png")
        await record_upload(_org_id, len(img_bytes))
    elif signature_type == "typed":
        if not (typed_name or "").strip():
            raise HTTPException(status_code=422, detail="יש להזין שם")
    else:
        raise HTTPException(status_code=422, detail="סוג חתימה לא מוכר")

    now = _now()
    sig = {
        "name": name,
        "signed_at": now,
        "signature_ref": signature_ref,
        "signature_type": signature_type,
        "typed_name": (typed_name.strip() if (signature_type == "typed" and typed_name) else None),
        "captured_by": user["id"],
    }
    # ATOMIC claim: re-assert draft + unsigned → concurrent signer loses.
    upd = await db.work_diary_entries.update_one(
        {"id": entry_id, "project_id": project_id, "deletedAt": None,
         "status": "draft", "worker_signature": None},
        {"$set": {"worker_signature": sig, "status": "signed",
                  "signed_at": now, "updated_at": now}},
    )
    if upd.modified_count == 0:
        raise HTTPException(status_code=409, detail="היומן כבר חתום")
    await _audit("work_diary", entry_id, "signed", user["id"], {
        "project_id": project_id, "signature_type": signature_type,
    })
    after = await _get_entry_or_404(db, project_id, entry_id)
    return _with_display_url(after)


# =====================================================================
# 2.6 ADDENDUM — SIGNED ONLY, append-only (decision 5)
# =====================================================================
@router.post("/{project_id}/entries/{entry_id}/addendums")
async def add_diary_addendum(
    project_id: str,
    entry_id: str,
    payload: WorkDiaryAddendumCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    entry = await _get_entry_or_404(db, project_id, entry_id)
    if entry["status"] != "signed":
        raise HTTPException(status_code=409, detail="היומן עדיין טיוטה — ערוך אותו ישירות")

    addendum = {"text": payload.text, "created_at": _now(), "created_by": user["id"]}
    # $push ONLY — never touches any other field on the signed record.
    await db.work_diary_entries.update_one(
        {"id": entry_id, "project_id": project_id, "deletedAt": None},
        {"$push": {"addendums": addendum}})
    await _audit("work_diary", entry_id, "addendum_added", user["id"], {
        "project_id": project_id,
    })
    after = await _get_entry_or_404(db, project_id, entry_id)
    return _with_display_url(after)


# =====================================================================
# Index management — called from server.py startup when module enabled.
# =====================================================================
async def ensure_work_diary_indexes(db) -> None:
    """
    Idempotent, background. The unique index includes deletedAt (null for
    all active docs) because Mongo partialFilterExpression cannot express
    {deletedAt: null}; with NO delete endpoint in D1 every doc has
    deletedAt=None, so (project_id, diary_date) uniqueness holds exactly.
    """
    await db.work_diary_entries.create_index(
        [("project_id", 1), ("diary_date", 1), ("deletedAt", 1)],
        unique=True, background=True, name="uniq_wd_project_date_active",
    )
    await db.work_diary_entries.create_index(
        [("project_id", 1), ("status", 1)],
        background=True, name="idx_wd_project_status",
    )
    logger.info("Work diary indices ensured (2 total)")
