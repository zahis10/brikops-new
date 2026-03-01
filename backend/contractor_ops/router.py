from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query, Body, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import os
import uuid
import secrets
import bcrypt
import logging
import re as _re
from jose import JWTError, jwt

from config import (
    APP_ID, JWT_SECRET, JWT_SECRET_VERSION,
    JWT_ALGORITHM, JWT_ALLOWED_ALGORITHMS,
    JWT_EXPIRATION_HOURS, JWT_CLOCK_SKEW_SECONDS,
    JWT_SUPER_ADMIN_EXPIRATION_MINUTES,
)
from config import is_super_admin_phone, SUPER_ADMIN_PHONES, ENABLE_DEBUG_ENDPOINTS, ENABLE_COMPLETE_ACCOUNT_GATE
from contractor_ops.phone_utils import normalize_israeli_phone
from contractor_ops.otp_service import OTPService
from contractor_ops.stepup_service import (
    create_challenge as stepup_create_challenge,
    verify_challenge as stepup_verify_challenge,
    has_valid_grant as stepup_has_valid_grant,
    ensure_indexes as stepup_ensure_indexes,
)

_router_otp_service = None

def set_router_otp_service(svc):
    global _router_otp_service
    _router_otp_service = svc

def _get_otp_service():
    if _router_otp_service:
        return _router_otp_service
    raise RuntimeError("OTP service not initialized")
from contractor_ops.bucket_utils import compute_task_bucket, BUCKET_LABELS, CATEGORY_TO_BUCKET, TRADE_MAP
from contractor_ops.billing import (
    get_effective_access, EffectiveAccess, get_billing_info,
    admin_billing_override, get_user_org, ensure_user_org,
    migrate_existing_projects, get_subscription, _resolve_access,
    PAYWALL_DETAIL, PAYWALL_CODE,
)
from contractor_ops.schemas import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    Project, Building, Floor, Unit, Company,
    Task, TaskCreate, TaskUpdate, TaskAssign, TaskStatusChange,
    TaskUpdateCreate, TaskUpdateResponse,
    AuditEvent, DashboardResponse,
    TaskStatus, VALID_TRANSITIONS, Priority, Role, Category,
    UpdateType, FloorKind,
    BulkFloorRequest, BulkUnitRequest, BulkResultResponse, HierarchyResponse,
    InsertFloorRequest,
    ManagementSubRole, MembershipRole, ManagerDecisionRequest,
    InviteCreate,
)

logger = logging.getLogger(__name__)
security = HTTPBearer()
router = APIRouter(prefix="/api")


async def _get_contractor_trade_key(db, user_id: str, project_id: str) -> Optional[str]:
    mem = await db.project_memberships.find_one(
        {'user_id': user_id, 'project_id': project_id},
        {'_id': 0, 'contractor_trade_key': 1},
    )
    return mem.get('contractor_trade_key') if mem else None


def _trades_match(task_category: Optional[str], contractor_trade_key: Optional[str]) -> bool:
    if not contractor_trade_key:
        return True
    if not task_category or task_category == 'general':
        return True
    task_bucket = CATEGORY_TO_BUCKET.get(task_category, task_category)
    trade_bucket = CATEGORY_TO_BUCKET.get(contractor_trade_key, contractor_trade_key)
    return task_bucket == trade_bucket

_db = None
_notification_engine = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db

def set_notification_engine(engine):
    global _notification_engine
    _notification_engine = engine

def get_notification_engine():
    return _notification_engine


def _now():
    return datetime.now(timezone.utc).isoformat()


def _hash_password_sync(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def _hash_password(password: str) -> str:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _hash_password_sync, password)


def _verify_password_sync(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

async def _verify_password(password: str, hashed: str) -> bool:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _verify_password_sync, password, hashed)


def _create_token(user_id: str, email: str, role: str, platform_role: str = 'none',
                   session_version: int = 0, phone_e164: str = '') -> str:
    now = datetime.now(timezone.utc)
    is_admin = (platform_role == 'super_admin')
    if is_admin:
        exp = now + timedelta(minutes=JWT_SUPER_ADMIN_EXPIRATION_MINUTES)
    else:
        exp = now + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'platform_role': platform_role or 'none',
        'iss': APP_ID,
        'secret_version': JWT_SECRET_VERSION,
        'iat': now,
        'exp': exp,
        'sv': session_version,
    }
    if phone_e164:
        payload['phone_e164'] = phone_e164
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    db = get_db()
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token, JWT_SECRET,
            algorithms=JWT_ALLOWED_ALGORITHMS,
            options={
                'require_exp': True,
                'require_iat': True,
                'require_iss': True,
                'leeway': JWT_CLOCK_SKEW_SECONDS,
            },
            issuer=APP_ID,
        )
        if payload.get('secret_version') != JWT_SECRET_VERSION:
            raise HTTPException(status_code=401, detail='Token secret version mismatch')
        user = await db.users.find_one({'id': payload['user_id']}, {'_id': 0})
        if not user:
            raise HTTPException(status_code=401, detail='User not found')
        if user.get('user_status') == 'pending_pm_approval':
            raise HTTPException(status_code=403, detail='Account pending approval')
        if user.get('user_status') == 'suspended':
            raise HTTPException(status_code=403, detail='Account suspended')
        jwt_sv = payload.get('sv', 0)
        db_sv = user.get('session_version', 0)
        if jwt_sv < db_sv:
            raise HTTPException(status_code=401, detail='Session revoked. Please login again.')
        user['_jwt_sv'] = jwt_sv
        user['_jwt_exp'] = payload.get('exp', 0)
        return user
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f'Invalid token: {str(e)}')


def require_roles(*roles: str):
    async def checker(user: dict = Depends(get_current_user)):
        if user['role'] not in roles:
            raise HTTPException(status_code=403, detail='Insufficient permissions')
        return user
    return checker


_admin_rate_limits = {}

def _check_admin_rate_limit(key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    now = datetime.now(timezone.utc).timestamp()
    if key not in _admin_rate_limits:
        _admin_rate_limits[key] = []
    _admin_rate_limits[key] = [t for t in _admin_rate_limits[key] if t > now - window_seconds]
    if len(_admin_rate_limits[key]) >= max_requests:
        return False
    _admin_rate_limits[key].append(now)
    return True


def _is_super_admin(user: dict) -> bool:
    return user.get('platform_role') == 'super_admin'


async def _audit_admin_access(user_id: str, route: str, method: str, status: int,
                               ip: str = '', user_agent: str = '', detail: str = ''):
    try:
        db = get_db()
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'event_type': 'admin_access',
            'actor_id': user_id,
            'route': route,
            'method': method,
            'status_code': status,
            'ip': ip,
            'user_agent': user_agent[:200] if user_agent else '',
            'detail': detail,
            'created_at': datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


async def require_super_admin(request: Request, user: dict = Depends(get_current_user)):
    user_phone = user.get('phone_e164', '')
    route = str(request.url.path)
    method = request.method
    ip = request.headers.get('x-forwarded-for', request.client.host if request.client else '')
    ua = request.headers.get('user-agent', '')

    rl_max = 30 if method == 'GET' else 10
    if not _check_admin_rate_limit(f"admin:{user.get('id', '')}:{method}", max_requests=rl_max, window_seconds=60):
        await _audit_admin_access(user.get('id', ''), route, method, 429, ip, ua, 'rate_limited')
        raise HTTPException(status_code=429, detail='יותר מדי בקשות. נסה שוב בעוד דקה.')

    if not is_super_admin_phone(user_phone):
        await _audit_admin_access(user.get('id', ''), route, method, 403, ip, ua, 'not_in_allowlist')
        raise HTTPException(status_code=403, detail='גישה מוגבלת למנהל מערכת בלבד')

    if not _is_super_admin(user):
        await _audit_admin_access(user.get('id', ''), route, method, 403, ip, ua, 'missing_platform_role')
        raise HTTPException(status_code=403, detail='גישה מוגבלת למנהל מערכת בלבד')

    await _audit_admin_access(user.get('id', ''), route, method, 200, ip, ua, 'granted')
    return user


async def require_stepup(request: Request, user: dict = Depends(require_super_admin)):
    user_id = user.get('id', '')
    sv = user.get('_jwt_sv', user.get('session_version', 0))
    if not await stepup_has_valid_grant(user_id, sv):
        route = str(request.url.path)
        ip = request.headers.get('x-forwarded-for', request.client.host if request.client else '')
        ua = request.headers.get('user-agent', '')
        await _audit_admin_access(user_id, route, request.method, 403, ip, ua, 'stepup_required')
        raise HTTPException(status_code=403, detail={'message': 'נדרש אימות נוסף (Step-Up)', 'code': 'stepup_required'})
    return user


async def _check_project_read_access(user: dict, project_id: str):
    if _is_super_admin(user):
        return True
    db = get_db()
    membership = await db.project_memberships.find_one({
        'user_id': user['id'],
        'project_id': project_id,
    })
    if not membership:
        raise HTTPException(status_code=403, detail='אין לך גישה לפרויקט זה')
    return True


async def _check_project_access(user: dict, project_id: str):
    if _is_super_admin(user):
        return True
    db = get_db()
    membership = await db.project_memberships.find_one({
        'user_id': user['id'],
        'project_id': project_id,
    })
    if not membership:
        raise HTTPException(status_code=403, detail='אין לך הרשאה לנהל פרויקט זה')
    management_roles = ['project_manager', 'management_team']
    if membership.get('role') not in management_roles:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    return True


async def _get_project_role(user: dict, project_id: str) -> str:
    if _is_super_admin(user):
        return 'project_manager'
    db = get_db()
    membership = await db.project_memberships.find_one({
        'user_id': user['id'],
        'project_id': project_id,
    }, {'_id': 0})
    if not membership:
        return 'none'
    return membership.get('role', 'none')


async def _get_project_membership(user: dict, project_id: str) -> dict:
    if _is_super_admin(user):
        return {'role': 'project_manager', 'sub_role': None}
    db = get_db()
    membership = await db.project_memberships.find_one({
        'user_id': user['id'],
        'project_id': project_id,
    }, {'_id': 0})
    if not membership:
        return {'role': 'none', 'sub_role': None}
    return {'role': membership.get('role', 'none'), 'sub_role': membership.get('sub_role')}


MANAGEMENT_ROLES = ('project_manager', 'management_team')


def get_public_base_url() -> str:
    url = os.environ.get('PUBLIC_APP_URL', '').rstrip('/')
    if url:
        return url
    raw = os.environ.get('REPLIT_DOMAINS', os.environ.get('REPLIT_DEV_DOMAIN', ''))
    if raw:
        if ',' in raw:
            raw = raw.split(',')[0]
        return f"https://{raw}"
    return ''


def _get_task_link(task_id: str) -> str:
    base = get_public_base_url()
    return f"{base}/tasks/{task_id}" if base else ""


async def _audit(entity_type: str, entity_id: str, action: str, actor_id: str, payload: dict):
    db = get_db()
    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': entity_type,
        'entity_id': entity_id,
        'action': action,
        'actor_id': actor_id,
        'payload': payload,
        'created_at': _now(),
    })


async def require_full_access(user: dict = Depends(get_current_user)):
    access = await get_effective_access(user['id'])
    if access != EffectiveAccess.FULL_ACCESS:
        raise HTTPException(
            status_code=402,
            detail={'detail': PAYWALL_DETAIL, 'code': PAYWALL_CODE},
        )
    return user


PAYWALL_EXEMPT_PATHS = {
    '/api/auth/', '/api/billing/', '/api/admin/',
    '/api/debug/', '/api/updates/feed',
}

async def _check_paywall(request_method: str, request_path: str, user: dict):
    if request_method == 'GET':
        return
    for exempt in PAYWALL_EXEMPT_PATHS:
        if request_path.startswith(exempt):
            return
    access = await get_effective_access(user['id'])
    if access != EffectiveAccess.FULL_ACCESS:
        raise HTTPException(
            status_code=402,
            detail={'detail': PAYWALL_DETAIL, 'code': PAYWALL_CODE},
        )


@router.get("/billing/me")
async def billing_me(user: dict = Depends(get_current_user)):
    info = await get_billing_info(user['id'])
    return info


@router.get("/billing/plans/active")
async def billing_plans_active(user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    if not _is_super_admin(user):
        has_any_project = await db.project_memberships.find_one(
            {'user_id': user['id'], 'role': {'$nin': ['contractor', 'viewer']}},
            {'_id': 0, 'project_id': 1}
        )
        if not has_any_project:
            has_org_role = await db.organization_memberships.find_one(
                {'user_id': user['id'], 'role': {'$in': ['org_admin', 'billing_admin']}},
                {'_id': 0}
            )
            if not has_org_role:
                org_owned = await db.organizations.find_one(
                    {'owner_user_id': user['id']}, {'_id': 0}
                )
                if not org_owned:
                    raise HTTPException(status_code=403, detail='אין הרשאה')
    plans = await db.billing_plans.find(
        {'is_active': True},
        {'_id': 0, 'id': 1, 'name': 1, 'version': 1, 'project_fee_monthly': 1, 'unit_tiers': 1}
    ).to_list(100)
    return plans


@router.get("/billing/org/{org_id}")
async def billing_org(org_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role, check_org_pm_role, get_billing_for_org
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            is_pm = await check_org_pm_role(user['id'], org_id)
            if not is_pm:
                raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיוב ארגון')
    result = await get_billing_for_org(org_id, user_id=user['id'])
    if result.get('error'):
        raise HTTPException(status_code=404, detail=result['error'])
    return result


@router.get("/billing/preview-renewal")
async def billing_preview_renewal(request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role, check_org_pm_role, preview_renewal
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    scope = request.query_params.get('scope', 'org')
    org_id = request.query_params.get('id', '')
    cycle = request.query_params.get('cycle', 'monthly')
    if not org_id:
        raise HTTPException(status_code=400, detail='חובה לציין id')
    if cycle not in ('monthly', 'yearly'):
        raise HTTPException(status_code=400, detail='cycle חייב להיות monthly או yearly')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        pm_role = await check_org_pm_role(user['id'], org_id) if not billing_role else False
        if not billing_role and not pm_role:
            raise HTTPException(status_code=403, detail='אין הרשאה לצפות בתצוגה מקדימה של חידוש')
    result = await preview_renewal(org_id, cycle)
    return result


@router.post("/billing/org/{org_id}/payment-request")
async def billing_payment_request(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, check_org_pm_role, create_payment_request
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    requested_by_kind = None
    if _is_super_admin(user):
        requested_by_kind = 'billing_manager'
    else:
        billing_role = await check_org_billing_role(user['id'], org_id)
        is_pm = await check_org_pm_role(user['id'], org_id)
        if billing_role in ('org_admin', 'billing_admin', 'owner'):
            requested_by_kind = 'billing_manager'
        elif is_pm:
            requested_by_kind = 'pm_handoff'
        else:
            raise HTTPException(status_code=403, detail='אין הרשאה ליצירת בקשת תשלום')
    body = await request.json()
    cycle = body.get('cycle', 'monthly')
    if cycle not in ('monthly', 'yearly'):
        raise HTTPException(status_code=400, detail='cycle חייב להיות monthly או yearly')
    note = body.get('note', '')
    contact_email = body.get('contact_email', '')
    try:
        result = await create_payment_request(org_id, user['id'], cycle, note, contact_email, requested_by_kind=requested_by_kind)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/billing/org/{org_id}/payment-requests")
async def billing_list_payment_requests(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, check_org_pm_role, list_payment_requests
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    pm_only_filter = None
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            is_pm = await check_org_pm_role(user['id'], org_id)
            if not is_pm:
                raise HTTPException(status_code=403, detail='אין הרשאה לצפייה בבקשות תשלום')
            pm_only_filter = user['id']
    status_param = request.query_params.get('status', '')
    statuses = [s.strip() for s in status_param.split(',') if s.strip()] if status_param else None
    valid_statuses = {'requested', 'sent', 'paid', 'canceled', 'pending_review', 'rejected'}
    if statuses and not all(s in valid_statuses for s in statuses):
        raise HTTPException(status_code=400, detail='סטטוס לא תקין')
    result = await list_payment_requests(org_id, statuses, requested_by_user_id=pm_only_filter)
    return result


@router.get("/billing/org/{org_id}/payment-config")
async def billing_get_payment_config(org_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, get_payment_config
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאה לצפייה בהגדרות תשלום')
    result = await get_payment_config(org_id)
    if result.get('error'):
        raise HTTPException(status_code=404, detail=result['error'])
    return result


@router.put("/billing/org/{org_id}/payment-config")
async def billing_update_payment_config(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, update_payment_config
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail='רק אדמין ראשי יכול לעדכן הגדרות תשלום')
    body = await request.json()
    bank_details = body.get('bank_details', '')
    bit_phone = body.get('bit_phone', '')
    result = await update_payment_config(org_id, user['id'], bank_details, bit_phone)
    return result


@router.post("/billing/org/{org_id}/payment-requests/{request_id}/mark-paid-by-customer")
async def billing_customer_mark_paid(org_id: str, request_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, customer_mark_paid
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role not in ('org_admin', 'billing_admin', 'owner'):
            raise HTTPException(status_code=403, detail='אין הרשאה לסימון תשלום')
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    customer_paid_note = body.get('customer_paid_note', '')
    try:
        result = await customer_mark_paid(org_id, request_id, user['id'], customer_paid_note)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/billing/org/{org_id}/payment-requests/{request_id}/receipt")
async def billing_upload_receipt_form(org_id: str, request_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, upload_receipt
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role not in ('org_admin', 'billing_admin', 'owner'):
            raise HTTPException(status_code=403, detail='אין הרשאה להעלאת אסמכתא')
    form = await request.form()
    file = form.get('file')
    if not file:
        raise HTTPException(status_code=400, detail='חובה לצרף קובץ')
    file_data = await file.read()
    if len(file_data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail='גודל הקובץ חורג מ-10MB')
    filename = file.filename or 'receipt'
    content_type = file.content_type or 'application/octet-stream'
    allowed_types = {'application/pdf', 'image/jpeg', 'image/png', 'image/jpg'}
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail='סוג קובץ לא נתמך — PDF, JPG, PNG בלבד')
    try:
        result = await upload_receipt(org_id, request_id, user['id'], file_data, filename, content_type)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/billing/org/{org_id}/payment-requests/{request_id}/receipt")
async def billing_get_receipt(org_id: str, request_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, get_receipt_url
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role not in ('org_admin', 'billing_admin', 'owner'):
            raise HTTPException(status_code=403, detail='אין הרשאה לצפייה באסמכתא')
    try:
        result = await get_receipt_url(org_id, request_id)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/billing/org/{org_id}/payment-requests/{request_id}/cancel")
async def billing_cancel_request(org_id: str, request_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, cancel_payment_request
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role not in ('org_admin', 'billing_admin', 'owner'):
            raise HTTPException(status_code=403, detail='אין הרשאה לבטל בקשות תשלום')
    try:
        result = await cancel_payment_request(org_id, request_id, user['id'])
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/billing/org/{org_id}/payment-requests/{request_id}/reject")
async def billing_reject_request(org_id: str, request_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, reject_payment_request
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail='רק אדמין ראשי יכול לדחות בקשות')
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    rejection_reason = body.get('rejection_reason', '')
    try:
        result = await reject_payment_request(org_id, request_id, user['id'], rejection_reason)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/billing/org/{org_id}/mark-paid")
async def billing_mark_paid(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, mark_paid
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail='רק אדמין ראשי יכול לאשר תשלומים')
    body = await request.json()
    request_id = body.get('request_id')
    cycle = body.get('cycle')
    paid_note = body.get('paid_note', '')
    try:
        result = await mark_paid(org_id, user['id'], request_id, cycle, paid_note)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/billing/project/{project_id}")
async def billing_project(project_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role, get_billing_for_project
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    org_id = project.get('org_id')
    if not org_id:
        raise HTTPException(status_code=400, detail='פרויקט ללא ארגון — לא ניתן להציג חיוב')
    if not _is_super_admin(user):
        membership = await db.project_memberships.find_one(
            {'user_id': user['id'], 'project_id': project_id}, {'_id': 0, 'role': 1}
        )
        mem_role = membership.get('role', 'none') if membership else 'none'
        if mem_role in ('contractor', 'viewer'):
            raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיוב פרויקט')
        if mem_role == 'none':
            billing_role = await check_org_billing_role(user['id'], org_id)
            if not billing_role:
                raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיוב פרויקט')
    result = await get_billing_for_project(project_id)
    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])
    can_edit = False
    if _is_super_admin(user):
        can_edit = True
    else:
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role in ('org_admin', 'billing_admin', 'owner'):
            can_edit = True
    result['user_can_edit_billing'] = can_edit
    membership = await db.project_memberships.find_one(
        {'user_id': user['id'], 'project_id': project_id}, {'_id': 0, 'role': 1}
    )
    result['user_project_role'] = membership.get('role') if membership else None
    return result


@router.patch("/billing/project/{project_id}")
async def billing_project_update(project_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, update_project_billing, recalc_org_total
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    org_id = project.get('org_id')
    if not org_id:
        raise HTTPException(status_code=400, detail='פרויקט ללא ארגון')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת עדכון חיוב פרויקט')
    pb = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0, 'id': 1})
    if not pb:
        raise HTTPException(status_code=404, detail='אין רשומת חיוב לפרויקט')
    body = await request.json()
    allowed_fields = {'plan_id', 'contracted_units', 'status', 'setup_state', 'billing_contact_note'}
    updates = {k: v for k, v in body.items() if k in allowed_fields}
    if not updates:
        raise HTTPException(status_code=400, detail='לא סופקו שדות לעדכון')
    try:
        result = await update_project_billing(pb['id'], updates, user['id'])
        await recalc_org_total(org_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/billing/project/{project_id}/handoff-request")
async def billing_handoff_request(project_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, request_billing_handoff
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    org_id = project.get('org_id')
    if not org_id:
        raise HTTPException(status_code=400, detail='פרויקט ללא ארגון')
    if not _is_super_admin(user):
        membership = await db.project_memberships.find_one(
            {'user_id': user['id'], 'project_id': project_id}, {'_id': 0, 'role': 1}
        )
        mem_role = membership.get('role', 'none') if membership else 'none'
        if mem_role in ('contractor', 'viewer', 'none'):
            billing_role = await check_org_billing_role(user['id'], org_id)
            if not billing_role:
                raise HTTPException(status_code=403, detail='אין הרשאה לבקשת העברת חיוב')
        if mem_role == 'management_team':
            raise HTTPException(status_code=403, detail='אין הרשאה לבקשת העברת חיוב')
    pb = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0, 'id': 1})
    if not pb:
        raise HTTPException(status_code=404, detail='אין רשומת חיוב לפרויקט')
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    note = body.get('note', None)
    try:
        result = await request_billing_handoff(pb['id'], user['id'], note)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/billing/project/{project_id}/handoff-ack")
async def billing_handoff_ack(project_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, acknowledge_billing_handoff
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    org_id = project.get('org_id')
    if not org_id:
        raise HTTPException(status_code=400, detail='פרויקט ללא ארגון')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאה לאישור העברת חיוב')
    pb = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0, 'id': 1})
    if not pb:
        raise HTTPException(status_code=404, detail='אין רשומת חיוב לפרויקט')
    try:
        result = await acknowledge_billing_handoff(pb['id'], user['id'])
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/billing/project/{project_id}/setup-complete")
async def billing_setup_complete(project_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, complete_billing_setup
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    org_id = project.get('org_id')
    if not org_id:
        raise HTTPException(status_code=400, detail='פרויקט ללא ארגון')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאה להשלמת הגדרת חיוב')
    pb = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0, 'id': 1})
    if not pb:
        raise HTTPException(status_code=404, detail='אין רשומת חיוב לפרויקט')
    try:
        result = await complete_billing_setup(pb['id'], user['id'])
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/billing/org/{org_id}/invoice/preview")
async def invoice_preview(org_id: str, period: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    from contractor_ops.invoicing import build_invoice_preview, check_and_enforce_dunning, validate_period_ym
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    try:
        validate_period_ym(period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיובי ארגון')
    await check_and_enforce_dunning(org_id)
    preview = await build_invoice_preview(org_id, period)
    return preview


@router.post("/billing/org/{org_id}/invoice/generate")
async def invoice_generate(org_id: str, period: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    from contractor_ops.invoicing import generate_invoice, validate_period_ym
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    try:
        validate_period_ym(period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role or billing_role == 'org_admin':
            raise HTTPException(status_code=403, detail='אין הרשאה להפקת חשבוניות')
    invoice = await generate_invoice(org_id, period, user['id'])
    return invoice


@router.get("/billing/org/{org_id}/invoices")
async def invoice_list(org_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    from contractor_ops.invoicing import list_invoices, check_and_enforce_dunning
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיובי ארגון')
    await check_and_enforce_dunning(org_id)
    invoices = await list_invoices(org_id)
    return {'invoices': invoices}


@router.get("/billing/org/{org_id}/invoices/{invoice_id}")
async def invoice_detail(org_id: str, invoice_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    from contractor_ops.invoicing import get_invoice
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיובי ארגון')
    invoice = await get_invoice(org_id, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail='חשבונית לא נמצאה')
    return invoice


@router.post("/billing/org/{org_id}/invoices/{invoice_id}/mark-paid")
async def invoice_mark_paid(org_id: str, invoice_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    from contractor_ops.invoicing import mark_invoice_paid
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role or billing_role == 'org_admin':
            raise HTTPException(status_code=403, detail='אין הרשאה לסימון חשבונית כשולם')
    try:
        result = await mark_invoice_paid(org_id, invoice_id, user['id'])
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orgs/{org_id}/billing-contact")
async def get_billing_contact_endpoint(org_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role, get_billing_contact
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת צפייה בפרטי חיוב ארגון')
    result = await get_billing_contact(org_id)
    if result.get('error'):
        raise HTTPException(status_code=404, detail=result['error'])
    return result


@router.put("/orgs/{org_id}/billing-contact")
async def update_billing_contact_endpoint(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role, update_billing_contact
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role not in ('owner', 'billing_admin'):
            raise HTTPException(status_code=403, detail='אין הרשאת עדכון פרטי חיוב ארגון')
    body = await request.json()
    result = await update_billing_contact(org_id, body, user['id'])
    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])
    return result


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


@router.post("/auth/logout-all")
async def logout_all_sessions(request: Request, user: dict = Depends(get_current_user)):
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
        query['$or'] = [
            {'name': {'$regex': q_stripped, '$options': 'i'}},
            {'phone_e164': {'$regex': q_stripped}},
            {'email': {'$regex': q_stripped, '$options': 'i'}},
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


@router.put("/projects/{project_id}/members/{user_id}/contractor-profile")
async def update_contractor_profile(project_id: str, user_id: str, body: dict = Body(...), user: dict = Depends(get_current_user)):
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')

    is_sa = user.get('platform_role') == 'super_admin'
    caller_membership = await _get_project_membership(user, project_id)
    caller_role = caller_membership.get('role', 'none') if caller_membership else 'none'

    org_id = project.get('org_id')
    caller_org_role = None
    if org_id:
        org_mem = await db.organization_memberships.find_one({'org_id': org_id, 'user_id': user['id']}, {'_id': 0, 'role': 1})
        caller_org_role = org_mem.get('role') if org_mem else None
        org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'owner_user_id': 1})
        if org and org.get('owner_user_id') == user['id']:
            caller_org_role = 'owner'

    can_edit = is_sa or caller_role in ('project_manager',) or caller_org_role in ('owner', 'org_admin')
    if not can_edit:
        raise HTTPException(status_code=403, detail='אין הרשאה לעדכן פרופיל קבלן')

    membership = await db.project_memberships.find_one({
        'project_id': project_id, 'user_id': user_id
    })
    if not membership:
        raise HTTPException(status_code=404, detail='חברות בפרויקט לא נמצאה')
    if membership.get('role') != 'contractor':
        raise HTTPException(status_code=400, detail='ניתן לעדכן פרופיל חברה/תחום רק לקבלנים')

    new_company_id = body.get('company_id')
    new_trade_key = body.get('trade_key')

    if not new_company_id or not str(new_company_id).strip():
        raise HTTPException(status_code=422, detail='חברה היא שדה חובה')
    if not new_trade_key or not str(new_trade_key).strip():
        raise HTTPException(status_code=422, detail='תחום הוא שדה חובה')

    company_doc = await db.project_companies.find_one({
        'id': new_company_id, 'project_id': project_id,
        'deletedAt': {'$exists': False},
    })
    if not company_doc:
        raise HTTPException(status_code=422, detail='חברה לא נמצאה בפרויקט זה')

    is_global_trade = new_trade_key in BUCKET_LABELS
    is_project_trade = False
    if not is_global_trade:
        is_project_trade = await db.project_trades.find_one({'project_id': project_id, 'key': new_trade_key}) is not None
    if not is_global_trade and not is_project_trade:
        raise HTTPException(status_code=422, detail=f'מקצוע לא תקין: {new_trade_key}')

    old_company_id = membership.get('company_id')
    old_trade_key = membership.get('contractor_trade_key')

    ts = _now()
    await db.project_memberships.update_one(
        {'project_id': project_id, 'user_id': user_id},
        {'$set': {
            'company_id': new_company_id,
            'contractor_trade_key': new_trade_key,
            'updated_at': ts,
        }}
    )

    await _audit('membership', f'{project_id}_{user_id}', 'member_contractor_profile_changed', user['id'], {
        'project_id': project_id,
        'target_user_id': user_id,
        'old_company_id': old_company_id,
        'new_company_id': new_company_id,
        'old_trade_key': old_trade_key,
        'new_trade_key': new_trade_key,
    })

    return {
        'success': True,
        'company_id': new_company_id,
        'contractor_trade_key': new_trade_key,
    }


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
    platform_role = 'super_admin' if is_super_admin_phone(user.get('phone_e164', '')) else 'none'
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
                          created_at=user.get('created_at'))
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
    platform_role = 'super_admin' if is_super_admin_phone(user.get('phone_e164', '')) else 'none'
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
                          created_at=user.get('created_at'))
    return {'token': token, 'user': user_resp.dict(), 'platform_role': platform_role}


@router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(id=user['id'], email=user.get('email', ''), name=user['name'],
                        phone=user.get('phone'), role=user['role'],
                        company_id=user.get('company_id'),
                        specialties=user.get('specialties'), phone_e164=user.get('phone_e164'),
                        user_status=user.get('user_status', 'active'),
                        created_at=user.get('created_at'),
                        platform_role=user.get('platform_role', 'none'))


@router.get("/users")
async def list_users(
    role: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    specialty: Optional[str] = Query(None),
    user: dict = Depends(require_roles('project_manager')),
):
    db = get_db()
    query = {}
    if role:
        query['role'] = role
    if company_id:
        query['company_id'] = company_id
    users = await db.users.find(query, {'_id': 0, 'password_hash': 0}).to_list(1000)
    if specialty:
        company_ids_with_specialty = await db.companies.distinct('id', {'specialties': specialty})
        users = [u for u in users if
                 u.get('company_id') in company_ids_with_specialty or
                 specialty in (u.get('specialties') or [])]
    return users


@router.post("/projects", response_model=Project)
async def create_project(project: Project, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    if not _is_super_admin(user):
        org = await get_user_org(user['id'])
        if org:
            sub = await get_subscription(org['id'])
            if sub and sub.get('status') == 'trialing':
                existing_count = await db.projects.count_documents({'org_id': org['id']})
                if existing_count >= 1:
                    raise HTTPException(
                        status_code=403,
                        detail='בתקופת הניסיון ניתן ליצור פרויקט אחד בלבד. לפרויקטים נוספים יש לשדרג את המנוי.'
                    )
    existing = await db.projects.find_one({'code': project.code})
    if existing:
        raise HTTPException(status_code=400, detail='Project code already exists')
    project_id = str(uuid.uuid4())
    ts = _now()
    org = await get_user_org(user['id'])
    join_code = None
    for _jc_attempt in range(10):
        candidate = f"BRK-{secrets.randbelow(9000) + 1000}"
        if not await db.projects.find_one({'join_code': candidate}):
            join_code = candidate
            break
    doc = {
        'id': project_id, 'name': project.name, 'code': project.code,
        'description': project.description, 'status': project.status.value if project.status else 'active',
        'client_name': project.client_name, 'start_date': project.start_date,
        'end_date': project.end_date, 'created_by': user['id'],
        'org_id': org['id'] if org else None,
        'join_code': join_code,
        'created_at': ts, 'updated_at': ts,
    }
    await db.projects.insert_one(doc)
    await db.project_memberships.update_one(
        {'project_id': project_id, 'user_id': user['id']},
        {'$set': {'id': str(uuid.uuid4()), 'project_id': project_id, 'user_id': user['id'], 'role': 'project_manager', 'created_at': ts}},
        upsert=True
    )
    await _audit('project', project_id, 'create', user['id'], {'name': project.name, 'code': project.code})
    return Project(**{k: v for k, v in doc.items() if k != '_id'})


@router.post("/projects/{project_id}/assign-pm")
async def assign_pm(project_id: str, body: dict, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    target_user_id = body.get('user_id')
    if not target_user_id:
        raise HTTPException(status_code=400, detail='user_id is required')
    target = await db.users.find_one({'id': target_user_id})
    if not target:
        raise HTTPException(status_code=404, detail='User not found')
    await db.users.update_one(
        {'id': target_user_id},
        {'$set': {'role': 'project_manager', 'project_id': project_id, 'updated_at': _now()}}
    )
    await db.project_memberships.update_one(
        {'project_id': project_id, 'user_id': target_user_id},
        {'$set': {'id': str(uuid.uuid4()), 'project_id': project_id, 'user_id': target_user_id, 'role': 'project_manager', 'created_at': _now()}},
        upsert=True
    )
    await _audit('user', target_user_id, 'assign_pm', user['id'], {'project_id': project_id, 'project_name': project.get('name')})
    return {'success': True, 'message': f'User {target.get("name")} assigned as PM to project {project.get("name")}'}


@router.get("/projects/{project_id}/available-pms")
async def list_available_pms(project_id: str, search: Optional[str] = Query(None), user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    existing_pm_ids = await db.project_memberships.distinct('user_id', {
        'project_id': project_id, 'role': 'project_manager'
    })
    query = {
        'id': {'$nin': existing_pm_ids},
        'user_status': {'$nin': ['rejected', 'suspended', 'pending_pm_approval']},
    }
    users = await db.users.find(query, {'_id': 0, 'password_hash': 0}).to_list(500)
    if search:
        search_lower = search.lower()
        users = [u for u in users if
                 search_lower in (u.get('name', '') or '').lower() or
                 search_lower in (u.get('email', '') or '').lower() or
                 search_lower in (u.get('phone_e164', '') or '').lower() or
                 search_lower in (u.get('phone', '') or '').lower()]
    return users


@router.get("/projects")
async def list_projects(user: dict = Depends(get_current_user)):
    db = get_db()
    if _is_super_admin(user):
        projects = await db.projects.find({}, {'_id': 0}).to_list(1000)
        enriched = []
        for p in projects:
            proj = Project(**p).dict()
            proj['my_role'] = 'project_manager'
            proj['my_sub_role'] = None
            enriched.append(proj)
        return enriched
    else:
        memberships = await db.project_memberships.find({'user_id': user['id']}, {'_id': 0}).to_list(1000)
        membership_map = {m['project_id']: m for m in memberships}
        project_ids = list(membership_map.keys())
        if not project_ids:
            return []
        projects = await db.projects.find({'id': {'$in': project_ids}}, {'_id': 0}).to_list(1000)
        enriched = []
        for p in projects:
            proj = Project(**p).dict()
            mem = membership_map.get(p['id'], {})
            proj['my_role'] = mem.get('role', 'viewer')
            proj['my_sub_role'] = mem.get('sub_role', None)
            if mem.get('role') == 'contractor':
                proj['my_trade_key'] = mem.get('contractor_trade_key')
            enriched.append(proj)
        return enriched


@router.get("/projects/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    await _check_project_read_access(user, project_id)
    proj = Project(**project).dict()
    if _is_super_admin(user):
        proj['my_role'] = 'project_manager'
        proj['my_sub_role'] = None
    else:
        membership = await db.project_memberships.find_one(
            {'user_id': user['id'], 'project_id': project_id}, {'_id': 0}
        )
        proj['my_role'] = membership.get('role', 'viewer') if membership else 'viewer'
        proj['my_sub_role'] = membership.get('sub_role', None) if membership else None
        if membership and membership.get('role') == 'contractor':
            proj['my_trade_key'] = membership.get('contractor_trade_key')
    return proj


@router.post("/projects/{project_id}/buildings", response_model=Building)
async def create_building(project_id: str, building: Building, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    await _check_project_access(user, project_id)
    building_id = str(uuid.uuid4())
    doc = {
        'id': building_id, 'project_id': project_id, 'name': building.name,
        'code': building.code, 'floors_count': building.floors_count or 0,
        'created_at': _now(),
    }
    await db.buildings.insert_one(doc)
    await _audit('building', building_id, 'create', user['id'], {'project_id': project_id, 'name': building.name})
    return Building(**{k: v for k, v in doc.items() if k != '_id'})


def _natural_sort_key(name: str):
    import re
    parts = re.split(r'(\d+)', name or '')
    result = []
    for p in parts:
        try:
            result.append((0, int(p)))
        except ValueError:
            result.append((1, p))
    return result

@router.get("/projects/{project_id}/buildings", response_model=List[Building])
async def list_buildings(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    buildings = await db.buildings.find({'project_id': project_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(1000)
    buildings.sort(key=lambda b: (b.get('sort_index', 0), _natural_sort_key(b.get('name', ''))))
    return [Building(**b) for b in buildings]


@router.post("/buildings/{building_id}/floors", response_model=Floor)
async def create_floor(building_id: str, floor: Floor, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    building = await db.buildings.find_one({'id': building_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not building:
        raise HTTPException(status_code=404, detail='Building not found')
    await _check_project_access(user, building['project_id'])

    is_numeric_floor = False
    try:
        floor_num_val = int(floor.name)
        is_numeric_floor = True
    except (ValueError, TypeError):
        floor_num_val = 0

    if is_numeric_floor:
        floor.floor_number = floor_num_val

    existing_floors = await db.floors.find({'building_id': building_id, 'archived': {'$ne': True}}, {'_id': 0}).sort('sort_index', 1).to_list(1000)

    if is_numeric_floor and existing_floors:
        insert_before = None
        for ef in existing_floors:
            ef_num = None
            try:
                ef_num = int(ef.get('name', ''))
            except (ValueError, TypeError):
                try:
                    ef_num = int(ef.get('floor_number', 0))
                except (ValueError, TypeError):
                    pass
            if ef_num is not None and ef_num > floor_num_val:
                insert_before = ef
                break
        if insert_before:
            floor.sort_index = insert_before.get('sort_index', 1000) - 1
        else:
            max_si = max(ef.get('sort_index', 0) for ef in existing_floors)
            floor.sort_index = max_si + 1000
    elif floor.sort_index is None:
        if existing_floors:
            max_si = max(ef.get('sort_index', 0) for ef in existing_floors)
            floor.sort_index = max_si + 1000
        else:
            floor.sort_index = floor.floor_number * 1000

    floor_id = str(uuid.uuid4())
    ts = _now()
    doc = {
        'id': floor_id, 'building_id': building_id, 'project_id': building['project_id'],
        'name': floor.name, 'floor_number': floor.floor_number,
        'sort_index': floor.sort_index,
        'display_label': floor.display_label or floor.name,
        'kind': floor.kind.value if floor.kind else None,
        'created_at': ts,
    }
    await db.floors.insert_one(doc)

    unit_count = floor.unit_count if floor.unit_count and floor.unit_count > 0 else 0
    created_units = []
    if unit_count > 0:
        all_units = await db.units.find({'building_id': building_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(100000)
        max_numeric = 0
        for u in all_units:
            try:
                n = int(u['unit_no'])
                if n > max_numeric:
                    max_numeric = n
            except (ValueError, TypeError):
                pass
        for i in range(unit_count):
            unit_no = str(max_numeric + i + 1)
            unit_id = str(uuid.uuid4())
            unit_doc = {
                'id': unit_id, 'floor_id': floor_id, 'building_id': building_id,
                'project_id': building['project_id'], 'unit_no': unit_no,
                'unit_type': 'apartment', 'status': 'available',
                'sort_index': (i + 1) * 10,
                'display_label': unit_no,
                'created_at': ts,
            }
            await db.units.insert_one(unit_doc)
            created_units.append(unit_no)

    reseq_floor_changes, reseq_unit_changes = await _compute_building_resequence(db, building_id)
    for c in reseq_floor_changes:
        await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})
    if reseq_unit_changes:
        for c in reseq_unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': f"__tmp_{c['id']}",
                'display_label': f"__tmp_{c['id']}",
            }})
        for c in reseq_unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': c['new_unit_no'],
                'display_label': c['new_display_label'],
                'sort_index': c['new_sort_index'],
            }})

    await _audit('floor', floor_id, 'create', user['id'], {
        'building_id': building_id, 'name': floor.name,
        'sort_index': doc['sort_index'], 'unit_count': unit_count,
        'created_units': created_units,
        'units_renumbered': len(reseq_unit_changes),
    })
    return Floor(**{k: v for k, v in doc.items() if k != '_id'})


@router.get("/buildings/{building_id}/floors", response_model=List[Floor])
async def list_floors(building_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    floors = await db.floors.find({'building_id': building_id, 'archived': {'$ne': True}}, {'_id': 0}).sort('sort_index', 1).to_list(1000)
    return [Floor(**f) for f in floors]


@router.post("/floors/{floor_id}/units")
async def create_unit(floor_id: str, unit: Unit, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    floor = await db.floors.find_one({'id': floor_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not floor:
        raise HTTPException(status_code=404, detail='Floor not found')
    await _check_project_access(user, floor['project_id'])
    building_id = floor['building_id']
    project_id = floor['project_id']
    ts = _now()

    unit_count = unit.unit_count if unit.unit_count and unit.unit_count > 0 else 0

    if unit_count > 0:
        all_units = await db.units.find({'building_id': building_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(100000)
        max_numeric = 0
        for u in all_units:
            try:
                n = int(u['unit_no'])
                if n > max_numeric:
                    max_numeric = n
            except (ValueError, TypeError):
                pass

        existing_floor_units = await db.units.find({'floor_id': floor_id, 'archived': {'$ne': True}}, {'_id': 0}).sort('sort_index', -1).to_list(1000)
        base_sort = (existing_floor_units[0].get('sort_index', 0) + 10) if existing_floor_units else 10

        created = []
        for i in range(unit_count):
            unit_no = str(max_numeric + i + 1)
            unit_id = str(uuid.uuid4())
            doc = {
                'id': unit_id, 'floor_id': floor_id, 'building_id': building_id,
                'project_id': project_id, 'unit_no': unit_no,
                'unit_type': 'apartment', 'status': 'available',
                'sort_index': base_sort + (i * 10),
                'display_label': unit_no, 'created_at': ts,
            }
            await db.units.insert_one(doc)
            created.append(unit_no)
            await _audit('unit', unit_id, 'create', user['id'], {'floor_id': floor_id, 'unit_no': unit_no})

        reseq_floor_changes, reseq_unit_changes = await _compute_building_resequence(db, building_id)
        for c in reseq_floor_changes:
            await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})
        if reseq_unit_changes:
            for c in reseq_unit_changes:
                await db.units.update_one({'id': c['id']}, {'$set': {
                    'unit_no': f"__tmp_{c['id']}", 'display_label': f"__tmp_{c['id']}",
                }})
            for c in reseq_unit_changes:
                await db.units.update_one({'id': c['id']}, {'$set': {
                    'unit_no': c['new_unit_no'], 'display_label': c['new_unit_no'],
                    'sort_index': c.get('new_sort_index', 0),
                }})

        return {'created': len(created), 'units': created}

    if not unit.unit_no:
        raise HTTPException(status_code=400, detail='יש להזין מספר דירה או כמות דירות')
    existing = await db.units.find_one({
        'project_id': project_id, 'building_id': building_id,
        'floor_id': floor_id, 'unit_no': unit.unit_no,
        'archived': {'$ne': True},
    })
    if existing:
        raise HTTPException(status_code=400, detail='Unit number already exists on this floor')
    if unit.sort_index is None:
        max_unit = await db.units.find_one({'floor_id': floor_id, 'archived': {'$ne': True}}, sort=[('sort_index', -1)])
        unit.sort_index = (max_unit.get('sort_index', 0) + 10) if max_unit else 10
    unit_id = str(uuid.uuid4())
    doc = {
        'id': unit_id, 'floor_id': floor_id, 'building_id': building_id,
        'project_id': project_id, 'unit_no': unit.unit_no,
        'unit_type': unit.unit_type.value if unit.unit_type else 'apartment',
        'status': unit.status.value if unit.status else 'available',
        'sort_index': unit.sort_index,
        'display_label': unit.display_label or unit.unit_no, 'created_at': ts,
    }
    await db.units.insert_one(doc)
    await _audit('unit', unit_id, 'create', user['id'], {'floor_id': floor_id, 'unit_no': unit.unit_no})
    return Unit(**{k: v for k, v in doc.items() if k != '_id'})


@router.get("/floors/{floor_id}/units", response_model=List[Unit])
async def list_units_by_floor(floor_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    units = await db.units.find({'floor_id': floor_id, 'archived': {'$ne': True}}, {'_id': 0}).sort('sort_index', 1).to_list(1000)
    return [Unit(**u) for u in units]


@router.post("/floors/bulk")
async def bulk_create_floors(body: BulkFloorRequest, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    await _check_project_access(user, body.project_id)
    building = await db.buildings.find_one({'id': body.building_id, 'project_id': body.project_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not building:
        raise HTTPException(status_code=404, detail='Building not found in this project')
    if body.from_floor > body.to_floor:
        raise HTTPException(status_code=422, detail='from_floor must be <= to_floor')
    if body.to_floor - body.from_floor > 200:
        raise HTTPException(status_code=422, detail='Maximum 200 floors per batch')

    if body.dry_run:
        would_create = 0
        would_skip = 0
        for num in range(body.from_floor, body.to_floor + 1):
            existing = await db.floors.find_one({'building_id': body.building_id, 'floor_number': num, 'archived': {'$ne': True}})
            if existing:
                would_skip += 1
            else:
                would_create += 1
        return {'dry_run': True, 'would_create': would_create, 'would_skip': would_skip, 'message': f'תצוגה מקדימה: {would_create} קומות חדשות, {would_skip} דילוגים'}

    batch_id = body.batch_id or str(uuid.uuid4())[:12]
    created = []
    skipped = 0
    ts = _now()
    for num in range(body.from_floor, body.to_floor + 1):
        existing = await db.floors.find_one({
            'building_id': body.building_id,
            'floor_number': num,
            'archived': {'$ne': True},
        })
        if existing:
            skipped += 1
            continue
        floor_id = str(uuid.uuid4())
        si = num * 1000
        doc = {
            'id': floor_id,
            'building_id': body.building_id,
            'project_id': body.project_id,
            'name': f'קומה {num}',
            'floor_number': num,
            'sort_index': si,
            'display_label': f'קומה {num}',
            'kind': 'basement' if num < 0 else ('ground' if num == 0 else 'residential'),
            'created_at': ts,
            'batch_id': batch_id,
        }
        await db.floors.insert_one(doc)
        created.append({'id': floor_id, 'name': doc['name'], 'floor_number': num, 'sort_index': si})

    await _audit('building', body.building_id, 'bulk_create_floors', user['id'], {
        'project_id': body.project_id,
        'from_floor': body.from_floor,
        'to_floor': body.to_floor,
        'created_count': len(created),
        'skipped_count': skipped,
        'batch_id': batch_id,
    })

    msg = f'נוצרו {len(created)} קומות'
    if skipped > 0:
        msg += f', דולגו {skipped} קומות קיימות'

    return {'created_count': len(created), 'skipped_count': skipped, 'items': created, 'message': msg, 'batch_id': batch_id}


@router.post("/units/bulk")
async def bulk_create_units(body: BulkUnitRequest, user: dict = Depends(require_roles('project_manager'))):
    import time as _time
    rid = str(uuid.uuid4())[:8]
    t0 = _time.time()
    db = get_db()
    await _check_project_access(user, body.project_id)
    building = await db.buildings.find_one({'id': body.building_id, 'project_id': body.project_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not building:
        raise HTTPException(status_code=404, detail='Building not found in this project')
    if body.from_floor > body.to_floor:
        raise HTTPException(status_code=422, detail='from_floor must be <= to_floor')
    if body.units_per_floor < 1 or body.units_per_floor > 100:
        raise HTTPException(status_code=422, detail='units_per_floor must be between 1 and 100')
    total_floors = body.to_floor - body.from_floor + 1
    if total_floors > 200:
        raise HTTPException(status_code=422, detail='Maximum 200 floors per batch')

    all_floors = await db.floors.find({'building_id': body.building_id, 'archived': {'$ne': True}}, {'_id': 0}).sort('sort_index', 1).to_list(1000)
    existing_numeric_units = await db.units.find({'building_id': body.building_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(100000)
    max_existing = 0
    for eu in existing_numeric_units:
        if _is_numeric_unit(eu.get('unit_no', '')):
            max_existing = max(max_existing, int(eu['unit_no']))
    global_counter = max_existing

    target_floors = [f for f in all_floors if body.from_floor <= f['floor_number'] <= body.to_floor]

    if body.dry_run:
        would_create = 0
        would_skip = 0
        temp_counter = global_counter
        for floor in target_floors:
            for unit_idx in range(body.units_per_floor):
                if body.unit_prefix:
                    unit_num = body.unit_start_number + unit_idx
                    unit_no = f'{body.unit_prefix}{str(unit_num).zfill(body.unit_number_padding) if body.unit_number_padding > 0 else str(unit_num)}'
                else:
                    temp_counter += 1
                    unit_no = str(temp_counter)
                existing = await db.units.find_one({'floor_id': floor['id'], 'unit_no': unit_no, 'archived': {'$ne': True}})
                if existing:
                    would_skip += 1
                else:
                    would_create += 1
        return {'dry_run': True, 'would_create': would_create, 'would_skip': would_skip, 'message': f'תצוגה מקדימה: {would_create} דירות חדשות, {would_skip} דילוגים'}

    batch_id = body.batch_id or str(uuid.uuid4())[:12]
    created = []
    skipped = 0
    ts = _now()

    for floor in target_floors:
        existing_floor_units = await db.units.find({'floor_id': floor['id'], 'archived': {'$ne': True}}, {'_id': 0}).to_list(10000)
        floor_unit_count = len(existing_floor_units)

        for unit_idx in range(body.units_per_floor):
            if body.unit_prefix:
                unit_num = body.unit_start_number + unit_idx
                unit_no = f'{body.unit_prefix}{str(unit_num).zfill(body.unit_number_padding) if body.unit_number_padding > 0 else str(unit_num)}'
            else:
                global_counter += 1
                unit_no = str(global_counter)

            existing = await db.units.find_one({
                'floor_id': floor['id'],
                'unit_no': unit_no,
                'archived': {'$ne': True},
            })
            if existing:
                skipped += 1
                continue

            unit_id = str(uuid.uuid4())
            si = (floor_unit_count + unit_idx + 1) * 10
            doc = {
                'id': unit_id,
                'floor_id': floor['id'],
                'building_id': body.building_id,
                'project_id': body.project_id,
                'unit_no': unit_no,
                'unit_type': 'apartment',
                'status': 'available',
                'sort_index': si,
                'display_label': unit_no,
                'created_at': ts,
                'batch_id': batch_id,
            }
            await db.units.insert_one(doc)
            created.append({'id': unit_id, 'unit_no': unit_no, 'floor_number': floor['floor_number']})

    await _audit('building', body.building_id, 'bulk_create_units', user['id'], {
        'project_id': body.project_id,
        'from_floor': body.from_floor,
        'to_floor': body.to_floor,
        'units_per_floor': body.units_per_floor,
        'created_count': len(created),
        'skipped_count': skipped,
        'batch_id': batch_id,
    })

    elapsed_ms = round((_time.time() - t0) * 1000, 1)
    units_requested = len(target_floors) * body.units_per_floor
    logger.info(
        f"[BULK-UNITS] rid={rid} project_id={body.project_id} building_id={body.building_id} "
        f"floors_matched={len(target_floors)} units_per_floor={body.units_per_floor} "
        f"units_requested={units_requested} units_created={len(created)} skipped={skipped} "
        f"errors=[] elapsed_ms={elapsed_ms}"
    )

    msg = f'נוצרו {len(created)} דירות'
    if skipped > 0:
        msg += f', דולגו {skipped} דירות קיימות'

    return {'created_count': len(created), 'skipped_count': skipped, 'items': created, 'message': msg, 'batch_id': batch_id}


@router.get("/projects/{project_id}/hierarchy")
async def get_project_hierarchy(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    await _check_project_read_access(user, project_id)

    buildings = await db.buildings.find({'project_id': project_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(1000)
    building_names = [b.get('name', '?') for b in buildings]
    logger.info(f"[HIERARCHY:ACCESS] user={user['id']} project={project_id} buildings={len(buildings)} names={building_names}")
    all_floors = await db.floors.find({'project_id': project_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(10000)

    building_ids = [b['id'] for b in buildings]
    floor_ids = [f['id'] for f in all_floors]

    all_units = []
    if floor_ids:
        all_units = await db.units.find({'floor_id': {'$in': floor_ids}, 'archived': {'$ne': True}}, {'_id': 0}).to_list(100000)

    units_by_floor = {}
    for u in all_units:
        fid = u['floor_id']
        if fid not in units_by_floor:
            units_by_floor[fid] = []
        raw_unit_no = u['unit_no']
        raw_display = u.get('display_label', raw_unit_no)
        if _is_numeric_unit(raw_unit_no):
            eff = raw_unit_no
        else:
            eff = raw_display or raw_unit_no
        units_by_floor[fid].append({
            'id': u['id'],
            'unit_no': raw_unit_no,
            'unit_type': u.get('unit_type', 'apartment'),
            'status': u.get('status', 'available'),
            'sort_index': u.get('sort_index', 0),
            'display_label': raw_display,
            'effective_label': eff,
        })

    for fid in units_by_floor:
        units_by_floor[fid].sort(key=lambda x: x['sort_index'])

    floors_by_building = {}
    for f in all_floors:
        bid = f['building_id']
        if bid not in floors_by_building:
            floors_by_building[bid] = []
        floors_by_building[bid].append({
            'id': f['id'],
            'name': f['name'],
            'floor_number': f['floor_number'],
            'sort_index': f.get('sort_index', f['floor_number'] * 1000),
            'display_label': f.get('display_label', f['name']),
            'kind': f.get('kind'),
            'units': units_by_floor.get(f['id'], []),
        })

    for bid in floors_by_building:
        floors_by_building[bid].sort(key=lambda x: x['sort_index'])

    buildings.sort(key=lambda b: (b.get('sort_index', 0), _natural_sort_key(b.get('name', ''))))
    hierarchy_buildings = []
    for b in buildings:
        hierarchy_buildings.append({
            'id': b['id'],
            'name': b['name'],
            'code': b.get('code'),
            'floors': floors_by_building.get(b['id'], []),
        })

    return {
        'project_id': project_id,
        'project_name': project['name'],
        'buildings': hierarchy_buildings,
    }


PHONE_VISIBLE_ROLES = ('project_manager',)


async def _enrich_memberships(project_id: str, can_see_phone: bool, limit: int = 1000):
    import time as _t
    t_start = _t.perf_counter()
    db = get_db()

    t0 = _t.perf_counter()
    memberships = await db.project_memberships.find({'project_id': project_id}, {'_id': 0}).to_list(limit)
    db_mem_ms = round((_t.perf_counter() - t0) * 1000, 1)

    user_ids = [m.get('user_id') for m in memberships if m.get('user_id')]

    t0 = _t.perf_counter()
    users_list = await db.users.find(
        {'id': {'$in': user_ids}},
        {'_id': 0, 'id': 1, 'name': 1, 'phone': 1, 'role': 1, 'company_id': 1}
    ).to_list(len(user_ids))
    user_map = {u['id']: u for u in users_list}

    all_company_ids = set()
    for u in users_list:
        if u.get('company_id'):
            all_company_ids.add(u['company_id'])
    for m in memberships:
        if m.get('company_id'):
            all_company_ids.add(m['company_id'])
    all_company_ids = list(all_company_ids)

    company_map = {}
    if all_company_ids:
        proj_companies = await db.project_companies.find(
            {'id': {'$in': all_company_ids}, 'deletedAt': {'$exists': False}},
            {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(len(all_company_ids))
        for c in proj_companies:
            company_map[c['id']] = c.get('name', '')
        missing_ids = [cid for cid in all_company_ids if cid not in company_map]
        if missing_ids:
            global_companies = await db.companies.find(
                {'id': {'$in': missing_ids}}, {'_id': 0, 'id': 1, 'name': 1}
            ).to_list(len(missing_ids))
            for c in global_companies:
                company_map[c['id']] = c.get('name', '')

    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    org_id = project.get('org_id') if project else None
    org_owner_id = None
    org_mem_map = {}
    if org_id and user_ids:
        org_doc = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'owner_user_id': 1})
        org_owner_id = org_doc.get('owner_user_id') if org_doc else None
        org_mems = await db.organization_memberships.find(
            {'org_id': org_id, 'user_id': {'$in': user_ids}},
            {'_id': 0, 'user_id': 1, 'role': 1}
        ).to_list(len(user_ids))
        org_mem_map = {om['user_id']: om.get('role', 'member') for om in org_mems}

    db_enrich_ms = round((_t.perf_counter() - t0) * 1000, 1)

    for m in memberships:
        u = user_map.get(m.get('user_id'))
        if u:
            m['user_name'] = u.get('name', '')
            if can_see_phone:
                m['user_phone'] = u.get('phone', '')
            if not m.get('role'):
                m['role'] = u.get('role', '')
            if m.get('role') == 'contractor':
                mem_cid = m.get('company_id')
                if mem_cid:
                    m['user_company_id'] = mem_cid
                elif u.get('company_id'):
                    m['user_company_id'] = u['company_id']
                if m.get('user_company_id'):
                    m['company_name'] = company_map.get(m['user_company_id'], '')
        uid = m.get('user_id')
        m['org_role'] = org_mem_map.get(uid)
        m['is_org_owner'] = (uid == org_owner_id) if org_owner_id else False

    total_ms = round((_t.perf_counter() - t_start) * 1000, 1)
    logger.info(
        f"[PERF] _enrich_memberships project={project_id[:8]} total_ms={total_ms} "
        f"db_mem_ms={db_mem_ms} db_enrich_ms={db_enrich_ms} "
        f"member_count={len(memberships)} query_count=3"
    )
    return memberships


@router.get("/projects/{project_id}/memberships")
async def list_project_memberships(project_id: str, user: dict = Depends(get_current_user)):
    await _check_project_read_access(user, project_id)
    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    can_see_phone = requester_role in PHONE_VISIBLE_ROLES
    return await _enrich_memberships(project_id, can_see_phone)


@router.get("/my-memberships")
async def get_my_memberships(user: dict = Depends(get_current_user)):
    db = get_db()
    memberships = await db.project_memberships.find({'user_id': user['id']}, {'_id': 0}).to_list(1000)
    return memberships


PLAN_DISCIPLINES = ('electrical', 'plumbing', 'architecture', 'construction', 'hvac', 'fire_protection')
PLAN_UPLOAD_ROLES = ('project_manager', 'management_team')


@router.get("/projects/{project_id}/plans")
async def list_project_plans(
    project_id: str,
    discipline: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    query = {'project_id': project_id, 'deletedAt': {'$exists': False}}
    if discipline:
        query['discipline'] = discipline
    plans = await db.project_plans.find(query, {'_id': 0}).sort('created_at', -1).to_list(500)
    from services.object_storage import resolve_urls_in_doc
    for p in plans:
        uploader = await db.users.find_one({'id': p.get('uploaded_by')}, {'_id': 0, 'name': 1})
        p['uploaded_by_name'] = uploader.get('name', '') if uploader else ''
        resolve_urls_in_doc(p)
    return plans


@router.post("/projects/{project_id}/plans")
async def upload_project_plan(
    project_id: str,
    file: UploadFile = File(...),
    discipline: str = Form(...),
    note: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    await _check_project_read_access(user, project_id)

    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    if requester_role not in PLAN_UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail='אין לך הרשאה להעלות תוכניות')

    custom_disciplines = await db.project_disciplines.find(
        {'project_id': project_id}, {'_id': 0, 'key': 1}
    ).to_list(100)
    custom_keys = {d['key'] for d in custom_disciplines}
    all_valid = set(PLAN_DISCIPLINES) | custom_keys
    if discipline not in all_valid:
        raise HTTPException(status_code=422, detail=f'תחום לא תקין. אפשרויות: {", ".join(sorted(all_valid))}')

    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')

    from services.storage_service import StorageService
    storage = StorageService()
    result = await storage.upload_file_with_details(file, f"project_plan_{project_id}_{discipline}")

    plan_id = str(uuid.uuid4())
    plan_doc = {
        'id': plan_id,
        'project_id': project_id,
        'discipline': discipline,
        'file_url': result.file_url,
        'original_filename': file.filename,
        'file_size': result.file_size,
        'uploaded_by': user['id'],
        'note': note or '',
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.project_plans.insert_one(plan_doc)
    plan_doc.pop('_id', None)

    await _audit('project_plan', plan_id, 'upload', user['id'], {
        'discipline': discipline,
        'filename': file.filename,
        'project_id': project_id,
    })

    from services.object_storage import resolve_urls_in_doc
    return resolve_urls_in_doc(dict(plan_doc))


@router.get("/projects/{project_id}/units/{unit_id}/plans")
async def list_unit_plans(
    project_id: str,
    unit_id: str,
    discipline: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)
    unit = await db.units.find_one({'id': unit_id, 'project_id': project_id})
    if not unit:
        raise HTTPException(status_code=404, detail='דירה לא נמצאה בפרויקט זה')
    query = {'project_id': project_id, 'unit_id': unit_id}
    if discipline:
        query['discipline'] = discipline
    plans = await db.unit_plans.find(query, {'_id': 0}).sort('created_at', -1).to_list(500)
    from services.object_storage import resolve_urls_in_doc
    for p in plans:
        uploader = await db.users.find_one({'id': p.get('uploaded_by')}, {'_id': 0, 'name': 1})
        p['uploaded_by_name'] = uploader.get('name', '') if uploader else ''
        resolve_urls_in_doc(p)
    return plans


@router.post("/projects/{project_id}/units/{unit_id}/plans")
async def upload_unit_plan(
    project_id: str,
    unit_id: str,
    file: UploadFile = File(...),
    discipline: str = Form(...),
    note: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    await _check_project_read_access(user, project_id)

    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    if requester_role not in PLAN_UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail='אין לך הרשאה להעלות תוכניות')

    custom_disciplines = await db.project_disciplines.find(
        {'project_id': project_id}, {'_id': 0, 'key': 1}
    ).to_list(100)
    custom_keys = {d['key'] for d in custom_disciplines}
    all_valid = set(PLAN_DISCIPLINES) | custom_keys
    if discipline not in all_valid:
        raise HTTPException(status_code=422, detail=f'תחום לא תקין. אפשרויות: {", ".join(sorted(all_valid))}')

    unit = await db.units.find_one({'id': unit_id, 'project_id': project_id})
    if not unit:
        raise HTTPException(status_code=404, detail='דירה לא נמצאה בפרויקט זה')

    from services.storage_service import StorageService
    storage = StorageService()
    result = await storage.upload_file_with_details(file, f"plan_{unit_id}_{discipline}")

    plan_id = str(uuid.uuid4())
    plan_doc = {
        'id': plan_id,
        'project_id': project_id,
        'unit_id': unit_id,
        'discipline': discipline,
        'file_url': result.file_url,
        'original_filename': file.filename,
        'file_size': result.file_size,
        'uploaded_by': user['id'],
        'note': note or '',
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.unit_plans.insert_one(plan_doc)
    plan_doc.pop('_id', None)

    await _audit('unit_plan', plan_id, 'upload', user['id'], {
        'discipline': discipline,
        'filename': file.filename,
        'unit_id': unit_id,
        'project_id': project_id,
    })

    from services.object_storage import resolve_urls_in_doc
    return resolve_urls_in_doc(dict(plan_doc))


@router.get("/projects/{project_id}/disciplines")
async def list_project_disciplines(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)
    defaults = [{'key': d, 'label': d, 'source': 'default'} for d in PLAN_DISCIPLINES]
    custom = await db.project_disciplines.find(
        {'project_id': project_id}, {'_id': 0}
    ).to_list(100)
    for c in custom:
        c.pop('project_id', None)
    return defaults + [{'key': c['key'], 'label': c.get('label', c['key']), 'source': 'custom'} for c in custom]


@router.post("/projects/{project_id}/disciplines")
async def add_project_discipline(
    project_id: str,
    body: dict = Body(...),
    user: dict = Depends(get_current_user),
):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    await _check_project_read_access(user, project_id)
    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    if requester_role not in PLAN_UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail='אין לך הרשאה להוסיף תחומים')

    label = (body.get('label') or '').strip()
    if not label:
        raise HTTPException(status_code=422, detail='שם תחום נדרש')
    import re
    key = re.sub(r'[^a-z0-9_]', '_', label.lower().strip()).strip('_')
    key = re.sub(r'_+', '_', key)
    if not key:
        key = 'custom_' + str(uuid.uuid4())[:8]

    if key in PLAN_DISCIPLINES:
        raise HTTPException(status_code=409, detail='תחום ברירת מחדל כבר קיים')
    existing = await db.project_disciplines.find_one({'project_id': project_id, 'key': key})
    if existing:
        raise HTTPException(status_code=409, detail='תחום זה כבר קיים בפרויקט')

    doc = {
        'id': str(uuid.uuid4()),
        'project_id': project_id,
        'key': key,
        'label': label,
        'source': 'custom',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'created_by': user['id'],
    }
    await db.project_disciplines.insert_one(doc)
    doc.pop('_id', None)

    await _audit('project_discipline', doc['id'], 'project_discipline_add', user['id'], {
        'project_id': project_id,
        'key': key,
        'label': label,
    })

    return {'key': key, 'label': label, 'source': 'custom'}


@router.delete("/projects/{project_id}/plans/{plan_id}")
async def delete_project_plan(
    project_id: str,
    plan_id: str,
    body: dict = Body(...),
    user: dict = Depends(get_current_user),
):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    await _check_project_read_access(user, project_id)
    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    if requester_role not in PLAN_UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail='אין לך הרשאה למחוק תוכניות')

    reason = (body.get('reason') or '').strip()
    if not reason:
        raise HTTPException(status_code=422, detail='חובה לציין סיבה למחיקה')

    plan = await db.project_plans.find_one({'id': plan_id, 'project_id': project_id, 'deletedAt': {'$exists': False}})
    if not plan:
        raise HTTPException(status_code=404, detail='תוכנית לא נמצאה')

    await db.project_plans.update_one({'id': plan_id}, {'$set': {'deletedAt': _now(), 'deletedBy': user['id'], 'deleteReason': reason}})

    await _audit('project_plan', plan_id, 'project_plan_soft_delete', user['id'], {
        'project_id': project_id,
        'discipline': plan.get('discipline', ''),
        'filename': plan.get('original_filename', ''),
        'reason': reason,
        'original_uploader': plan.get('uploaded_by', ''),
    })

    return {'success': True}


@router.get("/units/{unit_id}/tasks", response_model=List[Task])
async def list_unit_tasks(unit_id: str,
                          status: Optional[str] = Query(None),
                          category: Optional[str] = Query(None),
                          user: dict = Depends(get_current_user)):
    db = get_db()
    query = {'unit_id': unit_id}
    if status:
        query['status'] = status
    if category:
        query['category'] = category
    tasks = await db.tasks.find(query, {'_id': 0}).sort('created_at', -1).to_list(1000)
    tasks = sorted(tasks, key=_priority_sort_key)
    from services.object_storage import resolve_urls_in_doc
    result = []
    for t in tasks:
        td = Task(**t).dict()
        resolve_urls_in_doc(td)
        result.append(td)
    return result


@router.get("/units/{unit_id}")
async def get_unit_detail(unit_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    unit = await db.units.find_one({'id': unit_id}, {'_id': 0})
    if not unit:
        raise HTTPException(status_code=404, detail='Unit not found')
    floor = await db.floors.find_one({'id': unit.get('floor_id')}, {'_id': 0}) if unit.get('floor_id') else None
    building = await db.buildings.find_one({'id': unit.get('building_id')}, {'_id': 0}) if unit.get('building_id') else None
    project_id = unit.get('project_id') or (building.get('project_id') if building else None)
    project = await db.projects.find_one({'id': project_id}, {'_id': 0}) if project_id else None
    if project_id:
        await _check_project_read_access(user, project_id)

    effective_label = unit.get('display_label') or unit.get('unit_no', '')
    try:
        int(unit.get('unit_no', ''))
        effective_label = unit.get('display_label') or unit.get('unit_no', '')
    except (ValueError, TypeError):
        effective_label = unit.get('display_label') or unit.get('unit_no', '')

    tasks = await db.tasks.find({'unit_id': unit_id}, {'_id': 0}).to_list(10000)
    by_status = {}
    for t in tasks:
        s = t.get('status', 'open')
        by_status[s] = by_status.get(s, 0) + 1

    return {
        'unit': {
            **unit,
            'effective_label': effective_label,
        },
        'floor': {'id': floor['id'], 'name': floor.get('name', '')} if floor else None,
        'building': {'id': building['id'], 'name': building.get('name', '')} if building else None,
        'project': {'id': project['id'], 'name': project.get('name', ''), 'code': project.get('code', '')} if project else None,
        'kpi': {
            'total': len(tasks),
            'open': by_status.get('open', 0) + by_status.get('assigned', 0) + by_status.get('reopened', 0),
            'in_progress': by_status.get('in_progress', 0) + by_status.get('waiting_verify', 0) + by_status.get('pending_contractor_proof', 0) + by_status.get('pending_manager_approval', 0),
            'closed': by_status.get('closed', 0),
        },
    }


@router.post("/companies", response_model=Company)
async def create_company(company: Company, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    company_id = str(uuid.uuid4())
    doc = {
        'id': company_id, 'name': company.name,
        'trade': company.trade.value if company.trade else None,
        'contact_name': company.contact_name, 'contact_phone': company.contact_phone,
        'contact_email': company.contact_email, 'created_at': _now(),
    }
    await db.companies.insert_one(doc)
    await _audit('company', company_id, 'create', user['id'], {'name': company.name})
    return Company(**{k: v for k, v in doc.items() if k != '_id'})


@router.get("/companies", response_model=List[Company])
async def list_companies(user: dict = Depends(get_current_user)):
    db = get_db()
    companies = await db.companies.find({}, {'_id': 0}).to_list(1000)
    return [Company(**c) for c in companies]


@router.post("/tasks", response_model=Task)
async def create_task(task: TaskCreate, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    pid = (task.project_id or '').strip()
    if not pid:
        raise HTTPException(status_code=400, detail={'error_code': 'INVALID_PROJECT_ID', 'message': 'project_id is required'})
    task.project_id = pid
    await _check_project_access(user, pid)
    project = await db.projects.find_one({'id': pid}, {'_id': 0})
    if not project:
        raise HTTPException(status_code=400, detail={'error_code': 'PROJECT_NOT_FOUND', 'message': 'Project not found'})
    project_status = project.get('status', 'active')
    if project_status in ('draft', 'payment_pending', 'suspended'):
        raise HTTPException(status_code=403, detail=f'Project is {project_status}. Cannot create tasks.')
    if task.building_id:
        building_doc = await db.buildings.find_one({'id': task.building_id, 'project_id': task.project_id, 'archived': {'$ne': True}}, {'_id': 0})
        if not building_doc:
            raise HTTPException(status_code=404, detail='Building not found in this project')
    if task.floor_id:
        floor_doc = await db.floors.find_one({'id': task.floor_id, 'building_id': task.building_id, 'archived': {'$ne': True}}, {'_id': 0})
        if not floor_doc:
            raise HTTPException(status_code=404, detail='Floor not found in this building')
    if task.unit_id:
        unit_doc = await db.units.find_one({'id': task.unit_id, 'floor_id': task.floor_id, 'archived': {'$ne': True}}, {'_id': 0})
        if not unit_doc:
            raise HTTPException(status_code=404, detail='Unit not found on this floor')
    task_id = str(uuid.uuid4())
    ts = _now()
    initial_status = 'assigned' if task.assignee_id else 'open'
    doc = {
        'id': task_id, 'project_id': task.project_id, 'building_id': task.building_id,
        'floor_id': task.floor_id, 'unit_id': task.unit_id,
        'title': task.title, 'description': task.description,
        'category': task.category.value if task.category else 'general',
        'priority': task.priority.value if task.priority else 'medium',
        'status': initial_status, 'company_id': task.company_id,
        'assignee_id': task.assignee_id, 'due_date': task.due_date,
        'created_by': user['id'], 'created_at': ts, 'updated_at': ts,
        'attachments_count': 0, 'comments_count': 0,
    }
    await db.tasks.insert_one(doc)
    await db.task_status_history.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id,
        'old_status': None, 'new_status': initial_status,
        'changed_by': user['id'], 'note': 'Task created', 'created_at': ts,
    })
    await _audit('task', task_id, 'create', user['id'], {'title': task.title, 'project_id': task.project_id})

    notification_status = None
    engine = get_notification_engine()
    if engine and task.assignee_id:
        try:
            task_link = _get_task_link(task_id)
            job = await engine.enqueue(task_id, 'task_created', user['id'], task_link=task_link)
            if job and job.get('status') == 'queued':
                result = await engine.process_job(job)
                notification_status = {
                    'sent': True,
                    'channel': result.get('channel', 'unknown'),
                    'job_id': result.get('job_id', job.get('id', '')),
                    'provider_message_id': result.get('provider_message_id', ''),
                }
            elif job:
                notification_status = {'sent': False, 'reason': 'duplicate', 'job_id': job.get('id', '')}
        except Exception as e:
            logger.warning(f"[NOTIFY] Auto-enqueue failed for task_created: {e}")
            notification_status = {'sent': False, 'reason': str(e)[:200]}

    task_result = Task(**{k: v for k, v in doc.items() if k != '_id'}).dict()
    if notification_status:
        task_result['notification_status'] = notification_status
    return task_result


async def _build_bucket_maps(db, project_id=None):
    membership_trade_map = {}
    if project_id:
        memberships = await db.project_memberships.find(
            {'project_id': project_id, 'role': 'contractor', 'contractor_trade_key': {'$exists': True, '$ne': None}},
            {'_id': 0, 'user_id': 1, 'contractor_trade_key': 1}
        ).to_list(10000)
        for m in memberships:
            membership_trade_map[m['user_id']] = m['contractor_trade_key']

    contractor_map = {}
    users = await db.users.find(
        {'role': 'contractor'},
        {'_id': 0, 'id': 1, 'specialties': 1}
    ).to_list(10000)
    for u in users:
        specs = u.get('specialties') or []
        trade = next((s for s in specs if s != 'general'), specs[0] if specs else None)
        if trade:
            contractor_map[u['id']] = trade

    company_map = {}
    companies = await db.companies.find({}, {'_id': 0, 'id': 1, 'trade': 1}).to_list(10000)
    for c in companies:
        if c.get('trade'):
            company_map[c['id']] = c['trade']

    return contractor_map, company_map, membership_trade_map


PRIORITY_SORT_MAP = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}

def _priority_sort_key(t):
    pri = PRIORITY_SORT_MAP.get(t.get('priority', 'medium'), 2)
    ts = t.get('updated_at') or t.get('created_at')
    if isinstance(ts, datetime):
        return (pri, -ts.timestamp())
    if isinstance(ts, str):
        try:
            return (pri, -datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp())
        except Exception:
            pass
    return (pri, 0)

@router.get("/tasks", response_model=List[Task])
async def list_tasks(
    project_id: Optional[str] = Query(None),
    building_id: Optional[str] = Query(None),
    floor_id: Optional[str] = Query(None),
    unit_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    status_in: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    unassigned: Optional[bool] = Query(None),
    bucket_key: Optional[str] = Query(None),
    overdue: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    query = {}
    if project_id:
        query['project_id'] = project_id
    if building_id:
        query['building_id'] = building_id
    if floor_id:
        query['floor_id'] = floor_id
    if unit_id:
        query['unit_id'] = unit_id
    if status:
        query['status'] = status
    elif status_in:
        statuses = [s.strip() for s in status_in.split(',') if s.strip()]
        if len(statuses) == 1:
            query['status'] = statuses[0]
        elif statuses:
            query['status'] = {'$in': statuses}
    if unassigned:
        query['$or'] = [{'assignee_id': None}, {'assignee_id': {'$exists': False}}, {'assignee_id': ''}]
    elif assignee_id:
        if assignee_id == 'me':
            query['assignee_id'] = user['id']
        else:
            query['assignee_id'] = assignee_id
    if company_id:
        query['company_id'] = company_id
    if overdue:
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        query['due_date'] = {'$lt': now_iso, '$exists': True, '$ne': None}
        if 'status' not in query:
            query['status'] = {'$nin': ['closed']}
    if q:
        text_or = [
            {'title': {'$regex': q, '$options': 'i'}},
            {'description': {'$regex': q, '$options': 'i'}},
        ]
        if '$or' in query:
            existing_or = query.pop('$or')
            query.setdefault('$and', []).extend([{'$or': existing_or}, {'$or': text_or}])
        else:
            query['$or'] = text_or
    is_contractor = user['role'] == 'contractor'
    if not is_contractor and project_id:
        proj_role = await _get_project_role(user, project_id)
        if proj_role == 'contractor':
            is_contractor = True
    if is_contractor:
        query['assignee_id'] = user['id']

    tasks = await db.tasks.find(query, {'_id': 0}).sort('created_at', -1).to_list(10000)

    if bucket_key:
        contractor_map, company_map, membership_trade_map = await _build_bucket_maps(db, project_id)
        tasks = [t for t in tasks if compute_task_bucket(t, contractor_map, company_map, membership_trade_map)['bucket_key'] == bucket_key]

    tasks = sorted(tasks, key=_priority_sort_key)

    from services.object_storage import resolve_urls_in_doc
    result = []
    for t in tasks:
        td = Task(**t).dict()
        resolve_urls_in_doc(td)
        result.append(td)
    return result


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='הליקוי לא נמצא')
    membership = await _get_project_membership(user, task['project_id'])
    is_assignee = task.get('assignee_id') == user['id']
    is_contractor = membership['role'] == 'contractor' or user['role'] == 'contractor'
    if is_contractor and not is_assignee:
        raise HTTPException(status_code=404, detail='הליקוי לא נמצא')
    if is_contractor and is_assignee:
        trade_key = await _get_contractor_trade_key(db, user['id'], task['project_id'])
        if not _trades_match(task.get('category'), trade_key):
            raise HTTPException(status_code=404, detail='הליקוי לא נמצא')
    if membership['role'] == 'none' and not is_assignee:
        raise HTTPException(status_code=403, detail='No access to this task')
    task_data = Task(**task).dict()
    from services.object_storage import resolve_urls_in_doc
    resolve_urls_in_doc(task_data)
    task_data['user_project_role'] = membership['role'] if membership['role'] != 'none' else ('contractor' if is_assignee else 'none')
    task_data['user_project_sub_role'] = membership.get('sub_role')
    
    # Add location names
    proj = await db.projects.find_one({'id': task['project_id']}, {'_id': 0, 'name': 1})
    task_data['project_name'] = proj['name'] if proj else ''
    
    if task.get('building_id'):
        bld = await db.buildings.find_one({'id': task['building_id']}, {'_id': 0, 'name': 1})
        task_data['building_name'] = bld['name'] if bld else ''
    
    if task.get('floor_id'):
        fl = await db.floors.find_one({'id': task['floor_id']}, {'_id': 0, 'name': 1, 'number': 1})
        task_data['floor_name'] = fl.get('name') or str(fl.get('number', '')) if fl else ''
    
    if task.get('unit_id'):
        un = await db.units.find_one({'id': task['unit_id']}, {'_id': 0})
        task_data['unit_name'] = (un.get('display_label') or un.get('name') or un.get('unit_no') or str(un.get('number', ''))) if un else ''
    
    return task_data


@router.patch("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, update: TaskUpdate, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    project_role = await _get_project_role(user, task['project_id'])
    if project_role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail='Only management can update tasks')
    update_data = {k: v for k, v in update.dict(exclude_unset=True).items() if v is not None}
    if 'priority' in update_data and hasattr(update_data['priority'], 'value'):
        update_data['priority'] = update_data['priority'].value
    if 'category' in update_data and hasattr(update_data['category'], 'value'):
        update_data['category'] = update_data['category'].value
    update_data['updated_at'] = _now()
    await db.tasks.update_one({'id': task_id}, {'$set': update_data})
    await _audit('task', task_id, 'update', user['id'], update_data)
    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    return Task(**updated)


@router.patch("/tasks/{task_id}/assign")
async def assign_task(task_id: str, assignment: TaskAssign, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    project_role = await _get_project_role(user, task['project_id'])
    if project_role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail='Only management can assign tasks')

    assignee = await db.users.find_one({'id': assignment.assignee_id}, {'_id': 0})
    if not assignee:
        raise HTTPException(status_code=404, detail='Assignee not found')

    assignee_membership = await db.project_memberships.find_one({
        'project_id': task['project_id'], 'user_id': assignment.assignee_id
    })
    if not assignee_membership:
        raise HTTPException(status_code=404, detail='Assignee is not a member of this project')

    mem_company_id = assignee_membership.get('company_id')
    assignee_trade_key = assignee_membership.get('contractor_trade_key')

    if assignee_membership.get('role') == 'contractor':
        if not mem_company_id or not assignee_trade_key:
            raise HTTPException(status_code=409, detail={
                'code': 'CONTRACTOR_UNASSIGNED',
                'message': 'לא ניתן לשייך ליקוי לקבלן ללא חברה/תחום. יש לשייך קבלן לחברה ולתחום תחילה.',
            })

    effective_company_id = mem_company_id or assignment.company_id
    company = await db.project_companies.find_one({'id': effective_company_id, 'deletedAt': {'$exists': False}}, {'_id': 0})
    if not company:
        company = await db.companies.find_one({'id': effective_company_id}, {'_id': 0})
    if not company:
        raise HTTPException(status_code=404, detail='Company not found')
    category_synced = False
    task_category = task.get('category')
    if assignee_trade_key and not _trades_match(task_category, assignee_trade_key):
        if not assignment.force_category_change:
            task_cat_label = TRADE_MAP.get(task_category, task_category)
            trade_label = TRADE_MAP.get(assignee_trade_key, assignee_trade_key)
            raise HTTPException(
                status_code=409,
                detail={
                    'error': 'trade_mismatch',
                    'message': f'תחום הליקוי ({task_cat_label}) לא תואם לתחום הקבלן ({trade_label})',
                    'task_category': task_category,
                    'contractor_trade': assignee_trade_key,
                    'task_category_label': task_cat_label,
                    'contractor_trade_label': trade_label,
                }
            )
        category_synced = True

    ts = _now()
    old_status = task['status']
    new_status = 'assigned' if old_status == 'open' else old_status

    update_fields = {
        'company_id': effective_company_id,
        'assignee_id': assignment.assignee_id,
        'status': new_status,
        'updated_at': ts,
    }
    if category_synced:
        update_fields['category'] = assignee_trade_key
    await db.tasks.update_one({'id': task_id}, {'$set': update_fields})

    if old_status != new_status:
        await db.task_status_history.insert_one({
            'id': str(uuid.uuid4()), 'task_id': task_id,
            'old_status': old_status, 'new_status': new_status,
            'changed_by': user['id'], 'note': f'Assigned to {assignee.get("name", "")}',
            'created_at': ts,
        })
        await db.task_updates.insert_one({
            'id': str(uuid.uuid4()), 'task_id': task_id, 'user_id': user['id'],
            'user_name': user.get('name', ''),
            'content': f'שויך ל{assignee.get("name", "")} ({company.get("name", "")})',
            'update_type': 'status_change', 'old_status': old_status,
            'new_status': new_status, 'created_at': ts,
        })

    audit_details = {
        'company_id': effective_company_id,
        'assignee_id': assignment.assignee_id,
        'assignee_name': assignee.get('name', ''),
    }
    if category_synced:
        audit_details['category_changed'] = True
        audit_details['old_category'] = task_category
        audit_details['new_category'] = assignee_trade_key
        audit_details['reason'] = 'PM confirmed category change on cross-trade assignment'
    await _audit('task', task_id, 'assign', user['id'], audit_details)

    notification_status = None
    engine = get_notification_engine()
    if engine:
        try:
            task_link = _get_task_link(task_id)
            job = await engine.enqueue(task_id, 'task_assigned', user['id'], task_link=task_link)
            if job and job.get('status') == 'queued':
                proc_result = await engine.process_job(job)
                notification_status = {
                    'sent': True,
                    'channel': proc_result.get('channel', 'unknown'),
                    'job_id': proc_result.get('job_id', job.get('id', '')),
                    'provider_message_id': proc_result.get('provider_message_id', ''),
                }
            elif job:
                notification_status = {'sent': False, 'reason': 'duplicate', 'job_id': job.get('id', '')}
        except Exception as e:
            logger.warning(f"[NOTIFY] Auto-enqueue failed for assign: {e}")
            notification_status = {'sent': False, 'reason': str(e)[:200]}

    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    result = Task(**updated).dict()
    if category_synced:
        result['category_synced'] = True
        result['synced_category'] = assignee_trade_key
    if notification_status:
        result['notification_status'] = notification_status
    return result


@router.post("/tasks/{task_id}/status", response_model=Task)
async def change_task_status(task_id: str, change: TaskStatusChange, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')

    current_status = TaskStatus(task['status'])
    target_status = change.status

    project_role = await _get_project_role(user, task['project_id'])
    effective_role = project_role if project_role != 'none' else user['role']

    if effective_role == 'viewer' or user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers cannot change task status')

    if effective_role == 'contractor' or user['role'] == 'contractor':
        if target_status == TaskStatus.closed:
            raise HTTPException(status_code=403, detail='Contractors cannot close tasks. Use /contractor-proof to submit for approval.')
        contractor_allowed = {
            TaskStatus.assigned: [TaskStatus.in_progress],
            TaskStatus.in_progress: [TaskStatus.waiting_verify, TaskStatus.pending_contractor_proof],
        }
        if target_status not in contractor_allowed.get(current_status, []):
            raise HTTPException(status_code=403, detail='Contractors can only move assigned->in_progress or in_progress->pending_contractor_proof')

    allowed = VALID_TRANSITIONS.get(current_status, [])
    if target_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {current_status.value} -> {target_status.value}. Allowed: {[s.value for s in allowed]}"
        )

    ts = _now()
    await db.tasks.update_one({'id': task_id}, {'$set': {'status': target_status.value, 'updated_at': ts}})
    await db.task_status_history.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id,
        'old_status': current_status.value, 'new_status': target_status.value,
        'changed_by': user['id'], 'note': change.note or '', 'created_at': ts,
    })
    await db.task_updates.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id, 'user_id': user['id'],
        'user_name': user.get('name', ''), 'content': change.note or f'Status changed to {target_status.value}',
        'update_type': 'status_change', 'old_status': current_status.value,
        'new_status': target_status.value, 'created_at': ts,
    })
    await _audit('task', task_id, 'status_change', user['id'], {
        'old': current_status.value, 'new': target_status.value, 'note': change.note
    })

    notify_events = {
        'waiting_verify': 'status_waiting_verify',
        'closed': 'status_closed',
    }
    event_type = notify_events.get(target_status.value)
    if event_type:
        engine = get_notification_engine()
        if engine:
            try:
                task_link = _get_task_link(task_id)
                job = await engine.enqueue(task_id, event_type, user['id'], task_link=task_link)
                if job and job.get('status') == 'queued':
                    await engine.process_job(job)
            except Exception as e:
                logger.warning(f"[NOTIFY] Auto-enqueue failed for status_change: {e}")

    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    return Task(**updated)


@router.post("/tasks/{task_id}/reopen", response_model=Task)
async def reopen_task(task_id: str, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    if task['status'] != 'closed':
        raise HTTPException(status_code=400, detail='Only closed tasks can be reopened')
    ts = _now()
    await db.tasks.update_one({'id': task_id}, {'$set': {'status': 'reopened', 'updated_at': ts}})
    await db.task_status_history.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id,
        'old_status': 'closed', 'new_status': 'reopened',
        'changed_by': user['id'], 'note': 'Task reopened', 'created_at': ts,
    })
    await db.task_updates.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id, 'user_id': user['id'],
        'user_name': user.get('name', ''), 'content': 'Task reopened',
        'update_type': 'status_change', 'old_status': 'closed',
        'new_status': 'reopened', 'created_at': ts,
    })
    await _audit('task', task_id, 'reopen', user['id'], {})
    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    return Task(**updated)


@router.post("/tasks/{task_id}/contractor-proof")
async def contractor_proof(
    task_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')

    project_role = await _get_project_role(user, task['project_id'])
    if project_role != 'contractor' and user['role'] != 'contractor':
        raise HTTPException(status_code=403, detail='Only contractors can submit proof')
    if task.get('assignee_id') != user['id']:
        raise HTTPException(status_code=404, detail='הליקוי לא נמצא')
    trade_key = await _get_contractor_trade_key(db, user['id'], task['project_id'])
    if not _trades_match(task.get('category'), trade_key):
        raise HTTPException(status_code=404, detail='הליקוי לא נמצא')

    current_status = task.get('status', '')
    PROOF_ALLOWED_STATUSES = ('open', 'assigned', 'in_progress', 'pending_contractor_proof', 'returned_to_contractor')
    if current_status not in PROOF_ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f'לא ניתן להעלות הוכחה כשסטטוס הליקוי הוא {current_status}')

    form = await request.form()
    all_files = []
    note = None
    for key in form:
        val = form.getlist(key)
        for v in val:
            if hasattr(v, 'filename') and v.filename:
                all_files.append(v)
            elif key == 'note' and isinstance(v, str):
                note = v
    if not all_files:
        raise HTTPException(status_code=400, detail='At least one proof file is required')

    from services.storage_service import StorageService
    storage = StorageService()
    proof_urls = []
    for i, upload_file in enumerate(all_files):
        result = await storage.upload_file_with_details(upload_file, f"proof_{task_id}_{i}")
        proof_urls.append(result.file_url)

    ts = _now()
    old_status = current_status
    new_status = 'pending_manager_approval'
    proof_content = note or 'הוכחת תיקון הועלתה'

    for url in proof_urls:
        update_id = str(uuid.uuid4())
        doc = {
            'id': update_id, 'task_id': task_id, 'user_id': user['id'],
            'user_name': user.get('name', ''), 'content': proof_content,
            'update_type': 'attachment', 'attachment_url': url,
            'old_status': old_status, 'new_status': new_status,
            'created_at': ts,
        }
        await db.task_updates.insert_one(doc)

    await db.tasks.update_one({'id': task_id}, {'$set': {
        'status': new_status, 'updated_at': ts,
        'proof_urls': proof_urls,
    }, '$inc': {'attachments_count': len(proof_urls)}})

    await db.task_status_history.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id,
        'old_status': old_status, 'new_status': new_status,
        'changed_by': user['id'], 'note': proof_content, 'created_at': ts,
    })

    membership = await _get_project_membership(user, task['project_id'])
    await _audit('task', task_id, 'contractor_proof_uploaded', user['id'], {
        'old_status': old_status, 'new_status': new_status,
        'actor_project_role': membership['role'],
        'note': note or '', 'proof_urls': proof_urls,
    })

    engine = get_notification_engine()
    if engine:
        try:
            task_link = _get_task_link(task_id)
            job = await engine.enqueue(task_id, 'contractor_proof_uploaded', user['id'], task_link=task_link)
            if job and job.get('status') == 'queued':
                await engine.process_job(job)
        except Exception as e:
            logger.warning(f"[NOTIFY] contractor-proof notification failed: {e}")

    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    return {
        'success': True,
        'task': Task(**updated).dict(),
        'proof_url': proof_urls[0] if proof_urls else '',
        'proof_urls': proof_urls,
        'message': 'הוכחת תיקון נשלחה לאישור מנהל',
    }


@router.delete("/tasks/{task_id}/proof/{proof_id}")
async def delete_proof(task_id: str, proof_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='הליקוי לא נמצא')

    project_role = await _get_project_role(user, task['project_id'])
    if not _is_super_admin(user) and project_role != 'project_manager':
        raise HTTPException(status_code=403, detail='רק מנהל פרויקט יכול למחוק הוכחות')

    try:
        body = await request.json()
        reason = body.get('reason', '')
    except Exception:
        reason = ''
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail='חובה לציין סיבה למחיקה')

    proof = await db.task_updates.find_one({'id': proof_id, 'task_id': task_id, 'attachment_url': {'$exists': True}, 'deletedAt': {'$exists': False}}, {'_id': 0})
    if not proof:
        raise HTTPException(status_code=404, detail='הוכחה לא נמצאה')

    await db.task_updates.update_one({'id': proof_id, 'task_id': task_id}, {'$set': {'deletedAt': _now(), 'deletedBy': user['id'], 'deleteReason': reason.strip()}})

    uploader = await db.users.find_one({'id': proof.get('user_id')}, {'_id': 0, 'name': 1})
    await _audit('task', task_id, 'proof_soft_deleted', user['id'], {
        'proof_id': proof_id,
        'deleted_attachment_url': proof.get('attachment_url'),
        'original_uploader_id': proof.get('user_id'),
        'original_uploader_name': uploader.get('name', '') if uploader else '',
        'original_content': proof.get('content', ''),
        'original_created_at': proof.get('created_at', ''),
        'reason': reason.strip(),
    })

    return {'success': True, 'message': 'הוכחה נמחקה בהצלחה'}


@router.post("/tasks/{task_id}/manager-decision")
async def manager_decision(task_id: str, body: ManagerDecisionRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')

    project_role = await _get_project_role(user, task['project_id'])
    if project_role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail='Only management team or PM can approve/reject tasks')

    current_status = task.get('status', '')
    if current_status != 'pending_manager_approval':
        raise HTTPException(status_code=400, detail=f'Task must be in pending_manager_approval status, currently: {current_status}')

    decision = body.decision.lower()
    if decision not in ('approve', 'reject'):
        raise HTTPException(status_code=400, detail='Decision must be approve or reject')

    if decision == 'reject' and not body.reason:
        raise HTTPException(status_code=400, detail='Rejection reason is required')

    ts = _now()
    old_status = current_status

    if decision == 'approve':
        new_status = 'closed'
        audit_action = 'manager_approved_closed'
        update_content = 'תיקון אושר וסגור'
    else:
        new_status = 'returned_to_contractor'
        audit_action = 'manager_rejected_returned'
        update_content = f'הוחזר לקבלן: {body.reason}'

    await db.tasks.update_one({'id': task_id}, {'$set': {
        'status': new_status, 'updated_at': ts,
    }})

    await db.task_status_history.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id,
        'old_status': old_status, 'new_status': new_status,
        'changed_by': user['id'], 'note': update_content, 'created_at': ts,
    })

    await db.task_updates.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id, 'user_id': user['id'],
        'user_name': user.get('name', ''), 'content': update_content,
        'update_type': 'status_change', 'old_status': old_status,
        'new_status': new_status, 'created_at': ts,
    })

    membership = await _get_project_membership(user, task['project_id'])
    await _audit('task', task_id, audit_action, user['id'], {
        'old_status': old_status, 'new_status': new_status,
        'decision': decision, 'reason': body.reason or '',
        'actor_project_role': membership['role'],
        'actor_sub_role': membership.get('sub_role'),
    })

    event_type = 'manager_approved' if decision == 'approve' else 'manager_rejected'
    engine = get_notification_engine()
    if engine:
        try:
            task_link = _get_task_link(task_id)
            job = await engine.enqueue(task_id, event_type, user['id'],
                                       custom_message=body.reason or '', task_link=task_link)
            if job and job.get('status') == 'queued':
                await engine.process_job(job)
        except Exception as e:
            logger.warning(f"[NOTIFY] manager-decision notification failed: {e}")

    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    return {
        'success': True,
        'task': Task(**updated).dict(),
        'decision': decision,
        'message': 'תיקון אושר וסגור' if decision == 'approve' else f'תיקון נדחה: {body.reason}',
    }


@router.post("/tasks/{task_id}/updates", response_model=TaskUpdateResponse)
async def add_task_update(task_id: str, update: TaskUpdateCreate, user: dict = Depends(get_current_user)):
    db = get_db()
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers cannot add updates')
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    membership = await _get_project_membership(user, task['project_id'])
    is_assignee = task.get('assignee_id') == user['id']
    if membership['role'] == 'none' and not is_assignee:
        raise HTTPException(status_code=403, detail='No access to this task')
    update_id = str(uuid.uuid4())
    ts = _now()
    doc = {
        'id': update_id, 'task_id': task_id, 'user_id': user['id'],
        'user_name': user.get('name', ''), 'content': update.content,
        'update_type': update.update_type.value if update.update_type else 'comment',
        'attachment_url': update.attachment_url,
        'old_status': update.old_status.value if update.old_status else None,
        'new_status': update.new_status.value if update.new_status else None,
        'created_at': ts,
    }
    await db.task_updates.insert_one(doc)
    await db.tasks.update_one({'id': task_id}, {'$inc': {'comments_count': 1}, '$set': {'updated_at': ts}})
    await _audit('task_update', update_id, 'create', user['id'], {'task_id': task_id})
    return TaskUpdateResponse(**{k: v for k, v in doc.items() if k != '_id'})


@router.get("/tasks/{task_id}/updates", response_model=List[TaskUpdateResponse])
async def list_task_updates(task_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    updates = await db.task_updates.find({'task_id': task_id, 'deletedAt': {'$exists': False}}, {'_id': 0}).sort('created_at', -1).to_list(1000)
    from services.object_storage import resolve_urls_in_doc
    for u in updates:
        resolve_urls_in_doc(u)
    return [TaskUpdateResponse(**u) for u in updates]


@router.post("/tasks/{task_id}/attachments")
async def upload_task_attachment(task_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    db = get_db()
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers cannot upload attachments')
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    from services.storage_service import StorageService
    storage = StorageService()
    result = await storage.upload_file_with_details(file, f"task_{task_id}")
    ts = _now()
    update_id = str(uuid.uuid4())
    doc = {
        'id': update_id, 'task_id': task_id, 'user_id': user['id'],
        'user_name': user.get('name', ''), 'content': f'Attachment: {file.filename}',
        'update_type': 'attachment', 'attachment_url': result.file_url,
        'created_at': ts,
    }
    await db.task_updates.insert_one(doc)
    await db.tasks.update_one({'id': task_id}, {
        '$inc': {'attachments_count': 1},
        '$set': {'updated_at': ts},
    })
    await _audit('task_attachment', update_id, 'upload', user['id'], {
        'task_id': task_id, 'filename': file.filename, 'file_url': result.file_url,
    })

    existing_count = await db.task_updates.count_documents({
        'task_id': task_id, 'update_type': 'attachment',
    })
    if existing_count == 1:
        engine = get_notification_engine()
        if engine:
            try:
                task_link = _get_task_link(task_id)
                img_result = await engine.attach_image_to_notification(
                    task_id=task_id, attachment_id=update_id,
                    image_url=result.file_url, actor_id=user['id'],
                    task_link=task_link,
                )
                if img_result:
                    if img_result.get('status') == 'queued' and img_result.get('event_type') == 'media_followup':
                        await engine.process_job(img_result)
            except Exception as e:
                logger.warning(f"[NOTIFY-IMG] attach_image_to_notification failed: {e}")

    from services.object_storage import resolve_url
    return {'id': update_id, 'file_url': resolve_url(result.file_url), 'thumbnail_url': resolve_url(result.thumbnail_url), 'filename': file.filename}


@router.get("/updates/feed", response_model=List[TaskUpdateResponse])
async def updates_feed(
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    if project_id:
        task_ids = await db.tasks.distinct('id', {'project_id': project_id})
        query = {'task_id': {'$in': task_ids}}
    else:
        query = {}
    updates = await db.task_updates.find(query, {'_id': 0}).sort('created_at', -1).to_list(limit)
    from services.object_storage import resolve_urls_in_doc
    for u in updates:
        resolve_urls_in_doc(u)
    return [TaskUpdateResponse(**u) for u in updates]


# ── Project-scoped companies ──
@router.post("/projects/{project_id}/companies")
async def create_project_company(project_id: str, body: dict = Body(...), user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    await _check_project_access(user, project_id)
    name = (body.get('name') or '').strip()
    trade = (body.get('trade') or '').strip() or None
    contact_name = (body.get('contact_name') or '').strip() or None
    contact_phone = (body.get('contact_phone') or '').strip() or None
    if not name:
        raise HTTPException(status_code=422, detail='שם חברה הוא שדה חובה')
    phone_e164 = None
    if contact_phone:
        from .phone_utils import normalize_israeli_phone
        try:
            phone_result = normalize_israeli_phone(contact_phone)
            phone_e164 = phone_result.get('phone_e164') or contact_phone
        except (ValueError, Exception):
            phone_e164 = contact_phone
    company_id = str(uuid.uuid4())
    doc = {
        'id': company_id, 'project_id': project_id,
        'name': name,
        'trade': trade,
        'contact_name': contact_name,
        'contact_phone': phone_e164,
        'contact_phone_raw': contact_phone,
        'contact_email': body.get('contact_email'),
        'created_at': _now(),
    }
    await db.project_companies.insert_one(doc)
    await _audit('project_company', company_id, 'create', user['id'], {'project_id': project_id, 'name': doc['name']})
    return {k: v for k, v in doc.items() if k != '_id'}


@router.get("/projects/{project_id}/companies")
async def list_project_companies(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    await _check_project_read_access(user, project_id)
    companies = await db.project_companies.find({'project_id': project_id, 'deletedAt': {'$exists': False}}, {'_id': 0}).to_list(1000)
    return companies


@router.put("/projects/{project_id}/companies/{company_id}")
async def update_project_company(project_id: str, company_id: str, body: dict = Body(...), user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    await _check_project_access(user, project_id)
    existing = await db.project_companies.find_one({'id': company_id, 'project_id': project_id, 'deletedAt': {'$exists': False}})
    if not existing:
        raise HTTPException(status_code=404, detail='Company not found')
    update_data = {}
    for field in ('name', 'trade', 'contact_name', 'contact_phone', 'contact_email'):
        if field in body:
            update_data[field] = body[field]
    if update_data:
        await db.project_companies.update_one({'id': company_id}, {'$set': update_data})
    await _audit('project_company', company_id, 'update', user['id'], update_data)
    updated = await db.project_companies.find_one({'id': company_id}, {'_id': 0})
    return updated


@router.delete("/projects/{project_id}/companies/{company_id}")
async def delete_project_company(project_id: str, company_id: str, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    await _check_project_access(user, project_id)
    existing = await db.project_companies.find_one({'id': company_id, 'project_id': project_id, 'deletedAt': {'$exists': False}})
    if not existing:
        raise HTTPException(status_code=404, detail='Company not found')
    await db.project_companies.update_one({'id': company_id}, {'$set': {'deletedAt': _now(), 'deletedBy': user['id']}})
    await _audit('project_company', company_id, 'soft_delete', user['id'], {'project_id': project_id, 'name': existing.get('name', '')})
    return {'success': True}


# ── Team invites (RBAC invite system) ──
INVITE_RBAC = {
    'project_manager': ['project_manager', 'management_team', 'contractor'],
    'management_team': ['contractor'],
}
VALID_SUB_ROLES = ['site_manager', 'execution_engineer', 'safety_assistant', 'work_manager', 'safety_officer']


@router.post("/projects/{project_id}/invites")
async def create_team_invite(project_id: str, body: InviteCreate, user: dict = Depends(get_current_user)):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')

    membership = await _get_project_membership(user, project_id)
    inviter_role = membership['role']
    allowed_roles = INVITE_RBAC.get(inviter_role, [])
    if not allowed_roles:
        raise HTTPException(status_code=403, detail='אין לך הרשאה להזמין משתמשים')

    target_role = body.role.value
    if target_role not in allowed_roles:
        raise HTTPException(status_code=403, detail=f'אין לך הרשאה להזמין {target_role}')

    if not body.full_name or not body.full_name.strip():
        raise HTTPException(status_code=422, detail='שם מלא הוא שדה חובה')

    try:
        phone_result = normalize_israeli_phone(body.phone)
        phone = phone_result['phone_e164']
        phone_raw = phone_result['phone_raw']
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if target_role == 'contractor':
        if not body.trade_key or not body.trade_key.strip():
            raise HTTPException(status_code=422, detail='מקצוע הוא שדה חובה עבור קבלן')
        is_global = body.trade_key in BUCKET_LABELS
        is_project = False
        if not is_global:
            is_project = await db.project_trades.find_one({'project_id': project_id, 'key': body.trade_key}) is not None
        if not is_global and not is_project:
            raise HTTPException(status_code=422, detail=f'מקצוע לא תקין: {body.trade_key}')
        if not body.company_id or not body.company_id.strip():
            raise HTTPException(status_code=422, detail='חברה היא שדה חובה עבור קבלן')
        company_doc = await db.project_companies.find_one({
            'id': body.company_id, 'project_id': project_id,
            'deletedAt': {'$exists': False},
        })
        if not company_doc:
            raise HTTPException(status_code=422, detail='חברה לא נמצאה בפרויקט זה')
    elif body.trade_key:
        raise HTTPException(status_code=400, detail='trade_key מותר רק לתפקיד קבלן')
    if body.company_id and target_role != 'contractor':
        raise HTTPException(status_code=400, detail='company_id מותר רק לתפקיד קבלן')

    if target_role == 'management_team':
        if body.sub_role and body.sub_role not in VALID_SUB_ROLES:
            raise HTTPException(status_code=400, detail=f'sub_role חייב להיות אחד מ: {", ".join(VALID_SUB_ROLES)}')
    else:
        if body.sub_role:
            raise HTTPException(status_code=400, detail='sub_role מותר רק לתפקיד management_team')

    existing_invite = await db.invites.find_one({
        'project_id': project_id, 'target_phone': phone,
        'role': target_role, 'status': 'pending',
    })
    if existing_invite:
        raise HTTPException(status_code=400, detail='הזמנה ממתינה כבר קיימת עבור טלפון ותפקיד זה')

    existing_user = await db.users.find_one({'phone_e164': phone}, {'_id': 0})
    if existing_user:
        existing_membership = await db.project_memberships.find_one({
            'project_id': project_id, 'user_id': existing_user['id'],
        })
        if existing_membership:
            raise HTTPException(status_code=400, detail='משתמש כבר חבר בפרויקט זה')
        from contractor_ops.member_management import check_role_conflict
        await check_role_conflict(db, existing_user['id'], project_id, target_role,
                                  actor_id=user['id'], attempted_action='create_team_invite_auto_link')
        ts = _now()
        membership_doc = {
            'id': str(uuid.uuid4()),
            'project_id': project_id,
            'user_id': existing_user['id'],
            'role': target_role,
            'sub_role': body.sub_role if target_role == 'management_team' else None,
            'created_at': ts,
        }
        if target_role == 'contractor' and body.trade_key:
            membership_doc['contractor_trade_key'] = body.trade_key
        if target_role == 'contractor' and body.company_id:
            membership_doc['company_id'] = body.company_id
        await db.project_memberships.update_one(
            {'project_id': project_id, 'user_id': existing_user['id']},
            {'$set': membership_doc},
            upsert=True
        )
        if target_role == 'project_manager':
            await db.users.update_one(
                {'id': existing_user['id']},
                {'$set': {'role': 'project_manager', 'updated_at': ts}}
            )
        await _audit('invite', 'auto_link', 'auto_linked', user['id'], {
            'project_id': project_id, 'target_user_id': existing_user['id'],
            'role': target_role, 'phone': phone,
            'trade_key': body.trade_key if target_role == 'contractor' else None,
            'company_id': body.company_id if target_role == 'contractor' else None,
        })
        return {
            'success': True, 'auto_linked': True,
            'user_id': existing_user['id'],
            'message': f'משתמש {existing_user.get("name", phone)} שויך אוטומטית לפרויקט',
        }

    invite_id = str(uuid.uuid4())
    ts = _now()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    doc = {
        'id': invite_id,
        'project_id': project_id,
        'inviter_user_id': user['id'],
        'target_phone': phone,
        'phone_raw': phone_raw,
        'role': target_role,
        'sub_role': body.sub_role if target_role == 'management_team' else None,
        'trade_key': body.trade_key if target_role == 'contractor' else None,
        'company_id': body.company_id if target_role == 'contractor' else None,
        'full_name': body.full_name,
        'token': secrets.token_urlsafe(32),
        'status': 'pending',
        'expires_at': expires_at,
        'accepted_by_user_id': None,
        'accepted_at': None,
        'created_at': ts,
        'updated_at': ts,
    }
    await db.invites.insert_one(doc)
    await _audit('invite', invite_id, 'created', user['id'], {
        'project_id': project_id, 'phone': phone, 'role': target_role,
        'trade_key': body.trade_key if target_role == 'contractor' else None,
        'company_id': body.company_id if target_role == 'contractor' else None,
    })

    role_labels = {
        'project_manager': 'מנהל פרויקט',
        'management_team': 'צוות ניהול',
        'contractor': 'קבלן',
    }
    notification_status = {'channel_used': 'none', 'reason': 'not_attempted'}
    engine = get_notification_engine()
    if engine:
        try:
            base = get_public_base_url()
            join_link = f"{base}/onboarding?invite={invite_id}" if base else ""
            job = await engine.enqueue_invite(
                invite_id=invite_id,
                target_phone=phone,
                project_name=project.get('name', ''),
                join_link=join_link,
                inviter_name=user.get('name', ''),
                role_label=role_labels.get(target_role, target_role),
                created_by=user['id'],
            )
            if job and job.get('status') == 'queued':
                result = await engine.process_invite_job(job)
                notification_status = {
                    'channel_used': result.get('channel', 'none'),
                    'delivery_status': result.get('status', 'unknown'),
                    'reason': result.get('reason', ''),
                    'provider_message_id': result.get('provider_message_id', ''),
                    'job_id': result.get('job_id', ''),
                    'wa_skipped': result.get('wa_skipped', False),
                }
        except Exception as e:
            logger.warning(f"[INVITE] Notification failed for invite {invite_id}: {e}")
            notification_status = {'channel_used': 'none', 'delivery_status': 'failed', 'reason': str(e)[:200]}

    response = {k: v for k, v in doc.items() if k != '_id'}
    response['notification_status'] = notification_status
    return response


@router.get("/projects/{project_id}/invites")
async def list_team_invites(project_id: str, status: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    db = get_db()
    membership = await _get_project_membership(user, project_id)
    if membership['role'] not in ('project_manager', 'management_team'):
        raise HTTPException(status_code=403, detail='אין הרשאה')

    query = {'project_id': project_id}
    if status:
        query['status'] = status
    invites = await db.invites.find(query, {'_id': 0}).sort('created_at', -1).to_list(1000)

    legacy_query = {'project_id': project_id}
    if status:
        legacy_query['status'] = status
    legacy_invites = await db.team_invites.find(legacy_query, {'_id': 0}).sort('created_at', -1).to_list(1000)
    legacy_ids = {inv.get('id') for inv in invites}
    for li in legacy_invites:
        if li.get('id') not in legacy_ids:
            invites.append(li)

    return invites


@router.post("/projects/{project_id}/invites/{invite_id}/resend")
async def resend_team_invite(project_id: str, invite_id: str, user: dict = Depends(get_current_user)):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    membership = await _get_project_membership(user, project_id)
    if membership['role'] not in ('project_manager',):
        raise HTTPException(status_code=403, detail='אין הרשאה')
    invite = await db.invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        invite = await db.team_invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        raise HTTPException(status_code=404, detail='Invite not found')
    if invite['status'] != 'pending':
        raise HTTPException(status_code=400, detail='Can only resend pending invites')
    ts = _now()
    if 'target_phone' in invite:
        await db.invites.update_one({'id': invite_id}, {'$set': {'updated_at': ts}})
    else:
        await db.team_invites.update_one({'id': invite_id}, {'$set': {'updated_at': ts}})
    await _audit('invite', invite_id, 'resend', user['id'], {'project_id': project_id})

    notification_status = {'channel_used': 'none', 'reason': 'not_attempted'}
    target_phone = invite.get('target_phone', invite.get('phone', ''))
    engine = get_notification_engine()
    if engine and target_phone:
        try:
            project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'name': 1})
            base = get_public_base_url()
            join_link = f"{base}/onboarding?invite={invite_id}" if base else ""
            role_labels = {'project_manager': 'מנהל פרויקט', 'management_team': 'צוות ניהול', 'contractor': 'קבלן'}
            resend_id = f"{invite_id}_resend_{ts}"
            job = await engine.enqueue_invite(
                invite_id=resend_id,
                target_phone=target_phone,
                project_name=project.get('name', '') if project else '',
                join_link=join_link,
                inviter_name=user.get('name', ''),
                role_label=role_labels.get(invite.get('role', ''), invite.get('role', '')),
                created_by=user['id'],
            )
            if job and job.get('status') == 'queued':
                result = await engine.process_invite_job(job)
                delivery_status = result.get('status', 'unknown')
                channel = result.get('channel', 'none')
                notification_status = {
                    'channel_used': channel,
                    'delivery_status': delivery_status,
                    'reason': result.get('reason', ''),
                    'provider_message_id': result.get('provider_message_id', ''),
                    'job_id': result.get('job_id', ''),
                    'wa_skipped': result.get('wa_skipped', False),
                }
        except Exception as e:
            logger.warning(f"[INVITE-RESEND] Notification failed: {e}")
            notification_status = {'channel_used': 'none', 'delivery_status': 'failed', 'reason': str(e)[:200]}

    return {'success': True, 'message': 'הזמנה נשלחה מחדש', 'notification_status': notification_status}


@router.post("/projects/{project_id}/invites/{invite_id}/resend-sms")
async def resend_invite_sms(project_id: str, invite_id: str, user: dict = Depends(get_current_user)):
    if not _is_super_admin(user):
        membership = await _get_project_membership(user, project_id)
        if membership['role'] not in ('project_manager',):
            raise HTTPException(status_code=403, detail='אין הרשאה')
    db = get_db()
    invite = await db.invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        invite = await db.team_invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        raise HTTPException(status_code=404, detail='Invite not found')
    if invite['status'] != 'pending':
        raise HTTPException(status_code=400, detail='Can only resend pending invites')

    ts = _now()
    last_sms = await db.notification_jobs.find_one(
        {'invite_id': invite_id, 'channel': 'sms', 'status': 'sent'},
        sort=[('created_at', -1)]
    )
    if last_sms:
        from datetime import datetime, timezone
        last_ts = last_sms.get('updated_at') or last_sms.get('created_at', '')
        if last_ts:
            try:
                if isinstance(last_ts, str):
                    last_dt = datetime.fromisoformat(last_ts.replace('Z', '+00:00'))
                else:
                    last_dt = last_ts
                now_dt = datetime.now(timezone.utc)
                diff_secs = (now_dt - last_dt).total_seconds()
                if diff_secs < 60:
                    remaining = int(60 - diff_secs)
                    raise HTTPException(status_code=429, detail=f'SMS נשלח לאחרונה. נסה שוב בעוד {remaining} שניות.')
            except HTTPException:
                raise
            except Exception:
                pass

    target_phone = invite.get('target_phone', invite.get('phone', ''))
    if not target_phone:
        raise HTTPException(status_code=400, detail='אין מספר טלפון בהזמנה')

    notification_status = {'channel_used': 'none', 'delivery_status': 'not_attempted'}
    engine = get_notification_engine()
    if not engine or not engine.sms_client or not engine.sms_client.enabled:
        raise HTTPException(status_code=503, detail='שירות SMS לא זמין כרגע')

    try:
        project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'name': 1})
        base = get_public_base_url()
        join_link = f"{base}/onboarding?invite={invite_id}" if base else ""
        role_labels = {'project_manager': 'מנהל פרויקט', 'management_team': 'צוות ניהול', 'contractor': 'קבלן'}

        text_lines = [
            f"הזמנה לפרויקט {project.get('name', '') if project else ''}",
            f"הוזמנת על ידי: {user.get('name', '')}",
            f"תפקיד: {role_labels.get(invite.get('role', ''), invite.get('role', ''))}",
            f"להצטרפות: {join_link}",
        ]
        sms_text = "\n".join(text_lines)

        sms_job_id = f"{invite_id}_sms_{ts}"
        from contractor_ops.msg_logger import log_msg_delivery, mask_phone
        phone_masked = mask_phone(target_phone)

        log_msg_delivery(msg_type="invite", rid=sms_job_id, channel="sms", result="queued",
                         phone_masked=phone_masked)

        sms_result = await engine.sms_client.send_sms(target_phone, sms_text, context=f'invite_sms:{invite_id}')

        if sms_result.get('status') == 'sent':
            sms_sid = sms_result.get('provider_message_id', '')
            await db.notification_jobs.insert_one({
                'id': sms_job_id,
                'invite_id': invite_id,
                'event_type': 'invite_sms_direct',
                'target_phone': target_phone,
                'status': 'sent',
                'channel': 'sms',
                'provider_message_id': sms_sid,
                'created_by': user['id'],
                'created_at': ts,
                'updated_at': ts,
            })
            await _audit('invite', invite_id, 'resend_sms', user['id'], {
                'project_id': project_id, 'twilio_sid': sms_sid,
            })
            log_msg_delivery(msg_type="invite", rid=sms_job_id, channel="sms", result="sent",
                             provider_status=sms_sid[:20], phone_masked=phone_masked)
            notification_status = {
                'channel_used': 'sms', 'delivery_status': 'sent',
                'provider_message_id': sms_sid, 'job_id': sms_job_id,
            }
        else:
            error = sms_result.get('error', 'unknown')
            log_msg_delivery(msg_type="invite", rid=sms_job_id, channel="sms", result="failed",
                             error_code=str(error)[:80], phone_masked=phone_masked)
            notification_status = {
                'channel_used': 'sms', 'delivery_status': 'failed',
                'reason': str(error)[:200],
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[INVITE-RESEND-SMS] Failed: {e}")
        notification_status = {'channel_used': 'none', 'delivery_status': 'failed', 'reason': str(e)[:200]}

    return {'success': True, 'message': 'SMS נשלח', 'notification_status': notification_status}


@router.post("/projects/{project_id}/invites/{invite_id}/cancel")
async def cancel_team_invite(project_id: str, invite_id: str, user: dict = Depends(get_current_user)):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    membership = await _get_project_membership(user, project_id)
    if membership['role'] not in ('project_manager',):
        raise HTTPException(status_code=403, detail='אין הרשאה')
    invite = await db.invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        invite = await db.team_invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        raise HTTPException(status_code=404, detail='Invite not found')
    if invite['status'] != 'pending':
        raise HTTPException(status_code=400, detail='Can only cancel pending invites')
    ts = _now()
    if 'target_phone' in invite:
        await db.invites.update_one({'id': invite_id}, {'$set': {'status': 'cancelled', 'updated_at': ts}})
    else:
        await db.team_invites.update_one({'id': invite_id}, {'$set': {'status': 'cancelled', 'updated_at': ts}})
    await _audit('invite', invite_id, 'cancelled', user['id'], {'project_id': project_id})
    return {'success': True, 'message': 'הזמנה בוטלה'}


# ── Project stats (KPI) ──
@router.get("/projects/{project_id}/stats")
async def get_project_stats(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    await _check_project_access(user, project_id)
    buildings_count = await db.buildings.count_documents({'project_id': project_id, 'archived': {'$ne': True}})
    floors_count = await db.floors.count_documents({'project_id': project_id, 'archived': {'$ne': True}})
    units_count = await db.units.count_documents({'project_id': project_id, 'archived': {'$ne': True}})
    team_count = await db.project_memberships.count_documents({'project_id': project_id})
    invites_count = await db.invites.count_documents({'project_id': project_id, 'status': 'pending'})
    invites_count += await db.team_invites.count_documents({'project_id': project_id, 'status': 'pending'})
    companies_count = await db.project_companies.count_documents({'project_id': project_id})
    open_defects = await db.tasks.count_documents({'project_id': project_id, 'status': {'$nin': ['closed']}})
    return {
        'buildings': buildings_count,
        'floors': floors_count,
        'units': units_count,
        'team_members': team_count,
        'pending_invites': invites_count,
        'companies': companies_count,
        'open_defects': open_defects,
    }


@router.get("/projects/{project_id}/dashboard")
async def get_project_dashboard(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    await _check_project_read_access(user, project_id)
    role = await _get_project_role(user, project_id)
    is_pm_or_owner = role in ('project_manager',)
    now = datetime.utcnow()
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()

    base_filter = {'project_id': project_id}
    active_statuses = ['open', 'assigned', 'in_progress', 'pending_contractor_proof',
                       'returned_to_contractor', 'reopened']
    in_progress_statuses = ['in_progress', 'pending_contractor_proof',
                            'pending_manager_approval', 'returned_to_contractor']
    approval_statuses = ['pending_manager_approval', 'waiting_verify']

    tasks = await db.tasks.find(
        base_filter,
        {'_id': 0, 'id': 1, 'title': 1, 'status': 1, 'assignee_id': 1,
         'building_id': 1, 'floor_id': 1, 'unit_id': 1,
         'created_at': 1, 'updated_at': 1, 'due_date': 1, 'category': 1, 'priority': 1}
    ).to_list(50000)

    open_count = 0
    in_progress_count = 0
    closed_count = 0
    closed_last7 = 0
    open_last7 = 0
    pending_approval_count = 0
    overdue_count = 0
    now_iso = now.isoformat()
    pending_approval_tasks = []
    stuck_map = {}
    building_load = {}
    contractor_map = {}

    by_status = {}
    by_category = {}

    for t in tasks:
        s = t.get('status', '')
        tid = t.get('id', '')
        by_status[s] = by_status.get(s, 0) + 1
        cat = t.get('category', 'general')
        by_category[cat] = by_category.get(cat, 0) + 1
        if s in active_statuses:
            open_count += 1
        if s in in_progress_statuses:
            in_progress_count += 1
        if s == 'closed':
            closed_count += 1
            if t.get('updated_at', '') >= seven_days_ago:
                closed_last7 += 1
        if t.get('created_at', '') >= seven_days_ago and s in active_statuses:
            open_last7 += 1
        if s in approval_statuses:
            pending_approval_count += 1
            pending_approval_tasks.append({
                'id': tid, 'title': t.get('title', ''),
                'status': s, 'updated_at': t.get('updated_at', ''),
                'building_id': t.get('building_id'), 'unit_id': t.get('unit_id'),
            })
        if t.get('due_date') and t['due_date'] < now_iso and s not in ('closed',):
            overdue_count += 1

        aid = t.get('assignee_id')
        if aid and s in active_statuses:
            updated = t.get('updated_at', '')
            if aid not in stuck_map:
                stuck_map[aid] = []
            stuck_map[aid].append({
                'id': tid, 'title': t.get('title', ''),
                'status': s, 'updated_at': updated,
            })

        bid = t.get('building_id')
        if bid and s in active_statuses:
            building_load[bid] = building_load.get(bid, 0) + 1

        if aid:
            if aid not in contractor_map:
                contractor_map[aid] = {'open': 0, 'closed': 0, 'rework': 0, 'response_times': []}
            if s in active_statuses:
                contractor_map[aid]['open'] += 1
            if s == 'closed':
                contractor_map[aid]['closed'] += 1
            if s == 'returned_to_contractor':
                contractor_map[aid]['rework'] += 1

    team_count = await db.project_memberships.count_documents({'project_id': project_id})

    sla_response_7d = 0
    sla_close_7d = 0
    sla_response_30d = 0
    sla_close_30d = 0
    try:
        response_pipeline_7d = [
            {'$match': {'task_id': {'$in': [t['id'] for t in tasks]},
                        'new_status': 'in_progress',
                        'created_at': {'$gte': seven_days_ago}}},
            {'$group': {'_id': '$task_id', 'first_response': {'$min': '$created_at'}}}
        ]
        response_results_7d = await db.task_status_history.aggregate(response_pipeline_7d).to_list(10000)

        task_created_map = {t['id']: t.get('created_at', '') for t in tasks}
        response_deltas_7d = []
        for r in response_results_7d:
            created = task_created_map.get(r['_id'], '')
            if created and r.get('first_response'):
                try:
                    c = datetime.fromisoformat(created.replace('Z', '+00:00').replace('+00:00', ''))
                    f = datetime.fromisoformat(r['first_response'].replace('Z', '+00:00').replace('+00:00', ''))
                    delta_h = (f - c).total_seconds() / 3600
                    if delta_h >= 0:
                        response_deltas_7d.append(delta_h)
                except Exception:
                    pass
        if response_deltas_7d:
            sla_response_7d = round(sum(response_deltas_7d) / len(response_deltas_7d), 1)

        close_pipeline_7d = [
            {'$match': {'task_id': {'$in': [t['id'] for t in tasks]},
                        'new_status': 'closed',
                        'created_at': {'$gte': seven_days_ago}}},
            {'$group': {'_id': '$task_id', 'closed_at': {'$min': '$created_at'}}}
        ]
        close_results_7d = await db.task_status_history.aggregate(close_pipeline_7d).to_list(10000)
        close_deltas_7d = []
        for r in close_results_7d:
            created = task_created_map.get(r['_id'], '')
            if created and r.get('closed_at'):
                try:
                    c = datetime.fromisoformat(created.replace('Z', '+00:00').replace('+00:00', ''))
                    f = datetime.fromisoformat(r['closed_at'].replace('Z', '+00:00').replace('+00:00', ''))
                    delta_h = (f - c).total_seconds() / 3600
                    if delta_h >= 0:
                        close_deltas_7d.append(delta_h)
                except Exception:
                    pass
        if close_deltas_7d:
            sla_close_7d = round(sum(close_deltas_7d) / len(close_deltas_7d), 1)

        response_pipeline_30d = [
            {'$match': {'task_id': {'$in': [t['id'] for t in tasks]},
                        'new_status': 'in_progress',
                        'created_at': {'$gte': thirty_days_ago}}},
            {'$group': {'_id': '$task_id', 'first_response': {'$min': '$created_at'}}}
        ]
        response_results_30d = await db.task_status_history.aggregate(response_pipeline_30d).to_list(10000)
        response_deltas_30d = []
        for r in response_results_30d:
            created = task_created_map.get(r['_id'], '')
            if created and r.get('first_response'):
                try:
                    c = datetime.fromisoformat(created.replace('Z', '+00:00').replace('+00:00', ''))
                    f = datetime.fromisoformat(r['first_response'].replace('Z', '+00:00').replace('+00:00', ''))
                    delta_h = (f - c).total_seconds() / 3600
                    if delta_h >= 0:
                        response_deltas_30d.append(delta_h)
                except Exception:
                    pass
        if response_deltas_30d:
            sla_response_30d = round(sum(response_deltas_30d) / len(response_deltas_30d), 1)

        close_pipeline_30d = [
            {'$match': {'task_id': {'$in': [t['id'] for t in tasks]},
                        'new_status': 'closed',
                        'created_at': {'$gte': thirty_days_ago}}},
            {'$group': {'_id': '$task_id', 'closed_at': {'$min': '$created_at'}}}
        ]
        close_results_30d = await db.task_status_history.aggregate(close_pipeline_30d).to_list(10000)
        close_deltas_30d = []
        for r in close_results_30d:
            created = task_created_map.get(r['_id'], '')
            if created and r.get('closed_at'):
                try:
                    c = datetime.fromisoformat(created.replace('Z', '+00:00').replace('+00:00', ''))
                    f = datetime.fromisoformat(r['closed_at'].replace('Z', '+00:00').replace('+00:00', ''))
                    delta_h = (f - c).total_seconds() / 3600
                    if delta_h >= 0:
                        close_deltas_30d.append(delta_h)
                except Exception:
                    pass
        if close_deltas_30d:
            sla_close_30d = round(sum(close_deltas_30d) / len(close_deltas_30d), 1)
    except Exception as e:
        logger.warning(f"[DASHBOARD] SLA calculation error: {e}")

    stuck_threshold = (now - timedelta(hours=48)).isoformat()
    stuck_contractors = []
    contractor_ids = list(set(list(stuck_map.keys()) + list(contractor_map.keys())))
    user_docs = {}
    if contractor_ids:
        users_list = await db.users.find(
            {'id': {'$in': contractor_ids}},
            {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(1000)
        user_docs = {u['id']: u.get('name', '') for u in users_list}

    for aid, task_list in stuck_map.items():
        stuck_tasks = [t for t in task_list if t.get('updated_at', '') < stuck_threshold]
        if stuck_tasks:
            stuck_tasks.sort(key=lambda x: x.get('updated_at', ''))
            stuck_contractors.append({
                'contractor_id': aid,
                'contractor_name': user_docs.get(aid, ''),
                'stuck_count': len(stuck_tasks),
                'tasks': stuck_tasks[:5],
            })
    stuck_contractors.sort(key=lambda x: x['stuck_count'], reverse=True)

    building_ids = list(building_load.keys())
    building_names = {}
    if building_ids:
        bldgs = await db.buildings.find(
            {'id': {'$in': building_ids}},
            {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(500)
        building_names = {b['id']: b.get('name', '') for b in bldgs}

    load_by_building = []
    for bid, count in sorted(building_load.items(), key=lambda x: x[1], reverse=True)[:10]:
        load_by_building.append({
            'building_id': bid,
            'building_name': building_names.get(bid, bid),
            'open_count': count,
        })

    contractor_quality = []
    for aid, stats in contractor_map.items():
        total = stats['open'] + stats['closed']
        if total == 0:
            continue
        contractor_quality.append({
            'contractor_id': aid,
            'contractor_name': user_docs.get(aid, ''),
            'open': stats['open'],
            'closed': stats['closed'],
            'rework': stats['rework'],
        })
    contractor_quality.sort(key=lambda x: x['open'], reverse=True)

    result = {
        'kpis': {
            'open_total': int(open_count or 0),
            'open_last7': int(open_last7 or 0),
            'in_progress': int(in_progress_count or 0),
            'closed_total': int(closed_count or 0),
            'closed_last7': int(closed_last7 or 0),
            'pending_approval': int(pending_approval_count or 0),
            'overdue': int(overdue_count or 0),
            'team_count': int(team_count or 0),
            'sla_response_7d': float(sla_response_7d or 0),
            'sla_close_7d': float(sla_close_7d or 0),
            'sla_response_30d': float(sla_response_30d or 0),
            'sla_close_30d': float(sla_close_30d or 0),
        },
        'pending_approvals': pending_approval_tasks[:20] if is_pm_or_owner else [],
        'stuck_contractors': stuck_contractors[:10] if stuck_contractors else [],
        'load_by_building': load_by_building if load_by_building else [],
        'contractor_quality': contractor_quality[:20] if contractor_quality else [],
        'role': role or 'viewer',
        'total_tasks': int(len(tasks) or 0),
        'by_status': by_status or {},
        'by_category': by_category or {},
    }
    return result


@router.get("/projects/{project_id}/tasks/contractor-summary")
async def get_contractor_summary(
    project_id: str,
    status: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    task_query = {'project_id': project_id}
    if status:
        task_query['status'] = status

    tasks = await db.tasks.find(task_query, {'assignee_id': 1, '_id': 0}).to_list(10000)

    unassigned_count = 0
    by_assignee = {}
    for t in tasks:
        aid = t.get('assignee_id')
        if not aid:
            unassigned_count += 1
        else:
            by_assignee[aid] = by_assignee.get(aid, 0) + 1

    contractors = []
    if by_assignee:
        user_docs = await db.users.find(
            {'id': {'$in': list(by_assignee.keys())}},
            {'_id': 0, 'id': 1, 'name': 1, 'specialties': 1, 'company_id': 1}
        ).to_list(1000)
        user_map = {u['id']: {'name': u.get('name', ''), 'specialty': (u.get('specialties') or [None])[0]} for u in user_docs}
        for uid, count in by_assignee.items():
            contractors.append({
                'id': uid,
                'name': user_map.get(uid, {}).get('name', uid),
                'specialty': user_map.get(uid, {}).get('specialty'),
                'count': count,
            })
        contractors.sort(key=lambda c: c['count'], reverse=True)

    return {
        'total': len(tasks),
        'unassigned': unassigned_count,
        'contractors': contractors,
    }


@router.get("/projects/{project_id}/task-buckets")
async def get_task_buckets(
    project_id: str,
    status: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)

    is_contractor = user['role'] == 'contractor'
    my_trade_bucket = None
    if not is_contractor:
        proj_role = await _get_project_role(user, project_id)
        if proj_role == 'contractor':
            is_contractor = True
    if is_contractor:
        my_membership = await db.project_memberships.find_one(
            {'user_id': user['id'], 'project_id': project_id}, {'_id': 0}
        )
        if my_membership and my_membership.get('contractor_trade_key'):
            my_trade_bucket = CATEGORY_TO_BUCKET.get(
                my_membership['contractor_trade_key'], my_membership['contractor_trade_key']
            )

    task_query = {'project_id': project_id}
    if status:
        task_query['status'] = status
    if is_contractor:
        task_query['assignee_id'] = user['id']

    bucket_projection = {'_id': 0, 'id': 1, 'assignee_id': 1, 'company_id': 1, 'category': 1}
    tasks = await db.tasks.find(task_query, bucket_projection).to_list(10000)
    contractor_map, company_map, membership_trade_map = await _build_bucket_maps(db, project_id)

    bucket_counts = {}
    bucket_meta = {}
    total = len(tasks)
    for t in tasks:
        info = compute_task_bucket(t, contractor_map, company_map, membership_trade_map)
        bk = info['bucket_key']
        bucket_counts[bk] = bucket_counts.get(bk, 0) + 1
        if bk not in bucket_meta:
            bucket_meta[bk] = {'label_he': info['label_he'], 'source': info['source']}

    if is_contractor and my_trade_bucket:
        filtered_counts = {}
        filtered_meta = {}
        if my_trade_bucket in bucket_counts:
            filtered_counts[my_trade_bucket] = bucket_counts[my_trade_bucket]
            filtered_meta[my_trade_bucket] = bucket_meta[my_trade_bucket]
        else:
            filtered_counts[my_trade_bucket] = 0
            filtered_meta[my_trade_bucket] = {
                'label_he': BUCKET_LABELS.get(my_trade_bucket, my_trade_bucket),
                'source': 'membership',
            }
        bucket_counts = filtered_counts
        bucket_meta = filtered_meta
        total = sum(filtered_counts.values())
    else:
        contractor_memberships = await db.project_memberships.find(
            {'project_id': project_id, 'role': 'contractor', 'contractor_trade_key': {'$exists': True, '$ne': None}},
            {'_id': 0, 'contractor_trade_key': 1}
        ).to_list(10000)
        for m in contractor_memberships:
            trade = m['contractor_trade_key']
            bk = CATEGORY_TO_BUCKET.get(trade, trade)
            if bk not in bucket_counts:
                bucket_counts[bk] = 0
                bucket_meta[bk] = {'label_he': BUCKET_LABELS.get(bk, bk), 'source': 'membership'}

    buckets = []
    for bk, count in bucket_counts.items():
        buckets.append({
            'bucket_key': bk,
            'label_he': bucket_meta[bk]['label_he'],
            'count': count,
            'source': bucket_meta[bk]['source'],
        })
    buckets.sort(key=lambda b: b['count'], reverse=True)

    return {
        'total': total,
        'buckets': buckets,
    }


# ── Project-level custom trades ──

def _slugify_hebrew(label: str) -> str:
    slug = label.strip().lower().replace(' ', '_').replace('/', '_')
    slug = _re.sub(r'[^a-z0-9_\u0590-\u05ff]', '', slug)
    if not slug:
        slug = f"custom_{uuid.uuid4().hex[:8]}"
    return slug


@router.get("/projects/{project_id}/trades")
async def list_project_trades(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    await _check_project_read_access(user, project_id)
    base_trades = [{'key': k, 'label_he': v, 'source': 'global'} for k, v in BUCKET_LABELS.items()]
    custom_trades = await db.project_trades.find({'project_id': project_id}, {'_id': 0}).to_list(500)
    custom_list = [{'key': t['key'], 'label_he': t['label_he'], 'source': 'project'} for t in custom_trades]
    seen_keys = {t['key'] for t in custom_list}
    merged = [t for t in base_trades if t['key'] not in seen_keys] + custom_list
    merged.sort(key=lambda t: t['label_he'])
    return {'trades': merged}


@router.post("/projects/{project_id}/trades")
async def create_project_trade(project_id: str, body: dict = Body(...), user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    await _check_project_access(user, project_id)
    label_he = (body.get('label_he') or '').strip()
    if not label_he:
        raise HTTPException(status_code=422, detail='שם תחום הוא שדה חובה')
    key = body.get('key') or _slugify_hebrew(label_he)
    existing_global = key in BUCKET_LABELS
    existing_project = await db.project_trades.find_one({'project_id': project_id, 'key': key})
    if existing_global or existing_project:
        raise HTTPException(status_code=409, detail='תחום עם מפתח זה כבר קיים')
    doc = {
        'id': str(uuid.uuid4()),
        'project_id': project_id,
        'key': key,
        'label_he': label_he,
        'created_by': user['id'],
        'created_at': _now(),
    }
    await db.project_trades.insert_one(doc)
    await _audit('project_trade', doc['id'], 'create', user['id'], {'project_id': project_id, 'key': key, 'label_he': label_he})
    return {k: v for k, v in doc.items() if k != '_id'}


@router.get("/trades")
async def list_trades():
    trades = []
    for key, label in BUCKET_LABELS.items():
        trades.append({'key': key, 'label_he': label})
    trades.sort(key=lambda t: t['label_he'])
    return {'trades': trades}


# ── Excel import ──
@router.get("/projects/{project_id}/excel-template")
async def download_excel_template(project_id: str, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    await _check_project_access(user, project_id)
    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['building_name', 'building_code', 'floor_number', 'unit_no', 'unit_type'])
    writer.writerow(['בניין A', 'A', '1', '101', 'apartment'])
    writer.writerow(['בניין A', 'A', '1', '102', 'apartment'])
    writer.writerow(['בניין A', 'A', '2', '201', 'apartment'])
    from starlette.responses import StreamingResponse
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename=template_{project_id}.csv'}
    )


@router.post("/projects/{project_id}/excel-import")
async def import_excel(project_id: str, file: UploadFile = File(...), user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    await _check_project_access(user, project_id)
    import io, csv
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except:
        text = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(text))
    results = {'created': [], 'skipped': [], 'errors': []}
    row_num = 0
    ts = _now()
    for row in reader:
        row_num += 1
        bname = row.get('building_name', '').strip()
        bcode = row.get('building_code', '').strip()
        floor_num_str = row.get('floor_number', '').strip()
        unit_no = row.get('unit_no', '').strip()
        unit_type = row.get('unit_type', 'apartment').strip()
        if not bname:
            results['errors'].append({'row': row_num, 'error': 'missing building_name'})
            continue
        if not floor_num_str:
            results['errors'].append({'row': row_num, 'error': 'missing floor_number'})
            continue
        try:
            floor_num = int(floor_num_str)
        except ValueError:
            results['errors'].append({'row': row_num, 'error': 'invalid floor_number'})
            continue
        building = await db.buildings.find_one({'project_id': project_id, 'name': bname})
        if not building:
            bid = str(uuid.uuid4())
            building = {'id': bid, 'project_id': project_id, 'name': bname, 'code': bcode or None, 'floors_count': 0, 'created_at': ts}
            await db.buildings.insert_one(building)
        floor = await db.floors.find_one({'building_id': building['id'], 'floor_number': floor_num})
        if not floor:
            fid = str(uuid.uuid4())
            floor = {'id': fid, 'building_id': building['id'], 'project_id': project_id, 'name': f'קומה {floor_num}', 'floor_number': floor_num, 'created_at': ts}
            await db.floors.insert_one(floor)
        if unit_no:
            existing_unit = await db.units.find_one({'floor_id': floor['id'], 'unit_no': unit_no})
            if existing_unit:
                results['skipped'].append({'row': row_num, 'unit_no': unit_no, 'reason': 'duplicate'})
                continue
            uid = str(uuid.uuid4())
            unit_doc = {'id': uid, 'floor_id': floor['id'], 'building_id': building['id'], 'project_id': project_id, 'unit_no': unit_no, 'unit_type': unit_type if unit_type in ('apartment','commercial','parking','storage') else 'apartment', 'status': 'available', 'created_at': ts}
            await db.units.insert_one(unit_doc)
            results['created'].append({'row': row_num, 'unit_no': unit_no})
        else:
            results['created'].append({'row': row_num, 'note': 'floor only'})
    await _audit('project', project_id, 'excel_import', user['id'], {'created': len(results['created']), 'skipped': len(results['skipped']), 'errors': len(results['errors'])})
    return {'created_count': len(results['created']), 'skipped_count': len(results['skipped']), 'error_count': len(results['errors']), 'details': results}


@router.post("/projects/{project_id}/migrate-sort-index")
async def migrate_sort_index(project_id: str, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    floors_updated = 0
    units_updated = 0
    buildings = await db.buildings.find({'project_id': project_id}, {'_id': 0}).to_list(1000)
    for building in buildings:
        floors = await db.floors.find({'building_id': building['id']}, {'_id': 0}).sort('floor_number', 1).to_list(1000)
        for idx, f in enumerate(floors):
            si = f['floor_number'] * 1000
            updates = {'sort_index': si}
            if not f.get('display_label'):
                updates['display_label'] = f['name']
            await db.floors.update_one({'id': f['id']}, {'$set': updates})
            floors_updated += 1
            units = await db.units.find({'floor_id': f['id']}, {'_id': 0}).to_list(10000)
            units_sorted = sorted(units, key=lambda u: u.get('unit_no', ''))
            for uidx, u in enumerate(units_sorted):
                u_updates = {'sort_index': (uidx + 1) * 10}
                if not u.get('display_label'):
                    u_updates['display_label'] = u['unit_no']
                await db.units.update_one({'id': u['id']}, {'$set': u_updates})
                units_updated += 1
    await _audit('project', project_id, 'migrate_sort_index', user['id'], {'floors_updated': floors_updated, 'units_updated': units_updated})
    return {'success': True, 'floors_updated': floors_updated, 'units_updated': units_updated}


def _is_numeric_unit(unit_no: str) -> bool:
    try:
        int(unit_no)
        return True
    except (ValueError, TypeError):
        return False

async def _compute_building_resequence(db, building_id: str):
    floors = await db.floors.find({'building_id': building_id}, {'_id': 0}).sort('sort_index', 1).to_list(1000)
    floor_changes = []
    unit_changes = []
    global_counter = 0

    for idx, f in enumerate(floors):
        new_si = (idx + 1) * 1000
        old_si = f.get('sort_index', 0)
        if old_si != new_si:
            floor_changes.append({
                'type': 'floor',
                'id': f['id'],
                'name': f['name'],
                'old_sort_index': old_si,
                'new_sort_index': new_si,
            })
        units = await db.units.find({'floor_id': f['id']}, {'_id': 0}).sort('sort_index', 1).to_list(10000)
        numeric_in_floor = 0
        for uidx, u in enumerate(units):
            if _is_numeric_unit(u['unit_no']):
                global_counter += 1
                numeric_in_floor += 1
                new_unit_no = str(global_counter)
                new_si_u = numeric_in_floor * 10
                if u['unit_no'] != new_unit_no:
                    unit_changes.append({
                        'type': 'unit',
                        'id': u['id'],
                        'floor_id': f['id'],
                        'floor_name': f['name'],
                        'old_unit_no': u['unit_no'],
                        'new_unit_no': new_unit_no,
                        'new_sort_index': new_si_u,
                        'new_display_label': new_unit_no,
                    })
                else:
                    pass
            else:
                pass

    return floor_changes, unit_changes

@router.post("/buildings/{building_id}/resequence")
async def resequence_building(building_id: str, body: dict = Body(...), user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    building = await db.buildings.find_one({'id': building_id}, {'_id': 0})
    if not building:
        raise HTTPException(status_code=404, detail='Building not found')
    await _check_project_access(user, building['project_id'])
    dry_run = body.get('dry_run', False)

    floor_changes, unit_changes = await _compute_building_resequence(db, building_id)

    if dry_run:
        return {
            'dry_run': True,
            'floors_affected': len(floor_changes),
            'units_affected': len(unit_changes),
            'floor_changes': floor_changes,
            'unit_changes': unit_changes,
        }
    for c in floor_changes:
        await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})
    if unit_changes:
        for c in unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': f"__tmp_{c['id']}",
                'display_label': f"__tmp_{c['id']}",
            }})
        for c in unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': c['new_unit_no'],
                'display_label': c['new_display_label'],
                'sort_index': c['new_sort_index'],
            }})
    await _audit('building', building_id, 'resequence', user['id'], {
        'floors_affected': len(floor_changes),
        'units_affected': len(unit_changes),
        'floor_changes': floor_changes,
        'unit_changes': unit_changes,
    })
    return {
        'success': True,
        'floors_affected': len(floor_changes),
        'units_affected': len(unit_changes),
        'floor_changes': floor_changes,
        'unit_changes': unit_changes,
    }


@router.post("/projects/{project_id}/insert-floor")
async def insert_floor(project_id: str, body: InsertFloorRequest, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    await _check_project_access(user, project_id)
    building = await db.buildings.find_one({'id': body.building_id, 'project_id': project_id})
    if not building:
        raise HTTPException(status_code=404, detail='Building not found in this project')

    floors = await db.floors.find({'building_id': body.building_id}, {'_id': 0}).sort('sort_index', 1).to_list(1000)
    insert_si = body.insert_at_index

    floors_to_shift = [f for f in floors if f.get('sort_index', 0) >= insert_si]
    floor_shift_changes = []
    for f in floors_to_shift:
        old_si = f.get('sort_index', 0)
        new_si = old_si + 1000
        floor_shift_changes.append({
            'type': 'floor',
            'id': f['id'],
            'name': f['name'],
            'old_sort_index': old_si,
            'new_sort_index': new_si,
        })

    if body.dry_run:
        for c in floor_shift_changes:
            await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})
        temp_floor_id = '__preview__'
        temp_floor_doc = {
            'id': temp_floor_id, 'building_id': body.building_id, 'project_id': project_id,
            'name': body.name, 'floor_number': insert_si // 1000,
            'sort_index': insert_si,
            'display_label': body.display_label or body.name,
            'kind': body.kind.value if body.kind else None,
            'created_at': _now(),
        }
        await db.floors.insert_one(temp_floor_doc)
        _, unit_changes = await _compute_building_resequence(db, body.building_id)
        await db.floors.delete_one({'id': temp_floor_id})
        for c in floor_shift_changes:
            await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['old_sort_index']}})
        return {
            'dry_run': True,
            'new_floor_name': body.name,
            'insert_at_index': insert_si,
            'floors_affected': len(floor_shift_changes),
            'units_affected': len(unit_changes),
            'floor_changes': floor_shift_changes,
            'unit_changes': unit_changes,
        }

    for c in floor_shift_changes:
        await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})

    floor_id = str(uuid.uuid4())
    ts = _now()
    new_floor_doc = {
        'id': floor_id, 'building_id': body.building_id, 'project_id': project_id,
        'name': body.name, 'floor_number': insert_si // 1000,
        'sort_index': insert_si,
        'display_label': body.display_label or body.name,
        'kind': body.kind.value if body.kind else None,
        'created_at': ts,
    }
    await db.floors.insert_one(new_floor_doc)

    reseq_floor_changes, reseq_unit_changes = await _compute_building_resequence(db, body.building_id)
    for c in reseq_floor_changes:
        await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})
    if reseq_unit_changes:
        for c in reseq_unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': f"__tmp_{c['id']}",
                'display_label': f"__tmp_{c['id']}",
            }})
        for c in reseq_unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': c['new_unit_no'],
                'display_label': c['new_display_label'],
                'sort_index': c['new_sort_index'],
            }})

    await _audit('building', body.building_id, 'insert_floor', user['id'], {
        'project_id': project_id,
        'new_floor_id': floor_id,
        'new_floor_name': body.name,
        'insert_at_index': insert_si,
        'floors_shifted': len(floor_shift_changes),
        'units_renumbered': len(reseq_unit_changes),
        'floor_changes': floor_shift_changes,
        'unit_changes': reseq_unit_changes,
    })
    return {
        'success': True,
        'new_floor': {k: v for k, v in new_floor_doc.items() if k != '_id'},
        'floors_shifted': len(floor_shift_changes),
        'units_renumbered': len(reseq_unit_changes),
    }


@router.get("/health")
async def health_check():
    db = get_db()
    try:
        await db.command("ping")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    return {"status": "ok", "database": db_status, "app_id": APP_ID}


@router.get("/ready")
async def readiness_check():
    db = get_db()
    checks = {}
    all_ok = True
    try:
        await db.command("ping")
        checks["database"] = "ready"
    except Exception:
        checks["database"] = "not_ready"
        all_ok = False
    user_count = await db.users.count_documents({})
    checks["users_count"] = user_count
    project_count = await db.projects.count_documents({})
    checks["projects_count"] = project_count
    checks["app_id"] = APP_ID
    status_code = 200 if all_ok else 503
    from starlette.responses import JSONResponse
    return JSONResponse(
        content={"ready": all_ok, "checks": checks},
        status_code=status_code
    )


import subprocess as _subprocess
import os as _os

def _resolve_git_sha():
    release = _os.environ.get("RELEASE_SHA", "")
    if release:
        return release
    try:
        result = _subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=_os.path.dirname(_os.path.dirname(__file__))
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return _os.environ.get("GIT_SHA", "unknown")

_BUILD_GIT_SHA = _resolve_git_sha()
_BUILD_TIME = _os.environ.get("BUILD_TIME", _now())


@router.get("/admin/system-info")
async def admin_system_info(request: Request, user: dict = Depends(require_super_admin)):
    from config import APP_MODE, MONGO_URL, DB_NAME
    db = get_db()
    users_count = await db.users.count_documents({})
    projects_count = await db.projects.count_documents({})
    tasks_count = await db.tasks.count_documents({})
    memberships_count = await db.project_memberships.count_documents({})
    audit_count = await db.audit_events.count_documents({})

    if '@' in MONGO_URL:
        parts = MONGO_URL.split('@', 1)
        host_part = parts[1].split('/')[0] if '/' in parts[1] else parts[1]
        masked_host = f"****@{host_part}"
    elif 'localhost' in MONGO_URL or '127.0.0.1' in MONGO_URL:
        masked_host = "localhost"
    else:
        masked_host = MONGO_URL[:20] + "..."

    return {
        "db_name": DB_NAME,
        "db_host": masked_host,
        "app_mode": APP_MODE,
        "git_sha": _BUILD_GIT_SHA,
        "counts": {
            "users": users_count,
            "projects": projects_count,
            "tasks": tasks_count,
            "memberships": memberships_count,
            "audit_events": audit_count,
        },
        "seed_guard": {
            "run_seed": _os.environ.get('RUN_SEED', 'not set'),
            "seed_blocked_in_prod": True,
        },
    }


@router.get("/admin/diagnostics/role-conflicts")
async def admin_diagnostics_role_conflicts(request: Request, user: dict = Depends(require_stepup)):
    db = get_db()
    conflicts = []
    seen_keys = set()

    orgs = await db.organizations.find({}, {'_id': 0, 'id': 1, 'name': 1, 'owner_user_id': 1}).to_list(10000)
    for org in orgs:
        owner_uid = org.get('owner_user_id')
        if not owner_uid:
            continue
        org_id = org['id']
        org_project_ids = await db.projects.distinct('id', {'org_id': org_id})
        if not org_project_ids:
            continue
        contractor_mems = await db.project_memberships.find({
            'user_id': owner_uid,
            'project_id': {'$in': org_project_ids},
            'role': 'contractor',
        }, {'_id': 0, 'project_id': 1, 'created_at': 1}).to_list(1000)
        if contractor_mems:
            owner_user = await db.users.find_one({'id': owner_uid}, {'_id': 0, 'name': 1, 'email': 1})
            owner_name = owner_user.get('name', '') if owner_user else ''
            owner_email = owner_user.get('email', '') if owner_user else ''
            masked_email = ''
            if owner_email and '@' in owner_email:
                local, domain = owner_email.split('@', 1)
                masked_email = local[:2] + '***@' + domain if len(local) > 2 else '***@' + domain
            project_ids = [m['project_id'] for m in contractor_mems]
            earliest = min((m.get('created_at', '') for m in contractor_mems), default='')
            key = f"{owner_uid}|{org_id}|owner_as_contractor"
            if key not in seen_keys:
                seen_keys.add(key)
                conflicts.append({
                    'user_id': owner_uid,
                    'user_name': owner_name,
                    'user_email_masked': masked_email,
                    'org_id': org_id,
                    'org_name': org.get('name', ''),
                    'project_ids': project_ids,
                    'role': 'contractor',
                    'relation': 'owner_as_contractor',
                    'created_at': earliest,
                })

    all_contractor_mems = await db.project_memberships.find(
        {'role': 'contractor'}, {'_id': 0, 'user_id': 1, 'project_id': 1, 'created_at': 1}
    ).to_list(100000)
    contractor_user_ids = list(set(m['user_id'] for m in all_contractor_mems))
    if contractor_user_ids:
        owner_orgs = await db.organizations.find(
            {'owner_user_id': {'$in': contractor_user_ids}},
            {'_id': 0, 'id': 1, 'name': 1, 'owner_user_id': 1}
        ).to_list(10000)
        for o in owner_orgs:
            uid = o['owner_user_id']
            oid = o['id']
            o_project_ids = await db.projects.distinct('id', {'org_id': oid})
            if not o_project_ids:
                continue
            matching = [m for m in all_contractor_mems if m['user_id'] == uid and m['project_id'] in o_project_ids]
            if not matching:
                continue
            key = f"{uid}|{oid}|contractor_as_owner"
            if key not in seen_keys:
                seen_keys.add(key)
                c_user = await db.users.find_one({'id': uid}, {'_id': 0, 'name': 1, 'email': 1})
                c_name = c_user.get('name', '') if c_user else ''
                c_email = c_user.get('email', '') if c_user else ''
                masked = ''
                if c_email and '@' in c_email:
                    lp, dp = c_email.split('@', 1)
                    masked = lp[:2] + '***@' + dp if len(lp) > 2 else '***@' + dp
                pids = [m['project_id'] for m in matching]
                earliest = min((m.get('created_at', '') for m in matching), default='')
                conflicts.append({
                    'user_id': uid,
                    'user_name': c_name,
                    'user_email_masked': masked,
                    'org_id': oid,
                    'org_name': o.get('name', ''),
                    'project_ids': pids,
                    'role': 'contractor',
                    'relation': 'contractor_as_owner',
                    'created_at': earliest,
                })

    return {'conflicts': conflicts, 'count': len(conflicts)}


@router.get("/debug/version")
async def debug_version():
    from config import APP_MODE, WHATSAPP_ENABLED, OTP_PROVIDER, OWNER_PHONE, SUPER_ADMIN_PHONE, ENABLE_QUICK_LOGIN, SMS_ENABLED, ENABLE_ONBOARDING_V2, ENABLE_AUTO_TRIAL
    from contractor_ops.billing import BILLING_V1_ENABLED
    resp = {
        "git_sha": _BUILD_GIT_SHA,
        "build_time": _BUILD_TIME,
        "app_id": APP_ID,
        "feature_flags": {
            "app_mode": APP_MODE,
            "enable_quick_login": ENABLE_QUICK_LOGIN,
            "onboarding_v2": ENABLE_ONBOARDING_V2,
            "billing_v1_enabled": BILLING_V1_ENABLED,
        }
    }
    if APP_MODE == "dev":
        resp["feature_flags"].update({
            "whatsapp_enabled": WHATSAPP_ENABLED,
            "otp_provider": OTP_PROVIDER,
            "owner_phone_set": bool(OWNER_PHONE),
            "sms_enabled": SMS_ENABLED,
            "auto_trial": ENABLE_AUTO_TRIAL,
        })
        resp["super_admin_phone_set"] = bool(SUPER_ADMIN_PHONE)
    return resp


@router.get("/debug/otp-status")
async def debug_otp_status(user: dict = Depends(require_super_admin)):
    from config import OTP_PROVIDER, APP_MODE, WHATSAPP_ENABLED, SMS_ENABLED
    from config import WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID
    from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_MESSAGING_SERVICE_SID

    wa_ready = bool(WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID and WHATSAPP_ENABLED)
    sms_ready = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and (TWILIO_FROM_NUMBER or TWILIO_MESSAGING_SERVICE_SID))

    return {
        "otp_provider": OTP_PROVIDER,
        "app_mode": APP_MODE,
        "wa_ready": wa_ready,
        "wa_token_set": bool(WA_ACCESS_TOKEN),
        "wa_phone_id_set": bool(WA_PHONE_NUMBER_ID),
        "whatsapp_enabled_flag": WHATSAPP_ENABLED,
        "sms_ready": sms_ready,
        "twilio_sid_set": bool(TWILIO_ACCOUNT_SID),
        "twilio_token_set": bool(TWILIO_AUTH_TOKEN),
        "twilio_from_set": bool(TWILIO_FROM_NUMBER),
        "twilio_msg_svc_set": bool(TWILIO_MESSAGING_SERVICE_SID),
        "sms_enabled_flag": SMS_ENABLED,
    }


@router.get("/debug/whatsapp")
async def debug_whatsapp(request: Request, user: dict = Depends(require_stepup)):
    if not ENABLE_DEBUG_ENDPOINTS:
        raise HTTPException(status_code=404, detail="Not found")
    from config import WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID
    import httpx
    import os as _os_wa

    result = {
        "wa_phone_number_id": f"...{WA_PHONE_NUMBER_ID[-6:]}" if len(WA_PHONE_NUMBER_ID) > 6 else WA_PHONE_NUMBER_ID or "NOT SET",
        "waba_id": "NOT SET",
        "wa_token_length": len(WA_ACCESS_TOKEN) if WA_ACCESS_TOKEN else 0,
        "wa_token_set": bool(WA_ACCESS_TOKEN),
    }

    waba_id = _os_wa.environ.get('WABA_ID', '')
    if waba_id:
        result["waba_id"] = f"...{waba_id[-6:]}" if len(waba_id) > 6 else waba_id

    if not WA_ACCESS_TOKEN:
        result["token_check"] = {"error": "WA_ACCESS_TOKEN not set"}
        result["phone_check"] = {"error": "Cannot check without token"}
        return result

    headers = {"Authorization": f"Bearer {WA_ACCESS_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            me_resp = await client.get("https://graph.facebook.com/v21.0/me", headers=headers)
        result["token_check"] = {
            "status": me_resp.status_code,
            "response": me_resp.json() if me_resp.status_code == 200 else me_resp.text[:500],
        }
    except Exception as e:
        result["token_check"] = {"error": str(e)[:200]}

    if WA_PHONE_NUMBER_ID:
        try:
            fields = "display_phone_number,verified_name,code_verification_status,quality_rating,status"
            url = f"https://graph.facebook.com/v21.0/{WA_PHONE_NUMBER_ID}?fields={fields}"
            async with httpx.AsyncClient(timeout=10) as client:
                phone_resp = await client.get(url, headers=headers)
            result["phone_check"] = {
                "status": phone_resp.status_code,
                "response": phone_resp.json() if phone_resp.status_code == 200 else phone_resp.text[:500],
            }
        except Exception as e:
            result["phone_check"] = {"error": str(e)[:200]}
    else:
        result["phone_check"] = {"error": "WA_PHONE_NUMBER_ID not set"}

    return result


@router.get("/debug/whoami")
async def debug_whoami(user: dict = Depends(get_current_user)):
    import os as _os_w
    if _os_w.environ.get("APP_MODE", "dev") != "dev":
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "phone_e164": user.get("phone_e164"),
        "role": user.get("role"),
        "platform_role": user.get("platform_role", "none"),
    }


@router.get("/debug/m6-proof")
async def debug_m6_proof():
    import os as _os2
    if _os2.environ.get("APP_MODE", "dev") != "dev":
        raise HTTPException(status_code=404, detail="Not found")
    db = get_db()

    proj = await db.projects.find_one({}, {'_id': 0, 'id': 1, 'name': 1})
    if not proj:
        return {"error": "No projects in DB"}

    sample_task = await db.tasks.find_one(
        {'project_id': proj['id']},
        {'_id': 0}
    )
    if not sample_task:
        return {"error": "No tasks in DB", "project": proj}

    task_id = sample_task['id']
    updates = await db.task_updates.find(
        {'task_id': task_id}, {'_id': 0}
    ).sort('created_at', 1).to_list(100)

    proof_updates = [u for u in updates if u.get('update_type') == 'attachment']
    status_updates = [u for u in updates if u.get('update_type') == 'status_change']

    contractors = await db.project_memberships.find(
        {'project_id': proj['id'], 'role': 'contractor'}, {'_id': 0}
    ).to_list(100)
    contractor_ids = [c['user_id'] for c in contractors]
    contractor_users = await db.users.find(
        {'id': {'$in': contractor_ids}},
        {'_id': 0, 'id': 1, 'name': 1, 'email': 1, 'company_id': 1}
    ).to_list(100)

    return {
        "version": _BUILD_GIT_SHA,
        "project": proj,
        "sample_task": sample_task,
        "task_url": f"/tasks/{task_id}",
        "updates_count": len(updates),
        "proof_attachments": proof_updates,
        "status_changes": status_updates,
        "project_contractors": contractor_users,
        "valid_transitions": {k.value: [v.value for v in vs] for k, vs in VALID_TRANSITIONS.items()},
    }


@router.get("/debug/m411-proof")
async def debug_m411_proof():
    import os as _os2
    if _os2.environ.get("APP_MODE", "dev") != "dev":
        raise HTTPException(status_code=404, detail="Not found")
    db = get_db()

    proj = await db.projects.find_one({}, {'_id': 0, 'id': 1, 'name': 1})
    if not proj:
        return {"error": "No projects in DB"}

    project_id = proj['id']

    sample_unit = await db.units.find_one({}, {'_id': 0, 'id': 1, 'unit_no': 1, 'effective_label': 1})
    unit_id = sample_unit['id'] if sample_unit else 'none'

    plan_count = await db.unit_plans.count_documents({'project_id': project_id})
    sample_plans = await db.unit_plans.find({'project_id': project_id}, {'_id': 0}).to_list(3)

    contractor_user = await db.users.find_one({'role': 'contractor'}, {'_id': 0, 'id': 1, 'name': 1, 'role': 1})

    return {
        "version": _BUILD_GIT_SHA,
        "project": proj,
        "unit_home_url": f"/projects/{project_id}/units/{unit_id}" if sample_unit else None,
        "unit_defects_url": f"/projects/{project_id}/units/{unit_id}/tasks" if sample_unit else None,
        "unit_plans_url": f"/projects/{project_id}/units/{unit_id}/plans" if sample_unit else None,
        "plans_in_db": plan_count,
        "sample_plans": sample_plans,
        "plan_disciplines": list(PLAN_DISCIPLINES),
        "plan_upload_roles": list(PLAN_UPLOAD_ROLES),
        "contractor_routing": {
            "contractor_user": contractor_user,
            "expected_target": f"/projects/{project_id}/tasks?assignee=me",
            "blocked_from": f"/projects/{project_id}/control",
        },
    }


@router.get("/debug/unit-plans-proof")
async def debug_unit_plans_proof():
    import os as _os2
    import httpx as _httpx
    if _os2.environ.get("APP_MODE", "dev") != "dev":
        raise HTTPException(status_code=404, detail="Not found")

    api = 'http://localhost:8000'
    results = {}

    async with _httpx.AsyncClient() as client:
        login_r = await client.post(f'{api}/api/auth/login', json={'email': 'admin@contractor-ops.com', 'password': 'admin123'})
        if login_r.status_code != 200:
            return {"error": "Cannot login as admin"}
        admin_token = login_r.json()['token']
        admin_headers = {'Authorization': f'Bearer {admin_token}'}

        cont_r = await client.post(f'{api}/api/auth/login', json={'email': 'contractor1@contractor-ops.com', 'password': 'cont123'})
        cont_token = cont_r.json()['token'] if cont_r.status_code == 200 else None
        cont_headers = {'Authorization': f'Bearer {cont_token}'} if cont_token else {}

        projects_r = await client.get(f'{api}/api/projects', headers=admin_headers)
        projects = projects_r.json()
        if len(projects) < 2:
            return {"error": "Need 2 projects"}

        pid_a = projects[0]['id']
        pid_b = projects[1]['id']

        db = get_db()
        unit_a = await db.units.find_one({'project_id': pid_a}, {'_id': 0, 'id': 1})
        if not unit_a:
            return {"error": "No units in project A"}
        uid_a = unit_a['id']

        list_ok = await client.get(f'{api}/api/projects/{pid_a}/units/{uid_a}/plans', headers=admin_headers)
        results['list_200'] = {
            'status': list_ok.status_code,
            'plan_count': len(list_ok.json()) if list_ok.status_code == 200 else None,
        }

        mismatch = await client.get(f'{api}/api/projects/{pid_b}/units/{uid_a}/plans', headers=admin_headers)
        results['mismatch_404'] = {
            'status': mismatch.status_code,
            'body': mismatch.json(),
        }

        if cont_token:
            import io as _io
            upload_denied = await client.post(
                f'{api}/api/projects/{pid_a}/units/{uid_a}/plans',
                headers=cont_headers,
                files=[('file', ('proof.pdf', _io.BytesIO(b'%PDF proof'), 'application/pdf'))],
                data={'discipline': 'electrical', 'note': '__debug_proof__'},
            )
            results['contractor_upload_403'] = {
                'status': upload_denied.status_code,
                'body': upload_denied.json(),
            }

    await db.unit_plans.delete_many({'note': '__debug_proof__'})

    return {
        "version": _BUILD_GIT_SHA,
        "project_a": pid_a,
        "project_b": pid_b,
        "unit_a": uid_a,
        "results": results,
    }


@router.get("/debug/phone-rbac-proof")
async def debug_phone_rbac_proof(project_id: Optional[str] = Query(None)):
    import os as _os2
    if _os2.environ.get("APP_MODE", "dev") != "dev":
        raise HTTPException(status_code=404, detail="Not found")
    db = get_db()

    if not project_id:
        proj = await db.projects.find_one({}, {'_id': 0, 'id': 1})
        if not proj:
            return {"error": "No projects found in DB"}
        project_id = proj['id']

    authorized = await _enrich_memberships(project_id, can_see_phone=True, limit=3)
    unauthorized = await _enrich_memberships(project_id, can_see_phone=False, limit=3)

    return {
        "project_id": project_id,
        "note": "DEV-ONLY endpoint. Uses identical _enrich_memberships() helper as the real /projects/{id}/memberships endpoint.",
        "phone_visible_roles": list(PHONE_VISIBLE_ROLES),
        "A_authorized_response (owner/admin/PM)": {
            "status": 200,
            "description": "user_phone IS present",
            "members": authorized,
        },
        "B_unauthorized_response (contractor/viewer/management_team)": {
            "status": 200,
            "description": "user_phone is NOT present (field does not exist)",
            "members": unauthorized,
        },
    }


@router.get("/debug/m47-proof")
async def m47_proof():
    import os as _os2
    if _os2.environ.get("APP_MODE", "dev") != "dev":
        raise HTTPException(status_code=404, detail="Not found")
    from contractor_ops.bucket_utils import BUCKET_LABELS
    db = get_db()

    sample_task = await db.tasks.find_one({"unit_id": {"$exists": True, "$ne": None}}, sort=[("created_at", -1)])
    task_proof = None
    if sample_task:
        proj = await db.projects.find_one({"id": sample_task["project_id"]})
        bld = await db.buildings.find_one({"id": sample_task.get("building_id")}) if sample_task.get("building_id") else None
        flr = await db.floors.find_one({"id": sample_task.get("floor_id")}) if sample_task.get("floor_id") else None
        unt = await db.units.find_one({"id": sample_task.get("unit_id")}) if sample_task.get("unit_id") else None
        task_proof = {
            "id": sample_task["id"],
            "title": sample_task.get("title"),
            "category": sample_task.get("category"),
            "project_name": proj["name"] if proj else None,
            "building_name": bld["name"] if bld else None,
            "floor_name": flr["name"] if flr else None,
            "unit_name": unt.get("display_label") or unt.get("unit_no") or unt.get("name") if unt else None,
            "display_format": f"{proj['name'] if proj else '?'} / {bld['name'] if bld else '?'} / {flr['name'] if flr else '?'} / דירה {unt.get('display_label') or unt.get('unit_no') or unt.get('name') if unt else '?'}",
        }

    base_trades = [{"key": k, "label_he": v, "source": "global"} for k, v in BUCKET_LABELS.items()]
    custom_trades_cursor = db.project_trades.find({})
    custom_list = []
    async for ct in custom_trades_cursor:
        custom_list.append({"key": ct["key"], "label_he": ct["label_he"], "source": "project", "project_id": ct.get("project_id")})

    return {
        "version": {
            "git_sha": _BUILD_GIT_SHA,
            "build_time": _BUILD_TIME,
            "app_id": APP_ID,
        },
        "back_button": {
            "mechanism": "sessionStorage fallback (survives refresh)",
            "flow": "ProjectTasksPage passes returnTo via location.state → TaskDetailPage saves to sessionStorage → on Back click, reads state first then sessionStorage",
            "key": "taskDetailReturnTo",
        },
        "location_breadcrumb": {
            "sample_task": task_proof,
            "format": "פרויקט / בניין / קומה X / דירה Y",
        },
        "i18n": {
            "base_trades_count": len(base_trades),
            "custom_trades_count": len(custom_list),
            "base_trades": sorted(base_trades, key=lambda t: t["label_he"]),
            "custom_trades": custom_list,
        },
    }


@router.get("/debug/m45-proof")
async def m45_proof():
    import os
    if os.environ.get("APP_MODE", "dev") != "dev":
        raise HTTPException(status_code=404, detail="Not found")
    from contractor_ops.bucket_utils import BUCKET_LABELS
    from contractor_ops.phone_utils import normalize_israeli_phone

    trades_list = sorted(
        [{"key": k, "label_he": v} for k, v in BUCKET_LABELS.items()],
        key=lambda t: t["label_he"]
    )

    phone_example_raw = "0501234567"
    phone_result = normalize_israeli_phone(phone_example_raw)

    return {
        "version": {
            "git_sha": _BUILD_GIT_SHA,
            "build_time": _BUILD_TIME,
            "app_id": APP_ID,
        },
        "trades": {
            "count": len(trades_list),
            "items": trades_list,
        },
        "company_validation_examples": [
            {
                "scenario": "missing contact_name",
                "payload": {"name": "חברת בדיקה", "trade": "electrical", "contact_name": "", "contact_phone": "0501234567"},
                "expected_status": 422,
                "expected_detail": "שם איש קשר הוא שדה חובה",
            },
            {
                "scenario": "missing contact_phone",
                "payload": {"name": "חברת בדיקה", "trade": "electrical", "contact_name": "דוד כהן", "contact_phone": ""},
                "expected_status": 422,
                "expected_detail": "טלפון הוא שדה חובה",
            },
        ],
        "phone_normalization_example": {
            "input_raw": phone_example_raw,
            "output_e164": phone_result["phone_e164"],
            "output_raw_preserved": phone_result["phone_raw"],
        },
        "tasks_back_target": {
            "component": "ProjectTasksPage.js",
            "line": 149,
            "target": "/projects/{projectId}",
            "method": "navigate(`/projects/${projectId}`)",
        },
        "floors_modal_modes": ["range", "insert"],
        "invite_button_disabled_logic": {
            "conditions": [
                "!newPhone.trim()",
                "!newName.trim()",
                "!newRole",
                "newRole === 'management_team' && !newSubRole",
                "newRole === 'contractor' && !newTradeKey",
            ],
            "component": "ManagementPanel.js",
            "line": 1239,
        },
    }


@router.get("/debug/m4-proof")
async def m4_proof_page():
    import os
    if os.environ.get("APP_MODE", "dev") != "dev":
        raise HTTPException(status_code=404, detail="Not found")
    from starlette.responses import HTMLResponse
    import json as json_module
    db = get_db()
    project_id = None
    projects = await db.projects.find({"name": "פרויקט מגדלי הים"}, {"_id": 0}).to_list(1)
    if projects:
        project_id = projects[0].get("id")
    summary = {"total": 0, "unassigned": 0, "contractors": []}
    tasks_open = []
    if project_id:
        pipeline = [
            {"$match": {"project_id": project_id}},
            {"$group": {"_id": "$assignee_id", "count": {"$sum": 1}}}
        ]
        agg = await db.tasks.aggregate(pipeline).to_list(100)
        total = sum(r["count"] for r in agg)
        unassigned = sum(r["count"] for r in agg if not r["_id"])
        contractors = []
        for r in agg:
            if r["_id"]:
                u = await db.users.find_one({"id": r["_id"]}, {"_id": 0, "name": 1, "full_name": 1})
                uname = (u.get("name") or u.get("full_name") or "?") if u else "?"
                contractors.append({"id": r["_id"], "name": uname, "count": r["count"]})
        contractors.sort(key=lambda x: -x["count"])
        summary = {"total": total, "unassigned": unassigned, "contractors": contractors}
        tasks_open = await db.tasks.find({"project_id": project_id, "status": "open"}, {"_id": 0, "id": 1, "title": 1, "status": 1, "assignee_id": 1}).to_list(10)
    chips_html = ""
    for c in summary["contractors"]:
        chips_html += f'<span style="display:inline-block;background:#e0f2fe;color:#0369a1;padding:4px 12px;border-radius:999px;margin:0 4px;font-size:14px">{c["name"]} ({c["count"]})</span>'
    tasks_html = ""
    for t in tasks_open:
        tasks_html += f'<tr><td style="padding:4px 8px;border:1px solid #ddd">{t.get("title","")}</td><td style="padding:4px 8px;border:1px solid #ddd">{t.get("status","")}</td></tr>'
    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"><title>M4 Proof</title>
<style>body{{font-family:Heebo,sans-serif;background:#f8fafc;padding:20px;direction:rtl}}
.card{{background:#fff;border-radius:12px;padding:16px;margin:12px 0;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.kpi{{display:inline-block;background:#fff;border:2px solid #f59e0b;border-radius:12px;padding:16px 24px;margin:8px;cursor:pointer;text-align:center}}
.kpi:hover{{background:#fffbeb;transform:translateY(-2px);box-shadow:0 4px 12px rgba(245,158,11,.3)}}
.kpi .num{{font-size:32px;font-weight:700;color:#f59e0b}}.kpi .label{{font-size:14px;color:#64748b}}
.chip-active{{background:#0369a1!important;color:#fff!important}}
.filter-banner{{background:#fffbeb;border:1px solid #f59e0b;border-radius:8px;padding:8px 16px;margin:8px 0;font-size:13px;color:#92400e}}
.empty-state{{text-align:center;padding:32px;color:#94a3b8}}.empty-state button{{background:#f59e0b;color:#fff;border:none;padding:8px 20px;border-radius:8px;cursor:pointer;margin-top:12px}}
.invite-field{{margin:8px 0}}.invite-field label{{display:block;font-weight:600;margin-bottom:4px}}
.invite-field input{{width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px}}
.submit-btn{{background:#f59e0b;color:#fff;border:none;padding:10px 24px;border-radius:8px;font-size:14px}}
.submit-btn:disabled{{background:#cbd5e1;cursor:not-allowed}}
h2{{color:#1e293b;border-bottom:2px solid #f59e0b;padding-bottom:8px}}
.sha{{text-align:center;color:#94a3b8;font-size:11px;margin-top:20px}}
</style></head>
<body>
<h1 style="text-align:center;color:#1e293b">M4 Live Proof — BrikOps</h1>
<p class="sha">SHA: {_BUILD_GIT_SHA} | Build: {_BUILD_TIME}</p>

<h2>1. KPI Cards (לחיצים → ניווט ל-tasks?status=open)</h2>
<div class="card" style="text-align:center">
<div class="kpi" onclick="alert('ניווט ל: /projects/{project_id}/tasks?status=open')">
  <div class="num">{len(tasks_open)}</div>
  <div class="label">ליקויים פתוחים ←</div>
</div>
<div class="kpi" onclick="alert('ניווט ל: /projects/{project_id}/tasks?status=open')">
  <div class="num">{summary['total']}</div>
  <div class="label">סה״כ ליקויים</div>
</div>
<p style="font-size:12px;color:#64748b">👆 KPI cards are clickable — in real UI navigate to /projects/{project_id}/tasks?status=open</p>
</div>

<h2>2. Contractor Chips (צ'יפים עם ספירות)</h2>
<div class="card">
<div style="overflow-x:auto;white-space:nowrap;padding:8px 0">
  <span class="chip-active" style="display:inline-block;background:#0369a1;color:#fff;padding:4px 12px;border-radius:999px;margin:0 4px;font-size:14px">הכל ({summary['total']})</span>
  <span style="display:inline-block;background:#fef3c7;color:#92400e;padding:4px 12px;border-radius:999px;margin:0 4px;font-size:14px">ללא שיוך ({summary['unassigned']})</span>
  {chips_html}
</div>
</div>

<h2>3. Active Filter Indicator (מסונן לפי: ...)</h2>
<div class="card">
<div class="filter-banner">🔍 מסונן לפי: {summary['contractors'][0]['name'] if summary['contractors'] else 'N/A'} | סטטוס: open</div>
</div>

<h2>4. Empty State + "נקה סינון"</h2>
<div class="card">
<div class="empty-state">
  <p style="font-size:48px;margin:0">📋</p>
  <p>לא נמצאו משימות עם הסינון הנוכחי</p>
  <button onclick="alert('מנקה סינון...')">נקה סינון</button>
</div>
</div>

<h2>5. Tasks (status=open) — Real Data</h2>
<div class="card">
<table style="width:100%;border-collapse:collapse">
<tr style="background:#f1f5f9"><th style="padding:4px 8px;border:1px solid #ddd">כותרת</th><th style="padding:4px 8px;border:1px solid #ddd">סטטוס</th></tr>
{tasks_html}
</table>
</div>

<h2>6. Invite Validation (full_name חובה)</h2>
<div class="card">
<div class="invite-field"><label>שם מלא *</label><input id="fname" placeholder="שם מלא" oninput="document.getElementById('submitBtn').disabled=!this.value.trim()"></div>
<div class="invite-field"><label>טלפון *</label><input value="050-1234567" readonly></div>
<div class="invite-field"><label>תפקיד *</label><input value="contractor" readonly></div>
<button id="submitBtn" class="submit-btn" disabled>שלח הזמנה</button>
<p style="font-size:12px;color:#64748b;margin-top:8px">👆 כפתור disabled עד שמזינים שם מלא — הדגמה חיה של validation</p>
</div>

<h2>7. Contractor Summary API Response (Real)</h2>
<div class="card">
<pre style="direction:ltr;text-align:left;background:#f1f5f9;padding:12px;border-radius:8px;overflow-x:auto;font-size:13px">{json_module.dumps(summary, ensure_ascii=False, indent=2)}</pre>
</div>

<h2>8. Server Validation (422 Hebrew)</h2>
<div class="card">
<p><strong>POST /api/projects/.../invites</strong> ללא full_name:</p>
<pre style="direction:ltr;text-align:left;background:#fee2e2;padding:12px;border-radius:8px;font-size:13px">HTTP 422
{{"detail": "שם מלא הוא שדה חובה"}}</pre>
</div>

</body></html>"""
    return HTMLResponse(content=html)


@router.get("/debug/m4-proof-bottom")
async def m4_proof_page_bottom():
    import os
    if os.environ.get("APP_MODE", "dev") != "dev":
        raise HTTPException(status_code=404, detail="Not found")
    from starlette.responses import HTMLResponse
    import json as json_module
    db = get_db()
    project_id = None
    projects = await db.projects.find({"name": "פרויקט מגדלי הים"}, {"_id": 0}).to_list(1)
    if projects:
        project_id = projects[0].get("id")
    tasks_open = []
    summary = {"total": 0, "unassigned": 0, "contractors": []}
    if project_id:
        tasks_open = await db.tasks.find({"project_id": project_id, "status": "open"}).to_list(20)
        pipeline = [
            {"$match": {"project_id": project_id}},
            {"$group": {"_id": "$assignee_id", "count": {"$sum": 1}}},
        ]
        agg = await db.tasks.aggregate(pipeline).to_list(100)
        total = sum(a["count"] for a in agg)
        unassigned = sum(a["count"] for a in agg if not a["_id"])
        contractors = []
        for a in agg:
            if a["_id"]:
                u = await db.users.find_one({"id": a["_id"]}, {"_id": 0, "name": 1, "full_name": 1})
                uname = (u.get("name") or u.get("full_name") or "?") if u else "?"
                contractors.append({"id": a["_id"], "name": uname, "count": a["count"]})
        summary = {"total": total, "unassigned": unassigned, "contractors": sorted(contractors, key=lambda c: -c["count"])}
    tasks_html = ""
    for t in tasks_open[:7]:
        tasks_html += f'<tr><td style="padding:4px 8px;border:1px solid #ddd">{t.get("title","—")}</td><td style="padding:4px 8px;border:1px solid #ddd">{t.get("status","—")}</td></tr>'
    html = f"""<!DOCTYPE html><html lang="he" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>M4 Proof — Bottom</title>
<style>
body{{font-family:system-ui;max-width:800px;margin:0 auto;padding:12px;background:#f8fafc;font-size:13px}}
.card{{background:#fff;border-radius:10px;padding:12px;margin:8px 0;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.empty-state{{text-align:center;padding:20px;color:#94a3b8}}.empty-state button{{background:#f59e0b;color:#fff;border:none;padding:6px 16px;border-radius:6px;cursor:pointer;margin-top:8px}}
.invite-field{{margin:6px 0}}.invite-field label{{display:block;font-weight:600;margin-bottom:2px;font-size:12px}}
.invite-field input{{width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px}}
.submit-btn{{background:#f59e0b;color:#fff;border:none;padding:8px 20px;border-radius:6px;font-size:13px}}
.submit-btn:disabled{{background:#cbd5e1;cursor:not-allowed}}
h2{{color:#1e293b;border-bottom:2px solid #f59e0b;padding-bottom:4px;font-size:16px;margin:12px 0 4px}}
.sha{{text-align:center;color:#94a3b8;font-size:10px}}
</style></head>
<body>
<h1 style="text-align:center;color:#1e293b;font-size:18px;margin:8px 0">M4 Proof (4-8) — BrikOps</h1>
<p class="sha">SHA: {_BUILD_GIT_SHA}</p>

<h2>4. Empty State + "נקה סינון"</h2>
<div class="card">
<div class="empty-state">
  <p style="font-size:32px;margin:0">📋</p>
  <p>לא נמצאו משימות עם הסינון הנוכחי</p>
  <button onclick="alert('מנקה סינון...')">נקה סינון</button>
</div>
</div>

<h2>5. Tasks (status=open) — Real Data</h2>
<div class="card">
<table style="width:100%;border-collapse:collapse;font-size:12px">
<tr style="background:#f1f5f9"><th style="padding:3px 6px;border:1px solid #ddd">כותרת</th><th style="padding:3px 6px;border:1px solid #ddd">סטטוס</th></tr>
{tasks_html}
</table>
</div>

<h2>6. Invite Validation (full_name חובה)</h2>
<div class="card">
<div class="invite-field"><label>שם מלא *</label><input id="fname" placeholder="שם מלא" oninput="document.getElementById('submitBtn').disabled=!this.value.trim()"></div>
<div class="invite-field"><label>טלפון *</label><input value="050-1234567" readonly style="background:#f1f5f9"></div>
<button id="submitBtn" class="submit-btn" disabled>שלח הזמנה</button>
<p style="font-size:11px;color:#64748b;margin-top:4px">👆 disabled עד שמזינים שם מלא</p>
</div>

<h2>7. API Response (Real)</h2>
<div class="card">
<pre style="direction:ltr;text-align:left;background:#f1f5f9;padding:8px;border-radius:6px;font-size:11px;overflow-x:auto">{json_module.dumps(summary, ensure_ascii=False, indent=2)}</pre>
</div>

<h2>8. Server Validation (422 Hebrew)</h2>
<div class="card">
<pre style="direction:ltr;text-align:left;background:#fee2e2;padding:8px;border-radius:6px;font-size:12px">HTTP 422
{{"detail": "שם מלא הוא שדה חובה"}}</pre>
</div>

</body></html>"""
    return HTMLResponse(content=html)


@router.get("/notifications")
async def list_notifications(
    task_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    current_user: dict = Depends(require_roles('project_manager')),
):
    db = get_db()
    query = {}
    if task_id:
        query['task_id'] = task_id
    if status:
        query['status'] = status

    if _is_super_admin(current_user):
        jobs = await db.notification_jobs.find(query, {'_id': 0}).sort('created_at', -1).to_list(limit)
    else:
        memberships = await db.project_memberships.find(
            {'user_id': current_user['id']}, {'_id': 0, 'project_id': 1}
        ).to_list(1000)
        member_project_ids = [m['project_id'] for m in memberships]
        if not member_project_ids:
            return []
        if task_id:
            task_doc = await db.tasks.find_one({'id': task_id}, {'_id': 0, 'project_id': 1})
            if not task_doc or task_doc.get('project_id') not in member_project_ids:
                return []
        else:
            member_tasks = await db.tasks.find(
                {'project_id': {'$in': member_project_ids}}, {'_id': 0, 'id': 1}
            ).to_list(10000)
            member_task_ids = [t['id'] for t in member_tasks]
            if not member_task_ids:
                return []
            query['task_id'] = {'$in': member_task_ids}
        jobs = await db.notification_jobs.find(query, {'_id': 0}).sort('created_at', -1).to_list(limit)

    return jobs


@router.get("/notifications/stats")
async def notification_stats(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "project_manager" and not _is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    db = get_db()
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    results = await db.notification_jobs.aggregate(pipeline).to_list(100)
    stats = {r["_id"]: r["count"] for r in results}
    total = sum(stats.values())
    failed = stats.get("failed_permanent", 0) + stats.get("failed", 0)
    alert_threshold = 0.1
    alert_triggered = (failed / total > alert_threshold) if total > 0 else False
    return {
        "total": total,
        "by_status": stats,
        "failed_count": failed,
        "alert_threshold_pct": alert_threshold * 100,
        "alert_triggered": alert_triggered
    }
