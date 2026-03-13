from fastapi import APIRouter, HTTPException, Depends, Query, Request
from typing import Optional
from datetime import datetime, timezone
import uuid
import re

from contractor_ops.router import (
    get_db, get_current_user,
    require_super_admin, require_stepup,
    _audit_admin_access, _hash_password,
    _is_super_admin, logger,
)
from contractor_ops.phone_utils import normalize_israeli_phone
from contractor_ops.stepup_service import (
    create_challenge as stepup_create_challenge,
    verify_challenge as stepup_verify_challenge,
)
from contractor_ops.billing import (
    admin_billing_override, get_subscription, _resolve_access,
)

router = APIRouter(prefix="/api")


@router.post("/admin/stepup/request")
async def stepup_request(request: Request, user: dict = Depends(require_super_admin)):
    user_id = user.get('id', '')
    sv = user.get('_jwt_sv', user.get('session_version', 0))
    ip = request.headers.get('x-forwarded-for', request.client.host if request.client else '')
    ua = request.headers.get('user-agent', '')
    request_id = getattr(request.state, 'request_id', '')

    result = await stepup_create_challenge(
        user_id, sv,
        platform_role=user.get('platform_role', ''),
        request_id=request_id,
        ip=ip,
        ua=ua,
    )

    status = 'success' if result['success'] else result.get('error', 'unknown')
    http_code = 200 if result['success'] else (
        429 if status == 'rate_limited' else
        503 if status == 'smtp_unavailable' else 500
    )
    await _audit_admin_access(user_id, '/api/admin/stepup/request', 'POST',
                               http_code, ip, ua, f'stepup_request:{status}')

    if not result['success']:
        if result.get('error') == 'smtp_unavailable':
            raise HTTPException(
                status_code=503,
                detail={'message': result['message'], 'code': 'STEPUP_UNAVAILABLE_SMTP'},
            )
        code = 429 if result.get('error') == 'rate_limited' else 500
        raise HTTPException(status_code=code, detail=result.get('message', 'שגיאה בשליחת קוד.'))

    resp = {
        'challenge_id': result['challenge_id'],
        'masked_email': result['masked_email'],
        'ttl_seconds': result['ttl_seconds'],
    }
    if result.get('fallback'):
        resp['fallback'] = True
    return resp


@router.post("/admin/stepup/verify")
async def stepup_verify(request: Request, user: dict = Depends(require_super_admin)):
    body = await request.json()
    challenge_id = body.get('challenge_id', '')
    code = body.get('code', '')
    user_id = user.get('id', '')
    sv = user.get('_jwt_sv', user.get('session_version', 0))
    ip = request.headers.get('x-forwarded-for', request.client.host if request.client else '')
    ua = request.headers.get('user-agent', '')

    if not challenge_id or not code:
        raise HTTPException(status_code=400, detail='חסר challenge_id או code.')

    result = await stepup_verify_challenge(challenge_id, code, user_id, sv)

    status = 'success' if result['success'] else result.get('error', 'unknown')
    await _audit_admin_access(user_id, '/api/admin/stepup/verify', 'POST',
                               200 if result['success'] else 403,
                               ip, ua, f'stepup_verify:{status}')

    if not result['success']:
        raise HTTPException(status_code=403, detail=result.get('message', 'אימות נכשל.'))

    return {
        'success': True,
        'grant_ttl_seconds': result['grant_ttl_seconds'],
        'message': result['message'],
    }


@router.post("/admin/revoke-session/{user_id}")
async def admin_revoke_session(user_id: str, request: Request, admin: dict = Depends(require_stepup)):
    db = get_db()
    target_user = await db.users.find_one({'id': user_id}, {'_id': 0, 'id': 1, 'name': 1, 'session_version': 1})
    if not target_user:
        raise HTTPException(status_code=404, detail='User not found')
    old_sv = target_user.get('session_version', 0)
    new_sv = old_sv + 1
    await db.users.update_one({'id': user_id}, {'$set': {'session_version': new_sv}})
    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'session_revoked',
        'actor_id': admin['id'],
        'target_user_id': user_id,
        'old_session_version': old_sv,
        'new_session_version': new_sv,
        'ip': request.headers.get('x-forwarded-for', request.client.host if request.client else ''),
        'user_agent': request.headers.get('user-agent', '')[:200],
        'created_at': datetime.now(timezone.utc).isoformat(),
    })
    return {'success': True, 'user_id': user_id, 'new_session_version': new_sv}



@router.post("/admin/billing/override")
async def admin_override(request: Request, user: dict = Depends(require_stepup)):
    body = await request.json()
    org_id = body.get('org_id')
    action = body.get('action')
    until = body.get('until')
    note = body.get('note', '')

    if not org_id or not action:
        raise HTTPException(status_code=400, detail='חובה לציין org_id ו-action')
    if not note or not note.strip():
        raise HTTPException(status_code=400, detail='חובה לציין הערה (note)')

    result = await admin_billing_override(user['id'], org_id, action, until, note)
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error', 'שגיאה'))
    return result


@router.post("/admin/billing/apply-pending-decreases")
async def admin_apply_pending_decreases(user: dict = Depends(require_super_admin)):
    from contractor_ops.billing import BILLING_V1_ENABLED, apply_pending_decreases
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    count = await apply_pending_decreases()
    return {'applied': count}


@router.get("/admin/billing/payment-requests-summary")
async def admin_payment_requests_summary(user: dict = Depends(require_super_admin)):
    from contractor_ops.billing import BILLING_V1_ENABLED, list_open_payment_requests_all
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    result = await list_open_payment_requests_all()
    return result


@router.get("/admin/billing/orgs")
async def admin_list_orgs(user: dict = Depends(require_super_admin)):
    db = get_db()
    orgs = await db.organizations.find({}, {'_id': 0}).to_list(1000)
    result = []
    for org in orgs:
        sub = await get_subscription(org['id'])
        owner_uid = org.get('owner_user_id')
        owner = await db.users.find_one({'id': owner_uid}, {'_id': 0, 'name': 1, 'email': 1, 'phone_e164': 1}) if owner_uid else None
        access, reason = _resolve_access(sub)
        result.append({
            **org,
            'subscription': sub,
            'owner': owner,
            'effective_access': access.value,
            'read_only_reason': reason,
        })
    return result


@router.get("/admin/orgs/{org_id}/projects")
async def admin_org_projects(org_id: str, user: dict = Depends(require_super_admin)):
    db = get_db()
    projects = await db.projects.find(
        {"org_id": org_id}, {"_id": 0}
    ).to_list(100)
    for p in projects:
        member_count = await db.project_memberships.count_documents({"project_id": p["id"]})
        p["member_count"] = member_count
    return projects


@router.get("/admin/billing/audit")
async def admin_billing_audit(user: dict = Depends(require_super_admin)):
    db = get_db()
    events = await db.audit_events.find(
        {'entity_type': {'$in': ['subscription', 'billing_plan', 'project_billing', 'project']}},
        {'_id': 0}
    ).sort('created_at', -1).to_list(200)
    for ev in events:
        actor = await db.users.find_one({'id': ev.get('actor_id')}, {'_id': 0, 'name': 1})
        ev['actor_name'] = actor.get('name', '') if actor else ''
    return events


@router.get("/admin/billing/plans")
async def admin_list_plans(user: dict = Depends(require_super_admin)):
    from contractor_ops.billing import BILLING_V1_ENABLED
    from contractor_ops.billing_plans import list_plans
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    plans = await list_plans()
    return plans


@router.post("/admin/billing/plans")
async def admin_create_plan(request: Request, user: dict = Depends(require_stepup)):
    from contractor_ops.billing import BILLING_V1_ENABLED
    from contractor_ops.billing_plans import create_plan
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    body = await request.json()
    try:
        plan = await create_plan(body, user['id'])
        return plan
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/admin/billing/plans/{plan_id}")
async def admin_update_plan(plan_id: str, request: Request, user: dict = Depends(require_stepup)):
    from contractor_ops.billing import BILLING_V1_ENABLED
    from contractor_ops.billing_plans import update_plan
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    body = await request.json()
    try:
        plan = await update_plan(plan_id, body, user['id'])
        return plan
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/admin/billing/plans/{plan_id}/deactivate")
async def admin_deactivate_plan(plan_id: str, user: dict = Depends(require_stepup)):
    from contractor_ops.billing import BILLING_V1_ENABLED
    from contractor_ops.billing_plans import deactivate_plan
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    try:
        result = await deactivate_plan(plan_id, user['id'])
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/billing/migration/dry-run")
async def admin_migration_dry_run(user: dict = Depends(require_super_admin)):
    from contractor_ops.billing import BILLING_V1_ENABLED, dry_run_org_id_backfill
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    result = await dry_run_org_id_backfill()
    return result


@router.post("/admin/billing/migration/apply")
async def admin_migration_apply(user: dict = Depends(require_stepup)):
    from contractor_ops.billing import BILLING_V1_ENABLED, apply_org_id_backfill
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    result = await apply_org_id_backfill(user['id'])
    return result


@router.get("/admin/users")
async def admin_list_users(
    q: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_super_admin),
):
    import time as _t
    t_start = _t.perf_counter()
    db = get_db()
    query = {}
    if q and q.strip():
        q_stripped = q.strip()
        q_escaped = re.escape(q_stripped)
        digits = re.sub(r'[-\s()\u200e\u200f]', '', q_stripped)
        phone_conditions = [{'phone_e164': {'$regex': q_escaped}}]
        if digits.startswith('0') and 5 <= len(digits) <= 10:
            phone_conditions.append({'phone_e164': {'$regex': re.escape('+972' + digits[1:])}})
        query['$or'] = [
            {'name': {'$regex': q_escaped, '$options': 'i'}},
            *phone_conditions,
            {'email': {'$regex': q_escaped, '$options': 'i'}},
            {'id': q_stripped},
        ]

    t0 = _t.perf_counter()
    total = await db.users.count_documents(query)
    users = await db.users.find(query, {'_id': 0, 'password_hash': 0}).sort('created_at', -1).skip(skip).limit(limit).to_list(limit)
    db_list_ms = round((_t.perf_counter() - t0) * 1000, 1)

    user_ids = [u['id'] for u in users]

    t0 = _t.perf_counter()
    org_mems = await db.organization_memberships.find(
        {'user_id': {'$in': user_ids}}, {'_id': 0, 'user_id': 1, 'org_id': 1, 'role': 1}
    ).to_list(len(user_ids))
    org_mem_map = {m['user_id']: m for m in org_mems}

    org_ids = list({m['org_id'] for m in org_mems if m.get('org_id')})
    orgs = await db.organizations.find({'id': {'$in': org_ids}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(len(org_ids))
    org_name_map = {o['id']: o.get('name', '') for o in orgs}

    subs = await db.subscriptions.find({'org_id': {'$in': org_ids}}, {'_id': 0}).to_list(len(org_ids))
    sub_map = {s['org_id']: s for s in subs}

    pipeline = [
        {'$match': {'user_id': {'$in': user_ids}}},
        {'$group': {'_id': '$user_id', 'count': {'$sum': 1}}},
    ]
    proj_counts = await db.project_memberships.aggregate(pipeline).to_list(len(user_ids))
    proj_count_map = {pc['_id']: pc['count'] for pc in proj_counts}
    db_enrich_ms = round((_t.perf_counter() - t0) * 1000, 1)

    for u in users:
        org_mem = org_mem_map.get(u['id'])
        u['org_id'] = org_mem.get('org_id') if org_mem else None
        if u['org_id']:
            u['org_name'] = org_name_map.get(u['org_id'], '')
            sub = sub_map.get(u['org_id'])
            u['billing_status'] = sub.get('status', 'unknown') if sub else 'none'
            u['trial_end_at'] = sub.get('trial_end_at') if sub else None
        else:
            u['org_name'] = ''
            u['billing_status'] = 'none'
            u['trial_end_at'] = None
        u['project_count'] = proj_count_map.get(u['id'], 0)

    total_ms = round((_t.perf_counter() - t_start) * 1000, 1)
    logger.info(
        f"[PERF] GET /admin/users total_ms={total_ms} "
        f"db_list_ms={db_list_ms} db_enrich_ms={db_enrich_ms} "
        f"user_count={len(users)} query_count=4"
    )
    return {'users': users, 'total': total}


@router.get("/admin/users/{user_id}")
async def admin_get_user(user_id: str, admin: dict = Depends(require_super_admin)):
    db = get_db()
    target = await db.users.find_one({'id': user_id}, {'_id': 0, 'password_hash': 0})
    if not target:
        raise HTTPException(status_code=404, detail='משתמש לא נמצא')

    org_mems = await db.organization_memberships.find({'user_id': user_id}, {'_id': 0}).to_list(50)
    for om in org_mems:
        org = await db.organizations.find_one({'id': om['org_id']}, {'_id': 0, 'name': 1})
        om['org_name'] = org.get('name', '') if org else ''
        sub = await get_subscription(om['org_id'])
        om['billing_status'] = sub.get('status', 'unknown') if sub else 'none'
        om['trial_end_at'] = sub.get('trial_end_at') if sub else None

    proj_mems = await db.project_memberships.find({'user_id': user_id}, {'_id': 0}).to_list(200)
    for pm in proj_mems:
        proj = await db.projects.find_one({'id': pm['project_id']}, {'_id': 0, 'name': 1, 'code': 1, 'org_id': 1})
        pm['project_name'] = proj.get('name', '') if proj else ''
        pm['project_code'] = proj.get('code', '') if proj else ''
        org_id = proj.get('org_id') if proj else None
        if org_id:
            org_doc = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'owner_user_id': 1})
            pm['is_org_owner'] = (org_doc.get('owner_user_id') == user_id) if org_doc else False
            org_mem_rec = await db.organization_memberships.find_one(
                {'org_id': org_id, 'user_id': user_id}, {'_id': 0, 'role': 1}
            )
            pm['org_role'] = org_mem_rec.get('role') if org_mem_rec else None
        else:
            pm['is_org_owner'] = False
            pm['org_role'] = None

    target['org_memberships'] = org_mems
    target['project_memberships'] = proj_mems
    return target


@router.put("/admin/users/{user_id}/phone")
async def admin_change_user_phone(user_id: str, request: Request, admin: dict = Depends(require_stepup)):
    db = get_db()
    body = await request.json()
    new_phone_raw = body.get('phone')
    note = body.get('note', '').strip()

    if not new_phone_raw:
        raise HTTPException(status_code=400, detail='חובה לציין מספר טלפון חדש')
    if not note:
        raise HTTPException(status_code=400, detail='חובה לציין סיבה (note)')

    try:
        norm = normalize_israeli_phone(new_phone_raw)
        new_phone = norm['phone_e164']
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    target = await db.users.find_one({'id': user_id}, {'_id': 0, 'id': 1, 'phone_e164': 1, 'name': 1})
    if not target:
        raise HTTPException(status_code=404, detail='משתמש לא נמצא')

    conflict = await db.users.find_one({'phone_e164': new_phone, 'id': {'$ne': user_id}})
    if conflict:
        raise HTTPException(status_code=409, detail='המספר כבר קיים אצל משתמש אחר. לא ניתן לדרוס.')

    old_phone = target.get('phone_e164', '')
    await db.users.update_one({'id': user_id}, {'$set': {'phone_e164': new_phone}})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'user',
        'entity_id': user_id,
        'action': 'admin_phone_change',
        'actor_id': admin['id'],
        'note': note,
        'details': {'old_phone': old_phone, 'new_phone': new_phone, 'target_name': target.get('name', '')},
        'created_at': datetime.now(timezone.utc).isoformat(),
    })

    return {'success': True, 'phone_e164': new_phone}


ALLOWED_PREFERRED_LANGUAGES = {'he', 'en', 'ar', 'zh'}

@router.put("/admin/users/{user_id}/preferred-language")
async def admin_update_preferred_language(user_id: str, request: Request, admin: dict = Depends(require_super_admin)):
    db = get_db()
    body = await request.json()
    lang = body.get('preferred_language', '').strip().lower()

    if lang not in ALLOWED_PREFERRED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f'שפה לא חוקית. ערכים מותרים: {", ".join(sorted(ALLOWED_PREFERRED_LANGUAGES))}')

    target = await db.users.find_one({'id': user_id}, {'_id': 0, 'id': 1, 'name': 1, 'preferred_language': 1})
    if not target:
        raise HTTPException(status_code=404, detail='משתמש לא נמצא')

    old_value = target.get('preferred_language', 'he')
    await db.users.update_one({'id': user_id}, {'$set': {'preferred_language': lang}})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'user',
        'entity_id': user_id,
        'action': 'admin_preferred_language_change',
        'actor_id': admin['id'],
        'details': {'old_value': old_value, 'new_value': lang, 'target_name': target.get('name', '')},
        'created_at': datetime.now(timezone.utc).isoformat(),
    })

    return {'success': True, 'preferred_language': lang}


@router.post("/admin/users/{user_id}/reset-password")
async def admin_reset_user_password(user_id: str, request: Request, admin: dict = Depends(require_stepup)):
    from contractor_ops.identity_router import _validate_new_password
    db = get_db()
    body = await request.json()
    new_password = body.get('new_password', '').strip()
    note = body.get('note', '').strip()

    if not new_password:
        raise HTTPException(status_code=400, detail='חובה לציין סיסמה חדשה')
    if not note:
        raise HTTPException(status_code=400, detail='חובה לציין סיבה (note)')

    _validate_new_password(new_password)

    target = await db.users.find_one({'id': user_id}, {'_id': 0, 'id': 1, 'name': 1, 'session_version': 1})
    if not target:
        raise HTTPException(status_code=404, detail='משתמש לא נמצא')

    password_hash = await _hash_password(new_password)
    old_sv = target.get('session_version', 0)
    new_sv = old_sv + 1
    now = datetime.now(timezone.utc).isoformat()

    await db.users.update_one(
        {'id': user_id},
        {
            '$set': {'password_hash': password_hash, 'session_version': new_sv, 'updated_at': now},
            '$unset': {'password': ''},
        }
    )

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'user',
        'entity_id': user_id,
        'action': 'admin_password_reset',
        'actor_id': admin['id'],
        'payload': {
            'note': note,
            'old_session_version': old_sv,
            'new_session_version': new_sv,
            'target_name': target.get('name', ''),
        },
        'created_at': now,
    })

    logger.info(f"[ADMIN] password_reset user={user_id} by={admin['id']} sv={old_sv}->{new_sv}")

    return {'success': True, 'session_version': new_sv}


VALID_TARGET_ROLES = {'viewer', 'management_team', 'project_manager', 'contractor'}
VALID_ROLE_TRANSITIONS = {
    ('viewer', 'management_team'),
    ('viewer', 'project_manager'),
    ('viewer', 'contractor'),
    ('management_team', 'viewer'),
    ('management_team', 'project_manager'),
    ('management_team', 'contractor'),
    ('project_manager', 'viewer'),
    ('project_manager', 'management_team'),
    ('project_manager', 'contractor'),
    ('contractor', 'viewer'),
    ('contractor', 'management_team'),
    ('contractor', 'project_manager'),
}


@router.put("/admin/users/{user_id}/projects/{project_id}/role")
async def admin_change_user_role(user_id: str, project_id: str, request: Request,
                                  admin: dict = Depends(require_stepup)):
    db = get_db()
    body = await request.json()
    new_role = body.get('new_role', '').strip()
    note = body.get('note', '').strip()

    if not new_role:
        raise HTTPException(status_code=400, detail='חובה לציין תפקיד חדש')
    if not note:
        raise HTTPException(status_code=400, detail='חובה לציין סיבה (note)')

    valid_roles = {'project_manager', 'management_team', 'contractor', 'viewer'}
    if new_role not in valid_roles:
        raise HTTPException(status_code=400, detail=f'תפקיד לא תקין: {new_role}')

    membership = await db.project_memberships.find_one({
        'user_id': user_id, 'project_id': project_id
    })
    if not membership:
        raise HTTPException(status_code=404, detail='חברות בפרויקט לא נמצאה')

    old_role = membership['role']
    if old_role == new_role:
        raise HTTPException(status_code=400, detail='התפקיד החדש זהה לנוכחי')

    transition = (old_role, new_role)
    if transition not in VALID_ROLE_TRANSITIONS:
        raise HTTPException(status_code=409,
                            detail=f'מעבר מ-{old_role} ל-{new_role} אינו מותר')

    if new_role == 'contractor':
        target_user = await db.users.find_one({'id': user_id}, {'_id': 0, 'company_id': 1})
        trade_mem = membership.get('contractor_trade_key')
        if not (target_user and target_user.get('company_id')) and not trade_mem:
            raise HTTPException(status_code=400,
                                detail='לא ניתן להפוך לקבלן ללא חברה (company_id) או מקצוע (trade_key)')

    if old_role == 'project_manager':
        pm_count = await db.project_memberships.count_documents({
            'project_id': project_id, 'role': 'project_manager'
        })
        if pm_count <= 1:
            raise HTTPException(status_code=409,
                                detail='חייב להיות לפחות מנהל פרויקט אחד בפרויקט')

    from contractor_ops.member_management import check_role_conflict
    await check_role_conflict(db, user_id, project_id, new_role,
                              actor_id=admin['id'], attempted_action='admin_change_role', request=request)

    await db.project_memberships.update_one(
        {'user_id': user_id, 'project_id': project_id},
        {'$set': {'role': new_role}}
    )

    target = await db.users.find_one({'id': user_id}, {'_id': 0, 'name': 1})
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'name': 1})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'admin_change_role',
        'actor_id': admin['id'],
        'actor_name': admin.get('name', ''),
        'target_user_id': user_id,
        'target_user_name': target.get('name', '') if target else '',
        'project_id': project_id,
        'project_name': project.get('name', '') if project else '',
        'payload': {
            'old_role': old_role,
            'new_role': new_role,
            'note': note,
        },
        'created_at': datetime.now(timezone.utc).isoformat(),
    })

    return {
        'success': True,
        'old_role': old_role,
        'new_role': new_role,
        'user_id': user_id,
        'project_id': project_id,
    }
