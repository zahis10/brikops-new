# Section 2: RBAC Proof

## Targeted Assertions with Real API Calls

### 2.1 PM (org owner) can request handoff
- **Call**: POST /api/billing/project/c3e18b07-a7d8-411e-80f9-95028b15788a/handoff-request
- **Role**: org_owner_pm (pm@contractor-ops.com, org owner + project_manager)
- **Status**: 200
- **Result**: setup_state=pending_handoff
- **Verdict**: PASS

### 2.2 PM-only (not org owner/billing role) CANNOT PATCH billing
- **Call**: PATCH /api/billing/project/c3e18b07-a7d8-411e-80f9-95028b15788a
- **Role**: engineer@contractor-ops.com (project_manager on project, org role=member — NOT billing role, NOT org owner)
- **Status**: 403
- **Verdict**: PASS

### 2.3 management_team is read-only
- **GET billing/project**: 200 (allowed via org_admin role)
- **PATCH billing/project** (with org role reverted to member): 403
- **Verdict**: PASS — management_team without org billing role cannot write

### 2.4 Contractor blocked from all billing
- **GET billing/project**: 403
- **PATCH billing/project**: 403
- **POST handoff-request**: 403
- **Verdict**: PASS

### 2.5 Viewer blocked from all billing
- **GET billing/project**: 403
- **PATCH billing/project**: 403
- **Verdict**: PASS

### 2.6 org_admin can PATCH project billing
- **Call**: PATCH /api/billing/project/c3e18b07-a7d8-411e-80f9-95028b15788a
- **Role**: sitemanager@contractor-ops.com (org_admin in org)
- **Status**: 200
- **Result**: contracted_units=80
- **Verdict**: PASS

### 2.7 billing_admin can PATCH project billing
- **Call**: PATCH /api/billing/project/c3e18b07-a7d8-411e-80f9-95028b15788a
- **Role**: engineer@contractor-ops.com (billing_admin in org)
- **Status**: 200
- **Result**: contracted_units=85
- **Verdict**: PASS

### 2.8 super_admin override
- **Call**: PATCH /api/billing/project/c3e18b07-a7d8-411e-80f9-95028b15788a
- **Status**: 200
- **Verdict**: PASS

### 2.9 Project with org_id=None returns 400
- **Call**: PATCH /api/billing/project/test-no-org-proof
- **Status**: 400
- **Detail**: פרויקט ללא ארגון
- **Verdict**: PASS

