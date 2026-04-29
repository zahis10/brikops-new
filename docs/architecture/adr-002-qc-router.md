# ADR-002 — qc_router.py

**Status:** Accepted
**Date:** 2026-04-29
**File:** `backend/contractor_ops/qc_router.py` (2936 lines as of 2026-04-29)

## Why this exists

`qc_router.py` is the largest backend file. It owns the **QC stage
workflow** — the multi-stage approval flow that runs per floor per
building, where each stage (e.g. "concrete pour", "plumbing rough-in",
"finishes") moves through `draft → ready → pending_review → approved
or rejected → reopened` and notifies the right project managers and
named approvers at each transition.

It also exports a separate `notif_router` (mounted at
`/api/qc-notifications`) for the notification-list UI — kept in the
same file because the notification documents are written here on every
state transition and the read endpoints share validation helpers.

The file is large because QC has the densest state machine in the
product:
- 6 stage statuses (`VALID_STAGE_STATUSES_FULL` at line 26)
- 4 transition actions (`submitted`, `approved`, `rejected`, `reopened`)
- 2 approver modes (`all` stages vs `stages` whitelist)
- 3 recipient sets per action (PMs, approvers, submitter)
- File-attached photo proof per stage
- Stage history (immutable append-only log)

Splitting before documenting the WHY would risk silently changing one
of the 4 transition handlers in a way nobody catches until production.

## Architectural decisions

- **Decision: co-locate transition handlers and notification dispatch.**
  Every stage transition writes the new status, appends to history,
  builds the recipient set, and inserts notification documents in the
  same handler. Why: the recipient set depends on the action AND the
  pre-transition state (who submitted gets re-notified on rejection
  but not on approval). Splitting risks mismatched transactions.
- **Decision: notifications are documents in `qc_notifications`,
  not push notifications.** Why: the notification UI in the frontend
  reads `/api/qc-notifications` and renders an inbox; pushes are a
  separate channel layered on top via `notification_service.py`.
- **Decision: stage status set is closed (`VALID_STAGE_STATUSES_FULL`).**
  Why: the FE filter chips and aggregations all assume these 6 values.
  Adding a new status requires updating the chips, the dashboard
  aggregation, AND `_get_stage_recipients` — a per-status decision.
- **Decision: `MANAGEMENT_ROLES` is imported from `router.py`,
  not redefined here**. Why: drift hazard. Same as the
  `TERMINAL_TASK_STATUSES` lesson from BATCH 5C — local duplicates
  silently shadow imports.
- **Decision: `PM_ROLES = {'project_manager', 'owner'}` is local to
  this file**. Why: this is QC-specific (only PMs and owners get the
  "you have a stage to review" notification, not management_team or
  admins). Documented inline at the declaration so the next reader
  knows it's intentionally narrower than `MANAGEMENT_ROLES`.
- **Decision: notify-eligible roles are explicit
  (`NOTIFY_ELIGIBLE_ROLES = {'project_manager', 'owner', 'management_team'}`).**
  Why: separates "who can do the action" from "who gets notified about
  it" — a common confusion in the QC system before this constant was
  extracted.
- **Decision: file uploads land in `Path(__file__).parent.parent /
  "uploads" / "qc"` (line 99).** Why: legacy local-disk path inherited
  from M1; new code uses `services.object_storage` (S3) but QC stage
  photos still write here. Migration not justified pre-launch — the
  upload volume per stage is low and S3 listing for the stage UI would
  add latency.

## Conventions used here

- Every endpoint takes `user: dict = Depends(get_current_user)` or
  `Depends(require_roles(...))`.
- Every endpoint that reads a stage validates `_get_project_role(user,
  project_id)` against `QC_ALLOWED_ROLES = MANAGEMENT_ROLES` first.
- Stage history is **append-only** — no UPDATE on existing history
  entries. Rollbacks add a new entry with `action: "reopened"`.
- All timestamps via `_now()` (UTC ISO string) — never `datetime.now()`
  directly.
- All audit writes via `_audit(...)` from `router.py`.
- `qc_notifications` is the inbox; `notification_service.py` dispatches
  pushes on top — keep them separate.
- Recipient sets use Python `set` (not `list`) to dedupe automatically
  when a user is both a PM and a named approver.

## Natural seams (where to split if/when refactor happens)

- **Notification helpers** (`_create_qc_notification`,
  `_get_stage_recipients`, lines 40-97). Could move to
  `services/qc_notifications.py`. **~150 lines saved.**
- **`notif_router`** (the entire `/api/qc-notifications` namespace).
  Reads only — could move to `qc_notifications_router.py` with the
  shared notification model imports. **~200 lines saved.**
- **Photo upload + presign helpers** (legacy local-disk + signed URLs
  for stage attachments). Could merge into `services/object_storage.py`
  pattern eventually. **~250 lines saved.**
- **Approver-config endpoints** (`/api/qc/approvers`,
  add / remove / list). Could split to `qc_approvers_router.py`.
  **~200 lines saved.**
- **Template endpoints** (`/api/qc/templates`, super-admin only).
  Could split to `qc_templates_router.py`. **~300 lines saved.**

## When to refactor

- **Trigger:** if a 6th stage status is proposed, OR if approver modes
  expand beyond `all` / `stages` (e.g. per-trade approvers).
  The current shape barely fits in one head; one more dimension
  pushes it past the threshold.
- **Pre-requisite:** end-to-end test for each of the 4 transition
  actions, asserting the recipient set per action × project-membership
  combination. No current coverage at this granularity.
- **Pre-requisite:** decide whether to migrate uploads to S3 first.
  Splitting the file before the upload migration risks two churns.

## Recent changes

- 2026-04-22 (BATCH 5C): No change to this file — the
  `TERMINAL_TASK_STATUSES` dedupe was in `handover_router.py`. QC
  uses its own status set (`VALID_STAGE_STATUSES_FULL`); audit
  confirmed no shadow constants.
- M6 (Q1 2026): Added approver-mode `stages` (per-stage whitelist)
  alongside the original `all`-mode. Doubled the size of
  `_get_stage_recipients`.
- M4 (Q4 2025): Photo proof per stage (legacy upload path).

## Refactor backlog items touching this file

- `#11` (low) Migrate QC photo uploads to `services.object_storage`
  pattern (currently local disk).
- `#12` (low) Future ADR for `qc_approvers_router` extraction once
  approver modes expand.

See [`../refactor-backlog.md`](../refactor-backlog.md) for full details.
