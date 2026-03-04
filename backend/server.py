from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
import os
import sys
import uuid
import logging
from datetime import datetime, timezone

from config import (
    MONGO_URL, DB_NAME, APP_ID, APP_MODE,
    WHATSAPP_ENABLED, WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID,
    WA_TEMPLATE_NEW_DEFECT, WA_TEMPLATE_LANG,
    WA_TEMPLATE_INVITE, WA_TEMPLATE_INVITE_LANG,
    WA_WEBHOOK_VERIFY_TOKEN,
    META_APP_SECRET,
    OWNER_PHONE, OTP_PROVIDER,
    JWT_SECRET, ENABLE_QUICK_LOGIN,
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER,
    OTP_TTL_SECONDS, OTP_MAX_ATTEMPTS, OTP_RATE_LIMIT_SECONDS,
    STEPUP_EMAIL, SMTP_USER, SMTP_PASS,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_motor_opts = {
    "serverSelectionTimeoutMS": 10000,
    "connectTimeoutMS": 10000,
    "socketTimeoutMS": 20000,
    "maxPoolSize": 30,
    "maxIdleTimeMS": 60000,
    "retryWrites": True,
}
client = AsyncIOMotorClient(MONGO_URL, **_motor_opts)
db = client[DB_NAME]

_enable_docs = os.environ.get('ENABLE_API_DOCS', 'true').lower() != 'false'

app = FastAPI(
    title="BrikOps API",
    version="1.0.0",
    docs_url="/api/docs" if _enable_docs else None,
    openapi_url="/api/openapi.json" if _enable_docs else None,
    redoc_url=None,
)

import time as _time

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
    request.state.request_id = request_id
    start = _time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((_time.perf_counter() - start) * 1000, 1)
        logger.warning(
            f"[SLOW-ERR] rid={request_id} {request.method} {request.url.path} "
            f"time={elapsed_ms}ms (exception)"
        )
        raise
    elapsed_ms = round((_time.perf_counter() - start) * 1000, 1)
    response.headers["x-response-time-ms"] = str(elapsed_ms)
    response.headers["x-request-id"] = request_id
    if elapsed_ms > 800:
        logger.warning(
            f"[SLOW] rid={request_id} {request.method} {request.url.path} "
            f"status={response.status_code} time={elapsed_ms}ms"
        )
    return response

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/debug/db-ping")
async def debug_db_ping():
    import socket
    results = {}
    for i in range(3):
        t0 = _time.perf_counter()
        await db.command("ping")
        ms = round((_time.perf_counter() - t0) * 1000, 1)
        results[f"ping_{i+1}_ms"] = ms
    avg = round(sum(results.values()) / len(results), 1)
    host_info = {}
    try:
        mongo_host = db.client.address[0] if db.client.address else "unknown"
        host_info["mongo_host"] = mongo_host
        host_info["mongo_port"] = db.client.address[1] if db.client.address else 0
    except Exception:
        host_info["mongo_host"] = "unknown"
    try:
        host_info["server_hostname"] = socket.gethostname()
    except Exception:
        pass
    return {
        **results,
        "avg_ping_ms": avg,
        "pool_size": db.client.options.pool_options.max_pool_size,
        **host_info,
        "db_name": DB_NAME,
    }

from contractor_ops.router import router as ops_router, set_db, require_roles, get_current_user
from contractor_ops.billing import set_billing_db
from contractor_ops.billing_plans import set_plans_db
from contractor_ops.invoicing import set_invoicing_db
set_db(db)
set_billing_db(db)
set_plans_db(db)
set_invoicing_db(db)
app.include_router(ops_router)

from contractor_ops.notification_service import WhatsAppClient, NotificationEngine
from contractor_ops.notification_router import (
    create_notification_router, set_engine, set_wa_verify_token, set_meta_app_secret,
)

wa_client = WhatsAppClient(
    access_token=WA_ACCESS_TOKEN,
    phone_number_id=WA_PHONE_NUMBER_ID,
    template_name=WA_TEMPLATE_NEW_DEFECT,
    template_lang=WA_TEMPLATE_LANG,
    enabled=WHATSAPP_ENABLED,
)
notification_engine = NotificationEngine(
    db, wa_client,
    invite_template_name=WA_TEMPLATE_INVITE,
    invite_template_lang=WA_TEMPLATE_INVITE_LANG,
)
set_engine(notification_engine)
set_wa_verify_token(WA_WEBHOOK_VERIFY_TOKEN)
set_meta_app_secret(META_APP_SECRET)

from contractor_ops.router import set_notification_engine
set_notification_engine(notification_engine)

notify_router = create_notification_router(require_roles, get_current_user)
app.include_router(notify_router)

from contractor_ops.sms_service import SMSClient
from config import SMS_ENABLED, TWILIO_MESSAGING_SERVICE_SID
sms_client = SMSClient(
    account_sid=TWILIO_ACCOUNT_SID if SMS_ENABLED else '',
    auth_token=TWILIO_AUTH_TOKEN if SMS_ENABLED else '',
    from_number=TWILIO_FROM_NUMBER,
    messaging_service_sid=TWILIO_MESSAGING_SERVICE_SID,
    db=db,
)
notification_engine.sms_client = sms_client

from contractor_ops.otp_service import OTPService
from contractor_ops.onboarding_router import (
    create_onboarding_router, set_otp_service, set_onboarding_db,
)

from config import SMS_MODE, OTP_RESEND_MAX_15MIN, OTP_RESEND_MAX_DAILY
otp_service = OTPService(
    db, sms_client=sms_client,
    ttl_seconds=OTP_TTL_SECONDS,
    max_attempts=OTP_MAX_ATTEMPTS,
    rate_limit_seconds=OTP_RATE_LIMIT_SECONDS,
    resend_max_15min=OTP_RESEND_MAX_15MIN,
    resend_max_daily=OTP_RESEND_MAX_DAILY,
    sms_mode=SMS_MODE,
    app_mode=APP_MODE,
)
logger.info(f"[STARTUP] SMS_MODE={SMS_MODE} APP_MODE={APP_MODE} SMS_ENABLED={SMS_ENABLED} SMS_CLIENT_ENABLED={sms_client.enabled}")
set_otp_service(otp_service)
from contractor_ops.router import set_router_otp_service
set_router_otp_service(otp_service)
set_onboarding_db(db)

onboarding_router = create_onboarding_router(get_current_user, require_roles)
app.include_router(onboarding_router)

from contractor_ops.archive_router import router as archive_router
app.include_router(archive_router)

from contractor_ops.wa_login import router as wa_login_router, set_wa_login_db
set_wa_login_db(db)
app.include_router(wa_login_router)

from contractor_ops.member_management import router as member_mgmt_router
app.include_router(member_mgmt_router)

from contractor_ops.identity_service import set_identity_db
set_identity_db(db)
from contractor_ops.identity_router import router as identity_router
app.include_router(identity_router)

from contractor_ops.qc_router import router as qc_router, notif_router as qc_notif_router
app.include_router(qc_router)
app.include_router(qc_notif_router)

from contractor_ops.debug_router import router as debug_router
app.include_router(debug_router)

from contractor_ops.excel_router import router as excel_router
app.include_router(excel_router)

from contractor_ops.plans_router import router as plans_router
app.include_router(plans_router)

from contractor_ops.ownership_transfer import (
    create_transfer_router, set_transfer_db, set_transfer_sms_client,
    set_transfer_otp_service, ensure_indexes as ensure_transfer_indexes,
)
set_transfer_db(db)
set_transfer_sms_client(sms_client)
set_transfer_otp_service(otp_service)
transfer_router = create_transfer_router(get_current_user)
app.include_router(transfer_router)


async def create_indexes():
    try:
        await db.tasks.create_index([
            ("project_id", 1), ("building_id", 1), ("floor_id", 1),
            ("unit_id", 1), ("status", 1), ("due_date", 1)
        ])
        await db.tasks.create_index([("company_id", 1), ("assignee_id", 1), ("status", 1)])
        await db.tasks.create_index([("project_id", 1), ("status", 1), ("updated_at", -1)])
        await db.tasks.create_index([("project_id", 1), ("assignee_id", 1), ("status", 1)])
        await db.tasks.create_index([("assignee_id", 1), ("status", 1), ("updated_at", -1)])
        await db.tasks.create_index("updated_at")
        await db.task_updates.create_index([("task_id", 1), ("created_at", -1)])
        await db.units.create_index(
            [("project_id", 1), ("building_id", 1), ("floor_id", 1), ("unit_no", 1)],
            unique=True
        )
        await db.audit_events.create_index([("entity_type", 1), ("entity_id", 1), ("created_at", -1)])
        await db.users.create_index("email", unique=True, sparse=True)
        await db.projects.create_index("code", unique=True)
        await db.buildings.create_index("project_id")
        await db.floors.create_index("building_id")
        await db.task_status_history.create_index([("task_id", 1), ("created_at", -1)])
        await db.companies.create_index("specialties")
        await db.users.create_index([("role", 1), ("company_id", 1)])
        await db.users.create_index("specialties")
        await db.notification_jobs.create_index([("task_id", 1), ("created_at", -1)])
        await db.notification_jobs.create_index("idempotency_key", unique=True, sparse=True)
        await db.notification_jobs.create_index([("status", 1), ("next_retry_at", 1)])
        await db.notification_jobs.create_index("provider_message_id", sparse=True)
        await db.users.create_index("phone_e164", unique=True, sparse=True)
        await db.otp_codes.create_index("phone", unique=True)
        await db.otp_codes.create_index("expires_at", expireAfterSeconds=600)
        await db.join_requests.create_index([("project_id", 1), ("status", 1)])
        await db.join_requests.create_index("user_id")
        await db.project_memberships.create_index([("project_id", 1), ("user_id", 1)], unique=True)
        await db.project_memberships.create_index([("project_id", 1), ("role", 1)])
        await db.floors.create_index([("building_id", 1), ("sort_index", 1)])
        await db.units.create_index([("floor_id", 1), ("sort_index", 1)])
        await db.whatsapp_events.create_index([("received_at", -1)])
        await db.whatsapp_events.create_index("wa_message_id", sparse=True)
        await db.whatsapp_events.create_index("event_type")
        await db.sms_events.create_index([("created_at", -1)])
        await db.sms_events.create_index("to_phone")
        await db.projects.create_index("join_code", unique=True, sparse=True)
        await db.invites.create_index("token", unique=True, sparse=True)
        await db.invites.create_index([("target_phone", 1), ("status", 1)])
        await db.wa_login_tokens.create_index("token_hash", unique=True)
        await db.wa_login_tokens.create_index("expires_at", expireAfterSeconds=0)
        await db.users.create_index("email_verify_token", sparse=True)
        await db.users.create_index("password_reset_token", sparse=True)
        logger.info("[INDEXES] All MongoDB indexes created successfully")
    except Exception as e:
        logger.warning(f"[INDEXES] Index creation warning: {e}")


_DEMO_USERS = [
    {'email': 'pm@contractor-ops.com', 'password': 'pm123', 'name': 'מנהל פרויקט', 'role': 'project_manager', 'phone_e164': '+972500000002'},
    {'email': 'sitemanager@contractor-ops.com', 'password': 'mgmt123', 'name': 'מנהל עבודה', 'role': 'management_team', 'phone_e164': '+972500000010'},
    {'email': 'contractor1@contractor-ops.com', 'password': 'cont123', 'name': 'קבלן חשמל', 'role': 'contractor', 'phone_e164': '+972500100000'},
    {'email': 'viewer@contractor-ops.com', 'password': 'view123', 'name': 'צופה', 'role': 'viewer', 'phone_e164': '+972500000099'},
    {'email': 'superadmin@brikops.dev', 'password': 'super123', 'name': 'Super Admin', 'role': 'project_manager', 'phone_e164': '+972540000001'},
]

async def ensure_demo_users():
    import bcrypt as _bcrypt
    created = 0
    updated = 0
    for demo in _DEMO_USERS:
        existing = await db.users.find_one({'email': demo['email']}, {'_id': 0, 'id': 1, 'password_hash': 1})
        if existing:
            if not existing.get('password_hash') or not existing['password_hash'].startswith('$2'):
                pw_hash = _bcrypt.hashpw(demo['password'].encode(), _bcrypt.gensalt()).decode()
                await db.users.update_one({'id': existing['id']}, {'$set': {'password_hash': pw_hash}})
                updated += 1
        else:
            user_id = str(uuid.uuid4())
            pw_hash = _bcrypt.hashpw(demo['password'].encode(), _bcrypt.gensalt()).decode()
            await db.users.insert_one({
                'id': user_id, 'email': demo['email'], 'password_hash': pw_hash,
                'name': demo['name'], 'role': demo['role'], 'phone_e164': demo['phone_e164'],
                'user_status': 'active', 'company_id': None,
                'preferred_language': 'he',
                'created_at': datetime.now(timezone.utc).isoformat(),
            })
            created += 1
    if created or updated:
        logger.info(f"[DEMO-USERS] Ensured demo users: created={created} updated={updated}")
    else:
        logger.info("[DEMO-USERS] All demo users already exist")


async def seed_super_admin_user():
    from config import SUPER_ADMIN_PHONE, APP_MODE
    if APP_MODE != 'dev':
        logger.warning("[SEED] seed_super_admin_user() blocked — APP_MODE is not 'dev'")
        return
    if not SUPER_ADMIN_PHONE:
        return
    existing = await db.users.find_one({'phone_e164': SUPER_ADMIN_PHONE})
    if existing:
        return
    import uuid, bcrypt, asyncio
    from datetime import datetime, timezone
    from contractor_ops.billing import create_organization, create_trial_subscription
    user_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    pw_hash = await loop.run_in_executor(None, lambda: bcrypt.hashpw(b'super123', bcrypt.gensalt()).decode())
    await db.users.insert_one({
        'id': user_id,
        'name': 'Super Admin',
        'email': 'superadmin@brikops.dev',
        'password_hash': pw_hash,
        'phone_e164': SUPER_ADMIN_PHONE,
        'role': 'project_manager',
        'platform_role': 'none',
        'status': 'active',
        'company': 'BrikOps',
        'created_at': datetime.now(timezone.utc).isoformat(),
    })
    org = await create_organization(user_id, "BrikOps Admin")
    await create_trial_subscription(org['id'], trial_days=30)
    logger.info(f"[DEV-SEED] Created super admin user {user_id} + org {org['id']} (****{SUPER_ADMIN_PHONE[-4:]})")


async def bootstrap_super_admin():
    from config import SUPER_ADMIN_PHONE
    try:
        await db.users.update_many(
            {'platform_role': 'super_admin'},
            {'$set': {'platform_role': 'none'}}
        )

        if not SUPER_ADMIN_PHONE:
            logger.error("[SUPER_ADMIN] SUPER_ADMIN_PHONE not set — no super admin configured!")
            return

        user = await db.users.find_one({'phone_e164': SUPER_ADMIN_PHONE}, {'_id': 0, 'id': 1, 'name': 1})
        if not user:
            logger.error(f"[SUPER_ADMIN] No user found with phone ****{SUPER_ADMIN_PHONE[-4:]} — super admin NOT set!")
            return

        await db.users.update_one(
            {'id': user['id']},
            {'$set': {'platform_role': 'super_admin'}}
        )
        logger.info(f"[SUPER_ADMIN] Set platform_role=super_admin for user {user['id']} (****{SUPER_ADMIN_PHONE[-4:]})")
    except Exception as e:
        logger.error(f"[SUPER_ADMIN] Bootstrap error: {e}")


async def migrate_remove_owner_admin_roles():
    try:
        r1 = await db.users.update_many(
            {'role': {'$in': ['owner', 'admin']}},
            {'$set': {'role': 'project_manager'}}
        )
        r2 = await db.organization_memberships.update_many(
            {'role': {'$in': ['owner', 'admin']}},
            {'$set': {'role': 'project_manager'}}
        )
        r3 = await db.project_memberships.update_many(
            {'role': {'$in': ['owner', 'admin']}},
            {'$set': {'role': 'project_manager'}}
        )
        if r1.modified_count or r2.modified_count or r3.modified_count:
            logger.info(f"[MIGRATE-ROLES] Migrated owner/admin → project_manager: users={r1.modified_count}, org_memberships={r2.modified_count}, project_memberships={r3.modified_count}")
        else:
            logger.info("[MIGRATE-ROLES] No owner/admin roles to migrate")
    except Exception as e:
        logger.warning(f"[MIGRATE-ROLES] Migration warning: {e}")


async def auto_migrate_sort_index():
    try:
        sample = await db.floors.find_one({'sort_index': {'$exists': False}})
        if not sample:
            logger.info("[MIGRATE] All floors already have sort_index")
            return
        floors_updated = 0
        units_updated = 0
        async for f in db.floors.find({'sort_index': {'$exists': False}}):
            si = f.get('floor_number', 0) * 1000
            updates = {'sort_index': si}
            if not f.get('display_label'):
                updates['display_label'] = f.get('name', '')
            await db.floors.update_one({'_id': f['_id']}, {'$set': updates})
            floors_updated += 1
        floor_unit_counters = {}
        async for u in db.units.find({'sort_index': {'$exists': False}}).sort('unit_no', 1):
            fid = u.get('floor_id', '')
            if fid not in floor_unit_counters:
                floor_unit_counters[fid] = 0
            floor_unit_counters[fid] += 1
            try:
                si = int(u.get('unit_no', '0')) * 10
            except (ValueError, TypeError):
                si = floor_unit_counters[fid] * 10
            updates = {'sort_index': si}
            if not u.get('display_label'):
                updates['display_label'] = u.get('unit_no', '')
            await db.units.update_one({'_id': u['_id']}, {'$set': updates})
            units_updated += 1
        logger.info(f"[MIGRATE] Auto-migrated sort_index: {floors_updated} floors, {units_updated} units")
    except Exception as e:
        logger.warning(f"[MIGRATE] Auto-migration warning: {e}")


async def migrate_billing_orgs():
    from contractor_ops.billing import (
        create_organization, create_trial_subscription, migrate_existing_projects,
    )
    try:
        sample = await db.organizations.find_one()
        if sample:
            logger.info("[BILLING-MIGRATE] Organizations already exist, skipping migration")
            return

        owners = await db.users.find(
            {'role': {'$in': ['owner', 'admin']}},
            {'_id': 0, 'id': 1, 'name': 1, 'role': 1}
        ).to_list(100)

        if not owners:
            logger.info("[BILLING-MIGRATE] No owner/admin users found, skipping")
            return

        for owner in owners:
            org = await create_organization(owner['id'], f"הארגון של {owner.get('name', '')}")
            sub = await create_trial_subscription(org['id'], trial_days=30)
            count = await migrate_existing_projects(owner['id'], org['id'])
            logger.info(f"[BILLING-MIGRATE] Created org for {owner['id']}: org={org['id']}, projects_migrated={count}")

        await db.subscriptions.create_index("org_id", unique=True)
        await db.organization_memberships.create_index([("org_id", 1), ("user_id", 1)], unique=True)
        await db.organization_memberships.create_index("user_id")
        await db.project_billing.create_index("project_id", unique=True)
        await db.project_billing.create_index("org_id")
        await db.billing_plans.create_index("id", unique=True)
        logger.info("[BILLING-MIGRATE] Billing migration complete")
    except Exception as e:
        logger.warning(f"[BILLING-MIGRATE] Migration warning: {e}")


async def backfill_join_codes():
    import secrets as _secrets
    try:
        projects_without_code = await db.projects.find(
            {'$or': [{'join_code': {'$exists': False}}, {'join_code': None}, {'join_code': ''}]},
            {'_id': 0, 'id': 1}
        ).to_list(10000)
        if not projects_without_code:
            return
        count = 0
        for proj in projects_without_code:
            for _attempt in range(10):
                code = f"BRK-{_secrets.randbelow(9000) + 1000}"
                existing = await db.projects.find_one({'join_code': code})
                if not existing:
                    await db.projects.update_one(
                        {'id': proj['id'], '$or': [{'join_code': {'$exists': False}}, {'join_code': None}, {'join_code': ''}]},
                        {'$set': {'join_code': code}}
                    )
                    count += 1
                    break
        logger.info(f"[BACKFILL] join_code assigned to {count}/{len(projects_without_code)} projects")
    except Exception as e:
        logger.warning(f"[BACKFILL] join_code backfill warning: {e}")


def _mongo_sanity(url: str) -> str:
    return (
        f"is_set={bool(url)} len={len(url)} "
        f"starts_mongo={url.startswith('mongodb')} "
        f"has_at={'@' in url} "
        f"has_srv={'mongodb+srv://' in url}"
    )


async def _deferred_db_init():
    mongo_info = _mongo_sanity(MONGO_URL)
    try:
        users_count = await db.users.count_documents({})
        projects_count = await db.projects.count_documents({})
        logger.info(f"[DB-IDENTITY] {mongo_info} db={DB_NAME} users={users_count} projects={projects_count} mode={APP_MODE}")
    except Exception as e:
        logger.warning(f"[DB-IDENTITY] {mongo_info} db={DB_NAME} mode={APP_MODE} — count failed (non-fatal): {e}")

    try:
        await create_indexes()
        from contractor_ops.stepup_service import ensure_indexes as stepup_ensure_indexes, set_stepup_db
        set_stepup_db(db)
        await stepup_ensure_indexes(db)
        await ensure_transfer_indexes(db)
        from contractor_ops.invoicing import ensure_indexes as invoicing_ensure_indexes
        await invoicing_ensure_indexes()
    except Exception as e:
        logger.warning(f"[STARTUP] Index creation failed (non-fatal): {e}")

    if APP_MODE == 'prod' and (not STEPUP_EMAIL or not SMTP_USER or not SMTP_PASS):
        logger.warning("[STARTUP] WARNING: STEPUP_EMAIL/SMTP_USER/SMTP_PASS not configured — step-up auth will fail!")

    run_seed = os.environ.get('RUN_SEED', '').lower() == 'true'
    if run_seed and APP_MODE == 'dev':
        logger.warning("[SEED] RUN_SEED=true detected in dev mode — running seed_super_admin_user()")
        await seed_super_admin_user()
    else:
        logger.info("[SEED] Seed skipped (RUN_SEED not set or APP_MODE != dev)")

    if APP_MODE == 'dev':
        await ensure_demo_users()

    try:
        await bootstrap_super_admin()
        await auto_migrate_sort_index()
        await migrate_billing_orgs()
        await migrate_remove_owner_admin_roles()
        await backfill_join_codes()
    except Exception as e:
        logger.warning(f"[STARTUP] Migration/bootstrap failed (non-fatal): {e}")

    try:
        from contractor_ops.billing import BILLING_V1_ENABLED, apply_pending_decreases
        if BILLING_V1_ENABLED:
            from contractor_ops.billing_plans import seed_default_plans
            await seed_default_plans()
            applied = await apply_pending_decreases()
            if applied > 0:
                logger.info(f"[BILLING-STARTUP] Applied {applied} pending unit decrease(s)")
        orphan_count = await db.projects.count_documents(
            {'$or': [{'org_id': {'$exists': False}}, {'org_id': None}]}
        )
        logger.info(f"[BILLING-HEALTH] BILLING_V1_ENABLED={BILLING_V1_ENABLED} orphan_projects={orphan_count}")
    except Exception as e:
        logger.warning(f"[BILLING-HEALTH] Health check failed (non-fatal): {e}")

    logger.info("[STARTUP] Deferred DB init completed.")


@app.on_event("startup")
async def startup():
    import asyncio
    from config import ENABLE_ONBOARDING_V2, ENABLE_AUTO_TRIAL
    logger.info(f"[STARTUP] BrikOps starting — APP_ID={APP_ID}, MODE={APP_MODE}, DB={DB_NAME}")
    logger.info(f"[STARTUP] WhatsApp={WHATSAPP_ENABLED} SMS={SMS_ENABLED} OTP={OTP_PROVIDER}")
    logger.info(f"[STARTUP] ONBOARDING_V2={ENABLE_ONBOARDING_V2} AUTO_TRIAL={ENABLE_AUTO_TRIAL}")
    logger.info(f"[STARTUP] MONGO_URL {_mongo_sanity(MONGO_URL)}")
    from services.object_storage import log_backend as _log_storage_backend
    _log_storage_backend()

    if APP_MODE == 'prod' and ('localhost' in MONGO_URL or '127.0.0.1' in MONGO_URL):
        logger.critical("[FATAL] Production mode is using a LOCAL MongoDB! This is not allowed. Refusing to start.")
        print("FATAL: Production mode is using a LOCAL MongoDB! Refusing to start.", file=sys.stderr)
        sys.exit(1)

    run_seed = os.environ.get('RUN_SEED', '').lower() == 'true'
    if run_seed and APP_MODE == 'prod':
        logger.critical("[FATAL] RUN_SEED=true is FORBIDDEN in production! Refusing to start.")
        print("FATAL: RUN_SEED=true is FORBIDDEN in production! Refusing to start.", file=sys.stderr)
        sys.exit(1)

    asyncio.create_task(_deferred_db_init())

    logger.info("[STARTUP] Server accepting connections — DB init running in background.")


@app.on_event("shutdown")
async def shutdown():
    client.close()
    from contractor_ops.sms_service import _shared_sms_httpx
    if _shared_sms_httpx and not _shared_sms_httpx.is_closed:
        await _shared_sms_httpx.aclose()


uploads_dir = Path(__file__).parent / 'uploads'
uploads_dir.mkdir(exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

from services.object_storage import is_s3_mode as _is_s3_mode
if not _is_s3_mode():
    reports_dir = Path(__file__).parent / 'reports'
    reports_dir.mkdir(exist_ok=True)
    app.mount("/reports", StaticFiles(directory=str(reports_dir)), name="reports")
else:
    logger.info("[SPA] S3 mode — skipping /reports StaticFiles mount")

frontend_build = Path(__file__).parent.parent / 'frontend' / 'build'
if not frontend_build.exists():
    frontend_build = Path('/home/runner/workspace/frontend/build')

if frontend_build.exists():
    static_dir = frontend_build / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="frontend_static")
    logger.info(f"[SPA] Serving frontend from {frontend_build}")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            from starlette.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        file_path = frontend_build / full_path
        if file_path.is_file() and '..' not in full_path:
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_build / "index.html"))
else:
    logger.warning(f"[SPA] Frontend build not found, API-only mode")

from contractor_ops.billing import (
    get_effective_access, EffectiveAccess,
    PAYWALL_DETAIL, PAYWALL_CODE,
)
from starlette.responses import JSONResponse

PAYWALL_EXEMPT_PREFIXES = (
    '/api/auth/', '/api/billing/', '/api/admin/',
    '/api/debug/', '/api/updates/feed', '/api/webhooks/',
)

@app.middleware("http")
async def paywall_middleware(request: Request, call_next):
    if request.method == 'GET' or not request.url.path.startswith('/api/'):
        response = await call_next(request)
    else:
        exempt = any(request.url.path.startswith(p) for p in PAYWALL_EXEMPT_PREFIXES)
        if exempt:
            response = await call_next(request)
        else:
            auth_header = request.headers.get('authorization', '')
            if not auth_header.startswith('Bearer '):
                response = await call_next(request)
            else:
                from jose import jwt as jose_jwt, JWTError as JoseJWTError
                try:
                    token = auth_header[7:]
                    payload = jose_jwt.decode(
                        token, JWT_SECRET,
                        algorithms=['HS256'],
                        options={'require_exp': True, 'require_iat': True, 'require_iss': True, 'leeway': 60},
                        issuer=APP_ID,
                    )
                    user_id = payload.get('user_id')
                    user_role = payload.get('role', '')
                    if user_id and user_role not in ('viewer',):
                        _is_sa = False
                        if user_id:
                            _sa_doc = await db.users.find_one({'id': user_id}, {'_id': 0, 'platform_role': 1})
                            _is_sa = _sa_doc and _sa_doc.get('platform_role') == 'super_admin'
                        if not _is_sa:
                            access = await get_effective_access(user_id)
                            if access != EffectiveAccess.FULL_ACCESS:
                                return JSONResponse(
                                    status_code=402,
                                    content={'detail': PAYWALL_DETAIL, 'code': PAYWALL_CODE},
                                )
                    response = await call_next(request)
                except (JoseJWTError, Exception):
                    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

CANONICAL_DOMAIN = os.environ.get('PUBLIC_APP_URL', '').rstrip('/')
_canonical_host = ''
if CANONICAL_DOMAIN:
    try:
        from urllib.parse import urlparse
        _canonical_host = urlparse(CANONICAL_DOMAIN).hostname or ''
    except Exception:
        pass

@app.middleware("http")
async def canonical_redirect_middleware(request: Request, call_next):
    if not CANONICAL_DOMAIN or not _canonical_host:
        return await call_next(request)
    host = request.headers.get('host', '').split(':')[0].lower()
    if host == _canonical_host or host == f'www.{_canonical_host}':
        return await call_next(request)
    if request.url.path == '/health':
        return await call_next(request)
    if request.url.path.startswith('/api/'):
        return await call_next(request)
    path = request.url.path
    query = str(request.url.query)
    target = f"{CANONICAL_DOMAIN}{path}"
    if query:
        target = f"{target}?{query}"
    status_code = 308 if request.method != 'GET' else 301
    from starlette.responses import RedirectResponse
    return RedirectResponse(url=target, status_code=status_code)

_allowed_hosts_raw = os.environ.get('ALLOWED_HOSTS', '').strip()
if _allowed_hosts_raw and APP_MODE == 'prod':
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[h.strip() for h in _allowed_hosts_raw.split(',') if h.strip()],
    )

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=['*'],
    allow_headers=['*'],
)
