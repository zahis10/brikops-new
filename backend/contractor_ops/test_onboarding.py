import requests
import sys
import json
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

print("=" * 60)
print("  Access & Onboarding v1 Test Suite")
print("=" * 60)
print()

print("--- 1. OTP Flow ---")

test_phone = f"+97250{SUFFIX}01"

r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": test_phone})
check("Request OTP", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")
otp_response = r.json() if r.status_code == 200 else {}
check("OTP debug code present (dev mode)", 'otp_debug_code' in otp_response, f"keys={list(otp_response.keys())}")
check("OTP expires_in_seconds", otp_response.get('expires_in_seconds') == 300, f"got={otp_response.get('expires_in_seconds')}")
otp_code = otp_response.get('otp_debug_code', '000000')

r = requests.post(f"{BASE}/auth/verify-otp", json={"phone_e164": test_phone, "code": "999999"})
check("Verify OTP wrong code rejected", r.status_code == 400, f"status={r.status_code}")

r = requests.post(f"{BASE}/auth/verify-otp", json={"phone_e164": test_phone, "code": otp_code})
check("Verify OTP correct code", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")
verify_result = r.json() if r.status_code == 200 else {}
check("Verified=True", verify_result.get('verified') == True, f"got={verify_result.get('verified')}")
check("User not registered yet", verify_result.get('user_exists') == False, f"got={verify_result.get('user_exists')}")

print()
print("--- 2. Phone Validation ---")

r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": "invalid"})
check("Invalid phone rejected", r.status_code == 400, f"status={r.status_code}")

r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": "12345"})
check("Short phone rejected", r.status_code == 400, f"status={r.status_code}")

print()
print("--- 3. Owner Creates Project ---")

owner_email = f"owner_{SUFFIX}@test.com"
r = requests.post(f"{BASE}/auth/register", json={
    "email": owner_email, "password": "testpass123", "name": "Test Owner", "role": "owner"
})
check("Register owner", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/auth/login", json={"email": owner_email, "password": "testpass123"})
owner_token = r.json().get("token") if r.status_code == 200 else None
check("Login owner", owner_token is not None, f"status={r.status_code}")

project_code = f"ONB-{SUFFIX.upper()}"
r = requests.post(f"{BASE}/projects", json={
    "name": "Onboarding Test Project", "code": project_code,
    "description": "Test project for onboarding"
}, headers=auth_header(owner_token))
check("Owner creates project", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")
project_id = r.json().get("id") if r.status_code == 200 else None

print()
print("--- 4. Non-owner Cannot Create Project ---")

pm_email = f"pm_{SUFFIX}@test.com"
r = requests.post(f"{BASE}/auth/register", json={
    "email": pm_email, "password": "testpass123", "name": "Test PM", "role": "project_manager"
})
r = requests.post(f"{BASE}/auth/login", json={"email": pm_email, "password": "testpass123"})
pm_token = r.json().get("token") if r.status_code == 200 else None
check("Login PM", pm_token is not None, f"status={r.status_code}")

r = requests.post(f"{BASE}/projects", json={
    "name": "PM Project Attempt", "code": f"PM-{SUFFIX.upper()}",
}, headers=auth_header(pm_token))
check("PM cannot create project (403)", r.status_code == 403, f"status={r.status_code}")

contractor_email = f"cont_{SUFFIX}@test.com"
r = requests.post(f"{BASE}/auth/register", json={
    "email": contractor_email, "password": "testpass123", "name": "Test Contractor", "role": "contractor"
})
r = requests.post(f"{BASE}/auth/login", json={"email": contractor_email, "password": "testpass123"})
contractor_token = r.json().get("token") if r.status_code == 200 else None

r = requests.post(f"{BASE}/projects", json={
    "name": "Contractor Project", "code": f"CT-{SUFFIX.upper()}",
}, headers=auth_header(contractor_token))
check("Contractor cannot create project (403)", r.status_code == 403, f"status={r.status_code}")

print()
print("--- 5. Project Status Blocking ---")

r = requests.post(f"{BASE}/projects/{project_id}/buildings", json={
    "name": "Bldg A", "code": "A", "project_id": project_id
}, headers=auth_header(owner_token))
building_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/buildings/{building_id}/floors", json={
    "name": "Floor 1", "floor_number": 1, "building_id": building_id, "project_id": project_id
}, headers=auth_header(owner_token))
floor_id = r.json().get("id") if r.status_code == 200 else None

r = requests.post(f"{BASE}/floors/{floor_id}/units", json={
    "unit_no": "201", "floor_id": floor_id, "building_id": building_id, "project_id": project_id
}, headers=auth_header(owner_token))
unit_id = r.json().get("id") if r.status_code == 200 else None

suspended_code = f"SUS-{SUFFIX.upper()}"
r = requests.post(f"{BASE}/projects", json={
    "name": "Suspended Project", "code": suspended_code,
    "status": "suspended"
}, headers=auth_header(owner_token))
suspended_project_id = r.json().get("id") if r.status_code == 200 else None
check("Create suspended project", r.status_code == 200, f"status={r.status_code}")

if suspended_project_id:
    r2 = requests.post(f"{BASE}/projects/{suspended_project_id}/buildings", json={
        "name": "Bldg S", "code": "S", "project_id": suspended_project_id
    }, headers=auth_header(owner_token))
    s_building_id = r2.json().get("id") if r2.status_code == 200 else building_id

    r2 = requests.post(f"{BASE}/buildings/{s_building_id}/floors", json={
        "name": "Floor 1S", "floor_number": 1, "building_id": s_building_id, "project_id": suspended_project_id
    }, headers=auth_header(owner_token))
    s_floor_id = r2.json().get("id") if r2.status_code == 200 else floor_id

    r2 = requests.post(f"{BASE}/floors/{s_floor_id}/units", json={
        "unit_no": "S01", "floor_id": s_floor_id, "building_id": s_building_id, "project_id": suspended_project_id
    }, headers=auth_header(owner_token))
    s_unit_id = r2.json().get("id") if r2.status_code == 200 else unit_id

    r = requests.post(f"{BASE}/tasks", json={
        "project_id": suspended_project_id, "building_id": s_building_id,
        "floor_id": s_floor_id, "unit_id": s_unit_id,
        "title": "Should fail", "category": "general"
    }, headers=auth_header(owner_token))
    check("Suspended project blocks task creation (403)", r.status_code == 403, f"status={r.status_code}, body={r.text[:200]}")

r = requests.post(f"{BASE}/tasks", json={
    "project_id": project_id, "building_id": building_id,
    "floor_id": floor_id, "unit_id": unit_id,
    "title": "Active project task", "category": "general"
}, headers=auth_header(owner_token))
check("Active project allows task creation", r.status_code == 200, f"status={r.status_code}")

print()
print("--- 6. Phone Registration + Approval Flow ---")

reg_phone = f"+97250{SUFFIX}02"
r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": reg_phone})
otp_code2 = r.json().get('otp_debug_code', '000000') if r.status_code == 200 else '000000'

r = requests.post(f"{BASE}/auth/verify-otp", json={"phone_e164": reg_phone, "code": otp_code2})
check("Verify OTP for registration", r.status_code == 200, f"status={r.status_code}")

r = requests.get(f"{BASE}/auth/subcontractor-roles")
check("Get subcontractor roles", r.status_code == 200, f"status={r.status_code}")
sub_roles = r.json() if r.status_code == 200 else []
check("Subcontractor roles non-empty", len(sub_roles) > 0, f"got {len(sub_roles)}")

r = requests.get(f"{BASE}/auth/management-roles")
check("Get management roles", r.status_code == 200, f"status={r.status_code}")
mgmt_roles = r.json() if r.status_code == 200 else []
check("Management roles non-empty", len(mgmt_roles) > 0, f"got {len(mgmt_roles)}")

companies = requests.get(f"{BASE}/companies", headers=auth_header(owner_token)).json()
company_id = companies[0]['id'] if companies else None

r = requests.post(f"{BASE}/auth/register-with-phone", json={
    "phone_e164": reg_phone,
    "full_name": "עובד חדש",
    "project_id": project_id,
    "track": "subcontractor",
    "requested_role": sub_roles[0] if sub_roles else "plumber",
    "requested_company_id": company_id,
})
check("Register with phone", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")
reg_result = r.json() if r.status_code == 200 else {}
join_request_id = reg_result.get('join_request_id')
check("User status is pending", reg_result.get('user_status') == 'pending_pm_approval', f"got={reg_result.get('user_status')}")

r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": reg_phone})
otp_code3 = r.json().get('otp_debug_code', '000000') if r.status_code == 200 else '000000'
r = requests.post(f"{BASE}/auth/verify-otp", json={"phone_e164": reg_phone, "code": otp_code3})
verify3 = r.json() if r.status_code == 200 else {}
check("Pending user cannot login via OTP", verify3.get('user_status') == 'pending_pm_approval', f"got={verify3.get('user_status')}")
check("No token for pending user", 'token' not in verify3, f"token present={True if 'token' in verify3 else False}")

print()
print("--- 7. PM Approval Queue ---")

pm_mem_id = str(uuid.uuid4())
import pymongo
mongo = pymongo.MongoClient("mongodb://localhost:27017")
test_db = mongo["contractor_ops"]
test_db.project_memberships.insert_one({
    'id': pm_mem_id, 'project_id': project_id, 'user_id': None,
    'role': 'project_manager', 'status': 'active',
})
pm_user = test_db.users.find_one({'email': pm_email})
if pm_user:
    test_db.project_memberships.update_one(
        {'id': pm_mem_id},
        {'$set': {'user_id': pm_user['id']}}
    )

r = requests.get(f"{BASE}/projects/{project_id}/join-requests", headers=auth_header(pm_token))
check("PM can view join requests", r.status_code == 200, f"status={r.status_code}")
join_requests = r.json() if r.status_code == 200 else []
check("Join request visible", len(join_requests) > 0, f"count={len(join_requests)}")

pending_jr = next((jr for jr in join_requests if jr.get('status') == 'pending'), None)
if pending_jr:
    check("Join request has user_name", bool(pending_jr.get('user_name')), f"name={pending_jr.get('user_name')}")
    check("Join request has track", pending_jr.get('track') == 'subcontractor', f"track={pending_jr.get('track')}")

r = requests.get(f"{BASE}/projects/{project_id}/join-requests?status=pending", headers=auth_header(pm_token))
check("Filter join requests by status", r.status_code == 200, f"status={r.status_code}")

r = requests.get(f"{BASE}/projects/{project_id}/join-requests", headers=auth_header(contractor_token))
check("Contractor cannot view join requests (403)", r.status_code == 403, f"status={r.status_code}")

print()
print("--- 8. Approve Join Request ---")

if join_request_id:
    r = requests.post(f"{BASE}/join-requests/{join_request_id}/approve", json={}, headers=auth_header(pm_token))
    check("PM approves join request", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")
    approve_result = r.json() if r.status_code == 200 else {}
    check("Approve returns membership_id", 'membership_id' in approve_result, f"keys={list(approve_result.keys())}")

    r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": reg_phone})
    otp_code4 = r.json().get('otp_debug_code', '000000') if r.status_code == 200 else '000000'
    r = requests.post(f"{BASE}/auth/verify-otp", json={"phone_e164": reg_phone, "code": otp_code4})
    verify4 = r.json() if r.status_code == 200 else {}
    check("Approved user can login via OTP", 'token' in verify4, f"keys={list(verify4.keys())}")
    check("Approved user status is active", verify4.get('user_status') == 'active', f"got={verify4.get('user_status')}")

    r = requests.post(f"{BASE}/join-requests/{join_request_id}/approve", json={}, headers=auth_header(pm_token))
    check("Cannot approve already-approved request", r.status_code == 400, f"status={r.status_code}")

print()
print("--- 9. Reject Join Request ---")

reject_phone = f"+97250{SUFFIX}03"
r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": reject_phone})
otp5 = r.json().get('otp_debug_code', '000000') if r.status_code == 200 else '000000'
r = requests.post(f"{BASE}/auth/verify-otp", json={"phone_e164": reject_phone, "code": otp5})

r = requests.post(f"{BASE}/auth/register-with-phone", json={
    "phone_e164": reject_phone,
    "full_name": "עובד לדחייה",
    "project_id": project_id,
    "track": "management",
    "requested_role": mgmt_roles[0] if mgmt_roles else "engineer",
})
reject_result = r.json() if r.status_code == 200 else {}
reject_jr_id = reject_result.get('join_request_id')

if reject_jr_id:
    r = requests.post(f"{BASE}/join-requests/{reject_jr_id}/reject", json={
        "reason": "לא מתאים לפרויקט"
    }, headers=auth_header(pm_token))
    check("PM rejects join request", r.status_code == 200, f"status={r.status_code}")

    r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": reject_phone})
    otp6 = r.json().get('otp_debug_code', '000000') if r.status_code == 200 else '000000'
    r = requests.post(f"{BASE}/auth/verify-otp", json={"phone_e164": reject_phone, "code": otp6})
    verify6 = r.json() if r.status_code == 200 else {}
    check("Rejected user status", verify6.get('user_status') == 'rejected', f"got={verify6.get('user_status')}")
    check("Rejected user cannot get token", 'token' not in verify6, f"has_token={'token' in verify6}")

print()
print("--- 10. OTP Lockout ---")

lockout_phone = f"+97250{SUFFIX}04"
r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": lockout_phone})
check("Request OTP for lockout test", r.status_code == 200, f"status={r.status_code}")

for i in range(5):
    r = requests.post(f"{BASE}/auth/verify-otp", json={"phone_e164": lockout_phone, "code": "000000"})

check("Account locked after 5 wrong attempts", r.status_code in (400, 429), f"status={r.status_code}")

print()
print("--- 11. Management Registration ---")

mgmt_phone = f"+97250{SUFFIX}05"
r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": mgmt_phone})
otp7 = r.json().get('otp_debug_code', '000000') if r.status_code == 200 else '000000'
r = requests.post(f"{BASE}/auth/verify-otp", json={"phone_e164": mgmt_phone, "code": otp7})

r = requests.post(f"{BASE}/auth/register-with-phone", json={
    "phone_e164": mgmt_phone,
    "full_name": "מהנדס חדש",
    "project_id": project_id,
    "track": "management",
    "requested_role": "engineer",
})
check("Management registration", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")
mgmt_result = r.json() if r.status_code == 200 else {}
check("Management registration pending", mgmt_result.get('user_status') == 'pending_pm_approval', f"got={mgmt_result.get('user_status')}")

r = requests.post(f"{BASE}/auth/register-with-phone", json={
    "phone_e164": mgmt_phone,
    "full_name": "מהנדס כפול",
    "project_id": project_id,
    "track": "management",
    "requested_role": "engineer",
})
check("Duplicate phone registration rejected", r.status_code == 400, f"status={r.status_code}")

print()
print("--- 12. Validation Edge Cases ---")

r = requests.post(f"{BASE}/auth/register-with-phone", json={
    "phone_e164": f"+97250{SUFFIX}99",
    "full_name": "A",
    "project_id": project_id,
    "track": "management",
    "requested_role": "engineer",
})
check("Short name rejected", r.status_code == 400, f"status={r.status_code}")

r = requests.post(f"{BASE}/auth/register-with-phone", json={
    "phone_e164": f"+97250{SUFFIX}98",
    "full_name": "Valid Name",
    "project_id": "nonexistent",
    "track": "management",
    "requested_role": "engineer",
})
check("Nonexistent project rejected", r.status_code == 404, f"status={r.status_code}")

r = requests.post(f"{BASE}/auth/register-with-phone", json={
    "phone_e164": f"+97250{SUFFIX}97",
    "full_name": "Valid Name",
    "project_id": project_id,
    "track": "subcontractor",
    "requested_role": "plumber",
})
check("Subcontractor without company rejected", r.status_code == 400, f"status={r.status_code}")

r = requests.post(f"{BASE}/auth/register-with-phone", json={
    "phone_e164": f"+97250{SUFFIX}96",
    "full_name": "Valid Name",
    "project_id": project_id,
    "track": "management",
    "requested_role": "plumber",
})
check("Wrong role for track rejected", r.status_code == 400, f"status={r.status_code}")

print()
print("--- 13. Set Password ---")

if join_request_id:
    r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": reg_phone})
    otp_pw = r.json().get('otp_debug_code', '000000') if r.status_code == 200 else '000000'
    r = requests.post(f"{BASE}/auth/verify-otp", json={"phone_e164": reg_phone, "code": otp_pw})
    user_token = r.json().get('token') if r.status_code == 200 else None

    if user_token:
        r = requests.post(f"{BASE}/auth/set-password", json={"password": "newpass123"}, headers=auth_header(user_token))
        check("Set password", r.status_code == 200, f"status={r.status_code}")

        r = requests.post(f"{BASE}/auth/login-phone", json={
            "phone_e164": reg_phone, "password": "newpass123"
        })
        check("Login with phone+password after set", r.status_code == 200, f"status={r.status_code}")

        r = requests.post(f"{BASE}/auth/login-phone", json={
            "phone_e164": reg_phone, "password": "wrongpass"
        })
        check("Wrong password rejected", r.status_code == 401, f"status={r.status_code}")

        r = requests.post(f"{BASE}/auth/set-password", json={"password": "short"}, headers=auth_header(user_token))
        check("Short password rejected", r.status_code == 400, f"status={r.status_code}")

print()
print("=" * 60)
print(f"  RESULTS: {PASSED} passed, {FAILED} failed, {PASSED + FAILED} total")
print("=" * 60)
for r in RESULTS:
    print(r)
print()
if FAILED > 0:
    print(f"  {FAILED} TESTS FAILED")
    sys.exit(1)
else:
    print("  ALL TESTS PASSED")
    sys.exit(0)
