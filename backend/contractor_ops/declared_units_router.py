from fastapi import APIRouter, Depends, HTTPException

from contractor_ops.billing import get_subscription
from contractor_ops.declared_units import is_trial_status, validate_declared_units
from contractor_ops.router import (
    get_db, get_current_user, _check_project_access, _check_structure_admin,
    _audit, _now, logger,
)

router = APIRouter(prefix="/api")


@router.put("/projects/{project_id}/declared-units")
async def update_declared_units(project_id: str, body: dict,
                                user: dict = Depends(get_current_user)):
    await _check_project_access(user, project_id)
    await _check_structure_admin(user, project_id)
    db = get_db()
    project = await db.projects.find_one(
        {'id': project_id}, {'_id': 0, 'id': 1, 'org_id': 1, 'total_units': 1, 'name': 1},
    )
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    sub = await get_subscription(project['org_id'])
    if not is_trial_status(sub):
        raise HTTPException(status_code=403, detail={
            'detail': 'מחוץ לתקופת הניסיון שינוי הכמות המוצהרת נעשה בבקשה לאדמין',
            'error_code': 'NOT_TRIAL',
        })
    active_count = await db.units.count_documents(
        {'project_id': project_id, 'archived': {'$ne': True}},
    )
    try:
        new_total = validate_declared_units(
            body.get('total_units'), project.get('total_units') or 0, active_count,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.projects.update_one(
        {'id': project_id}, {'$set': {'total_units': new_total, 'updated_at': _now()}},
    )
    await _audit('project', project_id, 'total_units_changed', user['id'],
                 {'previous': project.get('total_units'), 'new': new_total,
                  'reason': 'pm_trial_update', 'org_id': project['org_id']})
    logger.info("[DECLARED-UNITS] project=%s org=%s %s -> %s (actor=%s, trial)",
                project_id, project['org_id'], project.get('total_units'), new_total, user['id'])
    return {'ok': True, 'project_id': project_id,
            'previous_total_units': project.get('total_units'), 'new_total_units': new_total}
