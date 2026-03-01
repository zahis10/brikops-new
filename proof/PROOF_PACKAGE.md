# Billing v1 Phase 1 — Proof Package

**Feature**: M9 Billing v1 Phase 1  
**Date**: 2025-02-25  
**Commit**: `7bae3fb` (version tag: `v644ec41`)  
**Environment**: Dev/Preview  
**Feature Flag**: `BILLING_V1_ENABLED` (default: `false`)

---

## Table of Contents

1. [Release Metadata](#1-release-metadata)
2. [API Proof Matrix](#2-api-proof-matrix)
3. [RBAC Endpoint-Level Proof](#3-rbac-endpoint-level-proof)
4. [Migration Proof](#4-migration-proof)
5. [Audit Trail Proof](#5-audit-trail-proof)
6. [Observed Units Source-of-Truth](#6-observed-units-source-of-truth)
7. [UI Proof](#7-ui-proof)

---

## 1. Release Metadata

| Property | Value |
|----------|-------|
| Commit | `7bae3fb` |
| Version Tag | `v644ec41` |
| Environment | Dev/Preview |
| Feature Flag | `BILLING_V1_ENABLED` |
| Default State | `false` (all endpoints return 404) |
| Backend Files | `billing.py`, `billing_plans.py`, `router.py` |
| Frontend Files | `OrgBillingPage.js`, `ProjectBillingCard.js`, `AdminBillingPage.js`, `BillingContext.js` |
| Tests | `test_billing_v1.py` (9 tests: 5 flag-off + 4 direct function) |
| Default Plans | `plan_basic` (500₪, tiers 200/500/900), `plan_pro` (900₪, tiers 350/800/1400) |

### New Endpoints (8)

| Method | Path | Guard |
|--------|------|-------|
| GET | `/api/billing/org/{org_id}` | org billing role |
| GET | `/api/billing/project/{project_id}` | project billing role |
| GET | `/api/admin/billing/plans` | super_admin |
| POST | `/api/admin/billing/plans` | super_admin + stepup |
| PUT | `/api/admin/billing/plans/{plan_id}` | super_admin + stepup |
| GET | `/api/admin/billing/migration/dry-run` | super_admin |
| POST | `/api/admin/billing/migration/apply` | super_admin + stepup |
| PUT | `/api/orgs/{org_id}/members/{user_id}/org-role` | owner/org_admin/super_admin |

### Rollback Instructions

1. Set `BILLING_V1_ENABLED=false` (or remove the env var)
2. Restart server
3. All billing endpoints return 404
4. No UI billing components render
5. No data migration needed — existing data remains inert

---

## 2. API Proof Matrix

**Full details**: [api_proof_matrix.md](api_proof_matrix.md)

29 endpoint×role combinations tested via real HTTP requests:

| # | Endpoint | Role | HTTP |
|---|----------|------|------|
| 1 | GET org billing | super_admin | 200 |
| 2 | GET org billing | owner (PM) | 200 |
| 3 | GET org billing | org_admin | 200 |
| 4 | GET org billing | billing_admin | 200 |
| 5 | GET org billing (cross-org) | PM | 403 |
| 6 | GET org billing | management_team | 403 |
| 7 | GET org billing | contractor | 403 |
| 8 | GET org billing | viewer | 403 |
| 9 | GET project billing | super_admin | 200 |
| 10 | GET project billing | owner (PM) | 200 |
| 11 | GET project billing | org_admin | 200 |
| 12 | GET project billing | billing_admin | 200 |
| 13 | GET project billing | management_team (no membership) | 403 |
| 14 | GET project billing | contractor | 403 |
| 15 | GET project billing | viewer | 403 |
| 16 | GET admin plans | super_admin | 200 |
| 17 | GET admin plans | PM | 403 |
| 18 | GET admin plans | contractor | 403 |
| 19 | POST admin plans | super_admin (no stepup) | 403 |
| 20 | PUT admin plans | super_admin (no stepup) | 403 |
| 21 | GET migration dry-run | super_admin | 200 |
| 22 | GET migration dry-run | PM | 403 |
| 23 | POST migration apply | super_admin (no stepup) | 403 |
| 24 | POST migration apply | PM | 403 |
| 25 | PUT org-role | super_admin | 200 |
| 26 | PUT org-role | owner (PM) | 200 |
| 27 | PUT org-role | contractor | 403 |
| 28 | PUT org-role | viewer | 403 |
| 29 | GET org billing (verify) | super_admin | 200 |

---

## 3. RBAC Endpoint-Level Proof

**Full details**: [rbac_proof.md](rbac_proof.md)

### Summary Matrix

| Role | Org Billing | Project Billing | Admin Plans | Migration |
|------|------------|----------------|-------------|-----------|
| super_admin | 200 | 200 | 200 | 200 |
| owner (PM) | 200 (own org) / 403 (cross-org) | 200 | 403 | 403 |
| org_admin | 200 | 200 | 403 | 403 |
| billing_admin | 200 | 200 | 403 | 403 |
| management_team | 403 | 403 | 403 | 403 |
| contractor | 403 | 403 | 403 | 403 |
| viewer | 403 | 403 | 403 | 403 |

Key proofs:
- Cross-org access blocked (PM on SA's org → 403)
- Stepup-guarded endpoints return 403 without stepup token
- management_team project role alone does not grant billing access

---

## 4. Migration Proof

**Full details**: [migration_proof.md](migration_proof.md)

| Test | Result |
|------|--------|
| Dry run | total=2, with_org_id=2, missing=0 |
| Apply (1st) | applied=0, skipped=0 (all clean) |
| Apply (2nd) | applied=0, skipped=0 (idempotent) |
| Audit events | 0 (expected — no backfill needed) |
| Auto-run on startup | None (admin-initiated only) |

Key safety features:
- `{'$exists': False}` guard prevents overwriting existing `org_id`
- Ambiguous projects are skipped, not auto-resolved
- Each applied backfill creates an audit event

---

## 5. Audit Trail Proof

**Full details**: [audit_trail_proof.md](audit_trail_proof.md)

All 8 required audit action types explicitly verified:

| # | Action | Events | Status | Evidence |
|---|--------|--------|--------|----------|
| 1 | `billing_plan_created` | 2 | VERIFIED | Plan creation with name + fee in payload |
| 2 | `billing_plan_updated` | 2 | VERIFIED | Before/after snapshots with version increment |
| 3 | `billing_plan_deactivated` | 3 | VERIFIED | Plan name in payload |
| 4 | `project_billing_created` | 2 | VERIFIED | Full billing record in payload |
| 5 | `project_billing_updated` | 1 | VERIFIED | Plan change without contracted_units change |
| 6 | `contracted_units_changed` | 3 | VERIFIED | Before/after with contracted_units diff |
| 7 | `org_role_changed` | 2 | VERIFIED | Old/new role in payload |
| 8 | `org_id_backfill_applied` | 0 | N/A | No-op: all projects have org_id, idempotency proven |

**Action differentiation**: `update_project_billing()` emits `project_billing_updated` when only `plan_id` changes, and `contracted_units_changed` when `contracted_units` changes. Both actions explicitly triggered and verified.

All audit events include: `actor_id`, `entity_type`, `entity_id`, `action`, `payload` (with before/after snapshots), `created_at`.

---

## 6. Observed Units Source-of-Truth

**Full details**: [observed_units_proof.md](observed_units_proof.md)

### Counting Rule
Count non-archived units in non-archived buildings for the given project.

### Verification

| Metric | Count |
|--------|-------|
| Total buildings | 5 |
| Active buildings | 4 |
| Archived buildings | 1 |
| Active units in active buildings | **102** |
| Archived units in active buildings | 2 |
| `compute_observed_units()` | **102** |

### Archive Exclusion Test

| Step | Count |
|------|-------|
| Before archive | 102 |
| After archiving 1 unit | 101 (-1) |
| After restoring unit | 102 (+1) |

---

## 7. UI Proof

**Full details**: [ui_proof.md](ui_proof.md)

### Authenticated Screenshots (via Playwright)

All screenshots taken via automated Playwright browser tests with real user login (email/password authentication), navigation, and full-page render capture.

| # | Page | User | Flag | Result |
|---|------|------|------|--------|
| 1 | ProjectBillingCard (settings tab) | PM | ON | Billing card with observed units (102), tier, monthly total |
| 2 | OrgBillingPage | PM (org owner) | ON | Org overview with subscription, project list, costs |
| 3 | OrgBillingPage | Sitemanager (org_admin) | ON | Identical view — org_admin access confirmed |
| 4 | AdminBillingPage | Super Admin | ON | Plans list (plan_basic, plan_pro) + migration section |
| 5 | Settings tab | PM | OFF | No billing card visible — graceful empty state |
| 6 | OrgBillingPage | PM | OFF | "Billing unavailable" — graceful 404 handling |

### Feature Flag Behavior
- **Flag ON**: All billing UI renders with real data from API (HTTP 200)
- **Flag OFF**: All billing API endpoints return 404; UI components handle gracefully (no crash, no error page, no billing exposure)

### PM Billing Visibility
- Project billing: visible in settings tab (PM is project member)
- Own org billing: visible at `/billing/org/:orgId` (PM is org owner)
- Other org billing: blocked (HTTP 403)
- Admin billing: blocked (HTTP 403, super_admin only)

---

## Proof Execution Summary

| Proof Section | Method | Verdict |
|---------------|--------|---------|
| API Matrix | 29 real HTTP requests | All pass |
| RBAC | 10 targeted assertions | All pass |
| Migration | Direct function calls + audit query | Idempotent, no auto-run |
| Audit Trail | 8 action types, all explicitly evidenced | 7 verified + 1 N/A (justified) |
| Observed Units | Function + manual cross-check + archive test | Exact match (102) |
| UI | 6 authenticated Playwright screenshots | Flag ON + flag OFF confirmed |

**Phase 1 Status**: Complete. Ready for reviewer approval.
