# #415 — Closed-Beta Batch 2b Patch — Cross-project draft guard + toast duration

## What & Why

A code review of Batch 2b (#414) surfaced one edge case and one UX nit that are both simple, low-risk single-line fixes.

### Issue 1 — Cross-project draft leak (SHOULD FIX → MUST FIX in this patch)

`NewDefectModal.js`'s draft-restore effect (lines ~151-167 after Batch 2b) has a unit-match guard, but the guard is gated on `hasPrefill`:

```js
if (hasPrefill && draft.unitId && prefillData?.unit_id && draft.unitId !== prefillData.unit_id) {
  return;
}
```

If `NewDefectModal` is opened from `ProjectTasksPage` (which passes only `{ project_id }` — no `unit_id`), `hasPrefill` is `false` and the guard short-circuits. A stale draft from project A could then silently restore into project B's defect form — the user would see project A's `title`/`description`/`category`/`companyId` appear inside a project B defect creation.

**Trigger sequence:**
1. User is on project A, opens NewDefectModal from a unit, fills fields, clicks "+ הוסף קבלן".
2. Draft saved with `projectId: A, unitId: U_A, title: "…"`.
3. User abandons the team-tab flow without clicking "חזור לליקוי".
4. Within 30 minutes, user navigates to project B's ProjectTasksPage and opens NewDefectModal.
5. `hasPrefill=false` → unit-match guard skipped → restore fires → project A's draft appears.

Rare, but real. The fix is one conditional before the unit-match guard.

### Issue 2 — 10-second toast might be too short for the return flow

The "חזור לליקוי" action is attached to the invite-success toast with `duration: 10000`. 10 seconds is tight for Hebrew readers who just finished typing contractor details. Bump to 15 seconds.

---

## Done looks like

### Test A — Cross-project guard (new)

1. On project A, open NewDefectModal from a unit. Fill title "דראפט A" + category + company. Click "+ הוסף קבלן".
2. ✅ Navigates to project A's team tab. Draft saved.
3. Manually navigate to a DIFFERENT project B (e.g., `/projects/B/tasks`).
4. Open NewDefectModal on project B (not via `?reopenDefect=1` — just a normal open).
5. ✅ Form opens EMPTY. No "הטיוטה שוחזרה" toast. Title is blank. sessionStorage still has the draft (not cleared since nothing matched).
6. Navigate back to project A → unit U_A → NewDefectModal.
7. ✅ Draft restores for project A. Toast "הטיוטה שוחזרה" appears.

### Test B — Same-project, different-unit guard still works (regression)

1. On project A, unit U_A, open NewDefectModal, fill fields, click "+ הוסף קבלן".
2. Draft saved.
3. Manually navigate to a different unit U_B on same project A.
4. Open NewDefectModal on U_B.
5. ✅ Form opens EMPTY (unit-match guard catches it — same project, different unit).

### Test C — Toast visible long enough

1. Do the full Batch 2b flow up to the "חזור לליקוי" toast.
2. ✅ Toast stays visible for ~15 seconds before auto-dismissing.
3. Clicking "חזור לליקוי" anytime in those 15s still works.

### Regressions (MUST NOT BREAK)

1. ✅ Test A from Batch 2b still passes (same-project, same-unit restore works end-to-end).
2. ✅ All flag-OFF behavior unchanged (kill-switches still work).
3. ✅ No new sessionStorage reads/writes.
4. ✅ `BottomSheetSelect.js` still zero diff.

---

## Out of scope

- ❌ Any change to how the draft is saved — only the restore path is touched.
- ❌ Any change to the unit-match guard — it stays as-is.
- ❌ Any change to `features.js`, `categoryBuckets.js`, `defectDraft.js`, `GroupedSelectField.js`.
- ❌ Any change to the 3 "+ הוסף חברה" buttons or to Batch 2a's Dialog guards.
- ❌ Any change to the "muted option looks dimmed in the trigger" cosmetic issue — that's a separate conversation (requires a UX call on whether to remove visual muting or keep it).
- ❌ Any change to ESLint config or any ESLint-related silencing — only act if the build actually warns.
- ❌ Any backend change.
- ❌ Any new dependencies.

---

## Tasks

### Task 1 — Add project-scope guard to NewDefectModal's restore effect

**File:** `frontend/src/components/NewDefectModal.js`

**Find with:** `grep -n "Restore in-progress draft" frontend/src/components/NewDefectModal.js`

**Location:** Inside the restore effect. Place the new guard BEFORE the existing unit-match guard.

**Change:**

```diff
  useEffect(() => {
    if (!FEATURES.DEFECT_DRAFT_PRESERVATION) return;
    if (!isOpen) return;
    const draft = loadDefectDraft();
    if (!draft) return;
+   // Project-scope guard: if the draft was saved for a different project than
+   // the one this modal is currently opened for, bail out. Covers the case
+   // where NewDefectModal is opened from ProjectTasksPage (no unit_id in
+   // prefillData, so the unit-match guard below can't fire).
+   if (draft.projectId && prefillData?.project_id && draft.projectId !== prefillData.project_id) {
+     return;
+   }
    if (hasPrefill && draft.unitId && prefillData?.unit_id && draft.unitId !== prefillData.unit_id) {
      return;
    }
    if (draft.category) setCategory(draft.category);
    ...
  }, [isOpen, hasPrefill, prefillData]);
```

**Why:** Two independent guards layered:
1. **New — project-scope:** Fires when we know both projectIds and they differ. Works even when `hasPrefill` is false.
2. **Existing — unit-scope:** Fires when we know both unitIds and they differ, and prefillData includes unit_id.

Either guard alone skips restore. Together they cover: same project same unit (restore), same project different unit (skip via unit guard), different project with or without unit_id (skip via project guard).

**Do NOT:** Move, modify, or remove the existing unit-match guard. Do NOT change the dependency array. Do NOT clear the draft when skipping — the draft must persist for a valid future match within its 30-min TTL.

---

### Task 2 — Bump the return-to-defect toast duration from 10s to 15s

**File:** `frontend/src/pages/ProjectControlPage.js`

**Find with:** `grep -n "duration: 10000" frontend/src/pages/ProjectControlPage.js`

**Location:** Inside `AddTeamMemberForm`'s success block (around line 1386 after Batch 2b).

**Change:**

```diff
- const toastOpts = returnAction ? { action: returnAction, duration: 10000 } : undefined;
+ const toastOpts = returnAction ? { action: returnAction, duration: 15000 } : undefined;
```

**Why:** 10 seconds is tight for a Hebrew-reading user who just finished a form. 15 seconds is a better fit without feeling sticky. Only applies when `returnAction` exists — toast calls without the action still use Sonner's default duration (unchanged).

**Do NOT:** Change any other toast config. Do NOT change the toast messages. Do NOT apply this duration to any other toast call in the app.

---

## Relevant files

### Modified:
- `frontend/src/components/NewDefectModal.js` — inside the restore effect, lines ~151-167
- `frontend/src/pages/ProjectControlPage.js` — one `duration` value inside AddTeamMemberForm's success block

### Untouched:
- Everything else. Zero other diffs.

---

## DO NOT

- ❌ Do NOT modify `frontend/src/components/BottomSheetSelect.js` — the hard line from Batch 2b is still in force.
- ❌ Do NOT modify `features.js`, `categoryBuckets.js`, `defectDraft.js`, `GroupedSelectField.js`.
- ❌ Do NOT modify `QuickAddCompanyModal.js`.
- ❌ Do NOT touch any other toast `duration` value in ProjectControlPage — only the one inside AddTeamMemberForm's success block.
- ❌ Do NOT change the order of the two guards — project guard must come FIRST (before the unit guard) so ProjectTasksPage-originating opens get caught.
- ❌ Do NOT clear the draft when either guard skips — it must persist until a valid match or TTL expiry.
- ❌ Do NOT add a third guard (e.g., buildingId or floorId) — over-specification risks false negatives.
- ❌ Do NOT change the dependency array of the restore effect.
- ❌ Do NOT modify any backend file.
- ❌ Do NOT add new package dependencies.

---

## VERIFY before commit

### 1. Grep sanity (this patch's own checks)

```bash
# (a) The new guard exists:
grep -n "draft.projectId && prefillData?.project_id && draft.projectId !== prefillData.project_id" frontend/src/components/NewDefectModal.js
# Expected: 1 hit.

# (b) The existing unit-match guard is still present and untouched:
grep -n "hasPrefill && draft.unitId && prefillData?.unit_id && draft.unitId !== prefillData.unit_id" frontend/src/components/NewDefectModal.js
# Expected: 1 hit.

# (c) Toast duration is now 15000 inside AddTeamMemberForm:
grep -n "duration: 15000" frontend/src/pages/ProjectControlPage.js
# Expected: 1 hit.

# (d) No stale 10000 duration remains:
grep -n "duration: 10000" frontend/src/pages/ProjectControlPage.js
# Expected: empty.

# (e) Only two files changed:
git diff --stat | grep -v "frontend/src/components/NewDefectModal.js\|frontend/src/pages/ProjectControlPage.js"
# Expected: empty.
```

### 2. Regression grep checks (inherited from Batch 2b — must still pass)

```bash
# (f) BottomSheetSelect untouched:
git diff --stat frontend/src/components/BottomSheetSelect.js
# Expected: empty.

# (g) Backend untouched:
git diff --stat backend/
# Expected: empty.

# (h) No package changes:
git diff frontend/package.json frontend/package-lock.json
# Expected: empty.

# (i) Flag references in all Fix A places still present (5+ hits):
grep -rn "FEATURES.DEFECT_DRAFT_PRESERVATION" frontend/src/
# Expected: 5+ hits (NewDefectModal button, NewDefectModal restore effect,
# ProjectControlPage toast shouldOfferReturn, UnitDetailPage effect,
# ApartmentDashboardPage effect).

# (j) Flag references in all Fix B places still present (2+ hits):
grep -rn "FEATURES.TRADE_SORT_IN_TEAM_FORM" frontend/src/
# Expected: 2+ hits (companyOptions useMemo + SelectField/GroupedSelectField conditional).

# (k) New files from Batch 2b untouched:
git diff --stat frontend/src/config/features.js frontend/src/utils/categoryBuckets.js frontend/src/utils/defectDraft.js frontend/src/components/GroupedSelectField.js
# Expected: empty.

# (l) QuickAddCompanyModal untouched:
git diff --stat frontend/src/components/QuickAddCompanyModal.js
# Expected: empty.

# (m) ProjectTasksPage untouched:
git diff --stat frontend/src/pages/ProjectTasksPage.js
# Expected: empty.
```

### 3. Build clean

```bash
cd frontend && REACT_APP_BACKEND_URL=https://example.com CI=true npm run build
```

Expected: no errors, no new warnings.

### 4. Manual tests

After deploy + hard refresh:

#### Test A — Cross-project guard (main patch fix)

1. Open NewDefectModal on project A, unit U_A. Fill title "דראפט A", category "hvac", pick a company.
2. Click "+ הוסף קבלן". Confirm navigation to project A's team tab + URL has `prefillTrade=hvac`.
3. Without adding a contractor, manually navigate to `/projects/<different_project_B>/tasks` (the tasks page of a different project).
4. Open NewDefectModal from the tasks page (click "הוסף ליקוי" or similar).
5. ✅ Form opens empty. No "הטיוטה שוחזרה" toast. Title blank.
6. DevTools → Session Storage: ✅ `brikops_defect_draft_v1` still present (not cleared).
7. Navigate back to project A, unit U_A, open NewDefectModal.
8. ✅ Draft restores with toast "הטיוטה שוחזרה".

#### Test B — Unit-match guard still works (regression)

1. Open NewDefectModal on project A, unit U_A. Fill fields. Click "+ הוסף קבלן".
2. Without adding a contractor, navigate to the same project A, unit U_B.
3. Open NewDefectModal on U_B.
4. ✅ Form opens empty. No "הטיוטה שוחזרה" toast. sessionStorage still has the draft.
5. Navigate back to U_A. Open NewDefectModal.
6. ✅ Draft restores for U_A.

#### Test C — Happy path (regression: Test A from Batch 2b)

1. Run the full Batch 2b Test A end-to-end.
2. ✅ All steps pass identically to Batch 2b shipping day.

#### Test D — Toast duration

1. Do the Batch 2b flow up to the "חזור לליקוי" toast.
2. ✅ Toast stays visible ~15s (count to 15, toast still there).
3. Clicking "חזור לליקוי" within that window works.
4. After 15s, toast auto-dismisses. Draft still in sessionStorage (until 30-min TTL).

#### Test E — Flag kill-switch (regression)

1. Flip `DEFECT_DRAFT_PRESERVATION: false`. Redeploy. Hard refresh.
2. Click "+ הוסף קבלן" → ✅ navigates to `?tab=companies` (pre-batch behavior).
3. Flip back to true. Redeploy.

---

## Commit message (exactly)

```
fix(defect-flow): add project-scope guard + bump return-toast duration (#414 patch)

Batch 2b review surfaced one edge case and one UX nit:

1. Cross-project draft leak: NewDefectModal's restore effect only had a
   unit-match guard, which is gated on hasPrefill. When the modal is
   opened from ProjectTasksPage (no unit_id in prefillData), the guard
   short-circuits — a stale draft from project A could silently restore
   into project B's defect creation. Added a project-scope guard BEFORE
   the unit-match guard so draft.projectId is checked against
   prefillData.project_id independently of hasPrefill.

2. Toast duration: the "חזור לליקוי" action toast lived for 10s. Bumped
   to 15s so Hebrew-reading users finishing a form have enough time to
   notice and click.

Two-line patch. No behavior change for the happy path. Flag-OFF behavior
unchanged. Draft is never cleared on skip — only on a successful restore
or 30-min TTL expiry.
```

---

## Deploy

```bash
./deploy.sh --prod
```

OTA only.

**Before declaring fix complete, Zahi should:**

1. Hard refresh browser (Cmd+Shift+R) or close/reopen the native app.
2. Run Test A (cross-project guard — the main fix).
3. Run Test C (Batch 2b happy path — regression).
4. If anything fails, flip `DEFECT_DRAFT_PRESERVATION` to `false`, redeploy, investigate.

---

## Definition of Done

- [ ] Project-scope guard added in `NewDefectModal.js` BEFORE the existing unit-match guard
- [ ] Toast duration changed from 10000 to 15000 (exactly one hit)
- [ ] All 13 grep checks pass (5 patch-specific + 8 regression)
- [ ] `npm run build` clean
- [ ] Test A passes (cross-project guard — patch's main fix)
- [ ] Test B passes (unit-match guard still works)
- [ ] Test C passes (Batch 2b happy path — regression)
- [ ] Test D passes (toast duration ~15s)
- [ ] Test E passes (flag kill-switch still works)
- [ ] `./deploy.sh --prod` succeeded
