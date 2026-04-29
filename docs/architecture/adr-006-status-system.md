# ADR-006 — Status system (cross-cutting)

**Status:** Accepted
**Date:** 2026-04-29
**Scope:** Cross-cutting — `tasks_router.py`, `handover_router.py`,
`qc_router.py`, `constants.py`, every frontend page that shows status
chips, every dashboard aggregation.

## Why this exists

BrikOps has three independent status namespaces (task / handover-protocol /
QC-stage), and within the task namespace alone there are 9 status
values that get re-grouped into 3 user-facing buckets for chips and
KPIs. Multiple incidents in 2026-Q2 (BATCH 5C, 5F, 5G) traced back to
silent drift between (a) the canonical status set, (b) local copies in
individual files, and (c) hardcoded status comparisons. This ADR is
the single source of truth for **how status is supposed to work**.

## The three namespaces (don't conflate them)

| Namespace | Values | Defined in | Notes |
|-----------|--------|-----------|-------|
| **Task** | `open`, `assigned`, `in_progress`, `pending_contractor_proof`, `pending_manager_approval`, `returned_to_contractor`, `reopened`, `waiting_verify`, `closed`, `approved`, `done`, `cancelled` | `schemas.py` (`TaskStatus` enum) + `VALID_TRANSITIONS` | Used by tasks, defects, all handover-spawned defects. |
| **Handover protocol** | `draft`, `in_progress`, `partially_signed`, `signed` | Inline string literals in `handover_router.py` | Per protocol document, not per item. |
| **QC stage** | `draft`, `ready`, `pending_review`, `approved`, `rejected`, `reopened` | `qc_router.py:26` (`VALID_STAGE_STATUSES_FULL`) | Per stage per floor. Note `approved` here ≠ task `approved`. |

These three are **distinct** despite reusing some words (`approved`,
`reopened`, `draft`). Don't write code that compares values across
namespaces.

## The single sources of truth (task namespace)

- **Terminal task statuses** —
  `backend/contractor_ops/constants.py:1`:
  ```python
  TERMINAL_TASK_STATUSES = {"closed", "approved", "done", "cancelled"}
  ```
  Import this. **Never redefine locally.**

- **Status bucket expansion** (chip → underlying values) —
  `backend/contractor_ops/tasks_router.py:40`:
  ```python
  STATUS_BUCKET_EXPANSION = {
      'open':        ['open', 'assigned', 'in_progress',
                      'pending_contractor_proof', 'reopened',
                      'waiting_verify'],
      'in_progress': ['in_progress', 'pending_contractor_proof',
                      'pending_manager_approval', 'returned_to_contractor',
                      'waiting_verify'],
      'closed':      ['closed', 'approved'],
  }
  ```
  Consume this whenever the question is "is this in bucket X?"

- **Display labels** — `frontend/src/i18n/he.json` under
  `"statuses"` key. Helper: `tStatus(key)` from
  `frontend/src/i18n/index.js`.

The DB layer never sees Hebrew; the UI layer never sees raw English
status keys (without going through `tStatus`).

## Architectural decisions

- **Decision: writes are string literals; reads (categorical) go
  through `STATUS_BUCKET_EXPANSION`.** Why: a write is a single named
  state transition; a read often asks "is this in some bucket?" The
  same code shouldn't try to handle both contracts.

- **Decision: `force_close → 'approved'` and `approve_proof → 'closed'`
  are different terminal statuses on purpose.** Both are terminal;
  the difference is the closure reason — `'closed'` = proof reviewed
  and accepted; `'approved'` = manager override / closed without proof
  review. The audit trail keeps the distinction; the dashboard
  treats them equivalently via `STATUS_BUCKET_EXPANSION['closed']`.

- **Decision: display labels (Hebrew) are derived; never persisted.**
  `he.json` maps status keys → user-facing strings. The DB stores
  English keys only. Changing a label in `he.json` doesn't migrate any
  data; changing a key in `STATUS_BUCKET_EXPANSION` requires a backfill
  if any task has that key persisted.

- **Decision: drift-guard test is required.** BATCH 5F shipped
  `backend/tests/test_status_buckets.py` to assert that the bucket
  expansion stays consistent with the dashboard aggregation's
  `open_statuses` and `handled_statuses` lists. This test must keep
  passing — adding a new status requires updating both the dict and
  the lists, and the test catches the desync.

## Conventions used here

- **Backend writes:** `db.tasks.update_one({...}, {'$set': {'status': 'closed'}})` — string literal matching `TaskStatus` enum.
- **Backend reads (single value):** `if task['status'] == 'closed':` —
  string literal.
- **Backend reads (categorical):**
  ```python
  if status in STATUS_BUCKET_EXPANSION:
      query['status'] = {'$in': STATUS_BUCKET_EXPANSION[status]}
  ```
  Or for "is this terminal?":
  ```python
  if task['status'] in TERMINAL_TASK_STATUSES:
      ...
  ```
- **Frontend reads (display):** `tStatus(task.status)` from
  `frontend/src/i18n/index.js`.
- **Frontend filter chips:** pass the bucket name to the API
  (`status=open`), let the backend expand. Don't expand client-side.

## Forbidden patterns (with reasons)

| Pattern | Why it's forbidden |
|---------|---------------------|
| `if task['status'] in ['open', 'in_progress', 'in_review']` | Silently rots when a status is added or renamed. BATCH 5G added 3 new statuses to the `open` bucket — every hardcoded list missed them. Always use `STATUS_BUCKET_EXPANSION['open']`. |
| Local `TERMINAL_TASK_STATUSES = {...}` redefinition | BATCH 5C found one in `handover_router.py` missing `'cancelled'`. Closed tasks were showing as still-open in the per-building breakdown. Removed the local copy; now imports from `constants.py`. |
| Hebrew status keys persisted to DB | Storage layer is English keys only. If you see `"status": "סגור"` in a document, it's a bug. Migrate immediately. |
| Status comparison across namespaces (e.g. `if task['status'] == stage['status']`) | The `approved` value in task namespace ≠ `approved` in QC stage namespace. They mean different things. |
| `$nin: ['closed', 'approved']` (without `'cancelled'` and `'done'`) | This was the bug at `handover_router.py:2336` (Task #27). The right way is `$nin: list(TERMINAL_TASK_STATUSES)` — but be aware some endpoints intentionally exclude only the "happy path" terminal pair. Document the intent inline if you do. |

## Lessons captured

- **BATCH 5C lesson:** Local duplicates of constants silently shadow
  imports. Always grep `^<CONST_NAME> = ` across the backend before
  assuming an update cascades.
- **BATCH 5F lesson:** The drift surface between
  `STATUS_BUCKET_EXPANSION` and the dashboard aggregation's literal
  lists is real. The drift-guard test catches the most likely failure
  mode (forgetting to update both); structural consolidation is
  refactor-backlog item #4.
- **BATCH 5G lesson:** Adding a new status requires updating
  `STATUS_BUCKET_EXPANSION` AND the dashboard aggregation lists AND
  the frontend chip strip AND `he.json`. Four places. Test after each
  step, in this order.

## When to refactor

- **Trigger:** if a 10th task status is added.
  Today the bucket expansion is a 3-key, ~20-value dict — readable.
  One more dimension and a config table or sub-typed enum becomes
  more readable.
- **Pre-requisite:** the drift-guard test must keep passing as you
  evolve the system.
- **Pre-requisite:** force_close regression tests (Task #28 — BLOCKING
  LAUNCH).

## Refactor backlog items related

- `#4` Consolidate the bucket expansion + the open/handled lists.
- `#9` `handover_router.py:2336` `$nin` missing `'done'`.
- `#10` force_close regression tests (BLOCKING LAUNCH).
- `#5` Audit for any remaining shadow constants.

See [`../refactor-backlog.md`](../refactor-backlog.md).
