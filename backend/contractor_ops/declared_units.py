"""The declared apartment count stays the single cap and price basis.

During a trial an authorized manager may explicitly increase it, with an audit.
Outside a trial, changes go through the admin quota request.
"""
from contractor_ops.billing import compute_subscription_snapshot

MAX_DECLARED_UNITS = 5000


def is_trial_status(sub) -> bool:
    return compute_subscription_snapshot(sub)['subscription_status'] == 'trial'


def validate_declared_units(new_total, current_total: int, active_count: int) -> int:
    """Return a validated int, or raise ValueError with a Hebrew message.

    Policy: only increases through the product; lowering is admin-only so units
    cannot be raised and then lowered before month-end.
    """
    if isinstance(new_total, bool) or not isinstance(new_total, int):
        raise ValueError('כמות הדירות חייבת להיות מספר שלם')
    if new_total < 1 or new_total > MAX_DECLARED_UNITS:
        raise ValueError(f'כמות הדירות חייבת להיות בין 1 ל-{MAX_DECLARED_UNITS}')
    if new_total <= int(current_total or 0):
        raise ValueError(f'אפשר רק להגדיל את כמות הדירות (רשום כיום {current_total})')
    if new_total < active_count:
        raise ValueError(f'לא ניתן להצהיר על {new_total} דירות כשיש כבר {active_count} דירות פעילות')
    return new_total
