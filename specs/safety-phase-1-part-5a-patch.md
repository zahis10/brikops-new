# Task #408a — Safety Phase 1 Part 5a — Patch: loading gate + polish

**Scope:** 2 files, ~25 lines changed. No new deps, no backend changes, no new endpoints.

**Why:** Part 5 (commit shown in #408 diff) shipped clean — 9 verify checks pass, 3 focus points correct, 3 unsolicited improvements. Code review flagged one SHOULD FIX and two NICE TO HAVE items. This patch folds all three in before Phase 1 closes.

**3 fixes:**

1. **`SafetyHomePage.js` — loading gate blocks on best-effort enrichment.** The main useEffect awaits `getMemberships` + `projectCompanyService.list` before `setLoading(false)` fires. On cold cache that's +200-500ms of skeleton time for data the main page doesn't need to render. Move to separate useEffect.
2. **`SafetyHomePage.js` — double docs fetch on initial mount.** The filter useEffect has `loading` in its deps, so it re-fires when loading flips to false and re-fetches documents that were already fetched by the main `Promise.all`. One wasted API call per page load.
3. **`SafetyExportMenu.js` — `decodeURIComponent` can throw.** On a malformed filename header the `download` flow crashes. Wrap in try/catch. Very unlikely in practice (backend filenames are plain ASCII), but zero-cost hardening.

---

## Fix 1 — Move memberships fetch out of the loading gate

**File:** `frontend/src/pages/SafetyHomePage.js`

### 1.1 Remove the memberships/companies fetch from the main useEffect

Find this block (around lines 94-119 of the current file — the section inside the main useEffect, after `setScoreData/setDocs/setTasks/setWorkers`):

**BEFORE:**

```javascript
        setScoreData(scoreResp);
        setDocs(docsResp || { items: [], total: 0 });
        setTasks(tasksResp || { items: [], total: 0 });
        setWorkers(workersResp || { items: [], total: 0 });

        // Best-effort fetch for filter dropdowns. Failures are silent —
        // dropdowns degrade to a disabled "טוען..." option.
        const [membershipsResp, companiesResp] = await Promise.all([
          projectService.getMemberships(projectId).catch(() => null),
          projectCompanyService.list(projectId).catch(() => null),
        ]);
        if (cancelled) return;

        const memberList = Array.isArray(membershipsResp)
          ? membershipsResp
          : (membershipsResp?.items || []);
        const userMap = new Map();
        memberList.forEach((m) => {
          const uid = m.user_id || m.id;
          if (uid && !userMap.has(uid)) {
            userMap.set(uid, {
              id: uid,
              name: m.user_name || m.name || m.full_name || m.email || uid,
            });
          }
        });
        setUsers(Array.from(userMap.values()));

        const companyList = Array.isArray(companiesResp)
          ? companiesResp
          : (companiesResp?.items || []);
        setCompanies(companyList.map((c) => ({ id: c.id, name: c.name || c.id })));
      } catch (err) {
```

**AFTER:**

```javascript
        setScoreData(scoreResp);
        setDocs(docsResp || { items: [], total: 0 });
        setTasks(tasksResp || { items: [], total: 0 });
        setWorkers(workersResp || { items: [], total: 0 });
      } catch (err) {
```

(Just delete the 26-line memberships/companies block. The `catch` line stays. No other change to this useEffect.)

### 1.2 Add a new useEffect for memberships/companies

Place it immediately **after** the main useEffect and **before** the existing docs-refetch-on-filter useEffect:

```javascript
// Best-effort enrichment for filter dropdowns — runs once the page is
// interactive, NOT during the loading gate. Dropdowns render "טוען..."
// until this completes. Failures are silent.
useEffect(() => {
  if (!projectId || loading || flagOff || forbidden) return;
  let cancelled = false;
  (async () => {
    const [membershipsResp, companiesResp] = await Promise.all([
      projectService.getMemberships(projectId).catch(() => null),
      projectCompanyService.list(projectId).catch(() => null),
    ]);
    if (cancelled) return;

    const memberList = Array.isArray(membershipsResp)
      ? membershipsResp
      : (membershipsResp?.items || []);
    const userMap = new Map();
    memberList.forEach((m) => {
      const uid = m.user_id || m.id;
      if (uid && !userMap.has(uid)) {
        userMap.set(uid, {
          id: uid,
          name: m.user_name || m.name || m.full_name || m.email || uid,
        });
      }
    });
    setUsers(Array.from(userMap.values()));

    const companyList = Array.isArray(companiesResp)
      ? companiesResp
      : (companiesResp?.items || []);
    setCompanies(companyList.map((c) => ({ id: c.id, name: c.name || c.id })));
  })();
  return () => { cancelled = true; };
}, [projectId, loading, flagOff, forbidden]);
```

**Why `loading` is still in the dep list:** this useEffect should only run once the main fetch has finished (`loading === false`). When loading transitions from true to false, this useEffect fires. It does not re-run on filter changes or tab changes because neither is in its deps.

---

## Fix 2 — Eliminate double docs fetch on initial mount

**File:** `frontend/src/pages/SafetyHomePage.js`

The filter useEffect currently has `loading` in its deps, so when `loading` flips from `true` to `false`, it fires and re-fetches documents even though the main `Promise.all` just fetched them.

**Fix via `useRef` first-run gate** — add an import and a ref:

### 2.1 Update React import

**BEFORE:**

```javascript
import React, { useEffect, useState } from 'react';
```

**AFTER:**

```javascript
import React, { useEffect, useRef, useState } from 'react';
```

### 2.2 Add the first-run ref inside the component

Place it next to the other state declarations (after `const [activeTab, setActiveTab] = useState('documents');`):

```javascript
// Skip the filter useEffect's initial run — main useEffect's Promise.all
// already fetched documents. The ref flips to false after the first real run.
const filterFetchFirstRun = useRef(true);
```

### 2.3 Update the docs-refetch useEffect

**BEFORE:**

```javascript
// Refetch documents whenever the filter changes (skipped before initial load
// and when the page is in a forbidden / flag-off / loading terminal state).
useEffect(() => {
  if (!projectId || loading || flagOff || forbidden) return;
  let cancelled = false;
  (async () => {
    try {
      const params = { limit: 50 };
      Object.entries(filter).forEach(([k, v]) => {
        if (v != null && v !== '') params[k] = v;
      });
      const resp = await safetyService.listDocuments(projectId, params);
      if (!cancelled) setDocs(resp || { items: [], total: 0 });
    } catch (err) {
      if (!cancelled) toast.error('שגיאה בטעינת ליקויים מסוננים');
    }
  })();
  return () => { cancelled = true; };
}, [projectId, filter, loading, flagOff, forbidden]);
```

**AFTER:**

```javascript
// Refetch documents whenever the filter changes. Skipped on the first run
// (main useEffect's Promise.all already fetched documents with no filter)
// and on forbidden / flag-off / loading terminal states.
useEffect(() => {
  if (!projectId || loading || flagOff || forbidden) return;

  // First run after the page finishes loading: skip — docs already fetched.
  if (filterFetchFirstRun.current) {
    filterFetchFirstRun.current = false;
    return;
  }

  let cancelled = false;
  (async () => {
    try {
      const params = { limit: 50 };
      Object.entries(filter).forEach(([k, v]) => {
        if (v != null && v !== '') params[k] = v;
      });
      const resp = await safetyService.listDocuments(projectId, params);
      if (!cancelled) setDocs(resp || { items: [], total: 0 });
    } catch (err) {
      if (!cancelled) toast.error('שגיאה בטעינת ליקויים מסוננים');
    }
  })();
  return () => { cancelled = true; };
}, [projectId, filter, loading, flagOff, forbidden]);
```

Only 5 lines added. The `filterFetchFirstRun` ref flips `false` on the very first valid run and never resets — subsequent filter changes fetch normally.

**Important:** the `handleBulkDelete` function ends with `setFilter((f) => ({ ...f }))`, which changes the `filter` reference. That will re-run the useEffect, and at that point `filterFetchFirstRun.current === false`, so the fetch runs. Bulk delete refetch still works. ✓

---

## Fix 3 — Harden `decodeURIComponent`

**File:** `frontend/src/components/safety/SafetyExportMenu.js`

The filename regex matches both `filename="..."` and RFC 5987 `filename*=UTF-8''...` patterns. The second form is URL-encoded, so `decodeURIComponent` is correct for it. But if the match group contains a stray `%` not followed by two hex digits, `decodeURIComponent` throws `URIError` and the download aborts.

**BEFORE:**

```javascript
function downloadBlob(response, fallbackName) {
  const disp = response?.headers?.['content-disposition'] || '';
  const match = disp.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
  const filename = match ? decodeURIComponent(match[1]) : fallbackName;
  const url = window.URL.createObjectURL(new Blob([response.data]));
  ...
}
```

**AFTER:**

```javascript
function downloadBlob(response, fallbackName) {
  const disp = response?.headers?.['content-disposition'] || '';
  const match = disp.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
  let filename = fallbackName;
  if (match) {
    try {
      filename = decodeURIComponent(match[1]);
    } catch (e) {
      // Malformed % in header — use the raw captured group as-is.
      filename = match[1];
    }
  }
  const url = window.URL.createObjectURL(new Blob([response.data]));
  ...
}
```

Only the filename-assignment lines change. Everything else in the function is untouched.

---

## DO NOT

- ❌ Do NOT change the `handleBulkDelete` refetch trigger (`setFilter((f) => ({ ...f }))`). The `filterFetchFirstRun` ref starts `true` and flips `false` on the first valid run — by the time bulk delete fires, it's already `false` so the refetch works.
- ❌ Do NOT move the memberships useEffect's deps to `[projectId]` alone. It needs `loading/flagOff/forbidden` so it doesn't fire during the loading gate or in terminal states.
- ❌ Do NOT add a loading spinner for the filter dropdowns. The existing "טוען..." text fallback in `renderEntitySelect` is sufficient UX.
- ❌ Do NOT remove the existing `if (cancelled) return;` guard after the memberships Promise.all. Still required — the user could navigate away mid-fetch.
- ❌ Do NOT refactor `downloadBlob` beyond the try/catch. Leave the regex, fallback logic, and blob URL creation intact.
- ❌ Do NOT touch `SafetyFilterSheet.js`, `SafetyBulkActionBar.js`, `api.js`, or `i18n/he.json` — they're fine as-is.
- ❌ Do NOT add any new imports beyond `useRef` to the React import in SafetyHomePage. No new packages, no new services.
- ❌ Do NOT "clean up" Part 5's existing pattern of `(err) => toast.error(...)` error handlers. House style.

---

## VERIFY before commit

### 1. Grep sanity

```bash
# (a) Memberships fetch is in a SEPARATE useEffect, not in the main one:
grep -c "projectService.getMemberships" frontend/src/pages/SafetyHomePage.js
# Expected: 1 (only in the new standalone useEffect)

# Count useEffects — should be 5 now (was 4):
grep -c "useEffect(" frontend/src/pages/SafetyHomePage.js
# Expected: 5 (main + memberships-NEW + docs-refetch + selection-on-filter + selection-on-tab)

# (b) useRef imported:
grep -n "useRef" frontend/src/pages/SafetyHomePage.js | head
# Expected: at least 2 hits (import + declaration + usage)

# (c) filterFetchFirstRun ref + skip logic:
grep -n "filterFetchFirstRun" frontend/src/pages/SafetyHomePage.js
# Expected: 3 hits (declaration + .current check + .current = false)

# (d) decodeURIComponent wrapped in try:
grep -B1 -A3 "decodeURIComponent" frontend/src/components/safety/SafetyExportMenu.js
# Expected: shows "try {" on the line before decodeURIComponent and "catch" after.

# (e) Backend still untouched:
git diff --stat backend/
# Expected: empty.

# (f) No new deps:
git diff frontend/package.json frontend/package-lock.json
# Expected: empty.

# (g) No @/ alias sneaked in:
grep -rn "from '@/" frontend/src/pages/SafetyHomePage.js frontend/src/components/safety/
# Expected: empty.
```

### 2. Build clean

```bash
cd frontend
npm run build
# Expected: no new warnings. In particular no "React Hook useEffect has a missing
# dependency" warning about the new useRef.
```

### 3. Manual — first paint is faster

1. Clear browser cache. Reload `/projects/<id>/safety` as PM on a project with 10+ members.
2. Expect: score/KPIs/tabs render within ~500ms. Filter sheet opens immediately.
3. Open the filter sheet → dropdowns show "טוען..." briefly → populate to "company1/2/3" and "user1/2/3" within another ~300ms.
4. Compare to Part 5 behavior: full skeleton should display for the full duration until memberships returns. After this patch, the page is interactive first.

### 4. Manual — no double docs fetch on initial load

Open DevTools Network, clear, reload `/projects/<id>/safety`. Under `safety/` requests:
- `GET /score` — 1 call ✓
- `GET /documents?limit=50` — **exactly 1 call** (before this patch it was 2)
- `GET /tasks?limit=50` — 1 call
- `GET /workers?limit=50` — 1 call
- `GET /incidents` — 0 calls (removed in Part 4a)
- `GET /projects/.../memberships` — 1 call (from the new useEffect)
- `GET /projects/.../companies` — 1 call

**If documents shows 2 calls** → `filterFetchFirstRun` ref isn't skipping correctly. Re-check the useEffect.

### 5. Manual — filter still triggers refetch

- Apply a filter (severity=גבוהה). Network shows **1 new** `/documents?severity=3&limit=50` call.
- Clear the filter. Network shows 1 more `/documents?limit=50` call.
- Bulk-delete 2 items. Network shows 2 DELETE calls, then 1 more `/documents` call (the refetch via `setFilter((f) => ({ ...f }))`).

### 6. Manual — export download edge case

Simulate a malformed header by (a) temporarily intercepting the response in the browser DevTools OR (b) just trust the try/catch and verify no other exports regress. Normal downloads (all 3 types) should still produce correct filenames from the Content-Disposition header. No console errors on any export.

### 7. Manual — full regression sanity

Run the full 13-step VERIFY from the Part 5 spec again. Nothing should regress. In particular:
- Forbidden user → immediate redirect (Part 4a route guard still works)
- Flag-off environment → `SafetyFlagOff` card
- Bulk bar appears/disappears with correct tab
- AlertDialog → cancel preserves selection
- All 3 exports download with server filenames

---

## Commit message (exactly)

```
fix(safety): Part 5a — don't block first paint on best-effort enrichment;
drop duplicate docs fetch; harden filename decode

1) SafetyHomePage.js: moved the memberships + projectCompanyService fetch
   out of the main loading gate into a separate useEffect that runs once
   the page is interactive. First paint is ~200-500ms faster on a cold
   cache; filter dropdowns render "טוען..." until they populate shortly
   after. Subsequent mounts hit the 30s cachedFetch and are instant.

2) SafetyHomePage.js: added a `filterFetchFirstRun` useRef guard to the
   docs-refetch effect so it skips its very first run (main useEffect's
   Promise.all already fetched documents). Eliminates the one duplicate
   /documents call per page load. Filter changes + bulk-delete refetch
   via setFilter((f) => ({...f})) continue to work because the ref
   flips false on the first skipped run.

3) SafetyExportMenu.js: wrapped decodeURIComponent in try/catch — a
   malformed % in the Content-Disposition header would have thrown
   URIError and aborted the download. Falls back to the raw capture
   group, then to the fallback filename. Unlikely in practice (backend
   filenames are plain ASCII) but zero-cost hardening.

No new deps, no backend changes. Scope unchanged from Part 5.
```

---

## Deploy

```bash
./deploy.sh --prod
```

OTA בלבד — אין שינוי native. Commit + push ביחד.

אחרי ה-deploy — שלח:
- `git log -1 --stat` (צפוי 2 files, ~25 lines diff)
- Unified diff
- Network tab screenshot: documents = 1 call בטעינה ראשונה (לא 2)
- Timing: page interactive time על cold cache (לפני/אחרי אם יש baseline)

---

## Definition of Done

- [ ] Main useEffect in `SafetyHomePage.js` no longer fetches memberships/companies
- [ ] New standalone useEffect fetches memberships/companies after loading=false
- [ ] `useRef` imported, `filterFetchFirstRun` ref declared
- [ ] Docs-refetch useEffect skips its first run via the ref
- [ ] `decodeURIComponent` wrapped in try/catch in `SafetyExportMenu.js`
- [ ] All 7 grep checks from VERIFY §1 pass
- [ ] Initial page load shows 1 documents call, not 2
- [ ] Filter changes + bulk delete still refetch documents correctly
- [ ] Full Part 5 regression (13 VERIFY steps) still passes
- [ ] `git diff --stat backend/` is empty
- [ ] `git diff frontend/package.json` is empty
- [ ] `./deploy.sh --prod` ran successfully
- [ ] No new deps, no backend changes

---

## After this patch

**Safety Phase 1 is complete.** Close:
- Task #408a (this) → completed
- Task #37 (Part 5 umbrella) → completed
- Task #29 (בטיחות + יומן עבודה Phase 1) → completed

**Phase 2 backlog candidates** (from the Part 5 spec DoD):
- Create/edit modals for documents/tasks/workers/incidents/trainings
- Incidents list view + incident-specific filters
- Tasks tab filter + bulk actions
- Workers tab filter + bulk actions
- Training expiry reminders
- Historical score trend chart
- Integration with work diary module
