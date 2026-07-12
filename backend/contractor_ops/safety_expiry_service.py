"""BATCH safety-w1-alerts — proactive WhatsApp expiry alerts (30/14/7/0)
for safety equipment checks + worker trainings.

Rides the EXISTING daily reminders job (scheduler daily lock + Shabbat skip).
Recipient resolution mirrors the PM-digest path (project_manager + owner
memberships, prefs / dormant / wa-disabled / cooldown checks — all REUSED
from reminder_service, never re-implemented).

Message composition = TEMPLATE PARAMS ONLY — the Meta-approved template
`safety_expiry_alert` (he, Utility) has 3 NAMED params: project / items /
count, and a dynamic-URL button with base https://app.brikops.com/safety/
(button param = suffix only, "{project_id}?src=wa").
Meta FORBIDS newlines inside params — items are ׀-separated and asserted
newline-free before send.
"""
import logging
from datetime import date

from contractor_ops import reminder_service
from contractor_ops.reminder_service import (
    SEND_PACING_SECONDS,
    _check_cooldown,
    _check_user_reminder_prefs,
    _is_user_dormant,
    _log_reminder,
    _resolve_phone_for_user,
    _send_wa_template,
    _user_disabled_whatsapp,
    mask_phone,
)
# Import ONLY — the safety package itself is never modified here.
from contractor_ops.safety.equipment import (
    _build_check_status,
    _equipment_latest_checks,
)

logger = logging.getLogger(__name__)

REMINDER_TYPE = "safety_expiry"
ALERT_THRESHOLDS = {30, 14, 7, 0}
MAX_ITEMS_IN_MESSAGE = 10
ITEM_SEPARATOR = " ׀ "

# Hebrew labels for the 10 fixed Cemento equipment categories (mirror of the
# FE safetyLabels EQUIPMENT_CATEGORY_HE map). Custom categories are free-text
# (already Hebrew) and pass through as-is.
EQUIPMENT_CATEGORY_HE = {
    "lifting_accessories": "אביזרי הרמה",
    "lifting_platform": "במת הרמה",
    "electrical_panel": "לוח חשמל ראשי / משני",
    "air_compressor": "קולט אוויר",
    "formwork": "טפסות",
    "forklift": "מלגזה",
    "temporary_power": "מתקן חשמל ארעי",
    "crane_regular": "עגורן (לא עגורן צריח)",
    "tower_crane": "עגורן צריח",
    "scaffolding": "פיגומים",
}

# Bug C semantics (same as the contractor sweep): only live projects alert.
ACTIVE_PROJECT_FILTER = {
    "status": "active",
    "$or": [
        {"archived": {"$exists": False}},
        {"archived": False},
        {"archived": None},
    ],
}


def _days_left(expires_at: str, today: str):
    """(expires_at - today).days for YYYY-MM-DD strings; None if malformed."""
    try:
        return (date.fromisoformat(expires_at) - date.fromisoformat(today)).days
    except (ValueError, TypeError):
        return None


def _expiry_phrase(days_left: int) -> str:
    return "פג היום" if days_left == 0 else f"פג בעוד {days_left} ימים"


def _sanitize_param(text: str) -> str:
    """Meta forbids newlines inside template params — strip defensively."""
    return " ".join(str(text).split())


async def collect_expiry_alerts(db, today: str) -> dict:
    """Return {project_id: {"items": [...], "total": N}} for all items whose
    days_left ∈ {30, 14, 7, 0} today.

    TRAININGS — ONE aggregation; only the NEWEST record per
    (worker_id, training_type) counts (p3c fix1/fix2 grouping — superseded
    records never alert). Trainings of soft-deleted workers are excluded.
    EQUIPMENT — active + non-deleted items; per-track latest check via the
    EXISTING _equipment_latest_checks + _build_check_status.
    """
    payloads: dict = {}

    def _add(project_id: str, item: dict):
        payloads.setdefault(project_id, {"items": [], "total": 0})
        payloads[project_id]["items"].append(item)
        payloads[project_id]["total"] += 1

    # ---- TRAININGS (one aggregation, newest-per-group) -------------------
    pipeline = [
        {"$match": {"deletedAt": None, "expires_at": {"$ne": None}}},
        {"$sort": {"trained_at": -1, "created_at": -1}},
        {"$group": {
            "_id": {"p": "$project_id", "w": "$worker_id", "t": "$training_type"},
            "doc": {"$first": "$$ROOT"},
        }},
    ]
    training_hits = []
    async for row in db.safety_trainings.aggregate(pipeline):
        doc = row["doc"]
        dl = _days_left(doc.get("expires_at") or "", today)
        if dl in ALERT_THRESHOLDS:
            training_hits.append(doc)

    if training_hits:
        worker_ids = sorted({t["worker_id"] for t in training_hits})
        workers = await db.safety_workers.find(
            {"id": {"$in": worker_ids}, "deletedAt": None},
            {"_id": 0, "id": 1, "full_name": 1},
        ).to_list(len(worker_ids))
        worker_names = {w["id"]: w.get("full_name") or "עובד" for w in workers}
        for t in training_hits:
            name = worker_names.get(t["worker_id"])
            if name is None:
                continue  # worker soft-deleted → no alert
            dl = _days_left(t["expires_at"], today)
            _add(t["project_id"], {
                "kind": "training",
                "days_left": dl,
                "label": _sanitize_param(
                    f"🎓 {name} — {t.get('training_type', '')} {_expiry_phrase(dl)}"
                ),
            })

    # ---- EQUIPMENT (per project: latest per track via existing helpers) --
    project_ids = await db.safety_equipment.distinct(
        "project_id", {"status": "active", "deletedAt": None}
    )
    for pid in sorted(project_ids):
        items = await db.safety_equipment.find(
            {"project_id": pid, "status": "active", "deletedAt": None},
            {"_id": 0, "id": 1, "category": 1, "internal_code": 1},
        ).to_list(1000)
        if not items:
            continue
        latest_map = await _equipment_latest_checks(db, pid, [it["id"] for it in items])
        for it in items:
            for entry in _build_check_status(it["category"], latest_map.get(it["id"], {}), today):
                expires_at = entry.get("expires_at")
                if not expires_at:
                    continue
                dl = _days_left(expires_at, today)
                if dl not in ALERT_THRESHOLDS:
                    continue
                cat_he = EQUIPMENT_CATEGORY_HE.get(it["category"], it["category"])
                _add(pid, {
                    "kind": "equipment",
                    "days_left": dl,
                    "label": _sanitize_param(
                        f"🔧 {it.get('internal_code', '')} ({cat_he}) — "
                        f"{entry.get('check_name', '')} {_expiry_phrase(dl)}"
                    ),
                })

    return payloads


def _compose_params(project_name: str, payload: dict) -> tuple:
    """Build the 3 NAMED template params. Returns (body_params, item_count).

    items: most-urgent-first, ׀-separated, capped at MAX_ITEMS_IN_MESSAGE
    with a trailing "+ עוד X"; count = UNCAPPED total. NO newlines anywhere
    (Meta rule) — hard-asserted.
    """
    items = sorted(payload["items"], key=lambda x: (x["days_left"], x["label"]))
    total = payload["total"]
    shown = [it["label"] for it in items[:MAX_ITEMS_IN_MESSAGE]]
    overflow = total - len(shown)
    if overflow > 0:
        shown.append(f"+ עוד {overflow}")
    items_text = ITEM_SEPARATOR.join(shown)

    body_params = [
        {"parameter_name": "project", "text": _sanitize_param(project_name)},
        {"parameter_name": "items", "text": items_text},
        {"parameter_name": "count", "text": str(total)},
    ]
    for p in body_params:
        assert "\n" not in p["text"] and "\r" not in p["text"], \
            "Meta template params must not contain newlines"
    return body_params, total


async def send_all_safety_expiry_alerts() -> dict:
    """Daily sweep — one aggregated message per (project, recipient).

    Exact-day thresholds keep the sweep idempotent; the scheduler's daily
    lock prevents double-runs; the reminder-log cooldown (REUSED) is a belt-
    and-braces guard against manual double-invocation on the same day.
    """
    db = reminder_service._db
    summary = {"sent": 0, "skipped": 0, "failed": 0, "projects": []}
    try:
        from contractor_ops.utils.timezone import IL_TZ
        from datetime import datetime
        today = datetime.now(IL_TZ).strftime("%Y-%m-%d")

        payloads = await collect_expiry_alerts(db, today)
        if not payloads:
            logger.info("[SAFETY-EXPIRY] No expiring items today — nothing to send")
            return summary

        from config import WA_TEMPLATE_SAFETY_EXPIRY

        for project_id in sorted(payloads.keys()):
            payload = payloads[project_id]
            project = await db.projects.find_one(
                {"id": project_id, **ACTIVE_PROJECT_FILTER},
                {"_id": 0, "id": 1, "name": 1, "org_id": 1},
            )
            if not project:
                summary["skipped"] += 1
                continue

            # Recipients — EXACTLY the PM-digest membership resolution.
            memberships = await db.project_memberships.find({
                "project_id": project_id,
                "role": {"$in": ["project_manager", "owner"]},
            }, {"_id": 0}).to_list(100)

            body_params, total = _compose_params(project.get("name", ""), payload)
            base_sent = summary["sent"]
            base_skipped = summary["skipped"]
            base_failed = summary["failed"]

            for mem in memberships:
                user = await db.users.find_one({"id": mem["user_id"]}, {"_id": 0})
                if not user:
                    continue
                user_id = user.get("id", "")

                if _user_disabled_whatsapp(user):
                    summary["skipped"] += 1
                    logger.info(f"[SAFETY-EXPIRY] Skipping user {user_id}: whatsapp_disabled")
                    continue
                if _is_user_dormant(user):
                    summary["skipped"] += 1
                    logger.info(f"[SAFETY-EXPIRY] Skipping user {user_id}: dormant")
                    continue
                pref_skip = _check_user_reminder_prefs(user, REMINDER_TYPE)
                if pref_skip:
                    summary["skipped"] += 1
                    logger.info(f"[SAFETY-EXPIRY] Skipping user {user_id}: {pref_skip}")
                    continue
                phone = _resolve_phone_for_user(user)
                if not phone:
                    summary["skipped"] += 1
                    logger.info(f"[SAFETY-EXPIRY] Skipping user {user_id}: no_valid_phone")
                    continue
                if await _check_cooldown(project_id, REMINDER_TYPE, user_id=user_id):
                    summary["skipped"] += 1
                    logger.info(f"[SAFETY-EXPIRY] Skipping user {user_id}: cooldown")
                    continue

                log_entry = {
                    "type": REMINDER_TYPE,
                    "recipient_user_id": user_id,
                    "recipient_phone": phone,
                    "project_id": project_id,
                    "org_id": project.get("org_id", ""),
                    "message_template": WA_TEMPLATE_SAFETY_EXPIRY,
                    "item_count": total,
                    "alert_date": today,
                    "triggered_by": "cron",
                }
                try:
                    button_params = [{"index": 0, "text": f"{project_id}?src=wa"}]
                    wa_result = await _send_wa_template(
                        phone, WA_TEMPLATE_SAFETY_EXPIRY, body_params,
                        button_params=button_params,
                    )
                    log_entry["status"] = "sent"
                    log_entry["wa_message_id"] = wa_result.get("provider_message_id", "")
                    summary["sent"] += 1
                    logger.info(
                        f"[SAFETY-EXPIRY] Alert sent project={project_id} "
                        f"to={mask_phone(phone)} items={total}"
                    )
                except Exception as e:
                    log_entry["status"] = "failed"
                    log_entry["error_detail"] = str(e)[:500]
                    summary["failed"] += 1
                    logger.error(
                        f"[SAFETY-EXPIRY] Send failed project={project_id} "
                        f"to={mask_phone(phone)}: {e}"
                    )
                await _log_reminder(log_entry)
                import asyncio
                await asyncio.sleep(SEND_PACING_SECONDS)

            # One run-level audit entry per (project, date) — ALWAYS written
            # (even when every recipient was skipped) for traceability.
            await _log_reminder({
                "type": "safety_expiry_run",
                "project_id": project_id,
                "org_id": project.get("org_id", ""),
                "alert_date": today,
                "item_count": total,
                "status": "completed",
                "sent": summary["sent"] - base_sent,
                "skipped": summary["skipped"] - base_skipped,
                "failed": summary["failed"] - base_failed,
                "triggered_by": "cron",
            })
            summary["projects"].append(project_id)
    except Exception as e:
        logger.critical(f"[SAFETY-EXPIRY] Catastrophic failure: {e}")
        summary["critical_error"] = str(e)[:500]

    return summary
