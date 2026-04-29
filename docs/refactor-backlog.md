# BrikOps Refactor Backlog

**Last updated:** 2026-04-29 (DOCS PHASE 1A)
**Audience:** Cowork / future hires picking up "while you're already in
this file" cleanup. Living document.

The principle (per the codebase docs strategy): documentation BEFORE
refactor. ADRs in `docs/architecture/` describe WHY; this file
describes WHAT could be cleaned up next, with evidence.

**Boy Scout Rule:** when you touch a file that has an item below,
propose folding the cleanup into the current batch. Get Zahi's
approval before expanding scope, but propose it.

---

## #1 — Extract `CompaniesTab` from `ProjectControlPage.js`

**File(s):** `frontend/src/pages/ProjectControlPage.js` (~ line range
TBD; tab is declared inline in the 4115-line file)
**Severity:** Medium (onboarding friction; isolated diff target)
**What's wrong (data, not feeling):** ProjectControlPage is 4115
lines. After BATCH 5B Companies state dedupe, `CompaniesTab` has a
clean prop interface (`projectId`, `companies`, `companiesLoading`,
`onRefreshCompanies`) and is the most clearly extractable seam. See
[ADR-001](./architecture/adr-001-project-control-page.md).
**Proposed fix:** Move to `frontend/src/components/project/CompaniesTab.js`.
Pure relocation; no behavior change.
**Estimated time:** 1-2 hours.
**Fold into batch X when:** next batch that touches CompaniesTab
internals (e.g. a new column, search/filter, etc.).

## #2 — Extract `TeamTab` + `AddTeamMemberForm`

**File(s):** `frontend/src/pages/ProjectControlPage.js`
**Severity:** Medium
**What's wrong:** ~700 lines of self-contained team-management UI
inline in the parent. Receives `projectId`, `companies`, `trades`,
`prefillTrade`, `returnToDefect`, `myRole`, `isOrgOwner`,
`onRefreshCompanies` — clean prop interface.
**Proposed fix:** Move to `components/project/TeamTab.js` +
`components/project/AddTeamMemberForm.js`.
**Estimated time:** 2-3 hours.
**Fold into batch X when:** next batch that touches team membership
flows.

## #3 — Centralize defect status / priority configs

**File(s):** `frontend/src/pages/ProjectControlPage.js` (status pill
helpers + DEFECT_STATUS_CONFIG / DEFECT_PRIORITY_CONFIG declared
inline) and any consumer.
**Severity:** Low
**What's wrong:** Status/priority display configs (icon + color +
background per value) are declared inline in this file. Only one
consumer today, but adding a second consumer (e.g. a new
TaskListPage) would invite a copy-paste.
**Proposed fix:** Extract to `utils/defectStatusConfig.js`. Existing
i18n labels stay in `he.json`; only the display config moves.
**Estimated time:** 1 hour.
**Fold into batch X when:** next file outside ProjectControlPage
needs the same display config.

## #4 — Consolidate `STATUS_BUCKET_EXPANSION` + dashboard aggregation lists

**File(s):** `backend/contractor_ops/tasks_router.py:40` (the
canonical dict) AND the function-local `open_statuses` /
`handled_statuses` lists used by the dashboard KPI aggregation in
the same file.
**Severity:** Medium (drift surface; test-guarded but not eliminated)
**What's wrong:** Two declarations of "what counts as open / handled"
exist in the same file. BATCH 5F shipped a drift-guard test
(`backend/tests/test_status_buckets.py`) that catches mismatches,
but the structural drift surface is still there. See
[ADR-006](./architecture/adr-006-status-system.md).
**Proposed fix:** Derive `open_statuses` and `handled_statuses` from
`STATUS_BUCKET_EXPANSION` directly, no re-declaration.
**Estimated time:** 1-2 hours (plus re-running the drift test).
**Fold into batch X when:** next batch touching the dashboard KPI
aggregation OR the bucket expansion (e.g. adding a new status).

## #5 — Audit for any other shadow constants in backend

**File(s):** Whole backend; high-value targets: `handover_router.py`,
`qc_router.py`, `safety_router.py`, `billing.py`.
**Severity:** Low (one known incident eradicated; pattern could recur)
**What's wrong:** BATCH 5C found `TERMINAL_TASK_STATUSES` redefined
in `handover_router.py`, missing `'cancelled'`. Removed the local
copy. No systematic audit across the rest of the backend confirms
this was the only occurrence.
**Proposed fix:** `grep -rn '^[A-Z_]\+ = '` across `backend/` and
flag any constant that exists in `constants.py` AND a per-file
location.
**Estimated time:** 1 hour audit + variable fix time per finding.
**Fold into batch X when:** next batch touching constants.py OR any
of the shadow-prone files.

## #6 — Centralize duplicated frontend `STATUS_LABELS` maps

**File(s):** `frontend/src/pages/AdminUsersPage.js`,
`HandoverTabPage.js`, `AdminActivityPage.js`, `AdminDashboardPage.js`,
`BuildingDefectsPage.js`, `ApartmentDashboardPage.js`,
`UnitDetailPage.js`, `OrgBillingPage.js`, plus
`utils/qcLabels.js`, `utils/billingLabels.js`. (8+ files declare
their own `STATUS_LABELS` map.)
**Severity:** Medium
**What's wrong:** After BATCH 5C/5F/5G the maps are aligned, but
each page declares its own copy. The next status addition risks
silent drift. See [ADR-007](./architecture/adr-007-i18n.md).
**Proposed fix:** Replace local maps with `tStatus()` calls from
`frontend/src/i18n/index.js`. The labels already live in
`he.json["statuses"]`.
**Estimated time:** 2-3 hours (mostly mechanical).
**Fold into batch X when:** next batch touching any of the 8 listed
pages with a status display.

## #7 — UserDrawer native `<select>` desktop + RTL + fixed positioning bug

**File(s):** `frontend/src/components/UserDrawer.js` (553 lines).
**Severity:** Medium (Desktop-only UX bug; not visible to mobile users)
**What's wrong:** Three native `<select>` elements inside a
`position:fixed` RTL drawer escape ~600px on Desktop browsers
(Chrome / Firefox / Safari). Mobile WebView is fine because
Capacitor renders selects with native pickers. Deferred from
Batch 5D as Task #21.
**Proposed fix:** Migrate to Radix Select (already used elsewhere
for new code).
**Estimated time:** 2-3 hours.
**Fold into batch X when:** next batch touching the user profile
drawer OR explicitly tasked.

## #8 — `ProjectControlPage:3770` drops `?from=dashboard` URL param

**File(s):** `frontend/src/pages/ProjectControlPage.js:3770` (the
in-page לאישור shortcut button in the orange pending-approval
banner).
**Severity:** Low (UX edge case from BATCH 5H smart-back)
**What's wrong:** When the user clicks the orange "צפה" button at
line 3770 to jump to the pending_manager_approval defects view,
the navigate call rebuilds the URL without the `from=dashboard`
param. Subsequently clicking the back arrow lands on `/projects`
instead of `/dashboard`. Task #36, BATCH 5H follow-up. See
[ADR-008](./architecture/adr-008-navigation.md).
**Proposed fix:** Read `searchParams.get('from')` in the navigate
call and propagate it.
**Estimated time:** 30 minutes.
**Fold into batch X when:** next batch touching ProjectControlPage's
header / banner / approval flow.

## #9 — `handover_router.py:2336` — `$nin` missing `'done'`

**File(s):** `backend/contractor_ops/handover_router.py:2336`
**Severity:** Medium (correctness — done-but-not-approved handover
defects show as still-open in the per-building breakdown)
**What's wrong:** The dashboard aggregation excludes terminal
statuses inline:
```python
"status": {"$nin": ["closed", "approved", "cancelled"]},
```
But `'done'` is missing. `TERMINAL_TASK_STATUSES` (the canonical
set in `constants.py:1`) includes `{"closed", "approved", "done",
"cancelled"}`. Discovered in BATCH 5C audit; tracked as Task #27.
See [ADR-003](./architecture/adr-003-handover-router.md).
**Proposed fix:** Replace inline list with
`list(TERMINAL_TASK_STATUSES)` (already imported from
`constants.py`). Add a regression test.
**Estimated time:** 30 minutes (fix) + 1 hour (test).
**Fold into batch X when:** next batch touching the handover
dashboard aggregation.

## #10 — `force_close → aggregation → reopen` regression tests — **BLOCKING LAUNCH**

**File(s):** New test file `backend/tests/test_force_close_regression.py`;
covers `tasks_router.py` + `handover_router.py` + dashboard
aggregations.
**Severity:** **HIGH (blocks launch per BATCH 5C spec — Task #28)**
**What's wrong:** No regression coverage exists for the
force_close → aggregation → reopen path. BATCH 5C surfaced this
gap. The path is load-bearing for legal correctness (force-closed
defects must reopen on tenant complaint and re-appear in the
dashboard count).
**Proposed fix:** Test scenarios:
1. Create task → force_close → assert status=`'approved'` →
   re-fetch via dashboard aggregation → assert NOT in open count.
2. Reopen the force-closed task → assert status=`'open'` (or
   appropriate) → re-fetch via dashboard → assert IN open count.
3. Same for handover-spawned defects.
**Estimated time:** 4-6 hours.
**Fold into batch X when:** **Before launch.** Standalone batch.

## #11 — Migrate QC photo uploads from local disk to object storage

**File(s):** `backend/contractor_ops/qc_router.py` (line 99 `UPLOADS_DIR`
+ all callers).
**Severity:** Low (works at current scale; bottleneck post-launch)
**What's wrong:** QC stage photos write to local disk
(`backend/uploads/qc/`). Other modules use `services.object_storage`
for S3-backed storage. The legacy local-disk path is fine for the
internal tester volume but doesn't scale to multi-instance / multi-region.
**Proposed fix:** Migrate to `services.object_storage`. Add a
backfill script for existing files.
**Estimated time:** 6-8 hours (including backfill).
**Fold into batch X when:** post-launch, when QC volume justifies
it OR when adding a second backend instance.

## #12 — Future ADR for `qc_approvers_router` extraction

**File(s):** `backend/contractor_ops/qc_router.py` (the
`/api/qc/approvers` endpoints).
**Severity:** Low
**What's wrong:** Approver-config endpoints could split to a
sibling router for maintainability if approver modes expand
beyond `all` / `stages` (per-trade approvers being a likely
future).
**Proposed fix:** Write ADR-009 first, then split.
**Estimated time:** 2 hours ADR + 4 hours split.
**Fold into batch X when:** next batch adding a new approver
mode OR refactoring approver config.

## #13 — Remove org legal text fallback at `handover_router.py:926`

**File(s):** `backend/contractor_ops/handover_router.py:926`
**Severity:** Low (legacy fallback for completed migration)
**What's wrong:** The TODO at line 926 says "Remove org fallback
after migration verified." The migration to consolidate legal text
into `default_handover_legal_text_*` org fields was completed
Q1 2026 but the fallback wasn't removed because there's no audit
showing zero orgs still rely on the legacy
`org.handover_legal_sections` field.
**Proposed fix:** Run a one-off audit query against prod to
confirm zero orgs use the legacy field, then remove the fallback
block (lines 919-943).
**Estimated time:** 1 hour audit + 30 minutes removal.
**Fold into batch X when:** next batch touching handover legal
text flows.

## #14 — Extract `HANDOVER_TEMPLATE` literal to its own file

**File(s):** `backend/contractor_ops/handover_router.py:27` (the
~600-line literal Python dict).
**Severity:** Low
**What's wrong:** The default handover template is a 600-line dict
literal at the top of the router file. Splits cleanly to its own
module without behavior change.
**Proposed fix:** Move to
`backend/contractor_ops/handover_template_default.py` exporting
a single `HANDOVER_TEMPLATE` constant.
**Estimated time:** 30 minutes.
**Fold into batch X when:** next batch touching the default
template OR splitting handover_router for any reason.

## #15 — Future ADR for `billing.py` (2200 lines)

**File(s):** `backend/contractor_ops/billing.py` (2200 lines —
sibling to `billing_router.py`, owns the business logic).
**Severity:** Low (works; just deserves an ADR for the next
contributor)
**What's wrong:** `billing_router.py` is the HTTP surface;
`billing.py` is the logic — but the WHY of the split, the
`check_org_billing_role()` semantic, the founder-eligibility
helper, and `is_founder_enabled()` deserve their own ADR.
**Proposed fix:** Write ADR-010 covering `billing.py` business
logic.
**Estimated time:** 3-4 hours.
**Fold into batch X when:** next batch touching billing business
logic.

## #16 — Future split of PayPlus webhook into `payplus_router.py`

**File(s):** `backend/contractor_ops/billing_router.py` (PayPlus-
specific endpoints — checkout-create, webhook, status check).
**Severity:** Low (waiting on a trigger)
**What's wrong:** PayPlus is one of N possible payment processors;
co-locating provider-specific code with billing dispatch is fine
today (single processor) but doesn't scale to two.
**Proposed fix:** Extract when adding a second payment processor
(Stripe / Tranzila / etc.).
**Estimated time:** 6-8 hours when triggered.
**Fold into batch X when:** evaluating a second payment processor.

## #17 — Fix N+1 in task-detail endpoint

**File(s):** `backend/contractor_ops/tasks_router.py:493`
**Severity:** Low (acceptable at current scale)
**What's wrong:** TODO at line 493 — task-detail endpoint does 5
sequential lookups (project, building, floor, unit, assignee) for
display labels. ~50ms wasted at single-tester load; matters at
>500 active users.
**Proposed fix:** Replace with a `$lookup` aggregation pipeline
that resolves all five in one trip.
**Estimated time:** 3-4 hours (including pagination + tests).
**Fold into batch X when:** P95 task-detail latency > 500ms.

## #18 — Decide fate of frozen en/ar/zh i18n JSON files (post-launch)

**File(s):** `frontend/src/i18n/en.json`, `ar.json`, `zh.json`.
**Severity:** Low (post-launch decision)
**What's wrong:** These three files exist (438-439 lines each) but
are not maintained as new keys are added to `he.json` (now 686
lines). Pre-launch decision was to defer the cost. Post-launch:
either drop them and ship Hebrew-only, or fund a translation pass.
See [ADR-007](./architecture/adr-007-i18n.md).
**Proposed fix:** Decide. If keep, add a key-coverage CI check.
If drop, delete the files and remove the locale infrastructure
from `index.js`.
**Estimated time:** 1 hour decision + variable execution.
**Fold into batch X when:** post-launch language strategy is set.

## #19 — Project root has 60+ `spec-*.md` files and ad-hoc handoff docs

**File(s):** Project root (60+ `spec-*.md`, several `*_PROOF.md`,
multiple `HANDOFF*.md`, etc.).
**Severity:** Low (visual clutter; unclear which are current)
**What's wrong:** Project root has accumulated 100+ markdown files
across two years of milestones. Many are completed-spec artifacts
that could move to `attached_assets/` or `docs/archive/`.
**Proposed fix:** Audit each file. Move historical ones to
`docs/archive/`, keep only currently-relevant docs at root
(README.md, CLAUDE.md, PROJECT_OVERVIEW.md, CODEBASE_SUMMARY.md,
WEEKLY_CHANGELOG.md).
**Estimated time:** 2-3 hours audit + execution.
**Fold into batch X when:** dedicated cleanup batch (low priority).

## #20 — Future ADRs for un-ADR'd >1500-line files

**File(s):** `OrgBillingPage.js` (2256), `StageDetailPage.js` (2239),
`billing.py` (2200), `onboarding_router.py` (2125),
`safety_router.py` (1912), `TaskDetailPage.js` (1909),
`admin_router.py` (1613), `projects_router.py` (1603),
`OnboardingPage.js` (1543), `ProjectPlansPage.js` (1518).
**Severity:** Low (each file works; ADR is preventive maintenance)
**What's wrong:** 10 files >1500 lines without an ADR. Onboarding
friction risk for future contributors.
**Proposed fix:** Write one ADR per file when it next gets touched
heavily. Don't proactively ADR every file (over-documentation
cost).
**Estimated time:** 2-4 hours per ADR.
**Fold into batch X when:** any batch significantly touching one
of these files (Boy Scout Rule).

---

## How to add an item

```markdown
## #N — <short title>

**File(s):** path/to/file.ext:LINE-RANGE
**Severity:** Low / Medium / High
**What's wrong (data, not feeling):** [evidence]
**Proposed fix:** [1-2 sentences]
**Estimated time:** [hours]
**Fold into batch X when:** [next-touched suggestion]
```
