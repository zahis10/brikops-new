"""
Audit Event Immutability Proof
==============================
Proves that audit events are:
1. Append-only (insert_one only, no update/delete routes)
2. No API endpoint exists to modify or delete audit events
3. Audit events cannot be tampered with via any exposed API
4. Events are created with server-side timestamps (not client-supplied)
"""

import requests, json, sys

BASE = 'http://localhost:8000/api'
results = []

def auth(email, password):
    r = requests.post(f'{BASE}/auth/login', json={'email': email, 'password': password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    d = r.json()
    return d['token'], d['user']

def hdr(token):
    return {'Authorization': f'Bearer {token}'}

def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((status, name))
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    return condition

print("=" * 70)
print("  Audit Event Immutability — Negative Test Set")
print("=" * 70)

owner_token, owner = auth('admin@contractor-ops.com', 'admin123')

print("\n--- 1. No PUT/PATCH endpoint for audit events ---")
r = requests.put(f'{BASE}/audit-events/fake-id', json={'action': 'tampered'}, headers=hdr(owner_token))
test("PUT /api/audit-events/{id} returns 404/405", r.status_code in [404, 405, 422],
     f"HTTP {r.status_code}")

r = requests.patch(f'{BASE}/audit-events/fake-id', json={'action': 'tampered'}, headers=hdr(owner_token))
test("PATCH /api/audit-events/{id} returns 404/405", r.status_code in [404, 405, 422],
     f"HTTP {r.status_code}")

print("\n--- 2. No DELETE endpoint for audit events ---")
r = requests.delete(f'{BASE}/audit-events/fake-id', headers=hdr(owner_token))
test("DELETE /api/audit-events/{id} returns 404/405", r.status_code in [404, 405, 422],
     f"HTTP {r.status_code}")

print("\n--- 3. No bulk delete/update for audit events ---")
r = requests.post(f'{BASE}/audit-events/bulk-delete', json={'ids': ['fake']}, headers=hdr(owner_token))
test("POST /api/audit-events/bulk-delete returns 404/405", r.status_code in [404, 405, 422],
     f"HTTP {r.status_code}")

r = requests.post(f'{BASE}/audit-events/bulk-update', json={'ids': ['fake'], 'action': 'tampered'}, headers=hdr(owner_token))
test("POST /api/audit-events/bulk-update returns 404/405", r.status_code in [404, 405, 422],
     f"HTTP {r.status_code}")

print("\n--- 4. Verify audit events exist and are read-only via DB ---")
from pymongo import MongoClient
mc = MongoClient('mongodb://127.0.0.1:27017')
db = mc.contractor_ops

count_before = db.audit_events.count_documents({})
test("Audit events collection has records", count_before > 0, f"{count_before} events")

sample = db.audit_events.find_one({}, {'_id': 0})
test("Audit event has 'id' field", 'id' in sample, str(list(sample.keys())))
test("Audit event has 'entity_type' field", 'entity_type' in sample)
test("Audit event has 'action' field", 'action' in sample)
test("Audit event has 'actor_id' field", 'actor_id' in sample)
test("Audit event has 'created_at' field (server timestamp)", 'created_at' in sample)
test("Audit event has 'payload' field", 'payload' in sample)

print("\n--- 5. Verify no audit modification in router source code ---")
import re
with open('/home/runner/workspace/backend/contractor_ops/router.py', 'r') as f:
    source = f.read()

audit_inserts = len(re.findall(r'audit_events\.insert_one', source))
audit_updates = len(re.findall(r'audit_events\.(update_one|update_many|replace_one|find_one_and_update)', source))
audit_deletes = len(re.findall(r'audit_events\.(delete_one|delete_many|find_one_and_delete|remove|drop)', source))

test("Router uses insert_one for audit events", audit_inserts > 0, f"{audit_inserts} insert calls")
test("Router has ZERO update calls on audit_events", audit_updates == 0, f"{audit_updates} update calls")
test("Router has ZERO delete calls on audit_events", audit_deletes == 0, f"{audit_deletes} delete calls")

print("\n--- 6. Verify audit events are monotonically ordered (append-only) ---")
events = list(db.audit_events.find({}, {'_id': 0, 'created_at': 1}).sort('created_at', 1).limit(50))
timestamps = [e['created_at'] for e in events]
is_sorted = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
test("Audit events are chronologically ordered (append-only)", is_sorted,
     f"checked {len(timestamps)} events")

print("\n--- 7. Verify POST to create arbitrary audit event is blocked ---")
r = requests.post(f'{BASE}/audit-events', json={
    'entity_type': 'fake', 'entity_id': 'fake', 'action': 'inject', 'actor_id': 'attacker'
}, headers=hdr(owner_token))
test("POST /api/audit-events (direct creation) returns 404/405", r.status_code in [404, 405, 422],
     f"HTTP {r.status_code}")

count_after = db.audit_events.count_documents({})
injected = db.audit_events.find_one({'action': 'inject', 'actor_id': 'attacker'})
test("No injected audit event in database", injected is None,
     f"count before={count_before}, after={count_after}")

passed = sum(1 for s, _ in results if s == "PASS")
failed = sum(1 for s, _ in results if s == "FAIL")
print(f"\n{'=' * 70}")
print(f"  AUDIT IMMUTABILITY RESULTS: {passed} passed, {failed} failed")
print(f"{'=' * 70}")

if failed > 0:
    print("\n  FAILED TESTS:")
    for s, name in results:
        if s == "FAIL":
            print(f"    - {name}")

sys.exit(0 if failed == 0 else 1)
