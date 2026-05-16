# Task #404 — Amendment: Safety nav tab position (replaces Step 6)

**Apply before starting implementation.** This replaces Step 6 of the Part 4 spec entirely. All other steps (1-5, 7) are unchanged.

---

## What changed & why

The original Step 6 said "add a nav tile to `ProjectDashboardPage`". That's wrong. Zahi wants the safety link in the **project-level top nav bar** — the same row that currently reads:

> דשבורד · מבנה · בקרת ביצוע · ליקויים · מסירות · תוכניות

**Final order (after this change):**

> דשבורד · מבנה · בקרת ביצוע · ליקויים · מסירות · **בטיחות** · תוכניות

Position 6 (between מסירות and תוכניות).

**Why this location:** Safety is a full domain (workers, docs, trainings, tasks, incidents, score, PDF register), not a dashboard tile and not a sub-tab inside another page. It sits peer-to-peer with the existing project-level domains.

---

## Where the nav lives

**File:** `frontend/src/pages/ProjectControlPage.js`

The project top-nav bar is a **local const** inside this page, not a shared component. It's defined as `workTabs` at **line ~3497** with a routing handler `handleWorkTab` at **line ~3506**. The HamburgerMenu is a global app-shell menu and contains no project-scoped items — **do NOT touch it**.

Verify the exact lines in your checkout:

```bash
grep -n "const workTabs" frontend/src/pages/ProjectControlPage.js
grep -n "const handleWorkTab" frontend/src/pages/ProjectControlPage.js
```

---

## Exact change 1 — `workTabs` array

Insert a `safety` entry between `handover` and `plans`. Keep the existing entries verbatim — do NOT reformat them.

**BEFORE (line ~3497-3504):**

```javascript
const workTabs = [
  { id: 'dashboard', label: 'דשבורד',    icon: BarChart3,     hidden: !['owner','admin','project_manager','management_team'].includes(myRole) },
  { id: 'structure', label: 'מבנה',       icon: Building2 },
  { id: 'qc',        label: 'בקרת ביצוע', icon: ClipboardCheck, hidden: !['owner','admin','project_manager','management_team'].includes(myRole) },
  { id: 'defects',   label: 'ליקויים',    icon: AlertTriangle },
  { id: 'handover',  label: 'מסירות',     icon: FileSignature, hidden: !['owner','admin','project_manager','management_team','contractor'].includes(myRole) },
  { id: 'plans',     label: 'תוכניות',    icon: FileText },
].filter(t => !t.hidden);
```

**AFTER:**

```javascript
const workTabs = [
  { id: 'dashboard', label: 'דשבורד',    icon: BarChart3,     hidden: !['owner','admin','project_manager','management_team'].includes(myRole) },
  { id: 'structure', label: 'מבנה',       icon: Building2 },
  { id: 'qc',        label: 'בקרת ביצוע', icon: ClipboardCheck, hidden: !['owner','admin','project_manager','management_team'].includes(myRole) },
  { id: 'defects',   label: 'ליקויים',    icon: AlertTriangle },
  { id: 'handover',  label: 'מסירות',     icon: FileSignature, hidden: !['owner','admin','project_manager','management_team','contractor'].includes(myRole) },
  { id: 'safety',    label: 'בטיחות',     icon: ShieldAlert,   hidden: !['owner','admin','project_manager','management_team'].includes(myRole) },
  { id: 'plans',     label: 'תוכניות',    icon: FileText },
].filter(t => !t.hidden);
```

**Role visibility:** `['owner','admin','project_manager','management_team']` — same 4 roles as `dashboard` and `qc`. Backend `_check_project_access` enforces the narrower `project_manager`/`management_team` at project-membership level, so an `owner`/`admin` without project membership will see the tab, click it, and land on `SafetyForbidden`. That's acceptable — consistent with how `dashboard` and `qc` behave today.

---

## Exact change 2 — `handleWorkTab` handler

Add a `safety` navigate branch. Place it **between `handover` and `plans`** so source order matches the tab order.

**BEFORE (line ~3506-3514):**

```javascript
const handleWorkTab = (id) => {
  if (id === 'dashboard') { navigate(`/projects/${projectId}/dashboard`); return; }
  if (id === 'qc')        { navigate(`/projects/${projectId}/qc`);        return; }
  if (id === 'handover')  { navigate(`/projects/${projectId}/handover`);  return; }
  if (id === 'plans')     { navigate(`/projects/${projectId}/plans`);     return; }
  setWorkMode(id);
  if (id !== 'structure') setActiveTab('');
  try { localStorage.setItem(`brikops_workMode_${projectId}`, id); } catch {}
};
```

**AFTER:**

```javascript
const handleWorkTab = (id) => {
  if (id === 'dashboard') { navigate(`/projects/${projectId}/dashboard`); return; }
  if (id === 'qc')        { navigate(`/projects/${projectId}/qc`);        return; }
  if (id === 'handover')  { navigate(`/projects/${projectId}/handover`);  return; }
  if (id === 'safety')    { navigate(`/projects/${projectId}/safety`);    return; }
  if (id === 'plans')     { navigate(`/projects/${projectId}/plans`);     return; }
  setWorkMode(id);
  if (id !== 'structure') setActiveTab('');
  try { localStorage.setItem(`brikops_workMode_${projectId}`, id); } catch {}
};
```

---

## `lucide-react` import

`ShieldAlert` is the icon. It is probably already imported in `ProjectControlPage.js` (used elsewhere) — **check first**:

```bash
grep -n "ShieldAlert" frontend/src/pages/ProjectControlPage.js
```

- If the grep returns hits → icon is already imported. You're done.
- If empty → add `ShieldAlert` to the existing `lucide-react` import line at the top of the file. **Do NOT add a new import statement** — merge into the existing one.

---

## DO NOT

- ❌ Do NOT touch `HamburgerMenu.js` — it's the global app-shell menu with no project-scoped items. Not the right place.
- ❌ Do NOT add a tile to `ProjectDashboardPage.js` — the amended plan supersedes that instruction.
- ❌ Do NOT extract `workTabs` into a shared component. Keep it a local const inside `ProjectControlPage.js`. The house pattern is local.
- ❌ Do NOT change the order of any other tab.
- ❌ Do NOT change the `hidden` role list on any existing tab.
- ❌ Do NOT add `safety` to the `if (id !== 'structure') setActiveTab('');` exception — `safety` is a navigate-out tab, not an in-page workMode tab, so it returns before that line runs (same as `dashboard`/`qc`/`handover`/`plans`).
- ❌ Do NOT add a new `lucide-react` import line — merge into the existing one.

---

## VERIFY

### 1. Tab appears in correct position

Open `/projects/<any_project_id>/control` as a user with role `project_manager` or `management_team`. The top nav bar must read **in this exact order**:

```
דשבורד · מבנה · בקרת ביצוע · ליקויים · מסירות · בטיחות · תוכניות
```

(Scroll horizontally if the nav overflows on mobile — the order is what matters, not whether all 7 fit on one screen.)

### 2. Tab is hidden for contractor

Open the same page as a `contractor` user. The "בטיחות" tab must NOT appear (same hidden behavior as `dashboard` and `qc` today).

### 3. Click navigates correctly

Click "בטיחות" as PM. Browser URL must become `/projects/<project_id>/safety`. Browser back button must return to Control page.

### 4. Other tabs unchanged

Click each of the other 6 tabs in order. Each must behave exactly as it did before this change. No regression.

### 5. No other files touched

```bash
git diff --stat | grep -v "frontend/src/pages/ProjectControlPage.js\|frontend/src/pages/SafetyHomePage.js\|frontend/src/components/safety/\|frontend/src/services/api.js\|frontend/src/App.js\|frontend/src/i18n/he.json"
```

Expected: empty. In particular, `HamburgerMenu.js` and `ProjectDashboardPage.js` must NOT appear in the diff.

---

## Fold this into the main Part 4 commit

This amendment is a scope clarification, not a separate commit. Include all changes (new page + nav tab) in the single Part 4 commit. No separate "fix" commit needed.

The commit message in the original spec is already updated to reflect this — it lists `ProjectControlPage.js` instead of `ProjectDashboardPage.js` in the Modified files section.

---

## Definition of Done (for this amendment)

- [ ] `safety` entry inserted in `workTabs` at position 6 (between handover and plans)
- [ ] `safety` navigate branch added in `handleWorkTab` between handover and plans
- [ ] `ShieldAlert` icon imported (added to existing lucide-react import only if not already present)
- [ ] Tab bar order verified visually as: דשבורד · מבנה · בקרת ביצוע · ליקויים · מסירות · בטיחות · תוכניות
- [ ] Tab hidden from `contractor`, visible to `owner`/`admin`/`project_manager`/`management_team`
- [ ] `HamburgerMenu.js` NOT modified
- [ ] `ProjectDashboardPage.js` NOT modified
- [ ] Single commit containing both this amendment and the rest of Part 4
