# Section 4: Snapshot Immutability Proof

## Step 1: Assign plan_basic, contracted_units=30

- project_fee_snapshot: 1200
- tier_fee_snapshot: 900
- pricing_version: 2
- monthly_total: 2100

## Step 2: Modify plan_basic project_fee_monthly in DB (1200 -> 1500)

- Direct MongoDB update: `billing_plans.update_one({id: 'plan_basic'}, {$set: {project_fee_monthly: 1500}})`

## Step 3: Re-read project billing (GET) — snapshot UNCHANGED

- project_fee_snapshot: 1200 (was 1200)
- tier_fee_snapshot: 900
- monthly_total: 2100
- **Immutable**: PASS — existing snapshot NOT changed by plan update

## Step 4: Re-assign plan (PATCH) — gets NEW pricing

- project_fee_snapshot: 1500 (expected 1500)
- monthly_total: 2400
- **Uses new pricing**: PASS

## Step 5: Restore plan_basic fee to 1200 and re-assign

- Restored and re-assigned: project_fee_snapshot=1200

## Conclusion

- Existing snapshots are **immutable** — changing plan pricing does not retroactively affect stored snapshots
- New assignments pick up the current plan pricing at time of assignment
- **PASS**: Snapshot immutability proven
