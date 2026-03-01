# Billing v1 — Audit Trail Proof

**Date**: 2025-02-25  
**Commit**: `7bae3fb`  
**Environment**: Dev/Preview, `BILLING_V1_ENABLED=true`

## Audit Event Types

All billing v1 operations emit structured audit events to the `audit_events` collection. Each event includes: `id`, `entity_type`, `entity_id`, `action`, `actor_id`, `payload`, `created_at`.

## Required Actions — Complete Evidence

### 1. `billing_plan_created` — VERIFIED (2 events)

| Field | Value |
|-------|-------|
| actor_id | `c452c225-8876-4a33-a69f-207145eeacb4` (super_admin) |
| entity_type | `billing_plan` |
| entity_id | `a0f65536-b2a6-4909-bf86-c2893c080cb2` |
| created_at | `2026-02-25T06:20:27.685476+00:00` |
| payload | `{"name": "תוכנית הוכחה", "project_fee_monthly": 400}` |

**How triggered**: Called `create_plan()` with plan data and SA actor_id.

---

### 2. `billing_plan_updated` — VERIFIED (2 events)

| Field | Value |
|-------|-------|
| actor_id | `c452c225-8876-4a33-a69f-207145eeacb4` (super_admin) |
| entity_type | `billing_plan` |
| entity_id | `a0f65536-b2a6-4909-bf86-c2893c080cb2` |
| created_at | `2026-02-25T06:20:27.690670+00:00` |
| payload.before | `{"name": "תוכנית הוכחה", "project_fee_monthly": 400, "version": 1}` |
| payload.after | `{"name": "תוכנית הוכחה מעודכנת", "project_fee_monthly": 450, "version": 2}` |

**How triggered**: Called `update_plan()` with updated name and fee.

---

### 3. `billing_plan_deactivated` — VERIFIED (3 events)

| Field | Value |
|-------|-------|
| actor_id | `c452c225-8876-4a33-a69f-207145eeacb4` (super_admin) |
| entity_type | `billing_plan` |
| entity_id | `a0f65536-b2a6-4909-bf86-c2893c080cb2` |
| created_at | `2026-02-25T06:20:27.700889+00:00` |
| payload | `{"name": "תוכנית הוכחה מעודכנת"}` |

**How triggered**: Called `deactivate_plan()` on the test plan.

---

### 4. `project_billing_created` — VERIFIED (2 events)

| Field | Value |
|-------|-------|
| actor_id | `c452c225-8876-4a33-a69f-207145eeacb4` (super_admin) |
| entity_type | `project_billing` |
| entity_id | `8a70ae84-1fa1-4bee-af83-0900c4f50863` |
| created_at | `2026-02-25T06:20:27.673376+00:00` |
| payload | `{"project_id": "proof-audit-project", "org_id": "69357d4b-...", "plan_id": "plan_basic", "contracted_units": 75, "monthly_total": 1000}` |

**How triggered**: Called `create_project_billing()` with plan_basic and 75 contracted units.

---

### 5. `project_billing_updated` — VERIFIED (1 event)

| Field | Value |
|-------|-------|
| actor_id | `c452c225-8876-4a33-a69f-207145eeacb4` (super_admin) |
| entity_type | `project_billing` |
| entity_id | `8a70ae84-1fa1-4bee-af83-0900c4f50863` |
| created_at | `2026-02-25T06:20:27.677622+00:00` |
| payload.before | `{"plan_id": "plan_basic", "contracted_units": 75, "monthly_total": 1000}` |
| payload.after | `{"plan_id": "plan_pro", "contracted_units": 75, "monthly_total": 1700}` |

**How triggered**: Called `update_project_billing()` changing `plan_id` from `plan_basic` to `plan_pro` **without** changing `contracted_units`. This emits `project_billing_updated` (not `contracted_units_changed`) because the contracted_units value did not change.

**Code reference** (`billing.py` lines 417-419):
```python
action = 'project_billing_updated'
if 'contracted_units' in updates and updates['contracted_units'] != existing.get('contracted_units'):
    action = 'contracted_units_changed'
```

---

### 6. `contracted_units_changed` — VERIFIED (3 events)

| Field | Value |
|-------|-------|
| actor_id | `c452c225-8876-4a33-a69f-207145eeacb4` (super_admin) |
| entity_type | `project_billing` |
| entity_id | `8a70ae84-1fa1-4bee-af83-0900c4f50863` |
| created_at | `2026-02-25T06:20:27.705816+00:00` |
| payload.before | `{"plan_id": "plan_pro", "contracted_units": 75, "monthly_total": 1700}` |
| payload.after | `{"plan_id": "plan_pro", "contracted_units": 200, "monthly_total": 1700}` |

**How triggered**: Called `update_project_billing()` changing `contracted_units` from 75 to 200. This emits `contracted_units_changed` because the contracted_units value changed.

---

### 7. `org_role_changed` — VERIFIED (2 events)

**Event 1 — sitemanager assigned org_admin:**

| Field | Value |
|-------|-------|
| actor_id | `16f6c934-0f5d-4c6d-842a-14aee775dff6` (SA session) |
| entity_type | `organization` |
| entity_id | `69357d4b-547d-4b53-988e-b28880e6f767` |
| created_at | `2026-02-25T05:42:03.999304+00:00` |
| payload | `{"target_user_id": "423c999c-...", "old_role": "member", "new_role": "org_admin"}` |

**Event 2 — engineer assigned billing_admin:**

| Field | Value |
|-------|-------|
| actor_id | `16f6c934-0f5d-4c6d-842a-14aee775dff6` (SA session) |
| entity_type | `organization` |
| entity_id | `69357d4b-547d-4b53-988e-b28880e6f767` |
| created_at | `2026-02-25T05:42:04.024546+00:00` |
| payload | `{"target_user_id": "a6c500be-...", "old_role": "member", "new_role": "billing_admin"}` |

**How triggered**: Called `PUT /api/orgs/{org}/members/{user}/org-role` API endpoint with SA credentials.

---

### 8. `org_id_backfill_applied` — N/A (0 events, expected)

| Evidence | Detail |
|----------|--------|
| Status | **N/A — no-op, all projects already have org_id** |
| Dry run result | `total_projects=2, projects_with_org_id=2, projects_missing_org_id=0` |
| Apply result (1st) | `applied_count=0, skipped_count=0` |
| Apply result (2nd) | `applied_count=0, skipped_count=0` (idempotent) |
| Justification | All 2 projects already had `org_id` assigned from the organization migration. No backfill was needed, so no audit events were emitted. This is correct — audit events for this action are only created when a project's `org_id` is actually set during backfill. |
| No auto-run | Confirmed: `server.py` contains no calls to `apply_org_id_backfill()`. Migration is admin-initiated only via `POST /api/admin/billing/migration/apply` (stepup-guarded). |

---

## Summary

| # | Action | Events | Status | Evidence |
|---|--------|--------|--------|----------|
| 1 | `billing_plan_created` | 2 | VERIFIED | Plan creation with name + fee in payload |
| 2 | `billing_plan_updated` | 2 | VERIFIED | Before/after snapshots with version increment |
| 3 | `billing_plan_deactivated` | 3 | VERIFIED | Plan name in payload |
| 4 | `project_billing_created` | 2 | VERIFIED | Full billing record in payload |
| 5 | `project_billing_updated` | 1 | VERIFIED | Plan change without contracted_units change |
| 6 | `contracted_units_changed` | 3 | VERIFIED | Before/after with contracted_units diff |
| 7 | `org_role_changed` | 2 | VERIFIED | Old/new role in payload |
| 8 | `org_id_backfill_applied` | 0 | N/A | No-op (all projects clean), idempotency proven |

**All 8 required audit action types have explicit evidence or documented N/A with justification.**
