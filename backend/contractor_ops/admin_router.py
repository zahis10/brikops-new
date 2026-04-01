from fastapi import APIRouter, HTTPException, Depends, Query, Request
from typing import Optional
from datetime import datetime, timezone
import uuid
import re
import copy

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


async def _check_not_pending_deletion(db, user_id: str):
    target = await db.users.find_one({'id': user_id}, {'_id': 0, 'user_status': 1})
    if target and target.get('user_status') == 'pending_deletion':
        raise HTTPException(status_code=409, detail='משתמש בתהליך מחיקה, לא ניתן לערוך')


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
    target_user = await db.users.find_one({'id': user_id}, {'_id': 0, 'id': 1, 'name': 1, 'session_version': 1, 'user_status': 1})
    if not target_user:
        raise HTTPException(status_code=404, detail='User not found')
    if target_user.get('user_status') == 'pending_deletion':
        raise HTTPException(status_code=409, detail='לא ניתן לבצע פעולה על משתמש בתהליך מחיקה')
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

    org_ids = [o['id'] for o in orgs]
    subs = await db.subscriptions.find(
        {'org_id': {'$in': org_ids}}, {'_id': 0}
    ).to_list(5000)
    sub_map = {s['org_id']: s for s in subs}

    owner_ids = [o.get('owner_user_id') for o in orgs if o.get('owner_user_id')]
    owner_map = {}
    if owner_ids:
        owners = await db.users.find(
            {'id': {'$in': list(set(owner_ids))}},
            {'_id': 0, 'id': 1, 'name': 1, 'email': 1, 'phone_e164': 1}
        ).to_list(5000)
        owner_map = {u['id']: u for u in owners}

    result = []
    for org in orgs:
        sub = sub_map.get(org['id'])
        access, reason = _resolve_access(sub)
        result.append({
            **org,
            'subscription': sub,
            'owner': owner_map.get(org.get('owner_user_id')),
            'effective_access': access.value,
            'read_only_reason': reason,
        })
    return result


@router.get("/admin/billing/invoices-summary")
async def admin_invoices_summary(user: dict = Depends(require_super_admin)):
    db = get_db()
    pipeline = [
        {'$sort': {'org_id': 1, 'period_ym': -1}},
        {'$group': {
            '_id': '$org_id',
            'period_ym': {'$first': '$period_ym'},
            'status': {'$first': '$status'},
            'total_amount': {'$first': '$total_amount'},
            'paid_at': {'$first': '$paid_at'},
        }},
    ]
    results = await db.invoices.aggregate(pipeline).to_list(5000)
    return {r['_id']: {
        'org_id': r['_id'],
        'period_ym': r.get('period_ym'),
        'status': r.get('status'),
        'total_amount': r.get('total_amount'),
        'paid_at': r.get('paid_at'),
    } for r in results}


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


@router.put("/admin/orgs/{org_id}")
async def admin_update_org(org_id: str, request: Request, user: dict = Depends(require_super_admin)):
    db = get_db()
    body = await request.json()
    name = body.get('name', '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='שם ארגון לא יכול להיות ריק')
    org = await db.organizations.find_one({'id': org_id})
    if not org:
        raise HTTPException(status_code=404, detail='ארגון לא נמצא')
    await db.organizations.update_one({'id': org_id}, {'$set': {'name': name}})
    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'update_org',
        'entity_type': 'organization',
        'actor_id': user['id'],
        'payload': {'org_id': org_id, 'name': name, 'old_name': org.get('name')},
        'created_at': datetime.now(timezone.utc).isoformat(),
    })
    return {'success': True, 'name': name}


@router.put("/admin/orgs/{org_id}/owner")
async def admin_change_org_owner(org_id: str, request: Request, user: dict = Depends(require_stepup)):
    db = get_db()
    body = await request.json()
    new_owner_id = body.get('user_id', '').strip()
    if not new_owner_id:
        raise HTTPException(status_code=400, detail='חובה לציין user_id')
    org = await db.organizations.find_one({'id': org_id})
    if not org:
        raise HTTPException(status_code=404, detail='ארגון לא נמצא')
    await _check_not_pending_deletion(db, new_owner_id)
    membership = await db.org_memberships.find_one({'org_id': org_id, 'user_id': new_owner_id})
    if not membership:
        raise HTTPException(status_code=400, detail='המשתמש אינו חבר בארגון')
    old_owner_id = org.get('owner_user_id')
    await db.organizations.update_one({'id': org_id}, {'$set': {'owner_user_id': new_owner_id}})
    if old_owner_id and old_owner_id != new_owner_id:
        await db.org_memberships.update_one(
            {'org_id': org_id, 'user_id': old_owner_id},
            {'$set': {'role': 'member', 'is_owner': False}}
        )
    await db.org_memberships.update_one(
        {'org_id': org_id, 'user_id': new_owner_id},
        {'$set': {'role': 'owner', 'is_owner': True}}
    )
    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'change_org_owner',
        'entity_type': 'organization',
        'actor_id': user['id'],
        'payload': {'org_id': org_id, 'old_owner_id': old_owner_id, 'new_owner_id': new_owner_id},
        'created_at': datetime.now(timezone.utc).isoformat(),
    })
    return {'success': True}


@router.get("/admin/billing/audit")
async def admin_billing_audit(user: dict = Depends(require_super_admin)):
    db = get_db()
    events = await db.audit_events.find(
        {'entity_type': {'$in': ['subscription', 'billing_plan', 'project_billing', 'project']}},
        {'_id': 0}
    ).sort('created_at', -1).to_list(200)

    actor_ids = list(set(ev.get('actor_id') for ev in events if ev.get('actor_id')))
    actor_map = {}
    if actor_ids:
        actors = await db.users.find(
            {'id': {'$in': actor_ids}},
            {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(5000)
        actor_map = {u['id']: u.get('name', '') for u in actors}

    for ev in events:
        ev['actor_name'] = actor_map.get(ev.get('actor_id'), '')
    return events


@router.get("/admin/billing/plans")
async def admin_list_plans(user: dict = Depends(require_super_admin)):
    from contractor_ops.billing import BILLING_V1_ENABLED
    from contractor_ops.billing_plans import list_plans
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    plans = await list_plans()
    return plans


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

    target = await db.users.find_one({'id': user_id}, {'_id': 0, 'id': 1, 'phone_e164': 1, 'name': 1, 'user_status': 1})
    if not target:
        raise HTTPException(status_code=404, detail='משתמש לא נמצא')
    if target.get('user_status') == 'pending_deletion':
        raise HTTPException(status_code=409, detail='משתמש בתהליך מחיקה, לא ניתן לערוך')

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

    target = await db.users.find_one({'id': user_id}, {'_id': 0, 'id': 1, 'name': 1, 'preferred_language': 1, 'user_status': 1})
    if not target:
        raise HTTPException(status_code=404, detail='משתמש לא נמצא')
    if target.get('user_status') == 'pending_deletion':
        raise HTTPException(status_code=409, detail='לא ניתן לבצע פעולה על משתמש בתהליך מחיקה')

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

    target = await db.users.find_one({'id': user_id}, {'_id': 0, 'id': 1, 'name': 1, 'session_version': 1, 'user_status': 1})
    if not target:
        raise HTTPException(status_code=404, detail='משתמש לא נמצא')
    if target.get('user_status') == 'pending_deletion':
        raise HTTPException(status_code=409, detail='משתמש בתהליך מחיקה, לא ניתן לערוך')

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

    await _check_not_pending_deletion(db, user_id)

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


@router.get("/admin/qc/templates")
async def admin_list_qc_templates(
    request: Request,
    user: dict = Depends(require_super_admin),
    search: str = Query(default="", description="Search by name"),
    archived: bool = Query(default=False, description="Include archived families"),
    sort: str = Query(default="name", description="Sort: name, last_modified, created"),
    type: str = Query(default=None, description="Filter by type: qc or handover"),
):
    db = get_db()
    query_filter = {}
    if type and type in ("qc", "handover"):
        query_filter["type"] = type
    if search.strip():
        query_filter["name"] = {"$regex": search.strip(), "$options": "i"}

    all_docs = await db.qc_templates.find(query_filter, {"_id": 0}).sort([("family_id", 1), ("version", -1)]).to_list(500)
    families = {}
    for doc in all_docs:
        fid = doc["family_id"]
        if fid not in families:
            families[fid] = {
                "family_id": fid,
                "name": doc["name"],
                "latest_version": doc["version"],
                "latest_id": doc["id"],
                "is_default": doc.get("is_default", False),
                "is_active": doc.get("is_active", False),
                "archived": doc.get("archived", False),
                "stage_count": len(doc.get("stages", doc.get("sections", []))),
                "type": doc.get("type", "qc"),
                "created_at": doc.get("created_at"),
                "last_modified": doc.get("created_at"),
                "versions": [],
            }
        else:
            v_created = doc.get("created_at")
            if v_created and (not families[fid]["created_at"] or v_created < families[fid]["created_at"]):
                families[fid]["created_at"] = v_created
        families[fid]["versions"].append({
            "id": doc["id"],
            "version": doc["version"],
            "is_active": doc.get("is_active", False),
            "created_at": doc.get("created_at"),
        })

    result = list(families.values())

    if not archived:
        result = [f for f in result if not f.get("archived")]

    if sort == "last_modified":
        result.sort(key=lambda f: f.get("last_modified") or "", reverse=True)
    elif sort == "created":
        result.sort(key=lambda f: f.get("created_at") or "", reverse=True)
    else:
        result.sort(key=lambda f: f.get("name", "").lower())

    return result


@router.put("/admin/qc/templates/{family_id}/archive")
async def admin_archive_qc_template_family(family_id: str, request: Request, user: dict = Depends(require_super_admin)):
    db = get_db()
    docs = await db.qc_templates.find({"family_id": family_id}, {"_id": 0, "id": 1}).to_list(100)
    if not docs:
        raise HTTPException(status_code=404, detail="Template family not found")

    body = await request.json()
    archive = body.get("archive", True)

    if archive:
        version_ids = [d["id"] for d in docs]
        active_projects = await db.projects.count_documents({
            "status": {"$in": ["active", "draft"]},
            "$or": [
                {"qc_template_family_id": family_id},
                {"qc_template_version_id": {"$in": version_ids}},
                {"qc_template_id": {"$in": version_ids}},
            ]
        })
        if active_projects > 0:
            raise HTTPException(status_code=400, detail=f"לא ניתן לארכב — התבנית משויכת ל-{active_projects} פרויקטים פעילים")

    await db.qc_templates.update_many(
        {"family_id": family_id},
        {"$set": {"archived": archive}}
    )
    action = "archived" if archive else "restored"
    logger.info(f"[QC-TPL] Family {family_id} {action} by user={user['id']}")
    return {"success": True, "family_id": family_id, "archived": archive}


@router.get("/admin/qc/templates/{template_id}")
async def admin_get_qc_template(template_id: str, user: dict = Depends(require_super_admin)):
    db = get_db()
    doc = await db.qc_templates.find_one({"id": template_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    return doc


@router.post("/admin/qc/templates")
async def admin_create_qc_template(request: Request, user: dict = Depends(require_super_admin)):
    db = get_db()
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    tpl_type = body.get("type", "qc")
    if tpl_type not in ("qc", "handover"):
        tpl_type = "qc"

    if tpl_type == "handover":
        sections = body.get("sections", [])
        if not sections:
            raise HTTPException(status_code=400, detail="At least one section is required")
    else:
        stages = body.get("stages", [])
        if not stages:
            raise HTTPException(status_code=400, detail="At least one stage is required")

    family_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    is_default = bool(body.get("is_default", False))

    doc = {
        "id": doc_id,
        "family_id": family_id,
        "name": name,
        "version": 1,
        "is_default": is_default,
        "is_active": True,
        "type": tpl_type,
        "created_at": now,
        "created_by": user["id"],
    }
    if tpl_type == "handover":
        doc["sections"] = sections
    else:
        doc["stages"] = stages

    if is_default:
        await db.qc_templates.update_many(
            {"type": tpl_type, "is_default": True, "family_id": {"$ne": family_id}},
            {"$set": {"is_default": False}}
        )
        logger.info(f"[QC-TPL] Cleared other defaults for type={tpl_type} — new default family={family_id}")

    await db.qc_templates.insert_one(doc)
    doc.pop("_id", None)
    logger.info(f"[QC-TPL] Created template family={family_id} id={doc_id} type={tpl_type} by user={user['id']}")
    return doc


@router.put("/admin/qc/templates/{template_id}")
async def admin_update_qc_template(template_id: str, request: Request, user: dict = Depends(require_super_admin)):
    db = get_db()
    old = await db.qc_templates.find_one({"id": template_id}, {"_id": 0})
    if not old:
        raise HTTPException(status_code=404, detail="Template not found")

    body = await request.json()
    name = body.get("name", old["name"]).strip()
    tpl_type = old.get("type", "qc")

    if tpl_type == "handover":
        sections = body.get("sections", old.get("sections", []))
        if not sections:
            raise HTTPException(status_code=400, detail="At least one section is required")
    else:
        stages = body.get("stages", old.get("stages", []))
        if not stages:
            raise HTTPException(status_code=400, detail="At least one stage is required")

    default_delivered_items = None
    default_property_fields = None
    signature_labels = None

    if tpl_type == "handover":
        import re as _re

        if "default_delivered_items" in body:
            ddi = body["default_delivered_items"]
            if not isinstance(ddi, list):
                raise HTTPException(status_code=400, detail="default_delivered_items must be a list")
            for i, item in enumerate(ddi):
                if not isinstance(item, dict) or not item.get("name", "").strip():
                    raise HTTPException(status_code=400, detail=f"default_delivered_items[{i}]: name is required")
            default_delivered_items = [
                {"name": it["name"].strip(), "quantity": it.get("quantity"), "notes": it.get("notes", "")}
                for it in ddi
            ]

        if "default_property_fields" in body:
            dpf = body["default_property_fields"]
            if not isinstance(dpf, list):
                raise HTTPException(status_code=400, detail="default_property_fields must be a list")
            seen_keys = set()
            for i, field in enumerate(dpf):
                if not isinstance(field, dict):
                    raise HTTPException(status_code=400, detail=f"default_property_fields[{i}]: must be an object")
                key = (field.get("key") or "").strip()
                label = (field.get("label") or "").strip()
                if not key:
                    raise HTTPException(status_code=400, detail=f"default_property_fields[{i}]: key is required")
                if not _re.match(r"^[a-z][a-z0-9_]*$", key):
                    raise HTTPException(status_code=400, detail=f"default_property_fields[{i}]: key must be lowercase alphanumeric+underscore (got '{key}')")
                if key in seen_keys:
                    raise HTTPException(status_code=400, detail=f"default_property_fields[{i}]: duplicate key '{key}'")
                seen_keys.add(key)
                if not label:
                    raise HTTPException(status_code=400, detail=f"default_property_fields[{i}]: label is required")
            default_property_fields = [{"key": f["key"].strip(), "label": f["label"].strip()} for f in dpf]

        if "signature_labels" in body:
            sl = body["signature_labels"]
            if not isinstance(sl, dict):
                raise HTTPException(status_code=400, detail="signature_labels must be an object")
            allowed_keys = {"manager", "tenant", "tenant_2", "contractor_rep"}
            if not set(sl.keys()).issubset(allowed_keys):
                raise HTTPException(status_code=400, detail=f"signature_labels keys must be from: {', '.join(sorted(allowed_keys))}")
            required_min = {"manager", "tenant", "contractor_rep"}
            if not required_min.issubset(set(sl.keys())):
                raise HTTPException(status_code=400, detail=f"signature_labels must include at least: {', '.join(sorted(required_min))}")
            for k in sl:
                if not isinstance(sl[k], str):
                    raise HTTPException(status_code=400, detail=f"signature_labels[{k}] must be a string")
            signature_labels = {k: sl.get(k, "") for k in allowed_keys}

    family_id = old["family_id"]
    max_doc = await db.qc_templates.find_one(
        {"family_id": family_id},
        {"_id": 0, "version": 1},
        sort=[("version", -1)]
    )
    new_version = (max_doc["version"] if max_doc else old["version"]) + 1
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    is_default = old.get("is_default", False)
    if body.get("is_default") is not None:
        is_default = bool(body["is_default"])

    new_doc = {
        "id": new_id,
        "family_id": family_id,
        "name": name,
        "version": new_version,
        "is_default": is_default,
        "is_active": True,
        "type": tpl_type,
        "created_at": now,
        "created_by": user["id"],
    }
    legal_sections = None
    if tpl_type == "handover":
        raw_legal = body.get("legal_sections")
        if raw_legal is not None:
            if not isinstance(raw_legal, list):
                raise HTTPException(status_code=400, detail="legal_sections חייב להיות מערך")
            from contractor_ops.handover_router import _validate_legal_sections
            legal_sections = _validate_legal_sections(raw_legal)

    if tpl_type == "handover":
        new_doc["sections"] = sections
        if default_delivered_items is not None:
            new_doc["default_delivered_items"] = default_delivered_items
        elif "default_delivered_items" in old:
            new_doc["default_delivered_items"] = old["default_delivered_items"]
        if default_property_fields is not None:
            new_doc["default_property_fields"] = default_property_fields
        elif "default_property_fields" in old:
            new_doc["default_property_fields"] = old["default_property_fields"]
        if signature_labels is not None:
            new_doc["signature_labels"] = signature_labels
        elif "signature_labels" in old:
            new_doc["signature_labels"] = old["signature_labels"]
        if legal_sections is not None:
            new_doc["legal_sections"] = legal_sections
        elif "legal_sections" in old:
            new_doc["legal_sections"] = old["legal_sections"]
    else:
        new_doc["stages"] = stages

    if is_default:
        await db.qc_templates.update_many(
            {"type": tpl_type, "is_default": True, "family_id": {"$ne": family_id}},
            {"$set": {"is_default": False}}
        )

    await db.qc_templates.insert_one(new_doc)

    await db.qc_templates.update_many(
        {"family_id": family_id, "id": {"$ne": new_id}, "is_active": True},
        {"$set": {"is_active": False}}
    )

    if tpl_type == "handover":
        repin = await db.projects.update_many(
            {"handover_template_family_id": family_id},
            {"$set": {"handover_template_version_id": new_id}}
        )
        if repin.modified_count > 0:
            logger.info(f"[QC-TPL] Auto-propagated {repin.modified_count} projects handover template family={family_id} -> {new_id}")
    else:
        repin = await db.projects.update_many(
            {"qc_template_family_id": family_id},
            {"$set": {"qc_template_version_id": new_id}}
        )
        if repin.modified_count > 0:
            logger.info(f"[QC-TPL] Auto-propagated {repin.modified_count} projects QC template family={family_id} -> {new_id}")

    new_doc.pop("_id", None)
    logger.info(f"[QC-TPL] Updated template family={family_id} v{old['version']}->v{new_version} new_id={new_id} by user={user['id']}")
    return new_doc


@router.post("/admin/qc/templates/{template_id}/clone")
async def admin_clone_qc_template(template_id: str, request: Request, user: dict = Depends(require_super_admin)):
    db = get_db()
    source = await db.qc_templates.find_one({"id": template_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Template not found")

    body = await request.json()
    name = body.get("name", f"{source['name']} — עותק").strip()

    new_family_id = str(uuid.uuid4())
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    tpl_type = source.get("type", "qc")
    doc = {
        "id": new_id,
        "family_id": new_family_id,
        "name": name,
        "version": 1,
        "is_default": False,
        "is_active": True,
        "type": tpl_type,
        "created_at": now,
        "created_by": user["id"],
    }
    if tpl_type == "handover":
        doc["sections"] = copy.deepcopy(source.get("sections", []))
        for extra_key in ("default_delivered_items", "default_property_fields", "signature_labels", "legal_sections"):
            if extra_key in source:
                doc[extra_key] = copy.deepcopy(source[extra_key])
    else:
        doc["stages"] = copy.deepcopy(source.get("stages", []))
    await db.qc_templates.insert_one(doc)
    doc.pop("_id", None)
    logger.info(f"[QC-TPL] Cloned template from={template_id} to family={new_family_id} id={new_id} by user={user['id']}")
    return doc


