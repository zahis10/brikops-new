# ADR-001 — ProjectControlPage.js

**Status:** Accepted
**Date:** 2026-04-29
**File:** `frontend/src/pages/ProjectControlPage.js` (4115 lines as of 2026-04-29)

## Why this exists

`ProjectControlPage` is the project's **home page** for management roles
(owner / admin / project_manager / management_team). It hosts seven
"work modes" (`structure`, `defects`, `qc`, `handover`, `plans`,
`safety`, `billing`) selected by the orange `workTabs` strip at the top,
plus a row of "management tabs" (`team`, `companies`, `data-export`,
plus contextual `settings` / `qc-template` / `handover-template` /
`billing`) that overlay the work-mode content.

The page is large because state for all seven work-modes is **lifted to
this parent component**. Sibling work-modes need to share several pieces
of state — selected building/floor/unit, hierarchy refresh signals,
KPI counts, billing snapshot — and React's prop-drilling cost from a
parent into nested tabs is lower than the synchronization cost of using
a context (which would also force re-renders across the entire tree on
every KPI tick). Splitting into seven separate routes was rejected
during BATCH 4: it broke the back-button stack, doubled API calls when
the user switched modes, and made the work-tabs animation feel jumpy.

The page works. 41 internal testers use it daily. The line count is a
documentation problem, not a correctness problem.

## Architectural decisions

- **Decision: lift work-mode state to the parent.** Why: sibling tabs
  share `hierarchy`, `companies`, `stats`, `qcSummary`, `billingInfo`.
  Trade-off accepted: 4115 lines of state and handlers in one file.
- **Decision: read `workMode` from `useSearchParams`, not React state.**
  Why: makes `?workMode=defects` shareable / bookmarkable, and the
  Capacitor hardware back button's `window.history.back()` lands on the
  previous work mode without extra logic. Trade-off: every work-mode
  switch is a URL change, which means a route render — but cheap because
  the component itself doesn't unmount.
- **Decision: KPI navigation cards (BATCH 5G/5H) navigate to
  `/projects/:id/control?workMode=defects&statusChip=...`** instead of
  setting React state directly. Why: same shareability benefit, plus
  the `from=dashboard` URL-param convention shipped in BATCH 5H lets
  the back arrow return to the dashboard instead of the project list.
  See [ADR-008](./adr-008-navigation.md) for the navigation conventions.
- **Decision: `STATUS_BADGES` and `KIND_LABELS` and `KIND_COLORS` are
  declared at module scope in this file**, not imported from
  `i18n/he.json`. Why: these are project-status (active/draft/suspended),
  unit-kind (residential/technical/...), and unit-color labels — small,
  stable, page-local. The cost of i18n indirection (an import + a `t()`
  call per render) wasn't justified for ~20 hardcoded strings that
  haven't changed in 9 months. **If they grow, migrate.**
- **Decision: `MGMT_TABS` and `SECONDARY_TABS` are static arrays at
  module scope.** Why: stable, no need for React state. Adding a tab
  means adding an entry — no further wiring.
- **Decision: BATCH 5B Companies dedupe**. The `companies` state was
  loaded by both `ProjectControlPage` AND `CompaniesTab` independently
  (silent double-fetch). 5B unified the source: parent loads,
  `CompaniesTab` receives via prop, child triggers refresh via
  `onRefreshCompanies` callback.

## Conventions used here

- `useSearchParams` for work-mode and tab routing. State in URL when
  shareable, in React when ephemeral.
- All API calls go through services in `frontend/src/services/api.js` —
  never direct `fetch` calls.
- Hebrew text inline for one-off labels; i18n helpers (`tTrade`, `tRole`,
  `tSubRole`, `t`, `tCategory`) for any value that comes from a constrained
  set with a known catalog.
- `dir="rtl"` on the root container, individual fields opt out with
  `dir="ltr"` (e.g. `InputField` for phone at line 1423).
- `BottomSheetModal` (defined locally at line 90) for mobile-first
  modals — uses Radix Sheet, not Dialog, because the mobile UX is a
  bottom sheet that becomes a centered modal on `sm:`+ screens.
- KPI counts come from `projectStatsService.get(projectId)` — never
  computed client-side from the task list (which would be paginated and
  wrong).
- Smart back-button (BATCH 5H, lines 3655-3667) reads
  `searchParams.get('from')` to decide whether to return to
  `/dashboard` or `/projects`. Hover tooltip changes accordingly.

## Natural seams (where to split if/when refactor happens)

The clearest extraction targets, in priority order:

- **`CompaniesTab`** (declared inside this file). After BATCH 5B
  dedupe, its props are minimal: `projectId`, `companies`,
  `companiesLoading`, `onRefreshCompanies`. Could move to
  `frontend/src/components/project/CompaniesTab.js` with no behavior
  change. **~600 lines saved.**
- **`TeamTab` + `AddTeamMemberForm`**. Similarly self-contained;
  receives `projectId`, `companies`, `trades`, `prefillTrade`,
  `returnToDefect`, `myRole`, `isOrgOwner`, `onRefreshCompanies`.
  **~700 lines saved.**
- **`AddCompanyForm` + `AddBuildingForm` + `AddFloorForm` +
  `AddUnitForm`**. Each is a distinct modal form with its own
  validation. Could move to `components/project/forms/`.
  **~500 lines saved.**
- **`DEFECT_STATUS_CONFIG` / `DEFECT_PRIORITY_CONFIG` / status pill
  helpers**. Already partially shared via `i18n/he.json` (statuses
  catalog), but display configs (icon + color + bg per status) are
  declared inline. Could become `utils/defectStatusConfig.js`.
  **~150 lines saved.**
- **`KpiSection`** — the dashboard-style cards at the top of the
  structure work-mode. Self-contained component; could move to
  `components/project/KpiSection.js`. Receives `stats`, `qcSummary`,
  `qcLoading`, `onViewDefects`, `onViewQc`. **~200 lines saved.**

If all five extractions happened, the parent would shrink to ~2000
lines — still large, but each tab/form would have its own file with a
focused diff in PRs.

## When to refactor

- **Trigger:** if 60% of frontend bugs in any quarter cluster in this
  file (today the cluster is more even — defects in Companies, Team,
  KPI navigation each show up in roughly equal volume).
- **Pre-requisite 1:** end-to-end tests covering the 7 work-modes
  switching back-and-forth without state loss (no current coverage).
- **Pre-requisite 2:** test for the URL-param contract — `?workMode=`,
  `?from=`, `?statusChip=`, `?prefillTrade=`, `?returnToDefect=`. These
  ship as a stable contract that drives multiple navigation flows
  (BATCH 5H smart-back depends on them).
- **Pre-requisite 3:** decide whether the extracted child components
  share state via props or context. Context risks over-rendering; props
  risk a drilling explosion. Spike one tab to compare.

## Recent changes

- 2026-04-29 (BATCH 5I): No change to this file — the back-button fix
  was on `HandoverOverviewPage` and `OrgBillingPage`. ProjectControlPage's
  smart back arrow (BATCH 5H, lines 3655-3667) was the reference pattern.
- 2026-04-28 (BATCH 5H): Smart back from `/control` to `/dashboard` via
  `?from=dashboard` URL param (lines 3655-3667). Added title tooltip
  ("חזרה לדשבורד" vs "חזרה לפרויקטים"). 6 KPI cards on
  ProjectDashboardPage now navigate here with the param. **Known
  follow-up:** the in-page לאישור shortcut at line 3770 drops the
  `from=dashboard` param when clicked — flagged as Task #36 / refactor
  backlog item #8.
- 2026-04-27 (BATCH 5G): `STATUS_BUCKET_EXPANSION['open']` expanded to
  6 statuses (added `pending_contractor_proof`, `reopened`,
  `waiting_verify`); the "בביצוע" KPI chip was removed because
  `in_progress` is now a subset of `open` for the dashboard count. Page
  consumes `stats.open` etc. — no change required here.
- 2026-04-26 (BATCH 5F): Added drift-guard test
  `backend/tests/test_status_buckets.py`. No file change here.
- 2026-04-22 (BATCH 5C): Status alignment — display labels (`he.json`)
  separated cleanly from DB values. No file change here, but the
  pattern is enforced going forward (see ADR-006).
- 2026-04-20 (BATCH 5B): Companies state dedupe — parent loads,
  `CompaniesTab` receives via prop. Removed the silent double-fetch.

## Refactor backlog items touching this file

- `#1` Extract `CompaniesTab` to its own file.
- `#2` Extract `TeamTab` + `AddTeamMemberForm`.
- `#3` Centralize `DEFECT_STATUS_CONFIG` / `DEFECT_PRIORITY_CONFIG`.
- `#8` In-page לאישור shortcut at line 3770 drops `from=dashboard`
  param (Task #36, BATCH 5H follow-up).

See [`../refactor-backlog.md`](../refactor-backlog.md) for full details.
