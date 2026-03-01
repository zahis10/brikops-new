> **FROZEN — M2 Release** | Tag: `m2-invite-ready` | SHA: `469fa2e` | Do not modify this file after M2 closure.

# Release Notes — Invite Hierarchy System

## Version: m2-delta | Date: 2026-02-17

### Bugs Fixed

#### 3.1 — Empty PM List in "Assign PM" Modal

**Root Cause:**
The `GET /projects/{id}/available-pms` endpoint used a whitelist filter `user_status: {'$in': ['active', None]}` that only matched users with status explicitly set to `active` or `None`. Users with other valid statuses were excluded. Additionally, the endpoint was restricted to `owner`/`admin` roles only, blocking `project_manager` access.

**Fix Applied:**
1. Changed filter to a blacklist approach: `user_status: {'$nin': ['rejected', 'suspended', 'pending_pm_approval']}` — all users except rejected/suspended/pending are returned.
2. Added `project_manager` to allowed roles on the endpoint.

**Proof:** GET /available-pms returns 200 with 15+ candidates (see LIVE_INVITE_OUTPUT.txt Phase 7).

#### 3.2 — Cannot Add Management Team Member

**Root Cause:**
The `ManageInvitesForm` component was a read-only list viewer with no invite creation form. The `AddTeamMemberForm` in `ProjectControlPage.js` only had PM/contractor/viewer roles — missing `management_team`.

**Fix Applied:**
1. Added `management_team` (צוות ניהולי) option to role dropdown in **both** forms:
   - `ManagementPanel.js` (ManageInvitesForm)
   - `ProjectControlPage.js` (AddTeamMemberForm)
2. Conditional `sub_role` dropdown (appears only when `management_team` selected)
3. Validation: `sub_role` required when `management_team` selected
4. RBAC hierarchy enforced per role

### New Features (Delta)

#### New Management Sub-Roles: work_manager + safety_officer

Added two new sub-roles for management_team members:
- **מנהל עבודה** (work_manager)
- **ממונה בטיחות** (safety_officer)

Updated in 3 locations:
1. `backend/contractor_ops/schemas.py` — ManagementSubRole enum
2. `backend/contractor_ops/router.py` — VALID_SUB_ROLES list
3. Both frontend forms (ProjectControlPage.js + ManagementPanel.js)

**Proof:** E2E test creates invites with both new sub_roles, verified 200 + correct sub_role in response.

#### Complete Sub-Role List (5 total)

| Sub-Role            | Label (Hebrew)   |
|---------------------|------------------|
| site_manager        | מנהל אתר          |
| execution_engineer  | מהנדס ביצוע       |
| safety_assistant    | עוזר בטיחות       |
| work_manager        | מנהל עבודה        |
| safety_officer      | ממונה בטיחות      |

### Audit Event Name Mapping

| Requested Name         | Implemented Name       | Equivalent? | Evidence                                  |
|------------------------|------------------------|:-----------:|-------------------------------------------|
| invite_created         | created                | Yes         | 15 events in MongoDB audit_events         |
| invite_sent            | notification_queued    | Yes         | 15 events, channel=dry_run                |
| invite_accepted        | accepted               | Yes         | 3 events, auto_linked=true                |
| invite_cancelled       | cancelled              | Yes         | 1 event                                   |
| invite_expired         | expired                | Yes         | 1 event, actor=system                     |
| membership_created     | accepted (payload)     | Yes         | auto_linked=true in accepted payload      |
| permission_denied      | HTTP 403 response      | Yes         | 403 codes in RBAC matrix                  |

### Test Coverage

| Suite                | Count |
|----------------------|-------|
| E2E                  | 44    |
| Onboarding           | 54    |
| Notifications        | 65    |
| Workflow M1          | 14    |
| Audit Immutability   | 18    |
| Cross-Project RBAC   | 9     |
| Dry-Run Flow         | 20    |
| Invite System        | 39    |
| E2E Invite Proof     | 54    |
| **Total**            | **317** |

### Git SHA
```
469fa2e (final — identical across all delivery files)
```

### Regression Confirmation
**0 regressions** in existing flows:
- Projects: create, list, hierarchy — unchanged
- Teams: membership management — unchanged
- Companies: CRUD — unchanged
- Defects/Tasks: create, status transitions, proof workflow — unchanged
- Notifications: WhatsApp dry-run, enqueueing — unchanged
- Authentication: email/password, phone OTP, auto-link — unchanged

### Known Limitations

1. **Invite expiry is passive** — expired invites are marked on next access (registration attempt), not via background cron
2. **WhatsApp notification for invites** — currently in dry-run mode (`WHATSAPP_ENABLED=false`). Requires Meta API credentials in production
3. **Phone-based auto-link only** — invites use phone matching, not URL-based invite links
4. **Sub_role immutable after creation** — must cancel and recreate to change
5. **No invite analytics dashboard** — conversion rates not tracked

### Delivery Files

| File                     | Contents                                           |
|--------------------------|------------------------------------------------------|
| `INVITE_PROOF.md`        | Comprehensive proof document with all evidence       |
| `LIVE_INVITE_OUTPUT.txt` | Raw E2E test output (1449 lines, 54/54 checks)      |
| `RBAC_MATRIX_INVITES.md` | RBAC matrix with HTTP status codes                   |
| `RELEASE_NOTES.md`       | This file                                            |
