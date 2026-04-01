from datetime import datetime, timezone, timedelta
from typing import Optional, List
from enum import Enum
import os
import uuid
import logging

from contractor_ops.utils.timezone import IL_TZ

logger = logging.getLogger(__name__)

BILLING_V1_ENABLED = os.environ.get('BILLING_V1_ENABLED', 'false').lower() == 'true'

VALID_ORG_ROLES = {'member', 'project_manager', 'org_admin', 'billing_admin'}
ORG_BILLING_ROLES = {'org_admin', 'billing_admin'}

VALID_SETUP_STATES = {'trial', 'pending_handoff', 'pending_billing_setup', 'ready', 'active'}
VALID_SETUP_TRANSITIONS = {
    'trial': {'pending_handoff'},
    'pending_handoff': {'pending_billing_setup', 'trial'},
    'pending_billing_setup': {'ready', 'pending_handoff'},
    'ready': {'active', 'pending_billing_setup'},
    'active': {'ready'},
}
VALID_BILLING_STATUSES = {'active', 'paused', 'archived'}


class SubscriptionStatus(str, Enum):
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    suspended = "suspended"
    canceled = "canceled"


class EffectiveAccess(str, Enum):
    FULL_ACCESS = "full_access"
    READ_ONLY = "read_only"


PAYWALL_DETAIL = "תקופת הניסיון הסתיימה. כדי להמשיך לעבוד יש לבצע תשלום."
PAYWALL_CODE = "PAYWALL"


_db = None


def set_billing_db(db):
    global _db
    _db = db


def get_db():
    if _db is None:
        raise RuntimeError("Billing DB not initialized")
    return _db


def _now():
    return datetime.now(timezone.utc).isoformat()


def _now_dt():
    return datetime.now(timezone.utc)


def _start_of_next_billing_period(billing_cycle: str = 'monthly') -> str:
    now_il = datetime.now(IL_TZ)
    if billing_cycle == 'yearly':
        next_start = now_il.replace(year=now_il.year + 1, month=1, day=1,
                                     hour=0, minute=0, second=0, microsecond=0)
    else:
        month = now_il.month + 1
        year = now_il.year
        if month > 12:
            month = 1
            year += 1
        next_start = now_il.replace(year=year, month=month, day=1,
                                      hour=0, minute=0, second=0, microsecond=0)
    return next_start.astimezone(timezone.utc).isoformat()


async def _get_project_index(org_id: str, project_id: str) -> int:
    db = get_db()
    all_pbs = await db.project_billing.find(
        {'org_id': org_id, 'status': 'active'}, {'_id': 0, 'project_id': 1, 'created_at': 1}
    ).to_list(1000)
    sorted_pbs = sorted(all_pbs, key=lambda p: (p.get('created_at', ''), p.get('project_id', '')))
    for i, pb in enumerate(sorted_pbs):
        if pb['project_id'] == project_id:
            return i + 1
    return 1


async def apply_pending_decreases(org_id: str = None) -> int:
    db = get_db()
    from contractor_ops.billing_plans import calculate_monthly
    now = _now()
    query = {
        'pending_contracted_units': {'$exists': True, '$ne': None},
        'pending_effective_from': {'$exists': True, '$ne': None, '$lte': now},
        'status': 'active',
    }
    if org_id:
        query['org_id'] = org_id
    pending_docs = await db.project_billing.find(query, {'_id': 0}).to_list(1000)
    applied = 0
    affected_orgs = set()
    for pb in pending_docs:
        new_units = pb['pending_contracted_units']
        plan_id = pb.get('plan_id')
        proj_index = await _get_project_index(pb['org_id'], pb['project_id'])
        new_monthly = calculate_monthly(new_units, plan_id=plan_id, project_index=proj_index)
        pricing_update = {'monthly_total': new_monthly}
        await db.project_billing.update_one(
            {'id': pb['id']},
            {
                '$set': {
                    'contracted_units': new_units,
                    'cycle_peak_units': new_units,
                    'updated_at': now,
                    **pricing_update,
                },
                '$unset': {
                    'pending_contracted_units': '',
                    'pending_effective_from': '',
                },
            }
        )
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'event_type': 'billing',
            'entity_type': 'project_billing',
            'entity_id': pb['id'],
            'action': 'contracted_units_decrease_applied',
            'actor_id': 'system',
            'payload': {
                'project_id': pb.get('project_id'),
                'org_id': pb.get('org_id'),
                'previous_contracted_units': pb.get('contracted_units'),
                'new_contracted_units': new_units,
                'pending_effective_from': pb.get('pending_effective_from'),
            },
            'created_at': now,
        })
        affected_orgs.add(pb.get('org_id'))
        applied += 1
        logger.info("[BILLING-UNITS] Applied pending decrease for project_billing %s: %s -> %s",
                     pb['id'], pb.get('contracted_units'), new_units)
    for oid in affected_orgs:
        await recalc_org_total(oid)
    if applied > 0:
        logger.info("[BILLING-UNITS] Applied %d pending decrease(s)", applied)
    return applied


async def create_organization(owner_user_id: str, name: str = "הארגון שלי") -> dict:
    db = get_db()
    org_id = str(uuid.uuid4())
    ts = _now()
    org_doc = {
        'id': org_id,
        'name': name,
        'owner_user_id': owner_user_id,
        'owner_set_at': ts,
        'created_at': ts,
    }
    await db.organizations.insert_one(org_doc)

    membership_doc = {
        'id': str(uuid.uuid4()),
        'org_id': org_id,
        'user_id': owner_user_id,
        'role': 'project_manager',
        'created_at': ts,
    }
    await db.organization_memberships.insert_one(membership_doc)

    return org_doc


async def create_trial_subscription(org_id: str, trial_days: int = 7) -> dict:
    db = get_db()
    ts = _now()
    trial_end = (_now_dt() + timedelta(days=trial_days)).isoformat()
    sub_doc = {
        'id': str(uuid.uuid4()),
        'org_id': org_id,
        'status': SubscriptionStatus.trialing.value,
        'trial_end_at': trial_end,
        'paid_until': None,
        'grace_until': None,
        'manual_override': {
            'is_comped': False,
            'comped_until': None,
            'is_suspended': False,
            'note': None,
            'by_user_id': None,
            'at': None,
        },
        'created_at': ts,
        'updated_at': ts,
    }
    await db.subscriptions.insert_one(sub_doc)
    return sub_doc


async def get_user_org(user_id: str) -> Optional[dict]:
    db = get_db()
    membership = await db.organization_memberships.find_one(
        {'user_id': user_id}, {'_id': 0}
    )
    if not membership:
        return None
    org = await db.organizations.find_one(
        {'id': membership['org_id']}, {'_id': 0}
    )
    return org


async def get_subscription(org_id: str) -> Optional[dict]:
    db = get_db()
    sub = await db.subscriptions.find_one({'org_id': org_id}, {'_id': 0})
    return sub


def _parse_dt(val) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(val).replace('Z', '+00:00'))
    except Exception:
        return None


def compute_subscription_snapshot(sub: Optional[dict], now: Optional[datetime] = None) -> dict:
    defaults = {
        'subscription_status': 'none',
        'billing_cycle': None,
        'auto_renew': False,
        'next_charge_at': None,
        'grace_until': None,
    }
    if not sub:
        return defaults

    if now is None:
        now = _now_dt()

    paid_until = _parse_dt(sub.get('paid_until'))
    trial_end_at = _parse_dt(sub.get('trial_end_at'))
    grace_until = _parse_dt(sub.get('grace_until'))
    mo = sub.get('manual_override') or {}

    if mo.get('is_suspended'):
        status = 'suspended'
    elif grace_until and paid_until and now >= paid_until and now < grace_until:
        status = 'past_due'
    elif paid_until and now < paid_until:
        status = 'active'
    elif trial_end_at and now < trial_end_at and (not paid_until or now >= paid_until):
        status = 'trial'
    elif paid_until and now >= paid_until:
        status = 'expired'
    elif trial_end_at and now >= trial_end_at:
        status = 'expired'
    else:
        status = 'none'

    return {
        'subscription_status': status,
        'billing_cycle': sub.get('billing_cycle', None),
        'auto_renew': sub.get('auto_renew', False),
        'next_charge_at': sub.get('next_charge_at', None),
        'grace_until': sub.get('grace_until', None),
    }


def _resolve_access(sub: Optional[dict]) -> tuple:
    if not sub:
        return (EffectiveAccess.READ_ONLY, 'no_subscription')

    now = _now()
    mo = sub.get('manual_override') or {}

    if mo.get('is_suspended'):
        return (EffectiveAccess.READ_ONLY, 'suspended')

    if sub.get('status') == 'active' and sub.get('paid_until') and sub['paid_until'] >= now:
        return (EffectiveAccess.FULL_ACCESS, None)

    if sub.get('status') == 'trialing' and sub.get('trial_end_at') and sub['trial_end_at'] >= now:
        return (EffectiveAccess.FULL_ACCESS, None)

    if mo.get('is_comped') and mo.get('comped_until') and mo['comped_until'] >= now:
        return (EffectiveAccess.FULL_ACCESS, None)

    if sub.get('status') == 'active':
        return (EffectiveAccess.READ_ONLY, 'payment_expired')

    if sub.get('status') == 'trialing':
        return (EffectiveAccess.READ_ONLY, 'trial_expired')

    return (EffectiveAccess.READ_ONLY, 'no_subscription')


async def get_effective_access(user_id: str, org_id: Optional[str] = None) -> EffectiveAccess:
    db = get_db()

    if user_id:
        sa_doc = await db.users.find_one({'id': user_id}, {'_id': 0, 'platform_role': 1})
        if sa_doc and sa_doc.get('platform_role') == 'super_admin':
            return EffectiveAccess.FULL_ACCESS

    if not org_id:
        org = await get_user_org(user_id)
        if not org:
            return EffectiveAccess.READ_ONLY
        org_id = org['id']

    sub = await get_subscription(org_id)
    access, _reason = _resolve_access(sub)
    return access


async def get_billing_info(user_id: str) -> dict:
    db = get_db()

    _is_super_admin = False
    if user_id:
        sa_doc = await db.users.find_one({'id': user_id}, {'_id': 0, 'platform_role': 1})
        _is_super_admin = sa_doc and sa_doc.get('platform_role') == 'super_admin'

    org = await get_user_org(user_id)
    if not org:
        return {
            'org_id': None,
            'org_name': None,
            'owner_user_id': None,
            'is_owner': _is_super_admin,
            'can_manage_billing': _is_super_admin,
            'is_org_pm': False,
            'role_display': None,
            'status': None,
            'trial_end_at': None,
            'paid_until': None,
            'effective_access': EffectiveAccess.FULL_ACCESS.value if _is_super_admin else EffectiveAccess.READ_ONLY.value,
            'read_only_reason': None if _is_super_admin else 'no_subscription',
            'days_remaining': 0,
        }

    org_id = org['id']
    is_owner = org.get('owner_user_id') == user_id

    billing_role = await check_org_billing_role(user_id, org_id) if not _is_super_admin else 'super_admin'
    can_manage = _is_super_admin or (billing_role in ('org_admin', 'billing_admin', 'owner'))
    is_pm = False
    if not can_manage:
        is_pm = await check_org_pm_role(user_id, org_id)

    mem = await db.organization_memberships.find_one(
        {'org_id': org_id, 'user_id': user_id}, {'_id': 0, 'role': 1}
    )
    role_display = mem.get('role') if mem else None

    sub = await get_subscription(org_id)
    access, reason = _resolve_access(sub)

    days_remaining = 0
    if sub:
        if sub.get('status') == 'trialing' and sub.get('trial_end_at'):
            try:
                end = datetime.fromisoformat(sub['trial_end_at'].replace('Z', '+00:00'))
                remaining = (end - _now_dt()).total_seconds()
                days_remaining = max(0, int(remaining / 86400))
            except Exception:
                pass

    snapshot = compute_subscription_snapshot(sub)

    return {
        'org_id': org_id,
        'org_name': org.get('name'),
        'owner_user_id': org.get('owner_user_id'),
        'is_owner': is_owner or _is_super_admin,
        'can_manage_billing': can_manage,
        'is_org_pm': is_pm,
        'role_display': role_display,
        'status': sub.get('status') if sub else None,
        'trial_end_at': sub.get('trial_end_at') if sub else None,
        'paid_until': sub.get('paid_until') if sub else None,
        'comped_until': (sub.get('manual_override') or {}).get('comped_until') if sub else None,
        'is_suspended': (sub.get('manual_override') or {}).get('is_suspended', False) if sub else False,
        'effective_access': EffectiveAccess.FULL_ACCESS.value if _is_super_admin else access.value,
        'read_only_reason': None if _is_super_admin else reason,
        'days_remaining': days_remaining,
        'subscription_status': snapshot['subscription_status'],
        'billing_cycle': snapshot['billing_cycle'],
        'auto_renew': snapshot['auto_renew'],
    }


async def _ensure_subscription(org_id: str) -> dict:
    db = get_db()
    ts = _now()
    sub_doc = {
        'id': str(uuid.uuid4()),
        'org_id': org_id,
        'status': 'inactive',
        'trial_end_at': None,
        'paid_until': None,
        'grace_until': None,
        'manual_override': {
            'is_comped': False,
            'comped_until': None,
            'is_suspended': False,
            'note': None,
            'by_user_id': None,
            'at': None,
        },
        'created_at': ts,
        'updated_at': ts,
    }
    await db.subscriptions.insert_one(sub_doc)
    logger.info(f"[BILLING] Auto-created inactive subscription for org {org_id}: sub={sub_doc['id']}")
    return sub_doc


async def admin_billing_override(actor_id: str, org_id: str, action: str,
                                  until: Optional[str] = None, note: str = '') -> dict:
    db = get_db()
    auto_created = False
    sub = await get_subscription(org_id)
    if not sub:
        await _ensure_subscription(org_id)
        sub = await get_subscription(org_id)
        auto_created = True

    ts = _now()
    update = {'updated_at': ts}
    audit_payload = {'action': action, 'org_id': org_id, 'note': note}
    if auto_created:
        audit_payload['auto_created'] = True

    if action == 'extend_trial':
        if sub.get('status') == 'active':
            return {'success': False, 'error': 'לא ניתן להאריך ניסיון לארגון עם מנוי פעיל. השתמש בהפעלת מנוי במקום.'}
        if not until:
            return {'success': False, 'error': 'חובה לציין תאריך'}
        update['trial_end_at'] = until
        update['status'] = 'trialing'
        audit_payload['trial_end_at'] = until

    elif action == 'activate':
        if not until:
            return {'success': False, 'error': 'חובה לציין תאריך'}
        update['status'] = 'active'
        update['paid_until'] = until
        audit_payload['paid_until'] = until

    elif action == 'comp':
        if not until:
            return {'success': False, 'error': 'חובה לציין תאריך'}
        update['manual_override.is_comped'] = True
        update['manual_override.comped_until'] = until
        update['manual_override.note'] = note
        update['manual_override.by_user_id'] = actor_id
        update['manual_override.at'] = ts
        audit_payload['comped_until'] = until

    elif action == 'suspend':
        update['manual_override.is_suspended'] = True
        update['manual_override.note'] = note
        update['manual_override.by_user_id'] = actor_id
        update['manual_override.at'] = ts

    elif action == 'unsuspend':
        update['manual_override.is_suspended'] = False
        update['manual_override.note'] = note
        update['manual_override.by_user_id'] = actor_id
        update['manual_override.at'] = ts

    else:
        return {'success': False, 'error': f'פעולה לא מוכרת: {action}'}

    await db.subscriptions.update_one({'org_id': org_id}, {'$set': update})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'subscription',
        'entity_id': sub['id'],
        'action': f'billing_{action}',
        'actor_id': actor_id,
        'payload': audit_payload,
        'created_at': ts,
    })

    new_access = await get_effective_access(actor_id, org_id)
    return {
        'success': True,
        'action': action,
        'effective_access': new_access.value,
    }


async def ensure_user_org(user_id: str, user_name: str = '') -> dict:
    org = await get_user_org(user_id)
    if org:
        return org

    org_name = f"הארגון של {user_name}" if user_name else "הארגון שלי"
    org = await create_organization(user_id, org_name)
    await create_trial_subscription(org['id'])

    logger.info(f"[BILLING] Created org + trial for user {user_id}: org={org['id']}")
    return org


async def migrate_existing_projects(user_id: str, org_id: str):
    db = get_db()
    result = await db.projects.update_many(
        {'created_by': user_id, 'org_id': {'$exists': False}},
        {'$set': {'org_id': org_id}}
    )
    if result.modified_count > 0:
        logger.info(f"[BILLING] Migrated {result.modified_count} projects to org {org_id} for user {user_id}")
    return result.modified_count


async def check_org_billing_role(user_id: str, org_id: str) -> Optional[str]:
    db = get_db()
    org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'owner_user_id': 1})
    if org and org.get('owner_user_id') == user_id:
        return 'owner'
    mem = await db.organization_memberships.find_one(
        {'org_id': org_id, 'user_id': user_id}, {'_id': 0, 'role': 1}
    )
    if mem and mem.get('role') in ORG_BILLING_ROLES:
        return mem['role']
    return None


async def compute_observed_units(project_id: str) -> int:
    db = get_db()
    active_buildings = await db.buildings.find(
        {'project_id': project_id, 'archived': {'$ne': True}},
        {'_id': 0, 'id': 1}
    ).to_list(10000)
    if not active_buildings:
        return 0
    building_ids = [b['id'] for b in active_buildings]
    count = await db.units.count_documents({
        'building_id': {'$in': building_ids},
        'archived': {'$ne': True},
    })
    return count


async def create_project_billing(project_id: str, org_id: str, actor_id: str,
                                  plan_id: Optional[str] = None,
                                  contracted_units: int = 0) -> dict:
    db = get_db()
    from contractor_ops.billing_plans import calculate_monthly

    existing = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0})
    if existing:
        raise ValueError('כבר קיים רשומת חיוב לפרויקט זה')

    proj_index = 1
    if plan_id:
        active_count = await db.project_billing.count_documents(
            {'org_id': org_id, 'status': 'active'}
        )
        proj_index = active_count + 1

    from contractor_ops.billing_plans import PROJECT_LICENSE_FIRST, PROJECT_LICENSE_ADDITIONAL, PRICE_PER_UNIT
    monthly_total = calculate_monthly(
        contracted_units, plan_id=plan_id, project_index=proj_index
    ) if plan_id else 0

    if plan_id and plan_id != 'founder_6m':
        license_fee = PROJECT_LICENSE_FIRST if proj_index <= 1 else PROJECT_LICENSE_ADDITIONAL
        units_fee = contracted_units * PRICE_PER_UNIT
    elif plan_id == 'founder_6m':
        license_fee = 500
        units_fee = 0
    else:
        license_fee = 0
        units_fee = 0

    observed = await compute_observed_units(project_id)
    ts = _now()
    doc = {
        'id': str(uuid.uuid4()),
        'project_id': project_id,
        'org_id': org_id,
        'plan_id': plan_id,
        'contracted_units': contracted_units,
        'observed_units': observed,
        'monthly_total': monthly_total,
        'license_fee': license_fee,
        'units_fee': units_fee,
        'price_per_unit': PRICE_PER_UNIT,
        'status': 'active',
        'setup_state': 'trial',
        'billing_contact_note': None,
        'created_at': ts,
        'updated_at': ts,
    }
    await db.project_billing.insert_one(doc)

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'project_billing',
        'entity_id': doc['id'],
        'action': 'project_billing_created',
        'actor_id': actor_id,
        'payload': {
            'project_id': project_id, 'org_id': org_id,
            'plan_id': plan_id, 'contracted_units': contracted_units,
            'monthly_total': monthly_total,
        },
        'created_at': ts,
    })

    doc.pop('_id', None)
    return doc


def validate_setup_transition(current_state: str, new_state: str) -> bool:
    allowed = VALID_SETUP_TRANSITIONS.get(current_state, set())
    return new_state in allowed


async def update_project_billing(project_billing_id: str, updates: dict, actor_id: str) -> dict:
    db = get_db()
    from contractor_ops.billing_plans import calculate_monthly

    existing = await db.project_billing.find_one({'id': project_billing_id}, {'_id': 0})
    if not existing:
        raise ValueError('רשומת חיוב לא נמצאה')

    ts = _now()
    before = {
        'plan_id': existing.get('plan_id'),
        'contracted_units': existing.get('contracted_units'),
        'monthly_total': existing.get('monthly_total'),
        'status': existing.get('status'),
        'setup_state': existing.get('setup_state'),
    }

    set_fields = {'updated_at': ts}
    unset_fields = {}
    current_contracted = existing.get('contracted_units', 0)
    unit_change_type = None

    if 'contracted_units' in updates:
        requested_units = updates['contracted_units']
        if requested_units > current_contracted:
            set_fields['contracted_units'] = requested_units
            peak = max(existing.get('cycle_peak_units', current_contracted), requested_units)
            set_fields['cycle_peak_units'] = peak
            if existing.get('pending_contracted_units') is not None and existing['pending_contracted_units'] < requested_units:
                unset_fields['pending_contracted_units'] = ''
                unset_fields['pending_effective_from'] = ''
            unit_change_type = 'increase'
        elif requested_units < current_contracted:
            sub = await get_subscription(existing.get('org_id'))
            billing_cycle = sub.get('billing_cycle', 'monthly') if sub else 'monthly'
            set_fields['pending_contracted_units'] = requested_units
            set_fields['pending_effective_from'] = _start_of_next_billing_period(billing_cycle)
            unit_change_type = 'decrease_scheduled'
        new_contracted_for_pricing = set_fields.get('contracted_units', current_contracted)
    else:
        new_contracted_for_pricing = current_contracted

    if 'status' in updates:
        new_status = updates['status']
        if new_status not in VALID_BILLING_STATUSES:
            raise ValueError(f'סטטוס לא תקין: {new_status}')
        set_fields['status'] = new_status

    if 'setup_state' in updates:
        new_setup = updates['setup_state']
        current_setup = existing.get('setup_state', 'trial')
        if not validate_setup_transition(current_setup, new_setup):
            raise ValueError(f'מעבר לא תקין: {current_setup} -> {new_setup}')
        set_fields['setup_state'] = new_setup

    if 'billing_contact_note' in updates:
        set_fields['billing_contact_note'] = updates['billing_contact_note']

    ALLOWED_PLAN_IDS = {'standard', 'founder_6m'}
    new_plan_id = updates.get('plan_id', existing.get('plan_id'))
    if new_plan_id and new_plan_id not in ALLOWED_PLAN_IDS:
        new_plan_id = 'standard'
    if new_plan_id:
        from contractor_ops.billing_plans import PROJECT_LICENSE_FIRST, PROJECT_LICENSE_ADDITIONAL, PRICE_PER_UNIT
        set_fields['plan_id'] = new_plan_id
        proj_index = await _get_project_index(existing['org_id'], existing['project_id'])
        set_fields['monthly_total'] = calculate_monthly(
            new_contracted_for_pricing, plan_id=new_plan_id, project_index=proj_index
        )
        if new_plan_id == 'founder_6m':
            set_fields['license_fee'] = 500
            set_fields['units_fee'] = 0
        else:
            set_fields['license_fee'] = PROJECT_LICENSE_FIRST if proj_index <= 1 else PROJECT_LICENSE_ADDITIONAL
            set_fields['units_fee'] = new_contracted_for_pricing * PRICE_PER_UNIT
        set_fields['price_per_unit'] = PRICE_PER_UNIT

    observed = await compute_observed_units(existing['project_id'])
    set_fields['observed_units'] = observed
    current_peak = existing.get('cycle_peak_units', current_contracted)
    new_peak = max(current_peak, observed, set_fields.get('contracted_units', current_contracted))
    set_fields['cycle_peak_units'] = new_peak

    update_op = {'$set': set_fields}
    if unset_fields:
        update_op['$unset'] = unset_fields
    await db.project_billing.update_one({'id': project_billing_id}, update_op)

    after = {
        'plan_id': set_fields.get('plan_id', existing.get('plan_id')),
        'contracted_units': set_fields.get('contracted_units', existing.get('contracted_units')),
        'monthly_total': set_fields.get('monthly_total', existing.get('monthly_total')),
        'status': set_fields.get('status', existing.get('status')),
        'setup_state': set_fields.get('setup_state', existing.get('setup_state')),
    }

    if unit_change_type == 'increase':
        action = 'contracted_units_increase'
    elif unit_change_type == 'decrease_scheduled':
        action = 'contracted_units_decrease_scheduled'
    elif 'contracted_units' in updates and updates['contracted_units'] != existing.get('contracted_units'):
        action = 'contracted_units_changed'
    else:
        action = 'project_billing_updated'

    audit_payload = {
        'project_id': existing['project_id'],
        'org_id': existing['org_id'],
        'before': before, 'after': after,
    }
    if unit_change_type == 'decrease_scheduled':
        audit_payload['pending_contracted_units'] = set_fields.get('pending_contracted_units')
        audit_payload['pending_effective_from'] = set_fields.get('pending_effective_from')

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'billing',
        'entity_type': 'project_billing',
        'entity_id': project_billing_id,
        'action': action,
        'actor_id': actor_id,
        'payload': audit_payload,
        'created_at': ts,
    })

    updated = await db.project_billing.find_one({'id': project_billing_id}, {'_id': 0})
    return updated


async def request_billing_handoff(project_billing_id: str, actor_id: str, note: str = None) -> dict:
    db = get_db()
    existing = await db.project_billing.find_one({'id': project_billing_id}, {'_id': 0})
    if not existing:
        raise ValueError('רשומת חיוב לא נמצאה')

    current_state = existing.get('setup_state', 'trial')
    if not validate_setup_transition(current_state, 'pending_handoff'):
        raise ValueError(f'מעבר לא תקין: {current_state} -> pending_handoff')

    ts = _now()
    set_fields = {'setup_state': 'pending_handoff', 'updated_at': ts}
    if note:
        set_fields['billing_contact_note'] = note

    await db.project_billing.update_one({'id': project_billing_id}, {'$set': set_fields})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'project_billing',
        'entity_id': project_billing_id,
        'action': 'billing_handoff_requested',
        'actor_id': actor_id,
        'payload': {
            'project_id': existing['project_id'],
            'org_id': existing['org_id'],
            'note': note,
            'before_state': current_state,
            'after_state': 'pending_handoff',
        },
        'created_at': ts,
    })

    updated = await db.project_billing.find_one({'id': project_billing_id}, {'_id': 0})
    return updated


async def acknowledge_billing_handoff(project_billing_id: str, actor_id: str) -> dict:
    db = get_db()
    existing = await db.project_billing.find_one({'id': project_billing_id}, {'_id': 0})
    if not existing:
        raise ValueError('רשומת חיוב לא נמצאה')

    current_state = existing.get('setup_state', 'trial')
    if not validate_setup_transition(current_state, 'pending_billing_setup'):
        raise ValueError(f'מעבר לא תקין: {current_state} -> pending_billing_setup')

    ts = _now()
    await db.project_billing.update_one(
        {'id': project_billing_id},
        {'$set': {'setup_state': 'pending_billing_setup', 'updated_at': ts}}
    )

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'project_billing',
        'entity_id': project_billing_id,
        'action': 'billing_handoff_acknowledged',
        'actor_id': actor_id,
        'payload': {
            'project_id': existing['project_id'],
            'org_id': existing['org_id'],
            'before_state': current_state,
            'after_state': 'pending_billing_setup',
        },
        'created_at': ts,
    })

    updated = await db.project_billing.find_one({'id': project_billing_id}, {'_id': 0})
    return updated


async def complete_billing_setup(project_billing_id: str, actor_id: str) -> dict:
    db = get_db()
    existing = await db.project_billing.find_one({'id': project_billing_id}, {'_id': 0})
    if not existing:
        raise ValueError('רשומת חיוב לא נמצאה')

    if not existing.get('plan_id'):
        raise ValueError('חובה לבחור תוכנית לפני השלמת ההגדרה')
    if not existing.get('contracted_units') or existing['contracted_units'] <= 0:
        raise ValueError('חובה להגדיר יחידות חוזיות לפני השלמת ההגדרה')

    current_state = existing.get('setup_state', 'trial')
    target_state = 'ready'
    if not validate_setup_transition(current_state, target_state):
        raise ValueError(f'מעבר לא תקין: {current_state} -> {target_state}')

    ts = _now()
    await db.project_billing.update_one(
        {'id': project_billing_id},
        {'$set': {'setup_state': target_state, 'updated_at': ts}}
    )

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'project_billing',
        'entity_id': project_billing_id,
        'action': 'project_billing_setup_completed',
        'actor_id': actor_id,
        'payload': {
            'project_id': existing['project_id'],
            'org_id': existing['org_id'],
            'plan_id': existing.get('plan_id'),
            'contracted_units': existing.get('contracted_units'),
            'monthly_total': existing.get('monthly_total'),
            'before_state': current_state,
            'after_state': target_state,
        },
        'created_at': ts,
    })

    updated = await db.project_billing.find_one({'id': project_billing_id}, {'_id': 0})
    return updated


async def get_billing_for_org(org_id: str, user_id: Optional[str] = None) -> dict:
    db = get_db()
    org = await db.organizations.find_one({'id': org_id}, {'_id': 0})
    if not org:
        return {'error': 'ארגון לא נמצא'}

    await apply_pending_decreases(org_id)

    sub = await get_subscription(org_id)

    if not sub:
        trial_end = org.get('trial_end_at') or org.get('trial_end_date')
        synthetic_sub = {
            'status': 'trialing' if trial_end else 'none',
            'trial_end_at': trial_end,
            'paid_until': None,
            'billing_email': None,
            'billing_cycle': None,
            'auto_renew': False,
            'next_charge_at': None,
            'grace_until': None,
            'manual_override': None,
        }
        logger.warning("Returning default subscription for org %s (no DB record, trial_end=%s)", org_id, trial_end)
    else:
        synthetic_sub = None

    effective_sub = synthetic_sub or sub

    project_billings = await db.project_billing.find(
        {'org_id': org_id}, {'_id': 0}
    ).to_list(1000)

    for pb in project_billings:
        observed = await compute_observed_units(pb['project_id'])
        await _refresh_peak_units(pb, observed)
    project_billings = await db.project_billing.find(
        {'org_id': org_id}, {'_id': 0}
    ).to_list(1000)

    total_monthly = sum(
        pb.get('monthly_total', 0) for pb in project_billings
        if pb.get('status') == 'active'
    )

    projects = []
    billed_project_ids = set()
    for pb in project_billings:
        proj = await db.projects.find_one({'id': pb['project_id']}, {'_id': 0, 'id': 1, 'name': 1})
        projects.append({
            **pb,
            'project_name': proj.get('name', '') if proj else '',
        })
        billed_project_ids.add(pb['project_id'])

    all_org_projects = await db.projects.find(
        {'org_id': org_id}, {'_id': 0, 'id': 1, 'name': 1}
    ).to_list(1000)
    for proj in all_org_projects:
        if proj['id'] not in billed_project_ids:
            projects.append({
                'project_id': proj['id'],
                'org_id': org_id,
                'project_name': proj.get('name', ''),
                'plan_id': None,
                'contracted_units': 0,
                'status': None,
                'monthly_total': 0,
            })

    org_members = await db.organization_memberships.find(
        {'org_id': org_id, 'role': {'$in': list(ORG_BILLING_ROLES)}},
        {'_id': 0}
    ).to_list(100)

    billing_users = []
    for mem in org_members:
        user = await db.users.find_one({'id': mem['user_id']}, {'_id': 0, 'id': 1, 'name': 1, 'email': 1})
        if user:
            billing_users.append({'user_id': user['id'], 'name': user.get('name', ''), 'role': mem['role']})

    access, reason = _resolve_access(effective_sub)
    snapshot = compute_subscription_snapshot(effective_sub)

    can_manage = False
    owner_name = None
    is_pm = False
    if user_id:
        is_sa = False
        sa_doc = await db.users.find_one({'id': user_id}, {'_id': 0, 'platform_role': 1})
        if sa_doc and sa_doc.get('platform_role') == 'super_admin':
            is_sa = True
        is_owner = org.get('owner_user_id') == user_id
        billing_role = await check_org_billing_role(user_id, org_id) if not is_sa else 'super_admin'
        can_manage = is_sa or (billing_role in ('org_admin', 'billing_admin', 'owner'))
        if not can_manage:
            is_pm = await check_org_pm_role(user_id, org_id)
            if is_pm:
                can_manage = True
            else:
                owner_user = await db.users.find_one({'id': org.get('owner_user_id')}, {'_id': 0, 'name': 1})
                owner_name = owner_user.get('name', '') if owner_user else None

    pc = org.get('payment_config') or {}
    payment_config = {
        'bank_details': pc.get('bank_details', ''),
        'bit_phone': pc.get('bit_phone', ''),
        'has_payment_options': bool(pc.get('bank_details') or pc.get('bit_phone')),
    } if can_manage else None

    from services.object_storage import generate_url as _gen_url
    raw_logo = org.get('logo_url')
    resolved_logo = _gen_url(raw_logo) if raw_logo else None

    return {
        'org_id': org_id,
        'org_name': org.get('name', ''),
        'owner_user_id': org.get('owner_user_id'),
        'logo_url': resolved_logo,
        'can_manage_billing': can_manage,
        'is_org_pm': is_pm,
        'owner_name': owner_name,
        'payment_config': payment_config,
        'subscription': {
            'status': effective_sub.get('status'),
            'trial_end_at': effective_sub.get('trial_end_at'),
            'paid_until': effective_sub.get('paid_until'),
            'billing_email': effective_sub.get('billing_email'),
            'total_monthly': total_monthly,
            'effective_access': access.value,
            'read_only_reason': reason,
            'subscription_status': snapshot['subscription_status'],
            'billing_cycle': snapshot['billing_cycle'],
            'auto_renew': snapshot['auto_renew'],
            'next_charge_at': snapshot['next_charge_at'],
            'grace_until': snapshot['grace_until'],
        },
        'projects': projects,
        'billing_roles': billing_users,
    }


async def preview_renewal(org_id: str, cycle: str) -> dict:
    db = get_db()
    sub = await get_subscription(org_id)
    now_utc = _now_dt()

    paid_until = _parse_dt(sub.get('paid_until')) if sub else None
    trial_end_at = _parse_dt(sub.get('trial_end_at')) if sub else None

    effective_start = max(now_utc, paid_until) if paid_until else now_utc
    if trial_end_at:
        effective_start = max(effective_start, trial_end_at)

    if cycle == 'yearly':
        new_paid_until = effective_start.replace(year=effective_start.year + 1)
    else:
        month = effective_start.month + 1
        year = effective_start.year
        if month > 12:
            month = 1
            year += 1
        day = min(effective_start.day, 28)
        new_paid_until = effective_start.replace(year=year, month=month, day=day)

    local_dt = new_paid_until.astimezone(IL_TZ)
    end_of_day_local = local_dt.replace(hour=23, minute=59, second=59, microsecond=0)
    end_of_day_utc = end_of_day_local.astimezone(timezone.utc)

    display_date = end_of_day_local.strftime('%d/%m/%Y')

    return {
        'cycle': cycle,
        'effective_start': effective_start.isoformat(),
        'new_paid_until': end_of_day_utc.isoformat(),
        'new_paid_until_display': display_date,
        'next_charge_at': None,
        'auto_renew_default': False,
    }


async def _refresh_peak_units(pb: dict, observed: int) -> bool:
    db = get_db()
    contracted = pb.get('contracted_units', 0)
    current_peak = pb.get('cycle_peak_units', contracted)
    new_peak = max(current_peak, observed, contracted)
    if new_peak != current_peak:
        await db.project_billing.update_one(
            {'id': pb['id']},
            {'$set': {'cycle_peak_units': new_peak, 'observed_units': observed}}
        )
        return True
    return False


async def get_billing_for_project(project_id: str) -> dict:
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'id': 1, 'name': 1, 'org_id': 1})
    if not project:
        return {'error': 'פרויקט לא נמצא'}

    org_id = project.get('org_id')
    if not org_id:
        return {'error': 'פרויקט ללא ארגון', 'project_id': project_id, 'project_name': project.get('name', '')}

    await apply_pending_decreases(org_id)

    pb = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0})

    observed = await compute_observed_units(project_id)

    if pb:
        await _refresh_peak_units(pb, observed)
        pb = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0})

    org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'name': 1})
    sub = await get_subscription(org_id)
    access = await get_effective_access('', org_id)
    _, reason = _resolve_access(sub)

    snapshot = compute_subscription_snapshot(sub)
    computed_status = snapshot.get('subscription_status', 'none')
    display_status = 'trialing' if computed_status == 'trial' else computed_status

    result = {
        'project_id': project_id,
        'project_name': project.get('name', ''),
        'org_id': org_id,
        'org_name': org.get('name', '') if org else '',
        'effective_access': access.value,
        'subscription_status': display_status,
        'read_only_reason': reason,
        'paid_until': sub.get('paid_until') if sub and computed_status == 'active' else None,
        'trial_end_at': sub.get('trial_end_at') if sub and computed_status == 'trial' else None,
        'billing': {
            'id': pb['id'],
            'plan_id': pb.get('plan_id'),
            'contracted_units': pb.get('contracted_units', 0),
            'observed_units': observed,
            'cycle_peak_units': pb.get('cycle_peak_units', pb.get('contracted_units', 0)),
            'tier_code': pb.get('tier_code', 'none'),
            'project_fee_snapshot': pb.get('project_fee_snapshot', 0),
            'tier_fee_snapshot': pb.get('tier_fee_snapshot', 0),
            'pricing_version': pb.get('pricing_version', 0),
            'monthly_total': pb.get('monthly_total', 0),
            'status': pb.get('status', 'active'),
            'setup_state': pb.get('setup_state', 'trial'),
            'billing_contact_note': pb.get('billing_contact_note'),
            'pending_contracted_units': pb.get('pending_contracted_units'),
            'pending_effective_from': pb.get('pending_effective_from'),
        } if pb else None,
    }
    return result


async def recalc_org_total(org_id: str):
    db = get_db()
    project_billings = await db.project_billing.find(
        {'org_id': org_id, 'status': 'active'}, {'_id': 0, 'monthly_total': 1}
    ).to_list(1000)
    total = sum(pb.get('monthly_total', 0) for pb in project_billings)
    await db.subscriptions.update_one(
        {'org_id': org_id},
        {'$set': {'total_monthly': total, 'updated_at': _now()}}
    )
    return total


async def dry_run_org_id_backfill() -> dict:
    db = get_db()
    total = await db.projects.count_documents({})
    with_org = await db.projects.count_documents({'org_id': {'$exists': True, '$ne': None}})
    missing_org = await db.projects.find(
        {'$or': [{'org_id': {'$exists': False}}, {'org_id': None}]},
        {'_id': 0, 'id': 1, 'name': 1, 'created_by': 1}
    ).to_list(10000)

    auto_resolvable = []
    ambiguous = []

    for proj in missing_org:
        creator_id = proj.get('created_by')
        if not creator_id:
            ambiguous.append({**proj, 'reason': 'no_creator'})
            continue
        org_mems = await db.organization_memberships.find(
            {'user_id': creator_id}, {'_id': 0, 'org_id': 1}
        ).to_list(100)
        unique_orgs = list({m['org_id'] for m in org_mems if m.get('org_id')})
        if len(unique_orgs) == 1:
            auto_resolvable.append({**proj, 'target_org_id': unique_orgs[0]})
        elif len(unique_orgs) == 0:
            ambiguous.append({**proj, 'reason': 'creator_has_no_org'})
        else:
            ambiguous.append({**proj, 'reason': 'creator_in_multiple_orgs', 'org_ids': unique_orgs})

    return {
        'total_projects': total,
        'projects_with_org_id': with_org,
        'projects_missing_org_id': len(missing_org),
        'auto_resolvable_count': len(auto_resolvable),
        'ambiguous_count': len(ambiguous),
        'auto_resolvable': auto_resolvable,
        'ambiguous': ambiguous,
    }


async def apply_org_id_backfill(actor_id: str) -> dict:
    db = get_db()
    dry_run = await dry_run_org_id_backfill()
    applied = []
    skipped = dry_run['ambiguous']

    for proj in dry_run['auto_resolvable']:
        current = await db.projects.find_one(
            {'id': proj['id']}, {'_id': 0, 'org_id': 1}
        )
        if current and current.get('org_id'):
            continue

        target_org_id = proj['target_org_id']
        await db.projects.update_one(
            {'id': proj['id']},
            {'$set': {'org_id': target_org_id}}
        )
        ts = _now()
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'project',
            'entity_id': proj['id'],
            'action': 'org_id_backfill_applied',
            'actor_id': actor_id,
            'payload': {
                'project_id': proj['id'],
                'project_name': proj.get('name', ''),
                'assigned_org_id': target_org_id,
            },
            'created_at': ts,
        })
        applied.append({
            'project_id': proj['id'],
            'project_name': proj.get('name', ''),
            'assigned_org_id': target_org_id,
        })

    return {
        'applied_count': len(applied),
        'skipped_count': len(skipped),
        'applied': applied,
        'skipped': skipped,
    }


async def get_billing_contact(org_id: str) -> dict:
    db = get_db()
    org = await db.organizations.find_one({'id': org_id}, {
        '_id': 0, 'id': 1, 'billing_email': 1, 'billing_cc_emails': 1, 'billing_contact_name': 1
    })
    if org is None:
        return {'error': 'ארגון לא נמצא'}
    return {
        'org_id': org_id,
        'billing_email': org.get('billing_email') or None,
        'billing_cc_emails': org.get('billing_cc_emails') or [],
        'billing_contact_name': org.get('billing_contact_name') or None,
    }


async def update_billing_contact(org_id: str, updates: dict, actor_id: str) -> dict:
    db = get_db()
    org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'id': 1})
    if not org:
        return {'error': 'ארגון לא נמצא'}

    allowed_fields = {'billing_email', 'billing_cc_emails', 'billing_contact_name'}
    set_fields = {}
    for k, v in updates.items():
        if k in allowed_fields:
            set_fields[k] = v
    if not set_fields:
        return {'error': 'אין שדות לעדכון'}

    set_fields['updated_at'] = _now()
    await db.organizations.update_one({'id': org_id}, {'$set': set_fields})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'billing',
        'entity_type': 'organization',
        'entity_id': org_id,
        'action': 'billing_contact_updated',
        'actor_id': actor_id,
        'created_at': _now(),
        'payload': {k: v for k, v in set_fields.items() if k != 'updated_at'},
    })

    logger.info(f"[BILLING-CONTACT] Updated for org {org_id} by {actor_id}: {list(set_fields.keys())}")
    return await get_billing_contact(org_id)


OPEN_REQUEST_STATUSES = ['requested', 'sent', 'pending_review']


async def check_org_pm_role(user_id: str, org_id: str) -> bool:
    db = get_db()
    mem = await db.organization_memberships.find_one(
        {'org_id': org_id, 'user_id': user_id, 'role': 'project_manager'}, {'_id': 0, 'role': 1}
    )
    return bool(mem)


async def cancel_payment_request(org_id: str, request_id: str, actor_id: str) -> dict:
    db = get_db()
    req = await db.billing_payment_requests.find_one(
        {'id': request_id}, {'_id': 0}
    )
    if not req or req.get('org_id') != org_id:
        raise FileNotFoundError('בקשת תשלום לא נמצאה')
    status = req.get('status', '')
    if status in ('requested', 'sent'):
        now = _now()
        await db.billing_payment_requests.update_one(
            {'id': request_id},
            {'$set': {'status': 'canceled', 'updated_at': now}}
        )
        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'event_type': 'billing',
            'entity_type': 'organization',
            'entity_id': org_id,
            'action': 'billing_payment_request_canceled',
            'actor_id': actor_id,
            'created_at': now,
            'payload': {'request_id': request_id, 'previous_status': status},
        })
        logger.info(f"[BILLING-PAYMENT-REQ] Canceled {request_id} by {actor_id}")
        return {'ok': True, 'request_id': request_id}
    status_labels = {
        'pending_review': 'הבקשה בבדיקה ולא ניתן לבטלה',
        'paid': 'הבקשה כבר אושרה ושולמה',
        'rejected': 'הבקשה כבר נדחתה',
        'canceled': 'הבקשה כבר בוטלה',
    }
    msg = status_labels.get(status, f'לא ניתן לבטל בקשה בסטטוס {status}')
    raise ValueError(msg)


async def compute_org_billing_amount(org_id: str, cycle: str = 'monthly') -> dict:
    db = get_db()
    from contractor_ops.billing_plans import calculate_monthly

    sub = await get_subscription(org_id)
    total_monthly = 0
    breakdown = []
    if sub:
        project_billings = await db.project_billing.find(
            {'org_id': org_id, 'status': 'active'}, {'_id': 0}
        ).to_list(1000)
        sorted_pbs = sorted(project_billings, key=lambda p: (p.get('created_at', ''), p.get('project_id', '')))
        for idx, pb in enumerate(sorted_pbs):
            contracted = pb.get('contracted_units', 0)
            observed = await compute_observed_units(pb['project_id'])
            await _refresh_peak_units(pb, observed)
            pb = await db.project_billing.find_one({'id': pb['id']}, {'_id': 0}) or pb
            contracted = pb.get('contracted_units', 0)
            peak = pb.get('cycle_peak_units', contracted)
            peak = max(peak, observed, contracted)
            billable = max(contracted, peak)
            plan_id = pb.get('plan_id')
            proj_monthly = calculate_monthly(
                billable, plan_id=plan_id, project_index=idx + 1
            )
            total_monthly += proj_monthly
            proj = await db.projects.find_one({'id': pb['project_id']}, {'_id': 0, 'name': 1})
            breakdown.append({
                'project_id': pb.get('project_id'),
                'project_name': proj.get('name', '') if proj else '',
                'plan_id': plan_id,
                'contracted_units': contracted,
                'observed_units': observed,
                'cycle_peak_units': peak,
                'billable_units': billable,
                'monthly_total': proj_monthly,
            })

    amount_ils = total_monthly if cycle == 'monthly' else total_monthly * 12
    return {
        'amount_ils': amount_ils,
        'total_monthly': total_monthly,
        'breakdown': breakdown,
    }


async def create_payment_request(org_id: str, user_id: str, cycle: str, note: str = '', contact_email: str = '', requested_by_kind: str = 'unknown') -> dict:
    db = get_db()
    from contractor_ops.billing_plans import calculate_monthly
    now = _now()

    await apply_pending_decreases(org_id)

    existing = await db.billing_payment_requests.find_one({
        'org_id': org_id,
        'status': {'$in': OPEN_REQUEST_STATUSES},
    }, {'_id': 0}, sort=[('created_at', -1)])
    if existing:
        pu = _parse_dt(existing.get('requested_paid_until'))
        display = pu.astimezone(IL_TZ).strftime('%d/%m/%Y') if pu else '—'
        return {
            'request_id': existing['id'],
            'requested_paid_until': existing.get('requested_paid_until'),
            'requested_paid_until_display': display,
            'amount_ils': existing.get('amount_ils', 0),
            'existing': True,
            'existing_open': True,
        }

    renewal = await preview_renewal(org_id, cycle)
    requested_paid_until = renewal['new_paid_until']

    total_monthly = 0
    billing_breakdown = []
    project_billings = await db.project_billing.find(
        {'org_id': org_id, 'status': 'active'}, {'_id': 0}
    ).to_list(1000)
    if project_billings:
        sorted_pbs = sorted(project_billings, key=lambda p: (p.get('created_at', ''), p.get('project_id', '')))
        for idx, pb in enumerate(sorted_pbs):
            contracted = pb.get('contracted_units', 0)
            observed = await compute_observed_units(pb['project_id'])
            await _refresh_peak_units(pb, observed)
            pb = await db.project_billing.find_one({'id': pb['id']}, {'_id': 0}) or pb
            contracted = pb.get('contracted_units', 0)
            peak = pb.get('cycle_peak_units', contracted)
            peak = max(peak, observed, contracted)
            billable = max(contracted, peak)
            plan_id = pb.get('plan_id')
            proj_monthly = calculate_monthly(
                billable, plan_id=plan_id, project_index=idx + 1
            )
            total_monthly += proj_monthly
            proj = await db.projects.find_one({'id': pb['project_id']}, {'_id': 0, 'name': 1})
            billing_breakdown.append({
                'project_id': pb.get('project_id'),
                'project_name': proj.get('name', '') if proj else '',
                'plan_id': plan_id,
                'contracted_units': contracted,
                'observed_units': observed,
                'cycle_peak_units': peak,
                'billable_units': billable,
                'monthly_total': proj_monthly,
            })

    amount_ils = total_monthly if cycle == 'monthly' else total_monthly * 12

    if amount_ils == 0:
        logger.warning(f"[BILLING-PAYMENT-REQ] amount_ils=0 for org {org_id} — no active project billing configured")
        raise ValueError('לא ניתן ליצור בקשת תשלום כי סכום החיוב הוא ₪0. יש להגדיר תמחור פרויקטים/תכנית חיוב בארגון.')

    request_id = str(uuid.uuid4())
    record = {
        'id': request_id,
        'org_id': org_id,
        'requested_by_user_id': user_id,
        'requested_by_kind': requested_by_kind,
        'cycle': cycle,
        'requested_paid_until': requested_paid_until,
        'amount_ils': amount_ils,
        'billable_total_monthly': total_monthly,
        'billing_breakdown': billing_breakdown,
        'status': 'requested',
        'note': note,
        'contact_email': contact_email,
        'created_at': now,
        'updated_at': now,
    }
    await db.billing_payment_requests.insert_one(record)

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'billing',
        'entity_type': 'organization',
        'entity_id': org_id,
        'action': 'billing_payment_request_created',
        'actor_id': user_id,
        'created_at': now,
        'payload': {
            'request_id': request_id,
            'cycle': cycle,
            'requested_paid_until': requested_paid_until,
            'amount_ils': amount_ils,
            'billable_total_monthly': total_monthly,
        },
    })

    logger.info(f"[BILLING-PAYMENT-REQ] Created {request_id} for org {org_id} by {user_id}: cycle={cycle} amount={amount_ils} billable_monthly={total_monthly}")

    return {
        'request_id': request_id,
        'requested_paid_until': requested_paid_until,
        'requested_paid_until_display': renewal['new_paid_until_display'],
        'amount_ils': amount_ils,
        'existing': False,
    }


async def customer_mark_paid(org_id: str, request_id: str, actor_id: str, customer_paid_note: str = '') -> dict:
    db = get_db()
    now = _now()

    req = await db.billing_payment_requests.find_one({'id': request_id}, {'_id': 0})
    if not req:
        raise ValueError('בקשת תשלום לא נמצאה')
    if req.get('org_id') != org_id:
        raise PermissionError('בקשת תשלום לא שייכת לארגון זה')
    if req.get('status') == 'pending_review':
        return {'status': 'pending_review', 'request_id': request_id, 'already': True}
    if req.get('status') not in ('requested', 'sent'):
        status_labels = {'paid': 'אושר ושולם', 'canceled': 'בוטל', 'rejected': 'נדחה'}
        label = status_labels.get(req['status'], req['status'])
        raise ValueError(f'לא ניתן לסמן — הבקשה כבר במצב: {label}')

    await db.billing_payment_requests.update_one(
        {'id': request_id},
        {'$set': {
            'status': 'pending_review',
            'customer_paid_note': customer_paid_note,
            'customer_marked_paid_at': now,
            'customer_marked_paid_by': actor_id,
            'updated_at': now,
        }}
    )

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'billing',
        'entity_type': 'organization',
        'entity_id': org_id,
        'action': 'billing_customer_marked_paid',
        'actor_id': actor_id,
        'created_at': now,
        'payload': {
            'request_id': request_id,
            'customer_paid_note': customer_paid_note,
        },
    })

    logger.info(f"[BILLING-CUSTOMER-MARKED-PAID] org={org_id} request={request_id} actor={actor_id}")
    return {'status': 'pending_review', 'request_id': request_id}


async def upload_receipt(org_id: str, request_id: str, actor_id: str, file_data: bytes, filename: str, content_type: str) -> dict:
    from services.object_storage import save_bytes
    db = get_db()
    now = _now()

    req = await db.billing_payment_requests.find_one({'id': request_id}, {'_id': 0})
    if not req:
        raise ValueError('בקשת תשלום לא נמצאה')
    if req.get('org_id') != org_id:
        raise PermissionError('בקשת תשלום לא שייכת לארגון זה')
    if req.get('status') in ('paid', 'canceled', 'rejected'):
        raise ValueError('לא ניתן להעלות אסמכתא לבקשה שסגורה')

    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'bin'
    storage_key = f"billing-receipts/{org_id}/{request_id}.{ext}"
    ref = save_bytes(file_data, storage_key, content_type)

    receipt_meta = {
        'ref': ref,
        'filename': filename,
        'size': len(file_data),
        'content_type': content_type,
        'uploaded_at': now,
        'uploaded_by': actor_id,
    }

    await db.billing_payment_requests.update_one(
        {'id': request_id},
        {'$set': {'receipt': receipt_meta, 'updated_at': now}}
    )

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'billing',
        'entity_type': 'organization',
        'entity_id': org_id,
        'action': 'billing_receipt_uploaded',
        'actor_id': actor_id,
        'created_at': now,
        'payload': {
            'request_id': request_id,
            'filename': filename,
            'size': len(file_data),
            'content_type': content_type,
        },
    })

    logger.info(f"[BILLING-RECEIPT] Uploaded for request={request_id} org={org_id} by={actor_id} file={filename}")
    return {'request_id': request_id, 'filename': filename, 'size': len(file_data)}


async def get_receipt_url(org_id: str, request_id: str) -> dict:
    from services.object_storage import resolve_url
    db = get_db()

    req = await db.billing_payment_requests.find_one({'id': request_id}, {'_id': 0})
    if not req:
        raise ValueError('בקשת תשלום לא נמצאה')
    if req.get('org_id') != org_id:
        raise PermissionError('בקשת תשלום לא שייכת לארגון זה')

    receipt = req.get('receipt')
    if not receipt:
        raise ValueError('לא נמצאה אסמכתא לבקשה זו')

    url = resolve_url(receipt.get('ref', ''))
    return {'url': url, 'filename': receipt.get('filename', ''), 'content_type': receipt.get('content_type', '')}


async def reject_payment_request(org_id: str, request_id: str, actor_id: str, rejection_reason: str = '') -> dict:
    db = get_db()
    now = _now()

    req = await db.billing_payment_requests.find_one({'id': request_id}, {'_id': 0})
    if not req:
        raise ValueError('בקשת תשלום לא נמצאה')
    if req.get('org_id') != org_id:
        raise PermissionError('בקשת תשלום לא שייכת לארגון זה')
    if req.get('status') == 'paid':
        raise ValueError('לא ניתן לדחות בקשה שכבר אושרה')
    if req.get('status') in ('canceled', 'rejected'):
        raise ValueError(f'הבקשה כבר במצב: {req["status"]}')

    await db.billing_payment_requests.update_one(
        {'id': request_id},
        {'$set': {'status': 'rejected', 'rejection_reason': rejection_reason, 'updated_at': now}}
    )

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'billing',
        'entity_type': 'organization',
        'entity_id': org_id,
        'action': 'billing_payment_request_rejected',
        'actor_id': actor_id,
        'created_at': now,
        'payload': {
            'request_id': request_id,
            'rejection_reason': rejection_reason,
        },
    })

    logger.info(f"[BILLING-REJECT] request={request_id} org={org_id} actor={actor_id}")
    return {'status': 'rejected', 'request_id': request_id}


async def mark_paid(org_id: str, actor_id: str, request_id: str = None, cycle: str = None, paid_note: str = '') -> dict:
    db = get_db()
    now = _now()

    if request_id:
        req = await db.billing_payment_requests.find_one({'id': request_id}, {'_id': 0})
        if not req:
            raise ValueError('בקשת תשלום לא נמצאה')
        if req.get('org_id') != org_id:
            raise PermissionError('בקשת תשלום לא שייכת לארגון זה')
        if req.get('status') in ('paid', 'canceled'):
            raise ValueError(f'בקשת תשלום כבר במצב: {req["status"]}')
        if req.get('status') == 'rejected':
            raise ValueError('לא ניתן לאשר בקשה שנדחתה — צור בקשה חדשה')
        cycle = req['cycle']
        new_paid_until_iso = req['requested_paid_until']
    elif cycle:
        if cycle not in ('monthly', 'yearly'):
            raise ValueError('cycle חייב להיות monthly או yearly')
        renewal = await preview_renewal(org_id, cycle)
        new_paid_until_iso = renewal['new_paid_until']
    else:
        raise ValueError('חובה לספק request_id או cycle')

    sub = await get_subscription(org_id)
    existing_paid_until = _parse_dt(sub.get('paid_until')) if sub else None
    new_paid_until = _parse_dt(new_paid_until_iso)

    if existing_paid_until and existing_paid_until > new_paid_until:
        new_paid_until = existing_paid_until
        new_paid_until_iso = existing_paid_until.isoformat()

    mo = (sub.get('manual_override') or {}) if sub else {}
    new_status = 'suspended' if mo.get('is_suspended') else 'active'

    update_fields = {
        'status': new_status,
        'paid_until': new_paid_until_iso,
        'auto_renew': False,
        'next_charge_at': None,
        'updated_at': now,
    }

    if sub:
        await db.subscriptions.update_one(
            {'org_id': org_id},
            {'$set': update_fields}
        )
    else:
        await db.subscriptions.insert_one({
            'org_id': org_id,
            **update_fields,
            'created_at': now,
        })

    if request_id:
        await db.billing_payment_requests.update_one(
            {'id': request_id},
            {'$set': {'status': 'paid', 'updated_at': now}}
        )

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'billing',
        'entity_type': 'organization',
        'entity_id': org_id,
        'action': 'billing_mark_paid',
        'actor_id': actor_id,
        'created_at': now,
        'payload': {
            'new_paid_until': new_paid_until_iso,
            'cycle': cycle,
            'request_id': request_id,
            'paid_note': paid_note,
            'previous_paid_until': existing_paid_until.isoformat() if existing_paid_until else None,
        },
    })

    logger.info(f"[BILLING-MARK-PAID] org={org_id} actor={actor_id} new_paid_until={new_paid_until_iso} request_id={request_id}")

    updated_sub = await get_subscription(org_id)
    snapshot = compute_subscription_snapshot(updated_sub)
    access, _ = _resolve_access(updated_sub)

    return {
        'paid_until': new_paid_until_iso,
        'subscription_status': snapshot['subscription_status'],
        'effective_access': access.value,
    }


async def list_payment_requests(org_id: str, statuses: Optional[List[str]] = None, requested_by_user_id: Optional[str] = None) -> dict:
    db = get_db()
    query = {'org_id': org_id}
    if statuses:
        query['status'] = {'$in': statuses}
    if requested_by_user_id:
        query['requested_by_user_id'] = requested_by_user_id

    requests = await db.billing_payment_requests.find(
        query, {'_id': 0}
    ).sort('created_at', -1).limit(50).to_list(50)

    user_ids = list(set(r.get('requested_by_user_id', '') for r in requests if r.get('requested_by_user_id')))
    user_map = {}
    if user_ids:
        users = await db.users.find(
            {'id': {'$in': user_ids}}, {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(100)
        user_map = {u['id']: u.get('name', '') for u in users}

    items = []
    for r in requests:
        receipt = r.get('receipt')
        item = {
            'id': r['id'],
            'cycle': r.get('cycle'),
            'requested_paid_until': r.get('requested_paid_until'),
            'amount_ils': r.get('amount_ils', 0),
            'status': r.get('status'),
            'note': r.get('note', ''),
            'customer_paid_note': r.get('customer_paid_note', ''),
            'rejection_reason': r.get('rejection_reason', ''),
            'requester_name': user_map.get(r.get('requested_by_user_id', ''), ''),
            'requested_by_user_id': r.get('requested_by_user_id'),
            'has_receipt': bool(receipt),
            'receipt_filename': receipt.get('filename', '') if receipt else '',
            'created_at': r.get('created_at'),
            'updated_at': r.get('updated_at'),
        }
        items.append(item)

    return {'requests': items}


async def get_payment_config(org_id: str) -> dict:
    db = get_db()
    org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'id': 1, 'payment_config': 1})
    if not org:
        return {'error': 'ארגון לא נמצא'}
    pc = org.get('payment_config') or {}
    return {
        'bank_details': pc.get('bank_details', ''),
        'bit_phone': pc.get('bit_phone', ''),
    }


async def update_payment_config(org_id: str, actor_id: str, bank_details: str = '', bit_phone: str = '') -> dict:
    db = get_db()
    now = _now()
    pc = {
        'bank_details': bank_details.strip(),
        'bit_phone': bit_phone.strip(),
        'updated_at': now,
        'updated_by': actor_id,
    }
    await db.organizations.update_one(
        {'id': org_id},
        {'$set': {'payment_config': pc}}
    )

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'billing',
        'entity_type': 'organization',
        'entity_id': org_id,
        'action': 'billing_payment_config_updated',
        'actor_id': actor_id,
        'created_at': now,
        'payload': {
            'bank_details_set': bool(bank_details.strip()),
            'bit_phone_set': bool(bit_phone.strip()),
        },
    })

    logger.info(f"[BILLING-CONFIG] Payment config updated for org {org_id} by {actor_id}")
    return {
        'bank_details': pc['bank_details'],
        'bit_phone': pc['bit_phone'],
    }


async def list_open_payment_requests_all() -> dict:
    db = get_db()
    open_statuses = ['requested', 'sent', 'pending_review']

    requests = await db.billing_payment_requests.find(
        {'status': {'$in': open_statuses}}, {'_id': 0}
    ).sort('created_at', -1).limit(20).to_list(20)

    open_count = await db.billing_payment_requests.count_documents(
        {'status': {'$in': open_statuses}}
    )

    org_ids = list(set(r.get('org_id', '') for r in requests if r.get('org_id')))
    user_ids = list(set(r.get('requested_by_user_id', '') for r in requests if r.get('requested_by_user_id')))

    org_map = {}
    if org_ids:
        orgs = await db.organizations.find(
            {'id': {'$in': org_ids}}, {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(100)
        org_map = {o['id']: o.get('name', '') for o in orgs}

    user_map = {}
    if user_ids:
        users = await db.users.find(
            {'id': {'$in': user_ids}}, {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(100)
        user_map = {u['id']: u.get('name', '') for u in users}

    REQUESTER_KIND_LABELS = {
        'billing_manager': 'מנהל חיוב',
        'pm_handoff': 'מנהל פרויקט',
        'unknown': 'לא ידוע',
    }

    items = []
    for r in requests:
        receipt = r.get('receipt')
        kind = r.get('requested_by_kind')
        if not kind:
            kind = 'unknown'
            logger.warning(f"[BILLING-SUMMARY] request {r['id']} missing requested_by_kind — displaying as unknown")
        items.append({
            'id': r['id'],
            'org_id': r.get('org_id'),
            'org_name': org_map.get(r.get('org_id', ''), ''),
            'cycle': r.get('cycle'),
            'requested_paid_until': r.get('requested_paid_until'),
            'amount_ils': r.get('amount_ils', 0),
            'status': r.get('status'),
            'requester_name': user_map.get(r.get('requested_by_user_id', ''), ''),
            'requested_by_kind': kind,
            'requester_kind_label': REQUESTER_KIND_LABELS.get(kind, 'לא ידוע'),
            'has_receipt': bool(receipt),
            'created_at': r.get('created_at'),
        })

    return {'open_count': open_count, 'requests': items}
