# Billing v1 — API Proof Matrix

**Date**: 2025-02-25  
**Commit**: `7bae3fb` (v644ec41)  
**Environment**: Dev/Preview, `BILLING_V1_ENABLED=true`

## Endpoint × Role Matrix

| # | Endpoint | Role | Expected | Actual | Notes |
|---|----------|------|----------|--------|-------|
| 1 | `GET /api/billing/org/{pm_org}` | super_admin | 200 | **200** | Returns org_name, subscription, projects array |
| 2 | `GET /api/billing/org/{pm_org}` | owner (PM on own org) | 200 | **200** | PM is org owner via `organizations.owner_user_id` |
| 3 | `GET /api/billing/org/{pm_org}` | org_admin (sitemanager) | 200 | **200** | Assigned org_admin role for proof |
| 4 | `GET /api/billing/org/{pm_org}` | billing_admin (engineer) | 200 | **200** | Assigned billing_admin role for proof |
| 5 | `GET /api/billing/org/{sa_org}` | PM (no role on SA org) | 403 | **403** | Cross-org access blocked |
| 6 | `GET /api/billing/org/{pm_org}` | management_team (safety officer) | 403 | **403** | No org billing access for management_team |
| 7 | `GET /api/billing/org/{pm_org}` | contractor | 403 | **403** | No org billing access |
| 8 | `GET /api/billing/org/{pm_org}` | viewer | 403 | **403** | No org billing access |
| 9 | `GET /api/billing/project/{project}` | super_admin | 200 | **200** | Returns observed_units=102, tier info |
| 10 | `GET /api/billing/project/{project}` | owner (PM) | 200 | **200** | PM is project member |
| 11 | `GET /api/billing/project/{project}` | org_admin (sitemanager) | 200 | **200** | Has project membership |
| 12 | `GET /api/billing/project/{project}` | billing_admin (engineer) | 200 | **200** | Has project membership |
| 13 | `GET /api/billing/project/{project}` | management_team (safety officer) | 403 | **403** | No project membership |
| 14 | `GET /api/billing/project/{project}` | contractor | 403 | **403** | No billing access for contractors |
| 15 | `GET /api/billing/project/{project}` | viewer | 403 | **403** | No billing access for viewers |
| 16 | `GET /api/admin/billing/plans` | super_admin | 200 | **200** | Returns plan_basic, plan_pro |
| 17 | `GET /api/admin/billing/plans` | PM | 403 | **403** | Admin-only endpoint |
| 18 | `GET /api/admin/billing/plans` | contractor | 403 | **403** | Admin-only endpoint |
| 19 | `POST /api/admin/billing/plans` | super_admin (no stepup) | 403 | **403** | Stepup token required |
| 20 | `PUT /api/admin/billing/plans/{id}` | super_admin (no stepup) | 403 | **403** | Stepup token required |
| 21 | `GET /api/admin/billing/migration/dry-run` | super_admin | 200 | **200** | Returns total=2, missing=0 |
| 22 | `GET /api/admin/billing/migration/dry-run` | PM | 403 | **403** | Admin-only endpoint |
| 23 | `POST /api/admin/billing/migration/apply` | super_admin (no stepup) | 403 | **403** | Stepup token required |
| 24 | `POST /api/admin/billing/migration/apply` | PM | 403 | **403** | Admin-only endpoint |
| 25 | `PUT /api/orgs/{org}/members/{user}/org-role` | super_admin | 200 | **200** | Role change works |
| 26 | `PUT /api/orgs/{org}/members/{user}/org-role` | PM (as owner) | 200 | **200** | Owner can change roles |
| 27 | `PUT /api/orgs/{org}/members/{user}/org-role` | contractor | 403 | **403** | No role management access |
| 28 | `PUT /api/orgs/{org}/members/{user}/org-role` | viewer | 403 | **403** | No role management access |
| 29 | `GET /api/billing/org/{pm_org}` | super_admin | 200 | **200** | Verification re-check |

**Total**: 29 endpoint×role combinations tested  
**All results match expected HTTP status codes.**

## Response Snippets

### Org Billing (200)
```json
{
  "org_id": "69357d4b-...",
  "org_name": "הארגון של מנהל פרויקט",
  "subscription": { "status": "active" },
  "projects": [{ "project_id": "c3e18b07-...", "observed_units": 102, ... }]
}
```

### Project Billing (200)
```json
{
  "project_id": "c3e18b07-...",
  "org_id": "69357d4b-...",
  "observed_units": 102,
  "contracted_units": 0,
  "tier_code": "tier_s",
  "monthly_total": 700
}
```

### Plans List (200)
```json
[
  { "id": "plan_basic", "name": "בסיסי", "project_fee_monthly": 500, ... },
  { "id": "plan_pro", "name": "מקצועי", "project_fee_monthly": 900, ... }
]
```

### Migration Dry Run (200)
```json
{
  "total_projects": 2,
  "projects_with_org_id": 2,
  "projects_missing_org_id": 0,
  "auto_resolvable_count": 0,
  "ambiguous_count": 0
}
```
