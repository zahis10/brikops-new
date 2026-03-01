# PATCH PROOF — Production Ready Fixes

**Date:** 2026-02-17  
**Environment:** `https://1cee46ff-369f-4827-bc32-71cdcce76566-00-1uiioobquz03d.pike.replit.dev`

---

## 1. PM Scoped Notifications

### Before Fix
PM could see ALL notifications globally, including tasks from projects they are not a member of.

### After Fix
PM sees only notifications for tasks in projects where they have a `project_memberships` record.

### Proof

**PM membership:**
```
PM projects: ['8ccd582d-…', '35438577-…']
```

**PM global list — scoped:**
```
GET /api/notifications (PM token) → 200, count=6
All notification task_ids belong to projects: {'8ccd582d-…'}
All in scope: PASS
```

**PM with explicit task_id from non-member project:**
```
GET /api/notifications?task_id=4ba31882-… (PM) → 200, count=0
  SCOPED: PASS — 0 results (PM is NOT member of proof project)
```

**Owner still sees everything:**
```
GET /api/notifications?task_id=4ba31882-… (Owner) → 200, count=2
```

---

## 2. Absolute Image URL in Media Payload

### Before Fix
```json
"image_url": "/api/uploads/f2cc5e1b-…"
```

### After Fix
```json
"image_url": "https://1cee46ff-…/api/uploads/df5ff311-…"
```

### Proof — Full media_followup payload:
```json
{
  "id": "d75ac782-5476-4fdc-8989-b8d157bf2987",
  "task_id": "e8774a59-40aa-4f6f-af91-fc6c81b95654",
  "event_type": "media_followup",
  "target_phone": "+97250010000",
  "payload": {
    "task_id": "e8774a59-40aa-4f6f-af91-fc6c81b95654",
    "title": "בדיקת URL מוחלט",
    "description": "test absolute URL",
    "category": "כללי",
    "priority": "בינוני",
    "status": "פתוח",
    "project_name": "Sprint Proof — מגדלי הכרמל",
    "building_name": "בניין A",
    "floor_name": "1",
    "unit_no": "1",
    "assignee_name": "קבלן electrical",
    "task_link": "https://1cee46ff-369f-4827-bc32-71cdcce76566-00-1uiioobquz03d.pike.replit.dev/tasks/e8774a59-40aa-4f6f-af91-fc6c81b95654",
    "image_url": "https://1cee46ff-369f-4827-bc32-71cdcce76566-00-1uiioobquz03d.pike.replit.dev/api/uploads/df5ff311-f60a-4f32-972f-3b6f01d94372.png"
  },
  "status": "skipped_dry_run",
  "idempotency_key": "fe6c117f782455de6a1435664ce54858"
}
```

**image_url is absolute (https://…): PASS**

### Idempotency (repeated):
```
Follow-ups before 2nd upload: 1
Follow-ups after 2nd upload:  1
IDEMPOTENCY: PASS
```

---

## 3. Unified Release SHA

### Implementation
`_resolve_git_sha()` now checks `RELEASE_SHA` env var first, then falls back to `git rev-parse --short HEAD`.

### Proof
```json
GET /api/debug/version → 200
{
  "git_sha": "e94466e",
  "build_time": "2026-02-17T11:30:52.237759+00:00",
  "app_id": "contractor-ops-001",
  "feature_flags": {
    "app_mode": "dev",
    "whatsapp_enabled": false,
    "otp_provider": "mock",
    "owner_phone_set": false
  }
}
```

```
Git HEAD:   e94466e
API git_sha: e94466e
MATCH: PASS
```

For production release: set `RELEASE_SHA` env var to lock the version permanently.

---

## RBAC Matrix (Refreshed)

| Endpoint          | Owner | PM  | Contractor | Viewer |
|-------------------|-------|-----|------------|--------|
| List projects     | 200   | 200 | 200        | 200    |
| Hierarchy (own)   | 200   | 403*| 403        | 403    |
| Create task       | 200   | 403*| 403        | 403    |
| Notifications     | 200   | 200 | 403        | 403    |
| Hierarchy (other) | 200   | 403 | 403        | 403    |

*PM gets 403 on proof project (not a member) — CORRECT behavior.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/contractor_ops/router.py` | PM scoped notifications filter + RELEASE_SHA support |
| `backend/contractor_ops/notification_service.py` | `_make_absolute_url()` helper + applied to image_url |

## Test Status

**163/163 PASS** (44 E2E + 65 Notifications + 54 Onboarding)
