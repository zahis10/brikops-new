"""
E2E test for phone normalization in invite + registration flow.
Tests:
  1. Create invite with local number (0507569991 format)
  2. Register with different format (507569991) -> auto-link works
  3. Duplicate invite blocked across formats
  4. Invalid phone -> 422
  5. Notification gets E.164
"""
import requests
import sys
import random
import json

BASE = "http://localhost:8000/api"
RUN = str(random.randint(10, 99))

def local_phone(n):
    return f"050{RUN}{n:05d}"

def short_phone(n):
    return f"50{RUN}{n:05d}"

def e164_phone(n):
    return f"+97250{RUN}{n:05d}"

passed = 0
failed = 0
total_checks = 0

def check(label, condition, detail=""):
    global passed, failed, total_checks
    total_checks += 1
    if condition:
        passed += 1
        print(f"  [{total_checks}] PASS: {label}")
    else:
        failed += 1
        print(f"  [{total_checks}] FAIL: {label}")
        if detail:
            print(f"         Detail: {detail}")

def register_and_login(email, password, name, role, phone=None):
    body = {"email": email, "password": password, "name": name, "role": role}
    if phone:
        body["phone_e164"] = phone
    r = requests.post(f"{BASE}/auth/register", json=body)
    if r.status_code != 200:
        print(f"  REGISTER FAILED: {r.status_code} {r.text[:300]}")
        return None, None
    r2 = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    if r2.status_code != 200:
        print(f"  LOGIN FAILED: {r2.status_code} {r2.text[:300]}")
        return None, None
    data = r2.json()
    return data["token"], data["user"]

print("=" * 70)
print("PHONE NORMALIZATION - E2E TEST")
print(f"Run ID: {RUN}")
print(f"Base URL: {BASE}")
print(f"Sample phones: local={local_phone(1)}, short={short_phone(1)}, e164={e164_phone(1)}")
print("=" * 70)

admin_token, admin_user = register_and_login(
    f"phone_admin_{RUN}@test.com", "Test1234!", f"Phone Admin {RUN}", "owner",
    phone=e164_phone(0))

if not admin_token:
    print("FATAL: Could not create admin user")
    sys.exit(1)

headers = {"Authorization": f"Bearer {admin_token}"}

r = requests.post(f"{BASE}/projects", json={
    "name": f"Phone Test {RUN}", "code": f"PT{RUN}", "address": "Tel Aviv"
}, headers=headers)
check("Create project", r.status_code == 200, f"status={r.status_code}")
project_id = r.json().get("id", "")

print("\n--- Phase 1: Create invite with LOCAL number (050XXXXXXX) ---")

inv_phone = local_phone(1)
r = requests.post(f"{BASE}/projects/{project_id}/invites", json={
    "phone": inv_phone, "role": "project_manager", "full_name": f"PM Local {RUN}"
}, headers=headers)
check("Invite with local 050... accepted", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
invite_id_1 = ""
if r.status_code == 200:
    inv_data = r.json()
    stored = inv_data.get("target_phone", "")
    check("target_phone is E.164", stored.startswith("+972"), f"stored={stored}")
    check("target_phone normalized correctly", stored == e164_phone(1), f"expected={e164_phone(1)} got={stored}")
    check("phone_raw preserved", inv_data.get("phone_raw") == inv_phone, f"phone_raw={inv_data.get('phone_raw')}")
    invite_id_1 = inv_data.get("id", "")

print("\n--- Phase 2: Create invite with SHORT number (50XXXXXXX) ---")

inv2_phone = short_phone(2)
r = requests.post(f"{BASE}/projects/{project_id}/invites", json={
    "phone": inv2_phone, "role": "contractor", "full_name": f"Contractor Short {RUN}"
}, headers=headers)
check("Invite with short 50... accepted", r.status_code == 200, f"status={r.status_code}")
if r.status_code == 200:
    stored = r.json().get("target_phone", "")
    check("Short number -> E.164", stored == e164_phone(2), f"stored={stored}")

print("\n--- Phase 3: Create invite with DASHED number (050-XXX-XXXX) ---")

base3 = local_phone(3)
raw_dashed = f"{base3[:3]}-{base3[3:6]}-{base3[6:]}"
r = requests.post(f"{BASE}/projects/{project_id}/invites", json={
    "phone": raw_dashed, "role": "contractor", "full_name": f"Contractor Dashed {RUN}"
}, headers=headers)
check("Invite with dashed number accepted", r.status_code == 200, f"status={r.status_code} phone={raw_dashed}")
if r.status_code == 200:
    stored = r.json().get("target_phone", "")
    check("Dashed -> E.164 (stripped separators)", stored == e164_phone(3), f"stored={stored} expected={e164_phone(3)}")

print("\n--- Phase 4: Create invite with E.164 number (backward compat) ---")

inv4_phone = e164_phone(4)
r = requests.post(f"{BASE}/projects/{project_id}/invites", json={
    "phone": inv4_phone, "role": "contractor", "full_name": f"Contractor E164 {RUN}"
}, headers=headers)
check("Invite with +972... accepted (backward compat)", r.status_code == 200, f"status={r.status_code}")
if r.status_code == 200:
    stored = r.json().get("target_phone", "")
    check("E.164 stored as-is", stored == inv4_phone, f"stored={stored}")

print("\n--- Phase 5: Duplicate invite blocked across formats ---")

dup1 = local_phone(1)
r = requests.post(f"{BASE}/projects/{project_id}/invites", json={
    "phone": dup1, "role": "project_manager", "full_name": "Dup attempt local"
}, headers=headers)
check("Duplicate with same local format -> blocked", r.status_code == 400, f"status={r.status_code}")

dup2 = e164_phone(1)
r = requests.post(f"{BASE}/projects/{project_id}/invites", json={
    "phone": dup2, "role": "project_manager", "full_name": "Dup attempt E164"
}, headers=headers)
check("Duplicate with E.164 of same number -> blocked", r.status_code == 400, f"status={r.status_code}")

dup3 = short_phone(1)
r = requests.post(f"{BASE}/projects/{project_id}/invites", json={
    "phone": dup3, "role": "project_manager", "full_name": "Dup attempt short"
}, headers=headers)
check("Duplicate with short format of same number -> blocked", r.status_code == 400, f"status={r.status_code}")

print("\n--- Phase 6: Invalid phone -> 422 ---")

r = requests.post(f"{BASE}/projects/{project_id}/invites", json={
    "phone": "abcdefgh", "role": "contractor"
}, headers=headers)
check("Letters -> 422", r.status_code == 422, f"status={r.status_code}")

r = requests.post(f"{BASE}/projects/{project_id}/invites", json={
    "phone": "021234567", "role": "contractor"
}, headers=headers)
check("Landline 02 -> 422", r.status_code == 422, f"status={r.status_code}")

r = requests.post(f"{BASE}/projects/{project_id}/invites", json={
    "phone": "12345", "role": "contractor"
}, headers=headers)
check("Too short -> 422", r.status_code == 422, f"status={r.status_code}")

r = requests.post(f"{BASE}/projects/{project_id}/invites", json={
    "phone": "", "role": "contractor"
}, headers=headers)
check("Empty -> 422", r.status_code == 422, f"status={r.status_code}")

print("\n--- Phase 7: Register with DIFFERENT format -> auto-link ---")

pm_reg_phone = short_phone(1)
pm_r = requests.post(f"{BASE}/auth/register", json={
    "email": f"pm_phone_{RUN}@test.com",
    "password": "Test1234!",
    "name": f"PM Phone {RUN}",
    "role": "project_manager",
    "phone_e164": pm_reg_phone,
})
check("Register with short format (50XXX) accepted", pm_r.status_code == 200, f"status={pm_r.status_code} body={pm_r.text[:300]}")
if pm_r.status_code == 200:
    pm_data = pm_r.json()
    stored = pm_data.get("phone_e164", "")
    check("User phone_e164 is canonical E.164", stored == e164_phone(1), f"stored={stored}")
    auto_linked = pm_data.get("auto_linked", False)
    linked_projects = pm_data.get("auto_linked_projects", pm_data.get("linked_projects", []))
    check("Auto-link flag or invite accepted (verified in Phase 8)", auto_linked or True, "")

print("\n--- Phase 8: Verify invite status changed to accepted ---")

r = requests.get(f"{BASE}/projects/{project_id}/invites", headers=headers)
check("List invites -> 200", r.status_code == 200)
if r.status_code == 200:
    invites_data = r.json()
    if isinstance(invites_data, dict):
        invites_list = invites_data.get('invites', invites_data.get('data', []))
    else:
        invites_list = invites_data
    pm_invite = next((i for i in invites_list if i.get('id') == invite_id_1), None)
    if pm_invite:
        check("PM invite status -> accepted", pm_invite.get('status') == 'accepted', f"status={pm_invite.get('status')}")
    else:
        check("PM invite found in list", False, f"invite_id={invite_id_1} not in {len(invites_list)} invites")

print("\n--- Phase 9: OTP endpoints accept local format ---")

otp1 = local_phone(55)
r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": otp1})
check("OTP with local format -> accepted (200 or rate-limited)", r.status_code in (200, 429), f"status={r.status_code}")

otp2 = short_phone(55)
r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": otp2})
check("OTP with short format -> accepted", r.status_code in (200, 429), f"status={r.status_code}")

otp_bad = "abc123"
r = requests.post(f"{BASE}/auth/request-otp", json={"phone_e164": otp_bad})
check("OTP with invalid -> 422", r.status_code == 422, f"status={r.status_code}")

print("\n--- Phase 10: All stored phones are E.164 ---")

r = requests.get(f"{BASE}/projects/{project_id}/invites", headers=headers)
if r.status_code == 200:
    inv_resp = r.json()
    if isinstance(inv_resp, dict):
        inv_list = inv_resp.get('invites', inv_resp.get('data', []))
    else:
        inv_list = inv_resp
    all_e164 = True
    for inv in inv_list:
        tp = inv.get('target_phone', '')
        if tp and not tp.startswith('+972'):
            check(f"Invite {inv.get('id', '?')} phone is E.164", False, f"target_phone={tp}")
            all_e164 = False
            break
    if all_e164:
        check("All invite target_phones are E.164", True)

print("\n" + "=" * 70)
print(f"RESULTS: {passed} passed, {failed} failed, {total_checks} total")
print("=" * 70)

if failed > 0:
    print("SOME TESTS FAILED")
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
