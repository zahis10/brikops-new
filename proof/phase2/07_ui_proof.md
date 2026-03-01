# Section 7: UI Proof

## 7.1 Authenticated Screenshot Evidence

All screenshots taken via automated Playwright browser sessions with real demo login credentials.

### Screenshot 1: PM Project Billing Tab (Flag ON) + Warning Badge

- **Login**: מנהל פרויקט (pm@contractor-ops.com) via demo quick-login
- **URL**: `/projects/c3e18b07-a7d8-411e-80f9-95028b15788a/control?tab=billing`
- **Observed**:
  - "חיוב" tab visible in the top-level tab bar (same level as structure/tasks tabs)
  - "חיוב פרויקט" heading displayed inside the ProjectBillingCard
  - Warning badge "חריגה מהיחידות החוזיות (לבדיקה)" visible — triggered by observed_units(102) > contracted_units(50)
  - Hebrew labels throughout: status badges, tier labels, fee amounts with ₪ prefix
  - No raw English billing terms visible
- **Verdict**: PASS — billing tab renders correctly with Hebrew labels and warning badge

### Screenshot 2: OrgBillingPage (Flag ON)

- **Login**: מנהל פרויקט (pm@contractor-ops.com, org owner) via demo quick-login
- **URL**: `/billing/org/69357d4b-547d-4b53-988e-b28880e6f767`
- **Observed**:
  - "חיוב ארגון" heading displayed
  - Project billing rows visible with status, tier, and fee information
  - Subscription total (סה"כ חודשי) displayed
  - Billing role members section ("בעלי הרשאות חיוב") visible
  - All labels in Hebrew
- **Verdict**: PASS — org billing page renders correctly with Hebrew labels

### Screenshot 3: AdminBillingPage — Organizations (Flag ON)

- **Login**: Super Admin via demo quick-login
- **URL**: `/admin/billing`
- **Observed**:
  - "ניהול חיוב ומנויים" heading displayed
  - Organizations list ("ארגונים") with org names, project counts, and billing status
  - Hebrew labels used throughout
- **Verdict**: PASS — admin billing page renders organization overview in Hebrew

### Screenshot 4: AdminBillingPage — Plans Section Expanded (Flag ON)

- **Login**: Super Admin via demo quick-login
- **URL**: `/admin/billing` → clicked "תוכניות תמחור (Billing v1)" to expand
- **Observed**:
  - Plan cards visible: plan_basic, plan_pro, plan_xl
  - Pricing displayed: ₪1,200 / ₪2,000 / ₪3,500
  - Tier information visible for each plan (tier_s, tier_m, tier_l, tier_xl)
  - Version v2 displayed
  - XL plan with tier_xl (501+ יחידות) at ₪8,500 confirmed
- **Verdict**: PASS — all 3 plans with XL pricing and version v2 visible

### Screenshot 5: חיוב Tab Placement Proof

- **Login**: מנהל פרויקט via demo quick-login
- **URL**: `/projects/c3e18b07-a7d8-411e-80f9-95028b15788a/control`
- **Observed**:
  - Tab bar visible at top of project control page
  - "חיוב" is a **top-level tab** in the tab bar (alongside structure, tasks, etc.)
  - It is NOT nested under QC approvers or any other section
  - Tab uses CreditCard icon as defined in `BILLING_TAB = { id: 'billing', label: 'חיוב', icon: CreditCard }`
- **Verdict**: PASS — billing tab is a standalone top-level tab, not under QC

## 7.2 billingLabels.js — Single Source of Truth

All billing UI components import label functions from `frontend/src/utils/billingLabels.js`.

### Import Evidence

| Component | File | Imports |
|-----------|------|---------|
| ProjectBillingCard | `frontend/src/components/ProjectBillingCard.js` | getBillingStatusLabel, getBillingStatusColor, getSetupStateLabel, getSetupStateColor, getTierLabel, formatCurrency, getObservedUnitsWarning |
| OrgBillingPage | `frontend/src/pages/OrgBillingPage.js` | getBillingStatusLabel, getBillingStatusColor, getSetupStateLabel, getSetupStateColor, getTierLabel, formatCurrency, getObservedUnitsWarning |
| AdminBillingPage | `frontend/src/pages/AdminBillingPage.js` | getBillingStatusLabel, getBillingStatusColor, getSetupStateLabel, getSetupStateColor, getTierLabel, formatCurrency, getObservedUnitsWarning |

### Hebrew Label Coverage

| Dictionary | Keys | Values (Hebrew) |
|-----------|------|-----------------|
| BILLING_STATUS_LABELS | trialing, active, past_due, suspended, canceled, **paused**, **archived** | ניסיון, פעיל, חוב פתוח, מושעה, בוטל, **מושהה**, **בארכיון** |
| ACCESS_LABELS | full_access, read_only | גישה מלאה, קריאה בלבד |
| SETUP_STATE_LABELS | trial, pending_handoff, pending_billing_setup, ready, active | ניסיון, ממתין להעברה, ממתין להגדרת חיוב, מוכן, פעיל |
| TIER_LABELS | tier_s, tier_m, tier_l, **tier_xl**, none | עד 50 יחידות, 51-200 יחידות, 201-500 יחידות, **501+ יחידות**, לא נבחרה תוכנית |

### New Phase 2 Additions

- `paused` status: "מושהה" (amber badge)
- `archived` status: "בארכיון" (slate badge)
- `tier_xl`: "501+ יחידות"
- `getObservedUnitsWarning()`: Returns "חריגה מהיחידות החוזיות (לבדיקה)" when observed > contracted
- `formatCurrency()`: Uses `₪` prefix with `he-IL` locale formatting

**Verdict**: PASS — billingLabels.js is the single source of truth, all labels are in Hebrew, no raw English strings

## 7.3 Warning Badge Logic (UI-only)

The `getObservedUnitsWarning(observed, contracted)` function:
- Returns warning string when `observed > contracted`
- Returns `null` otherwise
- This is **purely cosmetic** — the backend does NOT reject writes or change tiers based on observed > contracted
- Backend API response always includes both `observed_units` and `contracted_units` for the frontend to evaluate
- Backend proof: PATCH with contracted_units=50 on a project with observed_units=102 returns 200 (no rejection)
- UI proof: Screenshot 1 shows the warning badge when observed(102) > contracted(50)

**Verdict**: PASS — warning is UI-only, confirmed both in code and via authenticated screenshot

## 7.4 Route Configuration

From `frontend/src/App.js`:
- `/admin/billing` — AdminBillingPage (super_admin only)
- `/billing/org/:orgId` — OrgBillingPage (org owner + billing roles)
- ProjectBillingCard embedded in ProjectControlPage at `/projects/:projectId/control?tab=billing`

## 7.5 Flag-OFF Behavior

When `BILLING_V1_ENABLED=false`:
- Backend returns 404 for all billing endpoints (proven in Section 1)
- Frontend billing tab is conditionally hidden: `const TABS = billingEnabled ? [...BASE_TABS, BILLING_TAB] : BASE_TABS;`
- Feature flag read from: `versionService` → `data.feature_flags.billing_v1_enabled`
- Proven by `test_billing_v1.py::TestFeatureFlag` (5 tests pass)

**Verdict**: PASS — billing UI is fully feature-flagged; tab disappears when flag is OFF
