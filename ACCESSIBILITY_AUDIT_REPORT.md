# BrikOps Accessibility Audit Report

**Standard**: Israeli Standard 5568 (SI 5568) — based on WCAG 2.1 Level AA  
**Date**: 2026-03-14  
**Scope**: Full-stack application — React SPA frontend (36 page components, 20 shared components, 47 UI primitives)  
**Auditor**: Automated code-level review (no assistive-technology user testing)

---

## Launch Readiness Verdict

| Criterion | Assessment |
|-----------|------------|
| **Compliance Level** | **Partial** — Strong foundation (RTL, Radix primitives) but significant gaps in modal accessibility, landmarks, and legal requirements |
| **Legal Risk** | **HIGH** — Missing mandatory accessibility statement page (Israeli law); custom modals block keyboard/screen-reader users |
| **Launch Blocker?** | **Yes** — 2 critical findings must be resolved before public launch |
| **Top 3 Must-Fix** | 1. Add accessibility statement page (הצהרת נגישות) — legal requirement. 2. Migrate custom modals to Radix Dialog/Sheet/Drawer — keyboard users are blocked. 3. Add `<main>` landmark and skip-to-content link — screen reader navigation is broken. |

---

## Executive Summary

BrikOps is a Hebrew RTL construction-management SPA. The app has a solid foundation — correct `lang="he" dir="rtl"` on `<html>`, Radix-based accessible primitives for Dialog/Sheet/Select/Tabs, and some `aria-label` usage on key buttons. However, several **critical and high-severity gaps** exist that would fail an SI 5568 / WCAG 2.1 AA compliance audit.

**Finding counts**:

| Severity | Count |
|----------|-------|
| Critical | 2 |
| High     | 10 |
| Medium   | 6 |
| Low      | 4 |
| **Total** | **22** |

Every finding is categorized as one of:
- **Legal compliance risk** — May trigger legal action under Israeli disability regulations
- **Serious usability barrier** — Blocks or severely hinders assistive technology users
- **Improvement / hardening** — Best practice that improves experience but is not a strict conformance failure

---

## Legal Compliance Checklist (SI 5568 / Israeli Regulations)

| Requirement | Status | Details |
|-------------|--------|---------|
| Accessibility statement page (הצהרת נגישות) | **FAIL** | No `/accessibility` route exists; no statement published |
| Accessibility coordinator contact info | **FAIL** | No contact info for accessibility issues anywhere in the app |
| Keyboard navigation for all functions | **FAIL** | Custom modals lack focus trap/Escape; password toggles have `tabIndex={-1}`; some clickable `<div>`s are not keyboard accessible |
| Screen reader support | **FAIL** | No `<main>` landmark; no skip-to-content; modals lack `role="dialog"`; progress indicators lack ARIA |
| Color contrast (4.5:1 text, 3:1 large/UI) | **NOT TESTED** | Requires automated measurement tools (out of scope) |
| RTL layout correctness | **PASS** | `lang="he" dir="rtl"` on `<html>`; per-component `dir="rtl"` on modal content; layout renders correctly in RTL |
| Touch target minimum size | **PARTIAL** | Primary buttons are well-sized; some icon buttons and filter chips are below 44×44px mobile recommendation |
| Zoom support (200%+) | **PASS** | Viewport meta does not restrict zoom (`user-scalable` not set to `no`) |
| Form labels and error identification | **PARTIAL** | Many `<label>` elements lack `htmlFor`/`id` association; Radix-based forms use `aria-describedby`/`aria-invalid` correctly |

---

## Interactive Component Inventory

| Component Type | Instances | Implementation | Accessible? | Key Issues |
|----------------|-----------|---------------|-------------|------------|
| **Tabs** (Radix `TabsPrimitive`) | `ui/tabs.jsx` | Radix `@radix-ui/react-tabs` | **Yes** | Full ARIA, keyboard arrow-key support |
| **Tabs** (custom, LoginPage) | `LoginPage.js:278` | Manual `role="tablist"`/`role="tab"` | **Partial** | Missing `aria-controls`, `role="tabpanel"`, arrow-key nav |
| **Dialog** (Radix) | `ui/dialog.jsx` | Radix `@radix-ui/react-dialog` | **Yes** | Focus trap, Escape, `aria-modal`, sr-only close label |
| **Dialog** (custom raw `<div>`) | ~12 instances | `fixed inset-0` + `onClick` backdrop | **No** | No `role="dialog"`, no focus trap, no Escape, no focus restore |
| **Sheet/Drawer** (Radix) | `ui/sheet.jsx`, `ui/drawer.jsx` | Radix/Vaul | **Yes** | Full ARIA, focus trap, Escape |
| **Drawer** (custom, ManagementPanel) | `ManagementPanel.js` (4 instances) | `fixed inset-0` + `onClick` | **No** | Same issues as custom dialogs |
| **Dropdown** (NotificationBell) | `NotificationBell.js` | Absolute-positioned `<div>` | **No** | No `aria-expanded`, no Escape, no focus management |
| **Select** (Radix) | `ui/select.jsx` | Radix `@radix-ui/react-select` | **Yes** | Full ARIA, keyboard support |
| **Icon-only buttons** | ~15+ across pages | `<button>` with Lucide icon child | **Partial** | Some use `title` only (not `aria-label`); some have no accessible name |
| **Toast notifications** (Sonner) | App-wide via `toast()` | Sonner library | **Partial** | Sonner has basic SR support; no explicit `aria-live` region configured |
| **Progress ring** (SVG) | `ContractorDashboard.js:62` | Custom SVG circles | **No** | No `role="progressbar"`, no `aria-valuenow` |
| **Progress bars** (div) | `BuildingQCPage.js:389`, `FloorDetailPage.js` | `<div>` width percentage | **No** | No `role="progressbar"`, no `aria-value*` |
| **Image lightbox** | `TaskDetailPage.js:1461` | `fixed` overlay with `<img>` | **No** | No `role="dialog"`, no keyboard close, no alt text |
| **Carousel** (Radix) | `ui/carousel.jsx` | Embla + Radix patterns | **Yes** | `role="region"`, `aria-roledescription`, keyboard nav |
| **Filter button groups** | `ContractorDashboard.js:232`, `BuildingQCPage.js:319` | `<button>` with CSS active state | **Partial** | Missing `aria-pressed` or `aria-current` |
| **Camera modal** | `CameraModal.js` | Radix `@radix-ui/react-dialog` | **Yes** | Uses Radix Dialog directly |
| **Export modal** | `ExportModal.js` | App's Radix `Dialog` wrapper | **Yes** | Uses `DialogContent`/`DialogTitle` |
| **Filter drawer** | `FilterDrawer.js` | App's Radix `Sheet` wrapper | **Yes** | Uses `SheetContent`/`SheetTitle`/`SheetDescription` |
| **User drawer** | `UserDrawer.js` | App's Radix `Drawer` wrapper | **Yes** | Uses `DrawerContent`/`DrawerTitle` |
| **Project billing edit** | `ProjectBillingEditModal.js` | App's Radix `Dialog` wrapper | **Yes** | Uses `DialogContent`/`DialogTitle`/`DialogDescription` |
| **Complete account modal** | `CompleteAccountModal.js` | Custom `fixed inset-0` `<div>` | **No** | No dialog semantics, no focus trap |
| **Phone change modal** | `PhoneChangeModal.js` | Custom `fixed inset-0` `<div>` | **No** | No dialog semantics, no focus trap |
| **Paywall modal** | `PaywallModal.js` | Custom `fixed inset-0` `<div>` | **No** | No dialog semantics, no focus trap |
| **Upgrade wizard** | `UpgradeWizard.js` | Inline form (no overlay) | **Partial** | Not a modal; form labels need review |

---

## Critical User Journey Results

### Journey 1: Login / Registration / Onboarding

| Page | Keyboard Nav | Screen Reader | Issues |
|------|-------------|---------------|--------|
| `LoginPage.js` | **Partial** | **Partial** | Tab pattern has `role="tab"`/`aria-selected` but missing `aria-controls` and `role="tabpanel"`. Password show/hide button has `tabIndex={-1}` (unreachable). |
| `PhoneLoginPage.js` | **OK** | **Partial** | OTP input is functional; no major keyboard blocks. |
| `RegisterPage.js` | **OK** | **Partial** | `<label>` elements lack `htmlFor`/`id` association with inputs. |
| `OnboardingPage.js` | **OK** | **Partial** | Form is functional; some labels may lack association. |
| `ForgotPasswordPage.js` | **OK** | **OK** | Simple form, no major issues. |
| `ResetPasswordPage.js` | **Partial** | **Partial** | Password toggle buttons have `tabIndex={-1}`. |

### Journey 2: ProjectControlPage (Manager Main View)

| Area | Keyboard Nav | Screen Reader | Issues |
|------|-------------|---------------|--------|
| Building expand/collapse | **OK** | **OK** | Uses `aria-expanded` and `aria-label` ✓ |
| Hero card carousel | **Partial** | **Partial** | Carousel dots have `aria-label` ✓; Radix carousel component is accessible |
| FAB menu | **Partial** | **Fail** | No `aria-label` or `aria-expanded` on FAB button |
| Hard-delete confirmation modal | **Fail** | **Fail** | Custom `<div>` overlay — no dialog semantics, no focus trap, no Escape |
| Step-up auth modal | **Fail** | **Fail** | Custom `<div>` overlay — same issues |
| Add floor/unit inline forms | **OK** | **Partial** | `onKeyDown` Enter handled; labels not formally associated |

### Journey 3: Defect Creation + TaskDetailPage

| Area | Keyboard Nav | Screen Reader | Issues |
|------|-------------|---------------|--------|
| `NewDefectModal.js` | **Fail** | **Fail** | Custom `<div>` bottom sheet — no dialog semantics, no focus trap, no Escape |
| `TaskDetailPage.js` main content | **OK** | **Partial** | Content is scrollable; images have some alt text |
| Image lightbox | **Fail** | **Fail** | Custom overlay with no keyboard close, no `role="dialog"`, `alt=""` on enlarged image |
| Trade-mismatch modal | **Fail** | **Fail** | Custom `<div>` overlay — no dialog semantics |
| Comment input | **OK** | **OK** | `onKeyDown` Enter handled |

### Journey 4: QC Flow (4 Pages)

| Page | Keyboard Nav | Screen Reader | Issues |
|------|-------------|---------------|--------|
| `QCFloorSelectionPage.js` | **OK** | **Partial** | Building items are `<button>` (good); search input accessible; back button has `aria-label` |
| `BuildingQCPage.js` | **OK** | **Partial** | Floor items are `<button>` (good); filter buttons missing `aria-pressed`; progress bars missing `role="progressbar"` and `aria-value*` |
| `FloorDetailPage.js` | **OK** | **Partial** | Stage items are interactive; progress bar missing ARIA; summary stats use `text-[10px]` |
| `StageDetailPage.js` | **OK** | **OK** | Good `aria-label` coverage on action buttons (save, submit, approve, reject, reopen). Reject/reopen modals are custom `<div>` overlays (no dialog semantics). |

### Journey 5: ContractorDashboard

| Area | Keyboard Nav | Screen Reader | Issues |
|------|-------------|---------------|--------|
| Header stats | **OK** | **Partial** | No `<main>` landmark; stats are visual-only (no ARIA) |
| ProgressRing SVG | **N/A** | **Fail** | No `role="progressbar"`, no `aria-valuenow` |
| Project filter buttons | **OK** | **Partial** | Missing `aria-pressed` on active button |
| Open task cards | **OK** | **OK** | Action buttons ("צלם ותקן", "פרטים") are real `<button>` elements ✓ |
| Completed task items | **Fail** | **Fail** | `<div onClick>` — not keyboard focusable, no role |
| Settings/Logout icon buttons | **OK** | **Partial** | `title` only, no `aria-label` |

### Journey 6: Admin Pages

| Page | Keyboard Nav | Screen Reader | Issues |
|------|-------------|---------------|--------|
| `AdminPage.js` | **OK** | **Partial** | Uses `<header>` ✓; nav cards are `<button>` or links |
| `AdminUsersPage.js` | **Partial** | **Fail** | User detail drawer, role-edit, phone/password modals are all custom `<div>` overlays — no dialog semantics, no focus trap, no Escape |

**Note**: `AdminBillingPage.js`, `AdminOrgsPage.js`, and `OrgBillingPage.js` were excluded from deep audit per project constraints. They contain custom `<div>` modal overlays that likely share the same accessibility issues documented above.

### Journey 7: Account / Settings

| Page | Keyboard Nav | Screen Reader | Issues |
|------|-------------|---------------|--------|
| `AccountSettingsPage.js` | **Partial** | **Partial** | Password toggle has `tabIndex={-1}`; phone change triggers `PhoneChangeModal` (custom `<div>`, no dialog semantics) |
| `CompleteAccountModal.js` | **Fail** | **Fail** | Custom `<div>` overlay — no dialog semantics, no focus trap |

---

## Keyboard / Focus Audit Per Modal/Drawer/Dropdown

| Component | Focus Visible | Focus Order | Escape Key | Focus Trap | Focus Return |
|-----------|:------------:|:-----------:|:----------:|:----------:|:------------:|
| `ui/dialog.jsx` (Radix) | ✓ | ✓ | ✓ | ✓ | ✓ |
| `ui/sheet.jsx` (Radix) | ✓ | ✓ | ✓ | ✓ | ✓ |
| `ui/drawer.jsx` (Vaul) | ✓ | ✓ | ✓ | ✓ | ✓ |
| `FilterDrawer.js` → uses Sheet | ✓ | ✓ | ✓ | ✓ | ✓ |
| `UserDrawer.js` → uses Drawer | ✓ | ✓ | ✓ | ✓ | ✓ |
| `CameraModal.js` → uses Radix Dialog | ✓ | ✓ | ✓ | ✓ | ✓ |
| `ExportModal.js` → uses Dialog | ✓ | ✓ | ✓ | ✓ | ✓ |
| `ProjectBillingEditModal.js` → uses Dialog | ✓ | ✓ | ✓ | ✓ | ✓ |
| `ProjectControlPage.js` confirmation modal | ✗ | ✗ | ✗ | ✗ | ✗ |
| `ProjectControlPage.js` step-up auth | ✗ | ✗ | ✗ | ✗ | ✗ |
| `TaskDetailPage.js` trade-mismatch modal | ✗ | ✗ | ✗ | ✗ | ✗ |
| `TaskDetailPage.js` image lightbox | ✗ | ✗ | ✗ | ✗ | ✗ |
| `StageDetailPage.js` reject modal | ✗ | ✗ | ✗ | ✗ | ✗ |
| `StageDetailPage.js` reopen modal | ✗ | ✗ | ✗ | ✗ | ✗ |
| `AdminUsersPage.js` user detail drawer | ✗ | ✗ | ✗ | ✗ | ✗ |
| `AdminUsersPage.js` role-edit modal | ✗ | ✗ | ✗ | ✗ | ✗ |
| `AdminUsersPage.js` phone modal | ✗ | ✗ | ✗ | ✗ | ✗ |
| `AdminUsersPage.js` password modal | ✗ | ✗ | ✗ | ✗ | ✗ |
| `ManagementPanel.js` bottom sheets (×4) | ✗ | ✗ | ✗ | ✗ | ✗ |
| `WhatsAppRejectionModal.js` | ✗ | ✗ | ✗ | ✗ | ✗ |
| `QCApproversTab.js` approver modal | ✗ | ✗ | ✗ | ✗ | ✗ |
| `NewDefectModal.js` bottom sheet | ✗ | ✗ | ✗ | ✗ | ✗ |
| `PaywallModal.js` overlay | ✗ | ✗ | ✗ | ✗ | ✗ |
| `CompleteAccountModal.js` overlay | ✗ | ✗ | ✗ | ✗ | ✗ |
| `PhoneChangeModal.js` overlay | ✗ | ✗ | ✗ | ✗ | ✗ |
| `NotificationBell.js` dropdown | ✗ | ✗ | ✗ | ✗ | ✗ |

**Summary**: 8 modal/drawer instances use accessible Radix primitives (✓ all 5 criteria). 18 instances use custom `<div>` overlays that fail all 5 focus-management criteria.

---

## Detailed Findings

### 1. CRITICAL Findings

#### 1.1 No Accessibility Statement Page

**Category**: Legal compliance risk  
**WCAG**: N/A (Israeli law requirement)  
**Legal**: Under Israeli Equal Rights for Persons with Disabilities Regulations (Amendment – Service Accessibility Adaptations), 2013, every website providing a public service must publish an accessibility statement (הצהרת נגישות). This statement must include: contact details for the accessibility coordinator, date of last audit, known limitations, and the standard to which the site conforms.

**Current state**: No route, page, or link for an accessibility statement exists anywhere in the application.

**Files**: `frontend/src/App.js` (routing)  
**Impact**: Legal non-compliance; lawsuit risk  
**Fix**: Create an `/accessibility` route with a dedicated `AccessibilityStatementPage` component. Link to it from the footer or login page. The statement must be in Hebrew.

---

#### 1.2 Custom Modals Lack Dialog Semantics, Focus Trap, and Escape Handling

**Category**: Legal compliance risk / Serious usability barrier  
**WCAG**: 1.3.1 (Info and Relationships), 2.1.1 (Keyboard), 2.4.3 (Focus Order), 4.1.2 (Name, Role, Value)

**Current state**: 18 custom modal/overlay instances are built as raw `<div>` elements with `onClick` backdrop dismiss. None have:
- `role="dialog"` or `aria-modal="true"`
- Focus trapping (focus can Tab behind the overlay)
- `Escape` key to close
- Focus restoration to the triggering element on close

See the **Keyboard / Focus Audit** table above for the full per-component breakdown.

**Note**: The application *does* have accessible Radix-based `Dialog`, `Sheet`, and `Drawer` components in `frontend/src/components/ui/`. 8 components correctly use these (FilterDrawer, UserDrawer, CameraModal, ExportModal, ProjectBillingEditModal). The problem is that the remaining 18 modal UIs bypass these accessible primitives.

**Impact**: Keyboard-only and screen-reader users cannot operate modals (trapped behind overlay, cannot close, cannot reach content)  
**Fix**: Migrate all custom modal/overlay patterns to use the existing Radix `Dialog`, `Sheet`, or `Drawer` components.

---

### 2. HIGH Findings

#### 2.1 No `<main>` Landmark — App Wrapper Is a Plain `<div>`

**Category**: Serious usability barrier  
**WCAG**: 1.3.1 (Info and Relationships), 2.4.1 (Bypass Blocks)

**Current state**: `App.js` wraps all content in `<div className="App">`. There is no `<main>` landmark on the majority of pages. Screen readers cannot identify the primary content region.

Some pages use `<header>` (good): `ContractorDashboard`, `ProjectControlPage`, `AdminUsersPage`, `MyProjectsPage`, `ProjectTasksPage`, `ProjectDashboardPage`, `AdminPage`. Very few pages use `<main>`. No page uses `<nav>`.

**Files**: `frontend/src/App.js`, all page-level components  
**Impact**: Screen reader users cannot navigate by landmark  
**Fix**: Add `<main id="main-content">` to the App shell or each page. Add `<nav>` to navigation sections.

---

#### 2.2 No Skip-to-Content Link

**Category**: Serious usability barrier  
**WCAG**: 2.4.1 (Bypass Blocks)

**Current state**: No skip-navigation link exists. Keyboard users must Tab through the entire header and navigation on every page before reaching content.

**Files**: `frontend/public/index.html`, `frontend/src/App.js`  
**Impact**: Keyboard users waste significant effort on every page navigation  
**Fix**: Add a visually-hidden skip link as the first focusable element: `<a href="#main-content" className="sr-only focus:not-sr-only ...">דלג לתוכן</a>`. Pair with `<main id="main-content">`.

---

#### 2.3 Interactive `<div>` Elements — Not Keyboard Accessible

**Category**: Serious usability barrier  
**WCAG**: 2.1.1 (Keyboard), 4.1.2 (Name, Role, Value)

**Current state**: Clickable elements implemented as `<div>` with `onClick` but no `role="button"`, `tabIndex="0"`, or `onKeyDown` handler. They are invisible to keyboard and screen-reader users.

**Examples**:
- `ContractorDashboard.js:384-397`: Completed task items (`<div onClick={...} className="... cursor-pointer">`) — clickable list items that are not keyboard focusable

**Impact**: Keyboard-only users cannot interact with these elements  
**Fix**: Convert to `<button>` or add `role="button"`, `tabIndex={0}`, and `onKeyDown` (Enter/Space).

---

#### 2.4 Icon-Only Buttons Missing Accessible Names

**Category**: Serious usability barrier  
**WCAG**: 4.1.2 (Name, Role, Value), 1.1.1 (Non-text Content)

**Current state**: Several icon-only buttons rely on `title` attribute (not announced by all screen readers) instead of `aria-label`, or have no accessible name at all.

| File | Line | Element | Issue |
|------|------|---------|-------|
| `ContractorDashboard.js` | 199 | Settings button | `title` only, no `aria-label` |
| `ContractorDashboard.js` | 202 | Logout button | `title` only, no `aria-label` |
| `NotificationBell.js` | bell button | Bell icon toggle | No `aria-label`, no expanded state |
| `ProjectControlPage.js` | FAB button | Floating action button | Needs `aria-label` and `aria-expanded` |

**Positive**: `BuildingQCPage.js` back buttons have `aria-label="חזרה"` ✓, `InnerBuildingPage.js` has good `aria-label` usage, `StageDetailPage.js` has extensive `aria-label` coverage.

**Impact**: Screen reader users hear no label for these buttons  
**Fix**: Replace `title` with `aria-label` on all icon-only buttons, or use both. Add `aria-expanded` to toggle buttons.

---

#### 2.5 Password Toggle Buttons Have `tabIndex={-1}`

**Category**: Serious usability barrier  
**WCAG**: 2.1.1 (Keyboard)

**Current state**: The show/hide password toggle buttons on `LoginPage.js:425`, `ResetPasswordPage.js:151,181`, and `AccountSettingsPage.js:26` use `tabIndex={-1}`, making them completely unreachable via keyboard.

**Impact**: Keyboard users cannot toggle password visibility  
**Fix**: Remove `tabIndex={-1}`. Add `aria-label` describing the action (e.g., "הצג סיסמה" / "הסתר סיסמה") and use `aria-pressed` to convey state.

---

#### 2.6 Tab Pattern Incomplete — Missing `aria-controls`

**Category**: Serious usability barrier  
**WCAG**: 4.1.2 (Name, Role, Value)

**Current state**: `LoginPage.js:278-289` has a manual tab implementation with `role="tablist"`, `role="tab"`, and `aria-selected`. However:
- Missing `aria-controls` linking each tab to its panel
- Missing `role="tabpanel"` on the content panels
- Missing `id` attributes for the linkage
- No arrow-key navigation between tabs

**Note**: The Radix `Tabs` component in `ui/tabs.jsx` handles all of this correctly. It is available but not used on the login page.

**Impact**: Screen reader users cannot understand tab-panel relationship  
**Fix**: Either migrate to the Radix `Tabs` component or add `aria-controls`, `role="tabpanel"`, and arrow-key support.

---

#### 2.7 `ProgressRing` SVG Has No ARIA Semantics

**Category**: Serious usability barrier  
**WCAG**: 1.1.1 (Non-text Content), 4.1.2 (Name, Role, Value)

**Current state**: The `ProgressRing` component in `ContractorDashboard.js:62-76` renders an SVG progress indicator with no `role`, `aria-label`, `aria-valuenow`, `aria-valuemin`, or `aria-valuemax`. Screen readers see nothing meaningful.

**Impact**: Screen reader users get no information about monthly progress  
**Fix**: Add `role="progressbar"`, `aria-valuenow={percentage}`, `aria-valuemin={0}`, `aria-valuemax={100}`, and `aria-label="התקדמות החודש"`.

---

#### 2.8 Progress Bars Missing ARIA Attributes

**Category**: Serious usability barrier  
**WCAG**: 4.1.2 (Name, Role, Value)

**Current state**: `BuildingQCPage.js:389-391` renders a floor-progress bar as plain `<div>` elements. No `role="progressbar"`, `aria-valuenow`, `aria-valuemin`, or `aria-valuemax`. Same pattern in `FloorDetailPage.js` summary card.

**Impact**: Screen reader users cannot perceive completion progress  
**Fix**: Add `role="progressbar"` with appropriate `aria-value*` attributes.

---

#### 2.9 Filter Buttons Missing `aria-pressed` / `aria-current`

**Category**: Serious usability barrier  
**WCAG**: 4.1.2 (Name, Role, Value)

**Current state**: Toggle/filter button groups in `ContractorDashboard.js:232-253` (project selector) and `BuildingQCPage.js:319-335` (status filter) visually indicate the selected state via CSS but do not communicate it to assistive technology.

**Impact**: Screen reader users cannot tell which filter is active  
**Fix**: Add `aria-pressed="true"` or `aria-current="true"` to the active button in each filter group.

---

#### 2.10 Form Labels Not Programmatically Associated

**Category**: Serious usability barrier  
**WCAG**: 1.3.1 (Info and Relationships), 3.3.2 (Labels or Instructions)

**Current state**: Multiple `<label>` elements across pages precede inputs without `htmlFor`/`id` association:
- `RegisterPage.js:152, 181` — registration form input labels
- `UnitDetailPage.js:211, 229` — status and category labels
- `OwnershipTransferPage.js:151, 355` — input labels
- `InnerBuildingPage.js:357, 369` — floor name/unit count labels
- Various plan pages (`UnitPlansPage.js`, `ProjectPlansPage.js`)

**Impact**: Screen readers and voice-control users cannot identify which label belongs to which input  
**Fix**: Add matching `htmlFor` on `<label>` and `id` on `<input>`, or ensure `<label>` wraps its `<input>` child.

---

### 3. MEDIUM Findings

#### 3.1 Very Small Text Below Minimum Size

**Category**: Improvement / hardening  
**WCAG**: 1.4.4 (Resize Text) — advisory concern

**Current state**: 212 instances of `text-[10px]` or `text-[11px]` across page files. At 10px, text is extremely small on mobile and difficult to read for low-vision users. While WCAG does not specify a minimum font size, SI 5568 practice recommends a minimum of 12px for body text.

**Examples**: Status badges, timestamps, stat labels throughout `ContractorDashboard.js`, `BuildingQCPage.js`, `ProjectControlPage.js`, `TaskDetailPage.js`.

**Impact**: Difficult to read for low-vision users, especially on small mobile screens  
**Fix**: Increase minimum text size to 12px (0.75rem).

---

#### 3.2 No Live Regions for Dynamic Content Updates

**Category**: Serious usability barrier  
**WCAG**: 4.1.3 (Status Messages)

**Current state**: Only one `role="alert"` exists (in `ui/alert.jsx`). Loading states, toast notifications (Sonner), and dynamic data updates are not announced to screen readers. The `sonner` toast library has partial screen reader support, but explicit `aria-live` regions for key status changes (e.g., "טוען נתונים...", task count changes) are absent.

**Impact**: Screen reader users miss important status updates  
**Fix**: Add `aria-live="polite"` regions for loading indicators and dynamic status updates. Verify Sonner toast accessibility configuration.

---

#### 3.3 `<noscript>` Text in English

**Category**: Improvement / hardening  
**WCAG**: 3.1.2 (Language of Parts)

**Current state**: `index.html` contains `<noscript>You need to enable JavaScript to run this app.</noscript>` in English, while the page language is Hebrew.

**Impact**: Hebrew-speaking users with JS disabled see English text  
**Fix**: Translate to Hebrew: `<noscript>יש להפעיל JavaScript כדי להשתמש באפליקציה זו.</noscript>`.

---

#### 3.4 Image Lightbox Not Keyboard Accessible

**Category**: Serious usability barrier  
**WCAG**: 2.1.1 (Keyboard), 1.1.1 (Non-text Content)

**Current state**: `TaskDetailPage.js:1461` renders a full-screen image lightbox as a `<div onClick>` overlay. The enlarged image (`alt=""`) has no descriptive alt text and no Escape key handler. While a close mechanism exists via backdrop click, there is no keyboard-accessible close button and no `role="dialog"` semantics.

**Impact**: Keyboard users cannot close the lightbox; screen reader users get no image description  
**Fix**: Add a visible close button with `aria-label`, Escape key to close, descriptive alt text on the image, and `role="dialog"` on the container.

---

#### 3.5 NotificationBell Panel Not Accessible

**Category**: Serious usability barrier  
**WCAG**: 4.1.2 (Name, Role, Value), 2.1.1 (Keyboard)

**Current state**: The notification panel in `NotificationBell.js` opens as a floating `<div>` positioned absolutely. It has no `role`, no `aria-expanded` on the trigger button, no focus management, and dismisses only via click-outside (no Escape key).

**Impact**: Keyboard/SR users cannot operate notifications  
**Fix**: Add `aria-haspopup="true"` and `aria-expanded` to the bell button. Add `role="region"` or `role="dialog"` to the panel. Handle Escape key. Manage focus on open/close.

---

#### 3.6 Heading Hierarchy Inconsistencies

**Category**: Improvement / hardening  
**WCAG**: 1.3.1 (Info and Relationships) — advisory

**Current state**: Several pages skip heading levels:
- `ContractorDashboard.js`: `<h1>` (user name, line 192), then `<h3>` (line 279), then `<h2>` (line 300) — mixed/skipped levels
- `BuildingQCPage.js`: `<h1>` (line 284), then no `<h2>`
- `UnitHomePage.js`: `<h1>`, `<h2>`, `<h3>` — correct ✓

**Note**: Heading level skips are not strictly a conformance failure under WCAG 2.1 but are a best-practice recommendation that significantly helps screen reader navigation.

**Impact**: Screen reader landmark navigation is less useful  
**Fix**: Ensure a logical descending hierarchy: `h1` → `h2` → `h3` on every page.

---

### 4. LOW Findings

#### 4.1 Focus Styles Suppressed Then Restored — Inconsistent Pattern

**Category**: Improvement / hardening  
**WCAG**: 2.4.7 (Focus Visible)

**Current state**: Input fields use `focus:outline-none focus:ring-2 focus:ring-amber-500/50` — the native outline is removed and replaced with a custom ring. The ring uses 50% opacity (`ring-amber-500/50`), which may have insufficient contrast against white backgrounds.

Most buttons and interactive elements in page files have no explicit focus style, relying on browser defaults (which Tailwind's preflight may reset).

**Impact**: Focus indicator may not be visible enough for low-vision keyboard users  
**Fix**: Ensure all interactive elements have a visible focus indicator. Consider using `focus-visible:ring-2 focus-visible:ring-amber-500` (full opacity).

---

#### 4.2 Color-Only Status Indication

**Category**: Improvement / hardening  
**WCAG**: 1.4.1 (Use of Color)

**Current state**: Status badges and priority indicators use color as the primary differentiator. Most also include text labels (good), but some progress bars (`BuildingQCPage.js:390`) and priority borders (`ContractorDashboard.js:25`) rely solely on color.

**Impact**: Color-blind users may miss status information  
**Fix**: Ensure all status communications include text or iconographic alternatives alongside color. Progress bars should have text labels.

---

#### 4.3 Touch Target Size (Advisory — Beyond WCAG 2.1 Baseline)

**Category**: Improvement / hardening  
**WCAG**: 2.5.8 (Target Size — Minimum). Note: this criterion is from WCAG 2.2, not 2.1. Included as advisory.

**Current state**: Most primary action buttons are well-sized. However, some interactive elements are small:
- Filter option buttons at `text-xs` with small padding
- Icon buttons at `p-2` (32×32px) — close to minimum but below the 44×44px recommended for mobile

**Impact**: Users with motor impairments may have difficulty tapping small targets  
**Fix**: Ensure all touch targets are at least 44×44px on mobile views, or 24×24px minimum with 24px spacing.

---

#### 4.4 Viewport Meta Does Not Restrict Zoom (Positive Finding)

**Category**: N/A (positive)  
**WCAG**: 1.4.4 (Resize Text)

**Current state**: `<meta name="viewport" content="width=device-width, initial-scale=1" />` — does NOT set `maximum-scale=1` or `user-scalable=no`. This correctly allows users to zoom. ✓

---

## Positive Findings (What's Working Well)

| Area | Details |
|------|---------|
| **RTL/Language** | `<html lang="he" dir="rtl">` set correctly; per-component `dir="rtl"` on modal content |
| **Radix Primitives** | `Dialog`, `Sheet`, `Drawer`, `Select`, `Tabs` components in `ui/` are fully accessible (focus trap, Escape, ARIA roles). Used correctly in `FilterDrawer`, `UserDrawer`, `CameraModal`, `ExportModal`, `ProjectBillingEditModal` |
| **Form Validation** | `ui/form.jsx` uses `aria-describedby` and `aria-invalid` for error association |
| **Breadcrumbs** | `ui/breadcrumb.jsx` has `aria-label="breadcrumb"`, `aria-current="page"`, `role="presentation"` on separators |
| **Back Buttons** | `BuildingQCPage`, `InnerBuildingPage` back buttons have `aria-label="חזרה"` |
| **Carousel** | `ui/carousel.jsx` has `role="region"`, `aria-roledescription="carousel"`, keyboard navigation |
| **Alert** | `ui/alert.jsx` uses `role="alert"` |
| **Zoom Not Blocked** | Viewport meta allows user zoom |
| **StageDetailPage ARIA** | Good `aria-label` coverage on action buttons (save, submit, approve, reject, reopen) |
| **InnerBuildingPage ARIA** | Uses `aria-expanded`, `aria-label` on floor toggles and add buttons |
| **ProjectControlPage** | `aria-expanded` on building toggles, `aria-label` on carousel dots |

---

## Action Plan

### Tier 1: Must-Fix for Legal Compliance (Before Launch)

1. **Create accessibility statement page** — Add `/accessibility` route with Hebrew הצהרת נגישות, accessibility coordinator contact info, audit date, known limitations, and SI 5568 reference. Link from login page footer.
2. **Migrate custom modals to Radix primitives** — Replace all 18 custom `<div>` modal overlays with existing Radix `Dialog`, `Sheet`, or `Drawer` components. This provides focus trap, Escape key, `aria-modal`, and focus restoration automatically.
3. **Add `<main>` landmark and skip-to-content link** — Wrap app content in `<main id="main-content">` and add `<a href="#main-content" class="sr-only focus:not-sr-only">דלג לתוכן</a>` as first focusable element.

### Tier 2: Should-Fix for Usability (Before or Shortly After Launch)

4. Fix password toggle `tabIndex={-1}` → remove it; add `aria-label`
5. Replace `title` with `aria-label` on all icon-only buttons
6. Convert clickable `<div>` elements to `<button>` or add proper ARIA
7. Complete login page tab pattern (`aria-controls`, `role="tabpanel"`) or use Radix Tabs
8. Add `role="progressbar"` + `aria-value*` to ProgressRing and all progress bars
9. Add `aria-pressed` to filter/toggle button groups
10. Associate all form `<label>` elements with `htmlFor`/`id`
11. Add `aria-live="polite"` regions for loading states and status updates
12. Add keyboard support to NotificationBell panel

### Tier 3: Can Improve Later

13. Increase minimum text size from 10px to 12px
14. Fix heading hierarchy across pages
15. Translate `<noscript>` text to Hebrew
16. Improve focus indicator contrast (remove 50% opacity)
17. Add text alternatives alongside color-only progress/status indicators
18. Increase touch target sizes to 44×44px minimum

---

## What Was NOT Tested

| Area | Reason |
|------|--------|
| **Color contrast ratios** | Requires automated measurement tools (axe, Lighthouse, WAVE). Cannot be determined from code inspection alone. |
| **Real screen reader behavior** | No testing with NVDA, JAWS, or VoiceOver was performed. Findings are based on code analysis of ARIA attributes and semantic HTML. |
| **Real keyboard navigation flow** | Tab order was inferred from DOM order and `tabIndex` attributes, not tested in a live browser session. |
| **Responsive layout at zoom levels** | 200% and 400% zoom rendering was not visually tested. |
| **Animation/motion sensitivity** | `prefers-reduced-motion` media query usage was not audited. |
| **PDF/document accessibility** | Any downloadable documents or exports were not checked for accessibility. |
| **Backend error messages** | Localization and screen-reader-friendliness of API error responses were not audited. |
| **Excluded files** | `AdminBillingPage.js`, `AdminOrgsPage.js`, `OrgBillingPage.js`, `admin_router.py`, `billing_plans.py` were excluded per project constraints. They likely share the same patterns documented above. |
| **Third-party library internals** | Radix UI, Sonner, and Vaul were checked at the wrapper level only; internal accessibility was assumed correct per their documentation. |

---

## Testing Recommendations for Follow-Up

1. **Automated**: Run `axe-core` or `pa11y` against all routes after fixing Tier 1 items
2. **Manual keyboard test**: Tab through every page; verify all interactive elements are reachable and operable
3. **Screen reader test**: Test with NVDA (Windows) and VoiceOver (macOS/iOS) in Hebrew mode
4. **Zoom test**: Verify usability at 200% and 400% zoom
5. **Color contrast audit**: Run automated contrast checker on all color combinations (especially the small `text-[10px]` badges)
6. **Legal review**: Have accessibility statement reviewed by a legal professional familiar with Israeli disability regulations
