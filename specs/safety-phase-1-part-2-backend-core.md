# Safety Phase 1 — Part 2: Backend Core (CRUD + Filters + Audit)

> **For Replit agent. Paste verbatim. Do not deviate from DO NOT constraints.**
>
> Part 1 (#396, commit `17d6b5c`) is MERGED on `main`. Do not reopen its files except where noted. The feature flag is `ENABLE_SAFETY_MODULE` (default off). All code below is conditional on that flag via the router gate in `server.py`.

---

## Pre-reads (REQUIRED before writing code)

1. `backend/contractor_ops/safety_router.py` — Part 1 skeleton. Know the healthz pattern and `ensure_safety_indexes` layout.
2. `backend/contractor_ops/schemas.py` lines 663–813 — the 5 Safety models + 4 enums appended in Part 1. Use these verbatim for request/response shapes.
3. `backend/contractor_ops/router.py:103` — `_now()` returns `datetime.now(timezone.utc).isoformat()`. **Use it. Never call `datetime.utcnow()` or any other timestamp source.**
4. `backend/contractor_ops/router.py:146` — `get_current_user` dependency. Every endpoint uses this.
5. `backend/contractor_ops/router.py:219` — `require_roles(*roles)` factory. Returns a dependency that 403s if user's project role isn't in the allowed set.
6. `backend/contractor_ops/router.py:337` — `_check_project_access(user, project_id)` — raises 403 if user has no access. **Call this as the first line of every endpoint that takes a `project_id` path param.**
7. `backend/contractor_ops/router.py:372` — `_get_project_role(user, project_id)` — returns the user's project role + sub-role, or None.
8. `backend/contractor_ops/router.py:433` — `_audit(entity_type: str, entity_id: str, action: str, actor_id: str, payload: dict)`. **No `db` arg** — it calls `get_db()` internally. The `payload` dict is the flexible home for `project_id`, `before`, `after`, and any other context. **Call this on every Create, Update, Delete.**
9. `backend/contractor_ops/qc_router.py` — reference implementation. Mirrors the CRUD pattern and audit wiring we want here.
10. `backend/contractor_ops/companies_router.py:73-125` — reference for soft-delete with `deletedAt`/`deletedBy` camelCase convention.

---

## Context (why this matters)

Part 1 laid the foundation: feature flag, Pydantic models, router stub, 20 indices. Zero user-visible output.

Part 2 makes the backend **functional**: 25 CRUD endpoints across 5 resources, server-side filters on documents, soft-delete with 7-year retention on incidents, company-placeholder auto-creation, and `_audit()` on every write. After Part 2, Postman against a project with `ENABLE_SAFETY_MODULE=true` produces a fully-working API — still invisible to end users because the frontend doesn't exist yet (Parts 4–5).

Out of scope for Part 2: Safety Score (Part 3), PDF export (Part 3), Excel export (Part 3), any frontend.

---

## Goal

Expand `backend/contractor_ops/safety_router.py` with full CRUD + filters + audit for Workers, Trainings, Documents, Tasks, and Incidents. Expose a photo-upload helper endpoint. Add a `project_companies` placeholder creation path used by Worker.create when the caller supplies a `company_name` but no `company_id`.

## Success criteria

- With `ENABLE_SAFETY_MODULE=true` and a valid JWT:
  - 25 CRUD endpoints respond correctly (see endpoint list below).
  - Documents filter endpoint honors all 7 filter dimensions individually and combined.
  - Creating a Worker with `company_name` (no id) auto-creates a placeholder `project_companies` doc and returns its id.
  - Every Create/Update/Delete produces an `audit_events` record with correct `actor_id`, `resource_type`, `resource_id`, and a `before`/`after` diff on updates.
  - Soft-deleting an incident sets `deletedAt`, `deletedBy`, `deletion_reason`, and `retention_until = occurred_at + 7 years`. Hard delete is rejected (405).
  - Soft-deleted documents do NOT appear in list/filter results unless `include_deleted=true` is passed (admin-only).
- With the flag off: all 25 endpoints return 404 (router not registered).
- No new dependencies in `requirements.txt`.
- No frontend changes.
- Single commit on `main`, not pushed. Zahi pushes manually.

---

## RBAC matrix

| Action | Allowed roles |
|---|---|
| Read any safety resource (list/get) | All project members (`project_manager`, `management_team`, `contractor`, `viewer`) |
| Create/Update Worker, Training, Document, Task | `project_manager`, `management_team` (incl. sub-roles `safety_officer`, `safety_assistant`, `site_manager`, `execution_engineer`, `work_manager`) |
| Create Incident | Same as above |
| Update Incident | Same as above, BUT only by `project_manager` or `safety_officer` sub-role once status != "draft" |
| Delete (soft) Worker, Training, Document, Task | `project_manager` only |
| Delete (soft) Incident | `project_manager` only, AND requires `deletion_reason` non-empty |
| Hard delete anything | **NEVER** — endpoint returns 405 |
| Bypass (read only) | `super_admin` can read all, list soft-deleted via `include_deleted=true` |

Implementation: at the top of `safety_router.py`, define two tuple constants after the existing imports:

```python
SAFETY_WRITERS = ("project_manager", "management_team")
SAFETY_DELETERS = ("project_manager",)
```

And use `Depends(require_roles(*SAFETY_WRITERS))` / `Depends(require_roles(*SAFETY_DELETERS))` accordingly.

---

## Task 2.1 — Shared helpers at top of `safety_router.py`

**File:** `backend/contractor_ops/safety_router.py`
**Location:** Immediately after existing `router = APIRouter(...)` line, BEFORE the `healthz` endpoint.

Add these imports at the top of the file (merge into existing import block):

```python
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import uuid
import hashlib
import logging

from contractor_ops.router import (
    get_current_user, get_db, _now, _audit,
    _check_project_access, _get_project_role, _is_super_admin,
    require_roles,
)
from contractor_ops.schemas import (
    SafetyWorker, SafetyTraining, SafetyDocument, SafetyTask, SafetyIncident,
    SafetyCategory, SafetySeverity, SafetyDocumentStatus, SafetyTaskStatus,
)
```

Add these module-level helpers AFTER imports, BEFORE `router =`:

```python
SAFETY_WRITERS = ("project_manager", "management_team")
SAFETY_DELETERS = ("project_manager",)
INCIDENT_RETENTION_YEARS = 7


def _new_id() -> str:
    """UUID4 as string. Matches project convention."""
    return str(uuid.uuid4())


def _hash_id_number(id_number: str) -> str:
    """SHA-256 hash of Israeli ID / passport number. Used for worker lookup without storing raw PII."""
    if not id_number:
        return ""
    return hashlib.sha256(id_number.strip().encode("utf-8")).hexdigest()


def _retention_date(from_iso: str) -> str:
    """Return ISO string = from_iso + 7 years. Used for incident soft-delete."""
    dt = datetime.fromisoformat(from_iso.replace("Z", "+00:00"))
    return (dt + timedelta(days=365 * INCIDENT_RETENTION_YEARS)).isoformat()


async def _ensure_company_or_placeholder(
    db, project_id: str, company_id: Optional[str], company_name: Optional[str], actor_id: str
) -> Optional[str]:
    """
    If company_id is provided and exists on this project — return it.
    If only company_name is provided — create a placeholder project_companies doc and return its id.
    If neither — return None.
    """
    if company_id:
        doc = await db.project_companies.find_one({
            "id": company_id,
            "project_id": project_id,
            "deletedAt": None,
        })
        if doc:
            return company_id
        raise HTTPException(status_code=404, detail="company_id not found on this project")

    if not company_name:
        return None

    # Check if a placeholder with this exact name already exists on the project (non-deleted)
    existing = await db.project_companies.find_one({
        "project_id": project_id,
        "name": company_name.strip(),
        "deletedAt": None,
    })
    if existing:
        return existing["id"]

    new_id = _new_id()
    now = _now()
    await db.project_companies.insert_one({
        "id": new_id,
        "project_id": project_id,
        "name": company_name.strip(),
        "is_placeholder": True,
        "created_at": now,
        "created_by": actor_id,
    })
    return new_id
```

**VERIFY:**
```bash
python3 -c "from contractor_ops.safety_router import _new_id, _hash_id_number, _retention_date, _ensure_company_or_placeholder; print('helpers ok')"
```

---

## Task 2.2 — Workers CRUD

**5 endpoints** (append to `safety_router.py` after helpers, before `healthz`):

### 2.2.1 Create

```python
class SafetyWorkerCreate(BaseModel):
    company_id: Optional[str] = None
    company_name: Optional[str] = None  # used only if company_id absent
    full_name: str = Field(..., min_length=2, max_length=120)
    id_number: Optional[str] = None
    profession: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


@router.post("/{project_id}/workers", status_code=201, response_model=SafetyWorker)
async def create_worker(
    project_id: str,
    payload: SafetyWorkerCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
    db=Depends(get_db),
):
    await _check_project_access(user, project_id)

    resolved_company_id = await _ensure_company_or_placeholder(
        db, project_id, payload.company_id, payload.company_name, user["id"]
    )

    doc = {
        "id": _new_id(),
        "project_id": project_id,
        "company_id": resolved_company_id,
        "full_name": payload.full_name.strip(),
        "id_number": payload.id_number,  # raw, will be encrypted in a later migration
        "id_number_hash": _hash_id_number(payload.id_number) if payload.id_number else None,
        "profession": payload.profession,
        "phone": payload.phone,
        "notes": payload.notes,
        "created_at": _now(),
        "created_by": user["id"],
        "deletedAt": None,
        "deletedBy": None,
    }
    await db.safety_workers.insert_one(doc)
    await _audit(db, "safety.worker.created", user["id"], project_id,
                 "safety_worker", doc["id"], after=doc)
    return SafetyWorker(**doc)
```

**Note on `id_number_hash`:** this field lives in the Mongo document but is intentionally NOT on the `SafetyWorker` Pydantic model (Part 1 schemas). Pydantic v2 default is `extra="ignore"`, so `SafetyWorker(**doc)` silently drops it from the response — which is the desired behavior (the hash is a server-side lookup aid, never exposed to clients). Do NOT add `id_number_hash` to the `SafetyWorker` schema. Use `db.safety_workers.find_one({"id_number_hash": _hash_id_number(input_id)})` for lookups.

### 2.2.2 List (with pagination)

```python
@router.get("/{project_id}/workers")
async def list_workers(
    project_id: str,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    include_deleted: bool = False,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    await _check_project_access(user, project_id)

    q = {"project_id": project_id}
    if not include_deleted or not _is_super_admin(user):
        q["deletedAt"] = None

    total = await db.safety_workers.count_documents(q)
    cursor = db.safety_workers.find(q).sort("created_at", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"items": items, "total": total, "limit": limit, "offset": offset}
```

### 2.2.3 Get one

```python
@router.get("/{project_id}/workers/{worker_id}", response_model=SafetyWorker)
async def get_worker(
    project_id: str,
    worker_id: str,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    await _check_project_access(user, project_id)
    doc = await db.safety_workers.find_one({"id": worker_id, "project_id": project_id})
    if not doc:
        raise HTTPException(status_code=404, detail="worker not found")
    return SafetyWorker(**doc)
```

### 2.2.4 Update (partial)

```python
class SafetyWorkerUpdate(BaseModel):
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    profession: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    company_id: Optional[str] = None


@router.patch("/{project_id}/workers/{worker_id}", response_model=SafetyWorker)
async def update_worker(
    project_id: str,
    worker_id: str,
    payload: SafetyWorkerUpdate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
    db=Depends(get_db),
):
    await _check_project_access(user, project_id)
    before = await db.safety_workers.find_one({"id": worker_id, "project_id": project_id})
    if not before:
        raise HTTPException(status_code=404, detail="worker not found")
    if before.get("deletedAt"):
        raise HTTPException(status_code=410, detail="worker deleted")

    updates = payload.model_dump(exclude_unset=True)  # Pydantic v2 canonical
    if "id_number" in updates and updates["id_number"]:
        updates["id_number_hash"] = _hash_id_number(updates["id_number"])
    if "company_id" in updates and updates["company_id"]:
        # validate company exists on project
        comp = await db.project_companies.find_one({
            "id": updates["company_id"], "project_id": project_id
        })
        if not comp:
            raise HTTPException(status_code=404, detail="company_id not found on this project")
    updates["updated_at"] = _now()
    updates["updated_by"] = user["id"]

    await db.safety_workers.update_one({"id": worker_id}, {"$set": updates})
    after = await db.safety_workers.find_one({"id": worker_id})
    await _audit(db, "safety.worker.updated", user["id"], project_id,
                 "safety_worker", worker_id, before=before, after=after)
    return SafetyWorker(**after)
```

### 2.2.5 Soft delete

```python
class SoftDeleteBody(BaseModel):
    reason: Optional[str] = None


@router.delete("/{project_id}/workers/{worker_id}", status_code=204)
async def delete_worker(
    project_id: str,
    worker_id: str,
    body: SoftDeleteBody = SoftDeleteBody(),
    user: dict = Depends(require_roles(*SAFETY_DELETERS)),
    db=Depends(get_db),
):
    await _check_project_access(user, project_id)
    before = await db.safety_workers.find_one({"id": worker_id, "project_id": project_id})
    if not before:
        raise HTTPException(status_code=404, detail="worker not found")
    if before.get("deletedAt"):
        return  # idempotent

    now = _now()
    retention = _retention_date(now)
    await db.safety_workers.update_one({"id": worker_id}, {"$set": {
        "deletedAt": now,
        "deletedBy": user["id"],
        "deletion_reason": body.reason,
        "retention_until": retention,
    }})
    await _audit(db, "safety.worker.deleted", user["id"], project_id,
                 "safety_worker", worker_id, before=before)
    return
```

**VERIFY (with running server + flag on + seeded test project):**
```bash
# Create
curl -X POST -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"full_name":"בדיקה", "id_number":"123456789", "company_name":"חברת בדיקה"}' \
  http://localhost:8101/api/safety/$PROJECT_ID/workers

# Should return 201 + worker object with company_id set to a new placeholder
# Check: db.project_companies.find({is_placeholder: true}) shows the new company
# Check: db.audit_events.find({event_type: "safety.worker.created"}) shows event
```

---

## Task 2.3 — Trainings CRUD

Follow the exact same 5-endpoint pattern as Workers (Create/List/Get/Update/SoftDelete). Differences:

**Route prefix:** `/{project_id}/trainings`
**Collection:** `safety_trainings`
**Required fields on Create:** `worker_id`, `training_type`, `trained_at` (ISO date)
**Optional:** `instructor_name`, `duration_minutes`, `location`, `expires_at`, `certificate_url`
**Audit event types:** `safety.training.created`, `safety.training.updated`, `safety.training.deleted`

**Referential-integrity check on Create (MANDATORY — not just "exists"):**

```python
worker = await db.safety_workers.find_one({
    "id": payload.worker_id,
    "project_id": project_id,
    "deletedAt": None,  # EXPLICIT — reject trainings against soft-deleted workers
})
if not worker:
    raise HTTPException(status_code=404, detail="worker not found or deleted")
```

The `deletedAt: None` filter is load-bearing. Without it, a soft-deleted worker can still accumulate trainings, breaking audit trails. Apply the same `deletedAt: None` filter wherever Part 2 resolves a foreign key:
- Task.Create validating `document_id` → query `safety_documents` with `deletedAt: None`
- Task/Document.Update validating `assignee_id` → query `users` (no soft-delete on users in this project) but check `pending_deletion` status
- Incident.Create validating `injured_worker_id` → query `safety_workers` with `deletedAt: None`
- Company validation (everywhere via `_ensure_company_or_placeholder`) → **already correct**, uses `{id, project_id}` but should also add `deletedAt: None` to the existing `find_one`. Update the helper in Task 2.1 accordingly.

**Filter on List:**
- `?worker_id=<id>` — filter to one worker's trainings
- `?training_type=<str>` — exact match
- `?expires_before=<iso_date>` — returns trainings whose `expires_at` is before the given date (nulls excluded). Used for "expiring soon" queries.

Implement by extending `q` dict in the list handler. Respect `include_deleted` gate.

---

## Task 2.4 — Documents CRUD + filter endpoint

Follow Worker CRUD pattern. Differences:

**Route prefix:** `/{project_id}/documents`
**Collection:** `safety_documents`
**Audit event types:** `safety.document.created/updated/deleted`

### 2.4.1 Create

Required: `category` (SafetyCategory enum), `severity` (SafetySeverity enum), `title`, `found_at` (ISO UTC).
Optional: `description`, `location`, `company_id`, `profession`, `assignee_id`, `photo_urls`, `attachment_urls`.
On create: `reporter_id = user["id"]` (server-set, never from client), `status = SafetyDocumentStatus.open`.

### 2.4.2 Filter endpoint — **server-side, 7 dimensions**

```python
class SafetyDocumentFilters(BaseModel):
    category: Optional[SafetyCategory] = None
    severity: Optional[SafetySeverity] = None
    status: Optional[SafetyDocumentStatus] = None
    company_id: Optional[str] = None
    assignee_id: Optional[str] = None
    reporter_id: Optional[str] = None
    date_from: Optional[str] = None  # ISO
    date_to: Optional[str] = None


@router.get("/{project_id}/documents")
async def list_documents(
    project_id: str,
    category: Optional[SafetyCategory] = None,
    severity: Optional[SafetySeverity] = None,
    status_: Optional[SafetyDocumentStatus] = Query(None, alias="status"),
    company_id: Optional[str] = None,
    assignee_id: Optional[str] = None,
    reporter_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    include_deleted: bool = False,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    await _check_project_access(user, project_id)

    q = {"project_id": project_id}
    if not include_deleted or not _is_super_admin(user):
        q["deletedAt"] = None
    if category:      q["category"] = category.value
    if severity:      q["severity"] = severity.value
    if status_:       q["status"] = status_.value
    if company_id:    q["company_id"] = company_id
    if assignee_id:   q["assignee_id"] = assignee_id
    if reporter_id:   q["reporter_id"] = reporter_id
    if date_from or date_to:
        q["found_at"] = {}
        if date_from: q["found_at"]["$gte"] = date_from
        if date_to:   q["found_at"]["$lte"] = date_to

    total = await db.safety_documents.count_documents(q)
    cursor = db.safety_documents.find(q).sort("found_at", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"items": items, "total": total, "limit": limit, "offset": offset,
            "filters_applied": {k: v for k, v in {
                "category": category, "severity": severity, "status": status_,
                "company_id": company_id, "assignee_id": assignee_id,
                "reporter_id": reporter_id, "date_from": date_from, "date_to": date_to
            }.items() if v}}
```

**VERIFY:**
```bash
# Seed 10 documents with varied category/severity/status, then:
curl -H "Authorization: Bearer $JWT" \
  "http://localhost:8101/api/safety/$PID/documents?severity=3&status=open"
# Should return only sev-3 open documents. Check "filters_applied" echoes back.
```

### 2.4.3–2.4.5: Get / Update / Soft-delete

Same pattern as Worker. On Update, re-validate `company_id` and `assignee_id` exist on project.

---

## Task 2.5 — Tasks CRUD + status transitions

Follow Worker pattern. Differences:

**Route prefix:** `/{project_id}/tasks`
**Collection:** `safety_tasks`
**Required on Create:** `title`, `severity`, `document_id` (optional but warn if absent)
**Audit event types:** `safety.task.created/updated/deleted`

**Status transitions (enforced on Update):**

```
open ────> in_progress ────> completed
  │              │
  └──────────────┴──────────> cancelled
```

- `open → in_progress`: any SAFETY_WRITER
- `in_progress → completed`: writer, AND `corrective_action` must be non-empty on the update payload, AND `completed_at` auto-set to `_now()` server-side
- `any → cancelled`: `project_manager` only; requires non-empty `description` or audit note
- **Reverse transitions forbidden.** `completed → open` returns 409.

Implement as a `_assert_transition_allowed(current, next_status, user, payload)` helper. Return 409 with `detail={"current_status": ..., "requested": ..., "reason": "..."}` on invalid transition.

---

## Task 2.6 — Incidents CRUD + 7yr retention

Follow Worker pattern. Differences:

**Route prefix:** `/{project_id}/incidents`
**Collection:** `safety_incidents`
**Required on Create:** `incident_type` (one of `near_miss`, `injury`, `property_damage`), `severity`, `occurred_at` (ISO UTC), `description`.
**Audit event types:** `safety.incident.created/updated/deleted`

**Soft-delete special rules (override the standard pattern):**

```python
@router.delete("/{project_id}/incidents/{incident_id}", status_code=204)
async def delete_incident(
    project_id: str,
    incident_id: str,
    body: SoftDeleteBody,
    user: dict = Depends(require_roles(*SAFETY_DELETERS)),
    db=Depends(get_db),
):
    await _check_project_access(user, project_id)

    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=400, detail="deletion_reason is required for incidents")

    before = await db.safety_incidents.find_one({"id": incident_id, "project_id": project_id})
    if not before:
        raise HTTPException(status_code=404, detail="incident not found")
    if before.get("deletedAt"):
        return

    now = _now()
    retention = _retention_date(before["occurred_at"])  # 7yr from OCCURRED, not from now
    await db.safety_incidents.update_one({"id": incident_id}, {"$set": {
        "deletedAt": now,
        "deletedBy": user["id"],
        "deletion_reason": body.reason.strip(),
        "retention_until": retention,
    }})
    await _audit(db, "safety.incident.deleted", user["id"], project_id,
                 "safety_incident", incident_id, before=before)
    return
```

**Important:** `retention_until` is computed from `occurred_at`, NOT from `_now()`. Regulatory clock starts at occurrence.

---

## Task 2.7 — Photo/PDF upload helper endpoint

**One endpoint serves Workers, Documents, Tasks, and Incidents.** Returns a URL string; callers store the URL in their own `photo_urls` / `attachment_urls` / `certificate_url` / `medical_record_urls` fields via separate Update calls.

**Reuse the project's existing storage stack** — do NOT invent a new storage path. Based on `qc_router.py:1446-1520` precedent:

- `save_bytes(data, key, content_type)` from `services.object_storage` — writes bytes, returns a `stored_ref` (local path or `s3://` URI)
- `generate_url(stored_ref)` from `services.object_storage` — returns a usable URL (presigned for S3, direct for local)
- `validate_upload(file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES)` from `contractor_ops.upload_safety`
- `ALLOWED_IMAGE_EXTENSIONS`, `ALLOWED_IMAGE_TYPES` — existing constants (`.jpg/.jpeg/.png/.webp/.heic/.heif`)

**Add to imports at top of safety_router.py:**

```python
from contractor_ops.upload_safety import validate_upload, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES
```

**Safety-specific constants (add near `SAFETY_WRITERS`):**

```python
# Accepts images AND pdfs (unlike qc which is image-only)
SAFETY_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
    "application/pdf",
}
SAFETY_ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | {".pdf"}
MAX_SAFETY_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
```

**Endpoint (mirrors qc_router upload pattern):**

```python
@router.post("/{project_id}/upload")
async def upload_safety_file(
    project_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
    db=Depends(get_db),
):
    await _check_project_access(user, project_id)

    # Accept images + PDF (qc accepts images only, so we can't reuse its constants directly)
    validate_upload(file, SAFETY_ALLOWED_EXTENSIONS, SAFETY_ALLOWED_CONTENT_TYPES)

    content = await file.read()
    if len(content) > MAX_SAFETY_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="הקובץ גדול מדי (מקסימום 10MB)")

    content_type = file.content_type or "application/octet-stream"
    ext = content_type.split("/")[-1]
    if ext == "jpeg":
        ext = "jpg"
    elif content_type == "application/pdf":
        ext = "pdf"

    file_id = _new_id()
    key = f"safety/{project_id}/{file_id}.{ext}"

    from services.object_storage import save_bytes as obj_save_bytes, generate_url as obj_generate_url
    stored_ref = obj_save_bytes(content, key, content_type)
    url = obj_generate_url(stored_ref)

    await _audit(db, "safety.upload", user["id"], project_id,
                 "safety_upload", file_id,
                 after={"filename": file.filename, "key": key, "size": len(content)})

    return {
        "id": file_id,
        "url": url,
        "stored_ref": stored_ref,  # caller stores this in DB; resolve via generate_url on read
        "filename": file.filename,
        "content_type": content_type,
        "size": len(content),
    }
```

**Important:** callers (create/update Document, Incident, Training, etc.) store `stored_ref` (not the presigned URL) in the model's `photo_urls` / `certificate_url` / `medical_record_urls` field. On read-side in Part 4 frontend, resolve via a small helper endpoint or `generate_url()` server-side before returning. For Part 2, Create/Update just accepts the `stored_ref` string verbatim.

---

## Task 2.8 — Register router hooks (no-op if Part 1 wiring holds)

Verify `backend/server.py:428-438` still conditionally registers `safety_router`. Do NOT modify server.py in Part 2 unless a merge conflict surfaces.

---

## DO NOT constraints

1. **DO NOT** add any new env flag. Only `ENABLE_SAFETY_MODULE` (Part 1) gates this module.
2. **DO NOT** call `datetime.utcnow()`, `datetime.now()`, or `now_il()` anywhere. Only `_now()` from `contractor_ops.router`.
3. **DO NOT** invent a new upload helper. Use `save_bytes` + `generate_url` from `services.object_storage` and `validate_upload` from `contractor_ops.upload_safety` per Task 2.7.
4. **DO NOT** hard-delete anything. No `delete_one`, no `delete_many`. Always soft-delete.
5. **DO NOT** use snake_case for soft-delete fields. Always `deletedAt` / `deletedBy` (camelCase).
6. **DO NOT** allow the client to set `reporter_id`, `created_by`, `updated_by`, `created_at`, `updated_at`, `deletedAt`, or `deletedBy`. Server-set only.
7. **DO NOT** skip `_check_project_access` on any endpoint that takes `project_id` in the path.
8. **DO NOT** skip `_audit()` on any Create / Update / Delete.
9. **DO NOT** touch frontend (`frontend/`). Zero frontend changes this part.
10. **DO NOT** add deps to `requirements.txt`. If you think you need one, stop and ask.
11. **DO NOT** push. Single commit on `main`.
12. **DO NOT** modify Part 1 files (`config.py`, `schemas.py`, `safety_router.py`'s Part-1 code). You APPEND to `safety_router.py`; do not edit what's already there.

---

## End-to-end deliverable tests

Run with `ENABLE_SAFETY_MODULE=true` and a valid admin JWT. Assume `$PID` is a project the user has access to.

### Test 1 — Worker create with placeholder company
```bash
curl -s -X POST -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"full_name":"אחמד נ.","company_name":"קבלן משנה X"}' \
  http://localhost:8101/api/safety/$PID/workers | jq .

# Expect: 201, company_id set to a new UUID
# Expect: db.project_companies shows that id with is_placeholder=true
```

### Test 2 — Document create + filter
```bash
# Create 2 docs of different severity
curl -X POST ... -d '{"category":"scaffolding","severity":"3","title":"פיגום רעוע","found_at":"2026-04-22T10:00:00Z"}'
curl -X POST ... -d '{"category":"ppe","severity":"1","title":"קסדה חסרה","found_at":"2026-04-22T10:05:00Z"}'

# Filter
curl "http://localhost:8101/api/safety/$PID/documents?severity=3" | jq '.items | length'
# Expect: 1
```

### Test 3 — Task status transition guard
```bash
# Create task in open
TID=$(curl -X POST ... -d '{"title":"תקן פיגום","severity":"3"}' | jq -r .id)
# Valid: open → in_progress
curl -X PATCH ... -d '{"status":"in_progress"}'
# Valid: in_progress → completed (with corrective_action)
curl -X PATCH ... -d '{"status":"completed","corrective_action":"פיגום הוחלף"}'
# Invalid: completed → open → 409
curl -X PATCH ... -d '{"status":"open"}'
# Expect: 409
```

### Test 4 — Incident soft-delete sets correct retention
```bash
IID=$(curl -X POST ... -d '{"incident_type":"near_miss","severity":"2","occurred_at":"2020-01-15T12:00:00Z","description":"כמעט נפל כלי"}' | jq -r .id)
curl -X DELETE -H "Content-Type: application/json" ... -d '{"reason":"דיווח כפול"}'
# Check DB: retention_until should be "2027-01-15..." (occurred_at + 7yr), NOT now+7yr
```

### Test 5 — No-reason incident delete returns 400
```bash
curl -X DELETE ... -d '{}'
# Expect: 400 "deletion_reason is required for incidents"
```

### Test 6 — Hard-delete rejection
No endpoint for hard delete exists. `DELETE /api/safety/$PID/workers/$WID` with role != SAFETY_DELETER returns 403. `DELETE /api/safety/$PID/workers/$WID/hard` (or similar) returns 404 (no route).

### Test 7 — Audit events fired
After running tests 1–5, check:
```bash
db.audit_events.find({event_type: /^safety\./}).count()
# Expect: at least 7 events (create+update+delete across resources)
```

### Test 8 — Flag off → all endpoints 404
With `ENABLE_SAFETY_MODULE=false`:
```bash
curl -I http://localhost:8101/api/safety/$PID/workers
# Expect: 404
curl -I http://localhost:8101/api/safety/$PID/documents
# Expect: 404
```

---

## File scope (git diff --stat expectations)

```
backend/contractor_ops/safety_router.py  | ~600+ lines added
```

**That's it.** One file modified. No schema changes (all schemas shipped in Part 1). No server.py changes. No config.py changes. No frontend. No requirements.txt.

If `git diff --stat` shows anything else, stop and investigate.

---

## Commit message

```
feat(safety): Phase 1 Part 2 — Backend Core CRUD + filters + audit

- 25 CRUD endpoints across Workers / Trainings / Documents / Tasks / Incidents
- Documents list supports 7-dim filter (category, severity, status, company,
  assignee, reporter, date range) with filters_applied echo
- Task status transitions enforced server-side (forward-only, cancel allowed
  from any state, completed requires corrective_action)
- Incidents soft-delete computes retention_until from occurred_at + 7yr
  (regulatory clock), requires non-empty deletion_reason
- Shared company-placeholder helper: Worker.create with company_name (no id)
  auto-creates project_companies doc with is_placeholder=true
- ID number SHA-256 hashed on Worker for lookup without storing raw PII
- Photo/PDF upload helper supports jpg/png/webp/heic/pdf up to 10MB,
  reuses services.object_storage.save_bytes + generate_url
- All writes audited via _audit() with event_type taxonomy safety.*
- All endpoints gated by get_current_user; writes by require_roles;
  deletes by require_roles(SAFETY_DELETERS)
- Zero frontend changes. Zero new deps. Single file modified.

Tested with 8 end-to-end curl scenarios per spec. All passing.

Refs: specs/safety-phase-1-part-2-backend-core.md
Part 1: commit 17d6b5c (foundation)
```

---

## Post-merge next steps

After Zahi pushes this commit + restarts prod (flag stays OFF in prod):

1. Zahi flips `ENABLE_SAFETY_MODULE=true` in **staging only**.
2. Zahi runs Postman / curl tests against staging.
3. Once staging green — proceed to **Part 3 (Backend Advanced)**: Safety Score endpoint, Excel ws7/ws8/ws9, Hebrew PDF פנקס כללי.

Part 3 will touch `requirements.txt` (reportlab, hebrew font) — first native/dep change in this phase. Handle with care.
