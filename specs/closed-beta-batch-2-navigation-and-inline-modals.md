# #411 — Closed-Beta Batch 2 — Navigation + Inline Modals

## What & Why

Three fixes that address the most painful UX gap in the defect-creation flow: users lose all their typed content when they try to add a company or contractor mid-form. Plus a small default-tab fix on project entry. Plus a new UX improvement: smart-sort company dropdown by trade in the add-contractor form.

**Critical constraint:** production hot-fix — real customers using the app. The rule is "do not break anything else." Extractions are done by moving existing JSX verbatim — no logic rewrites.

## Done looks like

1. **Fix #2 — Project entry:** Clicking any project card from the projects list lands on the "מבנה" (structure) workMode, regardless of what tab the user last visited in that project. localStorage persistence for user-initiated tab clicks still works normally.

2. **Fix #3 — Inline "הוסף חברה":** In NewDefectModal, clicking "+ הוסף חברה" (3 places — lines 809, 822, 849) opens the existing `AddCompanyForm` as a nested modal ON TOP of NewDefectModal. User fills the form, saves, and the new company:
   - Appears in the NewDefectModal's company dropdown
   - Is auto-selected
   - User continues writing the defect without losing any typed content

3. **Fix #4 — Inline "הוסף קבלן":** In NewDefectModal, clicking "+ הוסף קבלן" (line 876) opens the existing `AddTeamMemberForm` as a nested modal ON TOP of NewDefectModal. Form is pre-populated with `role=contractor` (user can change it), `company_id=<currently selected company>`, and `trade_key=<defect's category>` — user can change any of these. Save → new contractor appears in dropdown, auto-selected, form state preserved.

4. **New feature — Trade-sort in contractor form:** When adding a contractor in `AddTeamMemberForm` and a trade is selected, the "חברה" dropdown shows companies with **matching trade first** (grouped/labeled), then companies with other/no trade below. User can still pick any company — this is a sorting preference, not enforcement.

## Out of scope

- ❌ Any change to the contractor↔company enforcement logic (backend `_trades_match()`). That stays. The trade-sort is a **UI sort only**, not a validation.
- ❌ Creating brand-new forms. All nested modals REUSE existing `AddCompanyForm` / `AddTeamMemberForm` — we extract them to shared components, we don't rewrite.
- ❌ Any change to the backend. `git diff backend/` MUST be empty.
- ❌ Changes to NewDefectModal's defect-creation logic, photo handling, category selection, etc. — only the 4 navigate calls and the nested-modal integration.
- ❌ The 4th navigate call was Fix #4 (add contractor). The first 3 are Fix #3 (add company). Fix #4 behaves identically to Fix #3 but opens AddTeamMemberForm instead.
- ❌ Changes to z-indexes anywhere.
- ❌ Fixing NewDefectModal's `z-50` (it's low compared to other modals but not broken). Out of scope here.
- ❌ Any change to how contractors are invited (SMS flow, phone verification). The existing AddTeamMemberForm already handles that — we're just reusing it.
- ❌ `ProjectControlPage` structural changes — only replace the inline form JSX with an import, no other refactor.
- ❌ Changes to company/contractor dropdown filter logic inside NewDefectModal beyond the trade-sort in AddTeamMemberForm.

## Architectural constraints

- Relative imports only (`../components/...`). No `@/` alias.
- No new deps. `git diff frontend/package.json frontend/package-lock.json` MUST be empty.
- No backend changes.
- BottomSheetModal `z-[9998]` naturally stacks above NewDefectModal (`z-50`) — no z-index manipulation needed.
- Use existing `projectCompanyService.create` and the existing AddTeamMemberForm's submit handler. Do NOT invent new API paths.

## Tasks

### Task 1 — Fix #2: Default landing tab = "מבנה"

**File:** `frontend/src/utils/navigation.js:9`

**Change:**
```diff
  if (MANAGEMENT_ROLES.includes(role)) {
-   navigate(`/projects/${id}/control`);
+   navigate(`/projects/${id}/control?workMode=structure`);
  } else if (role === 'contractor') {
```

**Why:** `ProjectControlPage` already gives priority order URL param → localStorage → default. Adding `?workMode=structure` to the navigate ensures the URL wins, so users always land on structure regardless of their last-clicked tab (stored in localStorage).

**DO NOT:**
- ❌ Change the contractor branch or the default branch of navigateToProject.
- ❌ Remove the localStorage save logic in ProjectControlPage — it should still work for subsequent tab clicks.

---

### Task 2 — Extract `AddCompanyForm` to a standalone component

**New file:** `frontend/src/components/AddCompanyForm.js`

**Source to extract:** `frontend/src/pages/ProjectControlPage.js:965-1160` (~195 lines)

**How to extract:**

1. **Create the new file** `frontend/src/components/AddCompanyForm.js`
2. **Move the entire `AddCompanyForm` inline component definition** from ProjectControlPage.js to the new file. Include the surrounding `BottomSheetModal` wrapper if it's part of the component.
3. **Props interface:**
   ```javascript
   export default function AddCompanyForm({ open, onOpenChange, onSuccess, projectId }) { ... }
   ```
   - `open`: boolean — controls sheet visibility
   - `onOpenChange(bool)`: close handler
   - `onSuccess(newCompany)`: called with the full company object after a successful save; caller uses this to refresh its dropdown and auto-select
   - `projectId`: string — needed for the API call
4. **Internal state:** whatever was local inside the inline form — keep it inside the new component unchanged.
5. **API call:** the existing `projectCompanyService.create(projectId, payload)` call stays exactly as-is. After a successful save, call `onSuccess(createdCompany)` before `onOpenChange(false)`.
6. **Imports:** only what the form actually uses. Remove any that belong to ProjectControlPage's surrounding context.

**In `ProjectControlPage.js`:**

1. Import the new component at the top:
   ```javascript
   import AddCompanyForm from '../components/AddCompanyForm';
   ```
2. Remove the inline `AddCompanyForm` definition (lines ~965-1160).
3. Replace the inline usage (wherever `<AddCompanyForm />` was rendered — probably in CompaniesTab near line 2725) with:
   ```jsx
   <AddCompanyForm
     open={showAddForm}
     onOpenChange={setShowAddForm}
     onSuccess={(company) => {
       setCompanies(prev => [...prev, company]);  // or loadCompanies() — whatever was happening after save
       setShowAddForm(false);
     }}
     projectId={projectId}
   />
   ```
4. **Verify:** the CompaniesTab's behavior is identical to before — same visual, same save behavior, same error handling.

**DO NOT:**
- ❌ Rewrite the form's internal logic. Move it verbatim.
- ❌ Change the API call signature.
- ❌ Change the "+ הוסף תחום חדש" inline trade-creation flow that's part of the form.
- ❌ Rename existing state variables inside the form.
- ❌ Reorder or restyle fields.
- ❌ Change the BottomSheetModal wrapper's z-index or styling.

---

### Task 3 — Integrate `AddCompanyForm` into NewDefectModal

**File:** `frontend/src/components/NewDefectModal.js`

**State addition:**
Add at the top of the component (near other `useState` calls):
```javascript
const [showAddCompanyModal, setShowAddCompanyModal] = useState(false);
```

**Replace the 3 navigate calls for "הוסף חברה" (lines ~809, 822, 849):**

For each:
```diff
- onClick={() => { onClose(); if (projectId) navigate(`/projects/${projectId}/control?tab=companies`); }}
+ onClick={() => setShowAddCompanyModal(true)}
```

**Render AddCompanyForm near the end of the JSX (just before the closing DialogPrimitive.Root or equivalent):**

```jsx
<AddCompanyForm
  open={showAddCompanyModal}
  onOpenChange={setShowAddCompanyModal}
  projectId={projectId}
  onSuccess={(newCompany) => {
    // Append to the companies list that feeds the dropdown
    setProjectCompanies(prev => [...prev, newCompany]);
    // Auto-select the new company
    setCompanyId(newCompany.id);
    // Close the nested modal
    setShowAddCompanyModal(false);
  }}
/>
```

**Import at the top:**
```javascript
import AddCompanyForm from './AddCompanyForm';
```

**⚠️ Important:** identify the actual state setter names used in NewDefectModal for the companies list (may be `setCompanies`, `setProjectCompanies`, `setAvailableCompanies`). Use the actual name — do not guess. Confirm with:
```bash
grep -n "setCompanies\|setProjectCompanies\|setAvailableCompanies" frontend/src/components/NewDefectModal.js
```

**DO NOT:**
- ❌ Call `onClose()` on the parent NewDefectModal when opening the nested modal — user must stay in their defect form.
- ❌ Change the trigger button JSX layout, label, or icons — only the onClick.
- ❌ Add a 4th "+ הוסף חברה" trigger — only the 3 existing ones.
- ❌ Touch the 4th navigate call (line 876) — that's for "+ הוסף קבלן", handled in Task 5.

---

### Task 4 — Extract `AddTeamMemberForm` to a standalone component

**New file:** `frontend/src/components/AddTeamMemberForm.js`

**Source to extract:** `frontend/src/pages/ProjectControlPage.js:1217-1422` (~205 lines)

**How to extract:** Same pattern as Task 2.

**Props interface:**
```javascript
export default function AddTeamMemberForm({
  open,
  onOpenChange,
  onSuccess,
  projectId,
  defaults = {}, // { role?, company_id?, trade_key? } — optional prefill
  companies,     // the list of companies in the project (for the dropdown)
  trades,        // the list of trades (for the dropdown)
  // ... any other props the inline form currently needs from ProjectControlPage state
}) { ... }
```

- `defaults`: optional object with `role`, `company_id`, `trade_key` — used to pre-populate the form when opened from NewDefectModal with context.
- `onSuccess(newMember)`: called with the newly created member/contractor object after save.

**⚠️ Careful with form's shared state:** AddTeamMemberForm in ProjectControlPage probably depends on local state like `setTeamMembers`, `memberToInvite`, trade list, company list, etc. Those need to become props or internal state of the extracted component.

**Exact props needed — investigate before extraction:**
```bash
grep -n "AddTeamMemberForm\|memberToInvite\|teamMembers\|setTeamMembers" frontend/src/pages/ProjectControlPage.js | head -30
```

**In `ProjectControlPage.js`:**

Same as Task 2 — replace inline with import, render with identical behavior.

**DO NOT:**
- ❌ Change the form's logic, fields, or validation.
- ❌ Change the API call (`authService.*` or whichever service the form uses).
- ❌ Change the invite/SMS flow — the existing form handles this; do not touch it.
- ❌ Add `company_id` / `trade_key` auto-fill logic — that lives in the `defaults` prop handling, driven by the caller (Task 5).

---

### Task 5 — Integrate `AddTeamMemberForm` into NewDefectModal + Fix #4

**File:** `frontend/src/components/NewDefectModal.js`

**State addition:**
```javascript
const [showAddContractorModal, setShowAddContractorModal] = useState(false);
```

**Replace the 1 navigate call for "הוסף קבלן" (line ~876):**

```diff
- onClick={() => { onClose(); if (projectId) navigate(`/projects/${projectId}/control?tab=companies`); }}
+ onClick={() => setShowAddContractorModal(true)}
```

**Render AddTeamMemberForm near the end of the JSX (after the AddCompanyForm from Task 3):**

```jsx
<AddTeamMemberForm
  open={showAddContractorModal}
  onOpenChange={setShowAddContractorModal}
  projectId={projectId}
  companies={projectCompanies}  // use the same state as the company dropdown
  trades={trades}               // the list of trades already available in NewDefectModal
  defaults={{
    role: 'contractor',
    company_id: companyId,      // currently selected company in NewDefectModal
    trade_key: selectedCategory || null,  // defect's category → contractor's trade_key
  }}
  onSuccess={(newMember) => {
    // Append to the project members list that feeds the contractor dropdown
    setProjectMembers(prev => [...prev, newMember]);
    // Auto-select the new contractor as assignee
    if (newMember.role === 'contractor') {
      setContractorId(newMember.user_id || newMember.id);
    }
    setShowAddContractorModal(false);
  }}
/>
```

**Import at the top:**
```javascript
import AddTeamMemberForm from './AddTeamMemberForm';
```

**⚠️ Important:** identify actual state names in NewDefectModal — `setProjectMembers` is a guess, the real name may differ. Confirm first:
```bash
grep -n "setProjectMembers\|setMembers\|setContractorId\|setAssignee" frontend/src/components/NewDefectModal.js
```

**DO NOT:**
- ❌ Force `role='contractor'` — the user can change it. We just default it.
- ❌ Disable any fields in AddTeamMemberForm when opened from NewDefectModal. User retains full control.
- ❌ Close NewDefectModal when opening the nested modal.
- ❌ Add a new backend endpoint or service method.

---

### Task 6 — Trade-sort in AddTeamMemberForm company dropdown

**File:** `frontend/src/components/AddTeamMemberForm.js` (the new extracted component from Task 4)

**The feature:** when the form has a `trade_key` selected AND the role is `contractor`, the "חברה" dropdown displays:

1. **Top group:** companies whose `trade` field matches the selected `trade_key` (after bucket mapping).
   - Group header: `תחום: <trade label>` (e.g., "תחום: אינסטלציה").
   - Visual: normal size, highlighted subtly (e.g., amber left-border or bold).
2. **Bottom group:** companies with different/no trade.
   - Group header: `חברות אחרות`.
   - Visual: slightly muted (e.g., lighter text color, smaller font).
3. User can pick from either group. No enforcement.

**Implementation:**

```javascript
import { CATEGORY_TO_BUCKET } from '../utils/categoryBuckets';  // or wherever the map lives

function groupCompaniesByTradeMatch(companies, selectedTradeKey) {
  if (!selectedTradeKey) return { match: [], other: companies };

  const targetBucket = CATEGORY_TO_BUCKET[selectedTradeKey] || selectedTradeKey;
  const match = [];
  const other = [];

  for (const c of companies) {
    const companyBucket = CATEGORY_TO_BUCKET[c.trade] || c.trade;
    if (companyBucket === targetBucket && c.trade) {
      match.push(c);
    } else {
      other.push(c);
    }
  }
  return { match, other };
}
```

**In the dropdown JSX:**

```jsx
{(() => {
  const { match, other } = groupCompaniesByTradeMatch(companies, selectedTradeKey);
  return (
    <>
      {match.length > 0 && (
        <>
          <div className="px-3 py-1.5 text-xs font-bold text-slate-700 bg-amber-50 border-b border-amber-100">
            תחום: {tradeLabel(selectedTradeKey)}
          </div>
          {match.map(c => (
            <DropdownItem key={c.id} value={c.id} /* normal styling */>
              {c.name}
            </DropdownItem>
          ))}
        </>
      )}
      {other.length > 0 && (
        <>
          <div className="px-3 py-1.5 text-xs font-medium text-slate-400 border-b border-slate-100 mt-1">
            חברות אחרות
          </div>
          {other.map(c => (
            <DropdownItem key={c.id} value={c.id} className="text-slate-500"> {/* muted */}
              {c.name}
            </DropdownItem>
          ))}
        </>
      )}
    </>
  );
})()}
```

**⚠️ `CATEGORY_TO_BUCKET` availability:** the backend has this mapping in `backend/contractor_ops/bucket_utils.py`. For the frontend to use it without a backend call, we need a frontend copy.

**Investigate first** — is there already a frontend bucket map?
```bash
grep -rn "CATEGORY_TO_BUCKET\|BUCKET_LABELS\|categoryBuckets" frontend/src/
```

- If yes: use it.
- If no: **create `frontend/src/utils/categoryBuckets.js`** with the same mapping as backend. Keep it in sync manually for now (document this in a comment).

**Trade label helper:** get the human-readable label for a trade_key (e.g., `'plumbing'` → `'אינסטלציה'`). Likely already in `frontend/src/i18n/` or `actionLabels.js`. Find with:
```bash
grep -rn "plumbing\|אינסטלציה\|tradeLabel" frontend/src/utils/ frontend/src/i18n/
```

**DO NOT:**
- ❌ Change the API — the dropdown data comes from the same `companies` prop.
- ❌ Add a second API call to filter companies by trade — do it client-side.
- ❌ Prevent selection of "other" companies — the user can pick any.
- ❌ Apply the sort when role !== 'contractor' — only when contractor role is selected.
- ❌ Apply the sort when `selectedTradeKey` is empty — show a flat list in that case.

---

## Relevant files

| File | Action | Approx lines |
|---|---|---|
| `frontend/src/utils/navigation.js` | MODIFY line 9 | 1 line |
| `frontend/src/components/AddCompanyForm.js` | CREATE | ~195 lines (extracted) |
| `frontend/src/components/AddTeamMemberForm.js` | CREATE | ~205 lines (extracted) |
| `frontend/src/pages/ProjectControlPage.js` | MODIFY — import + replace 2 inline blocks | ~400 lines removed, ~15 lines added |
| `frontend/src/components/NewDefectModal.js` | MODIFY — 4 onClick changes, 2 nested modals, 2 state additions | ~30 lines |
| `frontend/src/utils/categoryBuckets.js` | CREATE (if not found) | ~40 lines |

**Total:** ~2 new files (or 3 if categoryBuckets doesn't exist), 3 files modified.

---

## DO NOT (cross-cutting)

- ❌ Do NOT change any backend file.
- ❌ Do NOT add new deps.
- ❌ Do NOT change existing API calls or invent new endpoints.
- ❌ Do NOT change z-indexes anywhere.
- ❌ Do NOT rewrite forms. Extract verbatim.
- ❌ Do NOT add form validation beyond what's already in the inline forms.
- ❌ Do NOT change the user's defect form state when a nested modal opens — NewDefectModal state is preserved.
- ❌ Do NOT touch the 4th navigate call (line 876) in Task 3 — it's for contractor (Task 5).
- ❌ Do NOT add trade enforcement anywhere. The trade-sort is UI-only.
- ❌ Do NOT change the `_trades_match()` backend logic or `force_category_change` bypass.
- ❌ Do NOT change the invite/SMS flow — AddTeamMemberForm already handles it; reuse unchanged.
- ❌ Do NOT change ProjectControlPage's behavior when adding a company/member from the standalone page — it must work identically to before.
- ❌ Do NOT refactor other parts of ProjectControlPage while extracting. This is a hot-fix, not a cleanup.
- ❌ Do NOT rename any state variables. Keep all names intact.

---

## VERIFY before commit

### 1. Grep sanity

```bash
# (a) No backend changes:
git diff --stat backend/
# Expected: empty.

# (b) No new deps:
git diff frontend/package.json frontend/package-lock.json
# Expected: empty.

# (c) Navigation.js fix applied:
grep -n "navigate(\`/projects/\${id}/control?workMode=structure\`)" frontend/src/utils/navigation.js
# Expected: 1 hit.

# (d) New files exist:
ls frontend/src/components/AddCompanyForm.js frontend/src/components/AddTeamMemberForm.js
# Expected: both files present.

# (e) ProjectControlPage uses the new components:
grep -n "import AddCompanyForm\|import AddTeamMemberForm" frontend/src/pages/ProjectControlPage.js
# Expected: 2 hits.

# (f) NewDefectModal uses the new components:
grep -n "import AddCompanyForm\|import AddTeamMemberForm" frontend/src/components/NewDefectModal.js
# Expected: 2 hits.

# (g) No more navigate to /control?tab=companies in NewDefectModal:
grep -n "navigate.*control.*tab=companies" frontend/src/components/NewDefectModal.js
# Expected: empty.

# (h) No inline AddCompanyForm or AddTeamMemberForm definitions left in ProjectControlPage:
grep -n "^function AddCompanyForm\|^const AddCompanyForm\|^function AddTeamMemberForm\|^const AddTeamMemberForm" frontend/src/pages/ProjectControlPage.js
# Expected: empty (they're now imports, not definitions).

# (i) Trade-sort helper exists in AddTeamMemberForm:
grep -n "groupCompaniesByTradeMatch\|CATEGORY_TO_BUCKET" frontend/src/components/AddTeamMemberForm.js
# Expected: at least 1 hit.

# (j) categoryBuckets utility (if created):
ls frontend/src/utils/categoryBuckets.js 2>/dev/null || echo "not created (OK if bucket map already existed elsewhere)"
```

### 2. Build clean

```bash
cd frontend
npm run build
```
Expected: no new warnings beyond existing baseline.

### 3. Manual tests

#### Fix #2 — Default landing tab
- Log in as PM/owner
- Navigate to `/projects/<id>/control` → click "ליקויים" tab to switch
- Navigate back to `/projects` (via the "הפרויקטים שלי" button)
- Click the same project again
- ✅ Lands on **"מבנה"** tab (not "ליקויים" as saved in localStorage)

#### Fix #3 — Inline Add Company (×3 triggers)
For each of 3 scenarios (empty companies, filtered empty, inline link):
- Open NewDefectModal, type a title ("בדיקה inline חברה"), select a category, pick location
- Trigger the corresponding "+ הוסף חברה" button
- ✅ AddCompanyForm **opens as a BottomSheet ON TOP of NewDefectModal** (NewDefectModal still visible behind it)
- Fill company name "חברת בדיקה A", trade, contact
- Save
- ✅ BottomSheet closes automatically
- ✅ User back in NewDefectModal with title + category + location **still typed**
- ✅ "חברת בדיקה A" **selected in the company dropdown**
- Continue completing defect, submit
- ✅ Defect saves successfully with the new company

#### Fix #4 — Inline Add Contractor
- Same flow, but select an existing company first, then trigger "+ הוסף קבלן"
- ✅ AddTeamMemberForm opens as BottomSheet
- ✅ Form has `role=contractor` pre-selected (user can change)
- ✅ `company_id` pre-selected to the current company
- ✅ `trade_key` pre-selected if a category was picked in the defect
- Fill contractor name + phone, confirm, save
- ✅ New contractor appears in the dropdown, auto-selected
- ✅ Continue defect, submit — defect assigned to new contractor

#### New feature — Trade-sort
- In AddTeamMemberForm, select role=contractor
- Select trade=אינסטלציה (plumbing)
- Open the "חברה" dropdown
- ✅ **Top group "תחום: אינסטלציה"** — lists only companies with trade matching (plumbing or bucket equivalent)
- ✅ **Bottom group "חברות אחרות"** — all other companies, slightly muted
- ✅ Can still click and select any company from either group

#### Regression — ProjectControlPage still works standalone
- Open `/projects/<id>/control?tab=companies` directly (without NewDefectModal)
- Click "+ הוסף חברה"
- ✅ Same BottomSheet opens, same behavior as before
- Save → company appears in the companies list
- Same flow for `/control?tab=team` → "+ הוסף איש צוות" → AddTeamMemberForm works identically

### 4. Edge cases

- **Form state preserved:** Fill NewDefectModal fully, open AddCompanyForm, cancel (X button) → return to NewDefectModal with all fields still filled.
- **Save failure:** if AddCompanyForm's save fails (e.g., network error), BottomSheet stays open with an error toast. NewDefectModal state unchanged.
- **Multiple adds in a row:** add company → save, then immediately add contractor → save. Both should work, state preserved.

---

## Commit message (exactly)

```
feat(ui): Batch 2 closed-beta — inline modals + nav default

Three closed-beta fixes that clean up the defect creation flow:

1) navigation.js: projectToNavigate() now appends ?workMode=structure
   to the /control URL so clicking a project card always lands on the
   "מבנה" tab, regardless of the tab the user last visited. localStorage
   still drives intra-project tab-switching.

2) NewDefectModal + AddCompanyForm: extract the inline AddCompanyForm
   from ProjectControlPage into a standalone component under
   components/. Wire it up as a nested BottomSheet modal inside
   NewDefectModal that replaces the three navigate() calls to
   /control?tab=companies. User no longer loses their defect form
   when they need to add a new company. ProjectControlPage continues
   to use the same form via the extracted component — no behavior
   change there.

3) NewDefectModal + AddTeamMemberForm: same pattern for the "+ הוסף
   קבלן" path. AddTeamMemberForm extracted from ProjectControlPage.
   Invoked from NewDefectModal with role=contractor,
   company_id=<current>, trade_key=<defect category> pre-filled —
   user can still change any of them. Reuses the existing invite/SMS
   flow unchanged.

4) New feature in AddTeamMemberForm: when adding a contractor with a
   trade selected, the company dropdown shows matching-trade companies
   in a top group ("תחום: <name>"), and other companies below in a
   muted group ("חברות אחרות"). User can still pick any company — UI
   sort only, no enforcement.

BottomSheetModal's z-[9998] naturally stacks above NewDefectModal's
z-50, so nested dialogs work without z-index adjustments.

No backend changes. No new deps. No API changes.
```

---

## Deploy

```bash
./deploy.sh --prod
```

OTA only (no native changes).

**Post-deploy send to Zahi:**
- `git log -1 --stat`
- Unified diff
- `git diff --stat backend/` (must be empty)
- Output of 10 grep checks from VERIFY §1
- Screenshots on mobile 375px:
  1. NewDefectModal with text typed
  2. Nested AddCompanyForm open ON TOP of NewDefectModal (both visible)
  3. Return to NewDefectModal with company selected + typed text preserved
  4. AddTeamMemberForm with company dropdown open showing the two groups ("תחום: X" + "חברות אחרות")
  5. ProjectControlPage companies tab still working (regression)
  6. ProjectControlPage team tab still working (regression)

---

## Definition of Done

- [ ] `navigation.js:9` appends `?workMode=structure`
- [ ] `AddCompanyForm.js` created, extracted from ProjectControlPage
- [ ] `AddTeamMemberForm.js` created, extracted from ProjectControlPage
- [ ] ProjectControlPage imports both new components — inline definitions removed
- [ ] NewDefectModal imports both new components + wires them as nested modals
- [ ] 3 navigate calls for "הוסף חברה" replaced with `setShowAddCompanyModal(true)`
- [ ] 1 navigate call for "הוסף קבלן" replaced with `setShowAddContractorModal(true)`
- [ ] Trade-sort implemented in AddTeamMemberForm (conditional on role=contractor + trade_key selected)
- [ ] All 10 grep checks from VERIFY §1 pass
- [ ] `npm run build` succeeds with no new warnings
- [ ] All manual tests from VERIFY §3 pass
- [ ] All regression tests for ProjectControlPage companies+team tabs pass
- [ ] `git diff --stat backend/` is empty
- [ ] `git diff frontend/package.json` is empty
- [ ] Screenshots sent to Zahi
- [ ] `./deploy.sh --prod` succeeded
