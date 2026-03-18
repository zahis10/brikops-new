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
import jwt

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
                'require': ['exp', 'iat', 'iss'],
            },
            leeway=JWT_CLOCK_SKEW_SECONDS,
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
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f'Invalid token: {str(e)}')


def require_roles(*roles: str):
    async def checker(user: dict = Depends(get_current_user)):
        if user['role'] not in roles:
            raise HTTPException(status_code=403, detail='Insufficient permissions')
        return user
    return checker


async def _check_admin_rate_limit(key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    from pymongo import ReturnDocument
    from pymongo.errors import DuplicateKeyError
    db = get_db()
    now = datetime.now(timezone.utc)
    new_expires = now + timedelta(seconds=window_seconds)
    pipeline = [
        {"$set": {
            "count": {"$cond": {
                "if": {"$lte": [{"$ifNull": ["$expires_at", now - timedelta(seconds=1)]}, now]},
                "then": 1,
                "else": {"$add": [{"$ifNull": ["$count", 0]}, 1]},
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
                {"kind": "admin_rl", "key": key},
                pipeline,
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            return result["count"] <= max_requests
        except DuplicateKeyError:
            if attempt == 0:
                continue
            return False


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
    if not await _check_admin_rate_limit(f"admin:{user.get('id', '')}:{method}", max_requests=rl_max, window_seconds=60):
        await _audit_admin_access(user.get('id', ''), route, method, 429, ip, ua, 'rate_limited')
        raise HTTPException(status_code=429, detail='יותר מדי בקשות. נסה שוב בעוד דקה.')

    sa_check = is_super_admin_phone(user_phone)
    if not sa_check['matched']:
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


async def _check_structure_admin(user: dict, project_id: str):
    if _is_super_admin(user):
        return True
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project or not project.get('org_id'):
        raise HTTPException(status_code=403, detail='אין הרשאה לשנות מבנה פרויקט זה')
    org_id = project['org_id']
    org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'owner_user_id': 1})
    if org and org.get('owner_user_id') == user['id']:
        return True
    org_mem = await db.organization_memberships.find_one(
        {'org_id': org_id, 'user_id': user['id']}, {'_id': 0, 'role': 1}
    )
    if org_mem and org_mem.get('role') in ('owner', 'billing_admin'):
        return True
    raise HTTPException(status_code=403, detail='רק בעל הארגון או מנהל חיוב יכולים לשנות מבנה')


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




PHONE_VISIBLE_ROLES = ('project_manager', 'management_team')


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
