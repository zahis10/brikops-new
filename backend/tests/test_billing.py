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
