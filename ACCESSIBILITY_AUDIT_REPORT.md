# BrikOps Accessibility Audit Report

**Standard**: Israeli Standard 5568 (SI 5568) — based on WCAG 2.1 Level AA  
**Date**: 2026-03-14  
**Scope**: Full-stack application (React SPA + FastAPI backend)  
**Auditor**: Automated code-level review (no assistive-technology user testing)

---

## Executive Summary

BrikOps is a Hebrew RTL construction-management SPA. The app has a solid foundation — correct `lang="he" dir="rtl"` on `<html>`, Radix-based accessible primitives for Dialog/Sheet/Select/Tabs, and some `aria-label` usage on key buttons. However, several **critical and high-severity gaps** exist that would fail an SI 5568 / WCAG 2.1 AA compliance audit.

**Finding counts by severity**:

| Severity | Count |
|----------|-------|
| Critical | 2 |
| High     | 10 |
| Medium   | 6 |
| Low      | 4 |
| **Total** | **22** |

---

## 1. CRITICAL Findings

### 1.1 No Accessibility Statement Page

**WCAG**: N/A (Israeli law requirement)  
**Legal**: Under Israeli Equal Rights for Persons with Disabilities Regulations (Amendment – Service Accessibility Adaptations), 2013, every website providing a public service must publish an accessibility statement (הצהרת נגישות). This statement must include: contact details for the accessibility coordinator, date of last audit, known limitations, and the standard to which the site conforms.

**Current state**: No route, page, or link for an accessibility statement exists anywhere in the application.

**Files**: `frontend/src/App.js` (routing), all page files  
**Remediation**: Create an `/accessibility` route with a dedicated `AccessibilityStatementPage` component. Link to it from the footer or login page. The statement must be in Hebrew.

---

### 1.2 Custom Modals Lack Dialog Semantics, Focus Trap, and Escape Handling

**WCAG**: 1.3.1 (Info and Relationships), 2.1.1 (Keyboard), 2.4.3 (Focus Order), 4.1.2 (Name, Role, Value)

**Current state**: The application has ~15+ custom modal/overlay patterns built as raw `<div>` elements with `onClick` backdrop dismiss. None of these have:
- `role="dialog"` or `aria-modal="true"`
- Focus trapping (focus can Tab behind the overlay)
- `Escape` key to close
- Focus restoration to the triggering element on close

**Affected files** (non-exhaustive):
| File | Lines | Pattern |
|------|-------|---------|
| `ProjectControlPage.js` | 81, 106, 1974, 2011 | Confirmation modals, step-up auth |
| `TaskDetailPage.js` | 1420, 1461 | Trade-mismatch modal, image lightbox |
| `StageDetailPage.js` | 1886, 1927 | Reject/reopen modals |
| `AdminUsersPage.js` | 654, 659, 710, 759 | User detail drawer, role-edit, phone/password modals |
| `ManagementPanel.js` | 36, 115, 250, 310 | Bottom sheets |
| `WhatsAppRejectionModal.js` | 82 | Rejection modal |
| `QCApproversTab.js` | 253 | Approver modal |
| `NewDefectModal.js` | 41 | New defect bottom sheet |
| `PaywallModal.js` | ~line 85 | Paywall overlay |

**Note**: The application *does* have accessible Radix-based `Dialog`, `Sheet`, and `Drawer` components in `frontend/src/components/ui/`. The `FilterDrawer` and `UserDrawer` correctly use these. The problem is that most modal UIs bypass these accessible primitives and use raw `<div>` overlays instead.

**Remediation**: Migrate all custom modal/overlay patterns to use the existing Radix `Dialog`, `Sheet`, or `Drawer` components, or at minimum add `role="dialog"`, `aria-modal="true"`, focus trap, Escape key handling, and focus restoration.

---

## 2. HIGH Findings

### 2.1 No `<main>` Landmark — App Wrapper Is a Plain `<div>`

**WCAG**: 1.3.1 (Info and Relationships), 2.4.1 (Bypass Blocks)

**Current state**: `App.js` wraps all content in `<div className="App">`. There is no `<main>` landmark on the majority of pages. Screen readers cannot identify the primary content region.

Some pages use `<header>` (good): `ContractorDashboard`, `ProjectControlPage`, `AdminUsersPage`, `MyProjectsPage`, `ProjectTasksPage`, `ProjectDashboardPage`, `AdminPage`. Very few pages use `<main>`. No page uses `<nav>`.

**Files**: `frontend/src/App.js`, all page-level components  
**Remediation**: Add `<main id="main-content">` to the App shell or each page. Add `<nav>` to navigation sections.

---

### 2.2 No Skip-to-Content Link

**WCAG**: 2.4.1 (Bypass Blocks)

**Current state**: No skip-navigation link exists. Keyboard users must Tab through the entire header and navigation on every page before reaching content.

**Files**: `frontend/public/index.html`, `frontend/src/App.js`  
**Remediation**: Add a visually-hidden skip link as the first focusable element: `<a href="#main-content" className="sr-only focus:not-sr-only ...">דלג לתוכן</a>`. Pair with `<main id="main-content">`.

---

### 2.3 Interactive `<div>` Elements — Not Keyboard Accessible

**WCAG**: 2.1.1 (Keyboard), 4.1.2 (Name, Role, Value)

**Current state**: Multiple clickable elements are `<div>` with `onClick` but no `role="button"`, `tabIndex="0"`, or `onKeyDown` handler. They are invisible to keyboard and screen-reader users.

**Examples**:
- `ContractorDashboard.js:384-397`: Completed task items (`<div onClick={...} className="... cursor-pointer">`) — clickable list items that are not keyboard focusable

**Remediation**: Convert to `<button>` or add `role="button"`, `tabIndex={0}`, and `onKeyDown` (Enter/Space).

---

### 2.4 Icon-Only Buttons Missing Accessible Names

**WCAG**: 4.1.2 (Name, Role, Value), 1.1.1 (Non-text Content)

**Current state**: Several icon-only buttons rely on `title` attribute (not announced by all screen readers) instead of `aria-label`, or have no accessible name at all.

**Examples**:
| File | Line | Element | Issue |
|------|------|---------|-------|
| `ContractorDashboard.js` | 199 | Settings button | `title` only, no `aria-label` |
| `ContractorDashboard.js` | 202 | Logout button | `title` only, no `aria-label` |
| `NotificationBell.js` | ~bell button | Bell icon toggle | No `aria-label`, no expanded state |
| `ProjectControlPage.js` | FAB button | Floating action button | Needs `aria-label` and `aria-expanded` |

**Positive**: `BuildingQCPage.js` back buttons have `aria-label="חזרה"` ✓, `InnerBuildingPage.js` has good `aria-label` usage, `StageDetailPage.js` has extensive `aria-label` coverage.

**Remediation**: Replace `title` with `aria-label` on all icon-only buttons, or use both. Add `aria-expanded` to toggle buttons.

---

### 2.5 Password Toggle Buttons Have `tabIndex={-1}`

**WCAG**: 2.1.1 (Keyboard)

**Current state**: The show/hide password toggle buttons on `LoginPage.js:425`, `ResetPasswordPage.js:151,181`, and `AccountSettingsPage.js:26` use `tabIndex={-1}`, making them completely unreachable via keyboard.

**Remediation**: Remove `tabIndex={-1}`. Add `aria-label` describing the action (e.g., "הצג סיסמה" / "הסתר סיסמה") and use `aria-pressed` to convey state.

---

### 2.6 Tab Pattern Incomplete — Missing `aria-controls`

**WCAG**: 4.1.2 (Name, Role, Value)

**Current state**: `LoginPage.js:278-289` has a manual tab implementation with `role="tablist"`, `role="tab"`, and `aria-selected`. However:
- Missing `aria-controls` linking each tab to its panel
- Missing `role="tabpanel"` on the content panels
- Missing `id` attributes for the linkage
- No arrow-key navigation between tabs (WCAG pattern recommendation)

**Note**: The Radix `Tabs` component in `ui/tabs.jsx` handles all of this correctly. It is available but not used on the login page.

**Remediation**: Either migrate to the Radix `Tabs` component or add `aria-controls`, `role="tabpanel"`, and arrow-key support.

---

### 2.7 `ProgressRing` SVG Has No ARIA Semantics

**WCAG**: 1.1.1 (Non-text Content), 4.1.2 (Name, Role, Value)

**Current state**: The `ProgressRing` component in `ContractorDashboard.js:62-76` renders an SVG progress indicator with no `role`, `aria-label`, `aria-valuenow`, `aria-valuemin`, or `aria-valuemax`. Screen readers see nothing meaningful.

**Remediation**: Add `role="progressbar"`, `aria-valuenow={percentage}`, `aria-valuemin={0}`, `aria-valuemax={100}`, and `aria-label="התקדמות החודש"`.

---

### 2.8 Progress Bars Missing ARIA Attributes

**WCAG**: 4.1.2 (Name, Role, Value)

**Current state**: `BuildingQCPage.js:389-391` renders a floor-progress bar as plain `<div>` elements. No `role="progressbar"`, `aria-valuenow`, `aria-valuemin`, or `aria-valuemax`.

**Remediation**: Add `role="progressbar"` with appropriate `aria-value*` attributes.

---

### 2.9 Filter Buttons Missing `aria-pressed` / `aria-current`

**WCAG**: 4.1.2 (Name, Role, Value)

**Current state**: Toggle/filter button groups in `ContractorDashboard.js:232-253` (project selector) and `BuildingQCPage.js:319-335` (status filter) visually indicate the selected state via CSS but do not communicate it to assistive technology.

**Remediation**: Add `aria-pressed="true"` or `aria-current="true"` to the active button in each filter group.

---

### 2.10 Form Labels Not Programmatically Associated

**WCAG**: 1.3.1 (Info and Relationships), 3.3.2 (Labels or Instructions)

**Current state**: Multiple `<label>` elements across pages wrap or precede inputs without `htmlFor`/`id` association:
- `RegisterPage.js:152, 181` — registration form input labels
- `UnitDetailPage.js:211, 229` — status and category labels
- `OwnershipTransferPage.js:151, 355` — input labels
- `InnerBuildingPage.js:357, 369` — floor name/unit count labels
- Various plan pages and billing pages

**Remediation**: Add matching `htmlFor` on `<label>` and `id` on `<input>`, or ensure `<label>` wraps its `<input>` child.

---

## 3. MEDIUM Findings

### 3.1 Very Small Text Below Minimum Size

**WCAG**: 1.4.4 (Resize Text) — advisory concern

**Current state**: 212 instances of `text-[10px]` or `text-[11px]` across page files. At 10px, text is extremely small on mobile and difficult to read for low-vision users. While WCAG does not specify a minimum font size, SI 5568 practice recommends a minimum of 12px for body text.

**Examples**: Status badges, timestamps, stat labels throughout `ContractorDashboard.js`, `BuildingQCPage.js`, `ProjectControlPage.js`, `TaskDetailPage.js`.

**Remediation**: Increase minimum text size to 12px (0.75rem). For decorative counters, ensure parent container is large enough to read at 200% zoom.

---

### 3.2 No Live Regions for Dynamic Content Updates

**WCAG**: 4.1.3 (Status Messages)

**Current state**: Only one `role="alert"` exists (in `ui/alert.jsx`). Loading states, toast notifications (Sonner), and dynamic data updates are not announced to screen readers. The `sonner` toast library has partial screen reader support, but explicit `aria-live` regions for key status changes (e.g., "טוען נתונים...", task count changes) are absent.

**Remediation**: Add `aria-live="polite"` regions for loading indicators and dynamic status updates. Verify Sonner toast accessibility configuration.

---

### 3.3 `<noscript>` Text in English

**WCAG**: 3.1.2 (Language of Parts)

**Current state**: `index.html` contains `<noscript>You need to enable JavaScript to run this app.</noscript>` in English, while the page language is Hebrew.

**Remediation**: Translate to Hebrew: `<noscript>יש להפעיל JavaScript כדי להשתמש באפליקציה זו.</noscript>`.

---

### 3.4 Image Lightbox Not Keyboard Accessible

**WCAG**: 2.1.1 (Keyboard), 1.1.1 (Non-text Content)

**Current state**: `TaskDetailPage.js:1461` renders a full-screen image lightbox as a `<div onClick>` overlay. The enlarged image (`alt=""`) has no descriptive alt text and no Escape key handler. While a close mechanism exists via backdrop click, there is no keyboard-accessible close button and no `role="dialog"` semantics.

**Remediation**: Add a visible close button with `aria-label`, Escape key to close, descriptive alt text on the image, and `role="dialog"` on the container.

---

### 3.5 NotificationBell Panel Not Accessible

**WCAG**: 4.1.2 (Name, Role, Value), 2.1.1 (Keyboard)

**Current state**: The notification panel in `NotificationBell.js` opens as a floating `<div>` positioned absolutely. It has no `role`, no `aria-expanded` on the trigger button, no focus management, and dismisses only via click-outside (no Escape key).

**Remediation**: Add `aria-haspopup="true"` and `aria-expanded` to the bell button. Add `role="region"` or `role="dialog"` to the panel. Handle Escape key. Manage focus on open/close.

---

### 3.6 Heading Hierarchy Inconsistencies

**WCAG**: 1.3.1 (Info and Relationships)

**Current state**: Several pages skip heading levels:
- `ContractorDashboard.js`: `<h1>` (user name, line 192), then `<h3>` (line 279), then `<h2>` (line 300) — mixed/skipped levels
- `BuildingQCPage.js`: `<h1>` (line 284), then no `<h2>`
- `UnitHomePage.js`: `<h1>`, `<h2>`, `<h3>` — correct ✓

**Remediation**: Ensure a logical descending hierarchy: `h1` → `h2` → `h3` on every page.

---

## 4. LOW Findings

### 4.1 Focus Styles Suppressed Then Restored — Inconsistent Pattern

**WCAG**: 2.4.7 (Focus Visible)

**Current state**: Input fields use `focus:outline-none focus:ring-2 focus:ring-amber-500/50` — the native outline is removed and replaced with a custom ring. This is acceptable when the replacement ring provides sufficient contrast. However, the ring uses 50% opacity (`ring-amber-500/50`), which may fail the 3:1 contrast ratio for focus indicators against white backgrounds (WCAG 2.2 enhanced, but good practice under AA).

Most buttons and interactive elements in page files have no explicit focus style, relying on browser defaults (which Tailwind's preflight may reset).

**Remediation**: Ensure all interactive elements have a visible focus indicator with at least 3:1 contrast ratio. Consider using `focus-visible:ring-2 focus-visible:ring-amber-500` (full opacity).

---

### 4.2 Color-Only Status Indication

**WCAG**: 1.4.1 (Use of Color)

**Current state**: Status badges and priority indicators use color as the primary differentiator. Most also include text labels (good), but some progress bars (`BuildingQCPage.js:390`) and priority borders (`ContractorDashboard.js:25`) rely solely on color.

**Remediation**: Ensure all status communications include text or iconographic alternatives alongside color. Progress bars should have text labels.

---

### 4.3 Touch Target Size (Advisory — WCAG 2.2)

**WCAG**: 2.5.8 (Target Size — Minimum). Note: this success criterion is from WCAG 2.2, not 2.1. It is included here as an advisory best practice.

**Current state**: Most primary action buttons are well-sized. However, some interactive elements are small:
- Filter option buttons at `text-xs` with small padding
- Icon buttons at `p-2` (32×32px) — close to the 24×24px minimum but below the 44×44px recommended by Apple HIG / Material Design for mobile

**Remediation**: Ensure all touch targets are at least 44×44px on mobile views, or 24×24px minimum with 24px spacing.

---

### 4.4 Viewport Meta Does Not Restrict Zoom (Positive Finding)

**WCAG**: 1.4.4 (Resize Text)

**Current state**: `<meta name="viewport" content="width=device-width, initial-scale=1" />` — does NOT set `maximum-scale=1` or `user-scalable=no`. This correctly allows users to zoom. ✓

---

## 5. Positive Findings (What's Working Well)

| Area | Details |
|------|---------|
| **RTL/Language** | `<html lang="he" dir="rtl">` set correctly; per-component `dir="rtl"` on modal content |
| **Radix Primitives** | `Dialog`, `Sheet`, `Drawer`, `Select`, `Tabs` components in `ui/` are fully accessible (focus trap, Escape, ARIA roles). Used correctly in `FilterDrawer`, `UserDrawer` |
| **Form Validation** | `ui/form.jsx` uses `aria-describedby` and `aria-invalid` for error association |
| **Breadcrumbs** | `ui/breadcrumb.jsx` has `aria-label="breadcrumb"`, `aria-current="page"`, `role="presentation"` on separators |
| **Back Buttons** | `BuildingQCPage`, `InnerBuildingPage` back buttons have `aria-label="חזרה"` |
| **Carousel** | `ui/carousel.jsx` has `role="region"`, `aria-roledescription="carousel"`, keyboard navigation |
| **Alert** | `ui/alert.jsx` uses `role="alert"` |
| **Zoom Not Blocked** | Viewport meta allows user zoom |
| **Some ARIA Attributes** | `StageDetailPage` has good `aria-label` coverage on action buttons; `InnerBuildingPage` uses `aria-expanded`, `aria-label`; `ProjectControlPage` uses `aria-expanded` on building toggles |

---

## 6. Remediation Priority Matrix

| Priority | Finding | Effort | Impact |
|----------|---------|--------|--------|
| P0 | 1.1 Accessibility Statement | Low | Legal compliance |
| P0 | 1.2 Modal dialog semantics | High | Keyboard/SR users blocked |
| P1 | 2.1 `<main>` landmark | Low | SR navigation |
| P1 | 2.2 Skip-to-content | Low | Keyboard navigation |
| P1 | 2.3 Interactive divs → buttons | Medium | Keyboard access |
| P1 | 2.4 Icon button labels | Low | SR users |
| P1 | 2.5 Password toggle tabIndex | Low | Keyboard access |
| P1 | 2.6 Tab pattern completion | Low | SR users |
| P1 | 2.7 ProgressRing ARIA | Low | SR users |
| P1 | 2.8 Progress bar ARIA | Low | SR users |
| P1 | 2.9 Filter `aria-pressed` | Low | SR users |
| P1 | 2.10 Label-input association | Medium | SR/voice users |
| P2 | 3.1 Small text sizes | Medium | Low vision |
| P2 | 3.2 Live regions | Medium | SR users |
| P2 | 3.3 Noscript Hebrew | Low | Edge case |
| P2 | 3.4 Image lightbox a11y | Low | Keyboard/SR |
| P2 | 3.5 NotificationBell a11y | Medium | Keyboard/SR |
| P2 | 3.6 Heading hierarchy | Low | SR navigation |
| P3 | 4.1 Focus style consistency | Medium | Keyboard users |
| P3 | 4.2 Color-only indicators | Low | Color-blind users |
| P3 | 4.3 Touch target sizes | Low | Motor impairment |

---

## 7. Testing Recommendations

1. **Automated**: Run `axe-core` or `pa11y` against all routes after fixing P0/P1 items
2. **Manual keyboard test**: Tab through every page; verify all interactive elements are reachable and operable
3. **Screen reader test**: Test with NVDA (Windows) and VoiceOver (macOS/iOS) in Hebrew mode
4. **Zoom test**: Verify usability at 200% and 400% zoom
5. **Color contrast audit**: Run automated contrast checker on all color combinations (especially the small `text-[10px]` badges)

---

## 8. Scope Notes

- This audit covers application-level code only (React frontend).
- Third-party dependencies (Radix UI, Sonner, Vaul) were checked at the component wrapper level.
- The following files were **excluded per project constraints** and not deeply audited for remediation: `AdminBillingPage.js`, `AdminOrgsPage.js`, `OrgBillingPage.js`, `admin_router.py`, `billing_plans.py`. These files likely share the same patterns (custom modals, missing ARIA) found elsewhere.
- No assistive-technology user testing was performed; findings are based on code inspection.
- Backend API accessibility (error message localization, content-type headers) was not in scope.
