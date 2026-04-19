# #277 — Fix 5 Navigation Bugs (Back Buttons + Overdue + QC Timeline)

## What & Why
Multiple navigation bugs across QC, Dashboard, and Handover flows cause users to exit the project when pressing "back", see stale QC timeline data, and encounter broken "overdue" filter navigation. These are all UX-breaking issues that confuse users and destroy trust in the app's navigation consistency. The core principle: **back should always go to the logical parent, never outside the project**.

## Done looks like
- ✅ Pressing back from any QC page (StageDetail, FloorDetail) returns to QC area, never exits project
- ✅ Pressing back from Dashboard returns to "מבנה" (structure) page
- ✅ QC timeline refreshes immediately after approve/reject/reopen actions
- ✅ Dashboard "באיחור" card navigates correctly and shows filtered overdue defects
- ✅ Pressing back from HandoverTabPage returns to handover lobby (all units), not to unit "מבנה"

## Out of scope
- Redesigning the navigation/breadcrumb system
- Adding browser history state management library
- Changing URL structure or routing config
- Modifying any backend endpoints (except investigating overdue bug #3)

---

## Tasks

### Task 1 — Fix back navigation in StageDetailPage (QC stage → floor)

**File:** `frontend/src/pages/StageDetailPage.js`

**Line 1530-1538** — current `goBack` function:
```javascript
const goBack = () => {
  if (window.history.length > 2) {
    navigate(-1);
  } else if (returnToPath) {
    navigate(returnToPath);
  } else {
    navigate(`/projects/${projectId}/floors/${floorId}`);
  }
};
```

**Change to:**
```javascript
const goBack = () => {
  // Always navigate to explicit QC path — never rely on browser history
  navigate(`/projects/${projectId}/floors/${floorId}`);
};
```

**Why:** `window.history.length > 2` is unreliable — users arriving via direct link, bookmark, or page refresh will have short history and `navigate(-1)` exits the project. The explicit path `/projects/{id}/floors/{floorId}` is the QC floor detail page which is the correct parent.

---

### Task 2 — Fix back navigation in FloorDetailPage (QC floor → building QC)

**File:** `frontend/src/pages/FloorDetailPage.js`

**Line 222** — current back button:
```javascript
<button onClick={() => { if (window.history.length > 2) { navigate(-1); } else { navigate(`/projects/${projectId}/qc`); } }}
```

**Change to:**
```javascript
<button onClick={() => navigate(`/projects/${projectId}/buildings/${buildingId}/qc`)}
```

If `buildingId` is available in the component (check the route params or loaded data). If not available, fall back to:
```javascript
<button onClick={() => navigate(`/projects/${projectId}/qc`)}
```

**Also fix line 167** — same pattern in error state button.

```
grep -n "window.history.length" frontend/src/pages/FloorDetailPage.js
```

---

### Task 3 — Fix back navigation in ProjectDashboardPage (dashboard → structure)

**File:** `frontend/src/pages/ProjectDashboardPage.js`

**Line 245** — current back button:
```javascript
<button onClick={() => navigate(`/projects/${projectId}/control`)}
```

**Change to:**
```javascript
<button onClick={() => navigate(`/projects/${projectId}/control`)}
```

This actually navigates to `/control` which is the defects/structure area. **Verify:** does `/projects/{id}/control` default to the "מבנה" tab? If it defaults to "ליקויים" instead, change to:
```javascript
<button onClick={() => navigate(`/projects/${projectId}/control?tab=structure`)}
```

Or if the structure tab has its own route:
```
grep -n "tab=structure\|מבנה\|structure" frontend/src/pages/ProjectControlPage.js | head -10
grep -rn "route.*control\|path.*control" frontend/src/App.js frontend/src/routes/ | head -10
```

**Investigate first:** figure out how tabs work in ProjectControlPage and ensure the back button from dashboard always lands on "מבנה".

---

### Task 4 — Fix QC timeline not refreshing after actions

**File:** `frontend/src/pages/StageDetailPage.js`

**Lines 930-931** (handleApprove):
```javascript
await load();
loadTimeline();  // ← NOT awaited
```

**Lines 952-953** (handleReject):
```javascript
await load();
loadTimeline();  // ← NOT awaited
```

**Lines 972-973** (handleReopen):
```javascript
await load();
loadTimeline();  // ← NOT awaited
```

**Fix:** Add `await` before each `loadTimeline()` call:
```javascript
await load();
await loadTimeline();
```

Do this in ALL three handlers: `handleApprove`, `handleReject`, `handleReopen`.

Also search for any other action handlers that modify stage state but don't refresh timeline:
```
grep -n "await load()" frontend/src/pages/StageDetailPage.js
```
If any of those lines are NOT followed by `loadTimeline()`, add it.

---

### Task 5 — Investigate Dashboard "באיחור" (overdue) navigation

**File:** `frontend/src/pages/ProjectDashboardPage.js` line 332
```javascript
onClick={() => navigate(`/projects/${projectId}/control?workMode=defects&overdue=true`))
```

**File:** `frontend/src/pages/ProjectControlPage.js` line 3017
```javascript
const urlOverdue = searchParams.get('overdue') === 'true';
```

**File:** `backend/contractor_ops/tasks_router.py` lines 224-229
```python
if overdue:
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    query['due_date'] = {'$lt': now_iso, '$exists': True, '$ne': None}
    if 'status' not in query:
        query['status'] = {'$nin': ['closed', 'approved']}
```

**STEP 0 — INVESTIGATE FIRST:**
1. Check if the dashboard KPIs endpoint (`stats_router.py` line 51) uses the same overdue logic as `tasks_router.py` line 224. The KPI counts overdue by `due_date < now`, but the tasks filter also checks `due_date $exists`. Mismatch?
2. Check what `workMode=defects` does in ProjectControlPage — does it properly switch to defects view?
3. Test the actual API call: `GET /tasks?project_id=X&overdue=true` — does it return data?
4. Check if defects in the demo project even have `due_date` set

```
grep -n "workMode" frontend/src/pages/ProjectControlPage.js | head -10
grep -n "due_date" backend/contractor_ops/stats_router.py
```

**Report findings before implementing any fix.**

---

### Task 6 — Fix back from HandoverTabPage (unit handover → handover lobby)

**File:** `frontend/src/pages/HandoverTabPage.js`

**Line 203** — current back button:
```javascript
onClick={() => navigate(`/projects/${projectId}/units/${unitId}`)}
```

This navigates to the **unit home page** (מבנה של הדירה). The user expects to return to the **handover overview** (lobby of all units).

**Change to:**
```javascript
onClick={() => navigate(`/projects/${projectId}/handover`)}
```

This takes the user back to the handover overview page showing all units in the handover grid.

---

## Relevant files

| File | Lines | Bug |
|------|-------|-----|
| `frontend/src/pages/StageDetailPage.js` | 1530-1538, 930-931, 952-953, 972-973 | #1, #2 |
| `frontend/src/pages/FloorDetailPage.js` | 167, 222 | #1 |
| `frontend/src/pages/ProjectDashboardPage.js` | 245, 332 | #3, #4 |
| `frontend/src/pages/ProjectControlPage.js` | 3017, 3043-3044 | #3 |
| `frontend/src/pages/HandoverTabPage.js` | 203 | #5 |
| `backend/contractor_ops/tasks_router.py` | 224-229 | #3 |
| `backend/contractor_ops/stats_router.py` | 51 | #3 |

## DO NOT
- ❌ Don't add react-router history management libraries
- ❌ Don't change URL routing structure in App.js or route config
- ❌ Don't change the HandoverProtocolPage back button (line 421) — it already correctly navigates to `/projects/{id}/units/{unitId}/handover`
- ❌ Don't modify the QC timeline API endpoint or backend logic (only fix frontend refresh)
- ❌ Don't change the KPI card component or its styling
- ❌ Don't use `window.history.length` checks in any new navigation code — always use explicit paths
- ❌ Don't touch StageDetailPage render logic, item management, or approval flow — only fix `goBack` and `loadTimeline` await

## VERIFY

### Bug 1 — QC Back Navigation
1. Navigate directly to a QC stage URL (paste in browser) → press back → should stay in QC area (floor detail), NOT exit project
2. Navigate: QC overview → building → floor → stage → press back → should go to floor detail
3. From floor detail → press back → should go to building QC list

### Bug 2 — QC Timeline
1. Open a QC stage with items → approve the stage → timeline should immediately show the approval event with current timestamp
2. Reject a stage → timeline should show rejection event
3. Reopen a stage → timeline should show reopen event

### Bug 3 — Dashboard Overdue
1. Open dashboard → see "באיחור" count → click it → should navigate to filtered defect list showing overdue items
2. If count is 0, clicking should show empty state "אין ליקויים באיחור"
3. Verify no 404 or permission error

### Bug 4 — Dashboard Back
1. Navigate to dashboard → press back → should go to "מבנה" tab, NOT exit project
2. Navigate directly to dashboard URL (paste in browser) → press back → same behavior

### Bug 5 — Handover Back
1. Open handover overview → click unit → see handover protocols → press back → should return to handover overview (unit grid), NOT to unit "מבנה"
2. From handover protocol detail → press back → should go to unit's handover list (this already works, don't break it)

---

**Execution order:** Tasks 1, 2, 6 (simple navigation fixes) → Task 4 (await fix) → Task 3 (investigate + fix dashboard back) → Task 5 (investigate overdue)

**STOP after Tasks 1+2+6 and report. Then continue with Task 4. Then investigate Task 5.**
