# #314 — Critical + Medium UX Fixes (April 2026 Audit)

## What & Why
UX audit from 8.4.2026 found issues hurting app credibility and mobile usability: massive white space on dashboard (`min-h-screen`), missing `cursor-pointer` on defect cards, password displayed RTL (reversed), small touch targets in header (32px, below 44px WCAG minimum), and no scroll indicator on mobile tabs. This task bundles 7 fixes (3 critical + 4 medium) into one pass — all are CSS/JSX-only changes, no API or logic changes.

## Done looks like
- Project dashboard shows no excess white space below content at 1440px
- Defect cards show `cursor-pointer` on hover (chevron already exists — no change needed)
- Password field displays LTR (`BrikOpsDemo2026!` with `!` at end, not beginning)
- Project cards show a left chevron hint for navigation
- "לא עודכן" badge confirmed blue (verify only — already `bg-blue-400`)
- All header buttons ≥ 44×44px touch targets
- Mobile tabs show a gradient fade scroll indicator on the left edge
- No regressions in RTL layout at 375px, 768px, and 1440px

## Out of scope
- API/backend changes
- Changing the main amber color (#F59E0B)
- Changing tab order or tab structure
- Changing handover grid layout
- Changing breadcrumbs
- Removing sticky "פתח ליקוי" button
- Adding new libraries (only lucide-react already installed)
- Changing the font (Rubik)
- Touching any component in `components/ui/` (badge.jsx, select.jsx, tabs.jsx, etc.)

---

## Tasks

### Task 1 — Dashboard: remove white space (CRITICAL)

**File:** `frontend/src/pages/ProjectDashboardPage.js` line 242

**Current code (line 242):**
```jsx
<div className="min-h-screen bg-slate-50 pb-24" dir="rtl">
```

**Change to:**
```jsx
<div className="min-h-0 bg-slate-50 pb-24" dir="rtl">
```

**What this does:** `min-h-screen` forces the container to at least 100vh, creating massive white space below content on large screens. Replacing with `min-h-0` lets the content determine its own height.

```bash
grep -n "min-h-screen" frontend/src/pages/ProjectDashboardPage.js
```

**VERIFY:**
1. Open `/projects/{id}/dashboard` on 1440×900 → no excess white below "פעילות צוות" section
2. Open on 375×812 → content still renders normally, no visual change
3. Scroll to bottom → footer/bottom-nav appears right after content ends

---

### Task 2 — Defect card: add cursor-pointer (CRITICAL)

**File:** `frontend/src/pages/UnitDetailPage.js` line 271

> **NOTE:** The chevron already exists at line 296 (`<ChevronDown className="w-4 h-4 text-slate-300 -rotate-90 flex-shrink-0 mt-1" />`). Only `cursor-pointer` is missing.

**Current code (line 271):**
```jsx
className="w-full bg-white rounded-xl border border-slate-200 p-3.5 text-right hover:shadow-md transition-shadow active:bg-slate-50"
```

**Change to:**
```jsx
className="w-full bg-white rounded-xl border border-slate-200 p-3.5 text-right cursor-pointer hover:shadow-md transition-shadow active:bg-slate-50"
```

**That's it — just add `cursor-pointer` to the className string.**

```bash
grep -n "hover:shadow-md" frontend/src/pages/UnitDetailPage.js
```

**VERIFY:**
1. Open any unit page → hover over a defect card → cursor changes to pointer
2. Click → navigates to `/tasks/{id}` correctly
3. Chevron still visible on right side (already present at line 296)

---

### Task 3 — Password field: fix RTL display (CRITICAL)

**File:** `frontend/src/pages/LoginPage.js` lines 627-631

**Current code:**
```jsx
<input
  id="password" type={showPassword ? 'text' : 'password'} value={password}
  onChange={(e) => { setPassword(e.target.value); setErrors(prev => { const n = {...prev}; delete n.password; return n; }); }}
  placeholder="לפחות 8 תווים"
  className={`w-full h-11 px-3 py-2 pl-10 text-right text-slate-900 bg-white border rounded-lg transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 ${errors.password ? 'border-red-500' : 'border-slate-300 hover:border-slate-400'}`}
/>
```

**Change to (2 changes: add `dir="ltr"`, change `text-right` → `text-left`):**
```jsx
<input
  id="password" type={showPassword ? 'text' : 'password'} value={password}
  onChange={(e) => { setPassword(e.target.value); setErrors(prev => { const n = {...prev}; delete n.password; return n; }); }}
  placeholder="לפחות 8 תווים"
  dir="ltr"
  className={`w-full h-11 px-3 py-2 pl-10 text-left text-slate-900 bg-white border rounded-lg transition-colors placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 ${errors.password ? 'border-red-500' : 'border-slate-300 hover:border-slate-400'}`}
/>
```

**Changes:**
1. Add `dir="ltr"` attribute after `placeholder`
2. In className: `text-right` → `text-left`

```bash
grep -n 'id="password"' frontend/src/pages/LoginPage.js
```

**VERIFY:**
1. Go to `/login` → type `BrikOpsDemo2026!` → click the eye icon → password shows `BrikOpsDemo2026!` with `!` at the END (not beginning)
2. Placeholder "לפחות 8 תווים" still appears correctly (Hebrew placeholder in LTR field is fine — it's just a hint)
3. Eye icon toggle still works, aria-label still correct

---

### Task 4 — Project card: add chevron (MEDIUM)

**File:** `frontend/src/pages/MyProjectsPage.js` lines 338-356

**Current code (lines 338-356):**
```jsx
<div className="flex items-start gap-3">
  <div className="w-11 h-11 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
    <Building2 className="w-6 h-6 text-slate-500" />
  </div>
  <div className="flex-1 min-w-0">
    <div className="flex items-center gap-2 mb-1">
      <h3 className="text-base font-bold text-slate-900 truncate">{project.name}</h3>
      <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${statusColor}`}>
        {statusLabel}
      </span>
    </div>
    {project.code && (
      <p className="text-xs text-slate-500">{t('myProjects', 'code')}: {project.code}</p>
    )}
    {project.address && (
      <p className="text-xs text-slate-400 mt-0.5 truncate">{t('myProjects', 'address')}: {project.address}</p>
    )}
  </div>
</div>
```

**Change to:**
```jsx
<div className="flex items-start gap-3">
  <div className="w-11 h-11 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
    <Building2 className="w-6 h-6 text-slate-500" />
  </div>
  <div className="flex-1 min-w-0">
    <div className="flex items-center gap-2 mb-1">
      <h3 className="text-base font-bold text-slate-900 truncate">{project.name}</h3>
      <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${statusColor}`}>
        {statusLabel}
      </span>
    </div>
    {project.code && (
      <p className="text-xs text-slate-500">{t('myProjects', 'code')}: {project.code}</p>
    )}
    {project.address && (
      <p className="text-xs text-slate-400 mt-0.5 truncate">{t('myProjects', 'address')}: {project.address}</p>
    )}
  </div>
  <ChevronLeft className="w-5 h-5 text-slate-400 flex-shrink-0 self-center" />
</div>
```

**Also add `ChevronLeft` to imports (line 8-11):**

**Current:**
```jsx
import {
  Search, Plus, FolderOpen, ArrowLeft, LogOut, HardHat, Loader2, Building2, Phone,
  Users, CreditCard, Settings, BarChart3, ClipboardList, Shield, X
} from 'lucide-react';
```

**Change to:**
```jsx
import {
  Search, Plus, FolderOpen, ArrowLeft, LogOut, HardHat, Loader2, Building2, Phone,
  Users, CreditCard, Settings, BarChart3, ClipboardList, Shield, X, ChevronLeft
} from 'lucide-react';
```

```bash
grep -n "from 'lucide-react'" frontend/src/pages/MyProjectsPage.js
```

**VERIFY:**
1. Open `/projects` → each project card shows a left-pointing chevron on the left edge (left in RTL = forward)
2. Hover → `cursor-pointer` + shadow still works (already existed)
3. Click → navigates to project correctly

---

### Task 5 — Badge "לא עודכן": verify color (MEDIUM — VERIFY ONLY)

**File:** `frontend/src/pages/ApartmentDashboardPage.js` line 465

**Current code confirms `bg-blue-400` (blue, not green):**
```jsx
<span className="text-[10px] bg-blue-400 text-white px-2 py-0.5 rounded-full font-bold">לא עודכן</span>
```

**No code change needed.** Just run this grep to confirm no other instances use green:

```bash
grep -rn "לא עודכן" frontend/src/ | grep -v node_modules
```

**VERIFY:**
1. Open any apartment dashboard with unupdated spare tiles → badge shows blue, not green
2. Grep output shows all instances use `bg-blue-400` or similar blue shade

---

### Task 6 — Header buttons: increase touch targets (MEDIUM)

**File:** `frontend/src/pages/ProjectDashboardPage.js` lines 245, 263, 270, 276

There are 4 buttons in the dashboard header, all using `p-1.5`:

| Line | Button | Current | New |
|------|--------|---------|-----|
| 245 | Back (ArrowRight) | `p-1.5` | `p-3` |
| 263 | Settings | `p-1.5` | `p-3` |
| 270 | Send Digest | `p-1.5` | `p-3` |
| 276 | Refresh | `p-1.5` | `p-3` |

**Change `p-1.5` → `p-3` on all four buttons.** Nothing else changes in those lines.

Math: `p-3` = 12px padding × 2 + 20px icon + 2px border = 46px ≥ 44px minimum ✅

```bash
grep -n "p-1.5" frontend/src/pages/ProjectDashboardPage.js
```

**VERIFY:**
1. Open dashboard → header buttons visually larger but still proportional
2. Inspect any header button → computed width/height ≥ 44px
3. Test on 375px → buttons don't overflow or break header layout
4. Check that `NotificationBell` (line 262) is not affected — it's a separate component

---

### Task 7 — Mobile tabs: add scroll indicator (MEDIUM)

**File:** `frontend/src/pages/ProjectControlPage.js` lines 3366-3376

**Current code (lines 3366-3376):**
```jsx
<div className="bg-white border-b border-slate-100">
  <div className="max-w-[1100px] mx-auto px-4 py-2 flex gap-2 overflow-x-auto">
    {MGMT_TABS.map(tab => (
      <button key={tab.id} onClick={() => setActiveTab(activeTab === tab.id ? '' : tab.id)}
        className={`flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${activeTab === tab.id ? 'bg-amber-500 text-white shadow-sm' : 'bg-white text-slate-500 border border-slate-200 hover:bg-slate-50'}`}>
        {tab.icon && <span className="text-sm">{tab.icon}</span>}
        {tab.label}
      </button>
    ))}
  </div>
</div>
```

**Change to:**
```jsx
<div className="bg-white border-b border-slate-100">
  <div className="relative max-w-[1100px] mx-auto">
    <div className="px-4 py-2 flex gap-2 overflow-x-auto scrollbar-hide">
      {MGMT_TABS.map(tab => (
        <button key={tab.id} onClick={() => setActiveTab(activeTab === tab.id ? '' : tab.id)}
          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${activeTab === tab.id ? 'bg-amber-500 text-white shadow-sm' : 'bg-white text-slate-500 border border-slate-200 hover:bg-slate-50'}`}>
          {tab.icon && <span className="text-sm">{tab.icon}</span>}
          {tab.label}
        </button>
      ))}
    </div>
    <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-white to-transparent pointer-events-none md:hidden" />
  </div>
</div>
```

**Changes:**
1. Add `relative` wrapper around inner content
2. Move `max-w-[1100px] mx-auto` to the wrapper
3. Add `scrollbar-hide` class to the scroll container (if not available, skip — scrollbar is already thin on mobile)
4. Add gradient fade `div` — visible only on mobile (`md:hidden`), positioned on left side (forward direction in RTL)

```bash
grep -n "overflow-x-auto" frontend/src/pages/ProjectControlPage.js | head -5
```

**VERIFY:**
1. Open `/projects/{id}/control` on 375px width → see gradient fade on left edge of tab bar
2. Scroll tabs → gradient hints there are more tabs
3. At 768px+ → gradient disappears (`md:hidden`)
4. Tabs still clickable, active state still works

---

## Relevant files

| File | Lines | Change |
|------|-------|--------|
| `frontend/src/pages/ProjectDashboardPage.js` | 242 | `min-h-screen` → `min-h-0` |
| `frontend/src/pages/ProjectDashboardPage.js` | 245, 263, 270, 276 | `p-1.5` → `p-3` |
| `frontend/src/pages/UnitDetailPage.js` | 271 | add `cursor-pointer` |
| `frontend/src/pages/LoginPage.js` | 627-631 | add `dir="ltr"`, `text-right` → `text-left` |
| `frontend/src/pages/MyProjectsPage.js` | 9-11, 338-356 | add `ChevronLeft` import + icon |
| `frontend/src/pages/ApartmentDashboardPage.js` | 465 | verify only |
| `frontend/src/pages/ProjectControlPage.js` | 3366-3376 | gradient scroll indicator |

## DO NOT
- ❌ Don't change any component in `frontend/src/components/ui/` (badge.jsx, select.jsx, tabs.jsx, dropdown-menu.jsx)
- ❌ Don't change the amber primary color (#F59E0B) or any color tokens
- ❌ Don't add `cursor-pointer` to UnitDetailPage chevron or change the existing ChevronDown at line 296
- ❌ Don't change the tab order in ProjectControlPage (dashboard, building, QC, defects, handover)
- ❌ Don't touch the SECONDARY_TABS or BILLING_TAB emoji icons — that's a separate task
- ❌ Don't add new npm dependencies
- ❌ Don't change any backend file
- ❌ Don't touch NotificationBell component
- ❌ Don't change any routing or navigation logic
- ❌ Don't use `-webkit-overflow-scrolling: touch` (causes iOS freeze)
- ❌ Don't change the handover grid or unit grid layout
- ❌ Don't change breadcrumbs or the sticky "פתח ליקוי" button
