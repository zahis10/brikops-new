from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from contractor_ops.activity_hours import IL_TZ, active_now, platform_heatmap
from contractor_ops.admin_analytics import _require_super_admin
from contractor_ops.router import get_current_user, get_db

router = APIRouter(prefix="/api/admin/analytics")


@router.get("/active-now")
async def get_active_now(
    minutes: int = Query(15),
    user: dict = Depends(get_current_user),
):
    if minutes < 5 or minutes > 60:
        raise HTTPException(status_code=422, detail="minutes must be between 5 and 60")
    _require_super_admin(user)
    now = datetime.now(timezone.utc)
    result = await active_now(get_db(), minutes, now)
    result["generated_at"] = now.isoformat()
    result["today"] = now.astimezone(IL_TZ).date().isoformat()
    return result


@router.get("/hourly")
async def get_hourly(
    days: int = Query(7),
    org_id: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    if days not in (7, 30):
        raise HTTPException(status_code=422, detail="days must be 7 or 30")
    _require_super_admin(user)
    now = datetime.now(timezone.utc)
    result = await platform_heatmap(get_db(), days, now, org_id)
    result["generated_at"] = now.isoformat()
    result["today"] = now.astimezone(IL_TZ).date().isoformat()
    return result