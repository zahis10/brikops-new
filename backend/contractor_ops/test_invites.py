import requests
import sys
import uuid
import time

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

def h(token):
    return auth_header(token)

def register_and_login(email, password, name, role, phone_e164=None):
    payload = {"email": email, "password": password, "name": name, "role": role}
    if phone_e164:
        payload["phone_e164"] = phone_e164
    r = requests.post(f"{BASE}/auth/register", json=payload)
    if r.status_code != 200:
        print(f"    [DEBUG] Register failed for {email}: {r.status_code} {r.text[:200]}")
        return None, None
    r2 = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    if r2.status_code != 200:
        return None, None
    data = r2.json()
    return data.get("token"), data.get("user", {})

print("=" * 60)
print("  Invite System Test Suite")
print("=" * 60)
print()

print("--- 1. Setup: Register Users ---")
admin_token, admin_user = register_and_login(
    f"inv_admin_{SUFFIX}@test.com", "testpass123", "Invite Admin", "admin")
check("Register admin", admin_token is not None, "no token")

viewer_token, viewer_user = register_and_login(
    f"inv_viewer_{SUFFIX}@test.com", "testpass123", "Invite Viewer", "viewer")
check("Register viewer", viewer_token is not None, "no token")

contractor_token, contractor_user = register_and_login(
    f"inv_contractor_{SUFFIX}@test.com", "testpass123", "Invite Contractor", "contractor")
check("Register contractor", contractor_token is not None, "no token")

pm_token, pm_user = register_and_login(
    f"inv_pm_{SUFFIX}@test.com", "testpass123", "Invite PM", "viewer")
check("Register PM user (as viewer initially)", pm_token is not None, "no token")

print()
print("--- 2. Setup: Create Projects ---")
r = requests.post(f"{BASE}/projects", json={
    "name": f"Invite Test Project A {SUFFIX}", "code": f"ITA{SUFFIX}",
    "description": "Project A for invite tests"
}, headers=h(admin_token))
check("Create project A", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")
project_a_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/projects", json={
    "name": f"Invite Test Project B {SUFFIX}", "code": f"ITB{SUFFIX}",
    "description": "Project B for isolation tests"
}, headers=h(admin_token))
check("Create project B", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")
project_b_id = r.json().get("id") if r.status_code == 200 else None

print()
print("--- 3. RBAC Hierarchy Tests ---")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001001", "role": "project_manager"
}, headers=h(admin_token))
check("Admin can create invite role=project_manager", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")
pm_invite = r.json() if r.status_code == 200 else {}

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001002", "role": "management_team", "sub_role": "site_manager"
}, headers=h(admin_token))
check("Admin can create invite role=management_team (sub_role=site_manager)", r.status_code == 200,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001003", "role": "contractor"
}, headers=h(admin_token))
check("Admin can create invite role=contractor", r.status_code == 200,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/assign-pm", json={
    "user_id": pm_user["id"]
}, headers=h(admin_token))
check("Assign PM to project A", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")

pm_token2, _ = register_and_login(
    f"inv_pm_{SUFFIX}@test.com", "testpass123", "Invite PM", "viewer")
if pm_token2:
    pm_token = pm_token2

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001004", "role": "management_team", "sub_role": "execution_engineer"
}, headers=h(pm_token))
check("PM can create invite role=management_team", r.status_code == 200,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001005", "role": "contractor"
}, headers=h(pm_token))
check("PM can create invite role=contractor", r.status_code == 200,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001006", "role": "project_manager"
}, headers=h(pm_token))
check("PM CANNOT create invite role=project_manager", r.status_code == 403,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001007", "role": "contractor"
}, headers=h(contractor_token))
check("Contractor CANNOT create invite", r.status_code == 403,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001008", "role": "contractor"
}, headers=h(viewer_token))
check("Viewer CANNOT create invite", r.status_code == 403,
      f"status={r.status_code}, body={r.text[:200]}")

print()
print("--- 4. Invite Validation Tests ---")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": "0501234567", "role": "contractor"
}, headers=h(admin_token))
check("Invalid phone (no + prefix) rejected", r.status_code in (400, 422),
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001003", "role": "contractor"
}, headers=h(admin_token))
check("Duplicate pending invite rejected", r.status_code == 400,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001009", "role": "management_team"
}, headers=h(admin_token))
mgmt_no_subrole_status = r.status_code
check("management_team invite WITHOUT sub_role", mgmt_no_subrole_status == 200,
      f"status={mgmt_no_subrole_status}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001010", "role": "management_team", "sub_role": "invalid_role"
}, headers=h(admin_token))
check("management_team invite WITH invalid sub_role rejected", r.status_code == 400,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001011", "role": "management_team", "sub_role": "safety_assistant"
}, headers=h(admin_token))
check("management_team invite WITH valid sub_role", r.status_code == 200,
      f"status={r.status_code}, body={r.text[:200]}")
valid_mgmt_invite = r.json() if r.status_code == 200 else {}

print()
print("--- 5. Token & Expiry Tests ---")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001012", "role": "contractor"
}, headers=h(admin_token))
token_test_invite = r.json() if r.status_code == 200 else {}

check("Invite has token field (non-empty)",
      bool(token_test_invite.get("token")),
      f"token={token_test_invite.get('token')}")

check("Invite has expires_at field (in future)",
      bool(token_test_invite.get("expires_at")) and token_test_invite["expires_at"] > time.strftime("%Y-%m-%dT%H:%M:%S"),
      f"expires_at={token_test_invite.get('expires_at')}")

check("Invite has status=pending",
      token_test_invite.get("status") == "pending",
      f"status={token_test_invite.get('status')}")

print()
print("--- 6. Auto-Link Tests ---")

auto_link_phone = f"+9725{SUFFIX}013"
r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": auto_link_phone, "role": "project_manager"
}, headers=h(admin_token))
check("Create invite for auto-link phone", r.status_code == 200,
      f"status={r.status_code}, body={r.text[:200]}")
auto_link_invite = r.json() if r.status_code == 200 else {}
auto_link_invite_id = auto_link_invite.get("id", "")

r = requests.post(f"{BASE}/auth/register", json={
    "email": f"autolink_{SUFFIX}@test.com", "password": "testpass123",
    "name": "AutoLink User", "role": "viewer",
    "phone_e164": auto_link_phone
})
check("Register user with invited phone", r.status_code == 200,
      f"status={r.status_code}, body={r.text[:200]}")

r2 = requests.post(f"{BASE}/auth/login", json={
    "email": f"autolink_{SUFFIX}@test.com", "password": "testpass123"
})
autolink_user_token = r2.json().get("token") if r2.status_code == 200 else None

r = requests.get(f"{BASE}/projects/{project_a_id}/invites", headers=h(admin_token))
invites_list = r.json() if r.status_code == 200 else []
auto_invite_found = [inv for inv in invites_list if inv.get("id") == auto_link_invite_id]
if auto_invite_found:
    check("Invite status changed to accepted after auto-link",
          auto_invite_found[0].get("status") == "accepted",
          f"status={auto_invite_found[0].get('status')}")
else:
    check("Invite status changed to accepted after auto-link", False,
          f"invite {auto_link_invite_id} not found in list")

print()
print("--- 7. Invite Management Tests ---")

r = requests.get(f"{BASE}/projects/{project_a_id}/invites", headers=h(admin_token))
check("List invites returns results", r.status_code == 200 and len(r.json()) > 0,
      f"status={r.status_code}, count={len(r.json()) if r.status_code == 200 else 0}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001014", "role": "contractor"
}, headers=h(admin_token))
cancel_invite_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/projects/{project_a_id}/invites/{cancel_invite_id}/cancel", headers=h(admin_token))
check("Cancel pending invite", r.status_code == 200,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites/{cancel_invite_id}/cancel", headers=h(admin_token))
check("Cannot cancel already cancelled invite", r.status_code == 400,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": f"+97250001015", "role": "contractor"
}, headers=h(admin_token))
resend_invite_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/projects/{project_a_id}/invites/{resend_invite_id}/resend", headers=h(admin_token))
check("Resend pending invite", r.status_code == 200,
      f"status={r.status_code}, body={r.text[:200]}")

print()
print("--- 8. Cross-Project Isolation ---")

r = requests.post(f"{BASE}/projects/{project_b_id}/invites", json={
    "phone": f"+97250001016", "role": "contractor"
}, headers=h(pm_token))
check("PM of project A CANNOT create invite in project B", r.status_code == 403,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_b_id}/invites", json={
    "phone": f"+97250001017", "role": "contractor"
}, headers=h(admin_token))
project_b_invite_id = r.json().get("id") if r.status_code == 200 else None

r = requests.get(f"{BASE}/projects/{project_b_id}/invites", headers=h(pm_token))
check("PM of project A cannot list invites of project B", r.status_code == 403,
      f"status={r.status_code}")

if project_b_invite_id:
    r = requests.post(f"{BASE}/projects/{project_b_id}/invites/{project_b_invite_id}/cancel",
                       headers=h(pm_token))
    check("PM of project A cannot cancel invite in project B", r.status_code in (403, 404),
          f"status={r.status_code}")
else:
    check("PM of project A cannot cancel invite in project B", False, "no invite created in B")

print()
print("--- 9. Available PMs Endpoint Tests ---")

r = requests.get(f"{BASE}/projects/{project_a_id}/available-pms", headers=h(admin_token))
check("GET available-pms returns users", r.status_code == 200 and isinstance(r.json(), list),
      f"status={r.status_code}")

available_pms = r.json() if r.status_code == 200 else []
pm_ids_in_list = [u["id"] for u in available_pms]
check("Assigned PM not in available-pms", pm_user["id"] not in pm_ids_in_list,
      f"PM user {pm_user['id']} found in available list")

searchable_user_token, searchable_user = register_and_login(
    f"inv_searchable_{SUFFIX}@test.com", "testpass123", f"SearchableUser{SUFFIX}", "viewer")
r = requests.get(f"{BASE}/projects/{project_a_id}/available-pms?search=SearchableUser{SUFFIX}",
                  headers=h(admin_token))
check("Search filter works for available-pms",
      r.status_code == 200 and any(u.get("name", "").startswith("SearchableUser") for u in r.json()),
      f"status={r.status_code}, results={len(r.json()) if r.status_code == 200 else 0}")

print()
print("--- 10. No Duplicate Membership (Auto-Link Existing User) ---")

existing_user_phone = f"+9725{SUFFIX}018"
existing_user_token, existing_user_data = register_and_login(
    f"inv_existing_{SUFFIX}@test.com", "testpass123", "Existing User", "viewer",
    phone_e164=existing_user_phone)
check("Register user with phone for auto-link test", existing_user_token is not None, "no token")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": existing_user_phone, "role": "contractor"
}, headers=h(admin_token))
check("Invite for existing user phone auto-links",
      r.status_code == 200 and r.json().get("auto_linked") == True,
      f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/projects/{project_a_id}/invites", json={
    "phone": existing_user_phone, "role": "contractor"
}, headers=h(admin_token))
check("Second invite for same user+project rejected (already member)",
      r.status_code == 400,
      f"status={r.status_code}, body={r.text[:200]}")

print()
print("=" * 60)
print(f"  INVITE SYSTEM TEST SUMMARY")
print("=" * 60)
print(f"  Total: {PASSED + FAILED}")
print(f"  Passed: {PASSED}")
print(f"  Failed: {FAILED}")
for res in RESULTS:
    print(res)
print()
if FAILED == 0:
    print("VERDICT: ALL TESTS PASSED")
else:
    print(f"VERDICT: {FAILED} TESTS FAILED")
    sys.exit(1)
