"""Generic notification creation for defect lifecycle events.

Extends the existing qc_notifications collection (legacy name kept per
Zahi 2026-05-01 — no DB migration). New docs include `notification_type`
field; existing QC docs do not (treated as type 'qc' in list endpoint).
"""
import uuid
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


NOTIFICATION_TYPES = {
    'qc',                              # legacy QC stage events (existing)
    'defect_close_request',            # contractor uploaded proof, PM needs to approve
    'defect_status_change_by_pm',      # PM approved/rejected, contractor needs to know
}


async def create_defect_notification(
    db,
    recipients,
    *,
    notification_type: str,
    action: str,
    task_id: str,
    task_title: str,
    project_id: str,
    actor_id: str,
    actor_name: str,
    body: str,
    reason: str = None,
):
    """Insert one notification doc per recipient into qc_notifications.

    recipients: iterable of user_ids. Actor is auto-excluded.
    notification_type: one of NOTIFICATION_TYPES.
    action: raw verb (e.g. 'close_request', 'approved', 'rejected'). Mapped
            to a frontend code by the list endpoint.
    body: pre-built Hebrew display string ("{actor} ביקש לסגור ...").
    """
    if notification_type not in NOTIFICATION_TYPES:
        logger.warning(f"[NOTIF] Unknown notification_type='{notification_type}', skipping")
        return []

    now = _now()
    docs = []
    for uid in recipients:
        if not uid or uid == actor_id:
            continue
        docs.append({
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "notification_type": notification_type,
            "action": action,
            "task_id": task_id,
            "task_title": task_title,
            "project_id": project_id,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "body": body,
            "reason": reason,
            "created_at": now,
            "read_at": None,
        })
    if docs:
        await db.qc_notifications.insert_many(docs)
        logger.info(
            f"[NOTIF] Created {len(docs)} notifications type={notification_type} "
            f"action={action} task_id={task_id}"
        )
    return docs


async def get_defect_recipients_for_close_request(db, project_id: str):
    """For Event 1 (defect_close_request): return list of user_ids who can
    approve in this project = project_manager + management_team members."""
    memberships = await db.project_memberships.find(
        {"project_id": project_id, "role": {"$in": ["project_manager", "management_team"]}},
        {"_id": 0, "user_id": 1}
    ).to_list(100)
    return [m["user_id"] for m in memberships if m.get("user_id")]


def build_close_request_body(actor_name: str, task_title: str) -> str:
    """Body for Event 1: contractor wants to close a defect."""
    actor = actor_name or "קבלן"
    title = task_title or "ליקוי"
    return f"{actor} ביקש לסגור ליקוי \"{title}\" — ממתין לאישורך"


def build_status_change_body(decision: str, task_title: str, reason: str = None) -> str:
    """Body for Event 2: PM decided on contractor's proof."""
    title = task_title or "ליקוי"
    if decision == "approve":
        return f"המנהל אישר את התיקון של \"{title}\""
    elif decision == "reject":
        base = f"המנהל דחה את התיקון של \"{title}\""
        if reason:
            return f"{base} — {reason}"
        return base
    # Defensive: unknown decision
    return f"סטטוס השתנה: \"{title}\""
