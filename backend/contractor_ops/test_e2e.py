import requests
import sys
import json
import uuid

BASE = "http://localhost:8000/api"
PASSED = 0
FAILED = 0
RESULTS = []
SUFFIX = uuid.uuid4().hex[:6]

def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        RESULTS.append(f"  PASS  {name}")
        print(f"  [PASS] {name}")
    else:
        FAILED += 1
        RESULTS.append(f"  FAIL  {name} — {detail}")
        print(f"  [FAIL] {name} — {detail}")

def auth_header(token):
    return {"Authorization": f"Bearer {token}"}

print("=" * 60)
print("  Contractor Ops E2E Test Suite")
print("=" * 60)
print()

print("--- 1. Auth: Register + Login ---")
def register_and_login(email, password, name, role):
    r = requests.post(f"{BASE}/auth/register", json={
        "email": email, "password": password, "name": name, "role": role
    })
    r2 = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    return r2.json().get("token") if r2.status_code == 200 else None

admin_token = register_and_login(f"e2e_admin_{SUFFIX}@test.com", "testpass123", "E2E Admin", "admin")
check("Register+login admin", admin_token is not None, "no token")

contractor_token = register_and_login(f"e2e_contractor_{SUFFIX}@test.com", "testpass123", "E2E Contractor", "contractor")
check("Register+login contractor", contractor_token is not None, "no token")

viewer_token = register_and_login(f"e2e_viewer_{SUFFIX}@test.com", "testpass123", "E2E Viewer", "viewer")
check("Register+login viewer", viewer_token is not None, "no token")

r = requests.get(f"{BASE}/auth/me", headers=auth_header(admin_token))
check("GET /auth/me", r.status_code == 200 and r.json()["role"] == "admin", f"status={r.status_code}")

print()
print("--- 2. Project Hierarchy ---")
r = requests.post(f"{BASE}/projects", json={
    "name": "E2E Test Project", "code": f"E2E-{SUFFIX.upper()}",
    "description": "E2E test project"
}, headers=auth_header(admin_token))
check("Create project", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")
project_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/projects/{project_id}/buildings", json={
    "name": "Building Test", "code": "T1", "project_id": project_id
}, headers=auth_header(admin_token))
check("Create building", r.status_code == 200, f"status={r.status_code}")
building_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/buildings/{building_id}/floors", json={
    "name": "Floor 1", "floor_number": 1, "building_id": building_id, "project_id": project_id
}, headers=auth_header(admin_token))
check("Create floor", r.status_code == 200, f"status={r.status_code}")
floor_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/floors/{floor_id}/units", json={
    "unit_no": "101", "floor_id": floor_id, "building_id": building_id, "project_id": project_id
}, headers=auth_header(admin_token))
check("Create unit", r.status_code == 200, f"status={r.status_code}")
unit_id = r.json().get("id") if r.status_code == 200 else None

print()
print("--- 3. Task Lifecycle ---")
r = requests.post(f"{BASE}/tasks", json={
    "project_id": project_id, "building_id": building_id,
    "floor_id": floor_id, "unit_id": unit_id,
    "title": "E2E Test Task", "description": "Full lifecycle test",
    "category": "electrical", "priority": "high"
}, headers=auth_header(admin_token))
check("Create task (open)", r.status_code == 200 and r.json()["status"] == "open",
      f"status={r.status_code}")
task_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/tasks/{task_id}/status", json={"status": "assigned", "note": "Assigned to team"},
                   headers=auth_header(admin_token))
check("open -> assigned", r.status_code == 200 and r.json()["status"] == "assigned",
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/tasks/{task_id}/status", json={"status": "in_progress", "note": "Work started"},
                   headers=auth_header(admin_token))
check("assigned -> in_progress", r.status_code == 200 and r.json()["status"] == "in_progress",
      f"status={r.status_code}")

r = requests.post(f"{BASE}/tasks/{task_id}/status", json={"status": "waiting_verify"},
                   headers=auth_header(admin_token))
check("in_progress -> waiting_verify", r.status_code == 200 and r.json()["status"] == "waiting_verify",
      f"status={r.status_code}")

r = requests.post(f"{BASE}/tasks/{task_id}/status", json={"status": "closed", "note": "Verified OK"},
                   headers=auth_header(admin_token))
check("waiting_verify -> closed", r.status_code == 200 and r.json()["status"] == "closed",
      f"status={r.status_code}")

r = requests.post(f"{BASE}/tasks/{task_id}/reopen", headers=auth_header(admin_token))
check("closed -> reopened", r.status_code == 200 and r.json()["status"] == "reopened",
      f"status={r.status_code}")

r = requests.post(f"{BASE}/tasks/{task_id}/status", json={"status": "closed"},
                   headers=auth_header(admin_token))
check("reopened -> closed (final)", r.status_code == 200 and r.json()["status"] == "closed",
      f"status={r.status_code}")

print()
print("--- 4. Invalid Transitions ---")
r = requests.post(f"{BASE}/tasks/{task_id}/status", json={"status": "in_progress"},
                   headers=auth_header(admin_token))
check("closed -> in_progress BLOCKED", r.status_code == 400,
      f"status={r.status_code}")

print()
print("--- 5. Task Updates ---")
r = requests.post(f"{BASE}/tasks/{task_id}/updates", json={
    "task_id": task_id, "content": "This is a test comment"
}, headers=auth_header(admin_token))
check("Add task update/comment", r.status_code == 200, f"status={r.status_code}")

r = requests.get(f"{BASE}/tasks/{task_id}/updates", headers=auth_header(admin_token))
check("List task updates", r.status_code == 200 and len(r.json()) >= 1,
      f"status={r.status_code}, count={len(r.json()) if r.status_code == 200 else 0}")

print()
print("--- 6. RBAC: Viewer Restrictions ---")
if viewer_token:
    r = requests.post(f"{BASE}/projects", json={
        "name": "Viewer Project", "code": "VW-001"
    }, headers=auth_header(viewer_token))
    check("Viewer CANNOT create project", r.status_code == 403, f"status={r.status_code}")

    r = requests.post(f"{BASE}/tasks/{task_id}/updates", json={
        "task_id": task_id, "content": "Viewer comment"
    }, headers=auth_header(viewer_token))
    check("Viewer CANNOT add updates", r.status_code == 403, f"status={r.status_code}")

    r = requests.get(f"{BASE}/tasks", headers=auth_header(viewer_token))
    check("Viewer CAN read tasks", r.status_code == 200, f"status={r.status_code}")
else:
    print("  [SKIP] Viewer tests - no token")

print()
print("--- 7. RBAC: Contractor Restrictions ---")
if contractor_token:
    r = requests.post(f"{BASE}/projects", json={
        "name": "Contractor Project", "code": "CT-001"
    }, headers=auth_header(contractor_token))
    check("Contractor CANNOT create project", r.status_code == 403, f"status={r.status_code}")

    r = requests.get(f"{BASE}/tasks", headers=auth_header(contractor_token))
    check("Contractor CAN read tasks", r.status_code == 200, f"status={r.status_code}")
else:
    print("  [SKIP] Contractor tests - no token")

print()
print("--- 8. Defect Creation + Assignment Flow ---")

r = requests.post(f"{BASE}/companies", json={
    "name": "E2E Electric Co", "trade": "electrical",
    "specialties": ["electrical", "general"],
    "phone_e164": f"+97250{SUFFIX}99", "whatsapp_enabled": True, "whatsapp_opt_in": True,
}, headers=auth_header(admin_token))
check("Create company with specialties", r.status_code == 200, f"status={r.status_code}")
e2e_company_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/auth/register", json={
    "email": f"e2e_elec_{SUFFIX}@test.com", "password": "testpass123",
    "name": "E2E Electrician", "role": "contractor",
    "company_id": e2e_company_id, "specialties": ["electrical", "general"],
    "phone_e164": f"+97250{SUFFIX}99",
})
check("Register specialty contractor", r.status_code == 200, f"status={r.status_code}")
r2 = requests.post(f"{BASE}/auth/login", json={"email": f"e2e_elec_{SUFFIX}@test.com", "password": "testpass123"})
e2e_contractor_token = r2.json().get("token") if r2.status_code == 200 else None
e2e_contractor_id = r2.json().get("user", {}).get("id") if r2.status_code == 200 else None
check("Login specialty contractor", e2e_contractor_token is not None)

r = requests.post(f"{BASE}/tasks", json={
    "project_id": project_id, "building_id": building_id,
    "floor_id": floor_id, "unit_id": unit_id,
    "title": "ליקוי חשמל - שקע שבור", "description": "שקע חשמל שבור בסלון",
    "category": "electrical", "priority": "high"
}, headers=auth_header(admin_token))
check("Create defect with location", r.status_code == 200 and r.json()["status"] == "open",
      f"status={r.status_code}")
defect_id = r.json().get("id") if r.status_code == 200 else None
defect_data = r.json() if r.status_code == 200 else {}
check("Defect has building_id", defect_data.get("building_id") == building_id)
check("Defect has floor_id", defect_data.get("floor_id") == floor_id)
check("Defect has unit_id", defect_data.get("unit_id") == unit_id)

import tempfile, os
test_img_path = os.path.join(tempfile.gettempdir(), "e2e_test_defect.jpg")
with open(test_img_path, 'wb') as f:
    f.write(b'\xff\xd8\xff\xe0' + b'\x00' * 100)
with open(test_img_path, 'rb') as f:
    r = requests.post(f"{BASE}/tasks/{defect_id}/attachments",
                      files={"file": ("defect_photo.jpg", f, "image/jpeg")},
                      headers=auth_header(admin_token))
check("Upload defect image", r.status_code == 200 and "file_url" in r.json(),
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.patch(f"{BASE}/tasks/{defect_id}/assign", json={
    "company_id": e2e_company_id, "assignee_id": e2e_contractor_id,
}, headers=auth_header(admin_token))
check("Assign defect to contractor", r.status_code == 200 and r.json()["status"] == "assigned",
      f"status={r.status_code}, body={r.text[:200]}")
check("Assigned company_id set", r.json().get("company_id") == e2e_company_id)
check("Assigned assignee_id set", r.json().get("assignee_id") == e2e_contractor_id)

r = requests.get(f"{BASE}/tasks/{defect_id}", headers=auth_header(admin_token))
check("Get defect detail", r.status_code == 200 and r.json()["status"] == "assigned",
      f"status={r.status_code}")
check("Defect has attachments_count=1", r.json().get("attachments_count", 0) == 1)

r = requests.get(f"{BASE}/tasks?status=assigned&project_id={project_id}",
                  headers=auth_header(admin_token))
assigned_ids = [t["id"] for t in r.json()] if r.status_code == 200 else []
check("Defect appears in assigned filter", defect_id in assigned_ids,
      f"ids={assigned_ids[:5]}")

r = requests.get(f"{BASE}/users?role=contractor&company_id={e2e_company_id}",
                  headers=auth_header(admin_token))
check("Filter contractors by company", r.status_code == 200, f"status={r.status_code}")

print()
print("--- 9. Defect RBAC: Viewer Negative Tests ---")
if viewer_token:
    r = requests.post(f"{BASE}/tasks", json={
        "project_id": project_id, "building_id": building_id,
        "floor_id": floor_id, "unit_id": unit_id,
        "title": "Viewer Defect", "category": "general"
    }, headers=auth_header(viewer_token))
    check("Viewer CANNOT create defect", r.status_code == 403, f"status={r.status_code}")

    r = requests.patch(f"{BASE}/tasks/{defect_id}/assign", json={
        "company_id": e2e_company_id, "assignee_id": e2e_contractor_id,
    }, headers=auth_header(viewer_token))
    check("Viewer CANNOT assign defect", r.status_code == 403, f"status={r.status_code}")

    with open(test_img_path, 'rb') as f:
        r = requests.post(f"{BASE}/tasks/{defect_id}/attachments",
                          files={"file": ("viewer_photo.jpg", f, "image/jpeg")},
                          headers=auth_header(viewer_token))
    check("Viewer CANNOT upload attachment", r.status_code == 403, f"status={r.status_code}")
else:
    print("  [SKIP] Viewer defect tests - no token")

os.unlink(test_img_path)

print()
print("--- 10. Location Validation ---")
r = requests.post(f"{BASE}/tasks", json={
    "project_id": project_id, "building_id": "nonexistent-building",
    "floor_id": floor_id, "unit_id": unit_id,
    "title": "Bad Location Task", "category": "general"
}, headers=auth_header(admin_token))
check("Reject invalid building_id", r.status_code == 404, f"status={r.status_code}")

print()
print("--- 11. Dashboard + Feed ---")
r = requests.get(f"{BASE}/projects/{project_id}/dashboard", headers=auth_header(admin_token))
check("Project dashboard", r.status_code == 200 and "total_tasks" in r.json(),
      f"status={r.status_code}")

r = requests.get(f"{BASE}/updates/feed?project_id={project_id}", headers=auth_header(admin_token))
check("Updates feed", r.status_code == 200, f"status={r.status_code}")

print()
print("=" * 60)
print(f"  RESULTS: {PASSED} passed, {FAILED} failed")
print("=" * 60)
for res in RESULTS:
    print(res)
print()
if FAILED == 0:
    print("VERDICT: ALL TESTS PASSED")
else:
    print(f"VERDICT: {FAILED} TESTS FAILED")
    sys.exit(1)
