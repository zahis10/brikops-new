# Section 8: Release Metadata + Additional Checks

## Release Metadata

| Field | Value |
|-------|-------|
| Git SHA (short) | `a116bf8` |
| Git SHA (full) | `a116bf8008bbeeffc0c79bb5bc601a598330ea29` |
| Environment | Replit dev (MongoDB local :27017) |
| BILLING_V1_ENABLED | `true` |
| Test suite | `backend/tests/test_billing_v1.py` — 31 pass, 7 skip |
| Plans seeded | plan_basic (₪1,200), plan_pro (₪2,000), plan_xl (₪3,500) |
| Pricing version | v2 (4 tiers including tier_xl) |
| Proof generated | 2026-02-25 |

## Check A: setup-complete → ready (NOT active)

- **Call**: POST /api/billing/project/c3e18b07-a7d8-411e-80f9-95028b15788a/setup-complete
- **Precondition**: setup_state=pending_billing_setup
- **Result**: setup_state=`ready`
- **Expected**: `ready`
- **Verdict**: PASS — setup-complete transitions to `ready`, NOT `active`
- Explicit PATCH setup_state=active is required for final activation

## Check B: observed_units Warning is UI-Only

- **Call**: PATCH /api/billing/project/c3e18b07-a7d8-411e-80f9-95028b15788a with contracted_units=30
- **observed_units**: 102 (from DB, real project data)
- **contracted_units**: 30
- **tier_code**: `tier_s` (based on contracted_units=30 → tier_s)
- **HTTP Status**: 200
- **Verdict**: PASS — backend accepted contracted_units=30 even though observed=102 > 30
- Tier is determined by contracted_units only, NOT observed_units
- Warning display is handled by `getObservedUnitsWarning()` in billingLabels.js (frontend only)

## Check C: billingLabels.js is Single Source of Truth

Import evidence (grep results):

```
frontend/src/components/ProjectBillingCard.js:8:} from '../utils/billingLabels';
frontend/src/pages/OrgBillingPage.js:9:} from '../utils/billingLabels';
frontend/src/pages/AdminBillingPage.js:18:} from '../utils/billingLabels';
```

- **Files importing billingLabels**: 3
- **Components**: ProjectBillingCard.js, OrgBillingPage.js, AdminBillingPage.js
- **Verdict**: PASS — all billing UI components import from the same `billingLabels.js` module
- No duplicate label definitions found elsewhere

## Rollback Instructions

To disable Billing v1:
1. Set `BILLING_V1_ENABLED=false` in environment
2. All billing endpoints return 404
3. Frontend billing tabs/routes are hidden
4. No data loss — billing records remain in MongoDB

To revert Phase 2 additions:
1. Remove `plan_xl` from `billing_plans` collection
2. Remove `tier_xl` from plan unit_tiers
3. Remove `paused`/`archived` from billingLabels.js
4. Revert setup_state workflow endpoints from router.py
5. Revert RBAC changes in billing.py
