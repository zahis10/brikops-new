# #426 — Batch S6 — Shannon CRITICAL fix (role escalation + 2 IDORs)

## What & Why

**Public-launch blockers.** Shannon (Keygraph) AI pentester scan on 2026-04-26 found 2 CRITICAL vulnerabilities that the previous manual pentest (2026-04-22) missed. **A 3rd identical-pattern bug was also discovered during manual code review of the spec** — included here for atomic deploy.

1. **CRIT-A — Role self-elevation via `/api/auth/register`** — Any unauthenticated person on the internet can POST one request and receive a `project_manager` JWT. The endpoint accepts a client-supplied `role` field with zero server-side restriction. **Verified safe to fix:** the legitimate frontend (`RegisterPage.js`) calls `/api/auth/register-with-phone` and `/api/auth/register-management` — never `/api/auth/register`. The vulnerable endpoint is legacy and unused by the production UI.

2. **CRIT-B — IDOR on `/api/tasks/{task_id}/reopen`** — Once an attacker has any `project_manager` JWT (e.g., self-registered via CRIT-A), they can reopen ANY task in ANY project across the entire platform. The endpoint uses `require_roles('project_manager','management_team')` but skips the per-project membership check that every sibling endpoint correctly performs.

3. **CRIT-C — IDOR on `/api/tasks/{task_id}/attachments`** (discovered during S6 review, NOT in Shannon report) — Same pattern as CRIT-B: any non-viewer authenticated user can upload files to any task in any project. The endpoint at `tasks_router.py:1131` only checks `if user['role'] == 'viewer'` (line 1142) — no project membership check. Coverage audit of all 11 mutation endpoints in `tasks_router.py` revealed exactly 2 endpoints lack membership checks: `/reopen` (CRIT-B above) and `/attachments` (CRIT-C). Adding both fixes in one batch closes the same root cause.

**Combined attack chain:**
```
1. Internet attacker → POST /api/auth/register {"role":"project_manager"}
   → 200 OK, here's your 30-day PM JWT
2. Attacker → POST /api/tasks/{ANY_TASK_ID}/reopen
   → 200 OK, task reopened, DB write confirmed
```

This is the highest-impact attack path Shannon found. With the app already in the air (no customers yet), these MUST ship before any public marketing or customer onboarding.

**Same framing as S1/S2/S5a/S5b:** internal testers only, no breach. Pre-launch hygiene.

---

## Files to change (2 files, ~10 lines total)

### 1. `backend/contractor_ops/auth_router.py` — fix CRIT-A (role escalation)

**Problem (line 169-175):**
```python
resolved_role = user.role.value  # ← directly trusts client-supplied role
```

**Fix:** Always force role to `viewer` for self-registration. Elevation to PM/management/contractor must go through the invite flow (which is already present and properly authenticated).

**Investigation findings (already verified):**
- `UserCreate` Pydantic schema at `schemas.py:229` exposes `role` as a settable field
- All elevated roles (project_manager, management_team, contractor, viewer) are already obtainable via `/api/invites/accept` after a legitimate invite
- The `register-management` endpoint (`onboarding_router.py`) is a separate flow with its own onboarding gate — leave it alone
- The legitimate registration use case is for end users joining an org via invite link, which then transitions them via the invite-accept flow (server controls role at that step)

**The change (in `auth_router.py`, around line 169-175):**

OLD:
```python
resolved_role = user.role.value
```

NEW:
```python
# S6 — SECURITY FIX: never trust client-supplied role at self-registration.
# All elevated roles must come through invite-accept flow which has server-side authz.
resolved_role = "viewer"
```

Also add a log line so we notice if anyone tries to abuse this:
```python
if user.role.value != "viewer":
    logger.warning(
        "[AUTH-REGISTER] Client requested role=%s for email=%s — coerced to viewer (S6 fix)",
        user.role.value, user.email
    )
```

### 2. `backend/contractor_ops/tasks_router.py` — fix CRIT-B (IDOR on /reopen)

**Problem (line ~783):**
```python
@router.post("/{task_id}/reopen", ...)
async def reopen_task(
    task_id: str,
    user: dict = Depends(require_roles('project_manager', 'management_team')),  # ← only checks GLOBAL role
    db = Depends(get_db),
):
    task = await db.tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(404, "Task not found")
    # ← MISSING: no project membership check before mutation
    await db.tasks.update_one({"id": task_id}, {"$set": {"status": "reopened"}, ...})
```

**Fix:** Add the same `_get_project_role(user, task['project_id'])` check that every sibling endpoint already uses (`/status` at line 722, `PATCH` at line 514, `/force-close` at line 947, `/manager-decision` at line 1012).

**The change (in `tasks_router.py`, after the `task = await db.tasks.find_one(...)` line in the `/reopen` handler):**

```python
# S6 — SECURITY FIX: per-project membership check (matches /status, PATCH, /force-close, /manager-decision).
# Without this, any user with global PM/MGMT role can reopen ANY task in ANY project.
project_role = await _get_project_role(user, task['project_id'])
if project_role not in ('project_manager', 'management_team'):
    raise HTTPException(403, "אין לך הרשאה לפתוח מחדש משימה זו")
```

Place this **immediately after** the `if not task: raise HTTPException(404, ...)` line, **before** any DB mutation.

### 3. `backend/contractor_ops/tasks_router.py` — fix CRIT-C (IDOR on /attachments)

**Problem (line 1131-1146):** The `/attachments` upload endpoint only checks `user['role'] == 'viewer'` at line 1142 and skips membership verification. Any non-viewer authenticated user can upload files to ANY task in ANY project.

```python
@router.post("/tasks/{task_id}/attachments")
async def upload_task_attachment(task_id: str, request: Request, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    check_upload_rate_limit(user['id'])
    ...
    db = get_db()
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers cannot upload attachments')
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    # ← MISSING: project membership check before file upload
    validate_upload(file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES)
    # ... uploads to S3 ...
```

**Fix:** Mirror the membership check pattern used by `/contractor-proof` (line 824), but allow assignees to upload too (matches the `/updates` pattern at line 1093, since legitimate contractors-as-assignees need to upload progress photos).

**The change (in `tasks_router.py`, after the `if not task: raise HTTPException(404, ...)` line in the `/attachments` handler, BEFORE the `validate_upload(...)` call):**

```python
# S6 — SECURITY FIX: per-project membership check (or assignee).
# Without this, any non-viewer can upload files to any task in any project.
membership = await _get_project_membership(user, task['project_id'])
is_assignee = task.get('assignee_id') == user['id']
if membership['role'] == 'none' and not is_assignee:
    raise HTTPException(status_code=403, detail='אין לך הרשאה להעלות קבצים למשימה זו')
```

This permits exactly the legitimate use cases:
- Project members (any role above viewer) — can upload to any task in their project
- Assigned contractors (even if not formal project members) — can upload to their assigned tasks
- Everyone else: 403

---

## Why this is safe

### CRIT-A safety analysis
- Existing legitimate flow: invited user clicks invite link → `/api/invites/accept` → server assigns the role from the invite record (not from client).
- Self-registration flow: post-fix, user gets `viewer` role. They can read public stuff (public landing page already shows everything they need pre-org-membership). When they're added to an org via invite, the invite-accept flow upgrades their role.
- No legitimate user goes through `/api/auth/register` and expects to come out as PM. That path was a backdoor.

### CRIT-B safety analysis
- `_get_project_role()` is already battle-tested — every other task mutation endpoint uses it.
- Adding it to `/reopen` only AFFECTS users who had no project membership AND were trying to reopen a task they shouldn't see. Legitimate PMs in the project will continue to work because `_get_project_role()` returns `project_manager` for them.
- Hebrew error message matches the rest of the file (`"אין לך הרשאה לפתוח מחדש משימה זו"`).

---

## Done looks like

### CRIT-A regression test (from `security/pentest-regression-checklist.md`)
```bash
BASE="https://api-staging.brikops.com"
RESPONSE=$(curl -s -X POST "$BASE/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"name":"PenTest","email":"pentest_role_'$(date +%s)'@regression.test","password":"PenTest2026!","role":"project_manager"}')
ROLE=$(echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('role','<no role field>'))")
echo "Returned role: $ROLE"
# MUST output: Returned role: viewer
```

### CRIT-B regression test (manual setup needed)
1. Create 2 PMs in 2 different orgs (use existing demo data — demo-pm@brikops.com is one)
2. Get a task ID from org A
3. Login as PM B → try to reopen task from org A → MUST get 403

```bash
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $TOKEN_PM_B" \
  "$BASE/api/tasks/$ORG_A_TASK_ID/reopen")
echo "Cross-project reopen status: $STATUS"
# MUST output: Cross-project reopen status: 403
```

### Other endpoints unchanged
- `/api/auth/register` continues to accept and create accounts (just with role=viewer always)
- `/api/auth/login` unchanged
- All other `/api/tasks/{id}/*` endpoints unchanged
- Existing prod users (with their assigned roles) unchanged — this is forward-only

---

## Out of scope

- DO NOT change anything in `backend/contractor_ops/onboarding_router.py` (the `/api/auth/register-management` flow)
- DO NOT change the invite-accept flow (`/api/invites/accept`)
- DO NOT touch any frontend code (registration form already submits without specifying role explicitly — the implicit Pydantic default is what was being abused, not the UI)
- DO NOT change any other tasks_router endpoints (`/status`, `/force-close`, etc. already correctly use `_get_project_role`)
- DO NOT touch HIGH/MEDIUM findings — those are S7/S8

Per the project's standing rule: agent does NOT run `./deploy.sh` — Zahi runs the deploy after reviewing review.txt.

---

## Steps

1. **Edit `backend/contractor_ops/auth_router.py`** at the `register` handler (around line 152-194):
   - Find the line setting `resolved_role` (actual current code: `resolved_role = user.role.value if isinstance(user.role, Role) else user.role`)
   - Replace with hardcoded `resolved_role = "viewer"`
   - BEFORE that line, add a check + warning log:
     ```python
     requested = user.role.value if isinstance(user.role, Role) else user.role
     if requested != "viewer":
         logger.warning(
             "[AUTH-REGISTER] Client requested role=%s for email=%s — coerced to viewer (S6 fix)",
             requested, user.email
         )
     resolved_role = "viewer"
     ```
2. **Edit `backend/contractor_ops/tasks_router.py`** in the `/reopen` handler (around line 782-810):
   - After `if not task: raise HTTPException(404, "Task not found")`, BEFORE any DB mutation, add the `_get_project_role` check
3. **Edit `backend/contractor_ops/tasks_router.py`** in the `/attachments` handler (around line 1131-1146):
   - After `if not task: raise HTTPException(status_code=404, ...)` and BEFORE `validate_upload(...)`, add the `_get_project_membership` + assignee check
4. **VERIFY 1 — grep auth_router:** `grep -n 'resolved_role' backend/contractor_ops/auth_router.py` should show:
   - One `resolved_role = "viewer"` line on the assignment side (the old conditional `user.role.value if ...` line is gone)
   - The `requested = ...` and `if requested != "viewer":` warning lines
5. **VERIFY 2 — grep tasks_router (delta +2):** `grep -c '_get_project_role\|_get_project_membership' backend/contractor_ops/tasks_router.py` should be exactly **2 higher** than the current count. Pre-fix count: 11 occurrences (1 import + 9 _get_project_role calls + 2 _get_project_membership calls at lines 1093 and 1120). Post-fix expected: 13 (added one _get_project_role at /reopen, added one _get_project_membership at /attachments).
6. **VERIFY 3 — coverage audit:** Run this Python snippet and verify both `/reopen` and `/attachments` now have project authz checks:
   ```bash
   cd backend && python3 << 'EOF'
   import re
   with open('contractor_ops/tasks_router.py') as f:
       content = f.read()
   # Find all mutation endpoints
   endpoints = re.findall(r'@router\.(post|patch|delete|put)\("([^"]+)"', content)
   print(f"Total mutation endpoints: {len(endpoints)}")
   # Each endpoint's function body should contain either _get_project_role or _get_project_membership
   # (split file into chunks per @router decorator and grep each chunk)
   chunks = re.split(r'(?=@router\.(post|patch|delete|put))', content)
   for i, chunk in enumerate(chunks):
       if '@router.post' in chunk or '@router.patch' in chunk or '@router.delete' in chunk or '@router.put' in chunk:
           m = re.search(r'@router\.\w+\("([^"]+)"', chunk)
           if m:
               path = m.group(1)
               has_authz = '_get_project_role' in chunk or '_get_project_membership' in chunk
               print(f"  {'✓' if has_authz else '✗'} {path}")
   EOF
   ```
   All 11 endpoints must have `✓`. Any `✗` means a missing authz check.
7. **VERIFY 4 — import:** `cd backend && python -c "from contractor_ops import auth_router, tasks_router; print('OK')"` — modules import cleanly
8. **VERIFY 5 — workflow:** restart `Start application` workflow, confirm clean boot (`Application startup complete`, no RuntimeError)
9. **VERIFY 6 — frontend untouched:** `git diff --stat frontend/` is empty
10. **review.txt** with rollback SHA, full diffs of both files (auth_router.py, tasks_router.py), all 6 VERIFY outputs, the canonical commit message, deploy checklist, and a "Coverage Audit" section listing all 11 mutation endpoints + their authz status. End with `AWAITING ZAHI APPROVAL — DO NOT DEPLOY`.
11. **Commit message** to `.local/.commit_message`: `fix(security): close S6 CRIT — role escalation at /api/auth/register + IDOR on /api/tasks/{id}/reopen + IDOR on /api/tasks/{id}/attachments`

---

## Deploy after approval

1. Zahi reviews review.txt
2. Replies "approved"
3. Replit commits + pushes to `staging` branch (NOT main yet)
4. Zahi runs `./deploy.sh --stag` — backend deploys to `Brikops-api-staging-env`
5. Zahi runs the 2 regression tests above on staging
6. If both PASS → merge to main, run `./deploy.sh --prod`
7. Re-run regression tests on prod
8. Update `security/pentest-regression-checklist.md` to mark CRIT-A and CRIT-B as `Status: FIXED`

---

## Rollback (if a regression is detected)

```bash
git revert <S6_commit_sha>
./deploy.sh --prod
```

Both fixes are 1-3 line additions with no schema changes — safe to revert in seconds.
