"""Authorization and immutable monthly-account endpoints."""
from copy import deepcopy
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pymongo.errors import DuplicateKeyError

from contractor_ops.monthly_close import (
    BASELINE, _month_parts, build_account, build_snapshot, current_il_month, default_settings,
    load_inputs, month_label, next_month, suggest_stage_companies, validate_settings,
)
from contractor_ops.monthly_close_export import build_monthly_close_xlsx
from contractor_ops.notification_helpers import create_defect_notification
from contractor_ops.router import (
    _audit, _get_project_role, _is_super_admin, _now, get_current_user, get_db, get_public_base_url,
)

router = APIRouter(prefix='/api')
WRITE_ROLES = ('project_manager', 'owner')
VIEW_ROLES = WRITE_ROLES + ('management_team',)


async def _access(user, project_id, db):
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    if not project:
        raise HTTPException(404, 'הפרויקט לא נמצא')
    role = 'project_manager' if _is_super_admin(user) else await _get_project_role(user, project_id)
    company_id = None
    if role == 'contractor':
        membership = await db.project_memberships.find_one(
            {'project_id': project_id, 'user_id': user['id']}, {'_id': 0})
        company_id = (membership or {}).get('company_id')
        if not (project.get('monthly_close_settings') or {}).get('contractor_visible') or not company_id:
            raise HTTPException(403, 'אין הרשאה לחשבון החודשי')
    elif role not in VIEW_ROLES:
        raise HTTPException(403, 'אין הרשאה לחשבון החודשי')
    return {'role': role, 'company_id': company_id, 'can_write': role in WRITE_ROLES}


def _require(access, write=False):
    if (write and not access['can_write']) or (not write and access['role'] not in VIEW_ROLES):
        raise HTTPException(403, 'אין הרשאה לחשבון החודשי')


def _scope_account(account, access):
    result = deepcopy(account)
    result.pop('_id', None)
    cid = access.get('company_id')
    if access['role'] == 'contractor':
        result['contractors'] = [c for c in result.get('contractors', []) if c['company_id'] == cid]
        result['kpis'] = {key: sum(c['totals'][key] for c in result['contractors'])
                          for key in ('this_month', 'qc', 'manual')}
        corrections = [r for c in result['contractors'] for r in c.get('corrections', [])]
        result['kpis']['corrections'] = len(corrections)
        result['corrections'] = corrections
        result['unmapped_stages'] = []
        mapping = result.get('settings_snapshot', {}).get('stage_companies', {})
        mapping = {sid: company for sid, company in mapping.items() if company == cid}
        result['settings_snapshot'] = {'stage_companies': mapping}
        result['baseline_keys'] = [k for k in result.get('baseline_keys', []) if k[0] in mapping]
        stage_ids = {s['stage_id'] for c in result['contractors'] for s in c.get('stages', [])}
        result['totals'] = {**result.get('totals', {}), 'stages': len(stage_ids)}
        # A manager's project-wide free-text note is not a contractor-scoped field.
        result.pop('note', None)
    result['permissions'] = {'role': access['role'], 'can_write': access['can_write'],
        'can_close': access['can_write'] and result.get('status') != 'closed' and bool(result.get('closable')),
        'scoped_company_id': cid}
    return result


def _settings_shape(inputs, access):
    return {**inputs['settings'], 'can_write': access['can_write'],
        'stages': [{'id': s['id'], 'title': s.get('title', '')} for s in inputs['stages']],
        'companies': [{k: c.get(k, '') for k in ('id', 'name', 'trade', 'trade_label')} for c in inputs['companies']],
        'suggestions': suggest_stage_companies(inputs['stages'], inputs['companies'])}


def _live(month, inputs):
    account = build_account(month, **{k: v for k, v in inputs.items() if k != 'project'}, now=_now())
    project = inputs['project']
    account.update({'project_id': project['id'], 'project_name': project.get('name', ''),
                    'project': {'id': project['id'], 'name': project.get('name', '')}, 'is_snapshot': False})
    return account


async def _account(db, project_id, month):
    snapshot = await db.monthly_progress_closes.find_one({'project_id': project_id, 'month': month}, {'_id': 0})
    if snapshot:
        return {**snapshot, 'is_snapshot': True, 'closable': False}
    return _live(month, await load_inputs(db, project_id))


@router.get('/projects/{project_id}/monthly-close/settings')
async def get_settings(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    access = await _access(user, project_id, db)
    _require(access)
    return _settings_shape(await load_inputs(db, project_id), access)


@router.put('/projects/{project_id}/monthly-close/settings')
async def put_settings(project_id: str, body: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    access = await _access(user, project_id, db)
    _require(access, write=True)
    inputs = await load_inputs(db, project_id)
    settings = validate_settings(body, {s['id'] for s in inputs['stages']}, {c['id'] for c in inputs['companies']})
    project = inputs['project']
    old = project.get('monthly_close_settings')
    if body.get('updated_at') != (old or {}).get('updated_at'):
        raise HTTPException(409, 'ההגדרות השתנו, יש לטעון מחדש')
    predicate = {'id': project_id}
    if isinstance(old, dict):
        predicate['monthly_close_settings.updated_at'] = old.get('updated_at')
    else:
        predicate['monthly_close_settings'] = old if 'monthly_close_settings' in project else {'$exists': False}
    settings.update({'updated_at': _now(), 'updated_by': user['id']})
    result = await db.projects.update_one(predicate, {'$set': {'monthly_close_settings': settings}})
    if not result.matched_count:
        raise HTTPException(409, 'ההגדרות השתנו, יש לטעון מחדש')
    await _audit('monthly_close_settings', project_id, 'update', user['id'],
                 {k: settings[k] for k in ('stage_companies', 'contractor_visible')})
    inputs['settings'] = settings
    return _settings_shape(inputs, access)


@router.get('/projects/{project_id}/monthly-close/months')
async def get_months(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    await _access(user, project_id, db)
    snapshots = await db.monthly_progress_closes.find({'project_id': project_id},
        {'_id': 0, 'month': 1, 'label': 1, 'closed_at': 1, 'closed_by': 1}).sort('month', -1).to_list(None)
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    current = current_il_month()
    return {'current_month': current, 'next_closable': next_month(snapshots[0]['month']) if snapshots else current,
        'closed': [{'month': s['month'], 'label': s['label'], 'closed_at': s['closed_at'],
                    'closed_by_name': s.get('closed_by', {}).get('name', '')} for s in snapshots],
        'contractor_visible': (project.get('monthly_close_settings') or default_settings())['contractor_visible']}


@router.get('/projects/{project_id}/monthly-close/{month}')
async def get_month(project_id: str, month: str, user: dict = Depends(get_current_user)):
    db = get_db()
    access = await _access(user, project_id, db)
    _month_parts(month)
    return _scope_account(await _account(db, project_id, month), access)


@router.post('/projects/{project_id}/monthly-close/{month}/close')
async def close_month(project_id: str, month: str, body: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    access = await _access(user, project_id, db)
    _require(access, write=True)
    _month_parts(month)
    if await db.monthly_progress_closes.find_one({'project_id': project_id, 'month': month}, {'_id': 0}):
        raise HTTPException(409, 'החודש כבר נסגר')
    inputs = await load_inputs(db, project_id)
    account = _live(month, inputs)
    if month > current_il_month():
        raise HTTPException(422, 'אי אפשר לסגור חודש עתידי')
    if month != account['next_closable']:
        raise HTTPException(422, f"אפשר לסגור רק את {month_label(account['next_closable'])}")
    if not any(c.get('stages') for c in account['contractors']):
        raise HTTPException(422, 'אין שלבים משויכים לקבלנים — הגדר שיוך לפני הסגירה')
    if body.get('note') is not None and not isinstance(body['note'], str):
        raise HTTPException(422, 'הערה לא תקינה')
    doc = build_snapshot(account, inputs['project'], user, body.get('note'), _now())
    try:
        await db.monthly_progress_closes.insert_one(deepcopy(doc))
    except DuplicateKeyError:
        raise HTTPException(409, 'החודש כבר נסגר')
    await _audit('monthly_close', doc['id'], 'close', user['id'],
                 {'month': month, 'this_month': doc['kpis']['this_month'], 'contractors': len(doc['contractors'])})
    if inputs['settings'].get('contractor_visible'):
        for company in doc['contractors']:
            memberships = await db.project_memberships.find(
                {'project_id': project_id, 'role': 'contractor', 'company_id': company['company_id']},
                {'_id': 0, 'user_id': 1}).to_list(None)
            await create_defect_notification(db, list({m['user_id'] for m in memberships}),
                notification_type='monthly_close', action='month_closed', task_id=doc['id'],
                task_title=doc['label'], project_id=project_id, actor_id=user['id'], actor_name=user.get('name', ''),
                body=f"חשבון {doc['label']} בפרויקט {inputs['project'].get('name', '')} נסגר — הדוח שלך מוכן",
                extra={'month': month, 'company_id': company['company_id']})
    return _scope_account({**doc, 'is_snapshot': True, 'closable': False}, access)


@router.post('/projects/{project_id}/monthly-close/{month}/export.xlsx')
async def export_xlsx(project_id: str, month: str, body: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    access = await _access(user, project_id, db)
    _month_parts(month)
    company_id = body.get('company_id')
    if access['role'] == 'contractor' and company_id != access['company_id']:
        raise HTTPException(403, 'אין הרשאה לחשבון החודשי')
    account = _scope_account(await _account(db, project_id, month), access)
    company = next((c for c in account['contractors'] if c['company_id'] == company_id), None)
    if not company:
        raise HTTPException(404, 'הקבלן לא נמצא בחשבון')
    project = account.get('project') or {'id': project_id, 'name': account.get('project_name', '')}
    stream = build_monthly_close_xlsx(project, account, company, get_public_base_url())
    filename = f"דוח התקדמות לחשבון - {company['name']} - {month}.xlsx"
    return StreamingResponse(stream, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f"attachment; filename=\"progress-account-{month}.xlsx\"; filename*=UTF-8''{quote(filename)}"})