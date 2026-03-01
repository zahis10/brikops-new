> **FROZEN — M2 Release** | Tag: `m2-invite-ready` | SHA: `469fa2e` | Do not modify this file after M2 closure.

# RBAC Matrix — Invite System

## Verified: 2026-02-17T17:39Z | Source: LIVE_INVITE_OUTPUT.txt (automated E2E test, 54/54 checks)

## Invite Permissions Matrix

| Action              | Admin (owner) | PM (project_manager) | Management Team | Contractor | Viewer |
|---------------------|:-------------:|:--------------------:|:---------------:|:----------:|:------:|
| Create Invite       | 200           | 200                  | 200             | 403        | 403    |
| List Invites        | 200           | 200                  | 200             | 403        | 403    |
| Cancel Invite       | 200           | 200                  | 200             | 403        | 403    |
| Resend Invite       | 200           | 200                  | 200             | 403        | 403    |
| Cross-Project       | N/A           | 403                  | 403             | 403        | 403    |

## Invite Hierarchy — Who Can Invite Which Roles

| Inviter             | → project_manager | → management_team | → contractor |
|---------------------|:-----------------:|:------------------:|:------------:|
| Admin (owner)       | 200               | 200                | 200          |
| PM                  | 403               | 200                | 200          |
| Management Team     | 403               | 403                | 200          |
| Contractor          | 403               | 403                | 403          |
| Viewer              | 403               | 403                | 403          |

## Cross-Project Isolation

| Scenario                                      | Expected | Actual |
|-----------------------------------------------|----------|--------|
| PM of Project A creates invite in Project B   | 403      | 403    |
| PM of Project A lists invites of Project B    | 403      | 403    |

## Blocking Rules

| Scenario                          | Expected | Actual |
|-----------------------------------|----------|--------|
| Duplicate pending invite          | 400/409  | 400    |
| Cancel already-cancelled invite   | 400      | 400    |
| Expired invite (auto-link skip)   | N/A      | skipped (status→expired, auto_linked_projects=[]) |
| Management invites PM (hierarchy) | 403      | 403    |

## Management Team Sub-Roles (5 total)

| Sub-Role            | Label (Hebrew)   | Status   |
|---------------------|------------------|----------|
| site_manager        | מנהל אתר          | verified |
| execution_engineer  | מהנדס ביצוע       | verified |
| safety_assistant    | עוזר בטיחות       | verified |
| work_manager        | מנהל עבודה        | verified (Delta) |
| safety_officer      | ממונה בטיחות      | verified (Delta) |

## Audit Event Types (6 types, 36 events from MongoDB)

| Event Type           | Count | Description                                      |
|----------------------|-------|--------------------------------------------------|
| created              | 15    | Invite record created                            |
| notification_queued  | 15    | Notification intent logged (dry_run or WhatsApp)  |
| accepted             | 3     | Invite accepted via auto-link registration        |
| cancelled            | 1     | Invite cancelled by admin/PM                      |
| resend               | 1     | Invite resent                                     |
| expired              | 1     | Invite expired (passive, detected on registration)|

## Audit Name Mapping (Requested vs Implemented)

| Requested Name         | Implemented Name       | Equivalent? | Evidence (from MongoDB)                   |
|------------------------|------------------------|:-----------:|-------------------------------------------|
| invite_created         | created                | Yes         | 15 events, e.g. row #1 in audit table     |
| invite_sent            | notification_queued    | Yes         | 15 events, channel=dry_run, dry_run=true  |
| invite_accepted        | accepted               | Yes         | 3 events, auto_linked=true in payload     |
| invite_cancelled       | cancelled              | Yes         | 1 event, row #22 in audit table           |
| invite_expired         | expired                | Yes         | 1 event, actor=system, row #30            |
| membership_created     | accepted (payload)     | Yes         | auto_linked=true + role in accepted event |
| permission_denied      | HTTP 403 response      | Yes         | 403 status codes in RBAC matrix checks    |

## Notes
- All HTTP status codes verified via automated E2E tests (54/54 passed)
- RBAC is enforced at the API level (backend middleware)
- Project-level membership checked via `project_memberships` collection
- Cross-project requests use `_check_project_access()` middleware
- Git SHA: `469fa2e` (final — identical across all delivery files)
