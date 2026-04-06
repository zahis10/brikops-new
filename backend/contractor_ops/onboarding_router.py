from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Request
from typing import Optional
from datetime import datetime, timezone, timedelta
import uuid
import bcrypt
import logging
import jwt

from config import (
    APP_ID, JWT_SECRET, JWT_SECRET_VERSION, JWT_ALGORITHM,
    JWT_EXPIRATION_HOURS, JWT_SUPER_ADMIN_EXPIRATION_MINUTES, APP_MODE,
    is_super_admin_phone, ENABLE_AUTO_TRIAL,
    ENABLE_COMPLETE_ACCOUNT_GATE,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_FROM_NAME, SMTP_REPLY_TO,
    RESET_TOKEN_TTL_MINUTES, PASSWORD_RESET_BASE_URL,
)

from contractor_ops.phone_utils import normalize_israeli_phone
import secrets as _secrets
import hashlib as _hashlib
import smtplib
import re as _re_module
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from contractor_ops.billing import ensure_user_org, create_organization, create_trial_subscription, get_user_org, get_subscription, get_effective_access
from contractor_ops.schemas import (
    OTPRequest, OTPVerify, PhoneRegistration, ManagementRegistration,
    SetPasswordRequest, PhoneLoginRequest, JoinRequestResponse,
    ApproveRequest, RejectRequest, UserResponse, TokenResponse, Track,
)
from contractor_ops.social_auth_service import (
    verify_google_token,
    verify_apple_token,
    create_social_session,
    get_social_session,
    delete_social_session,
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_otp_service = None
_db = None
_rate_limits = {}


def set_otp_service(svc):
    global _otp_service
    _otp_service = svc


def set_onboarding_db(db):
    global _db
    _db = db


def get_otp():
    if _otp_service is None:
        raise RuntimeError("OTP service not initialized")
    return _otp_service


def get_db():
    if _db is None:
        raise RuntimeError("Onboarding DB not initialized")
    return _db


def _now():
    return datetime.now(timezone.utc).isoformat()


def _hash_password_sync(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def _hash_password(password):
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _hash_password_sync, password)

def _verify_password_sync(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

async def _verify_password(password, hashed):
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _verify_password_sync, password, hashed)


def _create_token(user_id, role, platform_role='none', session_version=0):
    now = datetime.now(timezone.utc)
    is_admin = (platform_role == 'super_admin')
    if is_admin:
        exp = now + timedelta(minutes=JWT_SUPER_ADMIN_EXPIRATION_MINUTES)
    else:
        exp = now + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        'user_id': user_id,
        'role': role,
        'platform_role': platform_role or 'none',
        'iss': APP_ID,
        'secret_version': JWT_SECRET_VERSION,
        'iat': now,
        'exp': exp,
        'sv': session_version,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _check_rate_limit(key, max_requests=5, window_seconds=60):
    now = datetime.now(timezone.utc).timestamp()
    if key not in _rate_limits:
        _rate_limits[key] = []
    _rate_limits[key] = [t for t in _rate_limits[key] if t > now - window_seconds]
    if len(_rate_limits[key]) >= max_requests:
        return False
    _rate_limits[key].append(now)
    return True


async def _check_rate_limit_mongo(db, kind: str, key: str, max_requests: int, window_seconds: int) -> bool:
    from pymongo import ReturnDocument
    from pymongo.errors import DuplicateKeyError

    now = datetime.now(timezone.utc)
    new_expires = now + timedelta(seconds=window_seconds)

    pipeline = [
        {"$set": {
            "count": {"$cond": {
                "if": {"$lte": [{"$ifNull": ["$expires_at", now - timedelta(seconds=1)]}, now]},
                "then": 1,
                "else": {"$add": [{"$ifNull": ["$count", 0]}, 1]},
            }},
            "window_start": {"$cond": {
                "if": {"$lte": [{"$ifNull": ["$expires_at", now - timedelta(seconds=1)]}, now]},
                "then": now,
                "else": {"$ifNull": ["$window_start", now]},
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
            result = await db.otp_rate_limits.find_one_and_update(
                {"kind": kind, "key": key},
                pipeline,
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            return result["count"] <= max_requests
        except DuplicateKeyError:
            if attempt == 0:
                continue
            return False


def _resolve_client_ip(request: Request) -> str:
    """Extract client IP from request.

    Trusted only when app runs behind a known reverse proxy:
      - Development: Replit dev proxy
      - Production: AWS Elastic Beanstalk ALB
    If the app is ever directly exposed without a trusted proxy,
    x-forwarded-for must NOT be trusted and this logic must be updated.
    """
    forwarded = request.headers.get('x-forwarded-for', '')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
        if ip and ip not in ('', 'unknown'):
            return ip
    return request.client.host if request.client else 'unknown'


MANAGEMENT_ROLES = [
    'project_manager_assistant', 'engineer', 'safety', 'foreman',
    'inspector', 'site_manager', 'admin_assistant',
]
SUBCONTRACTOR_ROLES = [
    'plumber', 'electrician', 'aluminum', 'painter', 'tiler',
    'carpenter', 'mason', 'hvac_tech', 'glazier', 'locksmith',
    'welder', 'insulator', 'roofer', 'landscaper', 'general_worker',
]


def create_onboarding_router(get_current_user_fn, require_roles_fn):
    router = APIRouter(prefix="/api")

    @router.post("/auth/request-otp")
    async def request_otp(req: OTPRequest, request: Request, background_tasks: BackgroundTasks):
        import uuid as _uuid
        request_id = str(_uuid.uuid4())[:8]

        if not req.phone_e164:
            raise HTTPException(status_code=400, detail='יש להזין מספר טלפון')
        try:
            phone_norm = normalize_israeli_phone(req.phone_e164)
            req.phone_e164 = phone_norm['phone_e164']
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        masked = req.phone_e164[:6] + '****' + req.phone_e164[-2:] if len(req.phone_e164) > 8 else req.phone_e164[:4] + '****'
        client_ip = _resolve_client_ip(request)

        db = get_db()

        if not await _check_rate_limit_mongo(db, "send_ip", client_ip, max_requests=20, window_seconds=900):
            logger.warning(f"[OTP-AUDIT] event=otp_throttled phone={masked} ip={client_ip} reason=send_ip_limit rid={request_id}")
            raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

        if not await _check_rate_limit_mongo(db, "send_phone_ip", f"{req.phone_e164}:{client_ip}", max_requests=3, window_seconds=300):
            logger.warning(f"[OTP-AUDIT] event=otp_throttled phone={masked} ip={client_ip} reason=send_phone_ip_limit rid={request_id}")
            raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

        otp = get_otp()
        sms_ready = bool(otp.sms_client and otp.sms_client.enabled)

        logger.info(
            f"[OTP-AUDIT] event=otp_requested phone={masked} ip={client_ip} "
            f"rid={request_id} sms_mode={otp.sms_mode} sms_ready={sms_ready}"
        )

        if not await _check_rate_limit_mongo(db, "send_phone", req.phone_e164, max_requests=5, window_seconds=300):
            logger.warning(f"[OTP-AUDIT] event=otp_throttled phone={masked} ip={client_ip} reason=send_phone_limit rid={request_id}")
            raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

        result = await otp.request_otp(req.phone_e164)

        if not result.get('success'):
            error_type = result.get('error', '')

            if error_type in ('rate_limited', 'too_many_attempts'):
                logger.warning(f"[OTP-AUDIT] event=otp_throttled phone={masked} ip={client_ip} reason={error_type} rid={request_id}")
                raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

            logger.warning(f"[OTP-AUDIT] event=otp_throttled phone={masked} ip={client_ip} reason={error_type} rid={request_id}")

            return {
                'success': True,
                'status': 'queued',
                'message': 'אם המספר קיים במערכת, קוד אימות נשלח.',
            }

        rid = result.get('rid', request_id)
        plain_code = result.pop('_code', None)

        if plain_code and not result.get('idempotent'):
            background_tasks.add_task(
                otp.deliver_otp_background, req.phone_e164, plain_code, rid
            )

        logger.info(
            f"[OTP-AUDIT] event=otp_queued phone={masked} ip={client_ip} "
            f"rid={rid} idempotent={result.get('idempotent', False)}"
        )

        response = {
            'success': True,
            'status': 'queued',
            'rid': rid,
            'expires_in': result.get('expires_in', 600),
            'message': 'אם המספר קיים במערכת, קוד אימות נשלח.',
        }
        if APP_MODE == 'dev' and result.get('otp_debug_code'):
            response['otp_debug_code'] = result['otp_debug_code']
        return response

    @router.post("/auth/verify-otp")
    async def verify_otp(req: OTPVerify, request: Request):
        if not req.phone_e164 or not req.code:
            raise HTTPException(status_code=400, detail='מספר טלפון וקוד נדרשים')
        try:
            phone_norm = normalize_israeli_phone(req.phone_e164)
            req.phone_e164 = phone_norm['phone_e164']
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        masked = req.phone_e164[:6] + '****' + req.phone_e164[-2:] if len(req.phone_e164) > 8 else req.phone_e164[:4] + '****'
        client_ip = _resolve_client_ip(request)

        db = get_db()

        if not await _check_rate_limit_mongo(db, "verify_ip", client_ip, max_requests=20, window_seconds=900):
            logger.warning(f"[OTP-AUDIT] event=otp_throttled phone={masked} ip={client_ip} reason=verify_ip_limit")
            raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

        if not await _check_rate_limit_mongo(db, "verify_phone", req.phone_e164, max_requests=10, window_seconds=300):
            logger.warning(f"[OTP-AUDIT] event=otp_throttled phone={masked} ip={client_ip} reason=verify_phone_limit")
            raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

        otp = get_otp()
        result = await otp.verify_otp(req.phone_e164, req.code)

        if not result['success']:
            error_type = result.get('error', '')
            if error_type == 'locked':
                logger.warning(f"[OTP-AUDIT] event=otp_lockout_triggered phone={masked} ip={client_ip} attempts={result.get('attempts', 'n/a')}")
                raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')
            logger.warning(f"[OTP-AUDIT] event=otp_verify_failed phone={masked} ip={client_ip} reason={error_type}")
            raise HTTPException(status_code=400, detail='קוד אימות שגוי או שפג תוקפו.')

        logger.info(f"[OTP-AUDIT] event=otp_verify_success phone={masked} ip={client_ip}")

        user = await db.users.find_one({'phone_e164': req.phone_e164}, {'_id': 0})

        if user:
            if user.get('user_status') == 'pending_pm_approval':
                return {
                    'verified': True,
                    'user_exists': True,
                    'user_status': 'pending_pm_approval',
                    'message': 'מחכה לאישור מנהל פרויקט',
                }
            if user.get('user_status') == 'rejected':
                return {
                    'verified': True,
                    'user_exists': True,
                    'user_status': 'rejected',
                    'message': 'הבקשה נדחתה. פנה למנהל הפרויקט.',
                }
            if user.get('user_status') == 'suspended':
                return {
                    'verified': True,
                    'user_exists': True,
                    'user_status': 'suspended',
                    'message': 'חשבון מושהה. פנה למנהל.',
                }
            if user['role'] == 'project_manager' and ENABLE_AUTO_TRIAL:
                await ensure_user_org(user['id'], user.get('name', ''))
            sa_check = is_super_admin_phone(user['phone_e164'])
            platform_role = 'super_admin' if sa_check['matched'] else 'none'
            if user.get('platform_role') != platform_role:
                await db.users.update_one({'id': user['id']}, {'$set': {'platform_role': platform_role}})
            sv = user.get('session_version', 0)
            token = _create_token(user['id'], user['role'],
                                  platform_role=platform_role, session_version=sv)
            await db.users.update_one(
                {'id': user['id']},
                {
                    '$set': {'last_login_at': _now()},
                    '$inc': {'login_count': 1},
                }
            )
            return {
                'verified': True,
                'user_exists': True,
                'user_status': user.get('user_status', 'active'),
                'token': token,
                'user': {
                    'id': user['id'],
                    'name': user.get('name', ''),
                    'phone_e164': user['phone_e164'],
                    'role': user['role'],
                    'email': user.get('email'),
                    'company_id': user.get('company_id'),
                    'user_status': user.get('user_status', 'active'),
                    'platform_role': platform_role,
                },
            }

        return {
            'verified': True,
            'user_exists': False,
            'requires_onboarding': True,
            'next': 'onboarding',
        }

    @router.post("/auth/register-with-phone")
    async def register_with_phone(reg: PhoneRegistration):
        if not reg.phone_e164:
            raise HTTPException(status_code=400, detail='יש להזין מספר טלפון')
        try:
            phone_norm = normalize_israeli_phone(reg.phone_e164)
            reg.phone_e164 = phone_norm['phone_e164']
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        if not reg.full_name or len(reg.full_name.strip()) < 2:
            raise HTTPException(status_code=400, detail='שם מלא נדרש')

        db = get_db()

        existing = await db.users.find_one({'phone_e164': reg.phone_e164})
        if existing:
            raise HTTPException(status_code=400, detail='מספר טלפון כבר רשום')

        project = await db.projects.find_one({'id': reg.project_id}, {'_id': 0})
        if not project:
            raise HTTPException(status_code=404, detail='פרויקט לא נמצא')

        if reg.track == Track.subcontractor:
            if not reg.requested_company_id:
                raise HTTPException(status_code=400, detail='חברה נדרשת לקבלן משנה')
            company = await db.companies.find_one({'id': reg.requested_company_id}, {'_id': 0})
            if not company:
                raise HTTPException(status_code=404, detail='חברה לא נמצאה')
            if reg.requested_role not in SUBCONTRACTOR_ROLES:
                raise HTTPException(status_code=400, detail='תפקיד לא תקין לקבלן משנה')
        else:
            if reg.requested_role not in MANAGEMENT_ROLES:
                raise HTTPException(status_code=400, detail='תפקיד לא תקין להנהלה')

        user_id = str(uuid.uuid4())
        ts = _now()

        role = 'contractor' if reg.track == Track.subcontractor else 'viewer'

        user_doc = {
            'id': user_id,
            'name': reg.full_name.strip(),
            'phone_e164': reg.phone_e164,
            'role': role,
            'user_status': 'pending_pm_approval',
            'company_id': reg.requested_company_id if reg.track == Track.subcontractor else None,
            'created_at': ts,
        }
        await db.users.insert_one(user_doc)

        pending_invites = await db.invites.find({
            'target_phone': reg.phone_e164,
            'status': 'pending',
        }).to_list(100)

        auto_linked_projects = []
        for invite in pending_invites:
            if invite.get('expires_at', '') < ts:
                await db.invites.update_one(
                    {'id': invite['id']},
                    {'$set': {'status': 'expired', 'updated_at': ts}}
                )
                await db.audit_events.insert_one({
                    'id': str(uuid.uuid4()),
                    'entity_type': 'invite',
                    'entity_id': invite['id'],
                    'action': 'expired',
                    'actor_id': 'system',
                    'payload': {
                        'project_id': invite['project_id'],
                        'phone': invite.get('target_phone'),
                        'role': invite.get('role'),
                        'reason': 'passive_expiry_on_registration',
                        'expires_at': invite.get('expires_at'),
                    },
                    'created_at': ts,
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

            await db.project_memberships.update_one(
                {'project_id': invite['project_id'], 'user_id': user_id},
                {'$set': {
                    'id': str(uuid.uuid4()),
                    'project_id': invite['project_id'],
                    'user_id': user_id,
                    'role': invite['role'],
                    'sub_role': invite.get('sub_role'),
                    'created_at': ts,
                }},
                upsert=True
            )

            if invite['role'] == 'project_manager':
                await db.users.update_one(
                    {'id': user_id},
                    {'$set': {'role': 'project_manager', 'user_status': 'active', 'updated_at': ts}}
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

            auto_linked_projects.append(invite['project_id'])

            await db.audit_events.insert_one({
                'id': str(uuid.uuid4()),
                'entity_type': 'invite',
                'entity_id': invite['id'],
                'action': 'accepted',
                'actor_id': user_id,
                'payload': {
                    'project_id': invite['project_id'],
                    'role': invite['role'],
                    'sub_role': invite.get('sub_role'),
                    'auto_linked': True,
                },
                'created_at': ts,
            })

        if auto_linked_projects:
            await db.users.update_one(
                {'id': user_id},
                {'$set': {'user_status': 'active', 'updated_at': ts}}
            )
            return {
                'success': True,
                'user_id': user_id,
                'user_status': 'active',
                'auto_linked_projects': auto_linked_projects,
                'message': f'נרשמת בהצלחה ושויכת אוטומטית ל-{len(auto_linked_projects)} פרויקטים.',
            }

        join_request_id = str(uuid.uuid4())
        await db.join_requests.insert_one({
            'id': join_request_id,
            'project_id': reg.project_id,
            'user_id': user_id,
            'track': reg.track.value,
            'requested_role': reg.requested_role,
            'requested_company_id': reg.requested_company_id,
            'status': 'pending',
            'reason': None,
            'created_at': ts,
            'reviewed_at': None,
            'reviewed_by': None,
        })

        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'join_request',
            'entity_id': join_request_id,
            'action': 'create',
            'actor_id': user_id,
            'payload': {
                'project_id': reg.project_id,
                'track': reg.track.value,
                'requested_role': reg.requested_role,
                'phone': reg.phone_e164[:6] + '***',
            },
            'created_at': ts,
        })

        return {
            'success': True,
            'user_id': user_id,
            'join_request_id': join_request_id,
            'user_status': 'pending_pm_approval',
            'message': 'הבקשה נשלחה. ממתין לאישור מנהל הפרויקט.',
        }

    @router.post("/auth/login-phone")
    async def login_with_phone(req: PhoneLoginRequest):
        db = get_db()
        user = await db.users.find_one({'phone_e164': req.phone_e164}, {'_id': 0})
        if not user:
            raise HTTPException(status_code=401, detail='מספר טלפון לא רשום')

        pw_hash = user.get('password_hash')
        legacy_pw = user.get('password', '')
        if not pw_hash and legacy_pw:
            if legacy_pw.startswith(('$2a$', '$2b$', '$2y$')):
                pw_hash = legacy_pw
            else:
                await db.audit_events.insert_one({
                    'id': str(uuid.uuid4()),
                    'entity_type': 'user', 'entity_id': user['id'],
                    'action': 'auth_password_migration_blocked_plaintext',
                    'actor_id': user['id'],
                    'payload': {'source': 'login_phone'},
                    'created_at': _now(),
                })
                raise HTTPException(status_code=401, detail='סיסמה שגויה')

        if not pw_hash:
            raise HTTPException(status_code=400, detail='לא הוגדרה סיסמה. יש להתחבר עם OTP.')

        if not await _verify_password(req.password, pw_hash):
            raise HTTPException(status_code=401, detail='סיסמה שגויה')

        if user.get('password_hash') and legacy_pw:
            await db.users.update_one({'id': user['id']}, {'$unset': {'password': ''}})
        elif not user.get('password_hash') and legacy_pw:
            await db.users.update_one(
                {'id': user['id']},
                {'$set': {'password_hash': pw_hash}, '$unset': {'password': ''}}
            )
            await db.audit_events.insert_one({
                'id': str(uuid.uuid4()),
                'entity_type': 'user', 'entity_id': user['id'],
                'action': 'auth_password_hash_backfilled',
                'actor_id': user['id'],
                'payload': {'source': 'login_phone', 'had_plaintext': False},
                'created_at': _now(),
            })

        if user.get('user_status') == 'pending_pm_approval':
            raise HTTPException(status_code=403, detail='מחכה לאישור מנהל פרויקט')

        if user.get('user_status') == 'suspended':
            raise HTTPException(status_code=403, detail='חשבון מושהה')

        if user['role'] == 'project_manager':
            await ensure_user_org(user['id'], user.get('name', ''))

        sa_check = is_super_admin_phone(user.get('phone_e164', ''))
        platform_role = 'super_admin' if sa_check['matched'] else user.get('platform_role', 'none')
        token = _create_token(user['id'], user['role'], platform_role=platform_role, session_version=user.get('session_version', 0))
        await db.users.update_one(
            {'id': user['id']},
            {
                '$set': {'last_login_at': _now()},
                '$inc': {'login_count': 1},
            }
        )
        return TokenResponse(
            token=token,
            user=UserResponse(
                id=user['id'], email=user.get('email'), name=user['name'],
                phone=user.get('phone'), role=user['role'],
                company_id=user.get('company_id'),
                phone_e164=user.get('phone_e164'),
                user_status=user.get('user_status', 'active'),
                created_at=user.get('created_at'),
            )
        )

    @router.post("/auth/set-password")
    async def set_password(req: SetPasswordRequest, user: dict = Depends(get_current_user_fn)):
        if not req.password or len(req.password) < 8:
            raise HTTPException(status_code=400, detail='סיסמה חייבת להיות לפחות 8 תווים')

        db = get_db()
        existing = await db.users.find_one({'id': user['id']}, {'_id': 0, 'password_hash': 1})
        if existing and existing.get('password_hash'):
            raise HTTPException(status_code=400, detail='סיסמה כבר הוגדרה. יש להשתמש בשינוי סיסמה.')

        hashed = await _hash_password(req.password)
        await db.users.update_one(
            {'id': user['id']},
            {'$set': {'password_hash': hashed}}
        )
        return {'success': True, 'message': 'סיסמה הוגדרה בהצלחה'}

    @router.get("/projects/{project_id}/join-requests")
    async def list_join_requests(
        project_id: str,
        status: Optional[str] = Query(None),
        user: dict = Depends(get_current_user_fn),
    ):
        if user['role'] not in ('project_manager',):
            raise HTTPException(status_code=403, detail='אין הרשאה')

        db = get_db()

        membership = await db.project_memberships.find_one({
            'project_id': project_id,
            'user_id': user['id'],
            'role': 'project_manager',
        })
        if not membership:
            raise HTTPException(status_code=403, detail='אתה לא מנהל פרויקט זה')

        query = {'project_id': project_id}
        if status:
            query['status'] = status

        requests = await db.join_requests.find(query, {'_id': 0}).sort('created_at', -1).to_list(1000)

        results = []
        for jr in requests:
            u = await db.users.find_one({'id': jr['user_id']}, {'_id': 0})
            company_name = None
            if jr.get('requested_company_id'):
                comp = await db.companies.find_one({'id': jr['requested_company_id']}, {'_id': 0})
                company_name = comp.get('name') if comp else None

            results.append(JoinRequestResponse(
                id=jr['id'],
                project_id=jr['project_id'],
                user_id=jr['user_id'],
                user_name=u.get('name', '') if u else '',
                user_phone=u.get('phone_e164', '') if u else '',
                track=jr['track'],
                requested_role=jr['requested_role'],
                requested_company_id=jr.get('requested_company_id'),
                company_name=company_name,
                status=jr['status'],
                reason=jr.get('reason'),
                created_at=jr.get('created_at'),
                reviewed_at=jr.get('reviewed_at'),
                reviewed_by=jr.get('reviewed_by'),
            ))

        return results

    @router.post("/join-requests/{request_id}/approve")
    async def approve_join_request(
        request_id: str,
        body: Optional[ApproveRequest] = None,
        user: dict = Depends(get_current_user_fn),
    ):
        if user['role'] not in ('project_manager',):
            raise HTTPException(status_code=403, detail='אין הרשאה')

        db = get_db()
        jr = await db.join_requests.find_one({'id': request_id}, {'_id': 0})
        if not jr:
            raise HTTPException(status_code=404, detail='בקשה לא נמצאה')

        if jr['status'] != 'pending':
            raise HTTPException(status_code=400, detail='בקשה כבר טופלה')

        membership = await db.project_memberships.find_one({
            'project_id': jr['project_id'],
            'user_id': user['id'],
            'role': 'project_manager',
        })
        if not membership:
            raise HTTPException(status_code=403, detail='אתה לא מנהל פרויקט זה')

        ts = _now()

        role_to_set = body.role if body and body.role else ('contractor' if jr['track'] == 'subcontractor' else 'viewer')
        company_to_set = body.company_id if body and body.company_id else jr.get('requested_company_id')

        from contractor_ops.member_management import check_role_conflict
        await check_role_conflict(db, jr['user_id'], jr['project_id'], role_to_set,
                                  actor_id=user['id'], attempted_action='approve_join_request')

        await db.users.update_one(
            {'id': jr['user_id']},
            {'$set': {
                'user_status': 'active',
                'role': role_to_set,
                'company_id': company_to_set,
            }}
        )

        membership_id = str(uuid.uuid4())
        await db.project_memberships.insert_one({
            'id': membership_id,
            'project_id': jr['project_id'],
            'user_id': jr['user_id'],
            'role': role_to_set,
            'status': 'active',
            'created_at': ts,
        })

        await db.join_requests.update_one(
            {'id': request_id},
            {'$set': {
                'status': 'approved',
                'reviewed_at': ts,
                'reviewed_by': user['id'],
            }}
        )

        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'join_request',
            'entity_id': request_id,
            'action': 'approve',
            'actor_id': user['id'],
            'payload': {
                'user_id': jr['user_id'],
                'project_id': jr['project_id'],
                'role': role_to_set,
            },
            'created_at': ts,
        })

        return {
            'success': True,
            'message': 'בקשה אושרה',
            'membership_id': membership_id,
        }

    @router.post("/join-requests/{request_id}/reject")
    async def reject_join_request(
        request_id: str,
        body: RejectRequest,
        user: dict = Depends(get_current_user_fn),
    ):
        if user['role'] not in ('project_manager',):
            raise HTTPException(status_code=403, detail='אין הרשאה')

        db = get_db()
        jr = await db.join_requests.find_one({'id': request_id}, {'_id': 0})
        if not jr:
            raise HTTPException(status_code=404, detail='בקשה לא נמצאה')

        if jr['status'] != 'pending':
            raise HTTPException(status_code=400, detail='בקשה כבר טופלה')

        membership = await db.project_memberships.find_one({
            'project_id': jr['project_id'],
            'user_id': user['id'],
            'role': 'project_manager',
        })
        if not membership:
            raise HTTPException(status_code=403, detail='אתה לא מנהל פרויקט זה')

        ts = _now()

        await db.users.update_one(
            {'id': jr['user_id']},
            {'$set': {'user_status': 'rejected'}}
        )

        await db.join_requests.update_one(
            {'id': request_id},
            {'$set': {
                'status': 'rejected',
                'reason': body.reason,
                'reviewed_at': ts,
                'reviewed_by': user['id'],
            }}
        )

        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'join_request',
            'entity_id': request_id,
            'action': 'reject',
            'actor_id': user['id'],
            'payload': {
                'user_id': jr['user_id'],
                'project_id': jr['project_id'],
                'reason': body.reason,
            },
            'created_at': ts,
        })

        return {
            'success': True,
            'message': 'בקשה נדחתה',
        }

    @router.get("/auth/management-roles")
    async def get_management_roles():
        return MANAGEMENT_ROLES

    @router.get("/auth/subcontractor-roles")
    async def get_subcontractor_roles():
        return SUBCONTRACTOR_ROLES

    @router.post("/auth/register-management", status_code=201)
    async def register_management(reg: ManagementRegistration):
        db = get_db()

        if not reg.full_name or len(reg.full_name.strip()) < 2:
            raise HTTPException(status_code=422, detail='שם מלא נדרש (לפחות 2 תווים)')
        if not reg.email or '@' not in reg.email:
            raise HTTPException(status_code=422, detail='כתובת אימייל נדרשת')
        if not reg.password or len(reg.password) < 8:
            raise HTTPException(status_code=422, detail='סיסמה נדרשת (לפחות 8 תווים)')
        if reg.requested_role not in MANAGEMENT_ROLES:
            raise HTTPException(status_code=422, detail='תפקיד לא תקין')

        email_lower = reg.email.strip().lower()

        try:
            phone_norm = normalize_israeli_phone(reg.phone_e164)
            phone_e164 = phone_norm['phone_e164']
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        join_code = reg.join_code.strip().upper()
        if not join_code:
            raise HTTPException(status_code=422, detail='קוד הצטרפות נדרש')

        project = await db.projects.find_one({'join_code': join_code}, {'_id': 0})
        if not project:
            raise HTTPException(status_code=404, detail='קוד הצטרפות לא נמצא')

        existing_phone = await db.users.find_one({'phone_e164': phone_e164})
        if existing_phone:
            raise HTTPException(status_code=400, detail='מספר טלפון כבר רשום במערכת')

        existing_email = await db.users.find_one({'email': email_lower})
        if existing_email:
            raise HTTPException(status_code=400, detail='כתובת אימייל כבר רשומה במערכת')

        user_id = str(uuid.uuid4())
        ts = _now()
        password_hash = await _hash_password(reg.password)

        user_doc = {
            'id': user_id,
            'name': reg.full_name.strip(),
            'email': email_lower,
            'password_hash': password_hash,
            'phone_e164': phone_e164,
            'role': 'management_team',
            'user_status': 'pending_pm_approval',
            'platform_role': 'none',
            'created_at': ts,
        }
        if ENABLE_COMPLETE_ACCOUNT_GATE != 'off':
            user_doc['account_complete'] = False
        await db.users.insert_one(user_doc)

        join_request_id = str(uuid.uuid4())
        await db.join_requests.insert_one({
            'id': join_request_id,
            'project_id': project['id'],
            'user_id': user_id,
            'track': 'management',
            'requested_role': reg.requested_role,
            'requested_company_id': None,
            'status': 'pending',
            'reason': None,
            'join_code_used': join_code,
            'created_at': ts,
        })

        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'user',
            'entity_id': user_id,
            'action': 'register_management',
            'actor_id': user_id,
            'payload': {
                'email': email_lower,
                'phone_e164': phone_e164,
                'requested_role': reg.requested_role,
                'project_id': project['id'],
                'join_code': join_code,
            },
            'created_at': ts,
        })

        logger.info(f"[REGISTER-MGMT] user={user_id} role={reg.requested_role} project={project['id']} join_code={join_code}")

        return {
            'user_id': user_id,
            'name': reg.full_name.strip(),
            'email': email_lower,
            'status': 'pending_pm_approval',
            'project_name': project.get('name', ''),
        }

    @router.get("/onboarding/status")
    async def onboarding_status(phone: str = Query(...)):
        db = get_db()
        try:
            norm = normalize_israeli_phone(phone)
            phone_e164 = norm['phone_e164']
        except ValueError:
            raise HTTPException(status_code=422, detail='מספר טלפון לא תקין')

        user = await db.users.find_one({'phone_e164': phone_e164}, {'_id': 0})

        pending_invites = await db.invites.find({
            'target_phone': phone_e164,
            'status': 'pending',
        }).to_list(50)
        ts = _now()
        active_invites = []
        for inv in pending_invites:
            if inv.get('expires_at', '') < ts:
                continue
            proj = await db.projects.find_one({'id': inv['project_id']}, {'_id': 0, 'id': 1, 'name': 1})
            active_invites.append({
                'invite_id': inv['id'],
                'project_id': inv['project_id'],
                'project_name': proj['name'] if proj else inv['project_id'],
                'role': inv.get('role', 'viewer'),
                'sub_role': inv.get('sub_role'),
                'invited_by': inv.get('created_by'),
                'created_at': inv.get('created_at'),
            })

        return {
            'user_status': user.get('user_status') if user else None,
            'has_org': bool(await get_user_org(user['id'])) if user else False,
            'pending_invites': active_invites,
            'can_create_org': user is not None and not bool(await get_user_org(user['id'])) if user else True,
        }

    @router.post("/onboarding/create-org")
    async def onboarding_create_org(body: dict):
        db = get_db()
        phone = body.get('phone')
        full_name = body.get('full_name', '').strip()
        org_name = body.get('org_name', '').strip()
        password = body.get('password', '')
        project_name = body.get('project_name', '').strip()
        email_raw = body.get('email', '').strip().lower() if body.get('email') else ''

        if not phone:
            raise HTTPException(status_code=400, detail='מספר טלפון נדרש')
        if not full_name or len(full_name) < 2:
            raise HTTPException(status_code=400, detail='שם מלא נדרש (לפחות 2 תווים)')
        if not email_raw or '@' not in email_raw:
            raise HTTPException(status_code=400, detail='כתובת אימייל נדרשת')
        import re as _re_email
        if not _re_email.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email_raw):
            raise HTTPException(status_code=400, detail='כתובת אימייל לא תקינה')
        if not org_name or len(org_name) < 2:
            raise HTTPException(status_code=400, detail='שם ארגון נדרש (לפחות 2 תווים)')
        if not password or len(password) < 8:
            raise HTTPException(status_code=400, detail='סיסמה נדרשת (לפחות 8 תווים)')
        import re as _re
        if not _re.search(r'[a-zA-Zא-ת]', password):
            raise HTTPException(status_code=400, detail='סיסמה חייבת לכלול לפחות אות אחת')
        if not _re.search(r'[0-9]', password):
            raise HTTPException(status_code=400, detail='סיסמה חייבת לכלול לפחות מספר אחד')
        _common_passwords = {'123456', '1234567', '12345678', '123456789', '1234567890', '111111', '000000', 'password', 'qwerty', 'abcdef', 'abcd1234', 'password1', 'abc123', 'admin123', '11111111'}
        if password.lower() in _common_passwords:
            raise HTTPException(status_code=400, detail='סיסמה זו נפוצה מדי, יש לבחור סיסמה חזקה יותר')

        try:
            norm = normalize_israeli_phone(phone)
            phone_e164 = norm['phone_e164']
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        email_taken = await db.users.find_one({'email': email_raw, 'phone_e164': {'$ne': phone_e164}}, {'_id': 1})
        if email_taken:
            raise HTTPException(status_code=400, detail='כתובת אימייל כבר רשומה במערכת')

        existing = await db.users.find_one({'phone_e164': phone_e164}, {'_id': 0})
        if existing:
            existing_org = await get_user_org(existing['id'])
            if existing_org:
                raise HTTPException(status_code=409, detail='למשתמש זה כבר קיים ארגון')
            existing_email = existing.get('email', '').strip().lower() if existing.get('email') else ''
            if existing_email and existing_email != email_raw:
                raise HTTPException(status_code=400, detail='לא ניתן לשנות אימייל דרך יצירת ארגון')
            user_id = existing['id']
            update_fields = {
                'name': full_name,
                'password_hash': await _hash_password(password),
                'role': 'project_manager',
                'user_status': 'active',
                'updated_at': _now(),
            }
            if not existing_email:
                update_fields['email'] = email_raw
            await db.users.update_one(
                {'id': user_id},
                {'$set': update_fields}
            )
        else:
            user_id = str(uuid.uuid4())
            ts = _now()
            new_pm_doc = {
                'id': user_id,
                'name': full_name,
                'email': email_raw,
                'phone_e164': phone_e164,
                'password_hash': await _hash_password(password),
                'role': 'project_manager',
                'user_status': 'active',
                'platform_role': 'none',
                'created_at': ts,
            }
            if ENABLE_COMPLETE_ACCOUNT_GATE != 'off':
                new_pm_doc['account_complete'] = False
            await db.users.insert_one(new_pm_doc)

        org = await create_organization(user_id, org_name)
        sub = await create_trial_subscription(org['id'])

        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'organization',
            'entity_id': org['id'],
            'action': 'create_via_onboarding',
            'actor_id': user_id,
            'payload': {
                'org_name': org_name,
                'email': email_raw,
                'trial_end': sub.get('trial_end_at'),
                'phone': phone_e164[:6] + '***',
            },
            'created_at': _now(),
        })

        user = await db.users.find_one({'id': user_id}, {'_id': 0})
        token = _create_token(
            user_id,
            user.get('role', 'project_manager'),
            user.get('platform_role', 'none'),
            user.get('session_version', 0),
        )

        project_id = str(uuid.uuid4())
        if not project_name:
            project_name = 'הפרויקט הראשון שלי'
        project_code = f"P-{_secrets.randbelow(9000) + 1000}"
        join_code = None
        for _jc in range(10):
            candidate = f"BRK-{_secrets.randbelow(9000) + 1000}"
            if not await db.projects.find_one({'join_code': candidate}):
                join_code = candidate
                break
        project_ts = _now()
        await db.projects.insert_one({
            'id': project_id,
            'name': project_name,
            'code': project_code,
            'description': '',
            'status': 'active',
            'client_name': '',
            'start_date': None,
            'end_date': None,
            'created_by': user_id,
            'org_id': org['id'],
            'join_code': join_code,
            'created_at': project_ts,
            'updated_at': project_ts,
        })
        await db.project_memberships.update_one(
            {'project_id': project_id, 'user_id': user_id},
            {'$set': {
                'id': str(uuid.uuid4()),
                'project_id': project_id,
                'user_id': user_id,
                'role': 'project_manager',
                'created_at': project_ts,
            }},
            upsert=True,
        )
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'project',
            'entity_id': project_id,
            'action': 'create_via_onboarding',
            'actor_id': user_id,
            'payload': {'project_name': project_name, 'org_id': org['id'], 'join_code': join_code},
            'created_at': project_ts,
        })

        logger.info(f"[ONBOARDING] create-org user={user_id} org={org['id']} project={project_id} trial_end={sub.get('trial_end_at')}")

        return {
            'success': True,
            'token': token,
            'user': {
                'id': user_id,
                'name': full_name,
                'phone_e164': phone_e164,
                'role': user.get('role', 'project_manager'),
                'platform_role': user.get('platform_role', 'none'),
            },
            'org': {'id': org['id'], 'name': org_name},
            'subscription': {
                'status': sub.get('status'),
                'trial_end_at': sub.get('trial_end_at'),
            },
            'project': {
                'id': project_id,
                'name': project_name,
                'join_code': join_code,
            },
        }

    @router.post("/onboarding/accept-invite")
    async def onboarding_accept_invite(body: dict):
        db = get_db()
        invite_id = body.get('invite_id')
        phone = body.get('phone')
        full_name = body.get('full_name', '').strip()
        password = body.get('password')
        opt_email = (body.get('email') or '').strip().lower() or None
        opt_lang = body.get('preferred_language') or None

        if not invite_id:
            raise HTTPException(status_code=400, detail='מזהה הזמנה נדרש')
        if not phone:
            raise HTTPException(status_code=400, detail='מספר טלפון נדרש')
        if not full_name or len(full_name) < 2:
            raise HTTPException(status_code=400, detail='שם מלא נדרש')

        try:
            norm = normalize_israeli_phone(phone)
            phone_e164 = norm['phone_e164']
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        invite = await db.invites.find_one({'id': invite_id, 'status': 'pending'}, {'_id': 0})
        if not invite:
            raise HTTPException(status_code=404, detail='הזמנה לא נמצאה או שכבר טופלה')

        if invite.get('target_phone') != phone_e164:
            raise HTTPException(status_code=403, detail='מספר הטלפון לא תואם את ההזמנה')

        ts = _now()
        if invite.get('expires_at', '') < ts:
            await db.invites.update_one({'id': invite_id}, {'$set': {'status': 'expired', 'updated_at': ts}})
            raise HTTPException(status_code=410, detail='ההזמנה פגה')

        existing_user = await db.users.find_one({'phone_e164': phone_e164}, {'_id': 0})
        if existing_user:
            user_id = existing_user['id']
            update_fields = {'name': full_name, 'user_status': 'active', 'updated_at': ts}
            if password:
                update_fields['password_hash'] = await _hash_password(password)
            if opt_email and not existing_user.get('email'):
                update_fields['email'] = opt_email
            if opt_lang:
                update_fields['preferred_language'] = opt_lang
            await db.users.update_one({'id': user_id}, {'$set': update_fields})
        else:
            if not password or len(password) < 8:
                raise HTTPException(status_code=400, detail='סיסמה נדרשת (לפחות 8 תווים)')
            user_id = str(uuid.uuid4())
            invite_role = invite.get('role', 'viewer')
            new_invite_doc = {
                'id': user_id,
                'name': full_name,
                'phone_e164': phone_e164,
                'password_hash': await _hash_password(password),
                'role': invite_role,
                'user_status': 'active',
                'platform_role': 'none',
                'created_at': ts,
            }
            if opt_email:
                new_invite_doc['email'] = opt_email
            if opt_lang:
                new_invite_doc['preferred_language'] = opt_lang
            if ENABLE_COMPLETE_ACCOUNT_GATE != 'off' and invite_role in ('project_manager', 'management_team'):
                new_invite_doc['account_complete'] = False
            await db.users.insert_one(new_invite_doc)

        from contractor_ops.member_management import check_role_conflict
        await check_role_conflict(db, user_id, invite['project_id'], invite.get('role', 'viewer'),
                                  actor_id=user_id, attempted_action='onboarding_accept_invite')

        membership_set = {
            'id': str(uuid.uuid4()),
            'project_id': invite['project_id'],
            'user_id': user_id,
            'role': invite.get('role', 'viewer'),
            'sub_role': invite.get('sub_role'),
            'created_at': ts,
        }
        if invite.get('role') == 'contractor' and invite.get('trade_key'):
            membership_set['contractor_trade_key'] = invite['trade_key']
        if invite.get('role') == 'contractor' and invite.get('company_id'):
            membership_set['company_id'] = invite['company_id']
        await db.project_memberships.update_one(
            {'project_id': invite['project_id'], 'user_id': user_id},
            {'$set': membership_set},
            upsert=True
        )

        org_info = {'org_id': None, 'org_name': None, 'is_owner': False, 'effective_access': 'read_only'}
        project = await db.projects.find_one({'id': invite['project_id']}, {'_id': 0, 'org_id': 1, 'name': 1})
        project_name = project.get('name', '') if project else ''
        project_org_id = project.get('org_id') if project else None

        if not project_org_id:
            inviter_org = await get_user_org(invite.get('inviter_user_id', ''))
            if inviter_org:
                project_org_id = inviter_org['id']
                await db.projects.update_one(
                    {'id': invite['project_id']},
                    {'$set': {'org_id': project_org_id}}
                )
                logger.info(f"[ONBOARDING] backfilled org_id={project_org_id} on project={invite['project_id']} from inviter")

        if project_org_id:
            await db.organization_memberships.update_one(
                {'org_id': project_org_id, 'user_id': user_id},
                {'$setOnInsert': {
                    'id': str(uuid.uuid4()),
                    'org_id': project_org_id,
                    'user_id': user_id,
                    'role': 'member',
                    'source': 'invite',
                    'project_id': invite['project_id'],
                    'created_at': ts,
                }},
                upsert=True
            )
            org = await db.organizations.find_one({'id': project_org_id}, {'_id': 0})
            if org:
                org_info['org_id'] = project_org_id
                org_info['org_name'] = org.get('name', '')
                org_info['is_owner'] = (org.get('owner_user_id') == user_id)
                eff = await get_effective_access(user_id, project_org_id)
                org_info['effective_access'] = eff.value

            await db.audit_events.insert_one({
                'id': str(uuid.uuid4()),
                'entity_type': 'organization',
                'entity_id': project_org_id,
                'action': 'org_member_added_via_invite',
                'actor_id': user_id,
                'payload': {
                    'org_id': project_org_id,
                    'org_name': org_info['org_name'],
                    'project_id': invite['project_id'],
                    'invite_id': invite_id,
                    'user_id': user_id,
                },
                'created_at': ts,
            })
            logger.info(f"[ONBOARDING] org-membership created org={project_org_id} user={user_id} via invite={invite_id}")

        await db.invites.update_one(
            {'id': invite_id},
            {'$set': {'status': 'accepted', 'accepted_by_user_id': user_id, 'accepted_at': ts, 'updated_at': ts}}
        )

        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'invite',
            'entity_id': invite_id,
            'action': 'accepted_via_onboarding',
            'actor_id': user_id,
            'payload': {
                'project_id': invite['project_id'],
                'role': invite.get('role'),
                'sub_role': invite.get('sub_role'),
                'trade_key': invite.get('trade_key'),
                'company_id': invite.get('company_id'),
            },
            'created_at': ts,
        })

        user = await db.users.find_one({'id': user_id}, {'_id': 0})
        token = _create_token(
            user_id,
            user.get('role', 'viewer'),
            user.get('platform_role', 'none'),
            user.get('session_version', 0),
        )

        logger.info(f"[ONBOARDING] accept-invite user={user_id} invite={invite_id} project={invite['project_id']}")

        return {
            'success': True,
            'token': token,
            'user': {
                'id': user_id,
                'name': full_name,
                'phone_e164': phone_e164,
                'role': user.get('role', 'viewer'),
            },
            'project_id': invite['project_id'],
            'project_name': project_name,
            'invite_role': invite.get('role', 'viewer'),
            'org_id': org_info['org_id'],
            'org_name': org_info['org_name'],
            'is_owner': org_info['is_owner'],
            'effective_access': org_info['effective_access'],
        }

    ROLE_LABELS_HE = {
        'project_manager': 'מנהל פרויקט',
        'management_team': 'צוות ניהול',
        'contractor': 'קבלן',
        'viewer': 'צופה',
    }

    @router.get("/invites/{invite_id}/info")
    async def get_invite_info(invite_id: str):
        db = get_db()
        invite = await db.invites.find_one({'id': invite_id}, {'_id': 0})
        if not invite:
            raise HTTPException(status_code=404, detail='הזמנה לא נמצאה')
        if invite.get('status') != 'pending':
            raise HTTPException(status_code=410, detail='ההזמנה כבר טופלה או פגה')
        ts = datetime.now(timezone.utc).isoformat()
        if invite.get('expires_at', '') < ts:
            await db.invites.update_one({'id': invite_id}, {'$set': {'status': 'expired', 'updated_at': ts}})
            raise HTTPException(status_code=410, detail='ההזמנה פגה')
        project = await db.projects.find_one({'id': invite['project_id']}, {'_id': 0, 'name': 1})
        role = invite.get('role', 'viewer')
        return {
            'invite_id': invite_id,
            'project_name': project['name'] if project else 'פרויקט',
            'project_id': invite['project_id'],
            'role': role,
            'role_display': ROLE_LABELS_HE.get(role, role),
        }

    @router.post("/onboarding/join-by-code")
    async def onboarding_join_by_code(body: dict):
        db = get_db()
        join_code = (body.get('join_code') or '').strip().upper()
        phone = body.get('phone')
        full_name = body.get('full_name', '').strip()
        password = body.get('password')
        requested_role = body.get('requested_role', 'viewer')

        if not join_code:
            raise HTTPException(status_code=400, detail='קוד הצטרפות נדרש')
        if not phone:
            raise HTTPException(status_code=400, detail='מספר טלפון נדרש')
        if not full_name or len(full_name) < 2:
            raise HTTPException(status_code=400, detail='שם מלא נדרש')

        try:
            norm = normalize_israeli_phone(phone)
            phone_e164 = norm['phone_e164']
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        project = await db.projects.find_one({'join_code': join_code}, {'_id': 0})
        if not project:
            raise HTTPException(status_code=404, detail='קוד הצטרפות לא נמצא')

        existing_user = await db.users.find_one({'phone_e164': phone_e164}, {'_id': 0})
        ts = _now()

        if existing_user:
            user_id = existing_user['id']
            existing_membership = await db.project_memberships.find_one(
                {'project_id': project['id'], 'user_id': user_id}
            )
            if existing_membership:
                raise HTTPException(status_code=409, detail='כבר שויכת לפרויקט זה')
            if password:
                await db.users.update_one(
                    {'id': user_id},
                    {'$set': {'name': full_name, 'password_hash': await _hash_password(password), 'updated_at': ts}}
                )
        else:
            if not password or len(password) < 8:
                raise HTTPException(status_code=400, detail='סיסמה נדרשת (לפחות 8 תווים)')
            user_id = str(uuid.uuid4())
            role = 'contractor' if requested_role in ('contractor',) else 'viewer'
            await db.users.insert_one({
                'id': user_id,
                'name': full_name,
                'phone_e164': phone_e164,
                'password_hash': await _hash_password(password),
                'role': role,
                'user_status': 'pending_pm_approval',
                'platform_role': 'none',
                'created_at': ts,
            })

        join_request_id = str(uuid.uuid4())
        await db.join_requests.insert_one({
            'id': join_request_id,
            'project_id': project['id'],
            'user_id': user_id,
            'track': 'subcontractor' if requested_role == 'contractor' else 'management',
            'requested_role': requested_role,
            'requested_company_id': body.get('company_id'),
            'status': 'pending',
            'reason': None,
            'join_code_used': join_code,
            'created_at': ts,
            'reviewed_at': None,
            'reviewed_by': None,
        })

        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'join_request',
            'entity_id': join_request_id,
            'action': 'create_via_join_code',
            'actor_id': user_id,
            'payload': {
                'project_id': project['id'],
                'join_code': join_code,
                'requested_role': requested_role,
                'phone': phone_e164[:6] + '***',
            },
            'created_at': ts,
        })

        logger.info(f"[ONBOARDING] join-by-code user={user_id} project={project['id']} code={join_code}")

        return {
            'success': True,
            'user_id': user_id,
            'join_request_id': join_request_id,
            'project_name': project.get('name'),
            'user_status': 'pending_pm_approval',
            'message': 'הבקשה נשלחה. ממתין לאישור מנהל הפרויקט.',
        }

    def _send_reset_email(to_email: str, reset_link: str) -> dict:
        if not SMTP_USER or not SMTP_PASS:
            return {'success': False, 'error': 'SMTP not configured'}

        msg = MIMEMultipart('alternative')
        msg['From'] = f'{SMTP_FROM_NAME} <{SMTP_FROM}>'
        msg['To'] = to_email
        msg['Reply-To'] = SMTP_REPLY_TO
        msg['Subject'] = 'BrikOps — איפוס סיסמה'

        text_body = (
            f'שלום,\n\n'
            f'קיבלנו בקשה לאיפוס הסיסמה שלך.\n'
            f'לחץ על הקישור הבא לאיפוס:\n\n'
            f'{reset_link}\n\n'
            f'הקישור תקף ל-{RESET_TOKEN_TTL_MINUTES} דקות.\n'
            f'אם לא ביקשת איפוס סיסמה, ניתן להתעלם מהודעה זו.\n\n'
            f'צוות BrikOps'
        )
        html_body = f'''
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #1a1a2e;">BrikOps — איפוס סיסמה</h2>
            <p>שלום,</p>
            <p>קיבלנו בקשה לאיפוס הסיסמה שלך.</p>
            <div style="text-align: center; margin: 24px 0;">
                <a href="{reset_link}" style="display: inline-block; background: #f59e0b; color: #fff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 16px;">
                    איפוס סיסמה
                </a>
            </div>
            <p style="color: #666; font-size: 13px;">הקישור תקף ל-{RESET_TOKEN_TTL_MINUTES} דקות.</p>
            <p style="color: #666; font-size: 13px;">אם לא ביקשת איפוס סיסמה, ניתן להתעלם מהודעה זו.</p>
        </div>
        '''
        from contractor_ops.email_templates import wrap_email
        msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(wrap_email(html_body, 'default'), 'html', 'utf-8'))

        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_FROM, to_email, msg.as_string())
            logger.info(f"[SMTP-SEND] from_name={SMTP_FROM_NAME} from_email={SMTP_FROM} reply_to={SMTP_REPLY_TO}")
            return {'success': True}
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"[RESET-EMAIL] SMTP auth failed: {e.smtp_code}")
            return {'success': False, 'error': f'SMTP auth failed ({e.smtp_code})'}
        except smtplib.SMTPException as e:
            logger.error(f"[RESET-EMAIL] SMTP error: {type(e).__name__}")
            return {'success': False, 'error': f'SMTP error: {type(e).__name__}'}
        except Exception as e:
            logger.error(f"[RESET-EMAIL] Send failed: {type(e).__name__}")
            return {'success': False, 'error': f'Send failed: {type(e).__name__}'}

    @router.post('/auth/forgot-password')
    async def forgot_password(request: Request):
        db = get_db()
        body = await request.json()
        email_raw = (body.get('email') or '').strip().lower()

        request_id = str(uuid.uuid4())[:8]
        client_ip = request.headers.get('x-forwarded-for', request.client.host if request.client else 'unknown')
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        if not await _check_rate_limit_mongo(db, "forgot_pw_ip", client_ip, max_requests=5, window_seconds=900):
            logger.warning(f"[FORGOT-PW] rid={request_id} IP_RATE_LIMITED ip={client_ip}")
            raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

        safe_response = {
            'ok': True,
            'message': 'אם הכתובת רשומה במערכת, נשלח אליה קישור לאיפוס סיסמה.',
        }

        if not email_raw or not _re_module.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email_raw):
            logger.info(f"[FORGOT-PW] rid={request_id} invalid_email")
            return safe_response

        if not await _check_rate_limit_mongo(db, "forgot_pw_email", email_raw, max_requests=3, window_seconds=900):
            logger.warning(f"[FORGOT-PW] rid={request_id} EMAIL_RATE_LIMITED email_prefix={email_raw.split('@')[0][:3]}***")
            return safe_response

        management_roles = {'project_manager', 'management_team'}
        user = await db.users.find_one(
            {'email': email_raw, 'role': {'$in': list(management_roles)}},
            {'_id': 1, 'id': 1, 'email': 1, 'role': 1, 'platform_role': 1, 'name': 1}
        )

        if not user:
            sa_user = await db.users.find_one(
                {'email': email_raw, 'platform_role': 'super_admin'},
                {'_id': 1, 'id': 1, 'email': 1, 'role': 1, 'platform_role': 1, 'name': 1}
            )
            if sa_user:
                user = sa_user

        if not user:
            logger.info(f"[FORGOT-PW] rid={request_id} no_management_user email_prefix={email_raw.split('@')[0][:3]}***")
            return safe_response

        user_id = user.get('id') or str(user['_id'])
        email_prefix = email_raw.split('@')[0][:3] + '***'

        token = _secrets.token_urlsafe(48)
        token_hash = _hashlib.sha256(token.encode('utf-8')).hexdigest()
        ts = _now()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)

        await db.password_reset_tokens.delete_many({'user_id': user_id, 'used': False})

        await db.password_reset_tokens.insert_one({
            'token_hash': token_hash,
            'token_prefix': token[:8],
            'user_id': user_id,
            'email': email_raw,
            'created_at': ts,
            'expires_at': expires_at.isoformat(),
            'expires_at_dt': expires_at,
            'used': False,
        })

        reset_link = f"{PASSWORD_RESET_BASE_URL}/reset-password?token={token}"
        send_result = _send_reset_email(email_raw, reset_link)

        await db.audit_events.insert_one({
            'event': 'password_reset_requested',
            'user_id': user_id,
            'email_prefix': email_prefix,
            'email_sent': send_result.get('success', False),
            'ip': client_ip,
            'created_at': ts,
        })

        if send_result.get('success'):
            logger.info(f"[FORGOT-PW] rid={request_id} email_sent user={user_id} prefix={email_prefix}")
        else:
            logger.error(f"[FORGOT-PW] rid={request_id} email_failed user={user_id} error={send_result.get('error')}")

        return safe_response

    @router.post('/auth/reset-password')
    async def reset_password(request: Request):
        db = get_db()
        body = await request.json()
        token = (body.get('token') or '').strip()
        new_password = body.get('new_password') or ''

        request_id = str(uuid.uuid4())[:8]

        client_ip = request.headers.get('x-forwarded-for', request.client.host if request.client else 'unknown')
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        if not await _check_rate_limit_mongo(db, "reset_pw_ip", client_ip, max_requests=10, window_seconds=900):
            logger.warning(f"[RESET-PW] rid={request_id} IP_RATE_LIMITED ip={client_ip}")
            raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

        if not token:
            raise HTTPException(status_code=400, detail='קישור לא תקף או שפג תוקפו')

        now = datetime.now(timezone.utc)
        token_hash = _hashlib.sha256(token.encode('utf-8')).hexdigest()
        token_doc = await db.password_reset_tokens.find_one({
            'token_hash': token_hash,
            'used': False,
        })
        if not token_doc:
            token_doc = await db.password_reset_tokens.find_one({
                'token': token,
                'used': False,
            })

        if not token_doc:
            logger.warning(f"[RESET-PW] rid={request_id} token_not_found_or_used")
            raise HTTPException(status_code=400, detail='קישור לא תקף או שפג תוקפו')

        expires_at = token_doc.get('expires_at_dt')
        if not expires_at:
            try:
                expires_at = datetime.fromisoformat(token_doc['expires_at']).replace(tzinfo=timezone.utc)
            except Exception:
                expires_at = now

        if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            logger.warning(f"[RESET-PW] rid={request_id} token_expired user={token_doc.get('user_id')}")
            await db.password_reset_tokens.update_one({'_id': token_doc['_id']}, {'$set': {'used': True}})
            raise HTTPException(status_code=400, detail='הקישור פג תוקף. יש לבקש קישור חדש.')

        if not new_password or len(new_password) < 8:
            raise HTTPException(status_code=400, detail='סיסמה נדרשת (לפחות 8 תווים)')
        if not _re_module.search(r'[a-zA-Zא-ת]', new_password):
            raise HTTPException(status_code=400, detail='סיסמה חייבת לכלול לפחות אות אחת')
        if not _re_module.search(r'[0-9]', new_password):
            raise HTTPException(status_code=400, detail='סיסמה חייבת לכלול לפחות מספר אחד')
        _common_passwords = {'123456', '1234567', '12345678', '123456789', '1234567890', '111111', '000000', 'password', 'qwerty', 'abcdef', 'abcd1234', 'password1', 'abc123', 'admin123', '11111111'}
        if new_password.lower() in _common_passwords:
            raise HTTPException(status_code=400, detail='סיסמה זו נפוצה מדי, יש לבחור סיסמה חזקה יותר')

        user_id = token_doc['user_id']
        password_hash = await _hash_password(new_password)
        ts = _now()

        existing_user = await db.users.find_one({'id': user_id}, {'session_version': 1})
        old_sv = existing_user.get('session_version', 0) if existing_user else 0
        new_sv = old_sv + 1

        await db.users.update_one(
            {'id': user_id},
            {'$set': {'password_hash': password_hash, 'session_version': new_sv, 'updated_at': ts}, '$unset': {'password': ''}}
        )

        await db.password_reset_tokens.update_one(
            {'_id': token_doc['_id']},
            {'$set': {'used': True, 'used_at': ts}}
        )

        await db.audit_events.insert_one({
            'event': 'password_reset_completed',
            'user_id': user_id,
            'email_prefix': token_doc.get('email', '').split('@')[0][:3] + '***',
            'session_version_change': f'{old_sv}->{new_sv}',
            'created_at': ts,
        })

        logger.info(f"[RESET-PW] rid={request_id} password_reset user={user_id}")

        return {'ok': True, 'message': 'הסיסמה עודכנה בהצלחה.'}

    # ──────────────────────────────────────────────
    # Social Login — Google + Apple Sign-In
    # ──────────────────────────────────────────────

    class SocialAuthRequest(BaseModel):
        provider: str = Field(..., pattern="^(google|apple)$")
        id_token: str
        apple_name: Optional[str] = None

    class SocialSendOtpRequest(BaseModel):
        session_token: str
        phone: Optional[str] = None

    class SocialVerifyOtpRequest(BaseModel):
        session_token: str
        otp_code: str

    def _mask_phone_social(phone: str) -> str:
        """054-1234567 → 054***4567"""
        if not phone or len(phone) < 7:
            return "***"
        return phone[:3] + "***" + phone[-4:]

    @router.post("/auth/social")
    async def social_auth(body: SocialAuthRequest, request: Request):
        client_ip = _resolve_client_ip(request)
        db = get_db()

        if not await _check_rate_limit_mongo(db, "social_ip", client_ip, max_requests=10, window_seconds=300):
            raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

        try:
            if body.provider == "google":
                social_info = await verify_google_token(body.id_token)
            elif body.provider == "apple":
                social_info = await verify_apple_token(body.id_token)
                if body.apple_name and not social_info.get("name"):
                    social_info["name"] = body.apple_name
            else:
                raise HTTPException(status_code=400, detail="ספק לא נתמך")
        except ValueError as e:
            logger.warning(f"[SOCIAL-AUTH] token_verify_failed provider={body.provider} ip={client_ip} error={e}")
            raise HTTPException(status_code=400, detail=str(e))

        social_id = social_info["sub"]
        email = social_info.get("email", "")
        name = social_info.get("name", "")
        social_id_field = f"{body.provider}_id"

        existing_user = await db.users.find_one({social_id_field: social_id}, {"_id": 0})

        if existing_user:
            if existing_user.get('role') != 'project_manager':
                raise HTTPException(status_code=403, detail='התחברות חברתית זמינה למנהלי פרויקט בלבד.')

            status = existing_user.get("user_status", "active")
            if status == "pending_deletion":
                raise HTTPException(
                    status_code=403,
                    detail={'message': 'החשבון שלך בתהליך מחיקה. בטל את המחיקה כדי להמשיך.', 'code': 'pending_deletion'}
                )
            if status == "suspended":
                raise HTTPException(status_code=403, detail='חשבון מושהה. פנה למנהל.')
            if status == "pending_pm_approval":
                return {"status": "pending_approval", "message": "מחכה לאישור מנהל פרויקט"}
            if status == "rejected":
                return {"status": "rejected", "message": "הבקשה נדחתה. פנה למנהל הפרויקט."}

            if ENABLE_AUTO_TRIAL:
                await ensure_user_org(existing_user['id'], existing_user.get('name', ''))

            sa_check = is_super_admin_phone(existing_user.get('phone_e164', ''))
            platform_role = 'super_admin' if sa_check['matched'] else 'none'
            if existing_user.get('platform_role') != platform_role:
                await db.users.update_one({'id': existing_user['id']}, {'$set': {'platform_role': platform_role}})

            sv = existing_user.get('session_version', 0)
            token = _create_token(existing_user['id'], existing_user['role'],
                                  platform_role=platform_role, session_version=sv)

            await db.users.update_one(
                {'id': existing_user['id']},
                {'$set': {'last_login_at': _now()}, '$inc': {'login_count': 1}}
            )

            logger.info(f"[SOCIAL-AUTH] login_success user={existing_user['id']} provider={body.provider}")

            return {
                "status": "authenticated",
                "token": token,
                "user": {
                    "id": existing_user["id"],
                    "name": existing_user.get("name", ""),
                    "phone_e164": existing_user.get("phone_e164", ""),
                    "role": existing_user["role"],
                    "email": existing_user.get("email"),
                    "company_id": existing_user.get("company_id"),
                    "user_status": existing_user.get("user_status", "active"),
                    "platform_role": platform_role,
                },
            }

        if email:
            email_user = await db.users.find_one({"email": email.lower()}, {"_id": 0})
            if email_user:
                if email_user.get('role') != 'project_manager':
                    raise HTTPException(status_code=403, detail='התחברות חברתית זמינה למנהלי פרויקט בלבד.')

                status = email_user.get("user_status", "active")
                if status == "pending_deletion":
                    raise HTTPException(
                        status_code=403,
                        detail={'message': 'החשבון שלך בתהליך מחיקה. בטל את המחיקה כדי להמשיך.', 'code': 'pending_deletion'}
                    )
                if status == "suspended":
                    raise HTTPException(status_code=403, detail='חשבון מושהה. פנה למנהל.')
                if status == "pending_pm_approval":
                    return {"status": "pending_approval", "message": "מחכה לאישור מנהל פרויקט"}
                if status == "rejected":
                    return {"status": "rejected", "message": "הבקשה נדחתה. פנה למנהל הפרויקט."}

                session_token = await create_social_session(db, {
                    "provider": body.provider,
                    "social_id": social_id,
                    "email": email,
                    "name": name,
                    "flow": "link",
                    "user_id": email_user["id"],
                })

                logger.info(f"[SOCIAL-AUTH] link_required user={email_user['id']} provider={body.provider}")

                return {
                    "status": "link_required",
                    "session_token": session_token,
                    "phone_masked": _mask_phone_social(email_user.get("phone_e164", "")),
                    "email": email,
                }

        session_token = await create_social_session(db, {
            "provider": body.provider,
            "social_id": social_id,
            "email": email,
            "name": name,
            "flow": "register",
        })

        logger.info(f"[SOCIAL-AUTH] registration_required provider={body.provider} email={'yes' if email else 'no'}")

        return {
            "status": "registration_required",
            "session_token": session_token,
            "email": email,
        }


    @router.post("/auth/social/send-otp")
    async def social_send_otp(body: SocialSendOtpRequest, request: Request):
        client_ip = _resolve_client_ip(request)
        db = get_db()

        if not await _check_rate_limit_mongo(db, "social_send_ip", client_ip, max_requests=20, window_seconds=900):
            raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

        session = await get_social_session(db, body.session_token)
        if not session:
            raise HTTPException(status_code=400, detail="הפעולה פגה תוקף, נסה שוב")

        if session["flow"] == "link":
            user = await db.users.find_one({"id": session["user_id"]}, {"_id": 0})
            if not user:
                raise HTTPException(status_code=400, detail="משתמש לא נמצא")
            phone = user["phone_e164"]

        elif session["flow"] == "register":
            if not body.phone:
                raise HTTPException(status_code=400, detail="מספר טלפון חובה")

            try:
                phone_norm = normalize_israeli_phone(body.phone)
                phone = phone_norm["phone_e164"]
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

            if not await _check_rate_limit_mongo(db, "social_send_phone", phone, max_requests=5, window_seconds=300):
                raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

            existing = await db.users.find_one({"phone_e164": phone}, {"_id": 0})
            if existing:
                if existing.get('role') != 'project_manager':
                    raise HTTPException(status_code=403, detail='התחברות חברתית זמינה למנהלי פרויקט בלבד.')

                status = existing.get("user_status", "active")
                if status == "pending_deletion":
                    raise HTTPException(
                        status_code=403,
                        detail={'message': 'החשבון שלך בתהליך מחיקה. בטל את המחיקה כדי להמשיך.', 'code': 'pending_deletion'}
                    )
                if status == "suspended":
                    raise HTTPException(status_code=403, detail='חשבון מושהה. פנה למנהל.')
                if status == "pending_pm_approval":
                    raise HTTPException(status_code=403, detail='מחכה לאישור מנהל פרויקט')
                if status == "rejected":
                    raise HTTPException(status_code=403, detail='הבקשה נדחתה. פנה למנהל הפרויקט.')

                await db.social_auth_sessions.update_one(
                    {"id": body.session_token},
                    {"$set": {"flow": "link", "user_id": existing["id"], "phone": phone}}
                )
                logger.info(f"[SOCIAL-AUTH] register_to_link phone_exists user={existing['id']}")
            else:
                await db.social_auth_sessions.update_one(
                    {"id": body.session_token},
                    {"$set": {"phone": phone}}
                )
        else:
            raise HTTPException(status_code=400, detail="flow לא חוקי")

        otp = get_otp()
        result = await otp.request_otp(phone)

        if not result["success"]:
            error = result.get("error", "")
            if error == "rate_limited":
                raise HTTPException(status_code=429, detail=result.get("message", "נא לנסות שוב מאוחר יותר."))
            if error == "too_many_attempts":
                raise HTTPException(status_code=429, detail=result.get("message", "חשבון נעול. נסה שוב מאוחר יותר."))
            raise HTTPException(status_code=400, detail=result.get("message", "שגיאה בשליחת קוד"))

        return {
            "status": "otp_sent",
            "phone_masked": _mask_phone_social(phone),
            "expires_in": result.get("expires_in", 300),
        }


    @router.post("/auth/social/verify-otp")
    async def social_verify_otp(body: SocialVerifyOtpRequest, request: Request):
        client_ip = _resolve_client_ip(request)
        db = get_db()

        if not await _check_rate_limit_mongo(db, "social_verify_ip", client_ip, max_requests=20, window_seconds=900):
            raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

        session = await get_social_session(db, body.session_token)
        if not session:
            raise HTTPException(status_code=400, detail="הפעולה פגה תוקף, נסה שוב")

        if session["flow"] == "link":
            user = await db.users.find_one({"id": session["user_id"]}, {"_id": 0})
            if not user:
                raise HTTPException(status_code=400, detail="משתמש לא נמצא")
            phone = user["phone_e164"]
        else:
            phone = session.get("phone")
            if not phone:
                raise HTTPException(status_code=400, detail="מספר טלפון חסר — שלח OTP קודם")

        if not await _check_rate_limit_mongo(db, "social_verify_phone", phone, max_requests=10, window_seconds=300):
            raise HTTPException(status_code=429, detail='נא לנסות שוב מאוחר יותר.')

        otp = get_otp()
        result = await otp.verify_otp(phone, body.otp_code)

        if not result["success"]:
            error = result.get("error", "")
            if error == "locked":
                raise HTTPException(status_code=429, detail=result.get("message", "נא לנסות שוב מאוחר יותר."))
            raise HTTPException(status_code=400, detail="קוד אימות שגוי או שפג תוקפו.")

        social_id_field = f"{session['provider']}_id"

        if session["flow"] == "link":
            link_user = await db.users.find_one({"id": session["user_id"]}, {"_id": 0})
            if not link_user:
                raise HTTPException(status_code=400, detail="משתמש לא נמצא")
            if link_user.get('role') != 'project_manager':
                raise HTTPException(status_code=403, detail='התחברות חברתית זמינה למנהלי פרויקט בלבד.')
            link_status = link_user.get("user_status", "active")
            if link_status == "pending_deletion":
                raise HTTPException(
                    status_code=403,
                    detail={'message': 'החשבון שלך בתהליך מחיקה. בטל את המחיקה כדי להמשיך.', 'code': 'pending_deletion'}
                )
            if link_status == "suspended":
                raise HTTPException(status_code=403, detail='חשבון מושהה. פנה למנהל.')
            if link_status == "pending_pm_approval":
                await delete_social_session(db, body.session_token)
                return {"status": "pending_approval", "message": "מחכה לאישור מנהל פרויקט"}
            if link_status == "rejected":
                await delete_social_session(db, body.session_token)
                return {"status": "rejected", "message": "הבקשה נדחתה. פנה למנהל הפרויקט."}

            await db.users.update_one(
                {"id": session["user_id"]},
                {
                    "$set": {social_id_field: session["social_id"]},
                    "$addToSet": {"auth_methods": session["provider"]},
                }
            )
            await db.users.update_one(
                {"id": session["user_id"]},
                {"$addToSet": {"auth_methods": "phone"}}
            )

            user = await db.users.find_one({"id": session["user_id"]}, {"_id": 0})

            logger.info(f"[SOCIAL-AUTH] linked user={user['id']} provider={session['provider']}")

        elif session["flow"] == "register":
            user_id = str(uuid.uuid4())
            ts = _now()
            email = session.get("email", "").lower().strip() if session.get("email") else ""
            name = session.get("name", "").strip() if session.get("name") else ""

            user_doc = {
                "id": user_id,
                "name": name,
                "phone_e164": phone,
                "role": "project_manager",
                "user_status": "active",
                "platform_role": "none",
                "created_at": ts,
                social_id_field: session["social_id"],
                "auth_methods": ["phone", session["provider"]],
            }
            if email:
                user_doc["email"] = email
            if ENABLE_COMPLETE_ACCOUNT_GATE != 'off':
                user_doc["account_complete"] = False

            await db.users.insert_one(user_doc)

            if ENABLE_AUTO_TRIAL:
                await ensure_user_org(user_id, name)

            user = await db.users.find_one({"id": user_id}, {"_id": 0})

            logger.info(f"[SOCIAL-AUTH] registered user={user_id} provider={session['provider']} phone={_mask_phone_social(phone)}")

        else:
            raise HTTPException(status_code=400, detail="flow לא חוקי")

        await delete_social_session(db, body.session_token)

        sa_check = is_super_admin_phone(user.get('phone_e164', ''))
        platform_role = 'super_admin' if sa_check['matched'] else 'none'
        if user.get('platform_role') != platform_role:
            await db.users.update_one({'id': user['id']}, {'$set': {'platform_role': platform_role}})

        sv = user.get('session_version', 0)
        token = _create_token(user['id'], user['role'],
                              platform_role=platform_role, session_version=sv)

        await db.users.update_one(
            {'id': user['id']},
            {'$set': {'last_login_at': _now()}, '$inc': {'login_count': 1}}
        )

        return {
            "status": "authenticated",
            "token": token,
            "user": {
                "id": user["id"],
                "name": user.get("name", ""),
                "phone_e164": user.get("phone_e164", ""),
                "role": user["role"],
                "email": user.get("email"),
                "company_id": user.get("company_id"),
                "user_status": user.get("user_status", "active"),
                "platform_role": platform_role,
            },
        }

    return router
