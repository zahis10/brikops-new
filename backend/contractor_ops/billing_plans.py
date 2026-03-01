from typing import Optional, List
import uuid
import logging

logger = logging.getLogger(__name__)

_db = None


def set_plans_db(db):
    global _db
    _db = db


def get_db():
    if _db is None:
        raise RuntimeError("Billing plans DB not initialized")
    return _db


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


UNIT_TIERS = [
    {'code': 'tier_s', 'label': 'עד 50 יחידות', 'max_units': 50, 'monthly_fee': 900},
    {'code': 'tier_m', 'label': '51-200 יחידות', 'max_units': 200, 'monthly_fee': 2400},
    {'code': 'tier_l', 'label': '201-500 יחידות', 'max_units': 500, 'monthly_fee': 4800},
    {'code': 'tier_xl', 'label': '501+ יחידות', 'max_units': None, 'monthly_fee': 8500},
]

DEFAULT_PLANS = [
    {
        'id': 'plan_basic',
        'name': 'בסיסי',
        'project_fee_monthly': 1200,
        'unit_tiers': UNIT_TIERS,
        'version': 2,
        'is_active': True,
    },
    {
        'id': 'plan_pro',
        'name': 'מקצועי',
        'project_fee_monthly': 2000,
        'unit_tiers': UNIT_TIERS,
        'version': 2,
        'is_active': True,
    },
    {
        'id': 'plan_xl',
        'name': 'XL',
        'project_fee_monthly': 3500,
        'unit_tiers': UNIT_TIERS,
        'version': 2,
        'is_active': True,
    },
]


def validate_plan(data: dict) -> Optional[str]:
    if not data.get('name') or not isinstance(data['name'], str):
        return 'שם תוכנית חובה'
    fee = data.get('project_fee_monthly')
    if fee is None or not isinstance(fee, (int, float)) or fee < 0:
        return 'עמלת פרויקט חודשית חייבת להיות מספר חיובי'
    tiers = data.get('unit_tiers')
    if not tiers or not isinstance(tiers, list) or len(tiers) == 0:
        return 'חובה להגדיר לפחות רמת תמחור אחת'
    for t in tiers:
        if not t.get('code') or not isinstance(t['code'], str):
            return 'כל רמת תמחור חייבת לכלול קוד'
        if not t.get('label') or not isinstance(t['label'], str):
            return 'כל רמת תמחור חייבת לכלול תווית'
        if t.get('monthly_fee') is None or not isinstance(t['monthly_fee'], (int, float)) or t['monthly_fee'] < 0:
            return 'עמלה חודשית חייבת להיות מספר חיובי'
    return None


def resolve_tier(plan: dict, contracted_units: int) -> dict:
    tiers = plan.get('unit_tiers', [])
    sorted_tiers = sorted(tiers, key=lambda t: t.get('max_units') or float('inf'))
    for tier in sorted_tiers:
        max_u = tier.get('max_units')
        if max_u is None or contracted_units <= max_u:
            return tier
    if sorted_tiers:
        return sorted_tiers[-1]
    return {'code': 'unknown', 'label': '', 'monthly_fee': 0}


def snapshot_pricing(plan: dict, contracted_units: int) -> dict:
    tier = resolve_tier(plan, contracted_units)
    project_fee = plan.get('project_fee_monthly', 0)
    tier_fee = tier.get('monthly_fee', 0)
    return {
        'project_fee_snapshot': project_fee,
        'tier_fee_snapshot': tier_fee,
        'tier_code': tier.get('code', 'unknown'),
        'pricing_version': plan.get('version', 1),
        'monthly_total': project_fee + tier_fee,
    }


async def seed_default_plans():
    db = get_db()
    for plan_data in DEFAULT_PLANS:
        existing = await db.billing_plans.find_one({'id': plan_data['id']})
        if not existing:
            doc = {**plan_data, 'created_at': _now()}
            await db.billing_plans.insert_one(doc)
            logger.info(f"[BILLING-PLANS] Seeded plan: {plan_data['id']} ({plan_data['name']})")
        elif existing.get('version', 1) < plan_data.get('version', 1):
            ts = _now()
            update_fields = {
                'name': plan_data['name'],
                'project_fee_monthly': plan_data['project_fee_monthly'],
                'unit_tiers': plan_data['unit_tiers'],
                'version': plan_data['version'],
                'is_active': plan_data.get('is_active', True),
                'updated_at': ts,
            }
            await db.billing_plans.update_one({'id': plan_data['id']}, {'$set': update_fields})
            logger.info(f"[BILLING-PLANS] Updated plan: {plan_data['id']} v{existing.get('version',1)} -> v{plan_data['version']}")


async def list_plans(active_only: bool = False) -> list:
    db = get_db()
    query = {'is_active': True} if active_only else {}
    plans = await db.billing_plans.find(query, {'_id': 0}).to_list(100)
    return plans


async def get_plan(plan_id: str) -> Optional[dict]:
    db = get_db()
    return await db.billing_plans.find_one({'id': plan_id}, {'_id': 0})


async def create_plan(data: dict, actor_id: str) -> dict:
    db = get_db()
    err = validate_plan(data)
    if err:
        raise ValueError(err)

    plan_id = str(uuid.uuid4())
    ts = _now()
    doc = {
        'id': plan_id,
        'name': data['name'],
        'project_fee_monthly': data['project_fee_monthly'],
        'unit_tiers': data['unit_tiers'],
        'version': 1,
        'is_active': True,
        'created_at': ts,
    }
    await db.billing_plans.insert_one(doc)

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'billing_plan',
        'entity_id': plan_id,
        'action': 'billing_plan_created',
        'actor_id': actor_id,
        'payload': {'name': data['name'], 'project_fee_monthly': data['project_fee_monthly']},
        'created_at': ts,
    })

    doc.pop('_id', None)
    return doc


async def update_plan(plan_id: str, data: dict, actor_id: str) -> dict:
    db = get_db()
    existing = await db.billing_plans.find_one({'id': plan_id}, {'_id': 0})
    if not existing:
        raise ValueError('תוכנית לא נמצאה')

    err = validate_plan(data)
    if err:
        raise ValueError(err)

    ts = _now()
    new_version = existing.get('version', 1) + 1
    update_fields = {
        'name': data['name'],
        'project_fee_monthly': data['project_fee_monthly'],
        'unit_tiers': data['unit_tiers'],
        'version': new_version,
        'updated_at': ts,
    }
    await db.billing_plans.update_one({'id': plan_id}, {'$set': update_fields})

    before = {
        'name': existing.get('name'),
        'project_fee_monthly': existing.get('project_fee_monthly'),
        'version': existing.get('version'),
    }
    after = {
        'name': data['name'],
        'project_fee_monthly': data['project_fee_monthly'],
        'version': new_version,
    }
    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'billing_plan',
        'entity_id': plan_id,
        'action': 'billing_plan_updated',
        'actor_id': actor_id,
        'payload': {'before': before, 'after': after},
        'created_at': ts,
    })

    updated = await db.billing_plans.find_one({'id': plan_id}, {'_id': 0})
    return updated


async def deactivate_plan(plan_id: str, actor_id: str) -> dict:
    db = get_db()
    existing = await db.billing_plans.find_one({'id': plan_id}, {'_id': 0})
    if not existing:
        raise ValueError('תוכנית לא נמצאה')

    ts = _now()
    await db.billing_plans.update_one({'id': plan_id}, {'$set': {'is_active': False, 'updated_at': ts}})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'billing_plan',
        'entity_id': plan_id,
        'action': 'billing_plan_deactivated',
        'actor_id': actor_id,
        'payload': {'name': existing.get('name')},
        'created_at': ts,
    })

    return {'success': True, 'plan_id': plan_id}
