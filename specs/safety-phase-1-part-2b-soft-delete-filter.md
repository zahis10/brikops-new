# Task #34b — Safety Phase 1 Part 2b — Patch: Soft-Delete Filter on Pre-Operation Reads

**Scope:** 1 file, ~25 lines changed. No new code, no new deps, no schema changes.

**Why:** Part 2 introduced `find_one` + `update_one` calls on the 5 safety collections that filter on `{id, project_id}` without `deletedAt: None`. This means after a soft-delete, the same record can still be GET/UPDATE/DELETE-ed, producing "zombie records" with both `deletedAt` and fresh `updated_at`.

**Evidence (grep output from commit 91febca4):**

```
254:    doc = await db.safety_workers.find_one({"id": worker_id, "project_id": project_id})
272:    before = await db.safety_workers.find_one({"id": worker_id, "project_id": project_id})
312:    before = await db.safety_workers.find_one({"id": worker_id, "project_id": project_id})
433:    doc = await db.safety_trainings.find_one({"id": training_id, "project_id": project_id})
448:    before = await db.safety_trainings.find_one({"id": training_id, "project_id": project_id})
477:    before = await db.safety_trainings.find_one({"id": training_id, "project_id": project_id})
628:    doc = await db.safety_documents.find_one({"id": document_id, "project_id": project_id})
643:    before = await db.safety_documents.find_one({"id": document_id, "project_id": project_id})
688:    before = await db.safety_documents.find_one({"id": document_id, "project_id": project_id})
852:    doc = await db.safety_tasks.find_one({"id": task_id, "project_id": project_id})
867:    before = await db.safety_tasks.find_one({"id": task_id, "project_id": project_id})
917:    before = await db.safety_tasks.find_one({"id": task_id, "project_id": project_id})
1049:   doc = await db.safety_incidents.find_one({"id": incident_id, "project_id": project_id})
1064:   before = await db.safety_incidents.find_one({"id": incident_id, "project_id": project_id})
1120:   before = await db.safety_incidents.find_one({"id": incident_id, "project_id": project_id})
```

15 find_one lines + all update_one pre-condition filters need the fix.

---

## Fix

**File:** `backend/contractor_ops/safety_router.py`

### Step 1 — Patch the 15 find_one calls

For **every one** of the 15 lines above, add `"deletedAt": None` to the filter:

```python
# BEFORE:
await db.safety_workers.find_one({"id": worker_id, "project_id": project_id})

# AFTER:
await db.safety_workers.find_one({"id": worker_id, "project_id": project_id, "deletedAt": None})
```

Exact lines to modify: **254, 272, 312, 433, 448, 477, 628, 643, 688, 852, 867, 917, 1049, 1064, 1120**.

### Step 2 — Patch update_one pre-condition filters

Run:

```bash
grep -n 'update_one({"id"' backend/contractor_ops/safety_router.py | grep -v "deletedAt"
```

For every line returned that **mutates** an existing record (PATCH/update flow — NOT the soft-delete update_one itself), add `"deletedAt": None` to the filter:

```python
# BEFORE:
await db.safety_workers.update_one(
    {"id": worker_id, "project_id": project_id},
    {"$set": update_data},
)

# AFTER:
await db.safety_workers.update_one(
    {"id": worker_id, "project_id": project_id, "deletedAt": None},
    {"$set": update_data},
)
```

The **soft-delete** `update_one` (the one that sets `deletedAt`) should **also** have `"deletedAt": None` in its filter — this enforces idempotency (second delete returns 404 instead of overwriting `deletedAt`). Verify each of the 5 soft-delete endpoints has this.

---

## DO NOT

- **Do NOT** touch lines 293, 459, 670, 899, 1098 — those are post-update reads right after a successful `update_one`, they're safe.
- **Do NOT** add any new query parameter (no `include_deleted` — that's Part 3+ territory).
- **Do NOT** change business logic — only filter conditions.
- **Do NOT** touch any other file (`server.py`, `schemas.py`, `router.py`, etc.).
- **Do NOT** add new indexes — existing `(project_id, deletedAt, ...)` compound indexes from Part 1 already cover this.
- **Do NOT** change HTTP status codes — 404 is already the right response when `find_one` returns `None`.
- **Do NOT** add migration scripts — this is a query-filter fix, not a schema change.

---

## VERIFY before commit

Run these 3 greps. **All three must return 0 lines.**

```bash
# 1. All find_one with project_id must have deletedAt:
grep -n 'find_one({"id"' backend/contractor_ops/safety_router.py | grep "project_id" | grep -v "deletedAt"

# 2. All update_one must have deletedAt:
grep -n 'update_one({"id"' backend/contractor_ops/safety_router.py | grep -v "deletedAt"

# 3. No raw dict without deletedAt in any filter that uses project_id:
grep -n '{"id":.*"project_id"' backend/contractor_ops/safety_router.py | grep -v "deletedAt" | grep -v "insert_one"
```

If any of the three returns lines → you missed a spot. Fix and re-run until all three are empty.

---

## Manual test (if ENABLE_SAFETY_MODULE=true in any env)

```bash
# 1. Create worker
POST /api/safety/projects/{project_id}/workers
→ capture worker_id

# 2. Soft-delete
DELETE /api/safety/projects/{project_id}/workers/{worker_id}
→ expect 204

# 3. Try to GET again
GET /api/safety/projects/{project_id}/workers/{worker_id}
→ expect 404 (BEFORE FIX: returns 200 with deletedAt visible)

# 4. Try to PATCH
PATCH /api/safety/projects/{project_id}/workers/{worker_id}
→ expect 404 (BEFORE FIX: returns 200, creates zombie record)

# 5. Try to DELETE again
DELETE /api/safety/projects/{project_id}/workers/{worker_id}
→ expect 404 (BEFORE FIX: returns 204, overwrites deletedAt)
```

Repeat for trainings, documents, tasks, incidents (same pattern).

If the feature flag is off in all environments (production, staging) — skip the manual test, commit after the 3 greps pass.

---

## Commit message (exactly)

```
fix(safety): Part 2b — add deletedAt:None filter to prevent zombie records

15 find_one calls + update_one pre-conditions on safety_workers/trainings/
documents/tasks/incidents were missing soft-delete filter. After a record
was soft-deleted, subsequent GET/PATCH/DELETE could still mutate it,
producing records with both deletedAt and fresh updated_at.

No new logic, no new deps, no schema changes. Only filter conditions.
```

---

## Deploy

```bash
./deploy.sh --prod
```

זה גם ה-commit וגם ה-push לפרוד. אין שום שלב נוסף מה-Mac.

אחרי ה-deploy — שלח לZahi `git log -1 --stat` + unified diff של הקומיט האחרון לריוויו סופי.

---

## Definition of Done

- [ ] All 15 find_one lines have `deletedAt: None`
- [ ] All update_one lines have `deletedAt: None`
- [ ] All 3 verification greps return 0 lines
- [ ] `./deploy.sh --prod` ran successfully (commit + push together)
- [ ] Diff sent to Zahi for post-deploy code review
- [ ] No other files modified
- [ ] No new deps in `requirements.txt`
