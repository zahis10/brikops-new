import logging
import asyncio
import bcrypt
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None

def set_identity_db(db):
    global _db
    _db = db

def get_db():
    return _db

MANAGEMENT_PROJECT_ROLES = {'project_manager', 'management_team'}
MANAGEMENT_ORG_ROLES = {'owner', 'org_admin', 'billing_admin'}


async def is_management_user(user_id: str) -> bool:
    db = get_db()
    user = await db.users.find_one({'id': user_id}, {'_id': 0, 'platform_role': 1})
    if user and user.get('platform_role') == 'super_admin':
        return True

    org = await db.organizations.find_one({'owner_user_id': user_id}, {'_id': 0, 'id': 1})
    if org:
        return True

    org_mem = await db.organization_memberships.find_one(
        {'user_id': user_id, 'role': {'$in': list(MANAGEMENT_ORG_ROLES)}},
        {'_id': 0, 'role': 1}
    )
    if org_mem:
        return True

    proj_mem = await db.project_memberships.find_one(
        {'user_id': user_id, 'role': {'$in': list(MANAGEMENT_PROJECT_ROLES)}},
        {'_id': 0, 'role': 1}
    )
    if proj_mem:
        return True

    return False


async def get_account_status(user: dict, gate_mode: str) -> dict:
    user_id = user['id']
    email = user.get('email') or None
    has_password = bool(user.get('password_hash'))
    email_verified = user.get('email_verified', False)
    account_complete = user.get('account_complete', True)

    is_mgmt = await is_management_user(user_id)

    missing_email = is_mgmt and not email
    missing_password = is_mgmt and not has_password
    would_require = is_mgmt and (missing_email or missing_password)

    requires_completion = False
    if gate_mode == 'enforce' and would_require:
        requires_completion = True
    elif gate_mode == 'soft' and would_require and not account_complete:
        requires_completion = True

    return {
        'gate_mode': gate_mode,
        'account_complete': account_complete,
        'email': email,
        'email_verified': email_verified,
        'has_password': has_password,
        'is_management': is_mgmt,
        'would_require_completion': would_require,
        'requires_completion': requires_completion,
    }


def _hash_password_sync(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


async def _hash_password(password: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _hash_password_sync, password)


async def complete_account(user_id: str, email: str, password: str) -> dict:
    db = get_db()

    email = email.strip().lower()

    existing = await db.users.find_one({'email': email, 'id': {'$ne': user_id}}, {'_id': 0, 'id': 1})
    if existing:
        return {'error': 'כתובת המייל כבר רשומה במערכת'}

    password_hash = await _hash_password(password)
    now = datetime.now(timezone.utc).isoformat()

    await db.users.update_one(
        {'id': user_id},
        {'$set': {
            'email': email,
            'password_hash': password_hash,
            'account_complete': True,
            'identity_enrolled_at': now,
            'updated_at': now,
        }}
    )

    await db.audit_events.insert_one({
        'id': __import__('uuid').uuid4().hex,
        'event_type': 'identity',
        'entity_type': 'user',
        'entity_id': user_id,
        'action': 'account_completed',
        'actor_id': user_id,
        'created_at': now,
        'payload': {'email_set': True, 'password_set': True},
    })

    logger.info(f"[IDENTITY] Account completed for user {user_id}, email={email}")

    user = await db.users.find_one({'id': user_id}, {'_id': 0, 'password_hash': 0})
    return {'ok': True, 'user': user}
