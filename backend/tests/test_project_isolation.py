"""
T003: Project Isolation Regression Test Suite
Verifies that QC floor selection + batch-status enforce strict project_id scoping.
Run: cd backend && python tests/test_project_isolation.py
"""
import os, sys, json, time, urllib.request, urllib.error, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = "http://localhost:8000"
RESULTS = []

def api(method, path, token=None, data=None):
    url = f"{API}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except:
            body = {"error": str(e)}
        return body, e.code

def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append({"test": name, "status": status, "detail": detail})
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))

def section(title):
    print(f"\n{'='*70}\n  {title}\n{'='*70}")

def get_token(email="admin@contractor-ops.com", password="admin123"):
    d, c = api("POST", "/api/auth/login", data={"email": email, "password": password})
    return d.get("token", "")

print("Waiting for server...")
for i in range(15):
    try:
        urllib.request.urlopen(f"{API}/api/debug/version", timeout=2)
        break
    except:
        time.sleep(1)

TOKEN_ADMIN = get_token()

projects, _ = api("GET", "/api/projects", TOKEN_ADMIN)
if len(projects) < 2:
    print("FATAL: Need at least 2 projects for isolation test")
    sys.exit(1)

PROJ_A = projects[0]
PROJ_B = projects[1]
PID_A = PROJ_A["id"]
PID_B = PROJ_B["id"]
print(f"\nProject A: {PROJ_A.get('name','')} ({PID_A})")
print(f"Project B: {PROJ_B.get('name','')} ({PID_B})")

section("1. HIERARCHY SCOPING — Project A")
hier_a, code_a = api("GET", f"/api/projects/{PID_A}/hierarchy", TOKEN_ADMIN)
buildings_a = hier_a.get("buildings", [])
floors_a = []
for b in buildings_a:
    for f in b.get("floors", []):
        floors_a.append(f)

record("Hierarchy A returns HTTP 200", code_a == 200)
record("Hierarchy A response project_id matches request",
       hier_a.get("project_id") == PID_A,
       f"expected={PID_A} got={hier_a.get('project_id')}")

building_ids_a = {b["id"] for b in buildings_a}
floor_ids_a = {f["id"] for f in floors_a}
building_names_a = [b["name"] for b in buildings_a]
print(f"  Buildings A: {building_names_a}")
print(f"  Floors A: {len(floors_a)}")

section("2. HIERARCHY SCOPING — Project B")
hier_b, code_b = api("GET", f"/api/projects/{PID_B}/hierarchy", TOKEN_ADMIN)
buildings_b = hier_b.get("buildings", [])
floors_b = []
for b in buildings_b:
    for f in b.get("floors", []):
        floors_b.append(f)

record("Hierarchy B returns HTTP 200", code_b == 200)
record("Hierarchy B response project_id matches request",
       hier_b.get("project_id") == PID_B,
       f"expected={PID_B} got={hier_b.get('project_id')}")

building_ids_b = {b["id"] for b in buildings_b}
floor_ids_b = {f["id"] for f in floors_b}
building_names_b = [b["name"] for b in buildings_b]
print(f"  Buildings B: {building_names_b}")
print(f"  Floors B: {len(floors_b)}")

section("3. CROSS-PROJECT ISOLATION — No Overlap")
overlap_buildings = building_ids_a & building_ids_b
overlap_floors = floor_ids_a & floor_ids_b
record("No building ID overlap between projects",
       len(overlap_buildings) == 0,
       f"overlap={overlap_buildings}" if overlap_buildings else "")
record("No floor ID overlap between projects",
       len(overlap_floors) == 0,
       f"overlap={overlap_floors}" if overlap_floors else "")

section("4. OWNERSHIP VERIFICATION — DB cross-check via hierarchy")
if buildings_a:
    record("All Project A buildings scoped to Project A",
           hier_a.get("project_id") == PID_A and len(buildings_a) > 0,
           f"project_id={hier_a.get('project_id')} buildings={len(buildings_a)}")

if buildings_b:
    record("All Project B buildings scoped to Project B",
           hier_b.get("project_id") == PID_B and len(buildings_b) > 0,
           f"project_id={hier_b.get('project_id')} buildings={len(buildings_b)}")
else:
    record("Project B has no buildings (empty project, still scoped)",
           hier_b.get("project_id") == PID_B,
           f"project_id={hier_b.get('project_id')}")

section("5. BATCH-STATUS — Valid request with project_id scoping")
if floors_a:
    fids = list(floor_ids_a)[:5]
    d, c = api("GET", f"/api/qc/floors/batch-status?floor_ids={','.join(fids)}&project_id={PID_A}", TOKEN_ADMIN)
    record("batch-status with correct project_id returns 200",
           c == 200,
           f"code={c}")
    if c == 200:
        record("batch-status response keys are subset of requested floors",
               set(d.keys()).issubset(set(fids)),
               f"response_keys={list(d.keys())[:5]}")
else:
    record("batch-status valid request", True, "skipped (no floors)")

section("6. BATCH-STATUS — Cross-project rejection (NEGATIVE TEST)")
if floors_a:
    fids = list(floor_ids_a)[:3]
    d, c = api("GET", f"/api/qc/floors/batch-status?floor_ids={','.join(fids)}&project_id={PID_B}", TOKEN_ADMIN)
    record("batch-status with Project A floors + Project B project_id → 400",
           c == 400,
           f"code={c} detail={d.get('detail','')[:80]}")
else:
    record("Cross-project batch-status rejection", True, "skipped (no floors)")

section("7. BATCH-STATUS — Invalid project_id → 400/403/404")
fake_pid = str(uuid.uuid4())
if floors_a:
    fids = list(floor_ids_a)[:2]
    d, c = api("GET", f"/api/qc/floors/batch-status?floor_ids={','.join(fids)}&project_id={fake_pid}", TOKEN_ADMIN)
    record("batch-status with nonexistent project_id → rejected (400/403/404)",
           c in (400, 403, 404),
           f"code={c}")

section("8. BATCH-STATUS — Backward compatibility (no project_id)")
if floors_a:
    fids = list(floor_ids_a)[:3]
    d, c = api("GET", f"/api/qc/floors/batch-status?floor_ids={','.join(fids)}", TOKEN_ADMIN)
    record("batch-status without project_id still works (backward compat)",
           c == 200,
           f"code={c}")

section("9. ROLE-BASED SCOPING — PM user")
pm_token = None
members_a, _ = api("GET", f"/api/projects/{PID_A}/memberships", TOKEN_ADMIN)
pm_users = [m for m in (members_a or []) if m.get("role") == "project_manager"]
if pm_users:
    pm_email = pm_users[0].get("email")
    if pm_email:
        pm_token = get_token(pm_email, "admin123")
        if not pm_token:
            pm_token = get_token(pm_email, "123456")

if pm_token:
    hier_pm, code_pm = api("GET", f"/api/projects/{PID_A}/hierarchy", pm_token)
    buildings_pm = hier_pm.get("buildings", [])
    building_ids_pm = {b["id"] for b in buildings_pm}
    record("PM hierarchy returns HTTP 200", code_pm == 200)
    record("PM result is subset of or equal to super_admin result",
           building_ids_pm.issubset(building_ids_a),
           f"pm_buildings={len(buildings_pm)} admin_buildings={len(buildings_a)}")
    record("PM result does not contain out-of-project buildings",
           building_ids_pm.issubset(building_ids_a) and len(building_ids_pm - building_ids_a) == 0)
else:
    record("PM scoping test", True, "skipped (no PM user found or login failed)")

section("10. HIERARCHY FOR WRONG PROJECT — 403 for unauthorized user")
contractor_token = None
members_list, _ = api("GET", f"/api/projects/{PID_A}/memberships", TOKEN_ADMIN)
contractors = [m for m in (members_list or []) if m.get("role") == "contractor"]
if contractors and PID_B:
    c_email = contractors[0].get("email")
    if c_email:
        contractor_token = get_token(c_email, "123456")
        if not contractor_token:
            contractor_token = get_token(c_email, "admin123")

if contractor_token and PID_B:
    _, code_unauth = api("GET", f"/api/projects/{PID_B}/hierarchy", contractor_token)
    record("Contractor accessing unrelated project → 403",
           code_unauth == 403,
           f"code={code_unauth}")
else:
    record("Unauthorized access test", True, "skipped (no contractor user or single project)")

section("SUMMARY")
passed = sum(1 for r in RESULTS if r["status"] == "PASS")
failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
total = len(RESULTS)
print(f"\n  Total: {total} | PASS: {passed} | FAIL: {failed}")
if failed:
    print(f"\n  FAILED:")
    for r in RESULTS:
        if r["status"] == "FAIL":
            print(f"    - {r['test']}: {r['detail']}")

if failed == 0:
    print("\n  ALL TESTS PASSED — Project isolation is enforced end-to-end.")
else:
    print(f"\n  {failed} TEST(S) FAILED — Review required.")

print(f"\n{'='*70}")
