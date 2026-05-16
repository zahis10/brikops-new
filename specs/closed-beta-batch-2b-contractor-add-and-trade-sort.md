# #414 — Closed-Beta Batch 2b — Contractor add flow (with draft save) + trade-sort

## What & Why

**Two fixes in one batch, both related to the "missing contractor" flow during defect creation. Both new behaviors are gated by feature flags for safe rollout.**

### Fix A: Contractor add destroys defect draft (Fix #4 from closed-beta feedback)

Today, when the user is filling out a new defect and discovers no contractor is assigned to the selected company, they click "+ הוסף קבלן" (NewDefectModal.js:877-884). This button currently does:

```js
onClick={() => { onClose(); if (projectId) navigate(`/projects/${projectId}/control?tab=companies`); }}
```

Problems:
1. Everything the user typed (title, description, category, location, images) is **lost**.
2. Navigates to the wrong tab (`companies` instead of `team` — contractors are added via team invites).
3. No way back — after adding the contractor, the user is stranded on team tab.

### Fix B: Companies dropdown in AddTeamMemberForm doesn't help users pick the right one

When the user arrives at team tab with `prefillTrade=electrical` (from the defect flow above, after we fix it), the AddTeamMemberForm shows ALL companies alphabetically. The user has to scroll to find companies that actually do electrical work. If the project has 30 companies across 10 trades, that's a needle-in-a-haystack.

### Shared solution strategy

For Fix A:
1. Save defect draft (text fields only — images cannot be serialized) to `sessionStorage` before navigating.
2. Navigate to team tab with `?tab=team&openInvite=1&prefillTrade={category}&returnToDefect=1`.
3. After successful invite save, show a "חזור לליקוי" action button in the success toast.
4. That button navigates to the original unit page with `?reopenDefect=1`.
5. The unit page reads that param and opens NewDefectModal.
6. NewDefectModal on open reads sessionStorage, restores the 10 text fields, clears the draft, and shows a toast: "הטיוטה שוחזרה. יש לצרף תמונות מחדש."

For Fix B:
1. Mirror the backend `CATEGORY_TO_BUCKET` + `BUCKET_LABELS` maps in a new frontend util.
2. Use a NEW wrapper component `GroupedSelectField` in AddTeamMemberForm that sorts companies whose `trade` bucket matches the current `tradeKey` bucket to the top with a subtle section header "תחום: {bucketLabel}", and (if there are non-matching companies) a muted "חברות אחרות" header above the rest.
3. `GroupedSelectField` internally delegates to `SelectField`. `SelectField` (BottomSheetSelect.js) is **NOT modified** — it's used in dozens of places across the app and any edit there is a blast-radius risk.

### Safety layers (CRITICAL)

1. **Two feature flags** gate all new behavior:
   - `FEATURES.DEFECT_DRAFT_PRESERVATION` — Fix A
   - `FEATURES.TRADE_SORT_IN_TEAM_FORM` — Fix B

   Both default to `true`. If either is flipped to `false`, the corresponding code path MUST fall back to pre-batch behavior exactly (bug-for-bug compatible with current prod).

2. **SelectField is untouched.** `BottomSheetSelect.js` has zero diff. All grouping/muting logic lives inside the new `GroupedSelectField` wrapper, which delegates to SelectField for the underlying dropdown.

**Critical constraint (from Zahi):** "זה לא פיצ'ר חדש, אנשים כבר עובדים עם זה" — do not break the existing flow for users who don't click "+ הוסף קבלן" and don't care about trade matching.

---

## Done looks like

### Fix A (contractor add draft preservation) — with DEFECT_DRAFT_PRESERVATION=true

1. Open NewDefectModal from any unit page (UnitDetailPage or ApartmentDashboardPage).
2. Fill title "בדיקה דראפט" + description + category "מיזוג" + pick a company.
3. The company has zero contractors → "אין קבלנים משויכים לחברה זו" + "+ הוסף קבלן" button appears.
4. ✅ Click "+ הוסף קבלן" → modal closes, URL changes to `/projects/{pid}/control?tab=team&openInvite=1&prefillTrade=hvac&returnToDefect=1`.
5. ✅ Team tab auto-opens AddTeamMemberForm with `tradeKey=hvac` preselected.
6. Fill phone, name, role=contractor, pick a company, save.
7. ✅ Success toast appears: "הזמנה נשלחה..." with an action button "חזור לליקוי".
8. ✅ Click "חזור לליקוי" → navigates to `/projects/{pid}/units/{unitId}?reopenDefect=1`.
9. ✅ Unit page opens NewDefectModal automatically. Modal shows title "בדיקה דראפט", description, category "מיזוג", company still selected.
10. ✅ Toast appears in the modal: "הטיוטה שוחזרה. יש לצרף תמונות מחדש."
11. ✅ Images input is empty — user must re-attach.
12. ✅ After re-attach + submit → defect saves normally. SessionStorage is empty.

### Fix A kill-switch — with DEFECT_DRAFT_PRESERVATION=false

1. Flip flag to false in `frontend/src/config/features.js`, redeploy.
2. Open NewDefectModal, fill fields, click "+ הוסף קבלן".
3. ✅ Behaves exactly like prod today: modal closes, navigates to `/projects/{pid}/control?tab=companies`. No sessionStorage write. No "חזור לליקוי" button. No `?reopenDefect=1` handling.

### Fix B (trade-sort) — with TRADE_SORT_IN_TEAM_FORM=true

1. Project has 5 companies: 2 tagged `trade: hvac`, 1 `trade: electrical`, 1 `trade: plumbing`, 1 with no trade.
2. User opens AddTeamMemberForm with `prefillTrade=hvac` (either via the new flow above, or manually).
3. ✅ Companies dropdown shows, in order:
   - Header "תחום: מיזוג"
   - The 2 hvac companies
   - Header "חברות אחרות" (muted)
   - The other 3 companies (slightly reduced opacity, alphabetical)
4. ✅ When user changes `tradeKey` inside the form (e.g., to `electrical`), the dropdown re-sorts: electrical company on top, others below.
5. ✅ When user picks `role` other than `contractor` (no tradeKey), dropdown shows ALL companies without headers.
6. ✅ When `prefillTrade` is empty AND user hasn't picked tradeKey yet, dropdown shows ALL companies without headers.

### Fix B kill-switch — with TRADE_SORT_IN_TEAM_FORM=false

1. Flip flag to false, redeploy.
2. Open AddTeamMemberForm with `prefillTrade=hvac`.
3. ✅ Companies dropdown shows all companies in original order — no headers, no muting. Exactly as prod today.

### Regression checks (MUST NOT BREAK regardless of flags)

1. ✅ The 3 "+ הוסף חברה" buttons from Batch 2a still open `QuickAddCompanyModal` inline (lines 811, 824, 851). No change to them.
2. ✅ ESC / X / ביטול on NewDefectModal still close it cleanly (no draft saved).
3. ✅ Submitting a defect normally (without going to add contractor) works — no sessionStorage side effects.
4. ✅ Opening NewDefectModal fresh (no draft in sessionStorage) shows empty form — no restore toast.
5. ✅ Opening AddTeamMemberForm directly (no prefillTrade) shows companies un-sorted — no headers.
6. ✅ The existing `openInvite=1` URL handler still works (cleans up URL, switches to team tab).
7. ✅ NewDefectModal still accepts `prefillData` for unit context — prefillData.unit_id etc. still get applied.
8. ✅ `SelectField` (BottomSheetSelect.js) has ZERO diff. All other callers of SelectField across the app behave exactly the same.

---

## Out of scope

- ❌ Any change to the image-saving mechanism. Images are lost by design (agreed with user).
- ❌ Any change to `QuickAddCompanyModal.js` (Batch 2a territory).
- ❌ Any change to the 3 "+ הוסף חברה" buttons (lines 811, 824, 851) — they already work inline via Batch 2a.
- ❌ Any change to `BottomSheetSelect.js` / `SelectField` — out of scope; use the new `GroupedSelectField` wrapper instead.
- ❌ Any backend change. `CATEGORY_TO_BUCKET` stays in Python; we mirror it in JS.
- ❌ Any change to tradeService, projectCompanyService, or teamInviteService.
- ❌ Any change to ProjectTasksPage — that flow doesn't have unitId, and users opening defects from there are typically managers who already know their contractors. Skip for this batch.
- ❌ Any change to the RoutesGuard / auth flow.
- ❌ No new npm dependencies.
- ❌ No migration of company.trade values — we match whatever is stored.
- ❌ Do NOT make the feature flags dynamic (env var, remote config, or user-scoped). They are static compile-time constants for now.

---

## Tasks

### Task 1 — Create `frontend/src/config/features.js` (feature flags)

**File:** `frontend/src/config/features.js` (NEW)

**Content:**

```js
// Compile-time feature flags for closed-beta safety.
// Flip any value to `false` to disable the corresponding new behavior
// and fall back to the exact pre-batch behavior. Keep flags here small
// and boolean — no env reads, no async loads.

export const FEATURES = {
  // Batch 2b — Fix #4: save NewDefectModal draft to sessionStorage, navigate
  // to team tab with returnToDefect flag, offer "חזור לליקוי" in the invite
  // success toast, and restore on re-open via ?reopenDefect=1.
  DEFECT_DRAFT_PRESERVATION: true,

  // Batch 2b — trade-sort in AddTeamMemberForm: group companies by bucket
  // match with "תחום: {label}" + "חברות אחרות" headers.
  TRADE_SORT_IN_TEAM_FORM: true,
};
```

**Why:** A single source of truth for batch-level toggles. Default to `true` so we ship on. Flipping to `false` is a one-line redeploy kill-switch if an edge case blows up in production.

---

### Task 2 — Create `frontend/src/utils/categoryBuckets.js`

**File:** `frontend/src/utils/categoryBuckets.js` (NEW)

**Content:**

```js
// Mirror of backend/contractor_ops/bucket_utils.py
// Source of truth is the backend — keep this in sync if backend changes.

export const CATEGORY_TO_BUCKET = {
  electrical: 'electrical',
  plumbing: 'plumbing',
  painting: 'painting',
  carpentry: 'carpentry_kitchen',
  carpentry_kitchen: 'carpentry_kitchen',
  bathroom_cabinets: 'bathroom_cabinets',
  finishes: 'finishes',
  structural: 'structural',
  masonry: 'structural',
  aluminum: 'aluminum',
  metalwork: 'metalwork',
  flooring: 'flooring',
  hvac: 'hvac',
  glazing: 'glazing',
  windows: 'glazing',
  doors: 'doors',
  general: 'general',
};

export const BUCKET_LABELS = {
  electrical: 'חשמלאי',
  plumbing: 'אינסטלטור',
  painting: 'צבעי',
  carpentry_kitchen: 'נגרות/מטבח',
  bathroom_cabinets: 'ארונות אמבטיה',
  finishes: 'גמרים',
  structural: 'שלד',
  aluminum: 'אלומיניום',
  metalwork: 'מסגרות',
  flooring: 'ריצוף',
  hvac: 'מיזוג',
  glazing: 'חלונות/זכוכית',
  doors: 'דלתות',
  general: 'כללי',
};

/**
 * Returns the bucket for a given category/trade key.
 * If the key isn't in the map (e.g., a custom trade key), returns the key itself.
 * This makes `getBucketForTrade(x) === getBucketForTrade(y)` a safe match
 * for both mapped and unmapped keys.
 */
export function getBucketForTrade(keyOrCategory) {
  if (!keyOrCategory) return null;
  const k = String(keyOrCategory).trim();
  if (!k) return null;
  return CATEGORY_TO_BUCKET[k] || k;
}

/**
 * Returns the Hebrew label for a bucket, or the bucket key itself if not found.
 */
export function getBucketLabel(bucket) {
  if (!bucket) return '';
  return BUCKET_LABELS[bucket] || bucket;
}

/**
 * True if two keys belong to the same bucket.
 */
export function isSameTradeBucket(a, b) {
  const ba = getBucketForTrade(a);
  const bb = getBucketForTrade(b);
  return !!ba && !!bb && ba === bb;
}
```

**Why:** Frontend needs to match defect category ↔ company.trade without calling backend. Backend `CATEGORY_TO_BUCKET` is the source of truth; we mirror it. If a company has a custom trade key not in the map, `getBucketForTrade` returns the key itself, so matching still works for exact-equal custom keys.

---

### Task 3 — Create `frontend/src/utils/defectDraft.js`

**File:** `frontend/src/utils/defectDraft.js` (NEW)

**Content:**

```js
const STORAGE_KEY = 'brikops_defect_draft_v1';
const MAX_AGE_MS = 30 * 60 * 1000; // 30 minutes

/**
 * Saves the NewDefectModal text-field state to sessionStorage for cross-page flow.
 * Images are intentionally NOT saved (File objects can't be serialized).
 */
export function saveDefectDraft(state) {
  try {
    const payload = {
      ...state,
      createdAt: Date.now(),
    };
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch (err) {
    console.warn('[defectDraft] save failed', err);
  }
}

/**
 * Loads the saved draft. Returns null if missing, malformed, or expired.
 * Does NOT clear — caller should call clearDefectDraft() after applying.
 */
export function loadDefectDraft() {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    const age = Date.now() - (parsed.createdAt || 0);
    if (age > MAX_AGE_MS) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch (err) {
    console.warn('[defectDraft] load failed', err);
    return null;
  }
}

export function clearDefectDraft() {
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {}
}

export function hasDefectDraft() {
  return !!loadDefectDraft();
}
```

**Why:** Centralize the draft persistence logic. 30-minute TTL prevents stale drafts from confusing users who abandoned the flow days ago. Versioned key (`_v1`) allows future schema changes.

---

### Task 4 — Create `frontend/src/components/GroupedSelectField.js` (SelectField wrapper)

**File:** `frontend/src/components/GroupedSelectField.js` (NEW)

**Purpose:** A thin wrapper around `SelectField` that accepts an `options` array which may include "header" and "muted" entries, and produces a visual grouping in the dropdown without touching `SelectField` itself.

**Strategy:** The wrapper injects header labels into the option labels (prefixed with a marker) and filters out header clicks at the `onChange` level, making header rows unreachable. Muting is done via a custom label prefix that visually dims the option.

Because `SelectField` is closed for modification, we cannot add a true non-interactive header row. The closest safe approximation without modifying SelectField is:

- **Headers** are rendered as **disabled options** (if SelectField supports a `disabled` flag on an option) OR as unclickable rows by intercepting `onChange` and ignoring header values.
- **Muted options** are rendered with a Unicode-space-prefixed label to create a visible indent, and a color hint via a leading dim character or by wrapping in a span — but since `SelectField.options` expects strings for labels (verify with `grep -n "options\\.map\\|opt\\.label" frontend/src/components/BottomSheetSelect.js`), we use string prefixes only.

**STEP 0 — INVESTIGATE FIRST:**

Before implementing, run:

```bash
grep -n "options\\.map\\|opt\\.label\\|opt\\.value\\|opt\\.disabled" frontend/src/components/BottomSheetSelect.js
```

Answer these questions BEFORE writing GroupedSelectField code:

1. What properties of an option does SelectField read? (at minimum `value` and `label` — does it read anything else?)
2. Does SelectField accept React nodes in `label`, or only strings? If React nodes are accepted, we can render a `<span className="text-slate-400 text-xs">` for headers and styled spans for muted rows.
3. Is there any `disabled` or `group` support already in SelectField that we can use non-destructively?

Report the answers in a comment at the top of GroupedSelectField.js so future maintainers know what SelectField tolerates.

**Implementation (adapt based on investigation):**

```jsx
import React, { useMemo } from 'react';
import { SelectField } from './BottomSheetSelect';

/**
 * SelectField wrapper that supports grouped options without modifying SelectField.
 *
 * Input option shape:
 *   - Normal:  { value, label }
 *   - Header:  { value: '__header_X', label: 'תחום: מיזוג', isHeader: true }
 *   - Muted:   { value, label, muted: true }
 *
 * Rendering strategy (depends on STEP 0 findings):
 *   - If SelectField.label accepts React nodes: headers get a <span className="text-xs text-slate-500 font-medium">
 *     and muted rows get a <span className="opacity-70">. Header onChange is blocked.
 *   - If only strings: headers get a prefix "── {label} ──" and muted rows get a leading " · " prefix.
 *     Header onChange is blocked either way.
 *
 * Props pass-through: every prop other than `options` and `onChange` is forwarded to SelectField as-is.
 */
const GroupedSelectField = ({ options = [], onChange, value, ...rest }) => {
  const { transformed, headerValues } = useMemo(() => {
    const headers = new Set();
    const out = options.map(opt => {
      if (opt?.isHeader) {
        headers.add(opt.value);
        // If SelectField accepts React nodes (confirmed in STEP 0):
        return {
          value: opt.value,
          label: (
            <span className={`text-xs font-medium ${opt.muted ? 'text-slate-400' : 'text-slate-500'} pointer-events-none`}>
              {opt.label}
            </span>
          ),
          disabled: true, // if SelectField supports it
        };
        // Fallback if SelectField only accepts strings:
        // return { value: opt.value, label: `── ${opt.label} ──`, disabled: true };
      }
      if (opt?.muted) {
        return {
          value: opt.value,
          label: (
            <span className="opacity-70">{opt.label}</span>
          ),
        };
        // String fallback: return { value: opt.value, label: ` · ${opt.label}` };
      }
      return { value: opt.value, label: opt.label };
    });
    return { transformed: out, headerValues: headers };
  }, [options]);

  const handleChange = (val) => {
    if (headerValues.has(val)) return; // block header clicks
    if (typeof onChange === 'function') onChange(val);
  };

  return (
    <SelectField
      {...rest}
      value={value}
      options={transformed}
      onChange={handleChange}
    />
  );
};

export default GroupedSelectField;
```

**Why:** Isolates all grouping/styling in a new component. SelectField is 100% unchanged — every existing caller continues to work identically. The wrapper is used ONLY inside AddTeamMemberForm (Task 9).

**Do NOT:**
- Do NOT import SelectField source and copy it — wrap, don't fork.
- Do NOT add grouping support to SelectField itself.
- Do NOT use this wrapper anywhere except AddTeamMemberForm for now. Other callers can adopt later if they need grouping.

---

### Task 5 — Update NewDefectModal.js "+ הוסף קבלן" button (feature-flagged)

**File:** `frontend/src/components/NewDefectModal.js`

**Find with:** `grep -n "הוסף קבלן" frontend/src/components/NewDefectModal.js`  
**Line:** 877-884

Add imports at top (group with the other `../utils` imports, around line 13):

```js
import { saveDefectDraft } from '../utils/defectDraft';
import { FEATURES } from '../config/features';
```

Replace the button's onClick (line 879):

```diff
- onClick={() => { onClose(); if (projectId) navigate(`/projects/${projectId}/control?tab=companies`); }}
+ onClick={() => {
+   if (!projectId) return;
+   if (!FEATURES.DEFECT_DRAFT_PRESERVATION) {
+     // Fallback: pre-batch behavior — exact match to current prod.
+     onClose();
+     navigate(`/projects/${projectId}/control?tab=companies`);
+     return;
+   }
+   saveDefectDraft({
+     projectId,
+     buildingId,
+     floorId,
+     unitId,
+     category,
+     title,
+     description,
+     priority,
+     companyId,
+     assigneeId,
+     prefillData: prefillData || null,
+   });
+   onClose();
+   const params = new URLSearchParams({
+     tab: 'team',
+     openInvite: '1',
+     returnToDefect: '1',
+   });
+   if (category) params.set('prefillTrade', category);
+   navigate(`/projects/${projectId}/control?${params.toString()}`);
+ }}
```

**Why:** The flag gates the new behavior. If flipped off, the exact pre-batch navigation runs instead. Router to `tab=team` + `openInvite=1` + `returnToDefect=1` + `prefillTrade=<category>` when on.

---

### Task 6 — Add draft restore effect to NewDefectModal.js (feature-flagged)

**File:** `frontend/src/components/NewDefectModal.js`

**Location:** Add new useEffect immediately AFTER the existing effect at lines 134-149 (the one that handles `hasPrefill`). Around line 150.

**Find with:** `grep -n "loadProjects, loadCompanies" frontend/src/components/NewDefectModal.js`

Update imports (combine into one import from `../utils/defectDraft`):

```js
import { saveDefectDraft, loadDefectDraft, clearDefectDraft } from '../utils/defectDraft';
```

Add the restore effect:

```js
  // Restore in-progress draft (from the "+ הוסף קבלן" → add contractor → return flow).
  // Gated on FEATURES.DEFECT_DRAFT_PRESERVATION. When the flag is off, this effect
  // is a no-op and the modal behaves exactly like prod today.
  // Runs once when the modal opens; intentionally skips images (not serializable).
  useEffect(() => {
    if (!FEATURES.DEFECT_DRAFT_PRESERVATION) return;
    if (!isOpen) return;
    const draft = loadDefectDraft();
    if (!draft) return;
    // Sanity check: the draft must be for the same unit context. If we're opening
    // on a different unit, ignore the draft (rare — means sessionStorage stuck).
    if (hasPrefill && draft.unitId && draft.unitId !== prefillData.unit_id) {
      return;
    }
    // Restore text fields only (project/building/floor/unit come from prefillData effect).
    if (draft.category) setCategory(draft.category);
    if (draft.title) setTitle(draft.title);
    if (draft.description) setDescription(draft.description);
    if (draft.priority) setPriority(draft.priority);
    if (draft.companyId) setCompanyId(draft.companyId);
    if (draft.assigneeId) setAssigneeId(draft.assigneeId);
    clearDefectDraft();
    toast.info('הטיוטה שוחזרה. יש לצרף תמונות מחדש.');
  }, [isOpen, hasPrefill, prefillData]);
```

**Why:** When the user returns from the team tab via "חזור לליקוי", the parent page reopens NewDefectModal. This effect restores the 6 text fields (project/building/floor/unit come from prefillData). The unit-match guard handles the edge case where a stale draft exists for a different unit. Clears the draft after restore so it doesn't re-apply on next open. Toast informs the user about the image limitation.

**Do NOT:** Move or modify the existing `useEffect` at lines 134-149 — it must run FIRST so prefillData is applied, then this effect restores additional fields on top.

---

### Task 7 — Pass `returnToDefect` through ProjectControlPage → TeamTab → AddTeamMemberForm

**File:** `frontend/src/pages/ProjectControlPage.js`

#### 7a — TeamTab render at line 3591

**Find with:** `grep -n "activeTab === 'team'" frontend/src/pages/ProjectControlPage.js`

**Change:**

```diff
-          {activeTab === 'team' && <TeamTab projectId={projectId} companies={companies} trades={trades} prefillTrade={searchParams.get('prefillTrade') || ''} myRole={myRole} isOrgOwner={isOrgOwner} onRefreshCompanies={loadCompanies} />}
+          {activeTab === 'team' && <TeamTab projectId={projectId} companies={companies} trades={trades} prefillTrade={searchParams.get('prefillTrade') || ''} returnToDefect={searchParams.get('returnToDefect') === '1'} myRole={myRole} isOrgOwner={isOrgOwner} onRefreshCompanies={loadCompanies} />}
```

#### 7b — TeamTab signature at line 2418

**Find with:** `grep -n "const TeamTab = " frontend/src/pages/ProjectControlPage.js`

**Change:**

```diff
- const TeamTab = ({ projectId, companies, prefillTrade, myRole, isOrgOwner, trades, onRefreshCompanies }) => {
+ const TeamTab = ({ projectId, companies, prefillTrade, returnToDefect, myRole, isOrgOwner, trades, onRefreshCompanies }) => {
```

#### 7c — AddTeamMemberForm render at line ~2685

**Find with:** `grep -n "<AddTeamMemberForm" frontend/src/pages/ProjectControlPage.js`

**Change:**

```diff
-        <AddTeamMemberForm projectId={projectId} companies={companies} onClose={() => setShowAddForm(false)} onSuccess={loadData} prefillTrade={prefillTrade} onRefreshCompanies={onRefreshCompanies} />
+        <AddTeamMemberForm projectId={projectId} companies={companies} onClose={() => setShowAddForm(false)} onSuccess={loadData} prefillTrade={prefillTrade} returnToDefect={returnToDefect} onRefreshCompanies={onRefreshCompanies} />
```

#### 7d — AddTeamMemberForm signature at line 1217

**Find with:** `grep -n "const AddTeamMemberForm = " frontend/src/pages/ProjectControlPage.js`

**Change:**

```diff
- const AddTeamMemberForm = ({ projectId, companies, onClose, onSuccess, prefillTrade, onRefreshCompanies }) => {
+ const AddTeamMemberForm = ({ projectId, companies, onClose, onSuccess, prefillTrade, returnToDefect, onRefreshCompanies }) => {
```

**Why:** Prop-drill `returnToDefect` from URL to the form. No new state needed — it's derived directly from searchParams.

---

### Task 8 — Show "חזור לליקוי" action in AddTeamMemberForm success toast (feature-flagged)

**File:** `frontend/src/pages/ProjectControlPage.js`

Add imports at top of file (near other imports):

```js
import { FEATURES } from '../config/features';
```

**Find with:** `grep -n "teamInviteService.create" frontend/src/pages/ProjectControlPage.js`

**Location:** AddTeamMemberForm success path at lines ~1334-1348.

At the top of the AddTeamMemberForm function body (around line 1221, after destructuring), add:

```js
  const navigate = useNavigate();
```

**Verify:** `useNavigate` is already imported at the top of the file (grep for `useNavigate`). If not, add it to the react-router-dom import.

**Find with:** `grep -n "from 'react-router-dom'" frontend/src/pages/ProjectControlPage.js`

In the success block (after `onSuccess(); onClose();` at lines 1347-1348), but BEFORE those calls so the toast config carries the action button — replace the whole success-toast block at lines 1336-1346 with:

```js
      const ns = result?.notification_status;
      const shouldOfferReturn = !!returnToDefect && FEATURES.DEFECT_DRAFT_PRESERVATION;
      const returnAction = shouldOfferReturn ? {
        label: 'חזור לליקוי',
        onClick: () => {
          // Read draft to find the original unit, then navigate back.
          // NewDefectModal will restore the saved fields on open (see Task 6).
          try {
            const raw = window.sessionStorage.getItem('brikops_defect_draft_v1');
            if (!raw) {
              toast.info('לא נמצאה טיוטה פעילה');
              return;
            }
            const draft = JSON.parse(raw);
            if (!draft || !draft.projectId || !draft.unitId) {
              toast.info('חסר מידע לחזרה לליקוי');
              return;
            }
            navigate(`/projects/${draft.projectId}/units/${draft.unitId}?reopenDefect=1`);
          } catch (err) {
            console.warn('[AddTeamMemberForm] return-to-defect failed', err);
            toast.error('שגיאה בחזרה לליקוי');
          }
        },
      } : undefined;

      const toastOpts = returnAction ? { action: returnAction, duration: 10000 } : undefined;
      if (ns?.channel_used === 'sms' && ns?.wa_skipped) {
        toast.success('הזמנה נשלחה ב-SMS (WhatsApp לא זמין כרגע)', toastOpts);
      } else if (ns?.channel_used === 'sms') {
        toast.success('הזמנה נשלחה בהצלחה ב-SMS', toastOpts);
      } else if (ns?.channel_used === 'whatsapp') {
        toast.success('הזמנה נשלחה בהצלחה ב-WhatsApp', toastOpts);
      } else if (ns?.channel_used === 'none' && ns?.reason) {
        toast.warning(`הזמנה נוצרה, אך שליחת ההודעה נכשלה: ${ns.reason}`, toastOpts);
      } else {
        toast.success('הזמנה נוצרה בהצלחה', toastOpts);
      }
```

**Why:** The toast action is gated on BOTH the flag AND `returnToDefect` being true. If the flag is off, `shouldOfferReturn` is false and the toast shows exactly the same text as today with no action button — identical to current prod behavior. `duration: 10000` only applies when the action is present; otherwise Sonner's default duration is used (unchanged).

**Do NOT:** Change the existing `onSuccess()` and `onClose()` calls at lines 1347-1348 — they stay as-is. Do NOT clear the draft here — if the toast auto-dismisses without user clicking, the draft stays until it expires (30 min) or the user reopens NewDefectModal.

---

### Task 9 — Use `GroupedSelectField` for companies dropdown in AddTeamMemberForm (feature-flagged)

**File:** `frontend/src/pages/ProjectControlPage.js`

**Find with:** `grep -n "companyOptions = companies.map" frontend/src/pages/ProjectControlPage.js`

**Line:** 1281 (in AddTeamMemberForm).

Add imports at top of file (near other imports):

```js
import { getBucketForTrade, getBucketLabel } from '../utils/categoryBuckets';
import GroupedSelectField from '../components/GroupedSelectField';
```

**Verify `useMemo` is imported** — grep for `useMemo` at the top of ProjectControlPage.js. If not in the react import, add it.

Replace line 1281:

```diff
- const companyOptions = companies.map(c => ({ value: c.id, label: c.name }));
+ const companyOptions = useMemo(() => {
+   const base = companies.map(c => ({ value: c.id, label: c.name, trade: c.trade }));
+   if (!FEATURES.TRADE_SORT_IN_TEAM_FORM) return base.map(c => ({ value: c.value, label: c.label }));
+   const activeKey = (tradeKey || prefillTrade || '').trim();
+   if (!activeKey || base.length === 0) return base.map(c => ({ value: c.value, label: c.label }));
+   const targetBucket = getBucketForTrade(activeKey);
+   if (!targetBucket) return base.map(c => ({ value: c.value, label: c.label }));
+   const matching = [];
+   const other = [];
+   for (const opt of base) {
+     const bucket = opt.trade ? getBucketForTrade(opt.trade) : null;
+     if (bucket && bucket === targetBucket) matching.push(opt);
+     else other.push(opt);
+   }
+   if (matching.length === 0) return base.map(c => ({ value: c.value, label: c.label }));
+   const bucketLabel = getBucketLabel(targetBucket) || activeKey;
+   const result = [
+     { value: `__header_match_${targetBucket}`, label: `תחום: ${bucketLabel}`, isHeader: true },
+     ...matching.map(m => ({ value: m.value, label: m.label })),
+   ];
+   if (other.length > 0) {
+     result.push({ value: '__header_other', label: 'חברות אחרות', isHeader: true, muted: true });
+     other.forEach(o => result.push({ value: o.value, label: o.label, muted: true }));
+   }
+   return result;
+ }, [companies, tradeKey, prefillTrade]);
```

Find the SelectField render for companies (line 1392):

**Find with:** `grep -n 'label="חברה' frontend/src/pages/ProjectControlPage.js`

**Change:**

```diff
-          <SelectField label="חברה *" value={companyId} onChange={setCompanyId} options={companyOptions} error={errors.companyId} emptyMessage="אין חברות – הוסף חברה למטה" />
+          {FEATURES.TRADE_SORT_IN_TEAM_FORM ? (
+            <GroupedSelectField label="חברה *" value={companyId} onChange={setCompanyId} options={companyOptions} error={errors.companyId} emptyMessage="אין חברות – הוסף חברה למטה" />
+          ) : (
+            <SelectField label="חברה *" value={companyId} onChange={setCompanyId} options={companyOptions} error={errors.companyId} emptyMessage="אין חברות – הוסף חברה למטה" />
+          )}
```

**Why:** When the flag is on, `companyOptions` may contain header/muted entries, so we route to `GroupedSelectField`. When the flag is off, `companyOptions` is the plain `{value, label}` list (bug-for-bug match to prod), and we route to the original `SelectField` — an identical render path to today.

**Do NOT:**
- Do NOT replace SelectField globally — only this single call site in AddTeamMemberForm.
- Do NOT change SelectField's props shape or behavior.
- Do NOT pass header/muted options to plain `SelectField` — that path only runs when the flag is off, and the options are guaranteed plain.

---

### Task 10 — Auto-open NewDefectModal on `?reopenDefect=1` in unit pages (feature-flagged)

**File 1:** `frontend/src/pages/UnitDetailPage.js`

**Find with:** `grep -n "NewDefectModal\|useSearchParams\|useParams" frontend/src/pages/UnitDetailPage.js`

Verify `useSearchParams` is imported from `react-router-dom`. If not, add it to the existing `react-router-dom` import line.

Add import:

```js
import { FEATURES } from '../config/features';
```

After the existing `useParams` line (line ~51):

```js
  const [searchParams, setSearchParams] = useSearchParams();
```

Add a new useEffect (place it near other effects; after `showDefectModal` state declaration around line 62):

```js
  // Auto-open NewDefectModal when arriving with ?reopenDefect=1 (from the
  // "add contractor and return" flow). Cleans up the URL param immediately
  // so back/forward doesn't reopen the modal indefinitely.
  // Gated on FEATURES.DEFECT_DRAFT_PRESERVATION — if flag is off, ?reopenDefect=1
  // is simply ignored (matches pre-batch behavior — the param didn't exist).
  useEffect(() => {
    if (!FEATURES.DEFECT_DRAFT_PRESERVATION) return;
    if (searchParams.get('reopenDefect') === '1') {
      setShowDefectModal(true);
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        next.delete('reopenDefect');
        return next;
      }, { replace: true });
    }
  }, [searchParams, setSearchParams]);
```

**File 2:** `frontend/src/pages/ApartmentDashboardPage.js`

**Find with:** `grep -n "NewDefectModal\|useSearchParams" frontend/src/pages/ApartmentDashboardPage.js`

Verify `useSearchParams` is imported. If not, add it.

Add import:

```js
import { FEATURES } from '../config/features';
```

After the existing `useParams` line (line ~83):

```js
  const [searchParams, setSearchParams] = useSearchParams();
```

Add the same effect (near `showDefectModal` state at line 99):

```js
  useEffect(() => {
    if (!FEATURES.DEFECT_DRAFT_PRESERVATION) return;
    if (searchParams.get('reopenDefect') === '1') {
      setShowDefectModal(true);
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        next.delete('reopenDefect');
        return next;
      }, { replace: true });
    }
  }, [searchParams, setSearchParams]);
```

**Why:** When the user clicks "חזור לליקוי" from the team tab, they land on the unit page with `?reopenDefect=1`. This effect detects that, opens the modal, and removes the param so refreshing/back won't re-trigger it. Two files because defects can be opened from either page. Gated on the same flag so the entire Fix A flow kill-switches cleanly.

**Do NOT:** Modify ProjectTasksPage.js — out of scope (that flow doesn't have a single unitId, so "return to defect" isn't meaningful there).

---

## Relevant files

### Modified:
- `frontend/src/components/NewDefectModal.js` — lines 13 (imports), ~877-884 (button onClick with flag gate), ~150 (new restore effect with flag gate)
- `frontend/src/pages/ProjectControlPage.js` — imports, line 1217 (AddTeamMemberForm signature), ~1221 (useNavigate), line 1281 (companyOptions with flag gate), line 1392 (SelectField/GroupedSelectField conditional), lines ~1336-1346 (success toast), line 2418 (TeamTab signature), line ~2685 (AddTeamMemberForm render), line 3591 (TeamTab render)
- `frontend/src/pages/UnitDetailPage.js` — imports, ~51 (useSearchParams), ~62 (new effect with flag gate)
- `frontend/src/pages/ApartmentDashboardPage.js` — imports, ~83 (useSearchParams), ~99 (new effect with flag gate)

### Created:
- `frontend/src/config/features.js`
- `frontend/src/utils/categoryBuckets.js`
- `frontend/src/utils/defectDraft.js`
- `frontend/src/components/GroupedSelectField.js`

### Untouched (CRITICAL):
- `frontend/src/components/BottomSheetSelect.js` (SelectField) — **ZERO DIFF required**
- `frontend/src/components/QuickAddCompanyModal.js` — zero changes
- `backend/` — zero changes
- `frontend/src/services/api.js` — zero changes
- `frontend/package.json` / `package-lock.json` — zero changes
- `frontend/src/pages/ProjectTasksPage.js` — zero changes (out of scope)

---

## DO NOT

- ❌ Do NOT modify `frontend/src/components/BottomSheetSelect.js` (SelectField). This is a hard line — the file is used in dozens of places across the app and the blast radius of any change is unacceptable. All grouping logic goes in the new `GroupedSelectField` wrapper.
- ❌ Do NOT change `QuickAddCompanyModal.js`. That's Batch 2a territory.
- ❌ Do NOT modify the 3 "+ הוסף חברה" buttons at NewDefectModal.js lines 811, 824, 851 — they already call `setShowQuickAddCompany(true)` correctly from Batch 2a.
- ❌ Do NOT touch the existing `onPointerDownOutside` + `onInteractOutside` guards on NewDefectModal's Dialog (line ~656-660) — that's the Batch 2a patch fix.
- ❌ Do NOT change the `modal={false}` prop on NewDefectModal's DialogPrimitive.Root — other flows depend on it.
- ❌ Do NOT persist images to IndexedDB, localStorage, or anywhere else — user explicitly chose to lose them.
- ❌ Do NOT clear the defect draft inside the AddTeamMemberForm success handler. Let NewDefectModal's restore effect clear it after applying.
- ❌ Do NOT change `teamInviteService.create` or any service call — the flow is front-end only.
- ❌ Do NOT rename `brikops_defect_draft_v1` — if you need a breaking schema change later, bump to v2 and migrate.
- ❌ Do NOT add a backend endpoint for drafts — keep everything client-side.
- ❌ Do NOT modify the `openInvite=1` URL handler at ProjectControlPage.js:3324-3336. It already does the right thing: deletes `openInvite`, sets `tab=team`, leaves everything else (including `prefillTrade` and `returnToDefect`) intact.
- ❌ Do NOT add a "cancel and return" button for users who enter the team tab but don't add a contractor. Out of scope — the 30-min sessionStorage TTL handles abandoned drafts.
- ❌ Do NOT try to preserve image File objects across navigation. The agreed behavior is: text fields survive, images must be re-attached.
- ❌ Do NOT modify ProjectTasksPage.js — no unitId context there.
- ❌ Do NOT make `FEATURES` flags dynamic (remote config, env reads, cookies, user-scoped). They are static `export const` values for safe, predictable rollout.
- ❌ Do NOT forget to gate BOTH Fix A surfaces (NewDefectModal button, NewDefectModal restore effect, toast action, parent page auto-open) on `FEATURES.DEFECT_DRAFT_PRESERVATION`. A partial gating is worse than no gating.
- ❌ Do NOT forget to gate BOTH Fix B surfaces (`companyOptions` sort, SelectField/GroupedSelectField switch) on `FEATURES.TRADE_SORT_IN_TEAM_FORM`.
- ❌ Do NOT add grouping/headers to SelectField when `tradeKey` and `prefillTrade` are both empty — that breaks existing team-tab behavior for non-contractor roles.
- ❌ Do NOT reorder Task 6's restore effect before the existing prefillData effect at lines 134-149 — prefillData must apply first so the unit-match guard has the right values.
- ❌ Do NOT add new dependencies. `sonner` is already used for toasts. `react-router-dom` already exports `useSearchParams` and `useNavigate`.
- ❌ Do NOT use `GroupedSelectField` anywhere except AddTeamMemberForm in this batch.
- ❌ Do NOT copy or fork SelectField into GroupedSelectField — wrap it with `<SelectField {...rest} ... />`. Imports stay at one level.

---

## VERIFY before commit

### 1. Grep sanity

```bash
# (a) New files exist:
test -f frontend/src/config/features.js && echo OK-features
test -f frontend/src/utils/categoryBuckets.js && echo OK-buckets
test -f frontend/src/utils/defectDraft.js && echo OK-draft
test -f frontend/src/components/GroupedSelectField.js && echo OK-grouped

# (b) SelectField (BottomSheetSelect.js) is NOT modified — THIS IS MANDATORY:
git diff --stat frontend/src/components/BottomSheetSelect.js
# Expected: empty. If any diff appears → abort, this breaks the spec's safety contract.

# (c) Feature flags file is correct shape:
grep -n "DEFECT_DRAFT_PRESERVATION\|TRADE_SORT_IN_TEAM_FORM" frontend/src/config/features.js
# Expected: 2 hits, both with `: true`.

# (d) FEATURES gate is referenced in all expected places:
grep -rn "FEATURES.DEFECT_DRAFT_PRESERVATION" frontend/src/
# Expected: at least 5 hits — NewDefectModal button, NewDefectModal restore effect,
# AddTeamMemberForm toast action, UnitDetailPage effect, ApartmentDashboardPage effect.

grep -rn "FEATURES.TRADE_SORT_IN_TEAM_FORM" frontend/src/
# Expected: at least 2 hits — companyOptions useMemo, GroupedSelectField/SelectField switch.

# (e) Draft save is wired into NewDefectModal button:
grep -n "saveDefectDraft" frontend/src/components/NewDefectModal.js
# Expected: 2 hits (import + onClick).

# (f) Draft load is wired into NewDefectModal restore effect:
grep -n "loadDefectDraft\|clearDefectDraft" frontend/src/components/NewDefectModal.js
# Expected: 2 hits in import + 1 each in restore effect = 3-4 lines.

# (g) returnToDefect prop is threaded end-to-end:
grep -n "returnToDefect" frontend/src/pages/ProjectControlPage.js
# Expected: at least 4 hits.

# (h) reopenDefect handling in both pages:
grep -n "reopenDefect" frontend/src/pages/UnitDetailPage.js frontend/src/pages/ApartmentDashboardPage.js
# Expected: at least 2 hits per file.

# (i) Trade-sort util is imported where used:
grep -n "getBucketForTrade\|getBucketLabel" frontend/src/pages/ProjectControlPage.js
# Expected: import + 2+ usages.

# (j) GroupedSelectField is used exactly once (in AddTeamMemberForm):
grep -rn "GroupedSelectField" frontend/src/ | grep -v GroupedSelectField.js
# Expected: 2 hits (import + usage in ProjectControlPage.js).

# (k) Backend untouched:
git diff --stat backend/ 2>/dev/null
# Expected: empty.

# (l) QuickAddCompanyModal untouched:
git diff --stat frontend/src/components/QuickAddCompanyModal.js
# Expected: empty.

# (m) No package changes:
git diff frontend/package.json frontend/package-lock.json
# Expected: empty.

# (n) ProjectTasksPage untouched:
git diff --stat frontend/src/pages/ProjectTasksPage.js
# Expected: empty.

# (o) Old route to ?tab=companies is gone from the flag-on path but still in the fallback:
grep -n "tab=companies" frontend/src/components/NewDefectModal.js
# Expected: exactly 1 hit (the fallback branch when flag is off).

# (p) The 3 "+ הוסף חברה" buttons are untouched:
grep -cn "setShowQuickAddCompany(true)" frontend/src/components/NewDefectModal.js
# Expected: 3 (exactly the same as before).
```

### 2. Build clean

```bash
cd frontend
npm run build
```

Expected: no new warnings, no new errors.

### 3. Manual tests

After deploy + hard refresh:

#### Test A — Main fix (Fix #4): contractor add preserves draft (flag ON)

1. Confirm `frontend/src/config/features.js` has `DEFECT_DRAFT_PRESERVATION: true`.
2. Open NewDefectModal from a unit page. Fill:
   - Title: "בדיקה באטץ' 2b"
   - Description: "ליקוי מיזוג חדש"
   - Category: `hvac` (מיזוג)
   - Priority: גבוה
   - Pick any company that has no contractors.
3. ✅ "אין קבלנים משויכים לחברה זו" appears with "+ הוסף קבלן" button.
4. Click "+ הוסף קבלן".
5. ✅ NewDefectModal closes. URL becomes `/projects/{pid}/control?tab=team&openInvite=1&returnToDefect=1&prefillTrade=hvac` (or similar).
6. ✅ After a moment, URL cleans to `/projects/{pid}/control?tab=team&returnToDefect=1&prefillTrade=hvac`.
7. ✅ AddTeamMemberForm is auto-open. Trade field pre-selected to `hvac` (מיזוג).
8. Fill phone "0501234567", name "שלמה בדיקה", role=contractor, pick a company, save.
9. ✅ Success toast: "הזמנה נשלחה..." with a "חזור לליקוי" action button.
10. Click "חזור לליקוי".
11. ✅ Navigates to `/projects/{pid}/units/{unitId}`. NewDefectModal opens automatically. Toast: "הטיוטה שוחזרה. יש לצרף תמונות מחדש."
12. ✅ Title shows "בדיקה באטץ' 2b", description filled, category=מיזוג, priority=גבוה, company still selected.
13. ✅ Images section is empty — re-attach at least one image.
14. Click submit → ✅ defect saves normally.
15. Open DevTools → Application → Session Storage → ✅ `brikops_defect_draft_v1` key is gone.

#### Test A-kill — Fix A kill-switch (flag OFF)

1. Flip `DEFECT_DRAFT_PRESERVATION` to `false` in `frontend/src/config/features.js`. Redeploy.
2. Hard refresh.
3. Open NewDefectModal. Fill fields. Click "+ הוסף קבלן".
4. ✅ Modal closes. Navigates to `/projects/{pid}/control?tab=companies` (NOT team — falls back to pre-batch behavior).
5. ✅ DevTools → Session Storage: NO `brikops_defect_draft_v1` key was written.
6. ✅ No "חזור לליקוי" button anywhere. No `?reopenDefect=1` handling.
7. Flip flag back to `true`. Redeploy for subsequent tests.

#### Test B — Trade-sort (flag ON)

1. Confirm `TRADE_SORT_IN_TEAM_FORM: true`.
2. Prepare: project with at least 5 companies across 2+ trades (e.g., 2 hvac, 1 electrical, 1 plumbing, 1 with no trade). If no such project exists, create companies on the Companies tab.
3. Open AddTeamMemberForm (Team tab → "הוסף חבר צוות" or via Test A).
4. Set role=contractor, trade=hvac.
5. ✅ Companies dropdown, in order:
   - Header "תחום: מיזוג" (small gray text, unclickable)
   - 2 hvac companies
   - Header "חברות אחרות" (smaller, lighter gray)
   - Other companies (slightly dimmed)
6. ✅ Clicking a header does nothing (no selection).
7. ✅ Clicking a matching company selects it.
8. Change trade to `electrical`. ✅ Dropdown re-sorts.
9. Change role to `management_team` (no trade). ✅ Dropdown shows all companies without headers (normal behavior).

#### Test B-kill — Fix B kill-switch (flag OFF)

1. Flip `TRADE_SORT_IN_TEAM_FORM` to `false`. Redeploy. Hard refresh.
2. Open AddTeamMemberForm with trade=hvac.
3. ✅ Companies dropdown shows all companies in plain order — no headers, no muting. Exactly as prod today.
4. ✅ No dim effect on any option.
5. Flip flag back to `true`. Redeploy.

#### Test C — Regression: normal defect creation

1. Open NewDefectModal from any unit. Fill everything normally. Do NOT click "+ הוסף קבלן".
2. Submit.
3. ✅ Defect saves normally. No "הטיוטה שוחזרה" toast. SessionStorage has no `brikops_defect_draft_v1` key.

#### Test D — Regression: cancel path

1. Open NewDefectModal. Fill some fields. Click X or ESC or ביטול.
2. ✅ Modal closes. SessionStorage has no `brikops_defect_draft_v1` key.
3. Reopen NewDefectModal.
4. ✅ Opens empty (no "הטיוטה שוחזרה" toast).

#### Test E — Regression: "+ הוסף חברה" inline modal (Batch 2a)

1. Open NewDefectModal. Pick a project with zero companies.
2. ✅ "+ הוסף חברה" button appears.
3. Click it.
4. ✅ QuickAddCompanyModal opens ON TOP OF NewDefectModal (parent stays visible, no navigation).
5. Fill + save quick-add.
6. ✅ Quick-add closes. NewDefectModal still there with everything intact. New company selected.

#### Test F — Edge case: expired draft

1. Open DevTools → Application → Session Storage.
2. Manually set `brikops_defect_draft_v1` to `{"createdAt":0, "title":"old"}`.
3. Open NewDefectModal.
4. ✅ No "הטיוטה שוחזרה" toast. Form is empty. The expired key is auto-removed.

#### Test G — Edge case: draft for different unit

1. Open NewDefectModal on unit A. Fill fields. Click "+ הוסף קבלן".
2. Without adding a contractor, manually navigate to unit B.
3. Open NewDefectModal on unit B.
4. ✅ No "הטיוטה שוחזרה" toast. Form is empty for unit B.
5. ✅ SessionStorage still has the draft (tied to unit A).
6. Navigate back to unit A → manually open NewDefectModal.
7. ✅ Draft restores for unit A (within 30 min).

#### Test H — Regression: other SelectField callers untouched

1. Open Companies tab → edit a company → change trade in the dropdown.
2. ✅ Trade dropdown behaves exactly like before (uses plain SelectField — zero change).
3. Navigate to any other page using SelectField (e.g., AddCompanyForm, edit forms).
4. ✅ All dropdowns work identically to pre-batch.

---

## Commit message (exactly)

```
feat(defect-flow): preserve draft across contractor-add flow + sort companies by trade (feature-flagged)

Fix #4: When user clicks "+ הוסף קבלן" inside NewDefectModal (because the
selected company has no assigned contractors), save text fields to
sessionStorage, navigate to team tab with openInvite+prefillTrade+returnToDefect
params, show "חזור לליקוי" action in the success toast, and on return restore
the saved fields into a fresh NewDefectModal. Images are intentionally lost
(File objects can't be serialized) — a toast informs the user.

Trade-sort: in AddTeamMemberForm, when tradeKey or prefillTrade is set,
sort companies whose trade maps to the same backend bucket to the top with
a "תחום: {label}" header, and group the rest under a muted "חברות אחרות"
header. Rendering uses a new GroupedSelectField wrapper — SelectField
(BottomSheetSelect.js) is NOT modified to avoid blast radius across the app.

Both behaviors are gated by compile-time flags in frontend/src/config/features.js
(DEFECT_DRAFT_PRESERVATION, TRADE_SORT_IN_TEAM_FORM). Flipping either to false
restores the exact pre-batch behavior.

New files:
- frontend/src/config/features.js (feature flags)
- frontend/src/utils/categoryBuckets.js (CATEGORY_TO_BUCKET, BUCKET_LABELS, helpers)
- frontend/src/utils/defectDraft.js (sessionStorage save/load/clear + 30-min TTL)
- frontend/src/components/GroupedSelectField.js (SelectField wrapper for grouped options)

Modified:
- NewDefectModal: updated "+ הוסף קבלן" handler (flag-gated); added
  draft-restore effect on open (flag-gated)
- ProjectControlPage: threaded returnToDefect prop; added "חזור לליקוי"
  toast action (flag-gated); sorted AddTeamMemberForm companyOptions by
  trade bucket (flag-gated); routes to GroupedSelectField when flag is on
- UnitDetailPage, ApartmentDashboardPage: auto-open NewDefectModal on
  ?reopenDefect=1 (flag-gated)

BottomSheetSelect.js (SelectField) untouched. QuickAddCompanyModal untouched.
Backend untouched. No new deps.
```

---

## Deploy

```bash
./deploy.sh --prod
```

OTA only (no native changes).

**Before declaring fix complete, Zahi should:**

1. Hard refresh browser (Cmd+Shift+R) or close/reopen the native app.
2. Run Test A end-to-end (main flow, flags ON).
3. Run Test B (trade-sort, flags ON).
4. Run Test E (regression: Batch 2a "+ הוסף חברה" still works).
5. Run Test H (regression: other SelectField callers untouched).
6. If something breaks in prod — flip the relevant flag to `false` in `frontend/src/config/features.js`, redeploy. No code revert needed.

---

## Definition of Done

- [ ] Four new files created: `features.js`, `categoryBuckets.js`, `defectDraft.js`, `GroupedSelectField.js`
- [ ] `BottomSheetSelect.js` has ZERO diff (`git diff --stat` is empty for that file)
- [ ] All 16 grep sanity checks pass
- [ ] `npm run build` clean, no new warnings
- [ ] Test A passes (main flow, flags ON)
- [ ] Test A-kill passes (Fix A kill-switch → pre-batch behavior exactly)
- [ ] Test B passes (trade-sort with headers, flags ON)
- [ ] Test B-kill passes (Fix B kill-switch → pre-batch behavior exactly)
- [ ] Test C passes (normal defect creation — no regression)
- [ ] Test D passes (cancel path — no false restore)
- [ ] Test E passes (Batch 2a inline "+ הוסף חברה" still works)
- [ ] Test F passes (expired draft auto-cleared)
- [ ] Test G passes (draft for different unit not misapplied)
- [ ] Test H passes (other SelectField callers untouched)
- [ ] `./deploy.sh --prod` succeeded
