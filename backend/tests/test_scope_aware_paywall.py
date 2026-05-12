"""BATCH J Phase 1 — Scope-aware paywall unit tests.

Pure unit tests with mocked db. No real Mongo, no integration, no live
server. Three batch-specific gates per Zahi 2026-05-11 follow-up:

  Test 1 — HAPPY PATH: defends "lazy lookup" (zero extra DB queries
           when legacy check returns FULL_ACCESS).
  Test 2 — URL PATTERN RESOLUTION: defends 5 supported URL patterns
           plus negative paths.
  Test 3 — FEATURE FLAG BYPASS: defends env-var rollback.

Test ordering rule (per spec):
  - Test 1 fails → architecture broken, DON'T DEPLOY.
  - Test 1 passes + Test 2 fails → URL parsing broken, DON'T DEPLOY.
  - Test 1+2 pass + Test 3 fails → rollback won't work, DON'T DEPLOY.

Uses asyncio.run() rather than pytest-asyncio to avoid extra config.
"""
import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Test 1 — HAPPY PATH (defends "lazy lookup" architecture)
# ---------------------------------------------------------------------------

def test_1_happy_path_does_not_call_resolve_request_org_id():
    """When get_effective_access returns FULL_ACCESS on the first
    (legacy) call, _resolve_request_org_id MUST NOT be called.
    Otherwise every request incurs 2 extra DB queries.
    """
    from contractor_ops import router as router_mod
    from contractor_ops.billing import EffectiveAccess

    fake_request = MagicMock()
    fake_request.url.path = '/api/tasks/T123/contractor-proof'
    fake_user = {'id': 'U1'}

    with patch.object(
        router_mod, 'get_effective_access',
        new=AsyncMock(return_value=EffectiveAccess.FULL_ACCESS),
    ) as ge_mock, patch.object(
        router_mod, '_resolve_request_org_id',
        new=AsyncMock(return_value='SHOULD_NEVER_BE_CALLED'),
    ) as resolve_mock, patch.object(
        router_mod, 'get_db', new=MagicMock(return_value=MagicMock()),
    ):
        result = asyncio.run(
            router_mod.require_full_access(fake_request, user=fake_user)
        )

    assert result is fake_user, "require_full_access must return the user dict on FULL_ACCESS"
    assert ge_mock.await_count == 1, "get_effective_access should be called exactly once on happy path"
    assert resolve_mock.await_count == 0, (
        "FAIL: _resolve_request_org_id called on happy path — "
        "lazy lookup contract broken; production-wide latency regression"
    )


# ---------------------------------------------------------------------------
# Test 2 — URL PATTERN RESOLUTION
# ---------------------------------------------------------------------------

def _build_mock_db(collection_returns):
    """Build a MagicMock db where db[name].find_one is an AsyncMock
    returning collection_returns[name] (or None).
    Also makes db.<name> attribute access work the same way.
    """
    collection_mocks = {}
    for name, doc in collection_returns.items():
        coll = MagicMock()
        coll.find_one = AsyncMock(return_value=doc)
        collection_mocks[name] = coll

    db = MagicMock()
    db.__getitem__.side_effect = lambda name: collection_mocks.setdefault(
        name, MagicMock(find_one=AsyncMock(return_value=None))
    )
    # Attribute access (db.projects, db.tasks, ...) must hit the same mock.
    for name, coll in collection_mocks.items():
        setattr(db, name, coll)
    return db, collection_mocks


def test_2a_projects_one_hop():
    from contractor_ops.router import _resolve_request_org_id
    db, mocks = _build_mock_db({'projects': {'org_id': 'O_DIRECT'}})
    org_id = asyncio.run(_resolve_request_org_id('/api/projects/P1/foo', db))
    assert org_id == 'O_DIRECT'
    assert mocks['projects'].find_one.await_count == 1


def test_2b_tasks_two_hop():
    from contractor_ops.router import _resolve_request_org_id
    db, mocks = _build_mock_db({
        'tasks': {'project_id': 'P1'},
        'projects': {'org_id': 'O1'},
    })
    org_id = asyncio.run(_resolve_request_org_id('/api/tasks/T1/foo', db))
    assert org_id == 'O1'
    assert mocks['tasks'].find_one.await_count == 1
    assert mocks['projects'].find_one.await_count == 1


def test_2c_buildings_two_hop():
    from contractor_ops.router import _resolve_request_org_id
    db, _ = _build_mock_db({
        'buildings': {'project_id': 'P9'},
        'projects': {'org_id': 'O9'},
    })
    assert asyncio.run(_resolve_request_org_id('/api/buildings/B1/x', db)) == 'O9'


def test_2d_floors_two_hop():
    from contractor_ops.router import _resolve_request_org_id
    db, _ = _build_mock_db({
        'floors': {'project_id': 'P7'},
        'projects': {'org_id': 'O7'},
    })
    assert asyncio.run(_resolve_request_org_id('/api/floors/F1/x', db)) == 'O7'


def test_2e_units_two_hop():
    from contractor_ops.router import _resolve_request_org_id
    db, _ = _build_mock_db({
        'units': {'project_id': 'P3'},
        'projects': {'org_id': 'O3'},
    })
    assert asyncio.run(_resolve_request_org_id('/api/units/U1/x', db)) == 'O3'


def test_2f_negative_no_pattern_match():
    """Paths that don't match any pattern must return None and not
    touch the db (caller falls back to legacy get_user_org)."""
    from contractor_ops.router import _resolve_request_org_id
    db, mocks = _build_mock_db({'projects': {'org_id': 'X'}})
    assert asyncio.run(_resolve_request_org_id('/api/admin/users', db)) is None
    assert mocks['projects'].find_one.await_count == 0


def test_2g_negative_entity_not_found():
    from contractor_ops.router import _resolve_request_org_id
    db, _ = _build_mock_db({'tasks': None})
    assert asyncio.run(_resolve_request_org_id('/api/tasks/MISSING/foo', db)) is None


def test_2h_negative_project_chain_missing():
    """Task found but its project lookup returns None → None."""
    from contractor_ops.router import _resolve_request_org_id
    db, _ = _build_mock_db({
        'tasks': {'project_id': 'P_GONE'},
        'projects': None,
    })
    assert asyncio.run(_resolve_request_org_id('/api/tasks/T1/x', db)) is None


def test_2i_negative_task_without_project_id():
    """Task doc exists but lacks project_id → None (no second hop)."""
    from contractor_ops.router import _resolve_request_org_id
    db, mocks = _build_mock_db({
        'tasks': {},
        'projects': {'org_id': 'SHOULD_NOT_REACH'},
    })
    assert asyncio.run(_resolve_request_org_id('/api/tasks/T1/x', db)) is None
    assert mocks['projects'].find_one.await_count == 0


# ---------------------------------------------------------------------------
# Test 3 — FEATURE FLAG BYPASS (defends rollback)
# ---------------------------------------------------------------------------

def test_3_feature_flag_bypass_ignores_caller_org_id(monkeypatch):
    """With PAYWALL_SCOPE_AWARE_ENABLED='false', get_effective_access
    must IGNORE the caller-provided org_id and fall back to legacy
    get_user_org. This is the env-var rollback contract.
    """
    monkeypatch.setenv('PAYWALL_SCOPE_AWARE_ENABLED', 'false')

    from contractor_ops import billing as billing_mod
    from contractor_ops.billing import EffectiveAccess, get_effective_access

    fake_db = MagicMock()
    fake_db.users = MagicMock()
    fake_db.users.find_one = AsyncMock(return_value=None)  # not super_admin

    get_user_org_mock = AsyncMock(return_value=None)  # no org → READ_ONLY

    with patch.object(billing_mod, 'get_db', new=MagicMock(return_value=fake_db)), \
         patch.object(billing_mod, 'get_user_org', new=get_user_org_mock):
        result = asyncio.run(get_effective_access(user_id='X', org_id='B_PAID'))

    assert get_user_org_mock.await_count == 1, (
        "FAIL: caller-provided org_id was honoured even with flag=false — "
        "env-var rollback won't work"
    )
    get_user_org_mock.assert_awaited_with('X')
    assert result == EffectiveAccess.READ_ONLY


def test_3b_feature_flag_default_true_honours_caller_org_id(monkeypatch):
    """Sanity: with flag unset (default 'true'), caller-provided
    org_id IS honoured (no get_user_org fallback)."""
    monkeypatch.delenv('PAYWALL_SCOPE_AWARE_ENABLED', raising=False)

    from contractor_ops import billing as billing_mod
    from contractor_ops.billing import EffectiveAccess, get_effective_access

    fake_db = MagicMock()
    fake_db.users = MagicMock()
    fake_db.users.find_one = AsyncMock(return_value=None)

    get_user_org_mock = AsyncMock(return_value={'id': 'A_EXPIRED'})
    get_subscription_mock = AsyncMock(return_value={'status': 'active', 'plan': 'standard'})
    resolve_access_mock = MagicMock(return_value=(EffectiveAccess.FULL_ACCESS, 'ok'))

    with patch.object(billing_mod, 'get_db', new=MagicMock(return_value=fake_db)), \
         patch.object(billing_mod, 'get_user_org', new=get_user_org_mock), \
         patch.object(billing_mod, 'get_subscription', new=get_subscription_mock), \
         patch.object(billing_mod, '_resolve_access', new=resolve_access_mock):
        result = asyncio.run(get_effective_access(user_id='X', org_id='B_PAID'))

    assert get_user_org_mock.await_count == 0, (
        "FAIL: get_user_org called when caller passed org_id and flag is default — "
        "scope-aware path not active"
    )
    get_subscription_mock.assert_awaited_with('B_PAID')
    assert result == EffectiveAccess.FULL_ACCESS
