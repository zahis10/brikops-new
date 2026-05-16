# Task #405 — Safety Phase 1 Part 5 — Frontend Polish (Filter + Bulk + Export)

**Scope:** 3 new components, 1 touch to `services/api.js`, 1 touch to `pages/SafetyHomePage.js`, 1 touch to `i18n/he.json`. No new deps. No backend changes. No new endpoints — everything wires to Parts 2 / 3 / 3a.

**Why:** Part 4 shipped a read-only Safety Home. Managers can see the score, tiles, and top-50 of each resource, but cannot:
1. **Filter documents** — the `/documents` endpoint supports a 7-dimension filter (category/severity/status/company/assignee/reporter/date range), but the Home page doesn't expose it.
2. **Bulk-delete** — a PM who finds 20 stale "open" documents has to soft-delete one at a time.
3. **Export** — the 3 regulatory outputs (`/export/excel`, `/export/filtered`, `/export/pdf-register`) are deployed and working, but there's no UI to trigger them.

Part 5 adds all three. Scope is **documents tab only** for filter + bulk. Tasks and workers stay read-only for Phase 1 — a future phase can extend. Exports are page-level (header buttons), not per-tab.

## Done looks like

- Header has two new buttons on the right side: **ייצוא** (export menu, 3 options) and **סינון** (filter sheet). Visible to PM/management_team.
- Clicking **סינון** opens a right-side Sheet with 7 filter fields. Apply → documents list refetches with filter query-string params. Clear → removes all filters. Active filter count shows on the button (e.g., "סינון (3)").
- **Documents tab** gets a left-side checkbox column. Selecting items reveals a sticky bottom bar with "בחירה: N · מחק · נקה". "מחק" opens a confirmation dialog → sequential DELETE calls → list refetches.
- **Export menu** has three options: ייצוא כללי (Excel 3-sheet) / ייצוא לפי סינון (Excel filtered — grey'd out if no filter active) / פנקס כללי PDF. Clicking any triggers a blob download with a correctly-named filename.
- Empty state when a filter returns zero documents: "לא נמצאו ליקויים המתאימים לסינון" with a "נקה סינון" button.
- Mobile (375px): filter button, export menu, and bulk bar all touch-friendly ≥44px, stack correctly, no horizontal scroll.
- All features respect the existing `SafetyForbidden` / `SafetyFlagOff` / loading states — no regression.

## Out of scope for Part 5

- ❌ Create/edit modals for documents/tasks/workers/incidents/trainings. The "+" button on tabs remains `toast.info('בקרוב')` per Part 4.
- ❌ Filter/bulk on the **tasks** and **workers** tabs. Documents only.
- ❌ Incidents tab. The KPI card stays; no list view.
- ❌ Backend bulk-delete endpoint. Frontend issues sequential DELETEs — accepted perf cost for Phase 1 (PM unlikely to bulk-delete 50+ at once).
- ❌ URL state for filters (shareable filtered views). Filters are in-memory only.
- ❌ Offline queueing for exports. Export requires network.
- ❌ Print styles, dark mode, or theme tokens. Existing Tailwind classes only.
- ❌ Any backend, schema, or endpoint change. If something is missing on the backend, STOP and ask Zahi.

---

## Steps

### Step 1 — Extend `safetyService` with blob-returning exports

**File:** `frontend/src/services/api.js`

Append three methods to the existing `safetyService` object (after `healthz`). They fetch binary bodies and return `Blob`s — the page wraps them in download triggers.

```javascript
// ---- exports (binary blob) ----

async exportExcel(projectId) {
  const response = await axios.get(
    `${API}/safety/${projectId}/export/excel`,
    { headers: getAuthHeader(), responseType: 'blob' }
  );
  return response; // caller reads .data (Blob) + .headers['content-disposition']
},

async exportFiltered(projectId, params = {}) {
  const response = await axios.get(
    `${API}/safety/${projectId}/export/filtered`,
    { headers: getAuthHeader(), responseType: 'blob', params }
  );
  return response;
},

async exportPdfRegister(projectId) {
  const response = await axios.get(
    `${API}/safety/${projectId}/export/pdf-register`,
    { headers: getAuthHeader(), responseType: 'blob' }
  );
  return response;
},

async deleteDocument(projectId, documentId) {
  const response = await axios.delete(
    `${API}/safety/${projectId}/documents/${documentId}`,
    { headers: getAuthHeader() }
  );
  return response.data;
},
```

**Why return the full response, not just `.data`:** the caller needs `Content-Disposition` to extract the filename the backend generated (includes timestamp + project prefix). No client-side filename guessing.

---

### Step 2 — Create `SafetyFilterSheet` component

**File:** `frontend/src/components/safety/SafetyFilterSheet.js` (new)

A right-side Sheet (shadcn Sheet from `components/ui/sheet.jsx`) with 7 fields. Controlled component — parent holds state, this component reads `value` + emits `onChange`.

**Props:**

```javascript
/**
 * @param {boolean} open
 * @param {function} onOpenChange
 * @param {object} value             — current filter state, see shape below
 * @param {function} onApply         — called with { ...filter } on apply
 * @param {function} onClear         — called with no args
 * @param {Array<{id,name}>} companies
 * @param {Array<{id,name}>} users
 */
```

**Filter shape:**

```javascript
{
  category:     null,  // SafetyCategory enum string or null
  severity:     null,  // '1' | '2' | '3' | null
  status:       null,  // 'open' | 'in_progress' | 'resolved' | 'verified' | null
  company_id:   null,
  assignee_id:  null,
  reporter_id:  null,
  date_from:    null,  // YYYY-MM-DD
  date_to:      null,  // YYYY-MM-DD
}
```

**Implementation notes:**

- Use `<Sheet open={open} onOpenChange={onOpenChange}>` + `<SheetContent side="left" dir="rtl">` — Hebrew RTL reads right-to-left, so the filter panel slides in from the **left** edge (same side as an English "right drawer"). Test on screen first — if it feels wrong, flip to `side="right"` per designer preference.
- Internal local state mirrors the prop `value`. On "החל" click → emit `onApply(localState)` → parent closes the sheet.
- Clear button inside the sheet → reset localState + emit `onClear()`.
- All selects use native `<select>` for simplicity (or `components/ui/select.jsx` if it exists — check with `ls frontend/src/components/ui/select.jsx`). Native is fine for Part 5.
- Category options come from a local constant:

```javascript
const CATEGORY_OPTIONS = [
  { value: 'scaffolding',         label: 'פיגומים' },
  { value: 'heights',             label: 'עבודה בגובה' },
  { value: 'electrical_safety',   label: 'בטיחות חשמל' },
  { value: 'lifting',             label: 'הרמה וציוד' },
  { value: 'excavation',          label: 'חפירות' },
  { value: 'fire_safety',         label: 'אש ובטיחות אש' },
  { value: 'ppe',                 label: 'ציוד מגן אישי' },
  { value: 'site_housekeeping',   label: 'סדר וניקיון' },
  { value: 'hazardous_materials', label: 'חומרים מסוכנים' },
  { value: 'other',               label: 'אחר' },
];
const SEVERITY_OPTIONS = [
  { value: '3', label: 'גבוהה' },
  { value: '2', label: 'בינונית' },
  { value: '1', label: 'נמוכה' },
];
const DOC_STATUS_OPTIONS = [
  { value: 'open',        label: 'פתוח' },
  { value: 'in_progress', label: 'בביצוע' },
  { value: 'resolved',    label: 'נפתר' },
  { value: 'verified',    label: 'אומת' },
];
```

- Companies + users come from props. If the parent doesn't have them, the dropdown renders "טוען..." as a single disabled option.
- Date inputs: native `<input type="date">`. Submit as `YYYY-MM-DD` — matches the backend's string-comparison filter on `found_at`.
- Layout: simple vertical stack, each field is a `<label>` + input pair. Use Tailwind classes consistent with the rest of the page.
- Footer of the sheet has two buttons side-by-side: "החל" (primary, `bg-slate-900 text-white`) and "נקה" (secondary). The SheetClose handles the X in the corner.

**Active-count helper** — export this pure function alongside the component so the parent can render the badge:

```javascript
export function countActiveFilters(filter) {
  if (!filter) return 0;
  return Object.values(filter).filter((v) => v != null && v !== '').length;
}
```

---

### Step 3 — Create `SafetyExportMenu` component

**File:** `frontend/src/components/safety/SafetyExportMenu.js` (new)

A dropdown trigger with 3 options. Use `components/ui/dropdown-menu.jsx` (shadcn pattern — confirmed available in the ui directory).

**Props:**

```javascript
/**
 * @param {string} projectId
 * @param {object} currentFilter     — Part 5 filter state (for "filtered" export)
 * @param {boolean} hasActiveFilter  — true if countActiveFilters > 0
 * @param {function} onExportStart   — called with {type} when an export begins
 * @param {function} onExportDone    — called with {type, filename} on success
 * @param {function} onExportError   — called with {type, error} on failure
 */
```

**3 items:**

```
ייצוא Excel כללי  — calls safetyService.exportExcel(projectId)
ייצוא לפי סינון   — calls safetyService.exportFiltered(projectId, currentFilter)
                    disabled + tooltip "אין סינון פעיל" when !hasActiveFilter
פנקס כללי PDF    — calls safetyService.exportPdfRegister(projectId)
```

**Download helper (inside this component):**

```javascript
function downloadBlob(response, fallbackName) {
  const disp = response.headers?.['content-disposition'] || '';
  const match = disp.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : fallbackName;
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
```

**UX:**

- While an export is in flight: disable the trigger button + show a small spinner ring on the icon.
- On success: `toast.success('הקובץ הורד בהצלחה')`.
- On failure: `toast.error('שגיאה בייצוא — נסה שוב')`.
- After ~500ms the button re-enables.

**Fallback filenames** (if `Content-Disposition` missing or malformed):
- excel → `safety_${projectId.slice(0,8)}_${yyyymmdd}.xlsx`
- filtered → `safety_filtered_${projectId.slice(0,8)}_${yyyymmdd}.xlsx`
- pdf → `safety_register_${projectId.slice(0,8)}_${yyyymmdd}.pdf`

Filenames from the backend already contain these patterns — the fallback exists only for edge cases.

---

### Step 4 — Create `SafetyBulkActionBar` component

**File:** `frontend/src/components/safety/SafetyBulkActionBar.js` (new)

A sticky bottom bar that appears when `selectedIds.size > 0` on the documents tab. Renders a native `<div>` with `position: fixed; bottom: 0` styling via Tailwind.

**Props:**

```javascript
/**
 * @param {number} count            — how many items selected
 * @param {function} onDelete       — called on delete-confirm (async)
 * @param {function} onClear        — called on clear-selection
 * @param {boolean} deleting        — true while delete is in progress
 */
```

**Layout:**

```
┌──────────────────────────────────────────────────┐
│  [נקה]              בחירה: N           [מחק]   │
└──────────────────────────────────────────────────┘
```

- Right button: מחק — destructive red, triggers a confirmation dialog. **Use `components/ui/alert-dialog.jsx`** (verified exists). The bar itself does NOT render the dialog — it just calls `onDelete`, and the parent page (`SafetyHomePage`) renders the `AlertDialog` modal with the count + confirm/cancel buttons. This keeps the bar a dumb presentational component.
- Middle: count text in Hebrew.
- Left button: נקה — secondary, clears selection.
- While `deleting=true`: both buttons disabled, מחק shows spinner.

**Z-index:** `z-30` so it sits above the tab content but below any modal (modals typically use `z-50`).

---

### Step 5 — Wire it into `SafetyHomePage`

**File:** `frontend/src/pages/SafetyHomePage.js`

### 5.1 New state

Add next to the existing state declarations:

```javascript
const [filter, setFilter] = useState({
  category: null, severity: null, status: null,
  company_id: null, assignee_id: null, reporter_id: null,
  date_from: null, date_to: null,
});
const [filterOpen, setFilterOpen] = useState(false);
const [selectedIds, setSelectedIds] = useState(new Set());
const [bulkDeleting, setBulkDeleting] = useState(false);
const [companies, setCompanies] = useState([]);
const [users, setUsers] = useState([]);
```

### 5.2 Fetch companies + users for the filter dropdowns

Inside the existing `useEffect`, after the `Promise.all` success branch, add **two parallel best-effort fetches** using the existing services. Verified both exist in `services/api.js`:

- `projectService.getMemberships(projectId)` — returns project memberships (for users)
- `projectCompanyService.list(projectId)` — returns the project's companies directly

**Import update** — add `projectCompanyService` to the existing api.js imports:

```javascript
import { safetyService, projectService, projectCompanyService } from '../services/api';
```

**Fetch logic** — add after the safety `Promise.all` success branch inside the same useEffect:

```javascript
// Fetch memberships + companies for the filter dropdowns (best-effort, parallel).
// Both services exist in api.js; both failures are silent — filter dropdowns
// just render "טוען..." and the page still works.
const [membershipsResp, companiesResp] = await Promise.all([
  projectService.getMemberships(projectId).catch(() => null),
  projectCompanyService.list(projectId).catch(() => null),
]);
if (cancelled) return;

// Users: dedupe by user_id. Shape from getMemberships is assumed to include
// at least user_id + a human-readable name field. Fallback chain covers
// common variants.
const userMap = new Map();
(membershipsResp || []).forEach((m) => {
  const uid = m.user_id || m.id;
  if (uid && !userMap.has(uid)) {
    userMap.set(uid, { id: uid, name: m.user_name || m.name || m.full_name || uid });
  }
});
setUsers(Array.from(userMap.values()));

// Companies come from the dedicated endpoint — no need to derive from memberships.
const companyList = (companiesResp || []).map((c) => ({
  id: c.id,
  name: c.name || c.id,
}));
setCompanies(companyList);
```

**If `getMemberships` returns a different shape than assumed** (e.g., wrapped in `{items: [...]}` envelope), adjust to `(membershipsResp?.items || membershipsResp || [])`. The same pattern applies to companies. The key constraint: **do not add a new backend endpoint**. If both calls return unexpected shapes, leave `users`/`companies` empty — the filter dropdowns degrade gracefully.

### 5.3 Refetch documents when filter changes

Add a separate useEffect that fires when `filter` changes (and on mount):

```javascript
useEffect(() => {
  if (!projectId || flagOff || forbidden) return;
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
}, [projectId, filter, flagOff, forbidden]);
```

**Important — two selection-cleanup useEffects:**

```javascript
// (a) Clear selection when filter changes — items from a different filter
// shouldn't carry over.
useEffect(() => { setSelectedIds(new Set()); }, [filter]);

// (b) Clear selection when leaving the documents tab — otherwise the bulk
// bar stays mounted invisibly (we only render it on documents tab via the
// selectedIds.size > 0 condition at page level), and returning to the
// documents tab makes it re-appear unexpectedly with stale selection.
useEffect(() => {
  if (activeTab !== 'documents') setSelectedIds(new Set());
}, [activeTab]);
```

Without (b), the user flow breaks like this:
1. Select 3 documents → bulk bar visible
2. Switch to the tasks tab → bulk bar disappears (selection is per-document-id, meaningless on tasks)
3. Switch back to documents → bulk bar suddenly re-appears with the 3 stale IDs highlighted

Clearing on `activeTab` transition makes the selection scoped to the current documents view.

### 5.4 Header buttons

In the header JSX (currently has back button + title + cacheAge), add the two new buttons before the cacheAge indicator. Hide them while `loading`/`flagOff`/`forbidden`.

```jsx
<SafetyExportMenu
  projectId={projectId}
  currentFilter={filter}
  hasActiveFilter={countActiveFilters(filter) > 0}
/>
<button
  type="button"
  onClick={() => setFilterOpen(true)}
  className="px-3 py-1.5 text-sm rounded-lg border border-slate-200 hover:bg-slate-50 flex items-center gap-1"
>
  <Filter className="w-4 h-4" />
  סינון
  {countActiveFilters(filter) > 0 && (
    <span className="bg-blue-600 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center">
      {countActiveFilters(filter)}
    </span>
  )}
</button>
```

Import `Filter` from `lucide-react`, and import `SafetyExportMenu` + `SafetyFilterSheet` + `countActiveFilters` from the new components.

Render the filter sheet just before the closing `</div>` of the page root:

```jsx
<SafetyFilterSheet
  open={filterOpen}
  onOpenChange={setFilterOpen}
  value={filter}
  onApply={(next) => { setFilter(next); setFilterOpen(false); }}
  onClear={() => setFilter({
    category: null, severity: null, status: null,
    company_id: null, assignee_id: null, reporter_id: null,
    date_from: null, date_to: null,
  })}
  companies={companies}
  users={users}
/>
```

### 5.5 Checkboxes in DocumentsList

Update `DocumentsList` to accept `selectedIds` + `onToggle` + a "select all" header row. Signature:

```javascript
function DocumentsList({ items, selectedIds, onToggle, onSelectAll, allSelected }) { ... }
```

- Add a header row above the `<ul>`: `<div>` with a checkbox + "בחר הכל" label + count.
- Each `<li>` gets a checkbox on the right (RTL: right = start) that toggles membership in `selectedIds`.
- Checkbox component: native `<input type="checkbox">` is fine. Must be at least 20×20px. Click handler stops propagation so clicking the row background doesn't also fire the row detail click.
- Pass `checked={selectedIds.has(d.id)}`.

Full empty-state case when filter returns zero:

```jsx
if (!items?.length) {
  const filterActive = countActiveFilters(filter) > 0;
  return (
    <div className="flex flex-col items-center justify-center py-12 text-slate-400">
      <ShieldAlert className="w-10 h-10 mb-2" />
      <p className="text-sm font-medium">
        {filterActive ? 'לא נמצאו ליקויים המתאימים לסינון' : 'אין ליקויים פתוחים'}
      </p>
      {filterActive && (
        <button
          type="button"
          onClick={onClearFilter}
          className="mt-3 text-sm text-blue-600 hover:underline"
        >
          נקה סינון
        </button>
      )}
    </div>
  );
}
```

Thread `filter` and `onClearFilter` props into `DocumentsList` so the empty state knows which message to show.

### 5.6 Bulk delete handler + AlertDialog

Use shadcn's `AlertDialog` for confirmation (verified `components/ui/alert-dialog.jsx` exists). Pattern: the bulk bar's "מחק" button opens the dialog; the dialog's "מחק" button runs the actual deletion.

**New state** — track the open/closed dialog:

```javascript
const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
```

**Handler** — the actual deletion, runs on confirm:

```javascript
const handleBulkDelete = async () => {
  if (selectedIds.size === 0) return;
  setBulkConfirmOpen(false);
  setBulkDeleting(true);
  const ids = Array.from(selectedIds);
  const results = await Promise.allSettled(
    ids.map((id) => safetyService.deleteDocument(projectId, id))
  );
  const failed = results.filter((r) => r.status === 'rejected').length;
  setBulkDeleting(false);
  setSelectedIds(new Set());
  if (failed > 0) {
    toast.error(`${failed} מתוך ${ids.length} לא נמחקו`);
  } else {
    toast.success(`${ids.length} ליקויים נמחקו`);
  }
  // Refetch documents with current filter
  setFilter({ ...filter }); // triggers the docs useEffect
};
```

**Why `Promise.allSettled` instead of `Promise.all`:** one 403/409 on a single document shouldn't abort the rest. Collect per-item results, report partial failures.

**Why `setFilter({...filter})` at the end:** the simplest way to retrigger the documents refetch useEffect. A dedicated `refetchDocuments` function would be cleaner, but adds plumbing for a one-liner.

**Render the dialog + bar conditionally:**

```jsx
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';

{/* Bulk action bar — the bar opens the dialog, not the dialog itself */}
{selectedIds.size > 0 && (
  <SafetyBulkActionBar
    count={selectedIds.size}
    onDelete={() => setBulkConfirmOpen(true)}
    onClear={() => setSelectedIds(new Set())}
    deleting={bulkDeleting}
  />
)}

{/* Confirm dialog — rendered at the page level */}
<AlertDialog open={bulkConfirmOpen} onOpenChange={setBulkConfirmOpen}>
  <AlertDialogContent dir="rtl">
    <AlertDialogHeader>
      <AlertDialogTitle>מחיקת ליקויים</AlertDialogTitle>
      <AlertDialogDescription>
        האם למחוק {selectedIds.size} ליקויים נבחרים? לא ניתן לבטל את הפעולה.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>ביטול</AlertDialogCancel>
      <AlertDialogAction
        onClick={handleBulkDelete}
        className="bg-red-600 hover:bg-red-700 text-white"
      >
        מחק
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

Note: "לא ניתן לבטל" is honest — while the records are soft-deleted (not truly purged), the Phase 1 UI doesn't expose a restore path. A future undo-via-toast feature can be added in Phase 2.

**Why `Promise.allSettled` instead of `Promise.all`:** one 403/409 on a single document shouldn't abort the rest. Collect per-item results, report partial failures.

**Why `setFilter({...filter})` at the end:** the simplest way to retrigger the documents refetch useEffect. A dedicated `refetchDocuments` function would be cleaner, but adds plumbing for a one-liner.

Render the bulk bar conditionally:

```jsx
{selectedIds.size > 0 && (
  <SafetyBulkActionBar
    count={selectedIds.size}
    onDelete={handleBulkDelete}
    onClear={() => setSelectedIds(new Set())}
    deleting={bulkDeleting}
  />
)}
```

---

### Step 6 — Extend i18n

**File:** `frontend/src/i18n/he.json`

Add keys to the existing `safety` section (merge, don't replace):

```json
"filter_title": "סינון ליקויים",
"filter_category": "קטגוריה",
"filter_severity": "חומרה",
"filter_status": "סטטוס",
"filter_company": "חברה",
"filter_assignee": "אחראי",
"filter_reporter": "מדווח",
"filter_date_from": "מתאריך",
"filter_date_to": "עד תאריך",
"filter_apply": "החל",
"filter_clear": "נקה",
"filter_all": "הכל",
"filter_none": "ללא סינון פעיל",
"filter_active_count": "פילטרים פעילים",
"no_results_filtered": "לא נמצאו ליקויים המתאימים לסינון",
"export_label": "ייצוא",
"export_excel": "ייצוא Excel כללי",
"export_filtered": "ייצוא לפי סינון",
"export_pdf": "פנקס כללי PDF",
"export_no_filter": "אין סינון פעיל",
"export_in_progress": "מייצא...",
"export_success": "הקובץ הורד בהצלחה",
"export_error": "שגיאה בייצוא — נסה שוב",
"bulk_select_all": "בחר הכל",
"bulk_selection": "בחירה",
"bulk_delete": "מחק",
"bulk_clear": "נקה",
"bulk_confirm": "למחוק {{count}} ליקויים?",
"bulk_partial_failure": "{{failed}} מתוך {{total}} לא נמחקו",
"bulk_success": "{{count}} ליקויים נמחקו"
```

Inline Hebrew is still acceptable per Part 4 precedent; the JSON exists for parity and future translations.

---

## DO NOT

- ❌ Do NOT add create/edit modals. They're a separate future phase.
- ❌ Do NOT add filter/bulk to the **tasks** or **workers** tabs. Documents only.
- ❌ Do NOT add a backend bulk-delete endpoint. Sequential DELETEs via `Promise.allSettled` is the Phase 1 approach.
- ❌ Do NOT change backend. `git diff --stat backend/` must be empty on this commit.
- ❌ Do NOT use `URLSearchParams` on the window location — filters stay in component state only.
- ❌ Do NOT persist filter to localStorage. Refresh = blank filter.
- ❌ Do NOT add `WebkitOverflowScrolling: 'touch'` to the sticky bulk bar — native scrolling works fine.
- ❌ Do NOT add SWR, react-query, or a custom data hook. Plain `useEffect` + per-promise `.catch` is the house pattern.
- ❌ Do NOT introduce `@/` alias imports — all imports relative (`../components/ui/...` or `../components/safety/...`).
- ❌ Do NOT hit `/safety/.../documents` more than once per filter change. Debouncing is NOT needed since the filter is committed only on "החל" click (not on every keystroke).
- ❌ Do NOT log `id_number` or `id_number_hash` anywhere. Worker rows (still on the workers tab) continue to render `full_name`/`profession`/`phone` only.
- ❌ Do NOT open the export menu as a modal. It's a dropdown (shadcn `DropdownMenu`).
- ❌ Do NOT disable the export buttons when the flag is off or forbidden — those states render their own full-page fallbacks, so exports never get a chance to render anyway.

---

## VERIFY before commit

### 1. Pre-build greps

```bash
# (a) No @/ alias:
grep -rn "from '@/" frontend/src/pages/SafetyHomePage.js frontend/src/components/safety/
# Expected: EMPTY.

# (b) No backend changes:
git diff --stat backend/ frontend/public/
# Expected: EMPTY.

# (c) 3 export methods + deleteDocument added to safetyService:
grep -n "exportExcel\|exportFiltered\|exportPdfRegister\|deleteDocument" frontend/src/services/api.js
# Expected: at least 4 hits (4 function declarations + 4 usages).

# (d) No new deps:
git diff frontend/package.json frontend/package-lock.json
# Expected: EMPTY.

# (e) shadcn Sheet + DropdownMenu + AlertDialog files exist (verified pre-spec):
ls frontend/src/components/ui/sheet.jsx frontend/src/components/ui/dropdown-menu.jsx frontend/src/components/ui/alert-dialog.jsx
# Expected: all three exist.

# (e2) projectCompanyService + projectService.getMemberships both exist:
grep -n "projectCompanyService\|getMemberships" frontend/src/services/api.js | head -5
# Expected: at least 3 hits — projectCompanyService export, getMemberships declaration, and import usage in SafetyHomePage.

# (f) 3 new safety components:
ls frontend/src/components/safety/*.js | wc -l
# Expected: 5 (SafetyScoreGauge + SafetyKpiCard from Part 4, plus 3 new).
```

### 2. Build + smoke

```bash
cd frontend
npm run build
# Expected: no new warnings vs. baseline. In particular no "unused variable" around filter/selection state.

npm start
# Expected: dev server boots clean.
```

### 3. Manual — filter happy path

On a seeded project as PM:
- Click "סינון" → sheet opens.
- Pick `severity=גבוהה`, `status=פתוח` → click "החל".
- Sheet closes. Documents list refetches with `?severity=3&status=open`. Count on button shows "2".
- Open DevTools Network → confirm the request URL includes the two params and nothing else.
- Click "נקה" inside the sheet → all fields reset, list refetches with no filter, badge disappears.

### 4. Manual — filter empty state

Apply a filter that matches zero documents (e.g., `severity=נמוכה` on a site with only sev3 open). The list shows "לא נמצאו ליקויים המתאימים לסינון" + "נקה סינון" button. Click the clear button → filter resets.

### 4b. Manual — selection cleanup on tab change (Zahi bug-prevention)

On documents tab as PM:
1. Select 3 documents via checkboxes → bulk bar appears with "בחירה: 3".
2. Click the "משימות" tab → bulk bar disappears.
3. Click the "עובדים" tab → bulk bar still hidden.
4. Click back to "ליקויים" → bulk bar must NOT re-appear. Selection must be empty. The "select all" checkbox in the list header must be unchecked. No individual row checkboxes highlighted.

If the bar re-appears on step 4 with the old selection → the `useEffect` on `activeTab` is missing or wrong. See spec Step 5.3 sub-point (b).

### 5. Manual — bulk delete

Without filter, on a project with ≥3 open documents:
- Click 3 checkboxes → bulk bar appears at bottom: "בחירה: 3 · מחק · נקה".
- Click "מחק" → shadcn AlertDialog opens (NOT native `window.confirm`) with Hebrew title "מחיקת ליקויים" + body "האם למחוק 3 ליקויים נבחרים? לא ניתן לבטל את הפעולה." + two buttons (ביטול / מחק).
- Click the red "מחק" button inside the dialog → Network tab: 3 DELETE calls fire in parallel.
- On success: toast "3 ליקויים נמחקו", list refetches, rows gone.
- `bulk bar` disappears (selection cleared).
- Regression check: clicking "ביטול" instead of "מחק" closes the dialog with no deletions and preserves selection.

### 6. Manual — bulk partial failure

Stop the backend mid-delete (or simulate by revoking one document server-side) and repeat step 5. Expect: `toast.error("1 מתוך 3 לא נמחקו")`, selection cleared, list refetches, 2 rows gone, 1 still present.

### 7. Manual — export Excel

Click "ייצוא" menu → "ייצוא Excel כללי" → file downloads with name `safety_<8chars>_<timestamp>.xlsx`. Open it → 3 Hebrew sheets (עובדים / הדרכות / אירועים). No `id_number_hash` column.

### 8. Manual — export filtered (disabled state)

With no filter active, open the export menu. "ייצוא לפי סינון" is greyed out with tooltip "אין סינון פעיל". Apply a filter, reopen menu — it's enabled. Click → downloads a filtered xlsx reflecting the filter.

### 9. Manual — export PDF register

Click "פנקס כללי PDF" → file downloads as `safety_register_<8chars>_<yyyymmdd>.pdf`. Open → 9 sections in Hebrew, management team section visible, page numbers in footer.

### 10. Manual — contractor blocked

As a `contractor` user, navigate to `/projects/.../safety` → immediate redirect to `/projects` (via Part 4a `allowedRoles`). Filter/export buttons never render because the page never loads.

### 11. Manual — flag off

With `ENABLE_SAFETY_MODULE=false` on the backend, navigate to the page → `SafetyFlagOff` card renders. Filter/export buttons NOT in DOM. No errors in console.

### 12. Mobile — 375px

- Filter button + export button fit in the header without overflow.
- Open filter sheet → full-height drawer, vertical scroll inside, keyboard doesn't cover submit button when a date input is focused.
- Bulk bar sticks to bottom, buttons ≥44pt touch targets, no horizontal scroll.

### 13. PII re-check

Network tab on `GET /safety/.../documents?severity=3` → response JSON has no `id_number`, no `id_number_hash`, no email. Each document has only the fields the UI actually renders.

---

## Commit message (exactly)

```
feat(safety): Part 5 — Frontend Polish (filter + bulk + export)

Adds three capabilities to the documents tab on SafetyHomePage:

1) Filter — 7-dim filter drawer (category, severity, status, company,
   assignee, reporter, date_from, date_to) that hits /documents with
   query params on "החל". Active-count badge on the trigger button.
   Empty state offers a quick-clear action.

2) Bulk delete — checkbox column + sticky action bar on the documents
   list. Sequential DELETEs via Promise.allSettled with partial-failure
   toast reporting. No new backend endpoint.

3) Export — dropdown menu with 3 actions: Excel (3-sheet), Filtered
   Excel (single sheet, disabled when no filter active), PDF Register
   (9-section פנקס כללי). Blob download with Content-Disposition-
   derived filename.

New files:
- frontend/src/components/safety/SafetyFilterSheet.js
- frontend/src/components/safety/SafetyExportMenu.js
- frontend/src/components/safety/SafetyBulkActionBar.js

Modified:
- frontend/src/pages/SafetyHomePage.js — filter state, selection state,
  header buttons, docs refetch on filter change, bulk delete handler,
  DocumentsList checkboxes + empty state
- frontend/src/services/api.js — exportExcel/exportFiltered/
  exportPdfRegister/deleteDocument methods on safetyService
- frontend/src/i18n/he.json — 26 new keys under the safety section

No new deps, no backend changes, no new endpoints. All three exports
wire to the existing Part 3/3a endpoints. Feature flag
ENABLE_SAFETY_MODULE stays off in prod.

Scope: documents tab only. Tasks/workers read-only remain. Create/edit
modals + incidents list are deferred to a future phase.
```

---

## Deploy

```bash
./deploy.sh --prod
```

OTA בלבד — אין שינוי native. דחיפה וpush יחד.

אחרי ה-deploy — שלח ל-Zahi:
- `git log -1 --stat`
- Unified diff
- `git diff --stat backend/` (חייב להיות ריק)
- Screenshots 375px + 1280px: (1) דף עם filter בר 3 פילטרים פעילים, (2) export menu פתוח, (3) bulk bar עם 3 פריטים נבחרים
- DevTools Network של `GET /documents?severity=3&status=open` — verify params פעילים
- פלט של 13 בדיקות VERIFY

---

## Definition of Done

- [ ] `safetyService` has 4 new methods (`exportExcel`, `exportFiltered`, `exportPdfRegister`, `deleteDocument`)
- [ ] `SafetyFilterSheet.js` renders 7-dim filter in a side Sheet
- [ ] `SafetyExportMenu.js` renders dropdown with 3 options, correct disabled state
- [ ] `SafetyBulkActionBar.js` renders sticky bottom bar with count + 2 buttons
- [ ] `SafetyHomePage.js` wires filter state + selection state + refetch useEffect + bulk delete handler
- [ ] DocumentsList has checkbox column + filter-aware empty state
- [ ] i18n `safety` section extended with 26 new keys
- [ ] All 6 pre-build greps pass
- [ ] All 13 manual VERIFY steps pass
- [ ] `git diff --stat backend/` is empty
- [ ] `git diff frontend/package.json` is empty
- [ ] `./deploy.sh --prod` ran successfully
- [ ] Screenshots + verification output sent to Zahi
- [ ] No new deps, no backend changes

---

## What closes after Part 5

Safety Phase 1 ends here. Task #29 ("בטיחות + יומן עבודה Phase 1") can be marked completed once Part 5 ships.

**Phase 2 candidates (not in this task):**
- Create/edit modals for all 5 resources
- Incidents list view + incident-specific filters
- Tasks tab filter + bulk actions
- Workers tab filter + bulk actions
- Task assignment workflow (push notifications, in-app)
- Training expiry reminders
- Historical score trend chart
- Integration with work diary module (shared worker list)
