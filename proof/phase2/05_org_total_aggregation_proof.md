# Section 5: Org Total Aggregation Proof

## Step 1: Active project billing

- Project monthly_total: 3600
- Org subscription total_monthly: 3600
- Project visible in org projects list: Yes

## Step 2: Pause project billing (status='paused')

- Project status after PATCH: paused
- Org subscription total_monthly: 0 (was 3600)
- Total dropped: PASS
- Project still visible in org projects list: Yes
- Project monthly_total in list: 3600 (snapshot preserved)

## Step 3: Re-activate project billing

- Org subscription total_monthly: 3600 (restored from 0)
- Total restored: PASS

## Conclusion

- `recalc_org_total` sums only `status='active'` project_billing rows
- Paused/archived projects excluded from org total but remain visible in project list with their snapshot values
- **PASS**: Active-only aggregation rule proven
