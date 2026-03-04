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
    ProjectMembershipSummary, OrgSummary,
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


@router.post("/billing/org/{org_id}/checkout")
async def billing_checkout(org_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת ניהול חיוב')
    raise HTTPException(status_code=501, detail='Credit card payment coming soon', headers={'X-Feature': 'stripe_checkout'})


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
            from contractor_ops.billing import check_org_pm_role
            is_pm = await check_org_pm_role(user['id'], org_id)
            if not is_pm:
                raise HTTPException(status_code=403, detail='אין הרשאת עדכון חיוב פרויקט')
            pm_project = await db.project_memberships.find_one(
                {'user_id': user['id'], 'project_id': project_id, 'role': 'project_manager'},
                {'_id': 0}
            )
            if not pm_project:
                raise HTTPException(status_code=403, detail='אין הרשאת עדכון חיוב פרויקט זה')
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


PLAN_DISCIPLINES = ('electrical', 'plumbing', 'architecture', 'construction', 'hvac', 'fire_protection')
PLAN_UPLOAD_ROLES = ('project_manager', 'management_team')


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
