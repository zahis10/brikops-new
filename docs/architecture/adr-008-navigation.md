# ADR-008 — Navigation (cross-cutting)

**Status:** Accepted
**Date:** 2026-04-29
**Scope:** `frontend/src/utils/navigation.js`, `frontend/src/App.js`
(routing table), every page with a back button, every CTA that opens
a project-scoped page.

## Why this exists

Navigation in a multi-role app is one of the easiest places to leak
bugs:
- A back button that worked from one entry point silently breaks from
  another.
- A role-aware "open project" button needs to land different roles on
  different pages.
- Capacitor's hardware back / iOS swipe-back uses the browser history
  stack; in-app back arrows often do not.
- A bare `/projects/:projectId` looks like a sensible path but doesn't
  exist as a route — the app falls through to the project list.

This ADR captures the conventions that emerged from BATCH 5H
(smart-back from `/control` to `/dashboard`) and BATCH 5I
(broken-route fix on `/handover` and `/org-billing`), so that the
next page added doesn't re-discover them.

## The routing reality (`frontend/src/App.js`)

Every project-scoped route has a **suffix**. The full set (22 routes
matching `path="/projects/:projectId/...`):

`/control`, `/dashboard`, `/handover`, `/qc`, `/plans`, `/tasks`,
`/units`, `/buildings`, `/floors`, `/safety`, plus per-resource
detail pages like `/floors/:floorId`,
`/buildings/:buildingId/floors/:floorId/qc/units`, etc.

**There is no bare `/projects/:projectId` route.** Code that does
`navigate(\`/projects/${id}\`)` falls through to the project list
(`/projects`) — usually NOT what the user wanted. BATCH 5I fixed two
sites doing exactly this (`HandoverOverviewPage:231`,
`OrgBillingPage:894`).

## The canonical helpers (`frontend/src/utils/navigation.js`)

```js
const MANAGEMENT_ROLES = ['owner', 'admin', 'project_manager', 'management_team'];

export function navigateToProject(project, navigate) {
  const id = project.id || project._id;
  const role = project.my_role;
  localStorage.setItem('lastProjectId', id);

  if (MANAGEMENT_ROLES.includes(role)) {
    navigate(`/projects/${id}/control?workMode=structure`);
  } else if (role === 'contractor') {
    navigate('/projects');
  } else {
    navigate(`/projects/${id}/tasks`);
  }
}

export function getProjectBackPath(projectRole, projectId) {
  if (MANAGEMENT_ROLES.includes(projectRole)) {
    return `/projects/${projectId}/control`;
  }
  return '/projects';
}
```

- **`navigateToProject(project, navigate)`** — canonical "open
  project" entry point. Reads the user's project role and lands them
  on the right home page. Use this from the project list / project
  switcher.
- **`getProjectBackPath(projectRole, projectId)`** — canonical "back
  to project" path. Use this from any in-project page that needs to
  return to the project's home.

**Use these instead of inlining navigate paths** unless you have a
specific reason (and document it inline).

## Architectural decisions

- **Decision: project-scoped routes have suffixes; navigation must
  match.** Why: lets the routing table describe meaningful
  destinations (control / dashboard / handover) instead of an opaque
  `/projects/:id` that needs further routing inside the page.
  Trade-off accepted: every back-to-project path needs the suffix
  too. **Documented in ADR text and refactor-backlog item, not just
  code.**

- **Decision: `?workMode=structure` is the default landing tab.** Why:
  it's the project's "home" — the structure tree is what 80% of
  management actions start from. The `getProjectBackPath` helper
  doesn't append it (so a back from a deep page lands you on the
  most recent work mode), but `navigateToProject` does (entering
  fresh, you want the default).

- **Decision: smart back from `/control` reads `?from=` URL param
  (BATCH 5H).** Pattern at `ProjectControlPage.js:3655-3667`:
  ```js
  if (searchParams.get('from') === 'dashboard') {
    navigate(`/projects/${projectId}/dashboard`);
  } else {
    navigate('/projects');
  }
  ```
  Why: keeps the back stack consistent with the entry stack. KPI cards
  on the dashboard pass `?from=dashboard`; the back arrow respects it.

- **Decision: tooltip text changes with destination.** The smart-back
  pattern also updates `title=` based on `from`:
  `"חזרה לדשבורד"` vs `"חזרה לפרויקטים"`. The user knows where the
  arrow will land before clicking. Same applied in BATCH 5I to
  `HandoverOverviewPage` (always "חזרה לפרויקט" because the destination
  is universal).

- **Decision: Capacitor hardware back uses
  `window.history.back()`** (App.js:513-519). Why: the in-app arrow
  is for explicit user intent; the hardware back is "go back in the
  history stack" — these are different mental models and shouldn't
  share code. The smart-back pattern only affects users who tap the
  visible icon. iOS swipe-back also follows the history stack.

- **Decision: KPI navigation cards use URL params, not React state.**
  Why: shareable / bookmarkable, plus the smart-back pattern needs
  the params to be in the URL to read them on the next page. KPI
  cards on `ProjectDashboardPage` navigate with
  `?from=dashboard&statusChip=...`.

- **Decision: `state.returnTo` for task drill-downs.** When a task
  detail page is opened from a list, `navigate('/tasks/...', {state: {returnTo: '/projects/X/control?workMode=defects'}})`
  carries the return target. Used by the task detail page's back
  arrow when it can't infer the source from history (e.g. deep-linked
  from a notification).

## Conventions used here

- **Open a project**: `navigateToProject(project, navigate)`.
- **Back to project home**: `navigate(getProjectBackPath(role, id))`
  or hardcode `/projects/${id}/control?workMode=structure` if the
  caller knows the destination is universal (e.g. a back arrow in the
  handover page that should always land on the structure view —
  BATCH 5I pattern).
- **Add a tooltip to icon-only back arrows** (`title="חזרה לפרויקט"`)
  — without a visible label, the affordance is unclear. Mobile
  WebView shows the tooltip on long-press; desktop shows it on hover.
- **Pass intent forward via URL params** (`?from=dashboard`,
  `?statusChip=...`) when the next page needs to know where it came
  from. Don't push to localStorage / sessionStorage for this — URL
  params are shareable and survive a page refresh.
- **Don't combine** `navigate(...)` with `state.returnTo` AND URL
  param `?from=...` — pick one mechanism per flow.

## Forbidden patterns (with reasons)

| Pattern | Why it's forbidden |
|---------|---------------------|
| `navigate(\`/projects/${id}\`)` | No such route; falls through to project list. BATCH 5I fixed two instances. |
| Inlining role-based routing logic | The `MANAGEMENT_ROLES` list is in `navigation.js`. If you inline `if (role === 'project_manager') navigate(...)` you'll miss `owner`, `admin`, `management_team` — and the next role addition breaks your code silently. |
| Icon-only back buttons without `title=` | Affordance is invisible. Hebrew tooltip pattern: `title="חזרה לפרויקט"` (universal) or condition on `from` (smart-back pattern from 5H). |
| Reading `from=dashboard` and not propagating it | If you re-navigate from a smart-back-aware page (e.g. an in-page CTA shortcut), strip or propagate `from=` consciously. The in-page לאישור shortcut at `ProjectControlPage:3770` currently drops it — flagged as Task #36 / refactor-backlog item #8. |

## Recent changes

- 2026-04-29 (BATCH 5I): Fixed `HandoverOverviewPage:231` and
  `OrgBillingPage:894` — both were calling `navigate(\`/projects/${id}\`)`
  and falling through. Now route to
  `/projects/${id}/control?workMode=structure`. Tooltip added to
  HandoverOverviewPage (icon-only arrow). Bonus regression sweep
  confirmed the broken `/projects/${...}` pattern is fully eradicated
  from `frontend/src/`.
- 2026-04-28 (BATCH 5H): Smart-back pattern shipped on
  `ProjectControlPage` (lines 3655-3667). `?from=dashboard` URL
  param + role-aware destination + tooltip per destination. 6 KPI
  cards on `ProjectDashboardPage` updated to pass the param.
  Breadcrumb updated. **Known follow-up:** `ProjectControlPage:3770`
  drops the param when clicked — Task #36.

## When to refactor

- **Trigger:** when a 4th destination joins the smart-back pattern
  (currently the back arrow handles 2 destinations). At 4+, a small
  helper `getSmartBackPath(searchParams, projectId)` replaces the
  inline `if/else`.
- **Trigger:** if React Router v7 Data Routers are adopted, the
  state-vs-URL trade-offs change.
- **Pre-requisite:** end-to-end test for the back-button matrix —
  for each entry source × each destination, assert the back button
  lands on the source. Today validated by Zahi's manual smoke.

## Refactor backlog items related

- `#7` UserDrawer.js native `<select>` desktop+RTL+fixed positioning
  bug (Task #21).
- `#8` `ProjectControlPage:3770` drops `from=dashboard` when the
  in-page לאישור shortcut is clicked (Task #36).

See [`../refactor-backlog.md`](../refactor-backlog.md).
