# Billing v1 — UI Proof

**Date**: 2025-02-25  
**Commit**: `7bae3fb`  
**Environment**: Dev/Preview

## Authenticated Screenshots (Flag ON)

All screenshots taken via automated Playwright browser tests with real user login (email/password authentication via `/api/auth/login`), navigation to billing pages, and screenshot capture after full page render including async data loading.

### Screenshot 1: ProjectBillingCard (PM, flag ON)

- **User**: pm@contractor-ops.com (Project Manager, org owner)
- **Path**: `/projects/c3e18b07-.../control?tab=settings`
- **Login method**: auto-login.html with redirect to project settings tab
- **Result**: ProjectBillingCard renders within the settings tab showing:
  - Organization name and subscription status
  - Pricing tier level (tier_m based on 102 observed units)
  - Contracted units count
  - Observed units count (102)
  - Monthly total cost
- **Status**: VERIFIED via Playwright screenshot

### Screenshot 2: OrgBillingPage (PM as org owner, flag ON)

- **User**: pm@contractor-ops.com (org owner of PM org)
- **Path**: `/billing/org/69357d4b-547d-4b53-988e-b28880e6f767`
- **Login method**: auto-login.html with redirect to org billing page
- **Result**: OrgBillingPage renders showing:
  - Organization name ("הארגון של מנהל פרויקט")
  - Subscription status and access level
  - Total monthly cost
  - Per-project billing breakdown with tier, units, and costs
- **Status**: VERIFIED via Playwright screenshot

### Screenshot 3: OrgBillingPage (org_admin, flag ON)

- **User**: sitemanager@contractor-ops.com (org_admin role on PM org)
- **Path**: `/billing/org/69357d4b-547d-4b53-988e-b28880e6f767`
- **Login method**: auto-login.html with redirect to org billing page
- **Result**: OrgBillingPage renders with identical data as org owner view
- **Proves**: org_admin role grants org billing read access in the UI
- **Status**: VERIFIED via Playwright screenshot

### Screenshot 4: AdminBillingPage (Super Admin, flag ON)

- **User**: admin@contractor-ops.com (super_admin)
- **Path**: `/admin/billing`
- **Login method**: auto-login.html with redirect to admin billing page
- **Result**: AdminBillingPage renders showing:
  - Billing plans section with plan_basic and plan_pro (names, fees, tiers, active status)
  - Migration section with dry-run results (total projects, org_id coverage)
  - Organization list with subscription statuses
- **Status**: VERIFIED via Playwright screenshot

## Flag OFF Behavior

### Billing Endpoints Return 404

With `BILLING_V1_ENABLED=false` (default), all billing API endpoints return HTTP 404:

```
GET /api/billing/org/{org_id}        → 404
GET /api/billing/project/{project_id} → 404
GET /api/admin/billing/plans          → 404
GET /api/admin/billing/migration/dry-run → 404
```

Verified via curl after removing `BILLING_V1_ENABLED=true` from the workflow and restarting the server.

### UI Graceful Degradation

- **ProjectBillingCard**: Does not render when billing API returns 404 (component handles missing data gracefully, shows no card)
- **OrgBillingPage**: Shows "billing unavailable" / error state when API returns 404 (no crash, no error page)
- **AdminBillingPage**: Billing-specific sections show empty/error state when endpoints return 404

### PM Billing Visibility (Flag ON)

- **Project billing**: PM sees ProjectBillingCard in project settings tab (HTTP 200 from project billing endpoint)
- **Own org billing**: PM sees OrgBillingPage for their own org (HTTP 200, PM is org owner)
- **Other org billing**: PM cannot access org billing for other organizations (HTTP 403, blocked by `check_org_billing_role`)
- **Admin billing**: PM cannot access AdminBillingPage (HTTP 403, super_admin only)

## UI Components Summary

| Component | Route/Location | Access | Flag ON | Flag OFF |
|-----------|---------------|--------|---------|----------|
| ProjectBillingCard | Project settings tab | PM, owner, org_admin, billing_admin | Renders with billing data | Not rendered (404 → no data) |
| OrgBillingPage | `/billing/org/:orgId` | Org owner, org_admin, billing_admin, SA | Full org billing view | "Billing unavailable" message |
| AdminBillingPage | `/admin/billing` | super_admin only | Plans + migration sections | Empty/error sections |

## Technical Implementation

| File | Purpose |
|------|---------|
| `ProjectBillingCard.js` | Project settings billing card component |
| `OrgBillingPage.js` | Organization billing overview page |
| `AdminBillingPage.js` | Admin plans + migration management page |
| `BillingContext.js` | Billing state management + API integration |
| `api.js` | billingService with 12 API methods |

All components use the established UI patterns (Radix UI, TailwindCSS, shadcn/ui) and follow RTL Hebrew layout conventions.
