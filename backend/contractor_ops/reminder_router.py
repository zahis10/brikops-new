import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import CRON_SECRET
from . import reminder_service
from contractor_ops.router import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["reminders"])
cron_router = APIRouter(tags=["cron"])

_get_current_user = None
_require_roles = None

ALLOWED_ROLES = {"project_manager", "owner", "super_admin", "management_team"}


async def _check_reminder_access(user: dict, project_id: str):
    if user.get("platform_role") == "super_admin":
        return
    db = get_db()
    membership = await db.project_memberships.find_one({
        "user_id": user["id"],
        "project_id": project_id,
    })
    if not membership or membership.get("role") not in ("project_manager", "owner", "management_team"):
        raise HTTPException(status_code=403, detail="אין לך הרשאה לשלוח תזכורות בפרויקט זה")


async def _check_reminder_rate_limit(
    kind: str, key: str, max_requests: int, window_seconds: int
) -> bool:
    """
    Per-user rate limit for manual reminder endpoints.
    Returns True if within limit, False if exceeded.
    Fail-open on infra errors (don't block legitimate users on DB hiccups).
    Added 2026-05-16 from pentest HIGH-N1.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    new_expires = now + timedelta(seconds=window_seconds)
    pipeline = [
        {"$set": {
            "count": {"$cond": {
                "if": {"$lte": [{"$ifNull": ["$expires_at", now - timedelta(seconds=1)]}, now]},
                "then": 1,
                "else": {"$add": [{"$ifNull": ["$count", 0]}, 1]},
            }},
            "expires_at": {"$cond": {
                "if": {"$lte": [{"$ifNull": ["$expires_at", now - timedelta(seconds=1)]}, now]},
                "then": new_expires,
                "else": {"$ifNull": ["$expires_at", new_expires]},
            }},
            "updated_at": now,
        }},
    ]
    for attempt in range(2):
        try:
            result = await db.reminder_rate_limits.find_one_and_update(
                {"kind": kind, "key": key},
                pipeline,
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            return result["count"] <= max_requests
        except DuplicateKeyError:
            if attempt == 0:
                continue
            return False  # fail-closed on persistent race
        except Exception as e:
            logger.warning(f"[REMINDER-RL] Rate limit check failed: {e} — allowing request")
            return True  # fail-open on infra errors
    return False


def create_reminder_router(require_roles, get_current_user):
    global _get_current_user, _require_roles
    _get_current_user = get_current_user
    _require_roles = require_roles

    @router.post("/projects/{project_id}/reminders/contractor/{company_id}")
    async def manual_contractor_reminder(
        project_id: str,
        company_id: str,
        user: dict = Depends(get_current_user),
    ):
        await _check_reminder_access(user, project_id)
        # Rate limit: max 10 manual reminders per user per project per hour
        # (anti-spam — pentest HIGH-N1 2026-05-16, shared budget with digest)
        rate_key = f"{user['id']}:{project_id}"
        if not await _check_reminder_rate_limit("manual_reminder", rate_key, max_requests=10, window_seconds=3600):
            raise HTTPException(
                status_code=429,
                detail="יותר מדי תזכורות ידניות בשעה האחרונה — חכה לפני שליחה נוספת"
            )
        result = await reminder_service.send_contractor_reminder(
            project_id=project_id,
            company_id=company_id,
            triggered_by=f"manual:{user['id']}",
            skip_cooldown=True,
            skip_preferences=True,
        )
        if result.get("status") == "skipped":
            reason = result.get("reason", "")
            if reason == "no_open_defects":
                raise HTTPException(status_code=400, detail="אין ליקויים פתוחים לקבלן זה")
            elif reason == "no_valid_phone":
                raise HTTPException(status_code=400, detail="לא נמצא מספר טלפון תקין לקבלן")
            raise HTTPException(status_code=400, detail=f"לא ניתן לשלוח תזכורת: {reason}")
        results = result.get("results", [])
        sent = sum(1 for r in results if r.get("status") == "sent")
        failed = sum(1 for r in results if r.get("status") == "failed")
        if sent == 0 and failed > 0:
            raise HTTPException(status_code=502, detail="שליחת התזכורת נכשלה לכל הנמענים")
        return result

    @router.post("/projects/{project_id}/reminders/digest")
    async def manual_pm_digest(
        project_id: str,
        user: dict = Depends(get_current_user),
    ):
        await _check_reminder_access(user, project_id)
        # Rate limit: shared budget with contractor reminder (same kind/key)
        rate_key = f"{user['id']}:{project_id}"
        if not await _check_reminder_rate_limit("manual_reminder", rate_key, max_requests=10, window_seconds=3600):
            raise HTTPException(
                status_code=429,
                detail="יותר מדי תזכורות ידניות בשעה האחרונה — חכה לפני שליחה נוספת"
            )
        result = await reminder_service.send_pm_digest(
            project_id=project_id,
            triggered_by=f"manual:{user['id']}",
            skip_preferences=True,
        )
        if result.get("status") == "skipped":
            reason = result.get("reason", "")
            if reason == "no_meaningful_data":
                raise HTTPException(status_code=400, detail="אין נתונים משמעותיים לסיכום")
            raise HTTPException(status_code=400, detail=f"לא ניתן לשלוח סיכום: {reason}")
        results = result.get("results", [])
        sent = sum(1 for r in results if r.get("status") == "sent")
        failed = sum(1 for r in results if r.get("status") == "failed")
        if sent == 0 and failed > 0:
            raise HTTPException(status_code=502, detail="שליחת הסיכום נכשלה לכל הנמענים")
        return result

    @router.get("/users/me/reminder-preferences")
    async def get_reminder_preferences(
        user: dict = Depends(get_current_user),
    ):
        db = get_db()
        user_doc = await db.users.find_one({"id": user["id"]}, {"_id": 0, "reminder_preferences": 1})
        prefs = (user_doc or {}).get("reminder_preferences", {})
        defaults = {"enabled": True, "days": [0, 1, 2, 3, 4]}
        return {
            "contractor_reminder": {**defaults, **prefs.get("contractor_reminder", {})},
            "pm_digest": {**defaults, **prefs.get("pm_digest", {})},
        }

    @router.put("/users/me/reminder-preferences")
    async def update_reminder_preferences(
        request: Request,
        user: dict = Depends(get_current_user),
    ):
        body = await request.json()
        validated = {}
        valid_days = {0, 1, 2, 3, 4}
        for key in ("contractor_reminder", "pm_digest"):
            if key not in body:
                continue
            section = body[key]
            if not isinstance(section, dict):
                raise HTTPException(status_code=400, detail=f"{key} חייב להיות אובייקט")
            entry = {}
            if "enabled" in section:
                if not isinstance(section["enabled"], bool):
                    raise HTTPException(status_code=400, detail=f"{key}.enabled חייב להיות true או false")
                entry["enabled"] = section["enabled"]
            if "days" in section:
                days = section["days"]
                if not isinstance(days, list):
                    raise HTTPException(status_code=400, detail=f"{key}.days חייב להיות מערך")
                for d in days:
                    if not isinstance(d, int) or d not in valid_days:
                        raise HTTPException(status_code=400, detail=f"{key}.days: ערך לא חוקי {d}. ערכים אפשריים: 0-4 (ראשון עד חמישי)")
                if len(days) != len(set(days)):
                    raise HTTPException(status_code=400, detail=f"{key}.days: ערכים כפולים")
                entry["days"] = sorted(set(days))
            if entry:
                validated[key] = entry
        if not validated:
            raise HTTPException(status_code=400, detail="לא נשלחו הגדרות לעדכון")
        db = get_db()
        current = (await db.users.find_one({"id": user["id"]}, {"_id": 0, "reminder_preferences": 1}) or {}).get("reminder_preferences", {})
        for k, v in validated.items():
            current[k] = {**current.get(k, {}), **v}
        await db.users.update_one({"id": user["id"]}, {"$set": {"reminder_preferences": current}})
        logger.info(f"[REMINDER-PREFS] User {user['id']} updated preferences: {validated}")
        defaults = {"enabled": True, "days": [0, 1, 2, 3, 4]}
        return {
            "contractor_reminder": {**defaults, **current.get("contractor_reminder", {})},
            "pm_digest": {**defaults, **current.get("pm_digest", {})},
        }

    @cron_router.post("/internal/cron/daily-reminders")
    async def cron_daily_reminders(request: Request):
        cron_secret = request.headers.get("X-Cron-Secret", "")
        if not CRON_SECRET or cron_secret != CRON_SECRET:
            logger.warning("[CRON] Invalid or missing X-Cron-Secret")
            raise HTTPException(status_code=403, detail="Forbidden")

        shabbat = reminder_service.is_shabbat()
        if shabbat:
            logger.info(f"[CRON] Skipping daily reminders: {shabbat}")
            return {"skipped": shabbat}

        reminder_type = request.query_params.get("type", "all")
        response = {}

        if reminder_type in ("digest", "all"):
            digest_result = await reminder_service.send_all_pm_digests()
            response["digest"] = digest_result
            logger.info(f"[CRON] PM digests: sent={digest_result['sent']} skipped={digest_result['skipped']} failed={digest_result['failed']}")

        if reminder_type in ("contractor", "all"):
            contractor_result = await reminder_service.send_all_contractor_reminders()
            response["contractor"] = contractor_result
            logger.info(f"[CRON] Contractor reminders: sent={contractor_result['sent']} skipped={contractor_result['skipped']} failed={contractor_result['failed']}")

        return response

    @cron_router.post("/internal/cron/daily-renewals")
    async def cron_daily_renewals(request: Request):
        cron_secret = request.headers.get("X-Cron-Secret", "")
        if not CRON_SECRET or cron_secret != CRON_SECRET:
            logger.warning("[CRON] Invalid or missing X-Cron-Secret for daily-renewals")
            raise HTTPException(status_code=403, detail="Forbidden")

        from contractor_ops.billing import BILLING_V1_ENABLED
        if not BILLING_V1_ENABLED:
            return {"skipped": "billing_disabled"}

        from contractor_ops.billing_router import billing_run_renewals_internal
        result = await billing_run_renewals_internal()
        return result

    return router, cron_router
