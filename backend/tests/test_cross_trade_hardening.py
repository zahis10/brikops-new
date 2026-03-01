"""Cross-trade hardening tests: contractors cannot see/act on tasks outside their trade."""
import pytest
import httpx
from pymongo import MongoClient

BASE = "http://localhost:8000"
db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]
PID = "c3e18b07-a7d8-411e-80f9-95028b15788a"


def _login(email, password):
    r = httpx.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        pytest.skip(f"Cannot login as {email}")
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json().get("user", {})


@pytest.fixture(scope="module")
def admin():
    headers, user = _login("admin@contractor-ops.com", "admin123")
    return headers, user


@pytest.fixture(scope="module")
def pm():
    headers, user = _login("pm@contractor-ops.com", "pm123")
    return headers


@pytest.fixture(scope="module")
def electrician():
    headers, user = _login("contractor1@contractor-ops.com", "cont123")
    return headers, user["id"]


@pytest.fixture(scope="module")
def plumber():
    headers, user = _login("contractor2@contractor-ops.com", "cont123")
    return headers, user["id"]


class TestContractorListHidesMismatch:
    def test_electrician_sees_only_electrical_tasks(self, electrician):
        headers, cont_id = electrician
        task = db.tasks.find_one({"project_id": PID, "assignee_id": cont_id})
        if not task:
            pytest.skip("No task assigned to electrician")
        db.tasks.update_one({"id": task["id"]}, {"$set": {"category": "plumbing"}})
        try:
            r = httpx.get(
                f"{BASE}/api/tasks",
                params={"project_id": PID, "assignee_id": "me"},
                headers=headers,
            )
            assert r.status_code == 200
            task_ids = [t["id"] for t in r.json()]
            assert task["id"] not in task_ids, "Mismatched-category task should be hidden from contractor list"
        finally:
            db.tasks.update_one({"id": task["id"]}, {"$set": {"category": "electrical"}})


class TestContractorDetailMismatch:
    def test_detail_returns_404_on_mismatched_category(self, electrician):
        headers, cont_id = electrician
        task = db.tasks.find_one({"project_id": PID, "assignee_id": cont_id})
        if not task:
            pytest.skip("No task assigned to electrician")
        original_cat = task.get("category", "electrical")
        db.tasks.update_one({"id": task["id"]}, {"$set": {"category": "plumbing"}})
        try:
            r = httpx.get(f"{BASE}/api/tasks/{task['id']}", headers=headers)
            assert r.status_code == 404, f"Expected 404 for cross-trade task detail, got {r.status_code}"
        finally:
            db.tasks.update_one({"id": task["id"]}, {"$set": {"category": original_cat}})


class TestContractorProofMismatch:
    def test_proof_upload_returns_404_on_mismatched_category(self, electrician):
        headers, cont_id = electrician
        task = db.tasks.find_one({"project_id": PID, "assignee_id": cont_id})
        if not task:
            pytest.skip("No task assigned to electrician")
        original = {"category": task.get("category"), "status": task.get("status")}
        db.tasks.update_one({"id": task["id"]}, {"$set": {"category": "plumbing", "status": "in_progress"}})
        try:
            r = httpx.post(
                f"{BASE}/api/tasks/{task['id']}/contractor-proof",
                headers=headers,
                files=[("files", ("test.jpg", b"\xff\xd8\xff\xe0 test", "image/jpeg"))],
                data={"note": "test"},
            )
            assert r.status_code == 404, f"Expected 404 for cross-trade proof upload, got {r.status_code}"
        finally:
            db.tasks.update_one({"id": task["id"]}, {"$set": original})


class TestAssignCrossTradeBlocked:
    def test_assign_returns_409_on_trade_mismatch(self, pm, plumber):
        _, plumber_id = plumber
        task = db.tasks.find_one({"project_id": PID, "category": "electrical"})
        if not task:
            pytest.skip("No electrical task found")
        plumber_user = db.users.find_one({"id": plumber_id}, {"_id": 0, "company_id": 1})
        r = httpx.patch(
            f"{BASE}/api/tasks/{task['id']}/assign",
            headers=pm,
            json={"company_id": plumber_user["company_id"], "assignee_id": plumber_id},
        )
        assert r.status_code == 409, f"Expected 409 for cross-trade assign, got {r.status_code}"
        data = r.json()
        detail = data.get("detail", {})
        assert detail.get("error") == "trade_mismatch"
        assert "task_category" in detail
        assert "contractor_trade" in detail

    def test_assign_with_force_changes_category(self, pm, plumber):
        _, plumber_id = plumber
        task = db.tasks.find_one({"project_id": PID, "category": "electrical"})
        if not task:
            pytest.skip("No electrical task found")
        original = {
            "category": task.get("category"),
            "assignee_id": task.get("assignee_id"),
            "company_id": task.get("company_id"),
            "status": task.get("status"),
        }
        plumber_user = db.users.find_one({"id": plumber_id}, {"_id": 0, "company_id": 1})
        plumber_mem = db.project_memberships.find_one(
            {"project_id": PID, "user_id": plumber_id}, {"_id": 0}
        )
        try:
            r = httpx.patch(
                f"{BASE}/api/tasks/{task['id']}/assign",
                headers=pm,
                json={
                    "company_id": plumber_user["company_id"],
                    "assignee_id": plumber_id,
                    "force_category_change": True,
                },
            )
            assert r.status_code == 200
            data = r.json()
            assert data.get("category_synced") is True
            assert data.get("synced_category") == plumber_mem.get("contractor_trade_key")
            assert data["category"] == plumber_mem.get("contractor_trade_key")
        finally:
            db.tasks.update_one({"id": task["id"]}, {"$set": original})

    def test_assign_no_block_when_trade_matches(self, pm, electrician):
        _, elec_id = electrician
        task = db.tasks.find_one({"project_id": PID, "category": "electrical"})
        if not task:
            pytest.skip("No electrical task found")
        original = {
            "assignee_id": task.get("assignee_id"),
            "company_id": task.get("company_id"),
            "status": task.get("status"),
        }
        elec_user = db.users.find_one({"id": elec_id}, {"_id": 0, "company_id": 1})
        try:
            r = httpx.patch(
                f"{BASE}/api/tasks/{task['id']}/assign",
                headers=pm,
                json={"company_id": elec_user["company_id"], "assignee_id": elec_id},
            )
            assert r.status_code == 200
            data = r.json()
            assert data.get("category_synced") is None or data.get("category_synced") is False
        finally:
            db.tasks.update_one({"id": task["id"]}, {"$set": original})


class TestDeleteProof:
    def test_admin_can_delete_proof_with_reason(self, admin):
        headers, admin_user = admin
        task = db.tasks.find_one({"project_id": PID, "assignee_id": {"$exists": True, "$ne": None}})
        if not task:
            pytest.skip("No assigned task found")
        import uuid
        proof_id = str(uuid.uuid4())
        db.task_updates.insert_one({
            "id": proof_id, "task_id": task["id"], "user_id": "test-user",
            "user_name": "test", "content": "test proof",
            "update_type": "attachment", "attachment_url": "/test/proof.jpg",
            "created_at": "2026-01-01T00:00:00Z",
        })
        try:
            r = httpx.request(
                "DELETE",
                f"{BASE}/api/tasks/{task['id']}/proof/{proof_id}",
                headers={**headers, "Content-Type": "application/json"},
                content='{"reason": "הוכחה שגויה מקבלן קודם"}',
            )
            assert r.status_code == 200
            assert r.json().get("success") is True
            deleted = db.task_updates.find_one({"id": proof_id})
            assert deleted is None, "Proof should be deleted from DB"
            audit = db.audit_events.find_one({"entity_id": task["id"], "action": "proof_deleted"})
            assert audit is not None, "Audit event should be created"
            assert audit["payload"]["reason"] == "הוכחה שגויה מקבלן קודם"
        finally:
            db.task_updates.delete_many({"id": proof_id})
            db.audit_events.delete_many({"entity_id": task["id"], "action": "proof_deleted"})

    def test_pm_cannot_delete_proof(self, pm):
        task = db.tasks.find_one({"project_id": PID})
        if not task:
            pytest.skip("No task found")
        r = httpx.request(
            "DELETE",
            f"{BASE}/api/tasks/{task['id']}/proof/fake-id",
            headers={**pm, "Content-Type": "application/json"},
            content='{"reason": "test"}',
        )
        assert r.status_code == 403, f"Expected 403 for PM deleting proof, got {r.status_code}"

    def test_delete_requires_reason(self, admin):
        headers, _ = admin
        task = db.tasks.find_one({"project_id": PID})
        if not task:
            pytest.skip("No task found")
        r = httpx.request(
            "DELETE",
            f"{BASE}/api/tasks/{task['id']}/proof/fake-id",
            headers={**headers, "Content-Type": "application/json"},
            content='{"reason": ""}',
        )
        assert r.status_code == 400, f"Expected 400 for empty reason, got {r.status_code}"
