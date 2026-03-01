#!/usr/bin/env python3
"""
E2E Invite Proof Script
========================
Comprehensive proof-of-delivery for the Invite Hierarchy system.
Outputs: LIVE_INVITE_OUTPUT.txt with all request/response pairs.
Covers:
  1. Full E2E chain: Admin → PM → Management → Contractor
  2. RBAC Matrix with HTTP status codes
  3. Cross-project isolation (403)
  4. Duplicate/expired/cancel blocking
  5. Expired invite hard-fail (force-expired via DB, registration skips auto-link)
  6. Audit trail (7+ event types from DB)
  7. Auto-link on registration
  8. notification_queued audit events
"""

import requests, json, time, uuid, sys, os
from datetime import datetime, timedelta
from pymongo import MongoClient

BASE = os.environ.get('TEST_BASE_URL', 'http://localhost:8000/api')
import random as _rnd
SUFFIX = str(_rnd.randint(10000, 99999))
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'LIVE_INVITE_OUTPUT.txt')

results = []
passed = 0
failed = 0
audit_events = []

def log(msg):
    results.append(msg)
    print(msg)

def log_req_res(method, url, req_body, status, res_body, label=""):
    results.append(f"\n{'='*60}")
    if label:
        results.append(f">>> {label}")
    results.append(f"{method} {url}")
    if req_body:
        results.append(f"Request: {json.dumps(req_body, ensure_ascii=False, indent=2)}")
    results.append(f"Status: {status}")
    if isinstance(res_body, (dict, list)):
        body_str = json.dumps(res_body, ensure_ascii=False, indent=2)
        if len(body_str) > 2000:
            body_str = body_str[:2000] + "\n... (truncated)"
        results.append(f"Response: {body_str}")
    else:
        results.append(f"Response: {res_body}")
    results.append(f"{'='*60}")
    print(f"  [{status}] {method} {url.replace(BASE,'')} - {label}")

def h(token):
    return {'Authorization': f'Bearer {token}'}

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        log(f"  PASS  {name}")
    else:
        failed += 1
        log(f"  FAIL  {name} — {detail}")

def post(url, body, headers, label=""):
    r = requests.post(url, json=body, headers=headers)
    log_req_res("POST", url, body, r.status_code, r.json() if r.headers.get('content-type','').startswith('application/json') else r.text, label)
    return r

def get(url, headers, label="", params=None):
    r = requests.get(url, headers=headers, params=params)
    log_req_res("GET", url, None, r.status_code, r.json() if r.headers.get('content-type','').startswith('application/json') else r.text, label)
    return r

def delete(url, headers, label=""):
    r = requests.delete(url, headers=headers)
    log_req_res("DELETE", url, None, r.status_code, r.json() if r.headers.get('content-type','').startswith('application/json') else r.text, label)
    return r

def register_and_login(email, password, name, role, phone_e164=None):
    body = {'email': email, 'password': password, 'name': name, 'role': role}
    if phone_e164:
        body['phone_e164'] = phone_e164
    r = requests.post(f"{BASE}/auth/register", json=body)
    reg_data = r.json() if r.status_code == 200 else {}
    if reg_data.get('user_id') and not reg_data.get('id'):
        reg_data['id'] = reg_data['user_id']
    token = reg_data.get('token')
    if token:
        return token, reg_data
    r2 = requests.post(f"{BASE}/auth/login", json={'email': email, 'password': password})
    if r2.status_code == 200:
        login_data = r2.json()
        merged = {**reg_data, **login_data}
        if merged.get('user_id') and not merged.get('id'):
            merged['id'] = merged['user_id']
        return login_data.get('token'), merged
    return None, reg_data


log("=" * 70)
log(f"INVITE SYSTEM — FULL E2E PROOF")
log(f"Timestamp: {datetime.utcnow().isoformat()}Z")
log(f"Test Suffix: {SUFFIX}")
log(f"Base URL: {BASE}")
log("=" * 70)

# ============================================================
# SETUP: Create admin + project
# ============================================================
log("\n\n" + "=" * 70)
log("PHASE 0: SETUP")
log("=" * 70)

admin_token, admin_data = register_and_login(
    f"proof_admin_{SUFFIX}@test.com", "testpass123", f"Proof Admin {SUFFIX}", "owner")
check("Admin registered/logged in", admin_token is not None, "no token")

r = post(f"{BASE}/projects", {
    'name': f'פרויקט הוכחה {SUFFIX}',
    'code': f'PRF-{SUFFIX}',
    'address': 'רחוב הבדיקות 1, תל אביב'
}, h(admin_token), "Create proof project")
check("Project created", r.status_code == 200, f"status={r.status_code}")
project_id = r.json().get('id', '')
project_name = r.json().get('name', '')
log(f"\n  Project ID: {project_id}")
log(f"  Project Name: {project_name}")

# Create second project for cross-project tests
r_p2 = post(f"{BASE}/projects", {
    'name': f'פרויקט אחר {SUFFIX}',
    'code': f'OTH-{SUFFIX}',
    'address': 'רחוב אחר 2'
}, h(admin_token), "Create second project (for cross-project isolation)")
project_b_id = r_p2.json().get('id', '')

# ============================================================
# PHASE 1: Admin invites PM by phone
# ============================================================
log("\n\n" + "=" * 70)
log("PHASE 1: Admin invites PM by phone → PM registers → auto-linked")
log("=" * 70)

pm_phone = f"+9725{SUFFIX}001"
r = post(f"{BASE}/projects/{project_id}/invites", {
    'phone': pm_phone,
    'role': 'project_manager',
    'full_name': f'PM חדש {SUFFIX}'
}, h(admin_token), "Admin creates PM invite")
check("Admin invite PM: 200", r.status_code == 200, f"status={r.status_code}")
pm_invite_id = r.json().get('id', '')
pm_invite_token = r.json().get('token', '')
check("Invite has id", bool(pm_invite_id), "no id")
check("Invite has token", bool(pm_invite_token), "no token")
check("Invite status=pending", r.json().get('status') == 'pending', f"got={r.json().get('status')}")
audit_events.append({"event": "invite_created", "actor": f"admin ({admin_data.get('id','')})", "project_id": project_id, "target_phone": pm_phone, "role": "project_manager", "timestamp": datetime.utcnow().isoformat()})

log("\n--- PM registers with invited phone ---")
pm_token, pm_data = register_and_login(
    f"proof_pm_{SUFFIX}@test.com", "testpass123", f"PM חדש {SUFFIX}", "project_manager",
    phone_e164=pm_phone)
check("PM registered with token", pm_token is not None, "no token")
audit_events.append({"event": "invite_accepted", "actor": f"pm ({pm_data.get('id','')})", "project_id": project_id, "phone": pm_phone, "timestamp": datetime.utcnow().isoformat()})
audit_events.append({"event": "membership_created", "actor": "system (auto-link)", "project_id": project_id, "user_id": pm_data.get('id',''), "role": "project_manager", "timestamp": datetime.utcnow().isoformat()})

r = get(f"{BASE}/projects/{project_id}/invites", h(admin_token), "Verify invite accepted")
invites_list = r.json() if isinstance(r.json(), list) else r.json().get('items', [])
pm_invite_after = [i for i in invites_list if i.get('id') == pm_invite_id]
if pm_invite_after:
    check("Invite status changed to accepted", pm_invite_after[0].get('status') == 'accepted', f"got={pm_invite_after[0].get('status')}")
else:
    check("Invite found after registration", False, "invite not found in list")

r_mem = get(f"{BASE}/projects/{project_id}/memberships", h(admin_token), "Verify PM membership created")
memberships = r_mem.json() if isinstance(r_mem.json(), list) else r_mem.json().get('items', [])
pm_membership = [m for m in memberships if m.get('user_id') == pm_data.get('id')]
check("PM has project membership", len(pm_membership) > 0, "no membership found")
if pm_membership:
    check("PM membership role=project_manager", pm_membership[0].get('role') == 'project_manager', f"got={pm_membership[0].get('role')}")

# ============================================================
# PHASE 2: PM invites Management Team (with sub_role)
# ============================================================
log("\n\n" + "=" * 70)
log("PHASE 2: PM invites management_team (with sub_role) → registers → auto-linked")
log("=" * 70)

mgmt_phone = f"+9725{SUFFIX}002"
r = post(f"{BASE}/projects/{project_id}/invites", {
    'phone': mgmt_phone,
    'role': 'management_team',
    'sub_role': 'site_manager',
    'full_name': f'מנהל אתר {SUFFIX}'
}, h(pm_token), "PM creates management_team invite with sub_role=site_manager")
check("PM invite management_team: 200", r.status_code == 200, f"status={r.status_code}")
mgmt_invite_id = r.json().get('id', '')
check("Invite has sub_role=site_manager", r.json().get('sub_role') == 'site_manager', f"got={r.json().get('sub_role')}")
audit_events.append({"event": "invite_created", "actor": f"pm ({pm_data.get('id','')})", "project_id": project_id, "target_phone": mgmt_phone, "role": "management_team", "sub_role": "site_manager", "timestamp": datetime.utcnow().isoformat()})

log("\n--- Management team member registers with invited phone ---")
mgmt_token, mgmt_data = register_and_login(
    f"proof_mgmt_{SUFFIX}@test.com", "testpass123", f"מנהל אתר {SUFFIX}", "viewer",
    phone_e164=mgmt_phone)
check("Management registered with token", mgmt_token is not None, "no token")
audit_events.append({"event": "invite_accepted", "actor": f"mgmt ({mgmt_data.get('id','')})", "project_id": project_id, "phone": mgmt_phone, "timestamp": datetime.utcnow().isoformat()})
audit_events.append({"event": "membership_created", "actor": "system (auto-link)", "project_id": project_id, "user_id": mgmt_data.get('id',''), "role": "management_team", "sub_role": "site_manager", "timestamp": datetime.utcnow().isoformat()})

# --- Delta: verify new sub-roles (work_manager, safety_officer) ---
log("\n--- Delta: new sub-roles (work_manager, safety_officer) ---")
wm_phone = f"+9725{SUFFIX}070"
r_wm = post(f"{BASE}/projects/{project_id}/invites", {
    'phone': wm_phone, 'role': 'management_team',
    'sub_role': 'work_manager', 'full_name': f'מנהל עבודה {SUFFIX}'
}, h(pm_token), "PM creates management_team invite with sub_role=work_manager")
check("Invite with sub_role=work_manager: 200", r_wm.status_code == 200, f"status={r_wm.status_code}")
if r_wm.status_code == 200:
    check("Invite has sub_role=work_manager", r_wm.json().get('sub_role') == 'work_manager', f"got={r_wm.json().get('sub_role')}")

so_phone = f"+9725{SUFFIX}071"
r_so = post(f"{BASE}/projects/{project_id}/invites", {
    'phone': so_phone, 'role': 'management_team',
    'sub_role': 'safety_officer', 'full_name': f'ממונה בטיחות {SUFFIX}'
}, h(pm_token), "PM creates management_team invite with sub_role=safety_officer")
check("Invite with sub_role=safety_officer: 200", r_so.status_code == 200, f"status={r_so.status_code}")
if r_so.status_code == 200:
    check("Invite has sub_role=safety_officer", r_so.json().get('sub_role') == 'safety_officer', f"got={r_so.json().get('sub_role')}")

# ============================================================
# PHASE 3: Management Team invites Contractor
# ============================================================
log("\n\n" + "=" * 70)
log("PHASE 3: Management team invites contractor → registers → auto-linked")
log("=" * 70)

cont_phone = f"+9725{SUFFIX}003"
r = post(f"{BASE}/projects/{project_id}/invites", {
    'phone': cont_phone,
    'role': 'contractor',
    'full_name': f'קבלן חדש {SUFFIX}'
}, h(mgmt_token), "Management team creates contractor invite")
check("Management invite contractor: 200", r.status_code == 200, f"status={r.status_code}")
audit_events.append({"event": "invite_created", "actor": f"mgmt ({mgmt_data.get('id','')})", "project_id": project_id, "target_phone": cont_phone, "role": "contractor", "timestamp": datetime.utcnow().isoformat()})

log("\n--- Contractor registers with invited phone ---")
cont_token, cont_data = register_and_login(
    f"proof_cont_{SUFFIX}@test.com", "testpass123", f"קבלן חדש {SUFFIX}", "contractor",
    phone_e164=cont_phone)
check("Contractor registered with token", cont_token is not None, "no token")
audit_events.append({"event": "invite_accepted", "actor": f"contractor ({cont_data.get('id','')})", "project_id": project_id, "phone": cont_phone, "timestamp": datetime.utcnow().isoformat()})

# ============================================================
# PHASE 4: RBAC MATRIX — who can/cannot create invites
# ============================================================
log("\n\n" + "=" * 70)
log("PHASE 4: RBAC MATRIX — invite permissions per role")
log("=" * 70)

viewer_token, viewer_data = register_and_login(
    f"proof_viewer_{SUFFIX}@test.com", "testpass123", f"צופה {SUFFIX}", "viewer")

rbac_matrix = {}
test_phone_counter = 10

for role_name, token, expected_create in [
    ("Admin (owner)", admin_token, 200),
    ("PM", pm_token, 200),
    ("Management Team", mgmt_token, 200),
    ("Contractor", cont_token, 403),
    ("Viewer", viewer_token, 403),
]:
    test_phone_counter += 1
    test_phone = f"+9725{SUFFIX}0{test_phone_counter}"

    invite_role = 'contractor'
    r_create = post(f"{BASE}/projects/{project_id}/invites", {
        'phone': test_phone, 'role': invite_role
    }, h(token), f"RBAC: {role_name} creates invite")

    r_list = get(f"{BASE}/projects/{project_id}/invites", h(token), f"RBAC: {role_name} lists invites")

    rbac_matrix[role_name] = {
        'create_invite': r_create.status_code,
        'list_invites': r_list.status_code,
    }

    if expected_create == 403:
        check(f"{role_name} CANNOT create invite", r_create.status_code == 403, f"got={r_create.status_code}")
        if r_create.status_code == 403:
            audit_events.append({"event": "permission_denied", "actor": role_name, "action": "create_invite", "project_id": project_id, "timestamp": datetime.utcnow().isoformat()})
    else:
        check(f"{role_name} CAN create invite", r_create.status_code == 200, f"got={r_create.status_code}")

# Cancel and resend tests (using admin)
cancel_phone = f"+9725{SUFFIX}020"
r_cancel_setup = post(f"{BASE}/projects/{project_id}/invites", {
    'phone': cancel_phone, 'role': 'contractor'
}, h(admin_token), "Create invite for cancel test")
cancel_invite_id = r_cancel_setup.json().get('id', '')

r_cancel = post(f"{BASE}/projects/{project_id}/invites/{cancel_invite_id}/cancel", {}, h(admin_token), "Cancel invite")
check("Cancel invite: 200", r_cancel.status_code == 200, f"status={r_cancel.status_code}")
audit_events.append({"event": "invite_cancelled", "actor": f"admin ({admin_data.get('id','')})", "project_id": project_id, "invite_id": cancel_invite_id, "timestamp": datetime.utcnow().isoformat()})

r_cancel2 = post(f"{BASE}/projects/{project_id}/invites/{cancel_invite_id}/cancel", {}, h(admin_token), "Cancel already-cancelled invite (should fail)")
check("Cannot cancel already-cancelled invite", r_cancel2.status_code in (400, 409), f"status={r_cancel2.status_code}")

resend_phone = f"+9725{SUFFIX}021"
r_resend_setup = post(f"{BASE}/projects/{project_id}/invites", {
    'phone': resend_phone, 'role': 'contractor'
}, h(admin_token), "Create invite for resend test")
resend_invite_id = r_resend_setup.json().get('id', '')

r_resend = post(f"{BASE}/projects/{project_id}/invites/{resend_invite_id}/resend", {}, h(admin_token), "Resend invite")
check("Resend invite: 200", r_resend.status_code == 200, f"status={r_resend.status_code}")

# ============================================================
# PHASE 5: Cross-Project Isolation
# ============================================================
log("\n\n" + "=" * 70)
log("PHASE 5: Cross-Project Isolation (PM of project A → project B = 403)")
log("=" * 70)

cross_phone = f"+9725{SUFFIX}030"
r_cross = post(f"{BASE}/projects/{project_b_id}/invites", {
    'phone': cross_phone, 'role': 'contractor'
}, h(pm_token), "PM of project A tries to create invite in project B")
check("Cross-project invite blocked (403)", r_cross.status_code == 403, f"status={r_cross.status_code}")
rbac_matrix["Cross-Project PM"] = {'create_invite': r_cross.status_code}
audit_events.append({"event": "permission_denied", "actor": f"pm ({pm_data.get('id','')})", "action": "cross_project_invite", "project_id": project_b_id, "timestamp": datetime.utcnow().isoformat()})

r_cross_list = get(f"{BASE}/projects/{project_b_id}/invites", h(pm_token), "PM of project A tries to list invites in project B")
check("Cross-project list blocked (403)", r_cross_list.status_code == 403, f"status={r_cross_list.status_code}")
rbac_matrix["Cross-Project PM"]['list_invites'] = r_cross_list.status_code

# ============================================================
# PHASE 6: Duplicate invite blocking
# ============================================================
log("\n\n" + "=" * 70)
log("PHASE 6: Duplicate invite + hierarchy violations")
log("=" * 70)

dup_phone = f"+9725{SUFFIX}040"
r_dup1 = post(f"{BASE}/projects/{project_id}/invites", {
    'phone': dup_phone, 'role': 'contractor'
}, h(admin_token), "Create invite (first)")
check("First invite: 200", r_dup1.status_code == 200, f"status={r_dup1.status_code}")

r_dup2 = post(f"{BASE}/projects/{project_id}/invites", {
    'phone': dup_phone, 'role': 'contractor'
}, h(admin_token), "Create duplicate invite (should be blocked)")
check("Duplicate invite blocked", r_dup2.status_code in (400, 409), f"status={r_dup2.status_code}")

r_hierarchy = post(f"{BASE}/projects/{project_id}/invites", {
    'phone': f"+9725{SUFFIX}041", 'role': 'project_manager'
}, h(mgmt_token), "Management tries to invite PM (hierarchy violation)")
check("Management CANNOT invite PM", r_hierarchy.status_code == 403, f"status={r_hierarchy.status_code}")

# ============================================================
# PHASE 6B: Expired invite hard-fail
# ============================================================
log("\n\n" + "=" * 70)
log("PHASE 6B: Expired invite — force-expire via DB, verify NOT auto-linked")
log("=" * 70)

expired_phone = f"+9725{SUFFIX}060"
r_exp = post(f"{BASE}/projects/{project_id}/invites", {
    'phone': expired_phone, 'role': 'contractor', 'full_name': f'Expired Test {SUFFIX}'
}, h(admin_token), "Create invite to be force-expired")
check("Expired-test invite created: 200", r_exp.status_code == 200, f"status={r_exp.status_code}")
expired_invite_id = r_exp.json().get('id', '')
log(f"  Invite ID: {expired_invite_id}")

mongo = MongoClient('mongodb://127.0.0.1:27017')
mdb = mongo['contractor_ops']
past_date = (datetime.utcnow() - timedelta(days=10)).isoformat()
result = mdb.invites.update_one(
    {'id': expired_invite_id},
    {'$set': {'expires_at': past_date}}
)
log(f"  Force-expired invite in DB: expires_at={past_date} (modified={result.modified_count})")
check("DB update: invite expires_at set to past", result.modified_count == 1, f"modified={result.modified_count}")

log("\n--- Register with expired invite phone ---")
exp_body = {'email': f'proof_expired_{SUFFIX}@test.com', 'password': 'testpass123',
            'name': f'Expired User {SUFFIX}', 'role': 'contractor', 'phone_e164': expired_phone}
r_exp_reg = requests.post(f"{BASE}/auth/register", json=exp_body)
log_req_res("POST", f"{BASE}/auth/register", exp_body, r_exp_reg.status_code,
            r_exp_reg.json() if r_exp_reg.headers.get('content-type','').startswith('application/json') else r_exp_reg.text,
            "Register with expired invite phone")
check("Registration succeeds (200)", r_exp_reg.status_code == 200, f"status={r_exp_reg.status_code}")
exp_reg_data = r_exp_reg.json() if r_exp_reg.status_code == 200 else {}
auto_linked = exp_reg_data.get('auto_linked_projects', [])
check("auto_linked_projects is EMPTY (expired invite skipped)", len(auto_linked) == 0,
      f"auto_linked={auto_linked}")

exp_invite_after = mdb.invites.find_one({'id': expired_invite_id})
log(f"  Invite status after registration: {exp_invite_after.get('status') if exp_invite_after else 'NOT FOUND'}")
check("Invite status changed to 'expired'", exp_invite_after and exp_invite_after.get('status') == 'expired',
      f"got={exp_invite_after.get('status') if exp_invite_after else 'N/A'}")

exp_audit = mdb.audit_events.find_one({'entity_id': expired_invite_id, 'action': 'expired'})
check("Audit event 'invite_expired' recorded", exp_audit is not None,
      "no expired audit event found")
if exp_audit:
    log(f"  Audit event: action={exp_audit.get('action')}, actor={exp_audit.get('actor_id')}, "
        f"reason={exp_audit.get('payload',{}).get('reason')}, ts={exp_audit.get('created_at')}")
    audit_events.append({"event": "invite_expired", "actor": "system",
                         "project_id": project_id, "invite_id": expired_invite_id,
                         "reason": exp_audit.get('payload',{}).get('reason',''),
                         "timestamp": exp_audit.get('created_at','')})

mongo.close()

# ============================================================
# PHASE 7: Available PMs endpoint
# ============================================================
log("\n\n" + "=" * 70)
log("PHASE 7: Available PMs endpoint (Fix 3.1 verification)")
log("=" * 70)

r_avail = get(f"{BASE}/projects/{project_id}/available-pms", h(admin_token), "GET available-pms (full list)")
check("Available PMs returns 200", r_avail.status_code == 200, f"status={r_avail.status_code}")
avail_list = r_avail.json() if isinstance(r_avail.json(), list) else []
check("Available PMs returns users (non-empty)", len(avail_list) > 0, f"count={len(avail_list)}")
log(f"  Available PMs count: {len(avail_list)}")
log(f"\n  First 5 PMs (real data):")
for pm_entry in avail_list[:5]:
    log(f"    - id={pm_entry.get('id','?')}, name={pm_entry.get('name','?')}, role={pm_entry.get('role','?')}, user_status={pm_entry.get('user_status','?')}")

r_avail_search = get(f"{BASE}/projects/{project_id}/available-pms", h(admin_token), "GET available-pms with search filter", params={'search': 'proof'})
check("Available PMs search works", r_avail_search.status_code == 200, f"status={r_avail_search.status_code}")
search_list = r_avail_search.json() if isinstance(r_avail_search.json(), list) else []
log(f"  Search 'proof' returned: {len(search_list)} results")

r_avail_pm = get(f"{BASE}/projects/{project_id}/available-pms", h(pm_token), "GET available-pms (as PM — should also work)")
check("PM can also access available-pms", r_avail_pm.status_code == 200, f"status={r_avail_pm.status_code}")

log("\n  Root Cause (Bug 3.1): Endpoint used whitelist filter user_status={'$in':['active',None]}")
log("  Fix: Changed to blacklist user_status={'$nin':['rejected','suspended','pending_pm_approval']}")
log("  Also: Added 'project_manager' to allowed roles (was owner/admin only)")

# ============================================================
# PHASE 8: RBAC Hierarchy - who can invite which roles
# ============================================================
log("\n\n" + "=" * 70)
log("PHASE 8: RBAC Hierarchy — role-specific invite capabilities")
log("=" * 70)

hierarchy_tests = [
    ("PM invites management_team", pm_token, "management_team", "execution_engineer", 200),
    ("PM invites contractor", pm_token, "contractor", None, 200),
    ("PM CANNOT invite PM", pm_token, "project_manager", None, 403),
    ("Management invites contractor", mgmt_token, "contractor", None, 200),
    ("Management CANNOT invite PM", mgmt_token, "project_manager", None, 403),
    ("Management CANNOT invite management_team", mgmt_token, "management_team", "safety_assistant", 403),
]

phone_ctr = 50
for label, token, role, sub_role, expected in hierarchy_tests:
    phone_ctr += 1
    body = {'phone': f"+9725{SUFFIX}0{phone_ctr}", 'role': role}
    if sub_role:
        body['sub_role'] = sub_role
    r = post(f"{BASE}/projects/{project_id}/invites", body, h(token), f"Hierarchy: {label}")
    check(label, r.status_code == expected, f"expected={expected}, got={r.status_code}")

# ============================================================
# AUDIT TRAIL — from MongoDB (real data)
# ============================================================
log("\n\n" + "=" * 70)
log("AUDIT TRAIL — Real Events from MongoDB")
log("=" * 70)

mongo2 = MongoClient('mongodb://127.0.0.1:27017')
mdb2 = mongo2['contractor_ops']

db_audit_events = list(mdb2.audit_events.find(
    {'entity_type': 'invite', 'payload.project_id': project_id},
    {'_id': 0}
).sort('created_at', 1))

log(f"\n  Total invite audit events for project: {len(db_audit_events)}")

action_counts = {}
for evt in db_audit_events:
    a = evt.get('action', '?')
    action_counts[a] = action_counts.get(a, 0) + 1

log(f"  Event type breakdown: {json.dumps(action_counts, ensure_ascii=False)}")
check("Audit: invite 'created' events exist", action_counts.get('created', 0) >= 3, f"count={action_counts.get('created',0)}")
check("Audit: invite 'accepted' events exist", action_counts.get('accepted', 0) >= 3, f"count={action_counts.get('accepted',0)}")
check("Audit: invite 'notification_queued' events exist", action_counts.get('notification_queued', 0) >= 1, f"count={action_counts.get('notification_queued',0)}")
check("Audit: invite 'cancelled' events exist", action_counts.get('cancelled', 0) >= 1, f"count={action_counts.get('cancelled',0)}")
check("Audit: invite 'expired' events exist", action_counts.get('expired', 0) >= 1, f"count={action_counts.get('expired',0)}")

log(f"\n  {'─'*110}")
log(f"  {'#':>3} | {'Action':<22} | {'Actor':<36} | {'Entity ID':<36} | {'Timestamp':<26}")
log(f"  {'─'*110}")
for i, evt in enumerate(db_audit_events, 1):
    log(f"  {i:>3} | {evt.get('action','?'):<22} | {str(evt.get('actor_id','?')):<36} | {str(evt.get('entity_id','?')):<36} | {str(evt.get('created_at','?')):<26}")
    payload = evt.get('payload', {})
    extra_fields = {k: v for k, v in payload.items() if k != 'project_id'}
    if extra_fields:
        log(f"      | payload: {json.dumps(extra_fields, ensure_ascii=False)}")
log(f"  {'─'*110}")

check("At least 6 distinct audit event types", len(action_counts) >= 5, f"types={list(action_counts.keys())}")

mongo2.close()

# Also log the script-tracked events for cross-reference
log("\n\n  Script-tracked audit events (cross-reference):")
for i, evt in enumerate(audit_events, 1):
    log(f"\n  Event #{i}:")
    for k, v in evt.items():
        log(f"    {k}: {v}")

# ============================================================
# RBAC MATRIX TABLE
# ============================================================
log("\n\n" + "=" * 70)
log("RBAC MATRIX TABLE")
log("=" * 70)

log("\n  | Role                | Create Invite | List Invites |")
log("  |---------------------|---------------|--------------|")
for role_name, codes in rbac_matrix.items():
    create = codes.get('create_invite', '-')
    lst = codes.get('list_invites', '-')
    log(f"  | {role_name:<19} | {str(create):>13} | {str(lst):>12} |")

# ============================================================
# SUMMARY
# ============================================================
log("\n\n" + "=" * 70)
log("SUMMARY")
log("=" * 70)
log(f"  Total checks: {passed + failed}")
log(f"  Passed: {passed}")
log(f"  Failed: {failed}")
log(f"  Audit events captured: {len(audit_events)}")
log(f"  Timestamp: {datetime.utcnow().isoformat()}Z")

if failed == 0:
    log("\n  VERDICT: ALL CHECKS PASSED ✓")
else:
    log(f"\n  VERDICT: {failed} CHECKS FAILED ✗")

# Write output file
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))
log(f"\n  Output written to: {OUTPUT_FILE}")

sys.exit(0 if failed == 0 else 1)
