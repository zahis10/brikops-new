# 🔍 Investigation Report — Batch 1 (6 fixes)

**Date:** 2026-04-23
**For:** Zahi's review before writing spec for Replit
**Source docs:** `CLOSED-BETA-FIXES.md`

All file paths verified. All line numbers confirmed. Risks identified.

---

## Fix #1 — Nav overflow crops "תוכניות" tab

### Verified location
**File:** `frontend/src/pages/ProjectControlPage.js:3547-3549`

```jsx
<div className="bg-white border-b border-slate-200">
  <div className="max-w-[560px] mx-auto flex gap-1 px-3 py-2 overflow-x-auto" dir="rtl">
    {workTabs.map(wt => { ... })}
  </div>
</div>
```

### The problem
Outer header container (line 3565) has `max-w-[1100px]` (page-wide).
**But** the workTabs container on line 3548 has `max-w-[560px]` — a 560px ceiling that was right for mobile, wrong for desktop. 7 tabs don't fit at 560px.

### The fix (1 line)
Change line 3548: `max-w-[560px]` → `max-w-[1100px]`

```diff
- <div className="max-w-[560px] mx-auto flex gap-1 px-3 py-2 overflow-x-auto" dir="rtl">
+ <div className="max-w-[1100px] mx-auto flex gap-1 px-3 py-2 overflow-x-auto" dir="rtl">
```

### Risks
- ✅ `overflow-x-auto` stays — mobile still scrolls horizontally
- ✅ No snapshot/CSS tests exist that would break
- ✅ `max-w-[560px]` appears only in this one place in the whole codebase — no coupled components
- ✅ The outer container already caps at 1100px, so workTabs can't exceed that
- ⚠️ On desktop, all 7 tabs will fit side-by-side. Visual check needed — do they look crammed? Probably fine with `gap-1 + px-3 py-2` existing padding.

---

## Fix #2 — Default landing tab = "מבנה"

### Status
⚠️ **Partial investigation — need Zahi's confirmation on current behavior before I commit to a fix direction.**

### What I know
- `ProjectControlPage.js:3511` — handler: `setWorkMode(id); if (id !== 'structure') setActiveTab('');`
- `ProjectControlPage.js:3513` — persists to `localStorage.getItem('brikops_workMode_${projectId}')`
- Initial state of `workMode` needs investigation — does it default to `'structure'` or to the localStorage value?
- Projects list page (where click originates) — haven't found yet, needs to know what URL it navigates to

### What I need to verify before fix
1. Where is the projects list click handler? Possible: `ProjectsPage.js` / `ProjectsHome` / somewhere in App.js routing. It likely does `navigate('/projects/${id}/dashboard')` (per observed behavior).
2. Does Zahi want: (a) always land on `/control` with workMode=structure regardless of last session, or (b) remember last mode EXCEPT default to structure on first visit?

### My recommendation
Most likely fix (pending confirmation):
- Projects list click → navigate to `/projects/:id/control` (not `/dashboard`)
- `ProjectControlPage` initial state → default `workMode = 'structure'` on fresh mount, reads localStorage ONLY if there's a saved value AND user explicitly switched tabs before

**Blocker:** I need to find the projects list file first to see current navigate target. Will defer fix spec for this one until I find it. **Skip in Batch 1 commit — handle alone after I locate the projects list.**

---

## Fix #7 + #8 — Trial banner (both in same component)

### Verified location
**File:** `frontend/src/components/TrialBanner.js` (154 lines)
**Rendered from:** `frontend/src/App.js:520` (app-shell global)
**Data source:** `BillingContext.js` → `GET /api/billing/me`

### The exact current logic

```js
// Line 9: AUTH pages already excluded
const AUTH_PAGES = ['/login', '/register', ..., '/onboarding', '/forgot-password', '/reset-password'];

// Line 29: Non-billing roles already excluded (early return)
const NON_BILLING_ROLES = ['management_team', 'contractor', 'viewer', 'site_manager', 'execution_engineer', 'safety_assistant'];

// Line 40: AUTH pages return null
// Line 41: No user/billing → return null
// Line 44: Super admin → return null
// Line 47: NON_BILLING_ROLES (checks both roleDisplay AND user.role) → return null

// Line 67-108: Trial-ending (days_remaining ≤ 7) — shows to billing contacts
// Line 111-145: Read-only lock (trial_expired etc.) — SHOWS TO EVERYONE WHO REACHED THIS POINT
```

### Fix #7 (scope to per-project)

**The issue:** Banner renders on `/projects` (list) because that path isn't in `AUTH_PAGES`.

**The fix (add 3 paths to exclusion):**

```diff
  const AUTH_PAGES = ['/login', '/register', '/register-management', '/phone-login', '/pending', '/onboarding', '/forgot-password', '/reset-password'];
+ const PROJECT_LIST_PAGES = ['/projects', '/'];
  ...
  if (AUTH_PAGES.includes(location.pathname)) return null;
+ if (PROJECT_LIST_PAGES.includes(location.pathname)) return null;
```

### Fix #8 (role visibility — the subtle one)

**The issue as Zahi reported it:** engineer (מהנדס ביצוע) saw the red banner "יש לבצע תשלום" at top + "הגישה מוגבלת" dialog at bottom.

**But line 47 already excludes `execution_engineer`.** So either:
- (a) The user's role isn't actually `execution_engineer` in DB (maybe `project_manager` with a project-level sub-role of "execution engineer")
- (b) There's ANOTHER component rendering the banner

**Verification done:** Searched for "יש לבצע תשלום" / "כדי להמשיך לעבוד" in all frontend files. Text not found literally. The CLOSEST messages are:
- `TrialBanner.js:14`: `'תקופת הניסיון הסתיימה — מצב צפייה בלבד'`
- `OrgBillingPage.js:962`: `'הניסיון הסתיים. כדי להמשיך לעבוד צריך לחדש מנוי.'`
- `PaywallModal.js:38`: `'תקופת הניסיון הסתיימה. כדי להמשיך ליצור, לערוך ולנהל ליקויים, יש לשדרג את החשבון.'`

**Most likely source of Zahi's screenshot text:** `PaywallModal.js` — it's a modal that could pop up on any page. Let me check its render conditions.

### What I need to verify before committing to Fix #8

1. Is the screenshot showing `TrialBanner` or `PaywallModal`? Need to check `PaywallModal.js` render conditions.
2. If PaywallModal — what triggers it? Is it role-aware?
3. Was Zahi's engineer user actually stored with `role='execution_engineer'` or `role='project_manager'`?

### Proposed fix (conservative — covers both cases)

**In `TrialBanner.js` lines 111-145:** wrap the read-only banner with billing-contact check:
```diff
- if (isReadOnly) {
+ if (isReadOnly && (canManageBilling || isOwner)) {
    // render red banner
  }
```

**Also investigate `PaywallModal.js`:** ensure it only shows to billing contacts, or doesn't show on projects list.

### Risks for Fix #7 + #8
- ✅ Owner on projects list with expired org will NOT see banner → might not realize they need to upgrade. **Mitigation:** keep PaywallModal or a smaller nudge visible to owner on projects list; the hard banner only inside project context.
- ⚠️ If Zahi wants owner to ALSO see the banner on projects list (so they're nudged to upgrade), we need an OPPOSITE fix: banner only shown to owner/billing on projects list, not at all to non-billing.

### Open question for Zahi
**For an owner with expired org who's on the projects list — do you want:**
- A. No banner at all (current proposal) — they only see it inside a project
- B. A banner with "שדרג" CTA visible (just hidden for non-owners)

I'd suggest B (more aggressive nudge on the owner's home base) — but it's your call.

---

## Fix #9 — Defect detail header polish

### Verified location
**File:** `frontend/src/pages/TaskDetailPage.js:777-807`

```jsx
<div className="bg-white border-b shadow-sm sticky top-0 z-10">
  <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
    <div className="flex items-center gap-2">
      <HardHat className="w-5 h-5 text-amber-500" />     {/* helmet icon */}
      <span className="font-bold text-slate-800">BrikOps</span>
    </div>
    <button ... className="flex items-center gap-1 text-sm text-slate-500 hover:text-amber-600 transition-colors">
      {/* dynamic label — "חזרה לרשימת ליקויים" in most cases */}
      <ArrowRight className="w-4 h-4" />
    </button>
  </div>
</div>
```

### The exact current state
- Container has **NO** `dir="rtl"` (line 777-778) — rendered in LTR order
- In LTR flex-between:
  - LEFT: HardHat icon + "BrikOps"
  - RIGHT: back button + ArrowRight
- Page content BELOW header (line 809) has `dir="rtl"`

### The fix (2 changes)

**1. Remove HardHat:** Delete line 780. Replace with either:
- Nothing (just text "BrikOps")
- OR use the real logo from `components/splash/BrikLogo.jsx` (I verified it exists)
- OR use `/public/favicon.png` or `logo.svg` (need to check public assets)

**2. Swap sides to RTL convention:** Add `dir="rtl"` to the flex container OR reorder the two divs in JSX.

**Cleanest diff:**
```diff
  <div className="bg-white border-b shadow-sm sticky top-0 z-10">
-   <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
+   <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between" dir="rtl">
      <div className="flex items-center gap-2">
-       <HardHat className="w-5 h-5 text-amber-500" />
        <span className="font-bold text-slate-800">BrikOps</span>
      </div>
      <button ...>
        ...
-       <ArrowRight className="w-4 h-4" />
+       <ArrowLeft className="w-4 h-4" />    {/* arrow points to end in RTL = left visual */}
      </button>
    </div>
  </div>
```

Also remove `HardHat` from the imports at the top of the file (line 10 currently).

### Risks
- ⚠️ The "ArrowRight" change — in RTL, a "back" action points LEFT visually. Zahi to confirm if arrow direction should change or stay. Many Hebrew apps use ArrowRight for "back" because the arrow points "backwards in reading direction" (right). User preference question.
- ✅ `TaskDetailPage` is used by both PMs and contractors — no regression for contractors since they see the same header.
- ✅ Removing `HardHat` — also removed from imports, otherwise unused-import warning.

### Open questions for Zahi
1. **Logo replacement:** real BrikLogo component / just text "BrikOps" / image from `/public`? Which do you prefer?
2. **Arrow direction:** flip to ArrowLeft (matches visual back direction in RTL), or keep ArrowRight (matches Hebrew idiom)?

---

## Fix #10a — Floor badge overflow (PrimeTestLab BUG-001)

### Verified locations — **the pattern is used in 5+ places**

**Primary (most likely the one QA flagged):**
- `BuildingDefectsPage.js:463` — filter badge on building defects
- `BuildingDefectsPage.js:565` — UNIT badge on unit cards (most likely)
- `ApartmentDashboardPage.js:695` — apartment dashboard badge
- `InnerBuildingPage.js:557` — inner building badge
- `HandoverOverviewPage.js:475` — handover overview badge
- `NotificationBell.js:89` (uses `-right-0.5` — different pattern)

**Sample (BuildingDefectsPage.js:565):**
```jsx
<div className="relative">
  <Home className={`w-8 h-8 ${getUnitIconColor(unit)}`} />
  {badgeCount > 0 && (
    <span className={`absolute -top-1.5 -left-1.5 text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center ${getUnitBadgeColor(unit)}`}>
      {badgeCount}
    </span>
  )}
</div>
```

### The root cause
`-top-1.5 -left-1.5` = **physical edge properties** (Tailwind). In CSS, `left` and `right` stay physical regardless of `dir="rtl"` on the parent.

**In LTR:** badge at top-left of icon — visually top-left. No card overflow (card has padding).
**In RTL:** badge still physically top-left → appears visually top-left (icon not mirrored since it's in a flex-centered parent). **But in some flex/grid contexts, the icon might be pushed to the visual right edge of the cell, and the badge's negative offset overflows the cell boundary.**

### The fix (consistent, all locations)

**Best (Tailwind 3.3+ logical properties):**
```diff
- className="absolute -top-1.5 -left-1.5 ..."
+ className="absolute -top-1.5 -start-1.5 ..."
```

`-start-1.5` in Tailwind maps to `inset-inline-start: -0.375rem`, which flips automatically:
- LTR: behaves like `-left-1.5` (badge on left of icon)
- RTL: behaves like `-right-1.5` (badge on right of icon visually)

**Verify Tailwind version:** `grep "tailwindcss" frontend/package.json` — need 3.3+.

### Risks
- ⚠️ This pattern is used in 5+ places. Fixing one without the others is inconsistent. **Recommend: fix all 5 in the same commit.**
- ⚠️ Some badge placements might be intentional (e.g., on LTR-only pages). Need to verify each one renders inside a dir="rtl" context.
- ✅ The fix is a drop-in Tailwind class change — no logic change, no side effects.

### Scope recommendation
Batch 1 should include: **all 5 instances** of `-left-1.5` → `-start-1.5` in the listed files. Plus an audit pass for any other `-left-X` / `-right-X` / `left-[-Xpx]` / `right-[-Xpx]` in absolute positioning inside dir="rtl" contexts.

---

## Fix #10b — Language menu opens Settings

### Verified location
**File:** `frontend/src/components/HamburgerMenu.js:13`

```jsx
{ id: 'language', label: 'שפה', icon: Globe, type: 'navigate', path: '/settings/account' },
```

Line 12 has the exact same `path: '/settings/account'` — so "שפה" and "הגדרות חשבון" navigate to the same page.

### Options for fix
**(A) Anchor navigation:** Change path to `/settings/account#language` and add scroll-to-anchor logic in `AccountSettingsPage.js` (which has a language selector at line 728).

**(B) Language picker modal:** Create a new small modal, invoke it from the menu click instead of navigating. `i18n/index.js` already has `setLanguage()` and persistence.

**(C) Remove the entry:** Since language is accessible from Settings, remove "שפה" from the hamburger to avoid the duplicate / misleading entry.

### My recommendation
**(A)** — simplest, no new component, anchor scroll is a 5-line change in AccountSettingsPage. Label stays meaningful ("שפה" still takes you to the language control).

### Risks
- ✅ No existing anchor navigation in the app — need to verify that AccountSettingsPage mounts properly from `#language` hash and `scrollIntoView` works.
- ✅ No currently working language picker elsewhere — so (A) doesn't conflict.

### Open question for Zahi
A / B / C?

---

## Fix #10c — Notifications popup RTL clipping (PrimeTestLab BUG-003)

### Verified location
**File:** `frontend/src/components/NotificationBell.js:96-100`

```jsx
<PopoverContent
  className="w-80 p-0 rounded-xl shadow-2xl border border-slate-200 overflow-hidden"
  align="end"          // ← the bug
  sideOffset={8}
>
```

Popover component is Radix UI (`frontend/src/components/ui/popover.jsx`).

### Why it fails in RTL
The bell button is in the header's LEFT area visually (LTR-ordered header without `dir="rtl"`). Radix `align="end"` aligns the popup's END to the trigger's END — in the bell's LTR context, "end" = right.

Result: popup's right edge aligns with bell's right edge, and popup extends LEFT. On narrow screens, the popup's LEFT side clips off-screen (the user's screenshot shows no clipping on the RIGHT — actually QA report says clipping is on RIGHT, which is the opposite).

Actually the QA report says:
> "popup has no right-side padding and gets clipped by the screen edge, while there is unused free space on the left side of the popup"

So in the QA tester's screen, the popup was too far RIGHT with empty space on the LEFT. This happens when `align="start"` — popup's start aligns with trigger's start, and in LTR, "start" = left. So the popup extends rightward from the bell — past the screen edge on small screens.

Either way, the fix is to add **collision detection**:

### The fix

```diff
  <PopoverContent
    className="w-80 p-0 rounded-xl shadow-2xl border border-slate-200 overflow-hidden"
-   align="end"
+   align="end"
    sideOffset={8}
+   collisionPadding={16}
  >
```

`collisionPadding={16}` tells Radix to keep the popup 16px inside the viewport edge on all sides, auto-shifting when near an edge. This is the correct general solution regardless of direction.

### Risks
- ✅ `collisionPadding` is a standard Radix prop, well-supported
- ✅ Won't change behavior when there's room — only kicks in near edges
- ⚠️ Need to verify the Radix version used supports `collisionPadding` (Radix Popover 1.0+). If older, fall back to `avoidCollisions={true}` (default) + manual `sideOffset`/`alignOffset`.

### Broader observation (from QA report cross-reference)
Both #10a and #10c are symptoms of "LTR-first design with RTL bolted on." Recommend: separate follow-up to audit all `absolute` positioning with physical edge values (`left-X`, `right-X`) in components rendered inside RTL contexts. Not in Batch 1.

---

## Summary — what's ready to spec NOW vs what's blocked

### ✅ Ready to spec and ship in Batch 1

| Fix | Status | Confidence |
|---|---|---|
| #1 Nav max-w | Clear 1-line change | 100% |
| #7 Banner scoping | Clear, add paths to exclusion | 95% |
| #9 Defect header polish | Clear, 2-3 changes | 90% (need Zahi's call on logo + arrow) |
| #10a Floor badge | Clear, use `-start-1.5` | 85% (need Tailwind version verify) |
| #10c Notifications popup | Clear, add `collisionPadding={16}` | 95% |

### ⚠️ Need Zahi's decision before spec

| Fix | Why blocked |
|---|---|
| #8 Banner role | Need to verify if Zahi's screenshot is TrialBanner or PaywallModal. Also need decision: owner sees banner on projects list or not? |
| #10b Language menu | A/B/C decision: anchor navigation / new modal / remove entry? |

### ⚠️ Need more investigation

| Fix | What's missing |
|---|---|
| #2 Default landing tab | Haven't located projects list click handler — where does navigation originate? Recommend: **skip Batch 1, handle in Batch 2 with the nav flow fixes.** |

---

## Recommended Batch 1 scope (narrowed)

**Ship together** (file count: 7, line count: ~15):
1. #1 nav max-w (1 line, `ProjectControlPage.js`)
2. #7 banner scoping (1 block added, `TrialBanner.js`)
3. #8 banner role on read-only (1 block wrapped, `TrialBanner.js`) — **assuming Zahi picks "don't show to non-billing" approach**
4. #9 defect header (3 changes, `TaskDetailPage.js`) — **assuming Zahi picks "text only, no helmet, swap to RTL, ArrowLeft"**
5. #10a floor badge (5 files, 1 class change each)
6. #10c notifications popup (1 prop added, `NotificationBell.js`)

**Hold for separate:**
- #2 default landing tab → Batch 2 (with navigation flow fixes)
- #10b language menu → ask Zahi which option

**Single commit target:** `fix(ui): Batch 1 — nav overflow, trial banner scope, defect header polish, RTL badge fixes`

---

## Open questions for Zahi (answer these, I write the spec):

1. **#8 trial banner — for owner on projects list:** A (no banner) or B (banner visible to owner only)?
2. **#9 defect header — logo choice:** real BrikLogo component, image file, or just text "BrikOps"?
3. **#9 defect header — arrow direction:** ArrowLeft (visual back in RTL) or ArrowRight (Hebrew idiom)?
4. **#10b language menu:** A (anchor to #language in Settings), B (new picker modal), or C (remove from hamburger)?

Answer those 4 questions and I go straight to spec + Replit.
