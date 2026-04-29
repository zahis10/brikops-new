# BrikOps Architecture — Index

**Last updated:** 2026-04-29 (DOCS PHASE 1A)
**Audience:** Anyone touching the codebase — Cowork, future hires, Zahi.

This directory documents the **WHY** of major files and cross-cutting
concerns. The code is the source of truth for HOW; the docs here are the
source of truth for WHY.

For the **directory tree** and per-module role inventory, see
[`../../CODEBASE_SUMMARY.md`](../../CODEBASE_SUMMARY.md).
For the **product overview / roadmap**, see
[`../../PROJECT_OVERVIEW.md`](../../PROJECT_OVERVIEW.md).
For the **deploy / native-vs-OTA** rules, see
[`../../CLAUDE.md`](../../CLAUDE.md).

---

## Top files by line count (as of 2026-04-29)

| Lines | File | What it does | ADR |
|------:|------|--------------|-----|
| 4115  | `frontend/src/pages/ProjectControlPage.js` | Project home — 7 work-modes, structure tree, defects, KPIs, settings tabs | [ADR-001](./adr-001-project-control-page.md) |
| 2936  | `backend/contractor_ops/qc_router.py` | QC stage workflow + approver notifications | [ADR-002](./adr-002-qc-router.md) |
| 2652  | `backend/contractor_ops/handover_router.py` | Handover protocol lifecycle (initial / final), legal sections, signatures | [ADR-003](./adr-003-handover-router.md) |
| 2256  | `frontend/src/pages/OrgBillingPage.js` | Org-level billing self-service (plans, invoices, project licenses) | — (future) |
| 2239  | `frontend/src/pages/StageDetailPage.js` | QC stage detail per floor (covered tangentially by ADR-002) | — |
| 2200  | `backend/contractor_ops/billing.py` | Billing core — plan selection, GI checks, subscription helpers | — (future, paired with ADR-004) |
| 2125  | `backend/contractor_ops/onboarding_router.py` | Org/project onboarding wizard endpoints | — (future) |
| 2068  | `backend/contractor_ops/billing_router.py` | Billing HTTP endpoints — PayPlus webhooks, plan switching, GI gate | [ADR-004](./adr-004-billing-router.md) |
| 1912  | `backend/contractor_ops/safety_router.py` | Safety inspections + corrective actions | — (future) |
| 1909  | `frontend/src/pages/TaskDetailPage.js` | Task drill-down — state machine UI, proof flow, reopen | — (covered by ADR-005) |
| 1613  | `backend/contractor_ops/admin_router.py` | Super-admin endpoints (orgs, users, impersonation) | — (future) |
| 1603  | `backend/contractor_ops/projects_router.py` | Project CRUD, membership, hierarchy | — (future) |
| 1543  | `frontend/src/pages/OnboardingPage.js` | Frontend onboarding wizard | — (future) |
| 1518  | `frontend/src/pages/ProjectPlansPage.js` | Project blueprints / plans viewer | — (future) |
| 1489  | `frontend/src/pages/AdminBillingPage.js` | Super-admin billing console | — (future) |
| 1419  | `backend/contractor_ops/export_router.py` | XLSX / CSV exports for tasks, units, audits | — |
| 1339  | `frontend/src/pages/HandoverSectionPage.js` | Handover section detail (covered tangentially by ADR-003) | — |
| 1289  | `backend/contractor_ops/tasks_router.py` | Task lifecycle state machine + dashboard KPI aggregations | [ADR-005](./adr-005-tasks-router.md) |
| 1197  | `backend/contractor_ops/debug_router.py` | Internal diagnostics endpoints | — |
| 1092  | `frontend/src/components/NewDefectModal.js` | New-defect creation modal (the only frontend component >1000 lines) | — |

The 9 file candidates without an ADR are flagged in
[`../refactor-backlog.md`](../refactor-backlog.md) as "future ADR triggers
when next touched heavily." The principle (per the spec): a 4000-line file
with a clear ADR is easier to onboard onto than a 500-line file refactored
into 6 files with no explanation. ADRs precede refactors.

---

## Cross-cutting ADRs

- [ADR-006 — Status system](./adr-006-status-system.md) — every status
  value, where written, where read, the 5C/5F/5G lessons, forbidden
  patterns.
- [ADR-007 — i18n](./adr-007-i18n.md) — module-level `t()` pattern,
  `he.json` source of truth, why en/ar/zh are deliberately frozen
  pre-launch.
- [ADR-008 — Navigation](./adr-008-navigation.md) — `getProjectBackPath`
  helper, the `?from=dashboard` URL-param convention from BATCH 5H, the
  broken `/projects/${id}` pattern fixed in BATCH 5I.

---

## Conventions (the short list)

### IDs
- All entities use **string UUIDs**: `str(uuid.uuid4())`.
- **Never** `ObjectId`. Mongo's `_id` is excluded from API responses
  (`{'_id': 0}` projection on every read).
- The application-level `id` field is what the frontend, audits, and
  cross-collection references use.

### Timestamps
- `_now()` (defined in `backend/contractor_ops/router.py`) returns a
  **UTC ISO-8601 string** (e.g. `"2026-04-29T07:18:23.123Z"`).
- **Never** `now_il()` or any local-timezone helper — UTC only at the
  storage layer. Display layers convert when needed.
- All timestamps in Mongo are strings, not BSON dates (matches the JSON
  contract and avoids serialization headaches).

### Status fields
- See [ADR-006](./adr-006-status-system.md) for the full picture.
- **Writes** use string literals (`"closed"`, `"approved"`, etc.).
- **Reads** that need to ask "is this open?" go through
  `STATUS_BUCKET_EXPANSION` in `tasks_router.py:40` (the single source of
  truth for what each user-facing chip means).
- **Terminal** statuses live in `backend/contractor_ops/constants.py:1`
  as `TERMINAL_TASK_STATUSES = {"closed", "approved", "done", "cancelled"}`.
  **Never** redefine this set locally — Batch 5C found a duplicate in
  `handover_router.py` and removed it.

### Hebrew / RTL
- All user-facing strings live in `frontend/src/i18n/he.json`.
- Helpers: `t('section', 'key')`, plus typed shortcuts `tStatus()`,
  `tCategory()`, `tPriority()`, `tRole()`, `tSubRole()`, `tTrade()` —
  see [ADR-007](./adr-007-i18n.md).
- Layout direction: every page sets `dir="rtl"` on its root container.
  Inputs that should stay LTR (phone numbers, emails) opt in with
  `dir="ltr"` on the field.
- en/ar/zh JSON files exist but are **frozen** pre-launch — Hebrew is
  the only user-facing locale we ship to internal testers right now.

### Auth
- Every protected endpoint uses `Depends(get_current_user)` or
  `Depends(require_roles(...))` from `contractor_ops.router`.
- Project-scoped endpoints additionally call `_check_project_access(user, project_id)`
  (write) or `_check_project_read_access(user, project_id)` (read).
- Org-billing endpoints route through `check_org_billing_role()` defined
  in `billing.py:532` — see [ADR-004](./adr-004-billing-router.md).

### Pagination
- Standard envelope: `{"items": [...], "total": N, "limit": N, "offset": N}`.
- Frontend filters/sorts on top of this — never re-implements pagination
  client-side.

---

## Anti-patterns to avoid (with reasons)

- **`WebkitOverflowScrolling: 'touch'`** — causes iOS WebView freeze on
  certain Capacitor versions. Never use.
- **`ObjectId`** — string UUIDs only. ObjectId leaks to JSON ugly and
  breaks the cross-collection reference convention.
- **`now_il()` / local-timezone helpers** — UTC only at the storage
  layer. Use `_now()`.
- **`console.log` with PII in production** — phone numbers, emails,
  full names. Use `mask_phone()` from `msg_logger`. The logger config
  drops debug-level logs in production but anything that hits stderr
  ships to logs.
- **`modal={true}` on Radix Dialog** — can leave `pointer-events: none`
  on `body` if the dialog unmounts mid-animation. Default `modal={false}`
  is safer; we manage focus manually.
- **Photo annotation rendering via `createPortal`** — events bubble to
  the parent canvas through the React tree even when DOM-portaled.
  Use the `PhotoAnnotation` component's contained event handling
  instead of porting overlay state up.
- **Native `<select>` in RTL + `position:fixed` drawer** — the dropdown
  escapes the drawer's bounds at ~600px on Desktop browsers (Mobile
  WebView is fine, which is why this shipped). Use Radix Select for new
  code. Open backlog item: UserDrawer migration.
- **`window.confirm()`** — looks ugly in mobile WebView and can't be
  styled. Use a Radix Dialog modal instead. Reference: `TaskDetailPage`
  reopen confirm modal.
- **Local duplicates of constants** — silently shadow imports. Always
  `grep "^<CONST_NAME> = "` before assuming an update cascades.
  Recent example: `handover_router.py` had its own `TERMINAL_TASK_STATUSES`
  that drifted from `constants.py`; Batch 5C removed it.
- **Hardcoding status comparisons** — `if status in ["open", "in_progress",
  "in_review"]` will silently rot when a status is added (BATCH 5G added
  3 new "open" statuses). Always go through `STATUS_BUCKET_EXPANSION`.
- **Bare `/projects/:projectId` route in navigate calls** — there is no
  such route. Every project-scoped page has a suffix
  (`/control`, `/dashboard`, `/handover`, `/qc`, `/plans`, `/tasks`,
  `/units`, `/buildings`, `/floors`, `/safety`). React Router falls
  through to the project list. Use `getProjectBackPath()` from
  `utils/navigation.js:17` or hardcode the full path with suffix.
  Recent example: BATCH 5I fixed this in `HandoverOverviewPage` and
  `OrgBillingPage`.

---

## When in doubt — where to find existing helpers

Always check these BEFORE building a new one:

| Helper | Location | What it does |
|--------|----------|--------------|
| `STATUS_BUCKET_EXPANSION` | `backend/contractor_ops/tasks_router.py:40` | Maps user-facing status chips to underlying status values. Single source of truth. |
| `TERMINAL_TASK_STATUSES` | `backend/contractor_ops/constants.py:1` | Set of statuses that exclude a task from "open" queries. |
| `_now()` | `backend/contractor_ops/router.py` | UTC ISO timestamp for all writes. |
| `_check_project_access` / `_check_project_read_access` | `backend/contractor_ops/router.py` | Project-scoped auth. Wrap every project-scoped endpoint. |
| `_get_project_role` / `_get_project_membership` | `backend/contractor_ops/router.py` | Reads the user's effective project role (lookups with super-admin override). |
| `check_org_billing_role` | `backend/contractor_ops/billing.py:532` | Org-level billing auth (org_admin / billing_admin / owner). |
| `mask_phone` | `backend/contractor_ops/msg_logger.py` | Redacts phone numbers in logs. |
| `_audit` | `backend/contractor_ops/router.py` | Writes an immutable audit-trail entry. |
| `validate_upload` | `backend/contractor_ops/upload_safety.py` | MIME + extension + magic-byte validation for all file uploads. |
| `getProjectBackPath` | `frontend/src/utils/navigation.js:17` | Canonical "back to project" path (role-aware). |
| `navigateToProject` | `frontend/src/utils/navigation.js:3` | Canonical "open project" navigation (role-aware entry point). |
| `t / tStatus / tCategory / tPriority / tRole / tSubRole / tTrade` | `frontend/src/i18n/index.js` | i18n helpers. Always use these — never inline Hebrew in JSX outside one-off labels. |
| `formatUnitLabel` | `frontend/src/utils/formatters.js` | Canonical unit label (handles `display_label` / `name` / `unit_no` fallbacks). |

---

## Reading order for a new contributor

1. [`../../CLAUDE.md`](../../CLAUDE.md) — deploy + standing rules (5 min).
2. [`../../PROJECT_OVERVIEW.md`](../../PROJECT_OVERVIEW.md) — what we're
   building and for whom (15 min).
3. [`../../CODEBASE_SUMMARY.md`](../../CODEBASE_SUMMARY.md) — directory
   tree (10 min).
4. This file (10 min).
5. The ADR for whatever file you're about to touch.
6. [`../refactor-backlog.md`](../refactor-backlog.md) — known
   opportunities; propose folding them when you're already in the file
   (Boy Scout Rule).
