# Section 3: Pricing Proof

## 3.1 Plans Listing (GET /api/admin/billing/plans)

| Plan ID | Name | Project Fee | Version | Active | Tiers |
|---------|------|-------------|---------|--------|-------|
| plan_basic | בסיסי | 1200 | v2 | True | tier_s(max=50, fee=900), tier_m(max=200, fee=2400), tier_l(max=500, fee=4800), tier_xl(max=None, fee=8500) |
| plan_pro | מקצועי | 2000 | v2 | True | tier_s(max=50, fee=900), tier_m(max=200, fee=2400), tier_l(max=500, fee=4800), tier_xl(max=None, fee=8500) |
| plan_xl | XL | 3500 | v2 | True | tier_s(max=50, fee=900), tier_m(max=200, fee=2400), tier_l(max=500, fee=4800), tier_xl(max=None, fee=8500) |

**Verdict**: PASS — 3 plans visible including XL

## 3.2 Tier Boundary Proof

| contracted_units | Expected Tier | Actual Tier | project_fee | tier_fee | monthly_total | Formula Check |
|-----------------|---------------|-------------|-------------|----------|---------------|---------------|
| 50 | tier_s | tier_s (PASS) | 1200 | 900 | 2100 | PASS (=1200+900) |
| 51 | tier_m | tier_m (PASS) | 1200 | 2400 | 3600 | PASS (=1200+2400) |
| 200 | tier_m | tier_m (PASS) | 1200 | 2400 | 3600 | PASS (=1200+2400) |
| 201 | tier_l | tier_l (PASS) | 1200 | 4800 | 6000 | PASS (=1200+4800) |
| 500 | tier_l | tier_l (PASS) | 1200 | 4800 | 6000 | PASS (=1200+4800) |
| 501 | tier_xl | tier_xl (PASS) | 1200 | 8500 | 9700 | PASS (=1200+8500) |

**All boundaries correct**: tier_s(<=50), tier_m(51-200), tier_l(201-500), tier_xl(501+)
**Formula verified**: monthly_total = project_fee_snapshot + tier_fee_snapshot for all cases

## 3.3 Cross-Plan Formula Verification

| Plan | Units | Tier | project_fee | tier_fee | monthly_total | Formula |
|------|-------|------|-------------|----------|---------------|---------|
| plan_basic | 100 | tier_m | 1200 | 2400 | 3600 | PASS |
| plan_pro | 100 | tier_m | 2000 | 2400 | 4400 | PASS |
| plan_xl | 100 | tier_m | 3500 | 2400 | 5900 | PASS |
