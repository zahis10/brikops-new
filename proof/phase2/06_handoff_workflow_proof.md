# Section 6: Handoff Workflow + Setup State Proof

## Step 1: PM requests handoff

- **Call**: POST /api/billing/project/c3e18b07-a7d8-411e-80f9-95028b15788a/handoff-request
- **Actor**: pm@contractor-ops.com (org owner + PM)
- **Status**: 200
- **setup_state**: pending_handoff
- **Verdict**: PASS

## Step 2: Billing role acknowledges handoff

- **Call**: POST /api/billing/project/c3e18b07-a7d8-411e-80f9-95028b15788a/handoff-ack
- **Actor**: admin@contractor-ops.com (super_admin)
- **Status**: 200
- **setup_state**: pending_billing_setup
- **Verdict**: PASS

## Step 3: Setup complete -> ready (NOT auto-active)

- **Call**: POST /api/billing/project/c3e18b07-a7d8-411e-80f9-95028b15788a/setup-complete
- **Status**: 200
- **setup_state**: ready
- **NOT auto-active**: PASS — setup_state is 'ready', not 'active'

## Step 4: Explicit activation (PATCH setup_state='active')

- **Call**: PATCH /api/billing/project/c3e18b07-a7d8-411e-80f9-95028b15788a
- **Status**: 200
- **setup_state**: active
- **Verdict**: PASS

## Step 5: Invalid transition (trial -> active) returns 400

- **Call**: PATCH setup_state='active' when current state is 'trial'
- **Status**: 400
- **Detail**: מעבר לא תקין: trial -> active
- **Verdict**: PASS

## Audit Events

Found 4 audit events after cutoff:

| # | Action | Actor | Timestamp |
|---|--------|-------|-----------|
| 1 | billing_handoff_requested | pm@contractor-ops.com | 2026-02-25T14:54:28.526571+00:00 |
| 2 | billing_handoff_acknowledged | admin@contractor-ops.com | 2026-02-25T14:54:28.544921+00:00 |
| 3 | project_billing_setup_completed | admin@contractor-ops.com | 2026-02-25T14:54:28.561726+00:00 |
| 4 | project_billing_updated | admin@contractor-ops.com | 2026-02-25T14:54:28.579917+00:00 |

**Expected actions**: {'project_billing_setup_completed', 'billing_handoff_requested', 'billing_handoff_acknowledged', 'project_billing_updated'}
**Found actions**: {'project_billing_setup_completed', 'billing_handoff_requested', 'billing_handoff_acknowledged', 'project_billing_updated'}
**Verdict**: PASS
