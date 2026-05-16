# #416 — Closed-Beta Batch 2b Patch 2 — Correct return URL + cancel banner

## What & Why

Two real-world issues from Zahi's first live test of Batch 2b:

### Issue 1 (CRITICAL) — "חזור לליקוי" lands on the wrong page

**What we did wrong:** The toast action in AddTeamMemberForm navigates to `/projects/${draft.projectId}/units/${draft.unitId}?reopenDefect=1`.

**What we assumed:** That URL maps to UnitDetailPage or ApartmentDashboardPage — pages that have NewDefectModal.

**What actually happens:** `App.js` routes `/projects/:projectId/units/:unitId` (no suffix) to `UnitHomePage` — the hub view with 3 menu cards (ליקויים / תוכניות / מסירה). UnitHomePage has no `NewDefectModal`, no `?reopenDefect=1` handler, and the param just stays in the URL. The user sees the hub menu instead of the restored defect form.

Real routes (from `App.js:366-449`):
- `/projects/:pid/units/:uid` → `UnitHomePage` (hub, no NewDefectModal)
- `/projects/:pid/units/:uid/tasks` → `UnitDetailPage` (has NewDefectModal)
- `/projects/:pid/units/:uid/defects` → `ApartmentDashboardPage` (has NewDefectModal)

**Root fix:** Stop guessing. Save the user's exact origin URL (`location.pathname`) inside the draft when they click "+ הוסף קבלן", and navigate back to that exact URL when they click "חזור לליקוי".

### Issue 2 — No way back if the user abandons the contractor-add flow

If the user enters the team tab and changes their mind (doesn't want to add a contractor), they're stuck: the "חזור לליקוי" button only appears in the post-save success toast. They have to manually navigate: back button → breadcrumbs → unit page. The draft sits in sessionStorage until it expires.

**Fix:** Show a persistent banner at the top of the Team tab whenever the URL carries `returnToDefect=1`. The banner has a "חזור לליקוי" button that does the same navigation as the post-save toast action, but lets the user abandon the team-add flow cleanly.

### Out-of-scope and stability

- The feature flags stay the same and both patches stay gated on `FEATURES.DEFECT_DRAFT_PRESERVATION`.
- `BottomSheetSelect.js` still zero diff.
- No change to the existing draft TTL (30 min), save/load/clear helpers, or unit-match/project-scope guards.
- No change to SelectField / GroupedSelectField / categoryBuckets.

---

## Done looks like

### Fix 1 — return URL is now exact

1. Open NewDefectModal from the unit's **tasks page** (`/projects/X/units/Y/tasks`).
2. Fill fields, click "+ הוסף קבלן".
3. DevTools → Application → Session Storage → `brikops_defect_draft_v1` → ✅ contains `returnUrl: "/projects/X/units/Y/tasks"`.
4. Add a contractor, click "חזור לליקוי".
5. ✅ URL becomes `/projects/X/units/Y/tasks?reopenDefect=1` (the original page — UnitDetailPage).
6. ✅ NewDefectModal auto-opens with draft restored.

Repeat with the user starting from **defects dashboard** (`/units/Y/defects`):
- ✅ `returnUrl` saved as `/projects/X/units/Y/defects`.
- ✅ Click "חזור לליקוי" → lands on ApartmentDashboardPage → modal opens.

### Fix 2 — cancel banner

1. From any NewDefectModal origin, click "+ הוסף קבלן".
2. ✅ Navigated to Team tab with URL `?tab=team&openInvite=1&returnToDefect=1&prefillTrade=...` (after the existing handler strips openInvite, only `tab=team&returnToDefect=1&prefillTrade=...` remains).
3. AddTeamMemberForm auto-opens.
4. ✅ A soft amber banner is visible at the top of the Team tab behind the form (when form is open) and in front (when form is closed): "חזרת מהליקוי — לחץ לחזרה בלי להוסיף חבר צוות" with a "חזור לליקוי" button.
5. Cancel the form (ביטול or X).
6. ✅ Banner is clearly visible above the team list.
7. Click "חזור לליקוי" on the banner.
8. ✅ Navigated to the saved returnUrl + `?reopenDefect=1`. Modal opens with draft restored.
9. Alternative flow: add a contractor successfully → toast still offers "חזור לליקוי" (unchanged).

### Regressions (MUST NOT BREAK)

1. ✅ Batch 2b happy path (Test A from the main Batch 2b spec) still works end-to-end — only difference is the returned URL is now exact.
2. ✅ Cross-project and unit-match guards still fire (from Patch 1).
3. ✅ Flag kill-switch still works.
4. ✅ Existing drafts without `returnUrl` (from pre-patch-2 sessions within the 30-min TTL window) still navigate somewhere reasonable via the fallback.
5. ✅ Team tab without `returnToDefect=1` shows NO banner.
6. ✅ `BottomSheetSelect.js` — still zero diff.

---

## Out of scope

- ❌ Persist the origin URL beyond sessionStorage (no localStorage, no backend draft endpoint).
- ❌ Add NewDefectModal to UnitHomePage (UnitHomePage is a hub — modals don't belong there).
- ❌ Auto-navigate back when the user cancels the form — require explicit click on the banner so cancel is reversible.
- ❌ Remember which tab/filter the user had on the origin page — just restore the path.
- ❌ Change the draft TTL (stays 30 min).
- ❌ Any change to `BottomSheetSelect.js`, `QuickAddCompanyModal.js`, `GroupedSelectField.js`, `categoryBuckets.js`.
- ❌ Any change to Batch 2b's existing guards (project-scope, unit-match, feature flags).
- ❌ Any backend change.
- ❌ Any new dependencies.

---

## Tasks

### Task 1 — Capture exact returnUrl when the user clicks "+ הוסף קבלן"

**File:** `frontend/src/components/NewDefectModal.js`

**Find with:** `grep -n "from 'react-router-dom'" frontend/src/components/NewDefectModal.js`

**Change 1 — extend the react-router-dom import:**

```diff
- import { useNavigate } from 'react-router-dom';
+ import { useNavigate, useLocation } from 'react-router-dom';
```

**Change 2 — add the location hook near the top of the component:**

**Find with:** `grep -n "const navigate = useNavigate" frontend/src/components/NewDefectModal.js`

```diff
  const navigate = useNavigate();
+ const location = useLocation();
```

**Change 3 — save `returnUrl` in the draft payload.**

**Find with:** `grep -n "saveDefectDraft({" frontend/src/components/NewDefectModal.js`

In the "+ הוסף קבלן" onClick, inside the `saveDefectDraft({ ... })` call, add a `returnUrl` line (place it as the last property, before the closing brace):

```diff
  saveDefectDraft({
    projectId,
    buildingId,
    floorId,
    unitId,
    category,
    title,
    description,
    priority,
    companyId,
    assigneeId,
    prefillData: prefillData || null,
+   returnUrl: location.pathname,
  });
```

**Why:** `location.pathname` captures the exact origin (e.g., `/projects/X/units/Y/tasks` or `/projects/X/units/Y/defects` or `/projects/X/tasks`). We intentionally skip `location.search` to avoid polluting the return URL with stale filter params — the user can re-apply filters after they come back.

**Do NOT:** Save `location.href` (includes origin + search, risks encoding issues) or `window.location.pathname` (bypasses react-router's state — stale during transitions). Use `useLocation()`.

---

### Task 2 — Add a shared helper for building the return URL

**File:** `frontend/src/utils/defectDraft.js`

Append a new exported function at the bottom of the file (after `hasDefectDraft`):

```js
/**
 * Builds the URL to navigate back to the defect creation flow.
 * Prefers the exact returnUrl saved in the draft; falls back to the
 * unit's defects dashboard if returnUrl is missing (legacy drafts).
 * Returns null if the draft doesn't have enough info to navigate.
 */
export function buildReturnToDefectUrl(draft) {
  if (!draft || !draft.projectId || !draft.unitId) return null;
  const base = draft.returnUrl || `/projects/${draft.projectId}/units/${draft.unitId}/defects`;
  const separator = base.includes('?') ? '&' : '?';
  return `${base}${separator}reopenDefect=1`;
}
```

**Why:** Shared logic between the post-save toast action AND the new cancel banner. Single source of truth for the fallback. Returns a plain string so callers can `navigate(url)` without branching.

**Do NOT:** Move the existing save/load/clear functions. Do NOT change the storage key. Do NOT change the TTL. Do NOT strip any query params from `base` — callers should pass intact `draft.returnUrl`.

---

### Task 3 — Switch the success toast action to use the helper

**File:** `frontend/src/pages/ProjectControlPage.js`

**Find with:** `grep -n "loadDefectDraft } from '../utils/defectDraft'" frontend/src/pages/ProjectControlPage.js`

**Change 1 — extend the import:**

```diff
- import { loadDefectDraft } from '../utils/defectDraft';
+ import { loadDefectDraft, buildReturnToDefectUrl } from '../utils/defectDraft';
```

**Change 2 — simplify the toast action.**

**Find with:** `grep -n "return-to-defect failed" frontend/src/pages/ProjectControlPage.js`

Replace the existing `returnAction.onClick` body (inside `AddTeamMemberForm`'s success path) with:

```diff
  const returnAction = shouldOfferReturn ? {
    label: 'חזור לליקוי',
    onClick: () => {
      try {
        const draft = loadDefectDraft();
        if (!draft) {
          toast.info('הטיוטה פגה או לא נמצאה');
          return;
        }
-       if (!draft.projectId || !draft.unitId) {
-         toast.info('חסר מידע לחזרה לליקוי');
-         return;
-       }
-       navigate(`/projects/${draft.projectId}/units/${draft.unitId}?reopenDefect=1`);
+       const url = buildReturnToDefectUrl(draft);
+       if (!url) {
+         toast.info('חסר מידע לחזרה לליקוי');
+         return;
+       }
+       navigate(url);
      } catch (err) {
        console.warn('[AddTeamMemberForm] return-to-defect failed', err);
        toast.error('שגיאה בחזרה לליקוי');
      }
    },
  } : undefined;
```

**Why:** Uses the shared helper. `draft.returnUrl` now drives the navigation (exact origin), fallback handles legacy drafts. Old behavior (missing projectId/unitId → info toast) preserved via the helper returning null.

**Do NOT:** Change `shouldOfferReturn`, `toastOpts`, the toast duration (15000), or any of the success-toast branches.

---

### Task 4 — Add the cancel banner at the top of TeamTab

**File:** `frontend/src/pages/ProjectControlPage.js`

**Find with:** `grep -n "const TeamTab = " frontend/src/pages/ProjectControlPage.js`

**Location:** Inside `TeamTab`, AT THE TOP of the rendered content — before the filter chips, before the list, and before the `<AddTeamMemberForm>` conditional.

**STEP 0 — INVESTIGATE FIRST:**

Before writing the banner JSX, locate the very first JSX element rendered by TeamTab. Run:

```bash
grep -n "return (" frontend/src/pages/ProjectControlPage.js | head -20
```

Find the `return (` inside `TeamTab` (between line 2418 and the function's closing brace, around 2745). Identify the outermost wrapper — typically a `<div className="...">`. The banner must be rendered as the FIRST child inside that wrapper.

**Change 1 — add a navigate hook (if not already present inside TeamTab).**

Verify: grep for `const navigate = useNavigate` inside TeamTab's body. If absent, add:

```js
const navigate = useNavigate();
```

at the top of `TeamTab` (after the existing `const { user: currentUser } = useAuth();` line).

**Change 2 — add the banner handler function.**

Inside `TeamTab`, add a new callback (place it near the existing `loadData` callback):

```js
const handleReturnToDefectCancel = useCallback(() => {
  try {
    const draft = loadDefectDraft();
    if (!draft) {
      toast.info('הטיוטה פגה או לא נמצאה');
      return;
    }
    const url = buildReturnToDefectUrl(draft);
    if (!url) {
      toast.info('חסר מידע לחזרה לליקוי');
      return;
    }
    navigate(url);
  } catch (err) {
    console.warn('[TeamTab] return-to-defect-cancel failed', err);
    toast.error('שגיאה בחזרה לליקוי');
  }
}, [navigate]);
```

**Change 3 — render the banner at the top of TeamTab's content.**

Immediately after the outermost wrapper's opening tag (the first `<div ...>` inside the `return (...)`), insert:

```jsx
{returnToDefect && (
  <div
    className="flex items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    dir="rtl"
  >
    <span className="flex-1">
      חזרת מהליקוי כדי להוסיף חבר צוות. אם התחרטת, אפשר לחזור לליקוי בלי לשמור.
    </span>
    <Button
      variant="outline"
      size="sm"
      onClick={handleReturnToDefectCancel}
      className="border-amber-300 bg-white text-amber-700 hover:bg-amber-100 active:bg-amber-200 whitespace-nowrap"
    >
      חזור לליקוי
    </Button>
  </div>
)}
```

**Why:** The banner is conditional on the `returnToDefect` prop (already passed from ProjectControlPage → TeamTab via Batch 2b). When the flag-ON user enters team tab from the defect flow, the banner is immediately visible above the form. Soft amber palette matches the existing "אין קבלנים" warning styling. Uses the existing `<Button>` component — no new design tokens.

**Do NOT:**
- ❌ Do NOT render the banner when `returnToDefect` is false (most common case — team tab opened normally).
- ❌ Do NOT navigate automatically. Require an explicit click on the banner button.
- ❌ Do NOT clear the draft when showing the banner. Clearing happens only inside NewDefectModal's restore effect after a successful return.
- ❌ Do NOT add the banner inside the `<AddTeamMemberForm>` conditional — the banner should also be visible when the form is closed (user cancelled).
- ❌ Do NOT change the `showAddForm` auto-open logic (`useState(!!prefillTrade)`). The banner sits alongside, not replaces.
- ❌ Do NOT make the banner sticky — a regular block element in normal flow is fine.
- ❌ Do NOT add close/dismiss "x" on the banner — the user either clicks the button to leave or ignores it; the banner disappears when `returnToDefect` is no longer in the URL.

---

## Relevant files

### Modified:
- `frontend/src/components/NewDefectModal.js` — `useLocation` import + hook + `returnUrl: location.pathname` in `saveDefectDraft`
- `frontend/src/pages/ProjectControlPage.js` — `buildReturnToDefectUrl` import, toast action refactored, TeamTab gets `useNavigate` + `handleReturnToDefectCancel` + banner JSX
- `frontend/src/utils/defectDraft.js` — new `buildReturnToDefectUrl` export

### Untouched (CRITICAL):
- `frontend/src/components/BottomSheetSelect.js` — zero diff
- `frontend/src/components/QuickAddCompanyModal.js` — zero diff
- `frontend/src/components/GroupedSelectField.js` — zero diff
- `frontend/src/config/features.js` — zero diff
- `frontend/src/utils/categoryBuckets.js` — zero diff
- `frontend/src/pages/UnitDetailPage.js` — zero diff (already handles `?reopenDefect=1`)
- `frontend/src/pages/ApartmentDashboardPage.js` — zero diff (already handles `?reopenDefect=1`)
- `frontend/src/pages/UnitHomePage.js` — zero diff (no NewDefectModal there; not the return target unless a legacy draft happened to save this path)
- `frontend/src/pages/ProjectTasksPage.js` — zero diff
- `backend/` — zero diff
- `frontend/package.json`, `package-lock.json` — zero diff

---

## DO NOT

- ❌ Do NOT touch `BottomSheetSelect.js`. Hard line from Batch 2b still in force.
- ❌ Do NOT modify the existing feature flags or add new ones.
- ❌ Do NOT alter Batch 2b's project-scope guard or unit-match guard in NewDefectModal's restore effect.
- ❌ Do NOT add a useEffect to UnitHomePage — it's a hub without NewDefectModal, so `?reopenDefect=1` wouldn't have a modal to open anyway. The fix is in the origin save + return navigate, not in adding the feature to more pages.
- ❌ Do NOT cache the draft's returnUrl in component state — always read fresh from sessionStorage via `loadDefectDraft()`.
- ❌ Do NOT persist returnUrl anywhere outside the draft (no localStorage, no cookies, no URL).
- ❌ Do NOT add an auto-dismiss timer to the banner. It stays visible as long as the user is in team tab with the param.
- ❌ Do NOT suppress the banner when the AddTeamMemberForm is open. The form is a bottom-sheet modal; the banner sits above the list content and is occluded naturally.
- ❌ Do NOT change the 15s toast duration from Patch 1.
- ❌ Do NOT change the 30-min sessionStorage TTL.
- ❌ Do NOT trim or normalize the `returnUrl` — store it verbatim from `location.pathname`. React Router will handle the navigation.
- ❌ Do NOT use `window.location.*` anywhere — use `useLocation()` / `useNavigate()` hooks only.

---

## VERIFY before commit

### 1. Grep sanity

```bash
# (a) useLocation added to NewDefectModal:
grep -n "useLocation" frontend/src/components/NewDefectModal.js
# Expected: 2 hits (import + hook call).

# (b) returnUrl is saved in the draft:
grep -n "returnUrl: location.pathname" frontend/src/components/NewDefectModal.js
# Expected: 1 hit.

# (c) buildReturnToDefectUrl exists:
grep -n "export function buildReturnToDefectUrl" frontend/src/utils/defectDraft.js
# Expected: 1 hit.

# (d) buildReturnToDefectUrl imported in ProjectControlPage:
grep -n "buildReturnToDefectUrl" frontend/src/pages/ProjectControlPage.js
# Expected: 3 hits (import + toast action usage + banner handler usage).

# (e) The old hard-coded return URL is gone:
grep -n 'navigate(`/projects/\${draft.projectId}/units/\${draft.unitId}?reopenDefect=1`)' frontend/src/pages/ProjectControlPage.js
# Expected: empty (or zero hits).

# (f) The banner conditional is present:
grep -n "{returnToDefect && (" frontend/src/pages/ProjectControlPage.js
# Expected: 1 hit (inside TeamTab's JSX).

# (g) TeamTab now uses useNavigate:
grep -cn "useNavigate" frontend/src/pages/ProjectControlPage.js
# Expected: at least 2 (top-level ProjectControlPage + AddTeamMemberForm + TeamTab = 3, but
# import/call patterns may collapse). The safe check is >=2.

# (h) Cancel handler exists:
grep -n "handleReturnToDefectCancel" frontend/src/pages/ProjectControlPage.js
# Expected: 2+ hits (declaration + banner onClick).

# (i) BottomSheetSelect still untouched:
git diff --stat frontend/src/components/BottomSheetSelect.js
# Expected: empty.

# (j) QuickAddCompanyModal still untouched:
git diff --stat frontend/src/components/QuickAddCompanyModal.js
# Expected: empty.

# (k) GroupedSelectField still untouched:
git diff --stat frontend/src/components/GroupedSelectField.js
# Expected: empty.

# (l) features.js still untouched:
git diff --stat frontend/src/config/features.js
# Expected: empty.

# (m) categoryBuckets.js still untouched:
git diff --stat frontend/src/utils/categoryBuckets.js
# Expected: empty.

# (n) UnitDetailPage + ApartmentDashboardPage untouched:
git diff --stat frontend/src/pages/UnitDetailPage.js frontend/src/pages/ApartmentDashboardPage.js
# Expected: empty.

# (o) UnitHomePage untouched:
git diff --stat frontend/src/pages/UnitHomePage.js
# Expected: empty.

# (p) Backend untouched:
git diff --stat backend/
# Expected: empty.

# (q) No package changes:
git diff frontend/package.json frontend/package-lock.json
# Expected: empty.

# (r) ProjectTasksPage still untouched:
git diff --stat frontend/src/pages/ProjectTasksPage.js
# Expected: empty.

# (s) Exactly three files changed:
git diff --name-only | sort
# Expected (exactly):
# frontend/src/components/NewDefectModal.js
# frontend/src/pages/ProjectControlPage.js
# frontend/src/utils/defectDraft.js
```

### 2. Build clean

```bash
cd frontend && REACT_APP_BACKEND_URL=https://example.com CI=true npm run build
```

Expected: no errors, no new warnings.

### 3. Manual tests

After deploy + hard refresh:

#### Test A — Return URL from UnitDetailPage (tasks)

1. Navigate to `/projects/X/units/Y/tasks` (UnitDetailPage).
2. Click "ליקוי חדש לדירה" → fill title, description, category, pick company.
3. Click "+ הוסף קבלן".
4. DevTools → Session Storage → `brikops_defect_draft_v1` → ✅ contains `"returnUrl":"/projects/X/units/Y/tasks"`.
5. Add a contractor → click "חזור לליקוי" in the toast.
6. ✅ URL becomes `/projects/X/units/Y/tasks?reopenDefect=1` — lands on UnitDetailPage.
7. ✅ NewDefectModal opens, draft restored, toast "הטיוטה שוחזרה. יש לצרף תמונות מחדש."

#### Test B — Return URL from ApartmentDashboardPage (defects)

1. Navigate to `/projects/X/units/Y/defects` (ApartmentDashboardPage).
2. Click "פתח ליקוי" → fill fields.
3. Click "+ הוסף קבלן".
4. ✅ Session storage has `"returnUrl":"/projects/X/units/Y/defects"`.
5. Complete contractor, click "חזור לליקוי".
6. ✅ Lands on `/projects/X/units/Y/defects?reopenDefect=1` — ApartmentDashboardPage.
7. ✅ Modal opens with restored state.

#### Test C — Cancel banner (new UX)

1. Do Test A up through step 3 (click "+ הוסף קבלן").
2. ✅ On team tab, a soft amber banner is visible above the form (or visible if you close the form).
3. Click X / ביטול on the AddTeamMemberForm to close it.
4. ✅ Banner is clearly visible at the top of the team tab.
5. Click "חזור לליקוי" on the banner.
6. ✅ Navigates to the saved returnUrl + `?reopenDefect=1`.
7. ✅ Modal opens with restored state.
8. ✅ SessionStorage cleared after restore.

#### Test D — No banner when returnToDefect is absent

1. Navigate directly to `/projects/X/control?tab=team` (no returnToDefect).
2. ✅ Team tab shows — no amber banner.
3. Open AddTeamMemberForm via the manual "+ הוסף חבר צוות" button.
4. Add a contractor, save.
5. ✅ Success toast has NO "חזור לליקוי" action (returnToDefect false).

#### Test E — Legacy draft without returnUrl (migration)

1. Manually set sessionStorage to a pre-patch shape:
   ```json
   {"createdAt": <now-ms>, "projectId":"X","unitId":"Y","title":"legacy"}
   ```
   (no `returnUrl`).
2. Open team tab with `?returnToDefect=1`.
3. Click the banner's "חזור לליקוי".
4. ✅ Falls back to `/projects/X/units/Y/defects?reopenDefect=1` (ApartmentDashboardPage).
5. ✅ Modal opens with "legacy" title restored.

#### Test F — Batch 2b happy path (regression)

1. Redo Test A/B from the main Batch 2b spec end-to-end (start to finish).
2. ✅ All steps pass — only difference is the return URL is now exact instead of bare `/units/:id`.

#### Test G — Flag kill-switch (regression)

1. Flip `DEFECT_DRAFT_PRESERVATION` to `false`. Redeploy. Hard refresh.
2. Click "+ הוסף קבלן" on a defect.
3. ✅ Navigates to `/projects/X/control?tab=companies` (pre-batch).
4. ✅ No banner in team tab (the URL doesn't have `returnToDefect=1` because the fallback didn't set it).
5. ✅ Session storage has NO `brikops_defect_draft_v1`.

#### Test H — Different-unit guard (regression from Patch 1)

1. Do Test A through step 3.
2. Without adding a contractor, navigate manually to a different unit (`/projects/X/units/Z/tasks`).
3. Open NewDefectModal.
4. ✅ Form opens empty. No restore toast. sessionStorage still has the draft.
5. Navigate back to Y's tasks page, open NewDefectModal.
6. ✅ Draft restores for Y.

#### Test I — Cross-project guard (regression from Patch 1)

1. Do Test A on project A through step 3.
2. Manually navigate to a different project's tasks page.
3. Open NewDefectModal.
4. ✅ Form opens empty. No restore toast.
5. Navigate back to project A, open on unit Y.
6. ✅ Draft restores.

---

## Commit message (exactly)

```
fix(defect-flow): use exact returnUrl + add cancel banner in team tab (#414 patch 2)

Patch 1's toast action hard-coded the return URL to
/projects/${pid}/units/${uid}?reopenDefect=1 — but that route maps to
UnitHomePage (a hub without NewDefectModal), not to the page the user
actually came from (UnitDetailPage or ApartmentDashboardPage). Users
clicking "חזור לליקוי" ended up on the unit home screen with a stale
?reopenDefect=1 in the URL and no modal.

Fix 1: NewDefectModal now captures location.pathname into the draft as
`returnUrl` when the user clicks "+ הוסף קבלן". A new shared helper
`buildReturnToDefectUrl(draft)` in utils/defectDraft.js appends
?reopenDefect=1 to that saved path (or falls back to .../defects for
legacy drafts from the 30-min TTL window). The post-save toast action
in AddTeamMemberForm now uses that helper.

Fix 2: added a persistent amber banner at the top of TeamTab when the
URL carries returnToDefect=1. The banner offers a "חזור לליקוי" button
that runs the same helper — so users who change their mind and don't
want to add a contractor can bail out cleanly without manual
navigation.

Both behaviors remain gated on FEATURES.DEFECT_DRAFT_PRESERVATION.
BottomSheetSelect.js still zero diff. QuickAddCompanyModal unchanged.
Backend unchanged. No new deps.
```

---

## Deploy

```bash
./deploy.sh --prod
```

OTA only.

**Before declaring fix complete, Zahi should:**

1. Hard refresh browser (Cmd+Shift+R) or close/reopen the native app.
2. Run Test A (return URL from tasks page — the main fix).
3. Run Test C (cancel banner — the UX addition).
4. Run Test F (Batch 2b happy path — regression).
5. If anything breaks, flip `DEFECT_DRAFT_PRESERVATION` to `false`, redeploy, investigate offline.

---

## Definition of Done

- [ ] `returnUrl` is saved in the draft via `location.pathname`
- [ ] `buildReturnToDefectUrl` exported from `defectDraft.js`
- [ ] Toast action uses the helper (no hard-coded URL)
- [ ] TeamTab banner visible when and only when `returnToDefect=1`
- [ ] Banner's button uses the helper
- [ ] All 19 grep checks pass
- [ ] `npm run build` clean
- [ ] Tests A–I pass
- [ ] `./deploy.sh --prod` succeeded
