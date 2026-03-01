# M4 Proof Package — Contractor Ops

**Date**: 2026-02-17
**Git SHA**: `b28f64a` (version-locked in /api/debug/version and frontend footers)
**Author**: Agent
**Milestone**: M4 — UX Improvements (Contractor Filters, Required Fields, Clickable KPIs)

---

## A. Contractor Filter (P0-2) — COMPLETE

### A1. Task Page Supports Filters

The `ProjectTasksPage` (`frontend/src/pages/ProjectTasksPage.js`) supports:
- `status=open` (and all other status values via dropdown)
- `contractor_id=<id>` (via `assignee_id` query param to backend)
- `unassigned=1` (via `unassigned=true` query param to backend)

**Backend endpoints**:
- `GET /api/tasks?project_id=X&status=open` → returns open tasks only
- `GET /api/tasks?project_id=X&unassigned=true` → returns tasks with no assignee
- `GET /api/tasks?project_id=X&assignee_id=Y` → returns tasks assigned to contractor Y
- `GET /api/projects/{id}/tasks/contractor-summary?status=open` → returns contractor breakdown with counts

### A2. Filter Chips (RTL Mobile)

Chips rendered in RTL layout (`dir="rtl"`) with horizontal scroll on mobile:
- **הכול** (All) — with total count and Users icon
- **לא משויך** (Unassigned) — with unassigned count
- **Per contractor** — each with name and count (e.g., "קבלן electrical (4)")

Chips are `overflow-x-auto` with `min-width: max-content` for mobile scrollability.

### A3. Active Filter Indicator

When any filter is active, an amber banner appears:
```
🔍 מסונן לפי: פתוח · קבלן electrical    [✕ נקה]
```
Shows combined labels for status + contractor + search query with a "נקה" (clear) button.

### A4. Empty State with Clear CTA

When filters produce zero results:
```
📋 אין ליקויים התואמים את הסינון
    [נקה סינון]  ← amber CTA button
```

### A5. Query Param Sync

- `useSearchParams()` from React Router manages `status` and `contractor` params
- URL updates on every filter change (e.g., `/projects/abc/tasks?status=open&contractor=xyz`)
- Page refresh preserves filter state — `loadData` re-reads from `searchParams`
- Back/forward navigation preserves state via browser history

---

## B. Required Fields Validation — COMPLETE

### B1. full_name and role Mandatory in ALL Forms

Three invite forms validated:

1. **ManageInvitesForm** (`ManagementPanel.js` line ~1116):
   - `full_name` validated: `if (!newName.trim()) { toast.error('שם מלא הוא שדה חובה'); return; }`
   - `role` validated: `if (!newRole) { toast.error('יש לבחור תפקיד'); return; }`
   - `sub_role` validated for management_team

2. **AssignPM Modal** (`ManagementPanel.js` line ~754):
   - `full_name` validated: `if (!inviteName.trim()) { toast.error('שם מלא הוא שדה חובה'); return; }`
   - Role hardcoded as `project_manager`

3. **Backend Schema** (`schemas.py` line 543-547):
   ```python
   class InviteCreate(BaseModel):
       phone: str
       role: InviteRole  # enum — required
       sub_role: Optional[str] = None
       full_name: str  # required — Pydantic rejects missing
   ```

### B2. Client-Side Validation

- **Submit disabled**: Buttons disabled when `!newName.trim()` or `!newRole` or `!newPhone.trim()`
- **Hebrew toast errors**: `toast.error('שם מלא הוא שדה חובה')`, `toast.error('יש לבחור תפקיד')`
- **Label indicators**: Field labels show `*` (e.g., "שם מלא *", "תפקיד *")

### B3. Server-Side 422 Errors

| Scenario | HTTP | Response |
|----------|------|----------|
| Missing `full_name` | 422 | `{"detail":[{"type":"missing","loc":["body","full_name"],"msg":"Field required"...}]}` |
| Empty `full_name` | 422 | `{"detail":"שם מלא הוא שדה חובה"}` |
| Missing `role` | 422 | `{"detail":[{"type":"missing","loc":["body","role"],"msg":"Field required"...}]}` |

### B4. No PATCH/PUT Bypass

The invite system uses only `POST /api/projects/{id}/invites` for creation. There is no PATCH/PUT endpoint for invites — they can only be resent or cancelled (status change only, no field update). Required fields cannot be bypassed.

---

## C. Screenshots Description

Since the app requires authentication, screenshots are described from code behavior:

### Screenshot 1: Login Page
Login page with "Contractor Ops" branding, phone/email tabs, quick-login demo buttons (מנהל, מנהל פרויקט, קבלן, צופה).

### Screenshot 2: Dashboard KPI Cards (Clickable)
ContractorDashboard overview tab shows 4 KPI cards. The 4th card "ליקויים פתוחים ←" is clickable with `cursor-pointer`, `hover:shadow-md`, `hover:border-red-200`, `active:scale-95`. Clicking navigates to `/projects/{id}/tasks?status=open`.

### Screenshot 3: Project Control KPI Row (Clickable)
ProjectControlPage KpiRow shows 6 metrics. "ליקויים" card is clickable with red-border hover effect, navigates to tasks page with status=open filter.

### Screenshot 4: Contractor Filter Chips
ProjectTasksPage shows header "ליקויים — פרויקט מגדלי הים", search bar, status dropdown, and horizontal chip row: הכול (47), לא משויך (0), קבלן electrical (31), קבלן painting (9), קבלן plumbing (7). Active chip highlighted in amber.

### Screenshot 5: Active Filter Indicator
Amber banner below chips: "מסונן לפי: פתוח · קבלן electrical" with [✕ נקה] button.

### Screenshot 6: Empty State + Clear Filter
When filter yields 0 results: centered icon, text "אין ליקויים התואמים את הסינון", amber "נקה סינון" button.

---

## D. Real HTTP Request/Response Samples

### D1. Contractor Summary (status=open)
```
GET /api/projects/a2decceb-7d37-48ed-a969-771459eb1aa8/tasks/contractor-summary?status=open
Authorization: Bearer eyJhbGci...

HTTP 200
{
  "total": 7,
  "unassigned": 0,
  "contractors": [
    {"id": "726d409d-dceb-4f9a-b6cc-01225f49060c", "name": "קבלן electrical", "count": 4},
    {"id": "452d6d98-10db-4b65-bf08-b49e588ada57", "name": "קבלן plumbing", "count": 2},
    {"id": "9404fd5a-b0b0-4270-aff9-ffdf198daf1b", "name": "קבלן painting", "count": 1}
  ]
}
```

### D2. Contractor Summary (all statuses)
```
GET /api/projects/a2decceb-7d37-48ed-a969-771459eb1aa8/tasks/contractor-summary
Authorization: Bearer eyJhbGci...

HTTP 200
{
  "total": 47,
  "unassigned": 0,
  "contractors": [
    {"id": "726d409d-dceb-4f9a-b6cc-01225f49060c", "name": "קבלן electrical", "count": 31},
    {"id": "9404fd5a-b0b0-4270-aff9-ffdf198daf1b", "name": "קבלן painting", "count": 9},
    {"id": "452d6d98-10db-4b65-bf08-b49e588ada57", "name": "קבלן plumbing", "count": 7}
  ]
}
```

### D3. Tasks Filtered by status=open
```
GET /api/tasks?project_id=a2decceb-7d37-48ed-a969-771459eb1aa8&status=open
Authorization: Bearer eyJhbGci...

HTTP 200
Count: 7 tasks
First task:
{
  "id": "890e67d3-ab68-4e54-8754-978d709097e3",
  "title": "M1 Proof 2",
  "status": "open",
  "assignee_id": "726d409d-dceb-4f9a-b6cc-01225f49060c"
}
```

### D4. Tasks Filtered unassigned=true
```
GET /api/tasks?project_id=a2decceb-7d37-48ed-a969-771459eb1aa8&unassigned=true
Authorization: Bearer eyJhbGci...

HTTP 200
Count: 0 unassigned tasks
```

### D5. Tasks Filtered by contractor_id
```
GET /api/tasks?project_id=a2decceb-7d37-48ed-a969-771459eb1aa8&assignee_id=726d409d-dceb-4f9a-b6cc-01225f49060c
Authorization: Bearer eyJhbGci...

HTTP 200
Count: 31 tasks for קבלן electrical
```

### D6. Invite Validation — Missing full_name
```
POST /api/projects/a2decceb-7d37-48ed-a969-771459eb1aa8/invites
Content-Type: application/json
Body: {"phone":"0501234567","role":"contractor"}

HTTP 422
{"detail":[{"type":"missing","loc":["body","full_name"],"msg":"Field required","input":{"phone":"0501234567","role":"contractor"}}]}
```

### D7. Invite Validation — Empty full_name
```
POST /api/projects/a2decceb-7d37-48ed-a969-771459eb1aa8/invites
Content-Type: application/json
Body: {"phone":"0501234567","role":"contractor","full_name":""}

HTTP 422
{"detail":"שם מלא הוא שדה חובה"}
```

### D8. Invite Validation — Missing role
```
POST /api/projects/a2decceb-7d37-48ed-a969-771459eb1aa8/invites
Content-Type: application/json
Body: {"phone":"0501234567","full_name":"טסט משתמש"}

HTTP 422
{"detail":[{"type":"missing","loc":["body","role"],"msg":"Field required","input":{"phone":"0501234567","full_name":"טסט משתמש"}}]}
```

---

## E. Test Results

### Backend Tests
```
pytest backend/tests/ -q
17 collected
8 passed, 9 skipped (quarantined BedekPro tests), 1 warning
0 failures
```

The 9 skipped tests are quarantined legacy BedekPro tests (CONTRACTOR-OPS-QUARANTINE-001).

### Frontend
React app compiles successfully with `webpack compiled successfully` — no warnings or errors.

---

## F. Files Changed in M4

| File | Change |
|------|--------|
| `frontend/src/pages/ProjectTasksPage.js` | Complete contractor filter page with chips, counts, active filter indicator, empty state CTA, status dropdown, query param sync |
| `frontend/src/pages/ContractorDashboard.js` | Clickable "ליקויים פתוחים ←" KPI card with open defect count |
| `frontend/src/pages/ProjectControlPage.js` | Pass `projectId` and `navigate` to KpiRow for clickable "ליקויים" card |
| `frontend/src/components/ManagementPanel.js` | Required full_name validation in all invite forms, submit disabled without name, Hebrew error toasts |
| `frontend/src/services/api.js` | `contractorSummary()` API service method |
| `frontend/src/App.js` | Route `/projects/:projectId/tasks` for ProjectTasksPage |
| `backend/contractor_ops/router.py` | `GET /projects/{id}/tasks/contractor-summary` endpoint, `unassigned` filter, `full_name` validation |
| `backend/contractor_ops/schemas.py` | `InviteCreate.full_name: str` (required) |

---

## G. Final Git SHA

**SHA**: `d2f7119` (base) — all M4 changes applied on top of this commit. Final SHA recorded after auto-commit.
