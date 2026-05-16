# #406 — Closed-Beta Batch 1 — UI Polish (6 fixes)

## What & Why

Six surgical UI fixes reported by closed-beta users. All are OTA-safe (no native changes), all are isolated to a small surface per file. Scope is deliberately tight — no logic changes, no new dependencies, no new routes.

**CRITICAL:** This is a production hot-fix — real customers are using the app. The rule is "do not break anything else." Each change touches only the exact lines specified. Do not refactor surrounding code, do not "improve while you're there."

## Done looks like

1. **Desktop browser on `/projects/:id/control`** — all 7 tabs visible without horizontal scroll: דשבורד · מבנה · בקרת ביצוע · ליקויים · מסירות · בטיחות · תוכניות.
2. **Non-billing user** (`contractor`, `execution_engineer`, `site_manager`, `safety_assistant`, etc.) never sees the "תקופת הניסיון הסתיימה" top banner anywhere.
3. **Billing contact** (`owner` or user with `can_manage_billing === true`) sees the banner inside a project, but **NOT on `/projects` (projects list) or `/`** — only inside `/projects/:projectId/*` routes.
4. **TaskDetailPage header** (defect detail for contractor view) — helmet icon gone, just "BrikOps" text on the right (RTL start), back link on the left (RTL end) with arrow pointing right.
5. **Unit/floor badges** (`-top-1.5 -left-1.5` pattern) — replaced with `-top-1.5 -start-1.5` so the badge auto-flips to the correct side in RTL vs LTR, stays anchored inside its parent card.
6. **Notifications bell popup** — doesn't clip off the edge of the screen anymore; stays within 16px of the viewport edge.
7. **"שפה" menu item** in hamburger — clicking it navigates to `/settings/account#language` and auto-scrolls to the language control.

## Out of scope

- ❌ Fix #2 (default landing tab on project click) — handled in Batch 2 with related nav flow fixes.
- ❌ Inline "הוסף חברה / הוסף קבלן" modals from NewDefectModal — handled in Batch 2.
- ❌ Team member tagging on defects — handled in Batch 3.
- ❌ Contact picker (native plugin) — handled in Batch 4.
- ❌ Any refactor of the TrialBanner / BillingContext logic beyond the two specified changes.
- ❌ Any change to i18n files, translation strings, or adding a new language picker modal.
- ❌ Any change to the Radix Popover base component (`frontend/src/components/ui/popover.jsx`) — only use its props from the consumer.
- ❌ Any change to Tailwind config, PostCSS config, or package.json.
- ❌ Creating new components. Every change is inside an existing file.

## Pre-verified dependency versions (no action needed)

Already confirmed before this spec was written:
- `tailwindcss`: **3.4.17** → `-start-*` / `-end-*` logical properties work natively. Use them directly. No `rtl:` modifier fallback needed.
- `@radix-ui/react-popover`: **1.1.11** → `collisionPadding` prop is fully supported. Use it directly.

## Architectural constraints

- **Relative imports only** (`../components/...`). No `@/` alias.
- **No new deps.** `git diff frontend/package.json frontend/package-lock.json` MUST be empty.
- **No backend changes.** `git diff backend/` MUST be empty.
- **Tailwind logical properties:** use `-start-1.5` / `-start-1` directly (version 3.4.17 supports this).

---

## Tasks

### Task 1 — Fix #1: Nav overflow on ProjectControlPage

**File:** `frontend/src/pages/ProjectControlPage.js`
**Line:** ~3548 (find with `grep -n "max-w-\[560px\]" frontend/src/pages/ProjectControlPage.js`)

**Change:**
```diff
  <div className="bg-white border-b border-slate-200">
-   <div className="max-w-[560px] mx-auto flex gap-1 px-3 py-2 overflow-x-auto" dir="rtl">
+   <div className="max-w-[1100px] mx-auto flex gap-1 px-3 py-2 overflow-x-auto" dir="rtl">
      {workTabs.map(wt => { ... })}
    </div>
  </div>
```

**Why:** Outer header already caps at `max-w-[1100px]` (line ~3565). The inner `max-w-[560px]` was a mobile-era leftover forcing desktop to crop the last tab. Mobile still scrolls horizontally via `overflow-x-auto`.

---

### Task 2 — Fix #7 + #8: Trial banner scope + role

**File:** `frontend/src/components/TrialBanner.js`

**Two changes.**

**2a. Add projects-list paths to excluded paths.**

**Line:** 9

**Change:**
```diff
  const AUTH_PAGES = ['/login', '/register', '/register-management', '/phone-login', '/pending', '/onboarding', '/forgot-password', '/reset-password'];
+ const PROJECTS_LIST_PAGES = ['/', '/projects'];
```

**Line:** 40

**Change:**
```diff
  if (AUTH_PAGES.includes(location.pathname)) return null;
+ if (PROJECTS_LIST_PAGES.includes(location.pathname)) return null;
  if (!user || loading || !billing) return null;
```

**2b. Guard the read-only banner with billing-contact check.**

**Lines:** ~111-145 (find with `grep -n "isReadOnly" frontend/src/components/TrialBanner.js`)

The read-only banner block currently renders for anyone who reached that point in the component (after the early returns). It must render only for billing contacts.

**Change:** wrap the existing `if (isReadOnly) { ... }` block so the entire read-only return is gated by `(canManageBilling || isOwner)`:

```diff
- if (isReadOnly) {
+ if (isReadOnly && (canManageBilling || isOwner)) {
    // existing JSX that returns the red banner unchanged
    return (...);
  }
```

**Why:**
- `NON_BILLING_ROLES` early return (line 47) already excludes `contractor`, `execution_engineer`, `site_manager`, `safety_assistant`, `viewer`, `management_team` — those users never reach the read-only block.
- But a `project_manager` WITHOUT billing permission (because billing is owner-or-delegated) falls through and sees the red banner. Zahi's policy: only users with billing responsibility see it.
- `canManageBilling` comes from `BillingContext.billing.can_manage_billing` — server returns `true` for owner + delegated billing admins + any PM explicitly granted billing permission. That's the right signal.

**DO NOT:**
- Do NOT remove the `NON_BILLING_ROLES` early return — keep both layers (early returns + the new guard).
- Do NOT touch the trial-ending (`days_remaining ≤ 7`) banner at lines 67-108 — it already correctly checks `canManageBilling || isOwner`.

---

### Task 3 — Fix #9: TaskDetailPage header polish

**File:** `frontend/src/pages/TaskDetailPage.js`
**Lines:** 777-807 (find with `grep -n "HardHat" frontend/src/pages/TaskDetailPage.js`)

**Three changes.**

**3a. Remove HardHat icon + its import.**

In the imports block (line ~10), remove `HardHat` from the `lucide-react` import:
```diff
- import { ArrowRight, ArrowLeft, ..., HardHat, ... } from 'lucide-react';
+ import { ArrowRight, ArrowLeft, ..., /* HardHat removed */ ... } from 'lucide-react';
```

If `ArrowLeft` is not already imported, **do not add it** — we don't need it.

In the header JSX (line ~780), remove the HardHat line:
```diff
  <div className="flex items-center gap-2">
-   <HardHat className="w-5 h-5 text-amber-500" />
    <span className="font-bold text-slate-800">BrikOps</span>
  </div>
```

**3b. Add `dir="rtl"` to the header's inner flex container.**

Line ~778:
```diff
- <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
+ <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between" dir="rtl">
```

This makes the flex order render from right → left. The first JSX child (BrikOps text) ends up on the right (RTL start), the second JSX child (back button) ends up on the left (RTL end). No need to reorder the JSX.

**3c. Inside the back button, put the arrow BEFORE the text in JSX order.**

Current (line ~783-805):
```jsx
<button onClick={...} className="flex items-center gap-1 ...">
  {(() => { /* returns "חזרה לרשימת ליקויים" or similar */ })()}
  <ArrowRight className="w-4 h-4" />
</button>
```

Change to (arrow first, text second — under RTL that renders arrow on the right of the button, text to its left, which is Zahi's requested "החץ ימינה ואז המלל"):
```jsx
<button onClick={...} className="flex items-center gap-1 ...">
  <ArrowRight className="w-4 h-4" />
  {(() => { /* returns "חזרה לרשימת ליקויים" or similar */ })()}
</button>
```

**Keep ArrowRight (→) — do NOT switch to ArrowLeft.** Per Zahi: Hebrew idiom for "back" is right-pointing arrow.

---

### Task 4 — Fix #10a: Badge RTL positioning (consistent across 5 files)

**The pattern:** 5 places in the frontend use `absolute -top-1.5 -left-1.5` for a small badge overlaid on an icon. This is LTR-physical-edge — causes overflow in RTL contexts where the parent is visually right-aligned.

**Fix:** replace `-left-1.5` → `-start-1.5` in all 5 places. Tailwind 3.4.17 supports this natively — use the logical property directly, no `rtl:` modifier needed.

**Files to change (all use the same `-top-1.5 -left-1.5` pattern on a `<span className="absolute ...">` badge):**

| File | Line | grep helper |
|---|---|---|
| `frontend/src/pages/BuildingDefectsPage.js` | ~463 | `grep -n "absolute -top-1.5 -left-1.5" frontend/src/pages/BuildingDefectsPage.js` |
| `frontend/src/pages/BuildingDefectsPage.js` | ~565 | (same grep) |
| `frontend/src/pages/ApartmentDashboardPage.js` | ~695 | `grep -n "absolute -top-1.5 -left-1.5" frontend/src/pages/ApartmentDashboardPage.js` |
| `frontend/src/pages/InnerBuildingPage.js` | ~557 | `grep -n "absolute -top-1.5 -left-1.5" frontend/src/pages/InnerBuildingPage.js` |
| `frontend/src/pages/HandoverOverviewPage.js` | ~475 | `grep -n "absolute -top-1 -left-1" frontend/src/pages/HandoverOverviewPage.js` (NOTE: this one uses `-top-1 -left-1`, change to `-top-1 -start-1`) |

For each, the diff is:
```diff
- className="absolute -top-1.5 -left-1.5 ..."
+ className="absolute -top-1.5 -start-1.5 ..."
```

(or `-top-1 -start-1` for HandoverOverviewPage.js)

**DO NOT:**
- Do NOT change `NotificationBell.js:89` — that uses `-top-0.5 -right-0.5` which is a different pattern (positive `right`, not negative `left`). Leave it alone in this batch.
- Do NOT change `TaskDetailPage.js:1482` or `TaskDetailPage.js:1513` — those use `right-[-14px]` in a timeline view; out of scope here.
- Do NOT change the numeric offset (`1.5` stays `1.5`, `1` stays `1`).
- Do NOT add the `rtl:` modifier if Tailwind is ≥3.3 — just use `-start-1.5`. Redundant modifiers cost bytes.

---

### Task 5 — Fix #10c: Notifications popup collision padding

**File:** `frontend/src/components/NotificationBell.js`
**Line:** ~96-100

**Change:**
```diff
  <PopoverContent
    className="w-80 p-0 rounded-xl shadow-2xl border border-slate-200 overflow-hidden"
    align="end"
    sideOffset={8}
+   collisionPadding={16}
  >
```

**Why:** `collisionPadding={16}` tells Radix Popover to keep the popup at least 16px inside the viewport on all sides, auto-shifting when close to an edge. This prevents clipping on the right edge in RTL narrow screens, and on the left edge in LTR. Works in both directions without code branching.

Radix Popover 1.1.11 (pre-verified) supports this prop — just add it.

**DO NOT:**
- Do NOT change `align="end"` or `sideOffset={8}`.
- Do NOT touch the inner content of the popup — only the `PopoverContent` props.
- Do NOT touch `frontend/src/components/ui/popover.jsx` (the base wrapper).

---

### Task 6 — Fix #10b: Language menu item → anchor navigation to Settings

**Two files.**

**6a. `frontend/src/components/HamburgerMenu.js` line 13**

Change the path so it includes the `#language` hash:
```diff
- { id: 'language', label: 'שפה', icon: Globe, type: 'navigate', path: '/settings/account' },
+ { id: 'language', label: 'שפה', icon: Globe, type: 'navigate', path: '/settings/account#language' },
```

That's the only change in this file.

**6b. `frontend/src/pages/AccountSettingsPage.js` — add anchor + scroll**

Find the language section with:
```bash
grep -n "preferred_language\|updateMyPreferredLanguage\|בחר שפה" frontend/src/pages/AccountSettingsPage.js
```

Around line ~728 (the language `<select>`) — wrap it in an element with `id="language"`:

```diff
+ <section id="language">
    {/* existing language label + select JSX */}
+ </section>
```

Then at the top of `AccountSettingsPage` component, add a `useEffect` that scrolls to the anchor when the hash is present:

```javascript
// Add this import if not already present
import { useLocation } from 'react-router-dom';

// Inside the component
const location = useLocation();

useEffect(() => {
  if (location.hash === '#language') {
    // Delay to ensure section is rendered
    setTimeout(() => {
      const el = document.getElementById('language');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }
}, [location.hash]);
```

**DO NOT:**
- Do NOT create a new language picker modal.
- Do NOT change the existing `<select>` dropdown behavior or the `updateMyPreferredLanguage` call.
- Do NOT remove the "שפה" entry from the hamburger (per Zahi: needed for future multi-language rollout).
- Do NOT add a separate `/settings/language` route.

---

## Relevant files (summary)

| File | Lines | What changes |
|---|---|---|
| `frontend/src/pages/ProjectControlPage.js` | ~3548 | `max-w-[560px]` → `max-w-[1100px]` |
| `frontend/src/components/TrialBanner.js` | 9, 40, ~111 | Add `PROJECTS_LIST_PAGES` + early return + wrap read-only block |
| `frontend/src/pages/TaskDetailPage.js` | ~10, ~778-805 | Remove HardHat import + icon, add dir="rtl" on header, reorder button children |
| `frontend/src/pages/BuildingDefectsPage.js` | ~463, ~565 | `-left-1.5` → `-start-1.5` |
| `frontend/src/pages/ApartmentDashboardPage.js` | ~695 | `-left-1.5` → `-start-1.5` |
| `frontend/src/pages/InnerBuildingPage.js` | ~557 | `-left-1.5` → `-start-1.5` |
| `frontend/src/pages/HandoverOverviewPage.js` | ~475 | `-left-1` → `-start-1` |
| `frontend/src/components/NotificationBell.js` | ~96-100 | Add `collisionPadding={16}` |
| `frontend/src/components/HamburgerMenu.js` | 13 | Path → `/settings/account#language` |
| `frontend/src/pages/AccountSettingsPage.js` | ~728 + top | Wrap language section in `<section id="language">` + useEffect for hash scroll |

**Total: 10 file touches, ~20 lines of actual code changes.**

---

## DO NOT (cross-cutting)

- ❌ Do NOT bump `package.json` — no new dependencies.
- ❌ Do NOT add linter rules, prettier config, or tsconfig changes.
- ❌ Do NOT migrate other `-left-X` usages outside the 5 files listed — focus only on those 5.
- ❌ Do NOT change anything in `backend/` — `git diff backend/` must be empty.
- ❌ Do NOT change the i18n locale files (`he.json`, `en.json`, `ar.json`, `zh.json`).
- ❌ Do NOT extract shared components "while you're at it" — this is hot-fix polish, not refactor.
- ❌ Do NOT change `modal={true}` / `modal={false}` on any Radix dialog/popover — leave defaults.
- ❌ Do NOT touch any file not listed in "Relevant files" above.
- ❌ Do NOT add console.log / debug statements.
- ❌ Do NOT "also fix" adjacent issues that look similar — only the 7 tasks specified above.
- ❌ Do NOT bump any version number (app version, package version).

---

## VERIFY before commit

### 1. Scope greps (must all pass)

```bash
# (a) No backend changes:
git diff --stat backend/
# Expected: empty.

# (b) No package changes:
git diff frontend/package.json frontend/package-lock.json
# Expected: empty.

# (c) No @/ alias imports in touched files:
grep -rn "from '@/" frontend/src/pages/TaskDetailPage.js frontend/src/components/TrialBanner.js frontend/src/components/HamburgerMenu.js frontend/src/pages/AccountSettingsPage.js frontend/src/components/NotificationBell.js frontend/src/pages/BuildingDefectsPage.js frontend/src/pages/ApartmentDashboardPage.js frontend/src/pages/InnerBuildingPage.js frontend/src/pages/HandoverOverviewPage.js frontend/src/pages/ProjectControlPage.js
# Expected: empty.

# (d) No remaining -left-1.5 in the 5 badge files (should all be -start-1.5 after fix):
grep -n "absolute -top-1.5 -left-1.5" frontend/src/pages/BuildingDefectsPage.js frontend/src/pages/ApartmentDashboardPage.js frontend/src/pages/InnerBuildingPage.js
# Expected: empty (no hits).
grep -n "absolute -top-1 -left-1" frontend/src/pages/HandoverOverviewPage.js
# Expected: empty (no hits).

# (e) HardHat removed from TaskDetailPage:
grep -n "HardHat" frontend/src/pages/TaskDetailPage.js
# Expected: empty.

# (f) collisionPadding added to NotificationBell:
grep -n "collisionPadding" frontend/src/components/NotificationBell.js
# Expected: 1 hit.

# (g) Language menu path updated:
grep -n "/settings/account#language" frontend/src/components/HamburgerMenu.js
# Expected: 1 hit.

# (h) AccountSettingsPage has the anchor section:
grep -n 'id="language"' frontend/src/pages/AccountSettingsPage.js
# Expected: 1 hit.

# (i) Nav max-width updated:
grep -n "max-w-\[1100px\] mx-auto flex gap-1 px-3 py-2 overflow-x-auto" frontend/src/pages/ProjectControlPage.js
# Expected: 1 hit.
grep -n "max-w-\[560px\]" frontend/src/pages/ProjectControlPage.js
# Expected: empty (no hits).

# (j) Trial banner: PROJECTS_LIST_PAGES and read-only guard:
grep -n "PROJECTS_LIST_PAGES" frontend/src/components/TrialBanner.js
# Expected: 2 hits (declaration + usage).
grep -n "isReadOnly && (canManageBilling || isOwner)" frontend/src/components/TrialBanner.js
# Expected: 1 hit.
```

### 2. Build clean

```bash
cd frontend
npm run build
```
Expected: no new warnings.

### 3. Manual tests

#### Fix #1 — Nav overflow
- Open desktop browser at `/projects/<any_project_id>/control` as `project_manager`
- Top tab bar shows all 7 tabs in one row: דשבורד · מבנה · בקרת ביצוע · ליקויים · מסירות · בטיחות · תוכניות
- No horizontal scroll needed

- Same page at mobile 375px width
- Tab bar scrolls horizontally as before (no regression)

#### Fix #7 + #8 — Trial banner
- Log in as a user whose org is in `trial_expired` state, and whose global role is `project_manager` AND who has `can_manage_billing=true` (owner-like).
  - On `/projects` (list): NO red banner.
  - Enter a project: red banner appears at top.
- Log in as a user whose role is `execution_engineer` (non-billing).
  - On `/projects` (list): NO red banner.
  - Enter a project: NO red banner. (The "הגישה מוגבלת" dialog still appears — that's correct and untouched.)
- Log in as a user with role `contractor` on a project in an expired org.
  - Any page: NO red banner.

#### Fix #9 — Defect header
- Open any defect detail page (tap a defect from the list): `/tasks/<task_id>` or contractor view.
- Header top row:
  - Right side: "BrikOps" text (no helmet icon).
  - Left side: "חזרה לרשימת ליקויים" text + arrow → pointing right, arrow ON THE RIGHT of text.
- Tap the back link → returns to the correct previous page (no regression on the existing navigation logic).

#### Fix #10a — Badge RTL positioning
- `/projects/<id>/control?tab=defects` — unit grid: badges on unit icons sit visually at top-RIGHT of the icon in RTL (Hebrew), not overflowing the card.
- Same page in LTR English — badges sit at top-LEFT of the icon (original LTR behavior).
- Check at least one screen each: BuildingDefectsPage, ApartmentDashboardPage, InnerBuildingPage, HandoverOverviewPage.

#### Fix #10c — Notifications popup
- Tap the bell icon in the header on both desktop and mobile 375px.
- Popup appears fully on-screen, with at least 16px padding from all viewport edges.
- No clipping on right (RTL) or left (LTR) edges.

#### Fix #10b — Language menu
- Open hamburger menu.
- Tap "שפה".
- Lands on `/settings/account` — the page scrolls smoothly to the language section.
- The language `<select>` is visible in viewport without the user needing to scroll further.

### 4. Regression sanity

- Open NewDefectModal from a defect list → form fields still work, no layout regression
- Open a contractor's defect view → still accessible, only the header changed
- Open Settings page manually (not from hamburger) → nothing broken, language section still works

---

## Commit message (exactly)

```
fix(ui): Batch 1 closed-beta polish (7 surgical fixes)

1) ProjectControlPage: widen workTabs container max-w 560→1100 so the
   "תוכניות" tab stops cropping on desktop. Mobile still scrolls
   horizontally via overflow-x-auto.

2) TrialBanner: hide the banner on the projects list (`/`, `/projects`)
   so multi-org users aren't nudged before choosing a project. The
   banner still shows inside project routes.

3) TrialBanner: wrap the read-only banner render in
   `isReadOnly && (canManageBilling || isOwner)` so non-billing users
   (contractor, execution_engineer, site_manager, safety_assistant,
   viewer, management_team, and any PM without billing permission)
   never see the payment-required red bar. The "access limited"
   dialog remains for everyone — that's the correct user-facing
   message.

4) TaskDetailPage header: remove the HardHat icon (not part of the
   brand logo), add dir="rtl" to the flex container so BrikOps ends up
   on the right (RTL start) and the back link on the left (RTL end),
   reorder the back button's children so the arrow renders on the
   right of the Hebrew label per Hebrew idiom.

5) Badge RTL positioning: replace `-left-1.5` / `-left-1` with
   `-start-1.5` / `-start-1` in 5 files (BuildingDefectsPage ×2,
   ApartmentDashboardPage, InnerBuildingPage, HandoverOverviewPage)
   so the count badge auto-flips to the correct side in RTL vs LTR.
   NotificationBell stays untouched (different pattern).

6) NotificationBell: add collisionPadding={16} to PopoverContent so
   the popup auto-shifts inward when close to the viewport edge. No
   more right-edge clipping on narrow mobile widths.

7) HamburgerMenu + AccountSettingsPage: "שפה" menu item now navigates
   to /settings/account#language with a useEffect-driven smooth scroll
   to an `<section id="language">` anchor wrapping the existing
   language `<select>`. Entry stays in the hamburger for future
   multi-language rollout; it just lands the user on the right
   control now instead of the page top.

No new deps, no backend changes, no native changes.
```

---

## Deploy

```bash
./deploy.sh --prod
```

OTA only. No `./ship.sh` needed. Cloudflare Pages + Capgo handle the rest.

**Post-deploy send to Zahi:**
- `git log -1 --stat` (expected: 10 files, ~20 insertions, ~15 deletions)
- Unified diff
- Output of all 11 grep checks from VERIFY §1
- `git diff --stat backend/` (must be empty)
- Screenshots — desktop 1280px + mobile 375px of:
  - `/projects/:id/control` showing full 7-tab nav
  - A defect detail page showing clean header (logo right, back link left, no helmet)
  - Unit grid showing badges on the correct side in RTL
  - Bell popup not clipping
  - Hamburger → שפה → landing on Settings scrolled to language

---

## Definition of Done

- [ ] Fix #1: `max-w-[1100px]` on workTabs; grep confirms
- [ ] Fix #7: `PROJECTS_LIST_PAGES` excluded in TrialBanner; grep confirms
- [ ] Fix #8: read-only banner wrapped with `canManageBilling || isOwner`; grep confirms
- [ ] Fix #9: HardHat removed (import + usage); `dir="rtl"` added to header; back button children reordered
- [ ] Fix #10a: all 5 files have `-start-1.5` / `-start-1`; no `-left-1.5` / `-left-1` remaining in those files
- [ ] Fix #10c: `collisionPadding={16}` added to NotificationBell
- [ ] Fix #10b: menu path is `/settings/account#language`; AccountSettingsPage has `<section id="language">` + scroll useEffect
- [ ] All 11 grep checks from VERIFY §1 pass
- [ ] `git diff --stat backend/` is empty
- [ ] `git diff frontend/package.json frontend/package-lock.json` is empty
- [ ] `npm run build` succeeds with no new warnings
- [ ] All 6 manual tests from VERIFY §3 pass
- [ ] Screenshots sent to Zahi
- [ ] `./deploy.sh --prod` succeeded
