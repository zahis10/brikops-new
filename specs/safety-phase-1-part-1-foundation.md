# Safety Phase 1 — Part 1: Foundation

**For:** Replit agent · **Paste as-is.** · **Language:** עברית + code comments in Hebrew/English.
**Est effort:** 2-3 hours · **Branch:** `feature/safety-phase-1-part-1`
**Depends on:** nothing · **Blocks:** Part 2

---

## ⚠️ Pre-reads (REQUIRED — read before coding)

1. **Design system (canonical design rules — DO NOT deviate):**
   `specs/safety-design-system.md`

2. **Master plan (overall context):**
   `specs/safety-phase-1-master-plan.md`

3. **Existing patterns to mimic (reference only — do NOT copy verbatim):**
   - `backend/contractor_ops/qc_router.py:1-60` — how a domain router is structured
   - `backend/contractor_ops/stepup_service.py:352-358` — how `ensure_indexes` is patterned
   - `backend/contractor_ops/companies_router.py:73-120` — `project_companies` CRUD + `deletedAt` soft-delete convention

---

## 🎯 Goal of Part 1

Lay foundation for the Safety module **without exposing any user-facing functionality yet.**

**Success = all of these true:**
- `GET /api/safety/healthz` returns `200 {"ok": true, "module": "safety", "enabled": <bool>}` when `ENABLE_SAFETY_MODULE=true`.
- Same endpoint returns `404` when flag is off (router not registered).
- MongoDB indices for 5 new safety collections + 6 new fields on `project_companies` exist after first startup.
- Zero user-visible changes. Zero changes to existing endpoints.
- No native build triggers hit (pure Python + config).

---

## 📋 Scope — 4 sub-tasks

| # | Sub-task | Files touched |
|---|----------|---------------|
| 1.1 | Feature flag `ENABLE_SAFETY_MODULE` | `backend/config.py` |
| 1.2 | Safety Pydantic base schemas (data models only) | `backend/contractor_ops/schemas.py` |
| 1.3 | `safety_router.py` stub + `ensure_safety_indexes()` | NEW `backend/contractor_ops/safety_router.py` |
| 1.4 | Conditional router wiring + startup indices | `backend/server.py` |

---

## 🛑 DO NOT — hard constraints

- **DO NOT** add `safety_officer` or `safety_assistant` to `ManagementSubRole` — **they already exist** at `backend/contractor_ops/schemas.py:34,36`. Just reference them.
- **DO NOT** create a separate `contractor_companies` collection. We reuse `project_companies` (extended in Part 2).
- **DO NOT** implement any CRUD endpoints in Part 1. Only `healthz`. Everything else is Part 2.
- **DO NOT** change existing collection schemas. The 6 new fields on `project_companies` are added via index-creation side effect (future writes populate), not via a `$set` migration on existing docs.
- **DO NOT** use snake_case for soft-delete fields — the project convention is `deletedAt` / `deletedBy` (camelCase). Stay consistent. All other new fields can be snake_case per Python style.
- **DO NOT** register the safety router unconditionally. It must be gated by `ENABLE_SAFETY_MODULE`.
- **DO NOT** auto-enable the flag in production. Default MUST be `false`.
- **DO NOT** add new dependencies to `requirements.txt` in Part 1. Reportlab + noto-sans-hebrew come in Part 3.
- **DO NOT** touch the frontend in Part 1. Zero `frontend/` changes.

---

## 📝 Task 1.1 — Feature flag in `backend/config.py`

**File:** `backend/config.py`
**Pattern:** Match existing flags at lines 66-67 (`WHATSAPP_ENABLED`, `ENABLE_REMINDER_SCHEDULER`).

**Add at the end of the flags block (around line 70, after `WA_INVITE_ENABLED`):**

```python
# Safety module Phase 1 — default off, opt-in per environment.
# When off, safety router is NOT registered and endpoints 404.
ENABLE_SAFETY_MODULE = os.environ.get('ENABLE_SAFETY_MODULE', 'false').lower() == 'true'
```

**Then expose it to `server.py` import block.** Verify the export happens naturally — no `__all__` needed, `server.py` imports `from config import (...)`.

**VERIFY:**
```bash
cd backend && python3 -c "from config import ENABLE_SAFETY_MODULE; print(ENABLE_SAFETY_MODULE)"
# Expected (with flag unset): False
# With flag set to 'true': True
ENABLE_SAFETY_MODULE=true python3 -c "from config import ENABLE_SAFETY_MODULE; print(ENABLE_SAFETY_MODULE)"
# Expected: True
```

---

## 📝 Task 1.2 — Safety Pydantic base schemas in `backend/contractor_ops/schemas.py`

**File:** `backend/contractor_ops/schemas.py`
**Where to insert:** END of file (append after the last existing class). Do NOT reorder existing classes.

**What to add — 5 minimal Pydantic models.** These are data-shape definitions only. Request/Response models (Create/Update/Filter) come in Part 2.

```python
# =====================================================================
# Safety Module — Phase 1 data models
# Added: 2026-04-22 · Part 1 Foundation
# References: specs/safety-phase-1-master-plan.md §5
# =====================================================================

class SafetyCategory(str, Enum):
    """10 regulatory safety categories per תקנות התשע"ט-2019"""
    scaffolding = "scaffolding"          # פיגומים
    heights = "heights"                  # עבודה בגובה
    electrical_safety = "electrical_safety"  # בטיחות חשמל
    lifting = "lifting"                  # הרמה וציוד
    excavation = "excavation"            # חפירות
    fire_safety = "fire_safety"          # אש ובטיחות אש
    ppe = "ppe"                          # ציוד מגן אישי
    site_housekeeping = "site_housekeeping"  # סדר וניקיון
    hazardous_materials = "hazardous_materials"  # חומרים מסוכנים
    other = "other"                      # אחר


class SafetySeverity(str, Enum):
    """Severity 1-3 per Cemento convention"""
    sev_1 = "1"   # נמוכה — הערה/שיפור
    sev_2 = "2"   # בינונית — דורש תיקון
    sev_3 = "3"   # גבוהה — עצירה מיידית


class SafetyDocumentStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    verified = "verified"


class SafetyTaskStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class SafetyWorker(BaseModel):
    """Worker on site — minimal Phase 1 shape. Extended in Part 2."""
    id: str                              # uuid4
    project_id: str
    company_id: Optional[str] = None     # FK → project_companies.id
    full_name: str
    id_number: Optional[str] = None      # Israeli/Palestinian/foreign ID; stored raw, hashed in Part 2
    profession: Optional[str] = None     # e.g. "נגר", "חשמלאי"
    phone: Optional[str] = None
    notes: Optional[str] = None
    created_at: str                      # ISO UTC via _now()
    created_by: str                      # actor user id
    # soft-delete (project-wide convention — camelCase)
    deletedAt: Optional[str] = None
    deletedBy: Optional[str] = None
    deletion_reason: Optional[str] = None
    retention_until: Optional[str] = None  # 7yr from delete for regulatory


class SafetyTraining(BaseModel):
    """Training record per worker. Expiry drives Safety Score."""
    id: str
    project_id: str
    worker_id: str                       # FK → safety_workers.id
    training_type: str                   # e.g. "הדרכת אתר", "הדרכת סיכונים"
    instructor_name: Optional[str] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    trained_at: str                      # ISO date
    expires_at: Optional[str] = None     # ISO date; null = no expiry
    certificate_url: Optional[str] = None  # R2/S3 URL if uploaded
    created_at: str
    created_by: str
    deletedAt: Optional[str] = None
    deletedBy: Optional[str] = None


class SafetyDocument(BaseModel):
    """Safety observation/finding — the regulatory תיעוד records."""
    id: str
    project_id: str
    category: SafetyCategory
    severity: SafetySeverity
    status: SafetyDocumentStatus = SafetyDocumentStatus.open
    title: str
    description: Optional[str] = None
    location: Optional[str] = None       # e.g. "קומה 4, גוש מזרחי"
    company_id: Optional[str] = None     # FK → project_companies.id
    profession: Optional[str] = None
    assignee_id: Optional[str] = None    # user id
    reporter_id: str                     # user id
    photo_urls: List[str] = []
    attachment_urls: List[str] = []      # PDF/doc attachments
    found_at: str                        # ISO UTC (when observed)
    resolved_at: Optional[str] = None
    created_at: str
    created_by: str
    updated_at: Optional[str] = None
    deletedAt: Optional[str] = None
    deletedBy: Optional[str] = None


class SafetyTask(BaseModel):
    """Corrective action task."""
    id: str
    project_id: str
    document_id: Optional[str] = None    # FK → safety_documents.id
    title: str
    description: Optional[str] = None
    status: SafetyTaskStatus = SafetyTaskStatus.open
    severity: SafetySeverity
    assignee_id: Optional[str] = None
    company_id: Optional[str] = None
    due_at: Optional[str] = None
    completed_at: Optional[str] = None
    corrective_action: Optional[str] = None
    verification_photo_urls: List[str] = []
    created_at: str
    created_by: str
    updated_at: Optional[str] = None
    deletedAt: Optional[str] = None
    deletedBy: Optional[str] = None


class SafetyIncident(BaseModel):
    """Near-miss or injury event. 7-year retention is REGULATORY (not optional)."""
    id: str
    project_id: str
    incident_type: str                   # "near_miss" | "injury" | "property_damage"
    severity: SafetySeverity
    occurred_at: str                     # ISO UTC
    description: str
    location: Optional[str] = None
    injured_worker_id: Optional[str] = None  # FK → safety_workers.id; null if near-miss
    witnesses: List[str] = []            # worker_ids
    photo_urls: List[str] = []
    medical_record_urls: List[str] = []  # PHI — encrypted at rest (Part 2)
    reported_to_authority: bool = False
    authority_report_ref: Optional[str] = None
    created_at: str
    created_by: str
    updated_at: Optional[str] = None
    # soft-delete: retention_until MUST be set to occurred_at + 7yr on delete
    deletedAt: Optional[str] = None
    deletedBy: Optional[str] = None
    deletion_reason: Optional[str] = None
    retention_until: Optional[str] = None
```

**Style notes:**
- `BaseModel` and `Enum` are already imported at the top of `schemas.py` — verify before adding. If not, add `from enum import Enum` and `from pydantic import BaseModel`.
- `List`, `Optional` — already imported via `from typing import ...` at top of file.
- Every model uses `id: str` (uuid4 generated at creation time via `str(uuid.uuid4())`).
- Every timestamp is `str` (ISO UTC via `_now()`), never `datetime`. Match project convention.

**VERIFY:**
```bash
cd backend && python3 -c "from contractor_ops.schemas import SafetyDocument, SafetyWorker, SafetyTraining, SafetyTask, SafetyIncident, SafetyCategory, SafetySeverity; print('OK')"
# Expected: OK
```

---

## 📝 Task 1.3 — `safety_router.py` stub + indices helper

**File:** `backend/contractor_ops/safety_router.py` — **CREATE NEW.**

**Full content (paste as-is):**

```python
"""
Safety module router — Phase 1 Part 1 (Foundation).

Only exposes healthz. All CRUD + filters arrive in Part 2.

Registration in server.py is GATED by ENABLE_SAFETY_MODULE env flag.
When flag is off, this module is never imported and endpoints 404.
"""
from fastapi import APIRouter, Depends
from contractor_ops.router import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/safety", tags=["safety"])


@router.get("/healthz")
async def healthz(user: dict = Depends(get_current_user)):
    """
    Liveness check for Safety module.
    Requires auth — never expose module existence to unauthenticated scanners.
    """
    return {"ok": True, "module": "safety", "enabled": True}


# =====================================================================
# Index management — called from server.py startup when module enabled.
# =====================================================================
async def ensure_safety_indexes(db) -> None:
    """
    Create MongoDB indices for Safety collections.
    Idempotent: `create_index` is a no-op if the same spec already exists.
    Safe to run on every startup.

    All indices use background=True to avoid locking hot collections.
    """
    # -----------------------------------------------------------------
    # safety_workers — 3 indices
    # -----------------------------------------------------------------
    await db.safety_workers.create_index(
        [("project_id", 1), ("deletedAt", 1)],
        background=True,
        name="idx_sw_project_deleted",
    )
    await db.safety_workers.create_index(
        [("project_id", 1), ("company_id", 1)],
        background=True,
        name="idx_sw_project_company",
    )
    await db.safety_workers.create_index(
        [("project_id", 1), ("id_number", 1)],
        background=True,
        sparse=True,
        name="idx_sw_project_idnum",
    )

    # -----------------------------------------------------------------
    # safety_trainings — 3 indices
    # -----------------------------------------------------------------
    await db.safety_trainings.create_index(
        [("project_id", 1), ("worker_id", 1)],
        background=True,
        name="idx_st_project_worker",
    )
    await db.safety_trainings.create_index(
        [("project_id", 1), ("expires_at", 1)],
        background=True,
        sparse=True,
        name="idx_st_project_expires",
    )
    await db.safety_trainings.create_index(
        [("project_id", 1), ("training_type", 1)],
        background=True,
        name="idx_st_project_type",
    )

    # -----------------------------------------------------------------
    # safety_documents — 5 filter-critical indices
    # -----------------------------------------------------------------
    await db.safety_documents.create_index(
        [("project_id", 1), ("deletedAt", 1), ("created_at", -1)],
        background=True,
        name="idx_sd_project_deleted_created",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("status", 1)],
        background=True,
        name="idx_sd_project_status",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("severity", 1)],
        background=True,
        name="idx_sd_project_severity",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("category", 1)],
        background=True,
        name="idx_sd_project_category",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("company_id", 1)],
        background=True,
        sparse=True,
        name="idx_sd_project_company",
    )

    # -----------------------------------------------------------------
    # safety_tasks — 4 indices
    # -----------------------------------------------------------------
    await db.safety_tasks.create_index(
        [("project_id", 1), ("deletedAt", 1), ("due_at", 1)],
        background=True,
        name="idx_stk_project_deleted_due",
    )
    await db.safety_tasks.create_index(
        [("project_id", 1), ("status", 1)],
        background=True,
        name="idx_stk_project_status",
    )
    await db.safety_tasks.create_index(
        [("project_id", 1), ("assignee_id", 1)],
        background=True,
        sparse=True,
        name="idx_stk_project_assignee",
    )
    await db.safety_tasks.create_index(
        [("document_id", 1)],
        background=True,
        sparse=True,
        name="idx_stk_document",
    )

    # -----------------------------------------------------------------
    # safety_incidents — 3 indices (7yr retention-critical)
    # -----------------------------------------------------------------
    await db.safety_incidents.create_index(
        [("project_id", 1), ("occurred_at", -1)],
        background=True,
        name="idx_si_project_occurred",
    )
    await db.safety_incidents.create_index(
        [("project_id", 1), ("severity", 1)],
        background=True,
        name="idx_si_project_severity",
    )
    await db.safety_incidents.create_index(
        [("retention_until", 1)],
        background=True,
        sparse=True,
        name="idx_si_retention",
    )

    # -----------------------------------------------------------------
    # project_companies — 2 new safety-related indices
    # (safe to add — collection is shared with other modules)
    # -----------------------------------------------------------------
    await db.project_companies.create_index(
        [("project_id", 1), ("safety_contact_id", 1)],
        background=True,
        sparse=True,
        name="idx_pc_project_safety_contact",
    )
    await db.project_companies.create_index(
        [("project_id", 1), ("is_placeholder", 1)],
        background=True,
        sparse=True,
        name="idx_pc_project_placeholder",
    )

    logger.info("Safety indices ensured (18 total across 6 collections)")
```

**Rationale for index choices:**
- Every `project_id + deletedAt + <sort>` combo is the hot filter path (list endpoints).
- `severity`, `status`, `category`, `company_id` are the 4 primary filter dimensions → each gets a compound with `project_id`.
- `sparse=True` only where the field may be absent (`id_number`, `expires_at`, `assignee_id`, etc.).
- `background=True` on ALL of them — Atlas builds in background, no collection lock.
- Names follow `idx_<table>_<keys>` convention for easy debugging.

**VERIFY:**
```bash
# Import check:
cd backend && python3 -c "from contractor_ops.safety_router import router, ensure_safety_indexes; print('OK')"
# Expected: OK

# Route inspection (when flag on, see Task 1.4):
# curl http://localhost:8000/api/safety/healthz -H "Authorization: Bearer <token>"
# Expected: {"ok":true,"module":"safety","enabled":true}
```

---

## 📝 Task 1.4 — Conditional wiring in `backend/server.py`

**File:** `backend/server.py`

### 1.4.a — Import flag in config import block

**Location:** The import block starting at line 15 (`from config import (...)`).

**Add** `ENABLE_SAFETY_MODULE` to the import tuple — alphabetically or at the end of the tuple, whichever matches the existing style. The existing block ends around line 29 — add:

```python
    # ... existing imports ...
    ENABLE_SAFETY_MODULE,
)
```

### 1.4.b — Register router conditionally

**Location:** After the last `app.include_router(...)` call for other feature-flagged modules. Best insertion point is **after `config_router` is registered around line 428** (search for `config_router` to confirm line).

**Insert:**

```python
# -----------------------------------------------------------------
# Safety module — Phase 1 (feature-gated)
# When ENABLE_SAFETY_MODULE is False, router is NEVER imported and
# endpoints 404. This is the STRONGEST guarantee that disabled ==
# invisible, for both scanners and accidental exposure.
# -----------------------------------------------------------------
if ENABLE_SAFETY_MODULE:
    from contractor_ops.safety_router import router as safety_router
    app.include_router(safety_router)
    logger.info("Safety module ENABLED — router registered at /api/safety")
else:
    logger.info("Safety module disabled (ENABLE_SAFETY_MODULE=false)")
```

### 1.4.c — Ensure indices on startup

**Location:** Inside the `@app.on_event("startup")` handler around **line 1178-1200**. Find the block where other `ensure_indexes` calls happen (look for `stepup_ensure_indexes`, `invoicing_ensure_indexes` around line 1112-1115).

**Add after the last existing `ensure_indexes` call:**

```python
    # Safety module indices (guarded by feature flag)
    if ENABLE_SAFETY_MODULE:
        from contractor_ops.safety_router import ensure_safety_indexes
        try:
            await ensure_safety_indexes(db)
        except Exception as e:
            logger.error(f"Failed to ensure safety indices: {e}")
            # Do NOT crash startup — module will still function, queries just slower
```

**Error handling rationale:** index creation is best-effort. If Atlas is temporarily unreachable during startup, the module should still boot and writes still succeed — queries just run without optimized indices until next restart.

**VERIFY Part 1.4:**

```bash
# 1. Default (flag off) — startup log
cd backend && uvicorn server:app --port 8001 2>&1 | head -50
# Look for: "Safety module disabled (ENABLE_SAFETY_MODULE=false)"
# curl http://localhost:8001/api/safety/healthz → 404

# 2. Flag on — startup log
ENABLE_SAFETY_MODULE=true uvicorn server:app --port 8001 2>&1 | head -50
# Look for:
#   "Safety module ENABLED — router registered at /api/safety"
#   "Safety indices ensured (18 total across 6 collections)"
# curl http://localhost:8001/api/safety/healthz -H "Authorization: Bearer <valid_jwt>"
# Expected: 200 {"ok":true,"module":"safety","enabled":true}
# curl http://localhost:8001/api/safety/healthz  (no auth)
# Expected: 401
```

---

## 🧪 End-to-end deliverable test

**Exit criteria for Part 1:**

Run all 4 of these from a clean shell. All MUST pass.

```bash
# Test 1 — flag OFF (default prod behavior)
cd backend && timeout 15 uvicorn server:app --port 8101 > /tmp/p1-off.log 2>&1 &
sleep 5
curl -s -o /dev/null -w "%{http_code}" http://localhost:8101/api/safety/healthz
# Expected output: 404

grep -q "Safety module disabled" /tmp/p1-off.log && echo "TEST 1 PASS" || echo "TEST 1 FAIL"
pkill -f "uvicorn server:app --port 8101"

# Test 2 — flag ON, unauthenticated
ENABLE_SAFETY_MODULE=true timeout 15 uvicorn server:app --port 8101 > /tmp/p1-on.log 2>&1 &
sleep 5
curl -s -o /dev/null -w "%{http_code}" http://localhost:8101/api/safety/healthz
# Expected output: 401

# Test 3 — flag ON, authenticated
TOKEN=$(/* obtain JWT via existing test user */)
curl -s http://localhost:8101/api/safety/healthz -H "Authorization: Bearer $TOKEN"
# Expected output: {"ok":true,"module":"safety","enabled":true}

# Test 4 — indices created
python3 -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL, DB_NAME
async def check():
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]
    names = set()
    for coll in ['safety_workers','safety_trainings','safety_documents','safety_tasks','safety_incidents','project_companies']:
        async for idx in db[coll].list_indexes():
            if idx['name'].startswith('idx_s') or idx['name'].startswith('idx_pc_project_safety') or idx['name'].startswith('idx_pc_project_placeholder'):
                names.add(idx['name'])
    assert len(names) == 18, f'Expected 18 safety indices, got {len(names)}: {names}'
    print(f'TEST 4 PASS — {len(names)} indices')
asyncio.run(check())
"
# Expected output: TEST 4 PASS — 18 indices

pkill -f "uvicorn server:app --port 8101"
```

---

## 📦 Commit / PR

**Branch:** `feature/safety-phase-1-part-1`
**Commit message:**

```
feat(safety): Phase 1 Part 1 — Foundation (feature flag + schemas + indices)

- Add ENABLE_SAFETY_MODULE env flag (default false)
- Add 5 safety Pydantic schemas (Worker, Training, Document, Task, Incident)
- Add 5 enums (Category, Severity, DocumentStatus, TaskStatus, IncidentType)
- Create safety_router.py with healthz stub only
- Add ensure_safety_indexes() — 18 indices across 6 collections
- Wire conditional registration + startup index creation in server.py

Gated behind feature flag. Zero user-visible changes when off.
Part 1 of 5. See specs/safety-phase-1-master-plan.md.

Refs: Task #33
```

**PR description:**
> Foundation-only. No endpoints exposed besides healthz. Safe to merge to main with flag off; Part 2 will add CRUD.
> **Native build:** NO. Pure backend.
> **Deploy:** `./deploy.sh --prod` only. No ship.sh needed.

---

## ⏭ After merge — before starting Part 2

1. Set `ENABLE_SAFETY_MODULE=true` in **Replit staging only** (not prod yet).
2. Restart staging, confirm test 3 + test 4 above pass on live Atlas.
3. Tell Zahi: "Part 1 green on staging, ready for Part 2 spec."
