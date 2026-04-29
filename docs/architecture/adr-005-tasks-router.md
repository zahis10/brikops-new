# ADR-005 — tasks_router.py

**Status:** Accepted
**Date:** 2026-04-29
**File:** `backend/contractor_ops/tasks_router.py` (1289 lines as of 2026-04-29)

## Why this exists

`tasks_router.py` owns the **task lifecycle state machine** and the
**dashboard KPI aggregations** that depend on it. A "task" in BrikOps
is a defect — a finding from QC, handover, safety, or manual entry
that needs a contractor assignment, proof upload, manager approval,
and closure.

The state machine has 9 statuses and 14+ valid transitions
(`VALID_TRANSITIONS` in `schemas.py`). The dashboard KPI aggregation
needs to count tasks by **user-facing bucket** (open / in_progress /
closed) — but each bucket maps to multiple underlying status values.
That mapping (`STATUS_BUCKET_EXPANSION` at line 40) is the **single
source of truth** for "what does each chip mean" and is the most
load-bearing constant in the file.

This file is the smallest of the file-specific ADR set (1289 lines),
but is documented because its drift surface is the highest. BATCH 5F
shipped a drift-guard test (`backend/tests/test_status_buckets.py`)
specifically to catch silent mismatches between this file and the
frontend.

## Architectural decisions

- **Decision: `STATUS_BUCKET_EXPANSION` is the single source of truth
  for status grouping.** Defined at module scope (line 40), consumed
  by the list endpoint at line 240, the dashboard KPI aggregation
  (sibling code in this file), and the drift-guard test in
  `backend/tests/test_status_buckets.py`. **Never hardcode
  `["open", "in_progress", ...]` elsewhere — always go through this
  dict.** See ADR-006 for the full status-system context.

- **Decision: writes use string literals, reads use the bucket
  expansion.** Why: writes are point-events (a task transitions to
  exactly one named status), but reads are categorical (a chip wants
  all tasks "in this bucket"). Different contracts, different APIs.

- **Decision: `force_close` writes `'approved'`, `approve_proof`
  writes `'closed'`.** This is intentional — they represent different
  closure reasons:
  - `'closed'` = the contractor's proof was reviewed and accepted
    (the happy path).
  - `'approved'` = a manager force-closed the task without reviewing
    proof (the override path; e.g. defect was resolved offline,
    contractor dispute, etc.).

  Both are terminal. The dashboard aggregations treat them
  equivalently via `STATUS_BUCKET_EXPANSION['closed']: ['closed',
  'approved']`. The audit trail keeps the distinction.

- **Decision: list endpoint accepts both `status` (single bucket name)
  and `status_in` (CSV of literal status values).** Why: the chip UI
  passes `status=open`; the filter drawer with multi-select passes
  `status_in=open,assigned,in_progress`. Two separate code paths
  (lines 239-249) handle this — `status` triggers bucket expansion,
  `status_in` is a literal list passthrough.

- **Decision: contractor scoping is layered late** (lines 277-297).
  Whatever query the management user built is then narrowed if the
  caller is a contractor — the contractor sees only tasks assigned to
  them OR to their company. Why: lets the contractor reuse the same
  endpoint (`GET /tasks?project_id=X`) the PM uses, with the auth
  layer narrowing the result set. Trade-off: the query-building flow
  is harder to read because the contractor narrowing happens after
  the user-supplied filters.

- **Decision: `bucket_key` queries use a Mongo `$facet` aggregation
  pipeline** (lines 299-329). Why: bucket-key is a computed field
  (combines trade + assignee company + membership trade map) — can't
  be a plain Mongo filter. The `$facet` runs the count and the page
  in one pipeline trip.

- **Decision: known N+1 at line 493 is documented, not fixed yet.**
  After fetching the task, we sequentially look up project, building,
  floor, unit, and assignee for display labels — 5 round-trips per
  task-detail request. The TODO at line 493 says "Optimize with
  `$lookup` aggregate when scale requires it." At 41 internal testers,
  the latency cost is ~50ms; at 10000 users it would matter. Tracked
  as refactor-backlog item #N.

- **Decision: assignee-on-create is rejected** (lines 87-92). Tasks
  must be created without an assignee, then assigned in a separate
  call. Why: keeps the audit trail clean ("created" and "assigned"
  are separate events) and matches the UI workflow.

## Conventions used here

- All routes prefixed `/api`.
- Every endpoint takes `user: dict = Depends(...)` and validates
  `_check_project_access` (write) or `_check_project_read_access`
  (read).
- Status writes: string literals matching `TaskStatus` enum in
  `schemas.py`.
- Status reads (categorical): always via `STATUS_BUCKET_EXPANSION`.
- Terminal-status checks: import `TERMINAL_TASK_STATUSES` from
  `contractor_ops.constants` — never redefine. (See ADR-006.)
- Pagination: `{"items": [...], "total": N, "limit": N, "offset": N}`.
- Aggregation pipelines preferred over Python-side post-processing
  for sort + paginate (consistent with `qc_router` and `handover_router`).
- Audit writes via `_audit()` for create / assign / status-change /
  close / reopen / delete.

## Natural seams (where to split if/when refactor happens)

- **Already small (1289 lines)** — splitting before further growth
  isn't justified.
- If split is needed eventually:
  - **List endpoint + bucket_key aggregation pipeline** could move to
    `tasks_query_router.py` (the most complex piece, lines 200-362).
  - **Notification dispatch** could move to `services/task_notifications.py`
    (currently inline at the action handlers).

## When to refactor

- **Trigger:** when the N+1 at line 493 starts showing up in P95
  latency measurements (today the P95 is acceptable; revisit at
  >500 active users).
- **Trigger:** if a 10th status is added — currently the bucket
  expansion is human-readable; one more dimension and a config table
  becomes more readable than a literal dict.
- **Pre-requisite:** force_close → aggregation → reopen regression
  tests (Task #28, **BLOCKING LAUNCH** per BATCH 5C — flagged in
  refactor-backlog item #10).
- **Pre-requisite:** the drift-guard test at
  `backend/tests/test_status_buckets.py` (BATCH 5F) must continue
  passing.

## Recent changes

- 2026-04-27 (BATCH 5G): `STATUS_BUCKET_EXPANSION['open']` expanded
  to 6 statuses (added `pending_contractor_proof`, `reopened`,
  `waiting_verify`). The "בביצוע" KPI chip on the frontend was
  removed since `in_progress` is now a subset of `open`.
- 2026-04-26 (BATCH 5F): Drift-guard test
  `backend/tests/test_status_buckets.py` added — asserts that
  `STATUS_BUCKET_EXPANSION` matches the open/handled status lists
  used by the dashboard aggregation.
- 2026-04-22 (BATCH 5C): Status alignment — confirmed
  `force_close → 'approved'` vs `approve_proof → 'closed'` are
  intentional and load-bearing for the audit trail.
- TODO at line 493: known N+1 in task-detail; optimize at scale.

## Refactor backlog items touching this file

- `#4` Consolidate `STATUS_BUCKET_EXPANSION` (line 40) and the
  open_statuses + handled_statuses lists used by the dashboard
  aggregation function — drift surface even with the test guard.
- `#10` `force_close → aggregation → reopen` regression tests
  (Task #28, **BLOCKING LAUNCH**).
- `#17` (low) N+1 fix in task-detail endpoint at line 493.

See [`../refactor-backlog.md`](../refactor-backlog.md) for full details.
