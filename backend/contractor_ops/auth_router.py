import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from contractor_ops.router import (
    get_db, get_current_user, get_current_user_allow_pending_deletion,
    _hash_password, _verify_password, _create_token,
    _get_otp_service, _audit, _now,
    ensure_user_org, MANAGEMENT_ROLES, logger,
)
from config import is_super_admin_phone, ENABLE_COMPLETE_ACCOUNT_GATE, SA_PHONES_SOURCE, SUPER_ADMIN_PHONES, _mask_phone, ALLOWED_LANGUAGES
from contractor_ops.phone_utils import normalize_israeli_phone
from contractor_ops.schemas import (
    UserCreate, UserLogin, UserResponse, Role,
    OrgSummary, ProjectMembershipSummary,
)

router = APIRouter(prefix="/api")


@router.post("/auth/logout-all")
async def logout_all_sessions(request: Request, user: dict = Depends(get_current_user_allow_pending_deletion)):
    db = get_db()
    user_id = user['id']
    old_sv = user.get('session_version', 0)
    new_sv = old_sv + 1
    await db.users.update_one({'id': user_id}, {'$set': {'session_version': new_sv}})
    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'action': 'logout_all_sessions',
        'actor_id': user_id,
        'target_user_id': user_id,
        'old_session_version': old_sv,
        'new_session_version': new_sv,
        'ip': request.headers.get('x-forwarded-for', request.client.host if request.client else ''),
        'user_agent': request.headers.get('user-agent', '')[:200],
        'created_at': datetime.now(timezone.utc).isoformat(),
    })
    return {'success': True, 'message': 'כל ההתחברויות בוטלו. יש להתחבר מחדש.'}


@router.post("/auth/change-phone/request")
async def request_phone_change(request: Request, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    db = get_db()
    body = await request.json()
    new_phone_raw = body.get('phone')
    if not new_phone_raw:
        raise HTTPException(status_code=400, detail='חובה לציין מספר טלפון חדש')

    try:
        norm = normalize_israeli_phone(new_phone_raw)
        new_phone = norm['phone_e164']
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    conflict = await db.users.find_one({'phone_e164': new_phone, 'id': {'$ne': user['id']}})
    if conflict:
        raise HTTPException(status_code=409, detail='המספר כבר רשום אצל משתמש אחר')

    otp_svc = _get_otp_service()
    result = await otp_svc.request_otp(new_phone)
    if not result.get('success'):
        error_type = result.get('error', '')
        if error_type in ('rate_limited', 'too_many_attempts'):
            raise HTTPException(status_code=429, detail=result['message'])
        else:
            raise HTTPException(status_code=422, detail=result['message'])

    rid = result.get('rid', '')
    plain_code = result.pop('_code', None)
    if plain_code and not result.get('idempotent'):
        background_tasks.add_task(
            otp_svc.deliver_otp_background, new_phone, plain_code, rid
        )

    result.pop('_code', None)
    return result


@router.post("/auth/change-phone/verify")
async def verify_phone_change(request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    body = await request.json()
    new_phone_raw = body.get('phone')
    code = body.get('code')

    if not new_phone_raw or not code:
        raise HTTPException(status_code=400, detail='חובה לציין מספר טלפון וקוד אימות')

    try:
        norm = normalize_israeli_phone(new_phone_raw)
        new_phone = norm['phone_e164']
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    conflict = await db.users.find_one({'phone_e164': new_phone, 'id': {'$ne': user['id']}})
    if conflict:
        raise HTTPException(status_code=409, detail='המספר כבר רשום אצל משתמש אחר')

    verify_result = await _get_otp_service().verify_otp(new_phone, code)
    if not verify_result.get('success'):
        raise HTTPException(status_code=400, detail=verify_result.get('message', 'קוד שגוי'))

    old_phone = user.get('phone_e164', '')
    await db.users.update_one({'id': user['id']}, {'$set': {'phone_e164': new_phone}})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'user',
        'entity_id': user['id'],
        'action': 'self_phone_change',
        'actor_id': user['id'],
        'note': 'שינוי מספר עצמי לאחר אימות OTP',
        'details': {'old_phone': old_phone, 'new_phone': new_phone},
        'created_at': datetime.now(timezone.utc).isoformat(),
    })

    return {'success': True, 'phone_e164': new_phone, 'force_logout': True}


@router.put("/auth/me/preferred-language")
async def update_my_preferred_language(request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    body = await request.json()
    lang = body.get('preferred_language', '').strip().lower()
    if lang not in ALLOWED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f'שפה לא נתמכת. ערכים אפשריים: {", ".join(ALLOWED_LANGUAGES)}')
    old_lang = user.get('preferred_language', 'he')
    await db.users.update_one({'id': user['id']}, {'$set': {'preferred_language': lang}})
    await _audit('user', user['id'], 'self_preferred_language_change', user['id'], {
        'old_language': old_lang,
        'new_language': lang,
    })
    return {'success': True, 'preferred_language': lang}


@router.put("/auth/me/whatsapp-notifications")
async def update_my_whatsapp_notifications(request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    body = await request.json()
    enabled = body.get('enabled')
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=400, detail='שדה enabled חייב להיות true או false')
    await db.users.update_one({'id': user['id']}, {'$set': {'whatsapp_notifications_enabled': enabled}})
    await _audit('user', user['id'], 'self_whatsapp_notifications_change', user['id'], {
        'old_value': user.get('whatsapp_notifications_enabled', True),
        'new_value': enabled,
    })
    return {'success': True, 'whatsapp_notifications_enabled': enabled}


@router.post("/auth/register", response_model=UserResponse)
async def register(user: UserCreate):
    db = get_db()
    if user.email:
        existing = await db.users.find_one({'email': user.email})
        if existing:
            raise HTTPException(status_code=400, detail='Email already registered')
    if user.phone_e164:
        try:
            phone_norm = normalize_israeli_phone(user.phone_e164)
            user.phone_e164 = phone_norm['phone_e164']
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        existing_phone = await db.users.find_one({'phone_e164': user.phone_e164})
        if existing_phone:
            raise HTTPException(status_code=400, detail='Phone already registered')
    user_id = str(uuid.uuid4())
    resolved_role = user.role.value if isinstance(user.role, Role) else user.role
    user_doc = {
        'id': user_id,
        'password_hash': (await _hash_password(user.password)) if user.password else None,
        'name': user.name,
        'phone': user.phone,
        'role': resolved_role,
        'company_id': user.company_id,
        'specialties': user.specialties,
        'user_status': 'active',
        'created_at': _now(),
    }
    if user.email:
        user_doc['email'] = user.email
    if user.phone_e164:
        user_doc['phone_e164'] = user.phone_e164
    if ENABLE_COMPLETE_ACCOUNT_GATE != 'off' and resolved_role in MANAGEMENT_ROLES:
        user_doc['account_complete'] = False
    await db.users.insert_one(user_doc)

    if user.phone_e164:
        pending_invites = await db.invites.find({
            'target_phone': user.phone_e164,
            'status': 'pending',
        }).to_list(100)

        ts = _now()
        for invite in pending_invites:
            if invite.get('expires_at', '') < ts:
                await db.invites.update_one(
                    {'id': invite['id']},
                    {'$set': {'status': 'expired', 'updated_at': ts}}
                )
                await _audit('invite', invite['id'], 'expired', 'system', {
                    'project_id': invite['project_id'],
                    'phone': invite.get('target_phone'),
                    'role': invite.get('role'),
                    'reason': 'passive_expiry_on_login',
                    'expires_at': invite.get('expires_at'),
                })
                continue

            from contractor_ops.member_management import has_role_conflict, _audit_role_conflict, _resolve_org_for_project
            if await has_role_conflict(db, user_id, invite['project_id'], invite['role']):
                resolve_org_id, _ = await _resolve_org_for_project(db, invite['project_id'])
                await _audit_role_conflict(
                    db, actor_id='system', target_user_id=user_id,
                    org_id=resolve_org_id or '', attempted_role=invite['role'],
                    current_roles=['owner_or_management'], reason='contractor_conflicts_with_org_management_role',
                )
                logger.warning(f"[ROLE-CONFLICT] register_auto_link_skip user={user_id[:8]} invite={invite['id'][:8]} project={invite['project_id'][:8]}")
                continue

            reg_membership_doc = {
                'id': str(uuid.uuid4()),
                'project_id': invite['project_id'],
                'user_id': user_id,
                'role': invite['role'],
                'sub_role': invite.get('sub_role'),
                'created_at': ts,
            }
            if invite['role'] == 'contractor' and invite.get('trade_key'):
                reg_membership_doc['contractor_trade_key'] = invite['trade_key']
            if invite['role'] == 'contractor' and invite.get('company_id'):
                reg_membership_doc['company_id'] = invite['company_id']
            await db.project_memberships.update_one(
                {'project_id': invite['project_id'], 'user_id': user_id},
                {'$set': reg_membership_doc},
                upsert=True
            )
            if invite['role'] == 'project_manager':
                await db.users.update_one(
                    {'id': user_id},
                    {'$set': {'role': 'project_manager', 'updated_at': ts}}
                )
            await db.invites.update_one(
                {'id': invite['id']},
                {'$set': {
                    'status': 'accepted',
                    'accepted_by_user_id': user_id,
                    'accepted_at': ts,
                    'updated_at': ts,
                }}
            )
            await _audit('invite', invite['id'], 'accepted', user_id, {
                'project_id': invite['project_id'],
                'role': invite['role'],
                'auto_linked': True,
                'trade_key': invite.get('trade_key'),
                'company_id': invite.get('company_id'),
            })

    await _audit('user', user_id, 'register', user_id, {'email': user.email, 'role': user_doc['role']})
    return UserResponse(id=user_id, email=user.email, name=user.name, phone=user.phone,
                        role=user_doc['role'], company_id=user.company_id,
                        specialties=user.specialties, phone_e164=user.phone_e164,
                        created_at=user_doc['created_at'])


_DEMO_EMAIL_DOMAINS = ('@contractor-ops.com', '@brikops.dev')

@router.post("/auth/login")
async def login(credentials: UserLogin):
    from config import ENABLE_QUICK_LOGIN
    if not ENABLE_QUICK_LOGIN:
        if any(credentials.email.endswith(d) for d in _DEMO_EMAIL_DOMAINS):
            raise HTTPException(status_code=403, detail='כניסה מהירה לא זמינה בסביבת ייצור')
    db = get_db()
    user = await db.users.find_one({'email': credentials.email}, {'_id': 0})
    if not user:
        raise HTTPException(status_code=401, detail='Invalid credentials')

    pw_hash = user.get('password_hash')
    legacy_pw = user.get('password', '')
    if not pw_hash and legacy_pw:
        if legacy_pw.startswith(('$2a$', '$2b$', '$2y$')):
            pw_hash = legacy_pw
        else:
            await db.audit_events.insert_one({
                'id': str(__import__('uuid').uuid4()),
                'entity_type': 'user', 'entity_id': user['id'],
                'action': 'auth_password_migration_blocked_plaintext',
                'actor_id': user['id'],
                'payload': {'source': 'login_email'},
                'created_at': _now(),
            })
            raise HTTPException(status_code=401, detail='Invalid credentials')

    if not pw_hash or not await _verify_password(credentials.password, pw_hash):
        raise HTTPException(status_code=401, detail='Invalid credentials')

    if user.get('password_hash') and legacy_pw:
        await db.users.update_one({'id': user['id']}, {'$unset': {'password': ''}})
    elif not user.get('password_hash') and legacy_pw:
        await db.users.update_one(
            {'id': user['id']},
            {'$set': {'password_hash': pw_hash}, '$unset': {'password': ''}}
        )
        await db.audit_events.insert_one({
            'id': str(__import__('uuid').uuid4()),
            'entity_type': 'user', 'entity_id': user['id'],
            'action': 'auth_password_hash_backfilled',
            'actor_id': user['id'],
            'payload': {'source': 'login_email', 'had_plaintext': False},
            'created_at': _now(),
        })
    if user.get('user_status') == 'pending_pm_approval':
        raise HTTPException(status_code=403, detail='Account pending manager approval')
    if user.get('user_status') == 'suspended':
        raise HTTPException(status_code=403, detail='Account suspended')
    if user['role'] == 'project_manager':
        await ensure_user_org(user['id'], user.get('name', ''))
    user_phone_raw = user.get('phone_e164', '')
    sa_check = is_super_admin_phone(user_phone_raw)
    platform_role = 'super_admin' if sa_check['matched'] else 'none'
    sa_reason = f" reason={sa_check['reason']}" if sa_check.get('reason') else ''
    logger.info(f"[SA_CHECK] user_phone_raw={_mask_phone(user_phone_raw)} norm={_mask_phone(sa_check.get('norm') or '')} matched={sa_check['matched']} list_count={len(SUPER_ADMIN_PHONES)} source={SA_PHONES_SOURCE}{sa_reason}")
    if user.get('platform_role') != platform_role:
        await db.users.update_one({'id': user['id']}, {'$set': {'platform_role': platform_role}})
    sv = user.get('session_version', 0)
    token = _create_token(user['id'], user['email'], user['role'], platform_role,
                          session_version=sv, phone_e164=user.get('phone_e164', ''))
    user_resp = UserResponse(id=user['id'], email=user['email'], name=user['name'],
                          phone=user.get('phone'), role=user['role'],
                          company_id=user.get('company_id'),
                          specialties=user.get('specialties'), phone_e164=user.get('phone_e164'),
                          user_status=user.get('user_status', 'active'),
                          created_at=user.get('created_at'),
                          whatsapp_notifications_enabled=user.get('whatsapp_notifications_enabled', True))
    await db.users.update_one(
        {'id': user['id']},
        {
            '$set': {'last_login_at': datetime.now(timezone.utc).isoformat()},
            '$inc': {'login_count': 1},
        }
    )

    return {'token': token, 'user': user_resp.dict(), 'platform_role': platform_role}


_DEV_LOGIN_ROLE_MAP = {
    'contractor': 'contractor1@contractor-ops.com',
    'project_manager': 'pm@contractor-ops.com',
    'management_team': 'sitemanager@contractor-ops.com',
    'viewer': 'viewer@contractor-ops.com',
    'super_admin': 'superadmin@brikops.dev',
}

@router.post("/auth/dev-login")
async def dev_login(request: Request):
    from config import APP_MODE
    if APP_MODE != 'dev':
        raise HTTPException(status_code=404, detail='Not found')
    body = await request.json()
    role = body.get('role', '')
    email = _DEV_LOGIN_ROLE_MAP.get(role)
    if not email:
        raise HTTPException(status_code=400, detail=f'Unknown role: {role}')
    db = get_db()
    user = await db.users.find_one({'email': email}, {'_id': 0})
    if not user:
        raise HTTPException(status_code=404, detail=f'Demo user not found for role: {role}')
    if user['role'] == 'project_manager':
        await ensure_user_org(user['id'], user.get('name', ''))
    user_phone_raw = user.get('phone_e164', '')
    sa_check = is_super_admin_phone(user_phone_raw)
    platform_role = 'super_admin' if sa_check['matched'] else 'none'
    sa_reason = f" reason={sa_check['reason']}" if sa_check.get('reason') else ''
    logger.info(f"[SA_CHECK] user_phone_raw={_mask_phone(user_phone_raw)} norm={_mask_phone(sa_check.get('norm') or '')} matched={sa_check['matched']} list_count={len(SUPER_ADMIN_PHONES)} source={SA_PHONES_SOURCE}{sa_reason}")
    if user.get('platform_role') != platform_role:
        await db.users.update_one({'id': user['id']}, {'$set': {'platform_role': platform_role}})
    sv = user.get('session_version', 0)
    token = _create_token(user['id'], user['email'], user['role'], platform_role,
                          session_version=sv, phone_e164=user.get('phone_e164', ''))
    user_resp = UserResponse(id=user['id'], email=user['email'], name=user['name'],
                          phone=user.get('phone'), role=user['role'],
                          company_id=user.get('company_id'),
                          specialties=user.get('specialties'), phone_e164=user.get('phone_e164'),
                          user_status=user.get('user_status', 'active'),
                          created_at=user.get('created_at'),
                          whatsapp_notifications_enabled=user.get('whatsapp_notifications_enabled', True))
    return {'token': token, 'user': user_resp.dict(), 'platform_role': platform_role}


@router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user_allow_pending_deletion)):
    db = get_db()
    user_id = user['id']

    org_summary = None
    try:
        org_mem = await db.organization_memberships.find_one(
            {'user_id': user_id}, {'_id': 0, 'org_id': 1}
        )
        if org_mem:
            org_doc = await db.organizations.find_one(
                {'id': org_mem['org_id']}, {'_id': 0, 'id': 1, 'name': 1}
            )
            if org_doc:
                org_summary = OrgSummary(id=org_doc['id'], name=org_doc.get('name'))
    except Exception:
        pass

    proj_summaries = None
    try:
        memberships = await db.project_memberships.find(
            {'user_id': user_id}, {'_id': 0}
        ).to_list(200)
        if memberships:
            project_ids = list({m['project_id'] for m in memberships if m.get('project_id')})
            company_ids = list({m['company_id'] for m in memberships if m.get('company_id')})

            projects_map = {}
            if project_ids:
                projects = await db.projects.find(
                    {'id': {'$in': project_ids}},
                    {'_id': 0, 'id': 1, 'name': 1}
                ).to_list(200)
                projects_map = {p['id']: p.get('name') for p in projects}

            companies_map = {}
            if company_ids:
                companies = await db.project_companies.find(
                    {'id': {'$in': company_ids}},
                    {'_id': 0, 'id': 1, 'name': 1}
                ).to_list(200)
                companies_map = {c['id']: c.get('name') for c in companies}

            proj_summaries = []
            for m in memberships:
                pid = m.get('project_id', '')
                cid = m.get('company_id')
                proj_summaries.append(ProjectMembershipSummary(
                    project_id=pid,
                    project_name=projects_map.get(pid),
                    role=m.get('role'),
                    contractor_trade_key=m.get('contractor_trade_key'),
                    company_id=cid,
                    company_name=companies_map.get(cid) if cid else None,
                ))
    except Exception:
        pass

    return UserResponse(
        id=user['id'], email=user.get('email', ''), name=user['name'],
        phone=user.get('phone'), role=user['role'],
        company_id=user.get('company_id'),
        specialties=user.get('specialties'), phone_e164=user.get('phone_e164'),
        user_status=user.get('user_status', 'active'),
        created_at=user.get('created_at'),
        platform_role=user.get('platform_role', 'none'),
        preferred_language=user.get('preferred_language'),
        whatsapp_notifications_enabled=user.get('whatsapp_notifications_enabled', True),
        organization=org_summary,
        project_memberships_summary=proj_summaries,
    )
