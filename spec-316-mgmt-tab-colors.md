# #316 — Add Color to Management Tab Icons (Hotfix for #315)

## What & Why
Task #315 replaced emoji icons with Lucide SVG icons in the management tabs (צוות, קבלנים, מנוי, ייצוא, מאשרים, תבנית QC, תבנית מסירה). The Lucide icons render correctly but are **monochrome gray on white** — the tabs lost all their color and personality. The row now looks lifeless and bland compared to the rest of the app. Each tab needs a distinct icon color to bring back visual energy, while the active tab (amber background) should keep its icon white.

## Done looks like
- Each management tab has a distinct icon color when inactive (not all the same gray)
- Active tab keeps white icon on amber background (existing behavior — no change)
- Colors match BrikOps palette: blues, greens, ambers, purples — warm and professional
- Inactive tab buttons have a **tinted background** matching their icon color (light wash)
- The row feels visually rich and approachable, similar to how the emojis used to feel

## Out of scope
- Changing the work tabs (דשבורד, מבנה, ליקויים etc.) — they're fine
- Changing tab order, labels, or functionality
- Changing the amber active state color
- Backend/API changes
- Adding new libraries

## Tasks

### Task 1 — Add color property to each tab in SECONDARY_TABS

**File:** `frontend/src/pages/ProjectControlPage.js` ~line 73

After #315, the SECONDARY_TABS array should have Lucide icon components. Add `color` and `bg` properties to each tab for inactive state styling:

**Change SECONDARY_TABS to:**
```jsx
const SECONDARY_TABS = [
  { id: 'team', label: 'צוות', icon: Users, color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200' },
  { id: 'companies', label: 'קבלנים וחברות', icon: Building2, color: 'text-violet-600', bg: 'bg-violet-50 border-violet-200' },
  { id: 'data-export', label: 'ייצוא נתונים', icon: Package, color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-200' },
  { id: 'settings', label: 'מאשרי בקרת ביצוע', icon: ClipboardCheck, color: 'text-cyan-600', bg: 'bg-cyan-50 border-cyan-200' },
  { id: 'qc-template', label: 'תבנית בקרת ביצוע', icon: FilePen, color: 'text-orange-600', bg: 'bg-orange-50 border-orange-200' },
  { id: 'handover-template', label: 'תבנית מסירה', icon: KeyRound, color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200' },
];
```

**And BILLING_TAB to:**
```jsx
const BILLING_TAB = { id: 'billing', label: 'מנוי ותשלום', icon: CreditCard, color: 'text-green-600', bg: 'bg-green-50 border-green-200' };
```

**Color rationale:**
- צוות (Users) → **blue** — people/collaboration
- קבלנים (Building2) → **violet** — companies/organizations
- ייצוא (Package) → **emerald** — export/data
- מאשרים (ClipboardCheck) → **cyan** — approval/verification
- תבנית QC (FilePen) → **orange** — editing/templates
- תבנית מסירה (KeyRound) → **amber** — handover/keys
- מנוי (CreditCard) → **green** — billing/money

```bash
grep -n "SECONDARY_TABS\|BILLING_TAB" frontend/src/pages/ProjectControlPage.js | head -10
```

---

### Task 2 — Update tab rendering to use color properties

**File:** `frontend/src/pages/ProjectControlPage.js` ~line 3368

**Current rendering (after #315):**
```jsx
{MGMT_TABS.map(tab => (
  <button key={tab.id} onClick={() => setActiveTab(activeTab === tab.id ? '' : tab.id)}
    className={`flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${activeTab === tab.id ? 'bg-amber-500 text-white shadow-sm' : 'bg-white text-slate-500 border border-slate-200 hover:bg-slate-50'}`}>
    {tab.icon && <span className="text-sm">{tab.icon}</span>}
    {tab.label}
  </button>
))}
```

**Change to:**
```jsx
{MGMT_TABS.map(tab => {
  const Icon = tab.icon;
  const isActive = activeTab === tab.id;
  return (
    <button key={tab.id} onClick={() => setActiveTab(isActive ? '' : tab.id)}
      className={`flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
        isActive
          ? 'bg-amber-500 text-white shadow-sm'
          : `${tab.bg} text-slate-600 hover:shadow-sm`
      }`}>
      <Icon className={`w-4 h-4 ${isActive ? 'text-white' : tab.color}`} />
      {tab.label}
    </button>
  );
})}
```

**Key changes:**
1. Destructure `tab.icon` as `Icon` component (same pattern as workTabs line 3352)
2. Inactive state uses `tab.bg` instead of `bg-white border-slate-200` — gives each tab a unique tinted background
3. Inactive state text is `text-slate-600` (slightly darker than before for readability on colored bg)
4. Icon gets `tab.color` when inactive, `text-white` when active
5. Active state unchanged — amber background, white text

```bash
grep -n "MGMT_TABS.map" frontend/src/pages/ProjectControlPage.js
```

---

## Relevant files

| File | Lines | Change |
|------|-------|--------|
| `frontend/src/pages/ProjectControlPage.js` | ~73-81 | Add `color` + `bg` to SECONDARY_TABS and BILLING_TAB |
| `frontend/src/pages/ProjectControlPage.js` | ~3368-3374 | Update rendering to use color properties |

## DO NOT
- ❌ Don't change the work tabs (workTabs, lines 3312-3319) — they're fine as-is
- ❌ Don't change the active state amber color (`bg-amber-500`)
- ❌ Don't change tab labels, order, or IDs
- ❌ Don't change any tab functionality or onClick behavior
- ❌ Don't touch any other file — this is a single-file fix
- ❌ Don't change the icon components themselves (Users, Building2, etc.) — only add color classes
- ❌ Don't use opacity or gradient tricks — use proper Tailwind color utilities
- ❌ Don't change the font size or padding of tabs

## VERIFY
1. Open `/projects/{id}/control` → management tab row shows colorful tinted buttons, each with a distinct icon color
2. Click "צוות" → tab becomes amber with white icon → click again → tab returns to blue tint
3. Compare visually: the row should feel warm and inviting, not clinical/gray
4. Check at 375px → colors still visible, no overflow issues
5. Check at 1440px → tabs centered, colors proportional
6. Active tab is still amber with white icon/text (no regression)
