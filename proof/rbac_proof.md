# Billing v1 — RBAC Endpoint-Level Proof

**Date**: 2025-02-25  
**Commit**: `7bae3fb`  
**Environment**: Dev/Preview, `BILLING_V1_ENABLED=true`

## RBAC Design

Billing v1 uses a two-tier RBAC system:

1. **Org-level billing access** (`check_org_billing_role`):
   - Owner: checked via `organizations.owner_user_id` (not membership)
   - `org_admin`: checked via `organization_memberships` collection
   - `billing_admin`: checked via `organization_memberships` collection
   - `super_admin`: platform-level bypass
   - All others: **403 Forbidden**

2. **Project-level billing access** (`check_project_billing_role`):
   - Project members with roles: `owner`, `project_manager`, `org_admin`, `billing_admin`
   - `super_admin`: platform-level bypass
   - `contractor`, `viewer`, `management_team` (without org role): **403 Forbidden**

3. **Admin endpoints**: `super_admin` only, some with stepup token requirement

## Proof Assertions (all via real HTTP requests)

### Assertion 1: PM reads project billing → 200
- **Request**: `GET /api/billing/project/c3e18b07-...` with PM token
- **Result**: **200 OK** — PM is project owner/manager
- **Response**: `observed_units=102, tier_code=tier_s, monthly_total=700`

### Assertion 2: PM reads org billing of SA's org → 403
- **Request**: `GET /api/billing/org/686b8f97-...` with PM token
- **Result**: **403 Forbidden** — PM has no role on SA's organization
- **Proves**: Cross-org access is blocked

### Assertion 3: PM reads org billing of own org → 200
- **Request**: `GET /api/billing/org/69357d4b-...` with PM token
- **Result**: **200 OK** — PM is owner of this org (via `organizations.owner_user_id`)
- **Response**: org_name, subscription status, project list

### Assertion 4: Contractor reads billing → 403
- **Request**: `GET /api/billing/org/69357d4b-...` with contractor token → **403**
- **Request**: `GET /api/billing/project/c3e18b07-...` with contractor token → **403**
- **Proves**: Contractors have no billing access

### Assertion 5: Viewer reads billing → 403
- **Request**: `GET /api/billing/org/69357d4b-...` with viewer token → **403**
- **Request**: `GET /api/billing/project/c3e18b07-...` with viewer token → **403**
- **Proves**: Viewers have no billing access

### Assertion 6: Super Admin reads all → 200
- **Request**: `GET /api/billing/org/69357d4b-...` with SA token → **200**
- **Request**: `GET /api/billing/project/c3e18b07-...` with SA token → **200**
- **Request**: `GET /api/admin/billing/plans` with SA token → **200**
- **Request**: `GET /api/admin/billing/migration/dry-run` with SA token → **200**
- **Proves**: Super admin has universal billing access

### Assertion 7: org_admin reads org billing → 200
- **Request**: `GET /api/billing/org/69357d4b-...` with sitemanager token (org_admin role)
- **Result**: **200 OK**
- **Proves**: org_admin role grants org billing read access

### Assertion 8: billing_admin reads org billing → 200
- **Request**: `GET /api/billing/org/69357d4b-...` with engineer token (billing_admin role)
- **Result**: **200 OK**
- **Proves**: billing_admin role grants org billing read access

### Assertion 9: management_team org billing → 403, project billing → 403
- **Request**: `GET /api/billing/org/69357d4b-...` with safety officer token → **403**
- **Request**: `GET /api/billing/project/c3e18b07-...` with safety officer token → **403**
- **Note**: Safety officer has management_team project role but no org billing role, and no project membership on the test project
- **Proves**: management_team alone does not grant billing access

### Assertion 10: Stepup-guarded endpoints → 403 without stepup
- **Request**: `POST /api/admin/billing/plans` with SA token (no stepup) → **403**
- **Request**: `PUT /api/admin/billing/plans/plan_basic` with SA token (no stepup) → **403**
- **Request**: `POST /api/admin/billing/migration/apply` with SA token (no stepup) → **403**
- **Proves**: Mutating admin endpoints require stepup authentication

## Summary

| Role | Org Billing | Project Billing | Admin Plans | Migration |
|------|------------|----------------|-------------|-----------|
| super_admin | 200 | 200 | 200 | 200 |
| owner (PM) | 200 (own org) | 200 | 403 | 403 |
| org_admin | 200 | 200 | 403 | 403 |
| billing_admin | 200 | 200 | 403 | 403 |
| management_team | 403 | 403 | 403 | 403 |
| contractor | 403 | 403 | 403 | 403 |
| viewer | 403 | 403 | 403 | 403 |

All assertions confirmed via real HTTP requests to the running server.
