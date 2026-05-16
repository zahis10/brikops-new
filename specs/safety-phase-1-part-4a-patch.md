# Task #404a — Safety Phase 1 Part 4a — Patch: role guard + code cleanup

**Scope:** 2 files, ~12 lines changed, 1 removed. No new deps, no backend changes.

**Why:** Part 4 (commits `bd4ef73` + `e7970cc`) shipped cleanly, code review approved — but three small things got missed or over-coded:

1. **`App.js` — missing `allowedRoles` on ProtectedRoute.** The route is open to any authenticated user; contractors who hit the URL directly load the page, make 5 API calls, get 403, then see `SafetyForbidden`. Works but wasteful. `ProtectedRoute` does support `allowedRoles` (verified — defined at `App.js:89`, checked at line 135, existing usage at line 270 for `project_manager`).

2. **`SafetyHomePage.js` — unused `incidents` state.** A 5th `listIncidents` call was added to `Promise.all` alongside an `eslint-disable` for the unused state variable. The incidents count already comes from `breakdown.incidents_last_90d` on the score response. The extra call + state adds network load for zero visible output.

3. **`SafetyHomePage.js` — severity maps double-keyed.** `SEVERITY_HE` and `SEVERITY_COLOR` each contain both string keys (`'1'/'2'/'3'`) and numeric keys (`1/2/3`). Backend stores severity as strings (verified in Part 3a review). Numeric keys are dead code.

---

## Fix 1 — Add `allowedRoles` to the safety route

**File:** `frontend/src/App.js`

Locate the safety route (added in Part 4, around line 324):

**BEFORE:**

```javascript
<Route
  path="/projects/:projectId/safety"
  element={
    <ProtectedRoute>
      <SafetyHomePage />
    </ProtectedRoute>
  }
/>
```

**AFTER:**

```javascript
<Route
  path="/projects/:projectId/safety"
  element={
    <ProtectedRoute allowedRoles={['project_manager', 'management_team', 'owner', 'admin']}>
      <SafetyHomePage />
    </ProtectedRoute>
  }
/>
```

**Role set rationale:** mirrors the `hidden` list on the `safety` workTabs entry in `ProjectControlPage.js:3503` (`['owner','admin','project_manager','management_team']`). Contractors who try the direct URL → immediate redirect to `/projects` (that's what ProtectedRoute does on role mismatch; see `App.js:135-137`). `owner`/`admin` with no project membership still go through → land on `SafetyForbidden` from the backend's `_check_project_access`. That's acceptable and matches how `dashboard` + `qc` behave today.

---

## Fix 2 — Remove unused `incidents` state + 5th API call

**File:** `frontend/src/pages/SafetyHomePage.js`

### 2.1 Remove the state declaration

**BEFORE (around line 27-29):**

```javascript
  const [workers, setWorkers] = useState({ items: [], total: 0 });
  // eslint-disable-next-line no-unused-vars
  const [incidents, setIncidents] = useState({ items: [], total: 0 });
  const [flagOff, setFlagOff] = useState(false);
```

**AFTER:**

```javascript
  const [workers, setWorkers] = useState({ items: [], total: 0 });
  const [flagOff, setFlagOff] = useState(false);
```

### 2.2 Remove the 5th fetch + setter

**BEFORE (inside the `Promise.all` block):**

```javascript
        const [scoreResp, docsResp, tasksResp, workersResp, incidentsResp] = await Promise.all([
          safetyService.getScore(projectId).catch((e) => ({ __err: e })),
          safetyService.listDocuments(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listTasks(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listWorkers(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listIncidents(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
        ]);
        if (cancelled) return;

        const responses = [scoreResp, docsResp, tasksResp, workersResp, incidentsResp];
```

**AFTER:**

```javascript
        const [scoreResp, docsResp, tasksResp, workersResp] = await Promise.all([
          safetyService.getScore(projectId).catch((e) => ({ __err: e })),
          safetyService.listDocuments(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listTasks(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
          safetyService.listWorkers(projectId, { limit: 50 }).catch((e) => ({ __err: e })),
        ]);
        if (cancelled) return;

        const responses = [scoreResp, docsResp, tasksResp, workersResp];
```

### 2.3 Remove the setIncidents call

**BEFORE (inside the success branch after the 404/403 checks):**

```javascript
        setScoreData(scoreResp);
        setDocs(docsResp || { items: [], total: 0 });
        setTasks(tasksResp || { items: [], total: 0 });
        setWorkers(workersResp || { items: [], total: 0 });
        setIncidents(incidentsResp || { items: [], total: 0 });
```

**AFTER:**

```javascript
        setScoreData(scoreResp);
        setDocs(docsResp || { items: [], total: 0 });
        setTasks(tasksResp || { items: [], total: 0 });
        setWorkers(workersResp || { items: [], total: 0 });
```

**Note:** `safetyService.listIncidents` stays in `services/api.js` — Part 5 will likely use it. We're only removing the call from the Home page, not the service method.

---

## Fix 3 — Simplify severity maps

**File:** `frontend/src/pages/SafetyHomePage.js`

Around line 14-18, remove the numeric-key entries.

**BEFORE:**

```javascript
const SEVERITY_HE = { '1': 'נמוכה', '2': 'בינונית', '3': 'גבוהה', 1: 'נמוכה', 2: 'בינונית', 3: 'גבוהה' };
const SEVERITY_COLOR = {
  '1': 'bg-blue-100 text-blue-800', '2': 'bg-amber-100 text-amber-800', '3': 'bg-red-100 text-red-800',
  1: 'bg-blue-100 text-blue-800', 2: 'bg-amber-100 text-amber-800', 3: 'bg-red-100 text-red-800',
};
```

**AFTER:**

```javascript
const SEVERITY_HE = { '1': 'נמוכה', '2': 'בינונית', '3': 'גבוהה' };
const SEVERITY_COLOR = {
  '1': 'bg-blue-100 text-blue-800',
  '2': 'bg-amber-100 text-amber-800',
  '3': 'bg-red-100 text-red-800',
};
```

**Rationale:** Backend Part 1 defines `SafetySeverity` as string enum `"1"/"2"/"3"`. Mongo stores these as strings. The JSON response preserves them as strings. In JavaScript, object property lookup coerces numeric keys to strings anyway (`obj[1] === obj['1']`) — so even if the backend accidentally sent an integer one day, `SEVERITY_HE[1]` would still find `SEVERITY_HE['1']`. The numeric entries are truly dead code.

---

## DO NOT

- ❌ Do NOT remove `listIncidents` from `services/api.js` — keep it for Part 5.
- ❌ Do NOT change the role set in the nav tab's `hidden` check — it's already correct.
- ❌ Do NOT add `contractor` to `allowedRoles` — the whole point is to exclude them.
- ❌ Do NOT introduce a `SafetyNotFound` or custom 403 page — `Navigate to="/projects"` is the house pattern for role-mismatch (see `App.js:136`).
- ❌ Do NOT rename `SEVERITY_HE` or `SEVERITY_COLOR` — only remove the dead numeric keys.
- ❌ Do NOT touch any other file — the diff should be exactly 2 files: `App.js` + `SafetyHomePage.js`.
- ❌ Do NOT run this as a separate deploy. Fold it into the next logical batch (Part 5 start) OR commit now, whichever is convenient. Either is fine — no urgency since behavior is already correct; this is polish.

---

## VERIFY before commit

### 1. Grep sanity

```bash
# (a) allowedRoles prop on the safety route:
grep -A3 "path=\"/projects/:projectId/safety\"" frontend/src/App.js | grep "allowedRoles"
# Expected: one hit with the 4-role list.

# (b) No more `incidents` state:
grep -n "\[incidents, setIncidents\]\|setIncidents\|eslint-disable.*no-unused-vars" frontend/src/pages/SafetyHomePage.js
# Expected: EMPTY.

# (c) No more 5th API call on the Home page:
grep -n "listIncidents" frontend/src/pages/SafetyHomePage.js
# Expected: EMPTY. (The service method in api.js stays — don't grep there.)

# (d) listIncidents still exported from api.js (for Part 5):
grep -n "listIncidents" frontend/src/services/api.js
# Expected: at least 2 hits (function declaration + method body).

# (e) No more numeric severity keys:
grep -n "1: 'bg-blue\|2: 'bg-amber\|3: 'bg-red\|1: 'נמוכה\|2: 'בינונית\|3: 'גבוהה" frontend/src/pages/SafetyHomePage.js
# Expected: EMPTY.
```

### 2. Build clean

```bash
cd frontend
npm run build
# Expected: no new warnings. The eslint-disable comment being gone should actually
# reduce the warning count by one.
```

### 3. Manual — contractor redirect

Log in as a `contractor` user. Manually enter `/projects/<project_id>/safety` in the URL bar → expect **immediate redirect to `/projects`**. No loading spinner, no 5 API calls in Network tab, no `SafetyForbidden` screen flash.

### 4. Manual — PM still works

Log in as a `project_manager` user → navigate to `/projects/<project_id>/safety` via nav tab → full page renders as before. Nothing broken.

### 5. Manual — Network tab

With PM logged in, open DevTools Network and navigate to `/safety`. Expect exactly **4 safety API calls**: `/score`, `/documents`, `/tasks`, `/workers`. No `/incidents` call. (Plus one call to `/projects/:id` for the header project name.)

### 6. No other files modified

```bash
git diff --stat | grep -v "frontend/src/App.js\|frontend/src/pages/SafetyHomePage.js"
# Expected: empty.
```

---

## Commit message (exactly)

```
fix(safety): Part 4a — add allowedRoles guard, drop unused incidents
fetch + dead severity keys

1) App.js: add allowedRoles=['project_manager','management_team','owner',
   'admin'] to the /projects/:projectId/safety route's ProtectedRoute.
   Matches the hidden-rule on the workTabs entry in ProjectControlPage
   and bounces contractors at the router level instead of letting them
   load the page and hit the backend 5 times for a 403.

2) SafetyHomePage.js: remove the unused `incidents` state and its
   listIncidents() call from Promise.all. The count is already in
   scoreData.breakdown.incidents_last_90d. Drops the eslint-disable
   comment too. listIncidents stays exported from services/api.js for
   Part 5 consumers.

3) SafetyHomePage.js: remove the numeric key duplicates from
   SEVERITY_HE and SEVERITY_COLOR. Backend stores severity as string
   enum "1"/"2"/"3" (Part 1 schema); JS object lookup coerces numeric
   keys to strings anyway, so the numeric entries were dead.

No backend changes, no new deps.
```

---

## Deploy

```bash
./deploy.sh --prod
```

זה ה-commit וה-push. אפשר לדחוף מיד או לצרף לתחילת Part 5 — שניהם בסדר.

אחרי ה-deploy — שלח ל-Zahi:
- `git log -1 --stat`
- Unified diff (צפוי ~15 lines diff, עם הסרות)
- פלט של 6 הבדיקות מ-VERIFY

---

## Definition of Done

- [ ] `allowedRoles` added to `/safety` ProtectedRoute with 4-role list
- [ ] `incidents` state + `setIncidents` removed
- [ ] `listIncidents` call removed from `Promise.all`
- [ ] `eslint-disable-next-line no-unused-vars` comment removed
- [ ] `SEVERITY_HE` numeric keys removed (6 entries → 3)
- [ ] `SEVERITY_COLOR` numeric keys removed (6 entries → 3)
- [ ] 6 grep checks from VERIFY §1 pass
- [ ] Manual contractor redirect test passes
- [ ] Manual PM test — page works as before
- [ ] Network tab shows 4 safety calls, not 5
- [ ] `git diff --stat` shows only 2 files touched
- [ ] `./deploy.sh --prod` succeeded OR folded into next commit
- [ ] No new deps, no backend changes
