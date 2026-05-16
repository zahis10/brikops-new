# 🐛 BrikOps Closed-Beta Fixes — Queue

> **⚠️ קלוד — אם אני מבקש ממך לעבוד על אחד הliquים האלה, תקרא את הקובץ הזה קודם.**
>
> **Opened:** 2026-04-23
> **Status:** 10 fixes collected, ready to spec + ship
> **Blocks:** Safety Phase 2 (must finish these first per Zahi's decision)
> **Related:** `SAFETY-STATUS.md` — the safety module state

---

## Executive summary

| # | Title | Type | Deploy | Complexity |
|---|---|---|---|---|
| 1 | Nav max-width crops "תוכניות" tab on desktop | CSS | OTA | Trivial (1 line) |
| 2 | Clicking a project should land on "מבנה" tab by default | Routing | OTA | Simple |
| 3 | Inline "הוסף חברה" modal inside NewDefectModal | UX refactor | OTA | Medium |
| 4 | Inline "הוסף קבלן" modal + investigate contractor↔company model | UX + investigation | OTA | Medium |
| 5 | Tag team members on defect (CC-style) | New feature | OTA | Medium-Large |
| 6 | Contact picker from phone in add-contact forms | Native plugin | **ship.sh** | Medium |
| 7 | Trial banner shows on projects list (should be per-project) | Scoping | OTA | Simple |
| 8 | Trial banner shows to non-billing users (should be owner-only) | Role check | OTA | Simple |
| 9 | Defect detail header: remove helmet icon + swap logo/back-link positions | UI polish | OTA | Simple |
| 10 | QA report from PrimeTestLab — 3 sub-bugs | UI polish | OTA | Simple each |

---

## Detailed fix list

### Fix #1 — Nav overflow crops "תוכניות" tab on desktop

**Problem:** On desktop browser, the project top-nav shows only 6 tabs (דשבורד · מבנה · בקרת ביצוע · ליקויים · מסירות · בטיחות) — the 7th tab "תוכניות" is hidden off-screen, requires horizontal scroll that users don't discover.

**Root cause:** `frontend/src/pages/ProjectControlPage.js:3548` — the container has `max-w-[560px]` + `overflow-x-auto`. 560px was designed for mobile viewport but persists on desktop.

**Fix:** Raise `max-w-[560px]` → `max-w-[1100px]` (or remove the max entirely and rely on parent `max-w-[1100px]`). Mobile still scrolls horizontally, desktop shows all 7 tabs.

**Verify:** Desktop 1280px+ shows all 7 tabs without scroll. Mobile 375px still fits 2-3 tabs and scrolls.

---

### Fix #2 — Default landing tab = "מבנה"

**Problem:** Clicking a project from the projects list lands on `/dashboard` or some default — Zahi wants always land on "מבנה" (structure) first.

**Root cause to investigate:** The project-card click handler in the projects list. Likely navigates to `/projects/:projectId/dashboard` — should go to `/projects/:projectId/control` (which defaults to structure workMode via `localStorage.getItem('brikops_workMode_${projectId}')` or the initial state).

**Fix approach:**
1. Find the projects-list click handler (probably `pages/ProjectsPage.js` or similar)
2. Change the target URL to `/projects/:projectId/control` (or `/control?tab=structure` to be explicit)
3. Check `ProjectControlPage.js` initial `workMode` state — ensure it defaults to `'structure'` if no `localStorage` value

**Verify:** Click any project from list → lands on Structure tab highlighted in workTabs.

---

### Fix #3 — Inline "הוסף חברה" modal inside NewDefectModal

**Problem:** User fills out NewDefectModal (title, description, priority, photos). When the domain has no companies, the "+ הוסף חברה" button navigates to `/projects/:id/control?tab=companies` — **destroys all form data**, user has to re-enter everything.

**Root cause:** `frontend/src/components/NewDefectModal.js:809, 822, 849, 876` — 4 navigate calls that exit the modal.

**Fix:** Replace the navigate calls with opening a **nested modal** (the existing Add-Company form) ON TOP of NewDefectModal.
1. Extract the Add-Company form content (currently a page section under `/control?tab=companies`) into a reusable `<AddCompanyModal>` component
2. In NewDefectModal, replace `navigate(...)` with `setShowAddCompanyModal(true)`
3. On successful save: append new company to the dropdown options, auto-select it, close nested modal, keep NewDefectModal state intact

**Verify:** User types full defect → clicks "+ הוסף חברה" → modal stacks → fills company form → save → returns to defect form with new company selected + all original input preserved.

---

### Fix #4 — Inline "הוסף קבלן" modal + investigate contractor↔company model

**Part A (UX fix, mirrors #3):** Same pattern — "+ הוסף קבלן" button inside NewDefectModal also navigates away instead of opening inline modal. Fix the same way: extract Add-Contractor form to reusable modal, call it from NewDefectModal.

**Part B (investigation before spec):** Before writing the spec, investigate:
- Where are contractors registered in the data model? `project_companies`? Separate collection?
- Do contractors have a "domain/trade" field (חשמל / אינסטלציה / גבס)?
- Is there enforcement that an electrician can only be registered under an electrical company?
- Or is it a free association (tag only, no enforcement)?
- What's Zahi's intent — strict enforcement, warning-only, or free?

Report findings to Zahi before writing the UX spec.

**Verify:** Same as #3 but for contractor flow. Plus a short investigation report on contractor↔company association.

---

### Fix #5 — Tag team members on defect (CC-style)

**Problem:** No way to notify secondary stakeholders on a defect. Example: engineer logs defect on tile work (assigned to contractor), but PM needs to order more tiles — currently no way to flag PM without making PM the owner.

**New field:** `tagged_user_ids: [str]` on defect/task schema (optional multi-select).

**UI:** In NewDefectModal (and EditDefectModal), after the contractor section, add "שתף עם" multi-select populated from project_memberships.

**Notifications:** Tagged users get:
- Push/email notification on defect creation
- The defect appears in a "מתויגים עליי" filter in ליקויים tab
- Notification also on defect updates (status changes, comments)

**Display:** On defect card, show small avatar strip of tagged users (max 3 + "+N").

**Open questions to resolve before implementation:**
1. Can tagged user self-remove from tag (like "leave thread" in Slack)?
2. Is notification severity same as assignee, or softer?
3. Permissions — can tagged user comment/change status, or read-only?
4. Does "watchers"/"נצפה ע״י" pattern already exist somewhere that should be extended vs. a new field?

**Investigation needed:** Search `frontend/src/components/` and `backend/contractor_ops/router.py` for existing `watchers` / `followers` / `cc` / `tagged` patterns.

**Verify:** Create defect → tag 2 users → they receive notification → they can filter "מתויגים עליי" and see the defect → defect card shows their avatars.

---

### Fix #6 — Contact picker from phone 📱 **(NATIVE CHANGE — ship.sh)**

**Problem:** Phone number field requires manual entry. User wants option to pick from device contacts instead.

**Affected forms:** Add contractor · Add company contact person · Add team member · Add safety worker

**Implementation:**
1. Install Capacitor plugin: `npm install @capacitor-community/contacts`
2. iOS: add `NSContactsUsageDescription` to `frontend/ios/App/App/Info.plist`:
   ```
   <key>NSContactsUsageDescription</key>
   <string>BrikOps זקוק לגישה לאנשי הקשר כדי שתוכל לבחור מהם במקום להקליד ידנית</string>
   ```
3. Android: add to `frontend/android/app/src/main/AndroidManifest.xml`:
   ```xml
   <uses-permission android:name="android.permission.READ_CONTACTS" />
   ```
4. UI: small "בחר איש קשר" icon button next to phone input. Click → native picker → populate name + phone.
5. Web fallback: Contact Picker API if `'contacts' in navigator && 'ContactsManager' in window`, else hide button.

**Deploy:** Requires `./ship.sh` + new App Store / Play Store builds (Android v1.0.19+, iOS next build). Plugin changes `package.json` + native files.

**Verify:** On iOS/Android, tap the icon → permission prompt (first time) → native picker → select contact → fields auto-fill. On web desktop, button hidden or falls back to manual.

---

### Fix #7 — Trial banner scope: per-project, not account-wide

**Problem:** "תקופת הניסיון הסתיימה" red banner appears on projects list screen. Shown because user's OWN org is expired — even though user also has access to ANOTHER project whose org has active license.

**Root cause:** Banner tied to `user.current_org.subscription_status` — doesn't know which project user is viewing.

**Fix:**
- Hide banner on `/projects` (list) and `/` routes
- Show only inside specific project routes (`/projects/:projectId/*`)
- Check the ORG of the viewed project (not user's default org)

**Edge case to handle:** If user's ALL orgs are expired, need a softer banner on the projects list ("אין לך פרויקטים פעילים — שדרג כדי להמשיך") with upgrade CTA.

**Verify:** User with 1 expired + 1 active project → no banner on `/projects` → enters expired project → banner appears → enters active project → no banner.

---

### Fix #8 — Trial banner visibility: owner/billing only

**Problem:** Regular team member (engineer, PM, contractor) sees the "יש לבצע תשלום" banner at the top when their org is expired. Implies it's their responsibility to pay — but billing is the org owner's job.

**Current state (correct):** The "הגישה מוגבלת" dialog is shown to all — friendly, tells them to contact org owner. Keep that.

**Fix:** Red top banner with "יש לבצע תשלום" CTA shown **only** to:
- `user.role === 'owner'` OR
- `user.is_billing_admin === true` (or whatever the billing admin flag is)

Non-billing users: either no banner (dialog is enough), or soft message: "מנהל הארגון צריך לשדרג את החשבון" (no payment CTA).

**Verify:** Org expired. Owner sees red banner + "שדרג" CTA. Engineer sees friendly dialog only, no red banner, no payment CTA.

---

### Fix #9 — Defect detail header polish

**Problem (view at the top of a defect detail page):**
1. Helmet icon 🪖 next to the word "BrikOps" — not part of official logo, should be removed
2. Layout: "חזרה לרשימת ליקויים ←" on RIGHT, "BrikOps" on LEFT — Zahi wants swapped

**Fix:**
- Remove the helmet icon entirely, OR replace with the real favicon/logo
- Layout (RTL convention):
  - RIGHT (start) = **BrikOps logo**
  - LEFT (end) = **"חזרה לרשימת ליקויים ←"**

**Location to find:** Probably `frontend/src/pages/DefectDetailPage.js` or a `ContractorViewPage` — the view has minimal chrome (no full nav), suggests a public/contractor-only defect view.

**Verify:** Open a defect detail page → see BrikOps logo on right (start), "חזרה לרשימת ליקויים" on left (end), no helmet.

---

### Fix #10 — QA report from PrimeTestLab (3 sub-bugs)

**Source:** `uploads/1776811407_BrikOps_QA_Report_v1_0_14.pdf` · Android v1.0.14 · April 2026

All 3 are Medium priority UI/RTL polish, none are blockers. Should be fixed together.

#### #10a — Floor badge overflows past card right edge

**Where:** Property/unit cards displaying "קומה 1/2/3" badges (probably `UnitCard` or `ApartmentCard` component).

**Problem:** Badge circle positioned **outside** the card's right border, appears detached/floating.

**Fix:**
- Replace physical `right: -X` with logical `insetInlineEnd` (or framework equivalent like `Alignment.topEnd`)
- Reduce negative offset (currently too large)
- If parent has `overflow: hidden`, badge must fit inside — or set `overflow: visible` and use small offset (4-8dp)
- Verify on narrow + wide card widths

#### #10b — Language menu opens Settings page

**Where:** Side/hamburger menu → "שפה" option.

**Problem:** Tapping "שפה" navigates to Settings page, not a language picker. Misleading label.

**Fix:** Two options:
1. Wire the menu item to open an actual language picker (modal/sheet/screen) with list of languages + persist + reload app
2. If language is meant to live inside Settings — remove the standalone menu entry to avoid misleading label

Zahi to decide direction at spec time.

#### #10c — Notifications popup clipped on right edge (RTL)

**Where:** Header → bell icon → notifications popup.

**Problem:** Popup has zero right-side padding, flush against screen edge, content clipped. Free space on left is wasted. Especially visible in Hebrew RTL because right edge is the "start" side users look at first.

**Fix:**
- Add `marginInlineEnd: 16dp` (or equivalent Tailwind `me-4`) instead of hardcoded `right: 0`
- Add edge-clamping to popup positioner — if calculated position overflows, auto-shift inward
- Consider redesigning as bottom sheet on mobile (more reliable across screen sizes)
- Test in both RTL Hebrew (default) and LTR English

**Cross-cutting observation (from the QA report):** #10a and #10c both indicate physical-edge CSS (`left/right`) used throughout the app. Broader cleanup: migrate to logical properties (`start/end`, `inset-inline`) for RTL correctness. Consider a dedicated "RTL audit" sweep as a separate follow-up.

---

## Proposed execution batches

Balance between "ship fast" (quick wins together) and "don't break things" (complex changes alone):

### Batch 1 — Quick polish (all CSS/routing, no logic changes) ⏱ ~3 hours total
Ship together in a single commit:
- **#1** nav max-w fix
- **#7 + #8** trial banner scoping + role visibility
- **#9** defect header helmet + layout swap
- **#10a** floor badge overflow
- **#10b** language menu (with Zahi's direction)
- **#10c** notifications popup RTL clipping

Deploy: `./deploy.sh --prod` (OTA). No native changes.

### Batch 2 — Navigation + inline modals (related UX) ⏱ ~5 hours
Ship together:
- **#2** default landing tab
- **#3** inline "הוסף חברה" modal
- **#4** inline "הוסף קבלן" modal + investigation report before spec

Deploy: OTA. Depends on extracting AddCompany/AddContractor forms into reusable modals.

### Batch 3 — New feature (tagging) ⏱ ~8-10 hours
Ship alone (new schema + notifications + UI):
- **#5** team member tagging on defect

Deploy: OTA. Requires backend schema migration + notification system hook.

### Batch 4 — Native change ⏱ ~4 hours + store review
Ship alone (requires `ship.sh` + store release):
- **#6** contact picker

Deploy: `./deploy.sh --prod` **+** `./ship.sh` (iOS + Android builds + TestFlight + Play Console release).

---

## Execution order (Zahi to confirm)

Recommended order — **Batch 1 → Batch 2 → Batch 3 → Batch 4**:
1. **Batch 1** first (quick wins give users immediate improvement + build confidence)
2. **Batch 2** (fixes the most painful flow — defect creation)
3. **Batch 3** (new capability, value-add)
4. **Batch 4** (nice-to-have, and store release = slower feedback cycle)

Alternative: start with Batch 2 if flow pain is more urgent than polish.

**Tell Zahi** to pick the order before starting.

---

## When Zahi says "let's start fix #X"

1. Re-read THIS file for the specific fix
2. Investigate the files mentioned (Grep/Read) to verify the root cause
3. Use `brikops-spec-writer` skill to write the spec (or for trivial fixes, write a mini-spec inline)
4. Present to Zahi for approval
5. Send to Replit
6. Review the resulting diff
7. Approve or request changes
8. Ship

## When Zahi says "batch #X"

Same flow, but one spec covering all fixes in the batch, and one commit to Replit.

---

## Tracker task mapping (optional, for future reference)

No individual tasks created yet for these fixes — will be created when a batch is started, as a single task per batch:

- Task: "Batch 1 — Quick polish (6 fixes)"
- Task: "Batch 2 — Navigation + inline modals (3 fixes)"
- Task: "Batch 3 — Team member tagging"
- Task: "Batch 4 — Contact picker (native)"

---

**Reminder to future Claude sessions:**
> קלוד, קרא את `CLOSED-BETA-FIXES.md` לפני שאתה מטפל באחד הליקויים. אל תתחיל לעבוד בלי להיזכר מה כל ליקוי, איפה הוא חי בקוד, ולאיזה batch הוא שייך.

---

## 🎓 Lessons learned (bugs that hit production)

### Batch 2a bug — nested Radix Dialog with `modal={false}`
**Problem:** NewDefectModal uses `<DialogPrimitive.Root modal={false}>`. When a nested Dialog opens (QuickAddCompanyModal with default `modal={true}`), focus transfers into the nested dialog. Radix's `DismissableLayer` fires `onFocusOutside` on the parent → parent's `onOpenChange(false)` fires → parent unmounts → nested dialog unmounts too → user loses everything.

**Fix:** add `onInteractOutside={(e) => e.preventDefault()}` to parent's `DialogPrimitive.Content`. This is the catch-all for pointer + focus dismiss. `onPointerDownOutside` alone is NOT enough — it only catches pointer events.

**Checklist for any future spec that adds a nested Dialog/Modal inside another Radix Dialog:**
- [ ] Check if parent uses `modal={false}` — if yes, verify both `onPointerDownOutside` AND `onInteractOutside` are prevented on parent's Content
- [ ] Manual test must explicitly verify: **parent modal still visible** with overlay behind the nested modal (not just "nested modal appeared")
- [ ] Manual test must explicitly verify: **typed content in parent preserved** after closing nested modal
- [ ] Run manual test **before commit**, not just post-deploy

### Batch 2a process fix — pre-deploy manual testing
**Problem:** Manual tests were only run POST-deploy. The `onInteractOutside` bug was caught only after users saw it in production.

**Going forward:** For any batch that touches modals, forms, or user input flows, add a **PRE-COMMIT MANUAL TEST** step to the spec. Replit (or Zahi) runs the app in Replit preview / local dev and executes the key user flow before committing. Only commit if the manual test passes.
