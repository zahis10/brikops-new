"""Billing system tests: trial, access gates, admin overrides, org isolation."""
import pytest
import httpx
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta

BASE = "http://localhost:8000"


def _login(email, password):
    r = httpx.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        pytest.skip(f"Cannot login as {email}")
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json().get("user", {})


def _set_platform_role(email, platform_role):
    db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    db.users.update_one({"email": email}, {"$set": {"platform_role": platform_role}})


@pytest.fixture(scope="module")
def super_admin():
    _set_platform_role("admin@contractor-ops.com", "super_admin")
    headers, user = _login("admin@contractor-ops.com", "admin123")
    yield headers, user
    _set_platform_role("admin@contractor-ops.com", "none")


@pytest.fixture(scope="module")
def pm():
    headers, user = _login("pm@contractor-ops.com", "pm123")
    return headers, user


class TestBillingMeEndpoint:

    def test_billing_me_returns_data(self, super_admin):
        headers, user = super_admin
        r = httpx.get(f"{BASE}/api/billing/me", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "effective_access" in data
        assert "org_id" in data
        assert "status" in data
        assert data["effective_access"] in ["full_access", "read_only"]

    def test_billing_me_requires_auth(self):
        r = httpx.get(f"{BASE}/api/billing/me")
        assert r.status_code in [401, 403, 422]


class TestTrialAccess:

    def test_active_trial_has_full_access(self, super_admin):
        headers, user = super_admin
        r = httpx.get(f"{BASE}/api/billing/me", headers=headers)
        assert r.status_code == 200
        data = r.json()
        if data["status"] == "trialing" and data.get("days_remaining", 0) > 0:
            assert data["effective_access"] == "full_access"

    def test_get_requests_always_allowed(self, super_admin):
        headers, user = super_admin
        r = httpx.get(f"{BASE}/api/projects", headers=headers)
        assert r.status_code == 200


class TestAdminOverrides:

    def test_admin_can_list_orgs(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/billing/orgs", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_admin_can_view_audit(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/billing/audit", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_override_requires_note(self, super_admin):
        headers, _ = super_admin
        orgs_r = httpx.get(f"{BASE}/api/admin/billing/orgs", headers=headers)
        if orgs_r.status_code != 200 or len(orgs_r.json()) == 0:
            pytest.skip("No orgs available")
        org_id = orgs_r.json()[0]["id"]
        r = httpx.post(f"{BASE}/api/admin/billing/override", json={
            "org_id": org_id,
            "action": "extend_trial",
            "until": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }, headers=headers)
        assert r.status_code in [400, 422]

    def test_extend_trial_works(self, super_admin):
        headers, _ = super_admin
        orgs_r = httpx.get(f"{BASE}/api/admin/billing/orgs", headers=headers)
        if orgs_r.status_code != 200 or len(orgs_r.json()) == 0:
            pytest.skip("No orgs available")
        org_id = orgs_r.json()[0]["id"]
        new_end = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
        r = httpx.post(f"{BASE}/api/admin/billing/override", json={
            "org_id": org_id,
            "action": "extend_trial",
            "until": new_end,
            "note": "Test extension",
        }, headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data.get("success") is True
        assert data.get("effective_access") == "full_access"

    def test_comp_works(self, super_admin):
        headers, _ = super_admin
        orgs_r = httpx.get(f"{BASE}/api/admin/billing/orgs", headers=headers)
        if orgs_r.status_code != 200 or len(orgs_r.json()) == 0:
            pytest.skip("No orgs available")
        org_id = orgs_r.json()[0]["id"]
        new_end = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
        r = httpx.post(f"{BASE}/api/admin/billing/override", json={
            "org_id": org_id,
            "action": "comp",
            "until": new_end,
            "note": "Test comp grant",
        }, headers=headers)
        assert r.status_code == 200
        assert r.json().get("success") is True

    def test_suspend_then_unsuspend(self, super_admin):
        headers, _ = super_admin
        orgs_r = httpx.get(f"{BASE}/api/admin/billing/orgs", headers=headers)
        if orgs_r.status_code != 200 or len(orgs_r.json()) == 0:
            pytest.skip("No orgs available")
        org_id = orgs_r.json()[0]["id"]

        r = httpx.post(f"{BASE}/api/admin/billing/override", json={
            "org_id": org_id,
            "action": "suspend",
            "note": "Test suspend",
        }, headers=headers)
        assert r.status_code == 200
        assert r.json().get("effective_access") == "read_only"

        r2 = httpx.post(f"{BASE}/api/admin/billing/override", json={
            "org_id": org_id,
            "action": "unsuspend",
            "note": "Test unsuspend",
        }, headers=headers)
        assert r2.status_code == 200
        assert r2.json().get("effective_access") == "full_access"


class TestAccessGate:

    def test_suspend_blocks_writes(self, super_admin):
        headers, _ = super_admin
        orgs_r = httpx.get(f"{BASE}/api/admin/billing/orgs", headers=headers)
        if orgs_r.status_code != 200 or len(orgs_r.json()) == 0:
            pytest.skip("No orgs available")
        org_id = orgs_r.json()[0]["id"]

        httpx.post(f"{BASE}/api/admin/billing/override", json={
            "org_id": org_id, "action": "suspend", "note": "Gate test suspend",
        }, headers=headers)

        r = httpx.post(f"{BASE}/api/projects", json={
            "name": "Test blocked project",
        }, headers=headers)
        assert r.status_code == 402
        body = r.json()
        assert body.get("code") == "PAYWALL"

        httpx.post(f"{BASE}/api/admin/billing/override", json={
            "org_id": org_id, "action": "unsuspend", "note": "Gate test unsuspend",
        }, headers=headers)

    def test_get_allowed_when_suspended(self, super_admin):
        headers, _ = super_admin
        orgs_r = httpx.get(f"{BASE}/api/admin/billing/orgs", headers=headers)
        if orgs_r.status_code != 200 or len(orgs_r.json()) == 0:
            pytest.skip("No orgs available")
        org_id = orgs_r.json()[0]["id"]

        httpx.post(f"{BASE}/api/admin/billing/override", json={
            "org_id": org_id, "action": "suspend", "note": "GET test suspend",
        }, headers=headers)

        r = httpx.get(f"{BASE}/api/projects", headers=headers)
        assert r.status_code == 200

        httpx.post(f"{BASE}/api/admin/billing/override", json={
            "org_id": org_id, "action": "unsuspend", "note": "GET test unsuspend",
        }, headers=headers)

    def test_audit_events_logged(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/billing/audit", headers=headers)
        assert r.status_code == 200
        events = r.json()
        billing_events = [e for e in events if e.get("action", "").startswith("billing_")]
        assert len(billing_events) > 0

    def test_pm_cannot_access_admin_billing(self, pm):
        headers, _ = pm
        r = httpx.get(f"{BASE}/api/admin/billing/orgs", headers=headers)
        assert r.status_code in [403, 401]

    def test_pm_cannot_override(self, pm):
        headers, _ = pm
        r = httpx.post(f"{BASE}/api/admin/billing/override", json={
            "org_id": "fake",
            "action": "suspend",
            "note": "should fail",
        }, headers=headers)
        assert r.status_code in [403, 401]


def test_get_billable_amount_plan_override_returns_founder_price():
    """Regression test for the founder-checkout hotfix.

    Bug: /billing/org/{id}/checkout with {plan:'founder'} was returning
    the calculated amount (e.g. ₪5,700 from project units) instead of
    ₪499 because get_billable_amount read sub.plan_id from DB ('standard')
    instead of the plan being selected. Real customer was charged the
    wrong amount.

    Note: written as a sync test that calls asyncio.run() per call rather
    than using @pytest.mark.asyncio, because pytest-asyncio is not in
    requirements.txt. Same pattern as the existing async tests in
    test_billing_v1.py — wire up Motor + set_billing_db inside the async
    block, then await the unit under test.
    """
    import asyncio
    import sys
    sys.path.insert(0, "/home/runner/workspace/backend")
    from motor.motor_asyncio import AsyncIOMotorClient
    from contractor_ops.billing import get_billable_amount, set_billing_db

    sync_db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    test_org_id = "regression-test-billing-plan-override"
    test_pb_id = f"pb-{test_org_id}"

    # Setup: org on 'standard' plan with active project_billing producing ≠499
    sync_db.subscriptions.update_one(
        {"org_id": test_org_id},
        {"$set": {
            "org_id": test_org_id,
            "plan_id": "standard",
            "status": "active",
        }},
        upsert=True,
    )
    sync_db.project_billing.update_one(
        {"id": test_pb_id},
        {"$set": {
            "id": test_pb_id,
            "org_id": test_org_id,
            "project_id": f"proj-{test_org_id}",
            "status": "active",
            "plan_id": "standard",
            "contracted_units": 50,
            "monthly_total": 1500,
        }},
        upsert=True,
    )

    async def run():
        client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
        mdb = client["contractor_ops"]
        set_billing_db(mdb)

        # Without override: should return calculated amount (NOT 499)
        baseline = await get_billable_amount(test_org_id, 'monthly')
        assert baseline['amount'] != 499, \
            f"Test setup wrong: baseline should NOT be 499, got {baseline['amount']}"

        # With override='founder_6m': MUST return 499 (the bug)
        with_override = await get_billable_amount(
            test_org_id, 'monthly', plan_override='founder_6m'
        )
        assert with_override['amount'] == 499, \
            f"plan_override='founder_6m' must return 499, got {with_override['amount']}"
        assert with_override['source'] == 'founder_plan'

        # Sanity: 'standard' override = calculated (not 499)
        with_std_override = await get_billable_amount(
            test_org_id, 'monthly', plan_override='standard'
        )
        assert with_std_override['amount'] != 499

    try:
        asyncio.run(run())
    finally:
        sync_db.subscriptions.delete_one({"org_id": test_org_id})
        sync_db.project_billing.delete_one({"id": test_pb_id})


def test_billing_checkout_rejects_founder_yearly(monkeypatch):
    """Regression test for the founder+yearly undercharge guard.

    Bug: POST /billing/org/{id}/checkout with {"plan":"founder","cycle":"yearly"}
    would charge ₪499 (founder is fixed-price) but the webhook would set
    paid_until based on cycle=yearly (+1 year), giving the user a year
    of access for the 6-month price. Architect review flagged this as
    SEVERE during the founder-checkout hotfix code review.

    The guard rejects any non-monthly cycle on the founder plan with HTTP 400.

    Pattern: same asyncio.run() approach as the prior regression test.
    Constructs a minimal stub Request and a super_admin user dict to
    bypass the billing_role check, monkeypatches PayPlus config to get
    past the 501 gate, and seeds a clean org so the founder branch is
    reachable.
    """
    import asyncio
    import sys
    sys.path.insert(0, "/home/runner/workspace/backend")
    from motor.motor_asyncio import AsyncIOMotorClient
    from fastapi import HTTPException
    from contractor_ops import billing_router as br
    from contractor_ops.billing import set_billing_db
    from contractor_ops.router import set_db as set_router_db
    from contractor_ops import billing as billing_module
    import config as cfg

    monkeypatch.setattr(cfg, "PAYPLUS_API_KEY", "test_key", raising=False)
    monkeypatch.setattr(cfg, "PAYPLUS_SECRET_KEY", "test_secret", raising=False)
    monkeypatch.setattr(cfg, "PAYPLUS_PAYMENT_PAGE_UID", "test_page_uid", raising=False)
    monkeypatch.setattr(billing_module, "BILLING_V1_ENABLED", True, raising=False)

    sync_db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    test_org_id = "regression-test-founder-yearly-guard"
    sync_db.subscriptions.delete_many({"org_id": test_org_id})
    sync_db.project_billing.delete_many({"org_id": test_org_id})
    sync_db.organizations.update_one(
        {"id": test_org_id},
        {"$set": {"id": test_org_id, "name": "Test Org", "billing": {}, "tax_id": ""}},
        upsert=True,
    )
    sync_db.feature_flags.update_one(
        {"key": "founder_plan_enabled"},
        {"$set": {"key": "founder_plan_enabled", "value": True}},
        upsert=True,
    )

    class StubRequest:
        def __init__(self, body_dict):
            self._body = body_dict

        async def json(self):
            return self._body

    super_admin_user = {
        "id": "test-super-admin-id",
        "email": "test-super-admin@local",
        "platform_role": "super_admin",
        "role": "super_admin",
    }

    async def run():
        client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
        mdb = client["contractor_ops"]
        set_billing_db(mdb)
        set_router_db(mdb)

        # Case A: plan='founder', cycle='yearly' MUST raise 400 with the Hebrew detail
        req_yearly = StubRequest({"plan": "founder", "cycle": "yearly"})
        try:
            await br.billing_checkout(test_org_id, req_yearly, user=super_admin_user)
        except HTTPException as e:
            assert e.status_code == 400, f"Expected 400 got {e.status_code} ({e.detail!r})"
            assert e.detail == 'תוכנית מייסדים זמינה רק במחזור חודשי', \
                f"Expected Hebrew founder-monthly-only message, got {e.detail!r}"
        else:
            raise AssertionError(
                "Founder + yearly MUST raise HTTPException(400) — guard is missing"
            )

        # Case B: plan='standard', cycle='yearly' MUST NOT be blocked by this guard
        # (it may fail later for other reasons — PayPlus stub, missing project_billing, etc.
        # what matters is it does NOT raise 400 with the founder-monthly-only message).
        req_std_yearly = StubRequest({"plan": "standard", "cycle": "yearly"})
        try:
            await br.billing_checkout(test_org_id, req_std_yearly, user=super_admin_user)
        except HTTPException as e:
            assert not (e.status_code == 400 and e.detail == 'תוכנית מייסדים זמינה רק במחזור חודשי'), \
                "Standard plan must not trigger the founder-monthly-only guard"
        except Exception:
            pass  # Any other downstream failure (PayPlus stub etc.) is fine for this test

    try:
        asyncio.run(run())
    finally:
        sync_db.subscriptions.delete_many({"org_id": test_org_id})
        sync_db.project_billing.delete_many({"org_id": test_org_id})
        sync_db.organizations.delete_one({"id": test_org_id})
