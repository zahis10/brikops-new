import logging
from fastapi import APIRouter, Request, Depends, HTTPException

from config import CRON_SECRET
from . import reminder_service
from contractor_ops.router import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["reminders"])
cron_router = APIRouter(tags=["cron"])

_get_current_user = None
_require_roles = None

ALLOWED_ROLES = {"project_manager", "owner", "super_admin"}


async def _check_reminder_access(user: dict, project_id: str):
    if user.get("platform_role") == "super_admin":
        return
    db = get_db()
    membership = await db.project_memberships.find_one({
        "user_id": user["id"],
        "project_id": project_id,
    })
    if not membership or membership.get("role") not in ("project_manager", "owner"):
        raise HTTPException(status_code=403, detail="אין לך הרשאה לשלוח תזכורות בפרויקט זה")


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
        result = await reminder_service.send_contractor_reminder(
            project_id=project_id,
            company_id=company_id,
            triggered_by=f"manual:{user['id']}",
            skip_cooldown=True,
        )
        if result.get("status") == "skipped":
            reason = result.get("reason", "")
            if reason == "no_open_defects":
                raise HTTPException(status_code=400, detail="אין ליקויים פתוחים לקבלן זה")
            elif reason == "no_valid_phone":
                raise HTTPException(status_code=400, detail="לא נמצא מספר טלפון תקין לקבלן")
            raise HTTPException(status_code=400, detail=f"לא ניתן לשלוח תזכורת: {reason}")
        return result

    @router.post("/projects/{project_id}/reminders/digest")
    async def manual_pm_digest(
        project_id: str,
        user: dict = Depends(get_current_user),
    ):
        await _check_reminder_access(user, project_id)
        result = await reminder_service.send_pm_digest(
            project_id=project_id,
            triggered_by=f"manual:{user['id']}",
        )
        if result.get("status") == "skipped":
            reason = result.get("reason", "")
            if reason == "no_meaningful_data":
                raise HTTPException(status_code=400, detail="אין נתונים משמעותיים לסיכום")
            raise HTTPException(status_code=400, detail=f"לא ניתן לשלוח סיכום: {reason}")
        return result

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

    return router, cron_router
