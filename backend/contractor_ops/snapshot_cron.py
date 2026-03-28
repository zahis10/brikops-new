import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, HTTPException
from config import CRON_SECRET
from contractor_ops.router import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cron"])

try:
    import zoneinfo
    IL_TZ = zoneinfo.ZoneInfo("Asia/Jerusalem")
except ImportError:
    from dateutil import tz as _tz
    IL_TZ = _tz.gettz("Asia/Jerusalem")

TERMINAL_STATUSES = {"closed", "done", "cancelled"}
ACTIVE_STATUSES = {"open", "assigned", "in_progress", "pending_contractor_proof",
                   "returned_to_contractor", "reopened", "pending_manager_approval",
                   "waiting_verify"}


def _israel_today() -> str:
    return datetime.now(IL_TZ).strftime("%Y-%m-%d")


def _israel_day_start_utc(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    local_start = dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=IL_TZ)
    return local_start.astimezone(timezone.utc).isoformat()


@router.post("/internal/cron/daily-snapshots")
async def cron_daily_snapshots(request: Request):
    cron_secret = request.headers.get("X-Cron-Secret", "")
    if not CRON_SECRET or cron_secret != CRON_SECRET:
        logger.warning("[SNAPSHOT-CRON] Invalid or missing X-Cron-Secret")
        raise HTTPException(status_code=403, detail="Forbidden")

    db = get_db()
    today = _israel_today()
    day_start_utc = _israel_day_start_utc(today)
    now_utc = datetime.now(timezone.utc).isoformat()

    projects = await db.projects.find(
        {"status": {"$nin": ["archived", "deleted"]}},
        {"_id": 0, "id": 1, "org_id": 1}
    ).to_list(None)

    if not projects:
        logger.info("[SNAPSHOT-CRON] No active projects found")
        return {"date": today, "snapshots_created": 0, "skipped": 0}

    project_ids = [p["id"] for p in projects]
    project_org_map = {p["id"]: p.get("org_id", "") for p in projects}

    existing = await db.daily_project_snapshots.find(
        {"date": today, "project_id": {"$in": project_ids}},
        {"_id": 0, "project_id": 1}
    ).to_list(None)
    existing_ids = {doc["project_id"] for doc in existing}

    new_project_ids = [pid for pid in project_ids if pid not in existing_ids]
    if not new_project_ids:
        logger.info(f"[SNAPSHOT-CRON] All {len(project_ids)} projects already have snapshots for {today}")
        return {"date": today, "snapshots_created": 0, "skipped": len(project_ids)}

    defect_agg = await db.tasks.aggregate([
        {"$match": {"project_id": {"$in": new_project_ids}}},
        {"$group": {
            "_id": "$project_id",
            "total": {"$sum": 1},
            "open": {"$sum": {"$cond": [{"$in": ["$status", list(ACTIVE_STATUSES)]}, 1, 0]}},
            "in_progress": {"$sum": {"$cond": [{"$in": ["$status", ["in_progress", "pending_contractor_proof", "pending_manager_approval", "returned_to_contractor"]]}, 1, 0]}},
            "closed": {"$sum": {"$cond": [{"$in": ["$status", list(TERMINAL_STATUSES)]}, 1, 0]}},
            "overdue": {"$sum": {"$cond": [
                {"$and": [
                    {"$ne": ["$due_date", None]},
                    {"$lt": ["$due_date", today]},
                    {"$not": {"$in": ["$status", list(TERMINAL_STATUSES)]}}
                ]}, 1, 0
            ]}},
            "created_today": {"$sum": {"$cond": [{"$gte": ["$created_at", day_start_utc]}, 1, 0]}},
            "closed_today": {"$sum": {"$cond": [
                {"$and": [
                    {"$in": ["$status", list(TERMINAL_STATUSES)]},
                    {"$gte": ["$updated_at", day_start_utc]}
                ]}, 1, 0
            ]}},
        }}
    ]).to_list(None)
    defect_map = {r["_id"]: r for r in defect_agg}

    qc_agg = await db.qc_runs.aggregate([
        {"$match": {"project_id": {"$in": new_project_ids}}},
        {"$unwind": "$stages"},
        {"$unwind": "$stages.items"},
        {"$group": {
            "_id": "$project_id",
            "total_items": {"$sum": 1},
            "checked": {"$sum": {"$cond": [
                {"$in": ["$stages.items.status", ["pass", "fail", "na"]]}, 1, 0
            ]}},
        }}
    ]).to_list(None)
    qc_map = {r["_id"]: r for r in qc_agg}

    handover_agg = await db.handover_protocols.aggregate([
        {"$match": {"project_id": {"$in": new_project_ids}}},
        {"$group": {
            "_id": "$project_id",
            "total_units": {"$sum": 1},
            "signed": {"$sum": {"$cond": [{"$eq": ["$status", "signed"]}, 1, 0]}},
            "in_progress": {"$sum": {"$cond": [{"$in": ["$status", ["in_progress", "partially_signed"]]}, 1, 0]}},
            "not_started": {"$sum": {"$cond": [{"$in": ["$status", ["draft", "not_started"]]}, 1, 0]}},
        }}
    ]).to_list(None)
    handover_map = {r["_id"]: r for r in handover_agg}

    membership_agg = await db.project_memberships.aggregate([
        {"$match": {"project_id": {"$in": new_project_ids}}},
        {"$group": {"_id": "$project_id", "total": {"$sum": 1}}}
    ]).to_list(None)
    membership_map = {r["_id"]: r["total"] for r in membership_agg}

    membership_users = await db.project_memberships.find(
        {"project_id": {"$in": new_project_ids}},
        {"_id": 0, "project_id": 1, "user_id": 1}
    ).to_list(None)
    project_user_ids = {}
    all_user_ids = set()
    for m in membership_users:
        project_user_ids.setdefault(m["project_id"], []).append(m["user_id"])
        all_user_ids.add(m["user_id"])

    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    user_logins = {}
    if all_user_ids:
        login_docs = await db.users.find(
            {"id": {"$in": list(all_user_ids)}},
            {"_id": 0, "id": 1, "last_login_at": 1}
        ).to_list(None)
        user_logins = {u["id"]: u.get("last_login_at", "") for u in login_docs}

    photos_agg = await db.task_updates.aggregate([
        {"$match": {
            "project_id": {"$in": new_project_ids},
            "attachment_url": {"$exists": True, "$ne": None},
            "created_at": {"$gte": day_start_utc},
        }},
        {"$group": {"_id": "$project_id", "count": {"$sum": 1}}}
    ]).to_list(None)
    photos_map = {r["_id"]: r["count"] for r in photos_agg}

    wa_sent_agg = await db.notification_jobs.aggregate([
        {"$match": {
            "channel": "whatsapp",
            "status": {"$in": ["sent", "delivered", "read"]},
            "created_at": {"$gte": day_start_utc},
            "task_id": {"$exists": True},
        }},
        {"$lookup": {
            "from": "tasks",
            "localField": "task_id",
            "foreignField": "id",
            "as": "task_doc",
            "pipeline": [{"$project": {"_id": 0, "project_id": 1}}]
        }},
        {"$unwind": "$task_doc"},
        {"$group": {"_id": "$task_doc.project_id", "count": {"$sum": 1}}}
    ]).to_list(None)
    wa_map = {r["_id"]: r["count"] for r in wa_sent_agg}

    snapshots = []
    for pid in new_project_ids:
        d = defect_map.get(pid, {})
        q = qc_map.get(pid, {})
        h = handover_map.get(pid, {})
        total_members = membership_map.get(pid, 0)

        user_ids_for_project = project_user_ids.get(pid, [])
        active_today = sum(1 for uid in user_ids_for_project if user_logins.get(uid, "") >= day_start_utc)
        active_7d = sum(1 for uid in user_ids_for_project if user_logins.get(uid, "") >= seven_days_ago)

        qc_total = q.get("total_items", 0)
        qc_checked = q.get("checked", 0)
        qc_pct = round(qc_checked / qc_total * 100, 1) if qc_total > 0 else 0.0

        h_total = h.get("total_units", 0)
        h_signed = h.get("signed", 0)
        h_in_progress = h.get("in_progress", 0)
        h_not_started = h.get("not_started", 0)
        h_pct = round(h_signed / h_total * 100, 1) if h_total > 0 else 0.0

        snapshots.append({
            "project_id": pid,
            "org_id": project_org_map.get(pid, ""),
            "date": today,
            "defects": {
                "open": d.get("open", 0),
                "in_progress": d.get("in_progress", 0),
                "closed": d.get("closed", 0),
                "overdue": d.get("overdue", 0),
                "created_today": d.get("created_today", 0),
                "closed_today": d.get("closed_today", 0),
            },
            "qc": {
                "total_items": qc_total,
                "checked": qc_checked,
                "completion_pct": qc_pct,
            },
            "handover": {
                "total_units": h_total,
                "signed": h_signed,
                "in_progress": h_in_progress,
                "not_started": h_not_started,
                "completion_pct": h_pct,
            },
            "team": {
                "total_members": total_members,
                "active_today": active_today,
                "active_7d": active_7d,
            },
            "photos_uploaded_today": photos_map.get(pid, 0),
            "whatsapp_sent_today": wa_map.get(pid, 0),
            "created_at": now_utc,
        })

    created_count = 0
    if snapshots:
        try:
            result = await db.daily_project_snapshots.insert_many(snapshots, ordered=False)
            created_count = len(result.inserted_ids)
        except Exception as e:
            details = getattr(e, 'details', {})
            created_count = details.get('nInserted', 0)
            logger.warning(f"[SNAPSHOT-CRON] Bulk insert error: {e} — nInserted={created_count}")

    logger.info(f"[SNAPSHOT-CRON] date={today} created={created_count} skipped={len(existing_ids)}")
    return {
        "date": today,
        "snapshots_created": created_count,
        "skipped": len(existing_ids),
    }
