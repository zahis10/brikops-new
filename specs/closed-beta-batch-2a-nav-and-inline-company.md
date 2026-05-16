# #412 — Closed-Beta Batch 2a — Default landing tab + inline Add Company

## What & Why

Two closed-beta fixes, deliberately kept small and safe. No code extraction. No changes to existing forms. No backend changes.

- **Fix #2:** Clicking any project card lands on the "מבנה" tab always.
- **Fix #3:** In the defect creation flow, adding a new company happens in a small inline modal instead of navigating away and losing the typed content.

Fix #4 (add contractor) and the trade-sort feature are deferred to Batch 2b — their solutions are different enough to warrant a separate spec.

## Done looks like

1. **Fix #2:** User clicks any project from the projects list → lands on `/projects/:id/control?workMode=structure` → "מבנה" tab is active, regardless of what tab they last visited in that project.

2. **Fix #3:** User opens NewDefectModal, types a title + description + picks category, and reaches the "שייך חברה" section. If no company matches their need, they click any of the 3 "+ הוסף חברה" buttons:
   - A small modal (let's call it `QuickAddCompanyModal`) opens on top of NewDefectModal
   - NewDefectModal stays visible behind it
   - The quick-add form has 4 fields: שם חברה (required), תחום (dropdown, optional), איש קשר (optional), טלפון (optional)
   - User fills and saves → the new company appears in NewDefectModal's company dropdown, auto-selected
   - All previously-typed defect fields are preserved

## Out of scope

- ❌ Fix #4 (add contractor) — **deferred to Batch 2b.** Line 876 of NewDefectModal stays untouched.
- ❌ The trade-sort feature in the contractor dropdown — **deferred to Batch 2b.**
- ❌ Any extraction of existing forms. `ProjectControlPage.js` is NOT touched. The existing inline `AddCompanyForm` there stays exactly as-is.
- ❌ "+ הוסף תחום חדש" inline flow — the QuickAddCompanyModal uses the existing list of trades via dropdown only. If user needs to add a new trade, they use the full companies management page.
- ❌ Company suggestions dropdown (search existing companies across projects) — this stays only on the full form in ProjectControlPage.
- ❌ Any backend change. `git diff backend/` MUST be empty.
- ❌ Any new dependency. `git diff frontend/package.json frontend/package-lock.json` MUST be empty.
- ❌ Any change to the existing companies service (`projectCompanyService.create`) signature.
- ❌ Any change to NewDefectModal's defect-creation logic, photo handling, category selection, etc. Only the 3 onClick handlers change + state + modal render.

## Architectural constraints

- Relative imports only (`../components/...`). No `@/` alias.
- Match existing style conventions — Tailwind, RTL, Hebrew labels, shadcn/Radix primitives.
- The new component is self-contained — can be imported and used with just `open`, `onOpenChange`, `onSuccess`, `projectId` props.
- Follow the existing `BottomSheetModal` / Radix Dialog pattern for the slim modal styling.

## Tasks

### Task 1 — Fix #2: Default landing tab to "מבנה"

**File:** `frontend/src/utils/navigation.js:9`

**Change:**
```diff
  if (MANAGEMENT_ROLES.includes(role)) {
-   navigate(`/projects/${id}/control`);
+   navigate(`/projects/${id}/control?workMode=structure`);
  } else if (role === 'contractor') {
```

**Why:** ProjectControlPage already reads `?workMode=` from URL and prefers it over localStorage on mount. Adding this param ensures every project-card click lands on structure tab, no matter what tab the user last clicked inside that project.

**DO NOT:**
- ❌ Change the contractor branch or the default branch.
- ❌ Remove localStorage save in ProjectControlPage — it should still work for intra-project tab clicks.
- ❌ Change any other navigation in the app.

---

### Task 2 — Create `QuickAddCompanyModal` component

**New file:** `frontend/src/components/QuickAddCompanyModal.js`

**Goal:** a small, self-contained modal that captures 4 fields (name, trade, contact_name, contact_phone), calls `projectCompanyService.create(projectId, payload)`, and reports back to the parent via `onSuccess(newCompany)`.

**Props interface:**
```javascript
export default function QuickAddCompanyModal({
  open,
  onOpenChange,
  projectId,
  categories = [],      // [{ value, label }] — the same CATEGORIES list used by NewDefectModal
  initialTrade = '',    // optional — pre-fills the trade dropdown (typically parent's current category)
  onSuccess,            // called with the created company object
}) { ... }
```

**Pre-verified:** `NewDefectModal.js` has `CATEGORIES` as a hardcoded module-level const at lines 29-34 (17 values, mapped to `{value, label}` via `tCategory(key)`). The NewDefectModal component has `category` state (from `useState`) that holds the user's current selection. Pass **both** as props to QuickAddCompanyModal: `categories={CATEGORIES}` and `initialTrade={category}`.

**Why `initialTrade`:** if the user already picked a category in the defect form and now is adding a company because "no companies in my category exist", the company they're adding is almost certainly for that trade. Auto-filling saves a click and reduces error.

**Structure (guidelines, not the exact code):**

- Use Radix `DialogPrimitive.Root` + `DialogPrimitive.Portal` + `DialogPrimitive.Overlay` + `DialogPrimitive.Content`, matching the existing patterns in `frontend/src/components/PaywallModal.js` or `WhatsAppRejectionModal.js` for reference.
- Modal positioning: centered on desktop, bottom-sheet on mobile (standard pattern in the project).
- Overlay: `fixed inset-0 bg-black/40 z-[9999]` (above NewDefectModal's z-50).
- Content: `z-[9999]`.
- Internal state: `name`, `tradeValue` (initialized from `initialTrade` prop on each open), `contactName`, `contactPhone`, `saving` (boolean for button disable).
- Fields (in order, all RTL):
  1. `<input>` — שם חברה * (required)
  2. `<select>` — תחום (dropdown from `categories` prop, optional — pre-filled from `initialTrade` if provided, otherwise empty default "בחר תחום")
  3. `<input>` — שם איש קשר (optional)
  4. `<input>` — טלפון (optional, `inputMode="tel"`)
- Action buttons at bottom:
  - "שמור" — primary, amber background (`bg-amber-500` matching project style), disabled when `name` is empty or `saving` is true
  - "בטל" — secondary
- Validation: trim `name` and require non-empty. No other client-side validation.
- On save:
  ```javascript
  try {
    setSaving(true);
    const payload = { name: name.trim() };
    if (tradeValue) payload.trade = tradeValue;
    if (contactName.trim()) payload.contact_name = contactName.trim();
    if (contactPhone.trim()) payload.contact_phone = contactPhone.trim();
    const newCompany = await projectCompanyService.create(projectId, payload);
    toast.success('החברה נוספה');
    onSuccess(newCompany);  // caller handles append-to-list + auto-select + close
  } catch (err) {
    toast.error(err.response?.data?.detail || 'שגיאה בהוספת חברה');
  } finally {
    setSaving(false);
  }
  ```
- On cancel: just `onOpenChange(false)` — no confirmation needed (slim form, not much to lose).

**Imports the component needs:**
```javascript
import React, { useState } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { toast } from 'sonner';
import { projectCompanyService } from '../services/api';
```

**Behavior when `open` becomes `true`:** reset internal state to defaults, and set `tradeValue` = `initialTrade` so the trade dropdown shows the parent's currently-selected category. Use `useEffect` keyed on `open` + `initialTrade`.

**Behavior when `open` becomes `false`:** no action needed — the next `open=true` will reset via the useEffect above.

**DO NOT:**
- ❌ Add any suggestions dropdown or search-as-you-type for trades.
- ❌ Add an inline "add new trade" flow — if the trade they need isn't in the list, they use the full management page.
- ❌ Add image upload, logo field, or any field beyond the 4 specified.
- ❌ Add internal navigation (no `useNavigate`).
- ❌ Call `onClose` on the parent NewDefectModal.
- ❌ Auto-close on ESC/overlay click if `saving` is true — let the request finish first. Respect Radix's `onEscapeKeyDown` / `onPointerDownOutside` with a `saving` guard.

---

### Task 3 — Integrate `QuickAddCompanyModal` into NewDefectModal

**File:** `frontend/src/components/NewDefectModal.js`

### 3a. Add state for the modal

Near the top of the component, with other `useState` declarations:

```javascript
const [showQuickAddCompany, setShowQuickAddCompany] = useState(false);
```

### 3b. Replace the 3 navigate calls for "+ הוסף חברה"

**Lines to change:** ~809, ~822, ~849 (find with `grep -n "navigate.*control.*tab=companies" frontend/src/components/NewDefectModal.js`).

For each of these 3 buttons:
```diff
- onClick={() => { onClose(); if (projectId) navigate(`/projects/${projectId}/control?tab=companies`); }}
+ onClick={() => setShowQuickAddCompany(true)}
```

**DO NOT** change the 4th navigate call (line ~876 — that's for "+ הוסף קבלן", deferred to Batch 2b). Confirm with grep that exactly 3 lines changed and 1 remains:

```bash
grep -c "navigate.*control.*tab=companies" frontend/src/components/NewDefectModal.js
# Expected: 1 (only the contractor line).
```

### 3c. Render QuickAddCompanyModal

Near the end of the component's JSX (just before the closing `DialogPrimitive.Root`), add:

```jsx
<QuickAddCompanyModal
  open={showQuickAddCompany}
  onOpenChange={setShowQuickAddCompany}
  projectId={projectId}
  categories={CATEGORIES}      // the const at lines 29-34 of NewDefectModal.js
  initialTrade={category}      // the current `category` state in NewDefectModal
  onSuccess={(newCompany) => {
    setCompanies(prev => [...prev, newCompany]);   // append to dropdown (verify actual setter name below)
    setCompanyId(newCompany.id);                   // auto-select
    setShowQuickAddCompany(false);                 // close modal
  }}
/>
```

### 3d. Identify actual state variable names

**Pre-verified (2026-04-23):**
- `category` state + `setCategory` at line ~79: `const [category, setCategory] = useState('');` ✓
- `companyId` state + `setCompanyId` — **verify before use** with: `grep -n "setCompanyId\|setCompany\b" frontend/src/components/NewDefectModal.js`
- Companies list setter — **verify before use**: `grep -n "setCompanies\|setProjectCompanies\|companies =" frontend/src/components/NewDefectModal.js`
- `CATEGORIES` constant at lines 29-34 (module-level) ✓

If the companies list is fetched via an API hook without a direct setter, alternative: after save, call the existing refetch function (e.g., `loadCompanies()` or similar).

### 3e. Import at the top

```javascript
import QuickAddCompanyModal from './QuickAddCompanyModal';
```

**DO NOT:**
- ❌ Call `onClose()` on the parent NewDefectModal when opening the quick-add modal. NewDefectModal state must be preserved.
- ❌ Add a 4th "+ הוסף חברה" trigger anywhere new. Only the 3 existing ones are modified.
- ❌ Touch the contractor button at line ~876 (that's Batch 2b).
- ❌ Change the label, icon, or styling of the trigger buttons. Only the `onClick` prop changes.
- ❌ Change the "trades" dropdown or company dropdown inside NewDefectModal itself — only the "add new" flow.

---

## Relevant files

| File | Action | Approx lines |
|---|---|---|
| `frontend/src/utils/navigation.js` | MODIFY line 9 (append `?workMode=structure`) | 1 line |
| `frontend/src/components/QuickAddCompanyModal.js` | CREATE new file | ~120 lines |
| `frontend/src/components/NewDefectModal.js` | MODIFY — 1 state, 3 onClick changes, 1 modal render, 1 import | ~15 lines |

**Total: 1 new file, 2 files modified, ~140 lines of changes (mostly the new file).**

---

## DO NOT (cross-cutting)

- ❌ Do NOT touch `ProjectControlPage.js` at all — this spec does not require any change there.
- ❌ Do NOT change `projectCompanyService` or its API path.
- ❌ Do NOT change any backend file.
- ❌ Do NOT add new deps.
- ❌ Do NOT change existing modal z-indexes.
- ❌ Do NOT add internal navigation inside the new modal.
- ❌ Do NOT close `NewDefectModal` when the quick-add modal opens or closes.
- ❌ Do NOT add fields beyond the 4 specified (name, trade, contact_name, contact_phone).
- ❌ Do NOT handle the contractor add flow (line ~876) — deferred.
- ❌ Do NOT add trade-sort logic — deferred.
- ❌ Do NOT rename existing state variables in NewDefectModal.

---

## VERIFY before commit

### 1. Scope greps

```bash
# (a) No backend changes:
git diff --stat backend/
# Expected: empty.

# (b) No new deps:
git diff frontend/package.json frontend/package-lock.json
# Expected: empty.

# (c) navigation.js fix applied:
grep -n "navigate(\`/projects/\${id}/control?workMode=structure\`)" frontend/src/utils/navigation.js
# Expected: 1 hit.

# (d) New file exists:
ls frontend/src/components/QuickAddCompanyModal.js
# Expected: file present.

# (e) Import added to NewDefectModal:
grep -n "import QuickAddCompanyModal" frontend/src/components/NewDefectModal.js
# Expected: 1 hit.

# (f) Exactly 1 navigate-to-companies call remaining (the contractor one at ~876):
grep -c "navigate.*control.*tab=companies" frontend/src/components/NewDefectModal.js
# Expected: 1.

# (g) showQuickAddCompany state added:
grep -n "showQuickAddCompany\|setShowQuickAddCompany" frontend/src/components/NewDefectModal.js
# Expected: at least 4 hits (declaration + 3 onClick handlers + modal render).

# (h) ProjectControlPage untouched:
git diff --stat frontend/src/pages/ProjectControlPage.js
# Expected: empty (no changes).

# (i) QuickAddCompanyModal uses the correct service:
grep -n "projectCompanyService.create" frontend/src/components/QuickAddCompanyModal.js
# Expected: 1 hit.
```

### 2. Build clean

```bash
cd frontend
npm run build
```
Expected: no new warnings.

### 3. Manual tests

#### Fix #2 — Default landing tab
1. Log in as PM
2. Open any project → click "ליקויים" tab
3. Go back to projects list (via sidebar / hamburger)
4. Click the same project again
5. ✅ **Lands on "מבנה" tab** (not "ליקויים")
6. Click "ליקויים" inside → switch works (localStorage still saves)
7. Click "תוכניות" inside → switch works

#### Fix #3 — Inline Add Company (the 3 triggers)

**Scenario A — no companies at all in the project:**
1. Create a fresh project with zero companies
2. Open any unit → click "+ פתח ליקוי"
3. Fill in title "בדיקה 1", description, category=ריצוף, pick a location
4. The "שייך חברה" section shows empty state with "+ הוסף חברה"
5. Click that button
6. ✅ QuickAddCompanyModal opens on top of NewDefectModal
7. ✅ NewDefectModal still visible behind it (darker overlay)
8. Fill name "חברת ריצוף א", pick trade=ריצוף, fill contact name + phone
9. Click שמור
10. ✅ Modal closes
11. ✅ NewDefectModal still open, "בדיקה 1" still in title, category=ריצוף still selected
12. ✅ "חברת ריצוף א" appears in company dropdown, selected

**Scenario B — no companies matching category:**
- Project has companies, but none match the picked category → "+ הוסף חברה" button in the filtered empty state → same flow as A

**Scenario C — inline "+ הוסף חברה" link:**
- Category picked, one or more companies exist, user clicks the small "+ הוסף חברה" link → same flow

#### Fix #3 — Edge cases
- **Cancel:** open QuickAddCompanyModal → type a name → click בטל → modal closes, NewDefectModal unchanged
- **Save failure:** simulate a backend error (stop API for a second) → click שמור → error toast appears, modal stays open, name still in the field
- **Multiple in a row:** add company → open again → add second company → both appear in dropdown

#### Regression — ProjectControlPage companies tab
1. Open `/projects/<id>/control?tab=companies`
2. Click "+ הוסף חברה חדשה"
3. ✅ The full inline AddCompanyForm (the one that's been there all along) opens
4. ✅ Company name suggestions dropdown still works
5. ✅ "+ הוסף תחום חדש" inline flow still works
6. ✅ Save works, company appears in the list

Per this spec, ProjectControlPage.js is not touched — so regression should be zero. This is just a sanity check.

### 4. Send after deploy

- `git log -1 --stat` (expected: 3 files, ~140 insertions)
- Unified diff
- `git diff --stat backend/` (must be empty)
- `git diff --stat frontend/src/pages/ProjectControlPage.js` (must be empty)
- Output of 9 grep checks from VERIFY §1
- Screenshots on mobile 375px:
  1. NewDefectModal with text typed
  2. QuickAddCompanyModal open on top of NewDefectModal
  3. Return to NewDefectModal with company selected + text preserved
  4. ProjectControlPage companies tab still working (screenshot of the full AddCompanyForm)

---

## Commit message (exactly)

```
feat(ui): Batch 2a — default landing tab + inline add company

Two closed-beta fixes:

1) navigation.js: navigateToProject now appends ?workMode=structure to
   the /control URL for management users so clicking a project card
   always lands on the "מבנה" tab. localStorage still drives intra-
   project tab-switching.

2) New QuickAddCompanyModal component — a slim 4-field form (name,
   trade, contact_name, contact_phone) that sits inside NewDefectModal
   as a nested modal. Replaces the 3 navigate() calls to
   /control?tab=companies on the "+ הוסף חברה" triggers at lines 809,
   822, 849. The user no longer loses their defect form when they need
   to add a company on the fly. Calls the same projectCompanyService.
   create as the full form — no API change. On success, the new
   company is appended to the company dropdown and auto-selected.

ProjectControlPage is NOT touched — the full AddCompanyForm there
(with suggestions dropdown, "add new trade" inline flow, etc.) stays
exactly as-is for users who need those features via the management
page.

The "+ הוסף קבלן" button at line 876 is deliberately left alone —
that's deferred to Batch 2b along with the trade-sort feature.

No backend changes. No new deps.
```

---

## Deploy

```bash
./deploy.sh --prod
```

OTA only.

**Post-deploy smoke test (within 10 minutes):**
1. Open `/projects/<id>/control?tab=companies` → add a company → verify it works
2. Open any unit → "+ פתח ליקוי" → fill form → trigger QuickAddCompanyModal → save → verify defect can be submitted

If either breaks, `git revert <commit> && ./deploy.sh --prod` — rollback in 5 minutes.

---

## Definition of Done

- [ ] `navigation.js:9` appends `?workMode=structure`
- [ ] `QuickAddCompanyModal.js` created with 4 fields
- [ ] `NewDefectModal.js` imports + wires QuickAddCompanyModal
- [ ] 3 onClick handlers changed (lines ~809, ~822, ~849)
- [ ] 1 onClick handler UNCHANGED (line ~876 — contractor, deferred)
- [ ] All 9 grep checks from VERIFY §1 pass
- [ ] `npm run build` succeeds with no new warnings
- [ ] Manual test: all 3 "+ הוסף חברה" triggers open QuickAddCompanyModal, save works, state preserved
- [ ] Manual test: default tab is "מבנה" on project click
- [ ] Regression: ProjectControlPage companies tab still works 100% unchanged
- [ ] `git diff --stat backend/` is empty
- [ ] `git diff --stat frontend/src/pages/ProjectControlPage.js` is empty
- [ ] `./deploy.sh --prod` succeeded
- [ ] Screenshots sent to Zahi
