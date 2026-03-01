# Billing v1 — Observed Units Source-of-Truth Proof

**Date**: 2025-02-25  
**Commit**: `7bae3fb`  
**Environment**: Dev/Preview, `BILLING_V1_ENABLED=true`

## Counting Rule

From `billing.py` — `compute_observed_units()`:

```python
async def compute_observed_units(project_id: str) -> int:
    db = get_db()
    active_buildings = await db.buildings.find(
        {'project_id': project_id, 'archived': {'$ne': True}},
        {'_id': 0, 'id': 1}
    ).to_list(10000)
    if not active_buildings:
        return 0
    building_ids = [b['id'] for b in active_buildings]
    count = await db.units.count_documents({
        'building_id': {'$in': building_ids},
        'archived': {'$ne': True},
    })
    return count
```

**Rule**: Count non-archived units in non-archived buildings for the given project.

## Real Project Count

- **Project**: `c3e18b07-a7d8-411e-80f9-95028b15788a`
- **`compute_observed_units()` result**: **102**

## Manual Cross-Check

| Metric | Count |
|--------|-------|
| Total buildings | 5 |
| Active buildings | 4 |
| Archived buildings | 1 |
| Total units in active buildings | 104 |
| Active units in active buildings | **102** |
| Archived units in active buildings | 2 |

**Match**: `compute_observed_units() = 102` matches manual count of active units in active buildings = **102**

## Archive Exclusion Proof

Test unit: `c778cb88-b0e...` in building "בניין A"

| Step | Action | Count | Delta |
|------|--------|-------|-------|
| 1 | Before archive | 102 | — |
| 2 | Archive unit | 101 | -1 |
| 3 | Restore unit | 102 | +1 |

- Archiving a unit **decreases** the observed count by 1
- Restoring the unit **restores** the original count
- **Archive exclusion confirmed**

## Tier Resolution

The observed unit count feeds into tier resolution for billing:

```
tier_s: max_units ≤ 50  → lowest fee
tier_m: max_units ≤ 200 → medium fee
tier_l: max_units > 200 → highest fee (or None = unlimited)
```

For this project: 102 observed units → resolves to `tier_m` (51-200 range) for plan_basic (monthly_fee=500) + project_fee=500 = **total 1000₪/month**.

## Conclusion

The `compute_observed_units()` function correctly:
1. Excludes archived buildings from the count
2. Excludes archived units within active buildings
3. Returns a count that matches manual DB verification
4. Dynamically responds to archive/restore operations
