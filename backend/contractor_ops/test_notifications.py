import requests
import sys
import time

BASE = "http://localhost:8000/api"
PASSED = 0
FAILED = 0
RESULTS = []


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
print("  Contractor Ops — Notification Module Test Suite")
print("=" * 60)
print()

print("--- Setup: Register users + create hierarchy ---")

import uuid
suffix = uuid.uuid4().hex[:6]

r = requests.post(f"{BASE}/auth/register", json={
    "email": f"notif_admin_{suffix}@test.com", "password": "testpass123",
    "name": "Notif Admin", "role": "admin"
})
r2 = requests.post(f"{BASE}/auth/login", json={
    "email": f"notif_admin_{suffix}@test.com", "password": "testpass123"
})
admin_token = r2.json().get("token") if r2.status_code == 200 else None
admin_id = r2.json().get("user", {}).get("id") if r2.status_code == 200 else None
check("Admin login", admin_token is not None)

r = requests.post(f"{BASE}/auth/register", json={
    "email": f"notif_viewer_{suffix}@test.com", "password": "testpass123",
    "name": "Notif Viewer", "role": "viewer"
})
r2 = requests.post(f"{BASE}/auth/login", json={
    "email": f"notif_viewer_{suffix}@test.com", "password": "testpass123"
})
viewer_token = r2.json().get("token") if r2.status_code == 200 else None
check("Viewer login", viewer_token is not None)

phone_suffix = suffix[:4].ljust(4, '0')

r = requests.post(f"{BASE}/companies", json={
    "name": f"Notif Electric Co {suffix}", "trade": "electrical",
    "specialties": ["electrical"], "phone_e164": f"+97250{phone_suffix}01",
    "whatsapp_enabled": True, "whatsapp_opt_in": True,
}, headers=auth_header(admin_token))
company_id = r.json().get("id") if r.status_code == 200 else None
check("Create company", company_id is not None, f"status={r.status_code}")

other_company = requests.post(f"{BASE}/companies", json={
    "name": f"Other Plumbing Co {suffix}", "trade": "plumbing",
    "specialties": ["plumbing"], "phone_e164": f"+97250{phone_suffix}09",
}, headers=auth_header(admin_token))
other_company_id = other_company.json().get("id") if other_company.status_code == 200 else None

r = requests.post(f"{BASE}/auth/register", json={
    "email": f"notif_contractor_{suffix}@test.com", "password": "testpass123",
    "name": "Notif Contractor", "role": "contractor",
    "company_id": other_company_id,
    "phone_e164": f"+97250{phone_suffix}02",
})
r2 = requests.post(f"{BASE}/auth/login", json={
    "email": f"notif_contractor_{suffix}@test.com", "password": "testpass123"
})
contractor_token = r2.json().get("token") if r2.status_code == 200 else None
check("Contractor login", contractor_token is not None)

r = requests.post(f"{BASE}/auth/register", json={
    "email": f"notif_elec_{suffix}@test.com", "password": "testpass123",
    "name": "Notif Electrician", "role": "contractor",
    "company_id": company_id, "specialties": ["electrical"],
    "phone_e164": f"+97250{phone_suffix}03",
})
r2 = requests.post(f"{BASE}/auth/login", json={
    "email": f"notif_elec_{suffix}@test.com", "password": "testpass123"
})
elec_token = r2.json().get("token") if r2.status_code == 200 else None
elec_id = r2.json().get("user", {}).get("id") if r2.status_code == 200 else None
check("Electrician login", elec_token is not None)

r = requests.post(f"{BASE}/projects", json={
    "name": f"Notif Test Project {suffix}", "code": f"NTP-{suffix.upper()}",
}, headers=auth_header(admin_token))
project_id = r.json().get("id") if r.status_code == 200 else None
check("Create project", project_id is not None)

r = requests.post(f"{BASE}/projects/{project_id}/buildings", json={
    "name": "Building N1", "code": "N1", "project_id": project_id
}, headers=auth_header(admin_token))
building_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/buildings/{building_id}/floors", json={
    "name": "Floor 1", "floor_number": 1, "building_id": building_id, "project_id": project_id
}, headers=auth_header(admin_token))
floor_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/floors/{floor_id}/units", json={
    "unit_no": "N101", "floor_id": floor_id, "building_id": building_id, "project_id": project_id
}, headers=auth_header(admin_token))
unit_id = r.json().get("id") if r.status_code == 200 else None
check("Create hierarchy", unit_id is not None)

r = requests.post(f"{BASE}/tasks", json={
    "project_id": project_id, "building_id": building_id,
    "floor_id": floor_id, "unit_id": unit_id,
    "title": "ליקוי חשמל לבדיקת התראות", "description": "בדיקת מערכת התראות",
    "category": "electrical", "priority": "high"
}, headers=auth_header(admin_token))
task_id = r.json().get("id") if r.status_code == 200 else None
check("Create task", task_id is not None)

print()
print("--- 1. Unit Tests: Phone Validator ---")

from contractor_ops.notification_service import validate_e164, generate_idempotency_key, build_whatsapp_payload, format_text_message

check("Valid E.164: +972501234567", validate_e164("+972501234567") == True)
check("Valid E.164: +14155551234", validate_e164("+14155551234") == True)
check("Valid E.164: +8613800138000", validate_e164("+8613800138000") == True)
check("Invalid: no + prefix", validate_e164("972501234567") == False)
check("Invalid: too short", validate_e164("+123") == False)
check("Invalid: letters", validate_e164("+972abc") == False)
check("Invalid: empty", validate_e164("") == False)
check("Invalid: +0 prefix", validate_e164("+0123456789") == False)

print()
print("--- 2. Unit Tests: Idempotency Key ---")

key1 = generate_idempotency_key("task-1", "task_assigned", "user-1")
key2 = generate_idempotency_key("task-1", "task_assigned", "user-1")
check("Same inputs = same key", key1 == key2)

key3 = generate_idempotency_key("task-2", "task_assigned", "user-1")
check("Different task = different key", key1 != key3)

key4 = generate_idempotency_key("task-1", "status_closed", "user-1")
check("Different event = different key", key1 != key4)

key5 = generate_idempotency_key("task-1", "task_assigned", "user-2")
check("Different assignee = different key", key1 != key5)

check("Key length = 32", len(key1) == 32)

print()
print("--- 3. Unit Tests: Payload Builder ---")

test_task = {
    "id": "t-1", "title": "ליקוי חשמל", "description": "שקע שבור",
    "category": "electrical", "priority": "high", "status": "assigned",
    "due_date": "2026-03-01",
}
test_project = {"name": "פרויקט הבדיקה"}
test_building = {"name": "בניין א"}
test_floor = {"name": "קומה 3"}
test_unit = {"unit_no": "301"}
test_assignee = {"name": "יוסי חשמלאי"}
test_company = {"name": "חשמל בע\"מ"}

payload = build_whatsapp_payload(
    test_task, test_project, test_building, test_floor, test_unit,
    test_assignee, test_company, task_link="https://app.example.com/tasks/t-1",
    custom_message="אנא טפל בדחיפות",
)
check("Payload has title", payload.get("title") == "ליקוי חשמל")
check("Payload has project_name", payload.get("project_name") == "פרויקט הבדיקה")
check("Payload has building_name", payload.get("building_name") == "בניין א")
check("Payload has category (Hebrew)", payload.get("category") == "חשמל")
check("Payload has priority (Hebrew)", payload.get("priority") == "גבוה")
check("Payload has assignee_name", payload.get("assignee_name") == "יוסי חשמלאי")
check("Payload has task_link", payload.get("task_link") == "https://app.example.com/tasks/t-1")
check("Payload has custom_message", payload.get("custom_message") == "אנא טפל בדחיפות")

text = format_text_message(payload)
check("Text message contains title", "ליקוי חשמל" in text)
check("Text message contains project", "פרויקט הבדיקה" in text)
check("Text message contains custom msg", "אנא טפל בדחיפות" in text)

print()
print("--- 4. Integration: Manual Notify (dry-run) ---")

r = requests.patch(f"{BASE}/tasks/{task_id}/assign", json={
    "company_id": company_id, "assignee_id": elec_id,
}, headers=auth_header(admin_token))
check("Assign task for notify test", r.status_code == 200 and r.json()["status"] == "assigned",
      f"status={r.status_code}")

r = requests.post(f"{BASE}/tasks/{task_id}/notify", json={
    "message": "בדיקת שליחה ידנית"
}, headers=auth_header(admin_token))
check("Manual notify (dry-run)", r.status_code == 200 and r.json().get("success") == True,
      f"status={r.status_code}, body={r.text[:300]}")
manual_job_id = r.json().get("job_id") if r.status_code == 200 else None
manual_status = r.json().get("status") if r.status_code == 200 else None
check("Dry-run status = skipped_dry_run", manual_status == "skipped_dry_run",
      f"status={manual_status}")

print()
print("--- 5. Integration: Notification Timeline ---")

r = requests.get(f"{BASE}/tasks/{task_id}/notifications", headers=auth_header(admin_token))
check("GET notifications timeline", r.status_code == 200, f"status={r.status_code}")
timeline = r.json() if r.status_code == 200 else []
check("Timeline has entries", len(timeline) >= 1, f"count={len(timeline)}")

if timeline:
    first = timeline[0]
    check("Timeline entry has task_id", first.get("task_id") == task_id)
    check("Timeline entry has event_type", first.get("event_type") in
          ["manual_send", "task_assigned"])
    check("Timeline entry has target_phone", len(first.get("target_phone", "")) > 0)
    check("Timeline entry has status", first.get("status") in
          ["queued", "skipped_dry_run", "sent", "delivered", "read", "failed"])

print()
print("--- 6. Integration: Auto-enqueue on assign ---")

auto_assign_timeline = [t for t in timeline if t.get("event_type") == "task_assigned"]
check("Auto-enqueue created on assign", len(auto_assign_timeline) >= 1,
      f"count={len(auto_assign_timeline)}")

print()
print("--- 7. Integration: Auto-enqueue on status change ---")

r = requests.post(f"{BASE}/tasks/{task_id}/status", json={
    "status": "in_progress"
}, headers=auth_header(admin_token))
check("Move to in_progress", r.status_code == 200, f"status={r.status_code}")

r = requests.post(f"{BASE}/tasks/{task_id}/status", json={
    "status": "waiting_verify"
}, headers=auth_header(admin_token))
check("Move to waiting_verify", r.status_code == 200, f"status={r.status_code}")

r = requests.get(f"{BASE}/tasks/{task_id}/notifications", headers=auth_header(admin_token))
timeline2 = r.json() if r.status_code == 200 else []
waiting_verify_jobs = [t for t in timeline2 if t.get("event_type") == "status_waiting_verify"]
check("Auto-enqueue on waiting_verify", len(waiting_verify_jobs) >= 1,
      f"count={len(waiting_verify_jobs)}")

r = requests.post(f"{BASE}/tasks/{task_id}/status", json={
    "status": "closed"
}, headers=auth_header(admin_token))
check("Move to closed", r.status_code == 200, f"status={r.status_code}")

r = requests.get(f"{BASE}/tasks/{task_id}/notifications", headers=auth_header(admin_token))
timeline3 = r.json() if r.status_code == 200 else []
closed_jobs = [t for t in timeline3 if t.get("event_type") == "status_closed"]
check("Auto-enqueue on closed", len(closed_jobs) >= 1, f"count={len(closed_jobs)}")

check("All auto-enqueued are skipped_dry_run",
      all(t.get("status") == "skipped_dry_run" for t in timeline3 if t.get("event_type") != "manual_send"),
      f"statuses={[t.get('status') for t in timeline3]}")

print()
print("--- 8. Integration: Idempotency (no duplicate sends) ---")

r = requests.post(f"{BASE}/tasks/{task_id}/notify", json={
    "message": "duplicate test 1"
}, headers=auth_header(admin_token))
check("First manual send", r.status_code == 200, f"status={r.status_code}")

r = requests.post(f"{BASE}/tasks/{task_id}/notify", json={
    "message": "duplicate test 2"
}, headers=auth_header(admin_token))
check("Second manual send (same minute)", r.status_code == 200, f"status={r.status_code}")

r = requests.get(f"{BASE}/tasks/{task_id}/notifications", headers=auth_header(admin_token))
timeline4 = r.json() if r.status_code == 200 else []
manual_jobs = [t for t in timeline4 if t.get("event_type") == "manual_send"]
check("Idempotency: max 2 manual sends in same minute",
      len(manual_jobs) <= 2, f"manual_count={len(manual_jobs)}")

print()
print("--- 9. Integration: Retry Endpoint (admin only) ---")

r = requests.post(f"{BASE}/notifications/nonexistent-id/retry",
                   headers=auth_header(admin_token))
check("Retry nonexistent job returns 404", r.status_code == 404, f"status={r.status_code}")

if manual_job_id:
    r = requests.post(f"{BASE}/notifications/{manual_job_id}/retry",
                       headers=auth_header(admin_token))
    check("Retry skipped job returns 400 (not failed)",
          r.status_code == 400, f"status={r.status_code}")

print()
print("--- 10. RBAC: Notification Timeline Restrictions ---")

if viewer_token:
    r = requests.get(f"{BASE}/tasks/{task_id}/notifications",
                      headers=auth_header(viewer_token))
    check("Viewer CANNOT view notification timeline", r.status_code == 403,
          f"status={r.status_code}")

if contractor_token:
    r = requests.get(f"{BASE}/tasks/{task_id}/notifications",
                      headers=auth_header(contractor_token))
    check("Unrelated contractor CANNOT view notification timeline", r.status_code == 403,
          f"status={r.status_code}")

if elec_token:
    r = requests.get(f"{BASE}/tasks/{task_id}/notifications",
                      headers=auth_header(elec_token))
    check("Assigned contractor CAN view notification timeline", r.status_code == 200,
          f"status={r.status_code}")

print()
print("--- 11. RBAC: Manual Notify + Retry Restrictions ---")

if viewer_token:
    r = requests.post(f"{BASE}/tasks/{task_id}/notify", json={},
                       headers=auth_header(viewer_token))
    check("Viewer CANNOT send WhatsApp", r.status_code == 403, f"status={r.status_code}")

if contractor_token:
    r = requests.post(f"{BASE}/tasks/{task_id}/notify", json={},
                       headers=auth_header(contractor_token))
    check("Contractor CANNOT send WhatsApp", r.status_code == 403, f"status={r.status_code}")

print()
print("--- 12. RBAC: Retry Restrictions ---")

if viewer_token and manual_job_id:
    r = requests.post(f"{BASE}/notifications/{manual_job_id}/retry",
                       headers=auth_header(viewer_token))
    check("Viewer CANNOT retry", r.status_code == 403, f"status={r.status_code}")

if contractor_token and manual_job_id:
    r = requests.post(f"{BASE}/notifications/{manual_job_id}/retry",
                       headers=auth_header(contractor_token))
    check("Contractor CANNOT retry", r.status_code == 403, f"status={r.status_code}")

print()
print("--- 13. Webhook: Delivery Status Processing ---")

r = requests.post(f"{BASE}/webhooks/whatsapp", json={
    "entry": [{
        "changes": [{
            "value": {
                "statuses": [{
                    "id": "fake-provider-msg-id-123",
                    "status": "delivered"
                }]
            }
        }]
    }]
})
check("Webhook processes delivery status", r.status_code == 200, f"status={r.status_code}")

r = requests.get(f"{BASE}/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=12345")
check("Webhook verify with wrong token fails", r.status_code == 403, f"status={r.status_code}")

print()
print("--- 14. Edge Cases ---")

r2 = requests.post(f"{BASE}/tasks", json={
    "project_id": project_id, "building_id": building_id,
    "floor_id": floor_id, "unit_id": unit_id,
    "title": "Unassigned task", "category": "general"
}, headers=auth_header(admin_token))
unassigned_task_id = r2.json().get("id") if r2.status_code == 200 else None

if unassigned_task_id:
    r = requests.post(f"{BASE}/tasks/{unassigned_task_id}/notify", json={},
                       headers=auth_header(admin_token))
    check("Cannot notify unassigned task", r.status_code == 400, f"status={r.status_code}")

r = requests.post(f"{BASE}/tasks/nonexistent-task-id/notify", json={},
                   headers=auth_header(admin_token))
check("Cannot notify nonexistent task", r.status_code == 404, f"status={r.status_code}")

print()
print("--- 15. Sample Response Structures ---")
r = requests.get(f"{BASE}/tasks/{task_id}/notifications", headers=auth_header(admin_token))
if r.status_code == 200 and len(r.json()) > 0:
    sample = r.json()[0]
    print(f"  Sample notification timeline entry:")
    import json
    print(f"  {json.dumps(sample, indent=2, ensure_ascii=False)}")
    check("Sample has required fields",
          all(k in sample for k in ['id', 'task_id', 'event_type', 'target_phone', 'status', 'attempts']),
          f"keys={list(sample.keys())}")

print()
print("=" * 60)
print(f"  RESULTS: {PASSED} passed, {FAILED} failed")
print("=" * 60)
for res in RESULTS:
    print(res)
print()
if FAILED == 0:
    print("VERDICT: ALL NOTIFICATION TESTS PASSED")
else:
    print(f"VERDICT: {FAILED} TESTS FAILED")
    sys.exit(1)
