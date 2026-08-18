"""Billing v1 tests: plans, project_billing, RBAC, migration, feature flag.

Test categories:
- TestFeatureFlag: runs when flag OFF (default). Verifies all new endpoints return 404/403.
- TestBilling*RBAC, TestPlans*, TestOrgBilling*, TestProjectBilling*, TestMigration*:
  runs when flag ON. Set BILLING_V1_ENABLED=true for both server and test runner.
- TestTierResolution, TestObservedUnits, TestAuditEvents, TestNullablePlanId:
  direct function tests; need BILLING_V1_ENABLED=true for the test process
  but don't need the server flag (they use motor directly).
"""
import pytest
import httpx
import os
from pymongo import MongoClient

BASE = "http://localhost:8000"
BILLING_V1 = os.environ.get("BILLING_V1_ENABLED", "false").lower() == "true"


def _login(email, password):
    r = httpx.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        pytest.skip(f"Cannot login as {email}")
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json().get("user", {})


def _set_platform_role(email, platform_role):
    db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
    db.users.update_one({"email": email}, {"$set": {"platform_role": platform_role}})


@pytest.fixture(scope="module")
def db():
    return MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]


@pytest.fixture(scope="module")
def super_admin():
    _set_platform_role("admin@contractor-ops.com", "super_admin")
    headers, user = _login("admin@contractor-ops.com", "admin123")
    yield headers, user


@pytest.fixture(scope="module")
def pm():
    headers, user = _login("pm@contractor-ops.com", "pm123")
    yield headers, user


@pytest.fixture(scope="module")
def contractor():
    r = httpx.post(f"{BASE}/api/auth/login", json={"email": "contractor@contractor-ops.com", "password": "contractor123"})
    if r.status_code != 200:
        pytest.skip("No contractor demo user")
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json().get("user", {})


@pytest.fixture(scope="module")
def viewer():
    r = httpx.post(f"{BASE}/api/auth/login", json={"email": "viewer@contractor-ops.com", "password": "viewer123"})
    if r.status_code != 200:
        pytest.skip("No viewer demo user")
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json().get("user", {})


@pytest.fixture(scope="module")
def project_id(pm):
    headers, _ = pm
    r = httpx.get(f"{BASE}/api/projects", headers=headers)
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) > 0, "No projects found"
    return projects[0]["id"]


@pytest.fixture(scope="module")
def org_id(db, project_id):
    proj = db.projects.find_one({"id": project_id})
    assert proj and proj.get("org_id"), "Project has no org_id"
    return proj["org_id"]


class TestFeatureFlag:
    @pytest.mark.skipif(BILLING_V1, reason="Only when flag OFF")
    def test_billing_org_404_when_flag_off(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/billing/org/fake-org", headers=headers)
        assert r.status_code == 404

    @pytest.mark.skipif(BILLING_V1, reason="Only when flag OFF")
    def test_billing_project_404_when_flag_off(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/billing/project/fake-proj", headers=headers)
        assert r.status_code == 404

    @pytest.mark.skipif(BILLING_V1, reason="Only when flag OFF")
    def test_plans_404_when_flag_off(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/billing/plans", headers=headers)
        assert r.status_code == 404

    @pytest.mark.skipif(BILLING_V1, reason="Only when flag OFF")
    def test_migration_dry_run_404_when_flag_off(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/billing/migration/dry-run", headers=headers)
        assert r.status_code == 404

    @pytest.mark.skipif(BILLING_V1, reason="Only when flag OFF")
    def test_migration_apply_blocked_when_flag_off(self, super_admin):
        headers, _ = super_admin
        r = httpx.post(f"{BASE}/api/admin/billing/migration/apply", headers=headers)
        assert r.status_code in (403, 404)


class TestBillingOrgRBAC:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_sa_can_read_org_billing(self, super_admin, org_id):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/billing/org/{org_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "org_name" in data
        assert "subscription" in data
        assert "projects" in data

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_pm_org_billing_access_depends_on_org_role(self, pm, org_id, db):
        headers, user = pm
        org = db.organizations.find_one({"id": org_id})
        is_owner = org and org.get("owner_user_id") == user.get("id")
        r = httpx.get(f"{BASE}/api/billing/org/{org_id}", headers=headers)
        if is_owner:
            assert r.status_code == 200
        else:
            assert r.status_code == 403


class TestBillingProjectRBAC:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_sa_can_read_project_billing(self, super_admin, project_id):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/billing/project/{project_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "org_name" in data
        assert "effective_access" in data

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_pm_can_read_project_billing(self, pm, project_id):
        headers, _ = pm
        r = httpx.get(f"{BASE}/api/billing/project/{project_id}", headers=headers)
        assert r.status_code == 200


class TestPlansRBAC:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_sa_can_list_plans(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/billing/plans", headers=headers)
        assert r.status_code == 200
        plans = r.json()
        assert isinstance(plans, list)

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_pm_cannot_list_plans(self, pm):
        headers, _ = pm
        r = httpx.get(f"{BASE}/api/admin/billing/plans", headers=headers)
        assert r.status_code == 403


class TestMigrationRBAC:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_sa_can_dry_run(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/billing/migration/dry-run", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "total_projects" in data
        assert "projects_with_org_id" in data
        assert "projects_missing_org_id" in data
        assert "auto_resolvable_count" in data
        assert "ambiguous_count" in data

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_pm_cannot_dry_run(self, pm):
        headers, _ = pm
        r = httpx.get(f"{BASE}/api/admin/billing/migration/dry-run", headers=headers)
        assert r.status_code == 403


class TestPlanStructure:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_default_plans_exist(self, super_admin, db):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/billing/plans", headers=headers)
        assert r.status_code == 200
        plans = r.json()
        plan_ids = [p["id"] for p in plans]
        assert "standard" in plan_ids

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_plan_has_required_fields(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/billing/plans", headers=headers)
        plans = r.json()
        for plan in plans:
            assert "id" in plan
            assert "name" in plan
            assert "license_first" in plan
            assert "license_additional" in plan
            assert "price_per_unit" in plan
            assert "is_active" in plan


class TestProjectBillingData:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_project_billing_has_observed_units(self, super_admin, project_id):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/billing/project/{project_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        if data.get("billing"):
            assert "observed_units" in data["billing"]
            assert "contracted_units" in data["billing"]
            assert isinstance(data["billing"]["observed_units"], int)

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_project_billing_has_access(self, super_admin, project_id):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/billing/project/{project_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["effective_access"] in ("full_access", "read_only")


class TestOrgBillingData:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_org_billing_has_subscription(self, super_admin, org_id):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/billing/org/{org_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "subscription" in data
        sub = data["subscription"]
        assert "status" in sub
        assert "effective_access" in sub

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_org_billing_has_projects_list(self, super_admin, org_id):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/billing/org/{org_id}", headers=headers)
        data = r.json()
        assert isinstance(data.get("projects"), list)


class TestMigrationIdempotency:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_dry_run_counts_consistent(self, super_admin):
        headers, _ = super_admin
        r1 = httpx.get(f"{BASE}/api/admin/billing/migration/dry-run", headers=headers)
        r2 = httpx.get(f"{BASE}/api/admin/billing/migration/dry-run", headers=headers)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["total_projects"] == r2.json()["total_projects"]
        assert r1.json()["projects_with_org_id"] == r2.json()["projects_with_org_id"]


class TestTierResolution:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_calculate_monthly_pricing(self, db):
        import sys
        sys.path.insert(0, "/home/runner/workspace/backend")
        from contractor_ops.billing_plans import calculate_monthly, PROJECT_LICENSE_FIRST, PROJECT_LICENSE_ADDITIONAL, PRICE_PER_UNIT

        assert calculate_monthly(10) == PROJECT_LICENSE_FIRST + 10 * PRICE_PER_UNIT
        assert calculate_monthly(50) == PROJECT_LICENSE_FIRST + 50 * PRICE_PER_UNIT
        assert calculate_monthly(200) == PROJECT_LICENSE_FIRST + 200 * PRICE_PER_UNIT
        assert calculate_monthly(0) == PROJECT_LICENSE_FIRST
        assert calculate_monthly(100, project_index=2) == PROJECT_LICENSE_ADDITIONAL + 100 * PRICE_PER_UNIT
        assert calculate_monthly(100, plan_id="founder_6m") == 499
        assert calculate_monthly(100, manual_override={"total_monthly": 3000}) == 3000


class TestObservedUnits:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_observed_units_counts_correctly(self, db, project_id):
        import asyncio
        import sys
        sys.path.insert(0, "/home/runner/workspace/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from contractor_ops.billing import set_billing_db, compute_observed_units

        async def run():
            client = AsyncIOMotorClient("mongodb://localhost:27017")
            mdb = client["contractor_ops"]
            set_billing_db(mdb)
            count = await compute_observed_units(project_id)
            assert isinstance(count, int)
            assert count >= 0

            manual_count = 0
            async for bld in mdb.buildings.find({"project_id": project_id, "$or": [{"archived": {"$ne": True}}, {"archived": {"$exists": False}}]}):
                async for unit in mdb.units.find({"building_id": bld["id"], "$or": [{"archived": {"$ne": True}}, {"archived": {"$exists": False}}]}):
                    manual_count += 1
            assert count == manual_count, f"compute_observed_units={count} but manual count={manual_count}"

        asyncio.run(run())


class TestAuditEvents:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_project_billing_creates_audit_event(self, db, project_id, org_id):
        import asyncio
        import sys
        sys.path.insert(0, "/home/runner/workspace/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from contractor_ops.billing import set_billing_db, create_project_billing
        from contractor_ops.billing_plans import set_plans_db

        async def run():
            client = AsyncIOMotorClient("mongodb://localhost:27017")
            mdb = client["contractor_ops"]
            set_billing_db(mdb)
            set_plans_db(mdb)

            await mdb.project_billing.delete_many({"project_id": "test-audit-proj"})

            try:
                pb = await create_project_billing("test-audit-proj", org_id, "test-actor")
                event = await mdb.audit_events.find_one({"action": "project_billing_created", "payload.project_id": "test-audit-proj"})
                assert event is not None, "Audit event not found"
                assert event["actor_id"] == "test-actor"
            finally:
                await mdb.project_billing.delete_many({"project_id": "test-audit-proj"})

        asyncio.run(run())


class TestNullablePlanId:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_project_billing_without_plan(self, db, org_id):
        import asyncio
        import sys
        sys.path.insert(0, "/home/runner/workspace/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from contractor_ops.billing import set_billing_db, create_project_billing
        from contractor_ops.billing_plans import set_plans_db

        async def run():
            client = AsyncIOMotorClient("mongodb://localhost:27017")
            mdb = client["contractor_ops"]
            set_billing_db(mdb)
            set_plans_db(mdb)

            test_pid = "test-null-plan-proj"
            await mdb.project_billing.delete_many({"project_id": test_pid})

            try:
                pb = await create_project_billing(test_pid, org_id, "test-actor")
                assert pb["plan_id"] is None
                assert pb["monthly_total"] == 0
                assert pb["contracted_units"] == 0
            finally:
                await mdb.project_billing.delete_many({"project_id": test_pid})

        asyncio.run(run())


class TestPricingModel:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_standard_plan_exists(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/billing/plans", headers=headers)
        assert r.status_code == 200
        plans = r.json()
        plan_ids = [p["id"] for p in plans]
        assert "standard" in plan_ids

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_plan_has_pricing_fields(self, super_admin):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/admin/billing/plans", headers=headers)
        plans = r.json()
        for plan in plans:
            if plan["is_active"]:
                assert "license_first" in plan
                assert "license_additional" in plan
                assert "price_per_unit" in plan

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_pricing_formula_consistency(self):
        import sys
        sys.path.insert(0, "/home/runner/workspace/backend")
        from contractor_ops.billing_plans import calculate_monthly, get_pricing_breakdown

        for units in [0, 10, 50, 100, 500]:
            cm = calculate_monthly(units)
            bd = get_pricing_breakdown(units)
            assert cm == bd["total_monthly"], f"Mismatch at {units} units: {cm} != {bd['total_monthly']}"


class TestWriteEndpointsRBAC:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_sa_can_patch_project_billing(self, super_admin, project_id):
        headers, _ = super_admin
        r = httpx.patch(f"{BASE}/api/billing/project/{project_id}", headers=headers,
                        json={"contracted_units": 100})
        assert r.status_code == 200
        data = r.json()
        assert data["contracted_units"] == 100

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_contractor_cannot_patch_project_billing(self, contractor, project_id):
        headers, _ = contractor
        r = httpx.patch(f"{BASE}/api/billing/project/{project_id}", headers=headers,
                        json={"contracted_units": 999})
        assert r.status_code == 403

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_patch_invalid_plan_returns_400(self, super_admin, project_id):
        headers, _ = super_admin
        r = httpx.patch(f"{BASE}/api/billing/project/{project_id}", headers=headers,
                        json={"plan_id": "nonexistent_plan"})
        assert r.status_code == 400

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_patch_plan_updates_pricing(self, super_admin, project_id):
        headers, _ = super_admin
        r = httpx.patch(f"{BASE}/api/billing/project/{project_id}", headers=headers,
                        json={"plan_id": "standard", "contracted_units": 60})
        assert r.status_code == 200
        data = r.json()
        assert data["plan_id"] == "standard"
        assert data["monthly_total"] > 0

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_patch_empty_body_returns_400(self, super_admin, project_id):
        headers, _ = super_admin
        r = httpx.patch(f"{BASE}/api/billing/project/{project_id}", headers=headers,
                        json={"random_field": 123})
        assert r.status_code == 400

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_patch_no_org_project_returns_400(self, super_admin, db):
        test_pid = "test-no-org-proj-rbac"
        db.projects.update_one(
            {"id": test_pid},
            {"$set": {"id": test_pid, "name": "Test No Org", "org_id": None}},
            upsert=True
        )
        try:
            headers, _ = super_admin
            r = httpx.patch(f"{BASE}/api/billing/project/{test_pid}", headers=headers,
                            json={"contracted_units": 10})
            assert r.status_code == 400
        finally:
            db.projects.delete_one({"id": test_pid})


class TestHandoffWorkflow:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_handoff_full_flow(self, super_admin, project_id, db):
        headers, _ = super_admin
        db.project_billing.update_one(
            {"project_id": project_id},
            {"$set": {"setup_state": "trial"}}
        )

        r = httpx.post(f"{BASE}/api/billing/project/{project_id}/handoff-request", headers=headers,
                       json={"note": "test handoff"})
        assert r.status_code == 200
        assert r.json()["setup_state"] == "pending_handoff"

        r = httpx.post(f"{BASE}/api/billing/project/{project_id}/handoff-ack", headers=headers)
        assert r.status_code == 200
        assert r.json()["setup_state"] == "pending_billing_setup"

        r = httpx.post(f"{BASE}/api/billing/project/{project_id}/setup-complete", headers=headers)
        assert r.status_code == 200
        assert r.json()["setup_state"] == "ready"

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_contractor_cannot_handoff(self, contractor, project_id):
        headers, _ = contractor
        r = httpx.post(f"{BASE}/api/billing/project/{project_id}/handoff-request", headers=headers)
        assert r.status_code == 403

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_invalid_transition_returns_400(self, super_admin, project_id, db):
        headers, _ = super_admin
        db.project_billing.update_one(
            {"project_id": project_id},
            {"$set": {"setup_state": "trial"}}
        )
        r = httpx.post(f"{BASE}/api/billing/project/{project_id}/setup-complete", headers=headers)
        assert r.status_code == 400


class TestSetupStateField:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_project_billing_has_setup_state(self, super_admin, project_id):
        headers, _ = super_admin
        r = httpx.get(f"{BASE}/api/billing/project/{project_id}", headers=headers)
        assert r.status_code == 200
        billing = r.json().get("billing")
        if billing:
            assert "setup_state" in billing
            assert billing["setup_state"] in ("trial", "pending_handoff", "pending_billing_setup", "ready", "active")

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_setup_state_transition_validation(self):
        import sys
        sys.path.insert(0, "/home/runner/workspace/backend")
        from contractor_ops.billing import validate_setup_transition

        assert validate_setup_transition("trial", "pending_handoff") is True
        assert validate_setup_transition("trial", "active") is False
        assert validate_setup_transition("pending_handoff", "pending_billing_setup") is True
        assert validate_setup_transition("pending_handoff", "trial") is True
        assert validate_setup_transition("pending_billing_setup", "ready") is True
        assert validate_setup_transition("ready", "active") is True
        assert validate_setup_transition("active", "trial") is False


class TestSnapshotImmutability:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_monthly_total_consistent_after_read(self, super_admin, project_id, db):
        headers, _ = super_admin
        r = httpx.patch(f"{BASE}/api/billing/project/{project_id}", headers=headers,
                        json={"plan_id": "standard", "contracted_units": 30})
        assert r.status_code == 200
        total_before = r.json()["monthly_total"]

        r2 = httpx.get(f"{BASE}/api/billing/project/{project_id}", headers=headers)
        assert r2.status_code == 200
        billing = r2.json()["billing"]
        assert billing["monthly_total"] == total_before


class TestBillingAuditPhase2:
    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_patch_creates_audit_event(self, super_admin, project_id, db):
        headers, _ = super_admin
        r = httpx.patch(f"{BASE}/api/billing/project/{project_id}", headers=headers,
                        json={"contracted_units": 42})
        assert r.status_code == 200
        event = db.audit_events.find_one(
            {"action": {"$in": ["project_billing_updated", "contracted_units_changed"]},
             "payload.project_id": project_id},
            sort=[("created_at", -1)]
        )
        assert event is not None
        assert "before" in event["payload"]
        assert "after" in event["payload"]

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_handoff_creates_audit_event(self, super_admin, project_id, db):
        headers, _ = super_admin
        db.project_billing.update_one(
            {"project_id": project_id},
            {"$set": {"setup_state": "trial"}}
        )
        r = httpx.post(f"{BASE}/api/billing/project/{project_id}/handoff-request", headers=headers,
                       json={"note": "audit test"})
        assert r.status_code == 200
        event = db.audit_events.find_one(
            {"action": "billing_handoff_requested", "payload.project_id": project_id},
            sort=[("created_at", -1)]
        )
        assert event is not None


class TestDeclaredUnitsFallback:
    """BATCH #581: calculated tier — declared-units fallback when a
    project_billing record exists but contracted_units was never set (==0).
    contracted>0 must stay the sole money input (2026-07-14 fix)."""

    def _run_case(self, contracted, declared, expected_amount, expected_source):
        import asyncio
        import sys
        import uuid
        from datetime import datetime, timezone
        sys.path.insert(0, "/home/runner/workspace/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from contractor_ops.billing import set_billing_db, compute_org_billing_amount

        async def run():
            client = AsyncIOMotorClient("mongodb://localhost:27017")
            mdb = client["contractor_ops"]
            set_billing_db(mdb)
            ts = datetime.now(timezone.utc).isoformat()
            org_id = str(uuid.uuid4())
            project_id = str(uuid.uuid4())
            sub_id = str(uuid.uuid4())
            pb_id = str(uuid.uuid4())
            try:
                await mdb.subscriptions.insert_one({
                    "id": sub_id, "org_id": org_id, "plan_id": "standard",
                    "status": "active", "created_at": ts,
                })
                await mdb.projects.insert_one({
                    "id": project_id, "org_id": org_id, "name": "Test P",
                    "status": "active", "total_units": declared,
                    "created_at": ts, "updated_at": ts,
                })
                await mdb.project_billing.insert_one({
                    "id": pb_id, "org_id": org_id, "project_id": project_id,
                    "status": "active", "plan_id": None,
                    "contracted_units": contracted, "created_at": ts,
                })
                result = await compute_org_billing_amount(org_id)
                assert result["amount_ils"] == expected_amount, \
                    f"contracted={contracted} declared={declared}: amount {result['amount_ils']} != {expected_amount}"
                assert len(result["breakdown"]) == 1
                assert result["breakdown"][0]["billable_source"] == expected_source
            finally:
                await mdb.subscriptions.delete_one({"id": sub_id})
                await mdb.projects.delete_one({"id": project_id})
                await mdb.project_billing.delete_one({"id": pb_id})

        asyncio.run(run())

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_a_never_priced_falls_back_to_declared(self):
        # The bug: contracted=0, declared=140 → 450 + 140*15 = 2550
        self._run_case(0, 140, 2550, "declared_fallback")

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_b_contracted_wins_over_declared(self):
        # 2026-07-14 behavior must NOT regress: 450 + 100*15 = 1950
        self._run_case(100, 140, 1950, "contracted")

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_c_no_units_at_all_license_fee_only(self):
        # billable_units=0; the record still carries the ₪450 license fee —
        # byte-identical to today's behavior for such a record.
        self._run_case(0, None, 450, "none")

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_d_ordinary_contracted_org(self):
        # 450 + 50*15 = 1200
        self._run_case(50, None, 1200, "contracted")


class TestSelfServeNoRecords:
    """BATCH #581 E3: org with ZERO active project_billing records prices its
    declared projects at read time; hard-gated to zero-record orgs only."""

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_e_zero_records_prices_declared_project(self):
        import asyncio
        import sys
        import uuid
        from datetime import datetime, timezone
        sys.path.insert(0, "/home/runner/workspace/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from contractor_ops.billing import set_billing_db, compute_org_billing_amount

        async def run():
            client = AsyncIOMotorClient("mongodb://localhost:27017")
            mdb = client["contractor_ops"]
            set_billing_db(mdb)
            ts = datetime.now(timezone.utc).isoformat()
            org_id = str(uuid.uuid4())
            project_id = str(uuid.uuid4())
            sub_id = str(uuid.uuid4())
            try:
                await mdb.subscriptions.insert_one({
                    "id": sub_id, "org_id": org_id, "plan_id": "standard",
                    "status": "active", "created_at": ts,
                })
                await mdb.projects.insert_one({
                    "id": project_id, "org_id": org_id, "name": "Idan P",
                    "status": "active", "total_units": 140,
                    "created_at": ts, "updated_at": ts,
                })
                result = await compute_org_billing_amount(org_id)
                assert result["amount_ils"] == 2550, f"amount {result['amount_ils']} != 2550"
                assert len(result["breakdown"]) == 1
                assert result["breakdown"][0]["billable_source"] == "declared_no_record"
                assert result["breakdown"][0]["billable_units"] == 140
            finally:
                await mdb.subscriptions.delete_one({"id": sub_id})
                await mdb.projects.delete_one({"id": project_id})

        asyncio.run(run())

    @pytest.mark.skipif(not BILLING_V1, reason="Requires BILLING_V1_ENABLED")
    def test_f_gate_org_with_a_record_never_bills_recordless_projects(self):
        import asyncio
        import sys
        import uuid
        from datetime import datetime, timezone
        sys.path.insert(0, "/home/runner/workspace/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from contractor_ops.billing import set_billing_db, compute_org_billing_amount

        async def run():
            client = AsyncIOMotorClient("mongodb://localhost:27017")
            mdb = client["contractor_ops"]
            set_billing_db(mdb)
            ts = datetime.now(timezone.utc).isoformat()
            org_id = str(uuid.uuid4())
            p1_id = str(uuid.uuid4())
            p2_id = str(uuid.uuid4())
            sub_id = str(uuid.uuid4())
            pb2_id = str(uuid.uuid4())
            try:
                await mdb.subscriptions.insert_one({
                    "id": sub_id, "org_id": org_id, "plan_id": "standard",
                    "status": "active", "created_at": ts,
                })
                # P1: declared units but NO billing record — must NOT be billed.
                await mdb.projects.insert_one({
                    "id": p1_id, "org_id": org_id, "name": "P1 recordless",
                    "status": "active", "total_units": 140,
                    "created_at": ts, "updated_at": ts,
                })
                # P2: has an active record with contracted=50.
                await mdb.projects.insert_one({
                    "id": p2_id, "org_id": org_id, "name": "P2 contracted",
                    "status": "active", "total_units": None,
                    "created_at": ts, "updated_at": ts,
                })
                await mdb.project_billing.insert_one({
                    "id": pb2_id, "org_id": org_id, "project_id": p2_id,
                    "status": "active", "plan_id": None,
                    "contracted_units": 50, "created_at": ts,
                })
                result = await compute_org_billing_amount(org_id)
                # 450 + 50*15 = 1200; P1 NOT billed — proves the zero-records gate.
                assert result["amount_ils"] == 1200, f"amount {result['amount_ils']} != 1200"
                assert len(result["breakdown"]) == 1
                assert result["breakdown"][0]["project_id"] == p2_id
                assert result["breakdown"][0]["billable_source"] == "contracted"
            finally:
                await mdb.subscriptions.delete_one({"id": sub_id})
                await mdb.projects.delete_many({"id": {"$in": [p1_id, p2_id]}})
                await mdb.project_billing.delete_one({"id": pb2_id})

        asyncio.run(run())
