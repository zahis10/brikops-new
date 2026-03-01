# M4.6 PROOF PACKAGE — Dynamic Project Trades & Required Field Asterisks
**Date**: 2026-02-18  
**Raw output file**: `LIVE_M46_OUTPUT.txt`

---

## 0) Version Lock

| Item | Value |
|------|-------|
| Git SHA (short) | `dc9c970` |
| Git SHA (full) | `dc9c9700a7d417d28f7b35a327dcc2e8c5a6d3fd` |
| GET /api/debug/version | `{"git_sha":"dc9c970","build_time":"2026-02-18T06:55:39","app_id":"contractor-ops-001"}` |
| SHA in frontend | Login page footer: `vdc9c970` (screenshot verified) + ProjectControlPage footer |

### Changed Files (M4.6)
```
backend/contractor_ops/router.py          — GET/POST /api/projects/{id}/trades + invite trade validation fix
frontend/src/components/ManagementPanel.js — AddCompanyForm + ManageInvitesForm: dynamic trades, "+ הוסף תחום חדש", asterisks
frontend/src/pages/ProjectControlPage.js  — AddCompanyForm + AddTeamMemberForm: dynamic trades, "+ הוסף תחום חדש", asterisks, prefill
frontend/src/pages/ProjectTasksPage.js    — "+ הוסף קבלן" CTA chip
frontend/src/services/api.js              — projectTrades.list() + projectTrades.create() API methods
replit.md                                 — Documentation updated
```

---

## 1) Custom Project Trades — E2E API Proof

### 1.1 API Proof (real IDs, real responses)

**Project A**: `c3e18b07-a7d8-411e-80f9-95028b15788a` (פרויקט מגדלי הים)  
**Project B**: `120651b1-683a-44b2-b5ff-73c646ebc81e` (פרויקט בדיקה B)

#### Step 1: GET trades BEFORE (14 base trades)
```
GET /api/projects/c3e18b07-a7d8-411e-80f9-95028b15788a/trades
Authorization: Bearer <admin_token>

Response (200):
{
  "trades": [
    {"key":"plumbing","label_he":"אינסטלטור","source":"global"},
    {"key":"aluminum","label_he":"אלומיניום","source":"global"},
    {"key":"bathroom_cabinets","label_he":"ארונות אמבטיה","source":"global"},
    {"key":"finishes","label_he":"גמרים","source":"global"},
    {"key":"doors","label_he":"דלתות","source":"global"},
    {"key":"glazing","label_he":"חלונות/זכוכית","source":"global"},
    {"key":"electrical","label_he":"חשמלאי","source":"global"},
    {"key":"general","label_he":"כללי","source":"global"},
    {"key":"hvac","label_he":"מיזוג","source":"global"},
    {"key":"metalwork","label_he":"מסגרות","source":"global"},
    {"key":"carpentry_kitchen","label_he":"נגרות/מטבח","source":"global"},
    {"key":"painting","label_he":"צבעי","source":"global"},
    {"key":"flooring","label_he":"ריצוף","source":"global"},
    {"key":"structural","label_he":"שלד","source":"global"}
  ]
}
>>> Count: 14 trades (all source=global)
```

#### Step 2: POST create "מעליות"
```
POST /api/projects/c3e18b07-a7d8-411e-80f9-95028b15788a/trades
Authorization: Bearer <admin_token>
Content-Type: application/json
Body: {"label_he":"מעליות"}

Response (200):
{
  "id": "97482861-85b9-43e9-871c-31007aa3578f",
  "project_id": "c3e18b07-a7d8-411e-80f9-95028b15788a",
  "key": "מעליות",
  "label_he": "מעליות",
  "created_by": "c452c225-8876-4a33-a69f-207145eeacb4",
  "created_at": "2026-02-18T06:52:38.481625+00:00"
}
```

#### Step 3: GET trades AFTER (15 = 14 global + 1 project)
```
GET /api/projects/c3e18b07-a7d8-411e-80f9-95028b15788a/trades

Response (200):
{
  "trades": [
    ... 14 global trades (source=global) ...,
    {"key":"מעליות","label_he":"מעליות","source":"project"}   ← NEW
  ]
}
>>> Count: 15 trades
>>> Project-specific: 1 (מעליות, source=project)
```

#### Step 4: POST duplicate "מעליות" → 409
```
POST /api/projects/c3e18b07-a7d8-411e-80f9-95028b15788a/trades
Body: {"label_he":"מעליות"}

Response (409):
{"detail":"תחום עם מפתח זה כבר קיים"}
```

### 1.2 Project Isolation Proof

"מעליות" exists in Project A but NOT in Project B:
```
GET /api/projects/120651b1-683a-44b2-b5ff-73c646ebc81e/trades

Response (200):
  Total trades in Project B: 14
  Contains מעליות: False ✓
  Project-specific trades: 0 ✓
```

---

## 2) UI Proof — "+ הוסף תחום חדש" in All Forms

**Note**: Screenshot tool cannot bypass login. Proof provided via code references + manual UAT steps.

### 2.1 Code Evidence — ManagementPanel AddCompanyForm
**File**: `frontend/src/components/ManagementPanel.js`
- **Lines 868-920**: `fetchTrades()` calls `api.projectTrades.list(projectId)` → loads from `/api/projects/{id}/trades`
- **Line 935**: Dropdown renders `tradeOptions` from API (14 base + custom)
- **Lines 941-972**: "+ הוסף תחום חדש" button → shows inline input → `handleAddTrade()` → POST to API → auto-selects new trade
- **Lines 918-920**: Asterisks: `שם חברה *`, `תחום *`, `שם איש קשר *`, `טלפון *`
- **Line 983**: Submit disabled: `disabled={saving || !name.trim() || !trade || !contactName.trim() || !contactPhone.trim()}`

### 2.2 Code Evidence — ManagementPanel ManageInvitesForm
**File**: `frontend/src/components/ManagementPanel.js`
- **Lines 1200-1240**: `fetchTrades()` for invite form → loads from `/api/projects/{id}/trades`
- **Line 1288**: `מספר טלפון *`
- **Line 1295**: `שם מלא *`
- **Line 1297**: `תפקיד *`
- **Line 1306**: `תת-תפקיד *` (when management_team)
- **Line 1317**: `תחום *` (when contractor)
- **Lines 1324-1353**: "+ הוסף תחום חדש" button + inline input + API creation
- **Line 1358**: Submit disabled until all required fields filled

### 2.3 Code Evidence — ProjectControlPage AddCompanyForm
**File**: `frontend/src/pages/ProjectControlPage.js`
- Same pattern: `fetchTrades()` loads from `/api/projects/{id}/trades`
- Asterisks on all 4 required fields
- "+ הוסף תחום חדש" inline creation
- Submit disabled until all fields filled

### 2.4 Code Evidence — ProjectControlPage AddTeamMemberForm
**File**: `frontend/src/pages/ProjectControlPage.js`
- Dynamic trades from project endpoint
- `תחום *` when role=contractor
- "+ הוסף תחום חדש" inline creation
- Trade prefill from URL param `prefillTrade`

### 2.5 Manual UAT Steps
1. Login as מנהל (admin) via quick-login
2. Navigate to any project → Management Panel (ניהול)
3. Click "הוסף חברה חדשה" → see asterisks on שם חברה*, תחום*, שם איש קשר*, טלפון*
4. In trade dropdown → scroll to bottom → see "+ הוסף תחום חדש"
5. Click it → type "מעליות" → click שמור → trade auto-selected
6. Go to Invites section → click "הזמנה חדשה"
7. Select role=contractor → trade dropdown appears with "מעליות" included
8. Same flow available in Project Control page (team tab)

---

## 3) "+ הוסף קבלן" CTA Proof

### 3.1 Code Evidence
**File**: `frontend/src/pages/ProjectTasksPage.js`
- **Lines 229-242**: Green `+ הוסף קבלן` chip rendered when user is admin/PM
- **Line 235**: `onClick` navigates to `/projects/${projectId}/control?openInvite=1&prefillTrade=${activeBucket || ''}`
- Only visible for admin/PM roles (RBAC check on line 229)

### 3.2 Prefill Flow
**File**: `frontend/src/pages/ProjectControlPage.js`
- URL params `openInvite=1` and `prefillTrade=<key>` are consumed
- Auto-opens team tab, opens AddTeamMemberForm, sets role=contractor and trade=prefillTrade

### 3.3 Invite with Custom Trade — API Proof
```
POST /api/projects/c3e18b07-a7d8-411e-80f9-95028b15788a/invites
Body: {"phone":"+972507777666","full_name":"דוד מעליות","role":"contractor","trade_key":"מעליות"}

Response (200):
{
  "id": "5edcea7b-0257-48de-9df3-0546fb732f8a",
  "project_id": "c3e18b07-a7d8-411e-80f9-95028b15788a",
  "target_phone": "+972507777666",
  "role": "contractor",
  "trade_key": "מעליות",     ← custom project trade accepted
  "full_name": "דוד מעליות",
  "status": "pending",
  "token": "K7vtsiMHtBQMIwVY-QAwpGHr4AWrqpnt8K2dJtgh2NY",
  "expires_at": "2026-02-25T06:56:35.036519+00:00"
}
```

### 3.4 Manual UAT Steps
1. Login as admin → Navigate to project tasks page
2. See bucket filter chips (חשמלאי, אינסטלטור, etc.)
3. Green `+ הוסף קבלן` chip at end of row
4. Click it → navigated to Project Control → Team tab → Invite form opens
5. Role = contractor, trade = pre-selected from active bucket filter

---

## 4) Required Fields Asterisks + Disabled Button

### 4.1 Companies Form — Asterisks
All 4 fields marked with `*`:
| Field | Label | Required |
|-------|-------|----------|
| Company name | שם חברה * | ✓ |
| Trade | תחום * | ✓ |
| Contact name | שם איש קשר * | ✓ |
| Contact phone | טלפון * | ✓ |

Submit button disabled until all filled: `disabled={saving || !name.trim() || !trade || !contactName.trim() || !contactPhone.trim()}`

### 4.2 Invite Form — Asterisks
| Field | Label | Condition | Required |
|-------|-------|-----------|----------|
| Phone | מספר טלפון * | Always | ✓ |
| Full name | שם מלא * | Always | ✓ |
| Role | תפקיד * | Always | ✓ |
| Sub-role | תת-תפקיד * | role=management_team | ✓ |
| Trade | תחום * | role=contractor | ✓ |

Submit button disabled: `disabled={creating || !newName.trim() || !newPhone.trim() || !newRole || (newRole === 'management_team' && !newSubRole) || (newRole === 'contractor' && !newTradeKey)}`

### 4.3 Backend 422 Validation (Hebrew)

```
POST company without contact_phone → HTTP 422
{"detail":"טלפון הוא שדה חובה"}

POST contractor invite without trade_key → HTTP 422
{"detail":"מקצוע הוא שדה חובה עבור קבלן"}
```

---

## 5) RBAC Proof

| Role | Action | HTTP Status | Expected | Result |
|------|--------|-------------|----------|--------|
| Owner/Admin | POST /projects/{id}/trades | 200 | 200 | ✓ PASS |
| Project Manager | POST /projects/{id}/trades | 200 | 200 | ✓ PASS |
| Contractor | POST /projects/{id}/trades | 403 | 403 | ✓ PASS |
| Viewer | POST /projects/{id}/trades | 403 | 403 | ✓ PASS |

### Raw responses:
```
Admin → 200: {"id":"...","key":"גנרטורים","label_he":"גנרטורים","source":"project"}
PM    → 200: {"id":"...","key":"מערכות שליטה","label_he":"מערכות שליטה","source":"project"}
Cont  → 403: {"detail":"Insufficient permissions"}
View  → 403: {"detail":"Insufficient permissions"}
```

---

## 6) Deliverables Checklist

| Deliverable | Status |
|-------------|--------|
| M46_PROOF.md | ✓ This file |
| LIVE_M46_OUTPUT.txt | ✓ 392 lines of raw API output |
| Git SHA | `dc9c970` |
| Bug fix: invite accepts custom project trades | ✓ Fixed during proof generation |
| 14→15 trades E2E | ✓ Verified |
| 409 duplicate | ✓ Verified |
| Project isolation | ✓ Verified (14 vs 15 across projects) |
| RBAC 200/403 | ✓ All 4 roles verified |
| 422 Hebrew validation | ✓ Verified |
| Invite with custom trade_key | ✓ Verified (מעליות accepted) |

---

## Bugfix Found During Proof

**Issue**: `POST /api/projects/{id}/invites` with `trade_key="מעליות"` (custom project trade) returned 422 "מקצוע לא תקין" because invite validation only checked against `BUCKET_LABELS` (14 global trades).

**Fix**: Updated invite endpoint (router.py line ~1799) to also check `project_trades` collection for project-specific custom trades before rejecting.

```python
# BEFORE (broken for custom trades):
if body.trade_key not in BUCKET_LABELS:
    raise HTTPException(422, detail=f'מקצוע לא תקין: {body.trade_key}')

# AFTER (supports custom project trades):
is_global = body.trade_key in BUCKET_LABELS
is_project = False
if not is_global:
    is_project = await db.project_trades.find_one({'project_id': project_id, 'key': body.trade_key}) is not None
if not is_global and not is_project:
    raise HTTPException(422, detail=f'מקצוע לא תקין: {body.trade_key}')
```

---

## 7) Invite Trade Isolation — Regression Tests

### 7.1 Test: Custom trade from Project A → invite in Project B (must fail 422)

```
POST /api/projects/<project_b>/invites
Body: {"phone":"+972508880005","full_name":"קבלן isolation","role":"contractor","trade_key":"בדיקת_regression"}

Status: 422
Response:
{
  "detail": "מקצוע לא תקין: בדיקת_regression"
}
```
Custom trade `בדיקת_regression` exists only in Project A — correctly rejected in Project B.

### 7.2 Test: Global trade in Project B (must succeed 200)

```
POST /api/projects/<project_b>/invites
Body: {"phone":"+972508880006","full_name":"קבלן גלובלי B","role":"contractor","trade_key":"plumbing"}

Status: 200
Response:
{
  "id": "f620687b-3acf-4afd-bd55-b0f88ad4f0c0",
  "project_id": "120651b1-683a-44b2-b5ff-73c646ebc81e",
  "target_phone": "+972508880006",
  "role": "contractor",
  "trade_key": "plumbing",
  "full_name": "קבלן גלובלי B",
  "status": "pending"
}
```
Global trade `plumbing` works in any project — correct.

---

## 8) Idempotency & Cleanup Proof — Back-to-Back Double Run

Tests use deterministic phones (`+972508880001`–`006`) with MongoDB cleanup fixture (delete before + after).

### Run 1:
```
tests/test_invite_custom_trade.py::TestInviteCustomTrade::test_invite_with_custom_project_trade_succeeds PASSED
tests/test_invite_custom_trade.py::TestInviteCustomTrade::test_invite_with_global_trade_still_works PASSED
tests/test_invite_custom_trade.py::TestInviteCustomTrade::test_invite_with_nonexistent_trade_rejected PASSED
tests/test_invite_custom_trade.py::TestInviteCustomTrade::test_invite_contractor_without_trade_rejected PASSED
tests/test_invite_custom_trade.py::TestInviteTradeIsolation::test_custom_trade_from_project_a_rejected_in_project_b PASSED
tests/test_invite_custom_trade.py::TestInviteTradeIsolation::test_global_trade_works_in_project_b PASSED

6 passed in 1.22s
```

### Run 2 (immediate back-to-back):
```
tests/test_invite_custom_trade.py::TestInviteCustomTrade::test_invite_with_custom_project_trade_succeeds PASSED
tests/test_invite_custom_trade.py::TestInviteCustomTrade::test_invite_with_global_trade_still_works PASSED
tests/test_invite_custom_trade.py::TestInviteCustomTrade::test_invite_with_nonexistent_trade_rejected PASSED
tests/test_invite_custom_trade.py::TestInviteCustomTrade::test_invite_contractor_without_trade_rejected PASSED
tests/test_invite_custom_trade.py::TestInviteTradeIsolation::test_custom_trade_from_project_a_rejected_in_project_b PASSED
tests/test_invite_custom_trade.py::TestInviteTradeIsolation::test_global_trade_works_in_project_b PASSED

6 passed in 1.23s
```

Both runs: **6/6 PASS**. Cleanup fixture ensures idempotency — no stale data between runs.

### Full suite: 58 passed, 9 skipped, 0 failures.

---

## Final acceptance: M4.6 complete

| Item | Value |
|------|-------|
| Git SHA | `34e0221` |
| Date | 2026-02-18 |
| Regression tests | 6/6 PASS (idempotent) |
| Full suite | 58 passed |
