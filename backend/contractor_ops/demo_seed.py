import uuid
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEMO_REVIEWER_ACCOUNTS = [
    {
        'email': 'demo-pm@brikops.com',
        'name': 'מנהל פרויקט (דמו)',
        'role': 'project_manager',
        'phone_e164': '+972540000901',
    },
    {
        'email': 'demo-team@brikops.com',
        'name': 'צוות ניהולי (דמו)',
        'role': 'management_team',
        'phone_e164': '+972540000902',
    },
    {
        'email': 'demo-contractor@brikops.com',
        'name': 'קבלן (דמו)',
        'role': 'contractor',
        'phone_e164': '+972540000903',
    },
    {
        'email': 'demo-viewer@brikops.com',
        'name': 'צופה (דמו)',
        'role': 'viewer',
        'phone_e164': '+972540000904',
    },
]

DEMO_ORG_NAME = 'חברת הדגמה'
DEMO_COMPED_UNTIL = '2030-12-31T23:59:59+00:00'


def _now():
    return datetime.now(timezone.utc).isoformat()


async def ensure_demo_reviewer_accounts(db, password: str, reset_passwords: bool = False):
    import bcrypt as _bcrypt

    created = 0
    updated = 0
    user_map = {}

    for acct in DEMO_REVIEWER_ACCOUNTS:
        existing = await db.users.find_one(
            {'email': acct['email']},
            {'_id': 0, 'id': 1, 'password_hash': 1, 'is_demo': 1},
        )

        if existing:
            user_map[acct['email']] = existing['id']
            updates = {}
            if not existing.get('is_demo'):
                updates['is_demo'] = True
            if reset_passwords:
                pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
                updates['password_hash'] = pw_hash
            if updates:
                updates['updated_at'] = _now()
                await db.users.update_one({'id': existing['id']}, {'$set': updates})
                updated += 1
        else:
            user_id = str(uuid.uuid4())
            pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
            await db.users.insert_one({
                'id': user_id,
                'email': acct['email'],
                'password_hash': pw_hash,
                'name': acct['name'],
                'role': acct['role'],
                'phone_e164': acct['phone_e164'],
                'user_status': 'active',
                'is_demo': True,
                'company_id': None,
                'preferred_language': 'he',
                'created_at': _now(),
            })
            user_map[acct['email']] = user_id
            created += 1

    if created or updated:
        logger.info(f"[DEMO] Ensured {len(DEMO_REVIEWER_ACCOUNTS)} demo reviewer accounts (created={created} updated={updated})")
    else:
        logger.info(f"[DEMO] All {len(DEMO_REVIEWER_ACCOUNTS)} demo reviewer accounts already exist")

    return user_map


async def ensure_demo_org(db, user_map: dict):
    ts = _now()
    pm_email = 'demo-pm@brikops.com'
    pm_user_id = user_map.get(pm_email)
    if not pm_user_id:
        logger.warning("[DEMO] demo-pm user not found in user_map — skipping org creation")
        return None

    org = await db.organizations.find_one({'is_demo': True}, {'_id': 0})

    if not org:
        org_id = str(uuid.uuid4())
        org = {
            'id': org_id,
            'name': DEMO_ORG_NAME,
            'owner_user_id': pm_user_id,
            'owner_set_at': ts,
            'is_demo': True,
            'created_at': ts,
        }
        await db.organizations.insert_one(org)
        logger.info(f"[DEMO] Created demo org '{DEMO_ORG_NAME}' id={org_id}")
    else:
        org_id = org['id']
        updates = {}
        if not org.get('is_demo'):
            updates['is_demo'] = True
        if org.get('owner_user_id') != pm_user_id:
            updates['owner_user_id'] = pm_user_id
            updates['owner_set_at'] = ts
        if updates:
            await db.organizations.update_one({'id': org_id}, {'$set': updates})

    members_ensured = 0
    role_map = {
        'demo-pm@brikops.com': 'owner',
        'demo-team@brikops.com': 'org_admin',
        'demo-contractor@brikops.com': 'member',
        'demo-viewer@brikops.com': 'member',
    }
    for email, user_id in user_map.items():
        existing_membership = await db.organization_memberships.find_one(
            {'org_id': org_id, 'user_id': user_id},
            {'_id': 0, 'id': 1},
        )
        if not existing_membership:
            await db.organization_memberships.insert_one({
                'id': str(uuid.uuid4()),
                'org_id': org_id,
                'user_id': user_id,
                'role': role_map.get(email, 'member'),
                'created_at': ts,
            })
            members_ensured += 1

    sub = await db.subscriptions.find_one({'org_id': org_id}, {'_id': 0})
    if not sub:
        await db.subscriptions.insert_one({
            'id': str(uuid.uuid4()),
            'org_id': org_id,
            'status': 'active',
            'trial_end_at': None,
            'paid_until': DEMO_COMPED_UNTIL,
            'grace_until': None,
            'manual_override': {
                'is_comped': True,
                'comped_until': DEMO_COMPED_UNTIL,
                'is_suspended': False,
                'note': 'Demo/reviewer org — auto-comped',
                'by_user_id': 'system',
                'at': ts,
            },
            'created_at': ts,
            'updated_at': ts,
        })
        logger.info(f"[DEMO] Created demo subscription for org {org_id} (comped until 2030-12-31)")
    else:
        mo = sub.get('manual_override') or {}
        if not mo.get('is_comped') or mo.get('comped_until') != DEMO_COMPED_UNTIL:
            await db.subscriptions.update_one(
                {'org_id': org_id},
                {'$set': {
                    'status': 'active',
                    'paid_until': DEMO_COMPED_UNTIL,
                    'manual_override.is_comped': True,
                    'manual_override.comped_until': DEMO_COMPED_UNTIL,
                    'manual_override.is_suspended': False,
                    'manual_override.note': 'Demo/reviewer org — auto-comped',
                    'manual_override.by_user_id': 'system',
                    'manual_override.at': ts,
                    'updated_at': ts,
                }},
            )
            logger.info(f"[DEMO] Updated demo subscription for org {org_id} — ensured is_comped until 2030-12-31")

    logger.info(f"[DEMO] Ensured demo org + {members_ensured} new memberships + subscription")
    return org_id
