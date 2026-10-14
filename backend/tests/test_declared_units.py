from datetime import datetime, timedelta, timezone

import pytest

from contractor_ops.declared_units import is_trial_status, validate_declared_units


def test_trial_status():
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    assert not is_trial_status(None)
    assert is_trial_status({'status': 'trialing', 'trial_end_at': future})
    assert not is_trial_status({'status': 'trialing', 'trial_end_at': past})
    assert not is_trial_status({
        'status': 'active', 'paid_until': future, 'trial_end_at': future,
    })
    assert not is_trial_status({
        'status': 'trialing', 'trial_end_at': future,
        'manual_override': {'is_suspended': True},
    })


@pytest.mark.parametrize('new,current,active', [(32, 24, 16), (25, 24, 16)])
def test_increase(new, current, active):
    assert validate_declared_units(new, current, active) == new


@pytest.mark.parametrize('new,current,active', [
    (24, 24, 16), (20, 24, 16), (30, 24, 32), (0, 0, 0),
    ('32', 24, 0), (True, 24, 0), (5001, 24, 0),
])
def test_invalid_declaration(new, current, active):
    with pytest.raises(ValueError):
        validate_declared_units(new, current, active)
