"""
Cross-Project RBAC Bypass Negative Test Set
============================================
Proves project isolation:
1. User with role in Project A cannot access Project B tasks
2. management_team membership doesn't cross projects
3. Contractor in Project A cannot submit proof for Project B task
4. PM of Project A cannot approve tasks in Project B
"""

import requests, json, io, struct, zlib, sys

BASE = 'http://localhost:8000/api'
results = []

def auth(email, password):
    r = requests.post(f'{BASE}/auth/login', json={'email': email, 'password': password})
    assert r.status_code == 200, f"Login failed for {email}: {r.text}"
    d = r.json()
    return d['token'], d['user']

def hdr(token):
    return {'Authorization': f'Bearer {token}'}

def make_png():
    raw = b'\x00\xff\x00\x00'
    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    def chunk(ct, d):
        c = ct + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')

def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((status, name))
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    return condition

print("=" * 70)
print("  Cross-Project RBAC Bypass — Negative Test Set")
print("=" * 70)

print("\n--- Setup: Create two isolated projects ---")

import time
unique = str(int(time.time()))[-6:]

owner_token, owner = auth('admin@contractor-ops.com', 'admin123')
cont_token, cont = auth('contractor1@contractor-ops.com', 'cont123')

r = requests.post(f'{BASE}/projects', json={'name': f'RBAC Test A {unique}', 'code': f'RA{unique}', 'address': 'Test A'}, headers=hdr(owner_token))
assert r.status_code == 200, f"Create project A failed: {r.text}"
project_a = r.json()
pid_a = project_a['id']

r = requests.post(f'{BASE}/projects', json={'name': f'RBAC Test B {unique}', 'code': f'RB{unique}', 'address': 'Test B'}, headers=hdr(owner_token))
assert r.status_code == 200, f"Create project B failed: {r.text}"
project_b = r.json()
pid_b = project_b['id']

r = requests.post(f'{BASE}/projects/{pid_a}/buildings', json={'name': 'Building A1', 'project_id': pid_a}, headers=hdr(owner_token))
assert r.status_code == 200, f"Create building A failed: {r.status_code} {r.text}"
bld_a = r.json()
r = requests.post(f'{BASE}/projects/{pid_b}/buildings', json={'name': 'Building B1', 'project_id': pid_b}, headers=hdr(owner_token))
assert r.status_code == 200, f"Create building B failed: {r.status_code} {r.text}"
bld_b = r.json()

r = requests.post(f'{BASE}/buildings/{bld_a["id"]}/floors', json={'name': '1', 'kind': 'residential'}, headers=hdr(owner_token))
assert r.status_code == 200, f"Create floor A failed: {r.status_code} {r.text}"
flr_a = r.json()
r = requests.post(f'{BASE}/buildings/{bld_b["id"]}/floors', json={'name': '1', 'kind': 'residential'}, headers=hdr(owner_token))
assert r.status_code == 200, f"Create floor B failed: {r.status_code} {r.text}"
flr_b = r.json()

r = requests.post(f'{BASE}/floors/{flr_a["id"]}/units', json={'unit_no': 'A-101'}, headers=hdr(owner_token))
assert r.status_code == 200, f"Create unit A failed: {r.status_code} {r.text}"
unit_a = r.json()
r = requests.post(f'{BASE}/floors/{flr_b["id"]}/units', json={'unit_no': 'B-101'}, headers=hdr(owner_token))
assert r.status_code == 200, f"Create unit B failed: {r.status_code} {r.text}"
unit_b = r.json()

r = requests.post(f'{BASE}/tasks', json={
    'project_id': pid_a, 'building_id': bld_a['id'], 'floor_id': flr_a['id'], 'unit_id': unit_a['id'],
    'title': 'Task in Project A', 'category': 'plumbing', 'priority': 'high',
    'assignee_id': cont['id'],
}, headers=hdr(owner_token))
task_a = r.json()

r = requests.post(f'{BASE}/tasks', json={
    'project_id': pid_b, 'building_id': bld_b['id'], 'floor_id': flr_b['id'], 'unit_id': unit_b['id'],
    'title': 'Task in Project B', 'category': 'electrical', 'priority': 'medium',
}, headers=hdr(owner_token))
task_b = r.json()

requests.post(f'{BASE}/tasks/{task_a["id"]}/status', json={'status': 'in_progress'}, headers=hdr(cont_token))

print(f"  Project A: {pid_a} (task: {task_a['id']})")
print(f"  Project B: {pid_b} (task: {task_b['id']})")

print("\n--- Test 1: Contractor assigned in Project A cannot view Project B tasks ---")
r = requests.get(f'{BASE}/tasks/{task_b["id"]}', headers=hdr(cont_token))
test("Contractor cannot GET task in Project B", r.status_code in [403, 404],
     f"HTTP {r.status_code}")

print("\n--- Test 2: Contractor cannot submit proof for Project B task ---")
png = make_png()
r = requests.post(f'{BASE}/tasks/{task_b["id"]}/contractor-proof',
    files={'file': ('proof.png', io.BytesIO(png), 'image/png')},
    data={'note': 'Cross-project attack'},
    headers=hdr(cont_token))
test("Contractor cannot POST proof to Project B task", r.status_code in [403, 404],
     f"HTTP {r.status_code}")

print("\n--- Test 3: Contractor cannot change status of Project B task ---")
r = requests.post(f'{BASE}/tasks/{task_b["id"]}/status', json={'status': 'in_progress'}, headers=hdr(cont_token))
test("Contractor cannot change status in Project B", r.status_code in [403, 404],
     f"HTTP {r.status_code}")

print("\n--- Test 4: Register a second PM, assign only to Project A ---")
pm2_data = {'email': 'pm2-rbac@test.com', 'password': 'pm2test123', 'name': 'PM2 RBAC Test', 'role': 'project_manager'}
requests.post(f'{BASE}/auth/register', json=pm2_data)
pm2_token, pm2 = auth('pm2-rbac@test.com', 'pm2test123')

r = requests.post(f'{BASE}/projects/{pid_a}/assign-pm', json={'user_id': pm2['id']}, headers=hdr(owner_token))

print("\n--- Test 5: PM of Project A cannot create tasks in Project B ---")
r = requests.post(f'{BASE}/tasks', json={
    'project_id': pid_b, 'building_id': bld_b['id'], 'floor_id': flr_b['id'], 'unit_id': unit_b['id'],
    'title': 'Cross-project task creation attempt', 'category': 'general', 'priority': 'low',
}, headers=hdr(pm2_token))
test("PM of Project A cannot create task in Project B", r.status_code in [403, 404],
     f"HTTP {r.status_code}")

print("\n--- Test 6: PM of Project A cannot approve/reject in Project B ---")
r = requests.post(f'{BASE}/tasks/{task_b["id"]}/manager-decision',
    json={'decision': 'approve'}, headers=hdr(pm2_token))
test("PM of Project A cannot approve in Project B", r.status_code in [403, 404],
     f"HTTP {r.status_code}")

print("\n--- Test 7: management_team membership does NOT cross projects ---")
mgmt_data = {'email': 'mgmt-rbac@test.com', 'password': 'mgmt123', 'name': 'Mgmt RBAC Test', 'role': 'viewer'}
requests.post(f'{BASE}/auth/register', json=mgmt_data)
mgmt_token, mgmt_user = auth('mgmt-rbac@test.com', 'mgmt123')

from pymongo import MongoClient
mc = MongoClient('mongodb://127.0.0.1:27017')
db = mc.contractor_ops
db.project_memberships.insert_one({
    'project_id': pid_a,
    'user_id': mgmt_user['id'],
    'role': 'management_team',
    'sub_role': 'site_manager',
    'created_at': '2026-02-17T00:00:00+00:00',
})

r = requests.post(f'{BASE}/tasks/{task_b["id"]}/manager-decision',
    json={'decision': 'approve'}, headers=hdr(mgmt_token))
test("management_team in Project A cannot approve in Project B", r.status_code in [403, 404],
     f"HTTP {r.status_code}")

print("\n--- Test 8: management_team CAN approve in their own project ---")
task_a_proof = requests.post(f'{BASE}/tasks/{task_a["id"]}/contractor-proof',
    files={'file': ('proof.png', io.BytesIO(make_png()), 'image/png')},
    data={'note': 'Proof for Project A'},
    headers=hdr(cont_token))

r = requests.post(f'{BASE}/tasks/{task_a["id"]}/manager-decision',
    json={'decision': 'approve'}, headers=hdr(mgmt_token))
test("management_team in Project A CAN approve in Project A", r.status_code == 200,
     f"HTTP {r.status_code}")

print("\n--- Test 9: Viewer cannot access any task details cross-project ---")
viewer_token, _ = auth('viewer@contractor-ops.com', 'view123')
r = requests.post(f'{BASE}/tasks/{task_b["id"]}/manager-decision',
    json={'decision': 'approve'}, headers=hdr(viewer_token))
test("Viewer cannot approve any task", r.status_code in [403, 404],
     f"HTTP {r.status_code}")

print("\n--- Test 10: Contractor in Project A cannot add comments to Project B task ---")
r = requests.post(f'{BASE}/tasks/{task_b["id"]}/updates',
    json={'task_id': task_b['id'], 'content': 'Cross-project comment attack', 'update_type': 'comment'},
    headers=hdr(cont_token))
test("Contractor cannot comment on Project B task", r.status_code in [403, 404],
     f"HTTP {r.status_code}")

passed = sum(1 for s, _ in results if s == "PASS")
failed = sum(1 for s, _ in results if s == "FAIL")
print(f"\n{'=' * 70}")
print(f"  CROSS-PROJECT RBAC RESULTS: {passed} passed, {failed} failed")
print(f"{'=' * 70}")

if failed > 0:
    print("\n  FAILED TESTS:")
    for s, name in results:
        if s == "FAIL":
            print(f"    - {name}")

sys.exit(0 if failed == 0 else 1)
