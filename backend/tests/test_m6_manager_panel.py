"""M6 integration tests: Manager panel, RBAC, proof workflow."""
import pytest
import httpx
from pymongo import MongoClient


BASE = "http://localhost:8000"
db = MongoClient("mongodb://127.0.0.1:27017")["contractor_ops"]


def _login(email, password):
    r = httpx.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        pytest.skip(f"Cannot login as {email}")
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json().get("user", {})


def _get_contractor_task(cont_id):
    task = db.tasks.find_one({"assignee_id": cont_id}, {"_id": 0})
    if not task:
        pytest.skip("No assigned task")
    return task


@pytest.fixture(scope="module")
def pm():
    headers, user = _login("pm@contractor-ops.com", "pm123")
    return headers


@pytest.fixture(scope="module")
def contractor():
    headers, user = _login("contractor1@contractor-ops.com", "cont123")
    return headers, user["id"]


class TestManagerDecision:
    def test_reject_requires_reason(self, pm, contractor):
        _, cont_id = contractor
        task = _get_contractor_task(cont_id)
        db.tasks.update_one({"id": task["id"]}, {"$set": {"status": "pending_manager_approval"}})
        try:
            r = httpx.post(f"{BASE}/api/tasks/{task['id']}/manager-decision",
                           json={"decision": "reject"},
                           headers=pm)
            assert r.status_code == 400
            detail = r.json()["detail"].lower()
            assert "reason" in detail or "required" in detail
        finally:
            db.tasks.update_one({"id": task["id"]}, {"$set": {"status": "in_progress"}})

    def test_approve_closes_task(self, pm, contractor):
        _, cont_id = contractor
        task = _get_contractor_task(cont_id)
        db.tasks.update_one({"id": task["id"]}, {"$set": {"status": "pending_manager_approval"}})
        try:
            r = httpx.post(f"{BASE}/api/tasks/{task['id']}/manager-decision",
                           json={"decision": "approve"},
                           headers=pm)
            assert r.status_code == 200
            assert r.json()["task"]["status"] == "closed"
        finally:
            db.tasks.update_one({"id": task["id"]}, {"$set": {"status": "in_progress"}})

    def test_reject_returns_to_contractor(self, pm, contractor):
        _, cont_id = contractor
        task = _get_contractor_task(cont_id)
        db.tasks.update_one({"id": task["id"]}, {"$set": {"status": "pending_manager_approval"}})
        try:
            r = httpx.post(f"{BASE}/api/tasks/{task['id']}/manager-decision",
                           json={"decision": "reject", "reason": "תמונות לא ברורות"},
                           headers=pm)
            assert r.status_code == 200
            assert r.json()["task"]["status"] == "returned_to_contractor"
        finally:
            db.tasks.update_one({"id": task["id"]}, {"$set": {"status": "in_progress"}})


class TestContractorBlocked:
    def test_contractor_blocked_from_manager_decision(self, pm, contractor):
        cont_headers, cont_id = contractor
        task = _get_contractor_task(cont_id)
        db.tasks.update_one({"id": task["id"]}, {"$set": {"status": "pending_manager_approval"}})
        try:
            r = httpx.post(f"{BASE}/api/tasks/{task['id']}/manager-decision",
                           json={"decision": "approve"},
                           headers=cont_headers)
            assert r.status_code == 403
        finally:
            db.tasks.update_one({"id": task["id"]}, {"$set": {"status": "in_progress"}})

    def test_contractor_blocked_from_update_task(self, contractor):
        cont_headers, cont_id = contractor
        task = _get_contractor_task(cont_id)
        r = httpx.patch(f"{BASE}/api/tasks/{task['id']}",
                        json={"priority": "critical"},
                        headers=cont_headers)
        assert r.status_code == 403

    def test_contractor_blocked_from_assign_task(self, contractor):
        cont_headers, cont_id = contractor
        task = _get_contractor_task(cont_id)
        r = httpx.patch(f"{BASE}/api/tasks/{task['id']}/assign",
                        json={"company_id": "fake", "assignee_id": "fake"},
                        headers=cont_headers)
        assert r.status_code == 403


class TestManagerUpdate:
    def test_manager_update_priority(self, pm, contractor):
        _, cont_id = contractor
        task = _get_contractor_task(cont_id)
        orig = task.get("priority", "medium")
        r = httpx.patch(f"{BASE}/api/tasks/{task['id']}",
                        json={"priority": "critical"},
                        headers=pm)
        assert r.status_code == 200
        assert r.json()["priority"] == "critical"
        httpx.patch(f"{BASE}/api/tasks/{task['id']}",
                    json={"priority": orig},
                    headers=pm)

    def test_manager_update_category(self, pm, contractor):
        _, cont_id = contractor
        task = _get_contractor_task(cont_id)
        orig = task.get("category", "general")
        r = httpx.patch(f"{BASE}/api/tasks/{task['id']}",
                        json={"category": "plumbing"},
                        headers=pm)
        assert r.status_code == 200
        assert r.json()["category"] == "plumbing"
        httpx.patch(f"{BASE}/api/tasks/{task['id']}",
                    json={"category": orig},
                    headers=pm)
