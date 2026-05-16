# #SAFETY-P1 — Safety Module Phase 1 (Contractors + Workers + Trainings)

> **Parent concept:** `future-features/safety-and-worklog-concept.md`
> **Scope:** Phase 1 Core — Contractor Companies + Workers + Worker Trainings (dual-flow)
> **Time estimate:** 4 weeks (2 backend, 1.5 frontend, 0.5 integration + E2E)
> **Guarded by:** `ENABLE_SAFETY_MODULE=false` (off by default — we flip it per tenant)
> **Blocks:** Phase 2 (Equipment), Phase 3 (Tours + Safety Score), Phase 4 (AI)

---

## What & Why

מודול הבטיחות הוא רגולטורית חובה בישראל (תקנות הבטיחות בעבודה, התשמ"ח-1988) וחסם deal-breaker בעסקאות enterprise — שיכון ובינוי ואלקטרה דורשים את זה במפורש. Cemento כבר מציעים. אי אפשר לסגור deal Enterprise בלי המודול הזה.

Phase 1 בונה את השכבה הנמוכה ביותר: **רישום קבלני משנה, עובדים, ורישום הדרכות בטיחות של העובדים** — עם dual-flow (סריקת תעודה קיימת vs. חתימה in-app). המודול נבנה **בידוד מלא** (collections נפרדות, router נפרד, components נפרדות) כדי שלא נשבור את הפיצ'ר הקיים של ליקויים/QC/מסירה.

כל הכרעות ה-architectural מגובות ב-deep code investigation של הקוד הקיים: אנחנו משתמשים ב-helpers הקנוניים (`require_roles`, `_check_project_access`, `_audit`), באותו pattern של Tasks (Pydantic-first), ועם 6 שדות audit/soft-delete/retention שמכינים את המודול ל-SOC2 מיום אחד.

**Deeper context:** קרא את `future-features/safety-and-worklog-concept.md` — במיוחד את הסעיף "🔬 Post-Deep-Research Architecture Addendum" בסוף הקובץ. כל ההחלטות מגובות שם עם rationale.

---

## Done looks like

אחרי Phase 1, לקוח שעל-tenant שלו הפעלנו `ENABLE_SAFETY_MODULE=true` יכול:

1. לראות tab חדש "**בטיחות ויומן עבודה**" ב-`ProjectControlPage` (רק אם `project_manager` או `management_team`).
2. לפתוח מסך ראשי — רשימת קבלני משנה באותו פרויקט, עם group header לכל קבלן + מונה עובדים + collapsible.
3. להוסיף קבלן משנה ידנית (שם, מס' רישום אופציונלי). לקבלן שנוסף ע"י לקוח אחר קודם — מופיע באוטוקומפליט מה-DB הפנימי שלנו.
4. לראות בלוק "אין חברה" (collapsible, collapsed by default אם ריק) — seeded אוטומטית לכל פרויקט חדש.
5. להוסיף עובד לקבלן (שם מלא, ת.ז., טלפון, מקצוע, תפקיד).
6. לראות רשימת ת.ז. **masked** ברשימת העובדים (`****1234`); הת.ז. המלאה מופיעה רק בפרופיל העובד למשתמש management.
7. ברמת עובד — להוסיף רישום הדרכה ב-2 flows:
   - **"סרוק מסמך"**: תאריך הסמכה + משך תוקף + העלאת תמונה/PDF של תעודה קיימת
   - **"חתום באפליקציה"**: תאריך חתימה (auto = היום) + משך תוקף + canvas signature + אופציונלי מתורגמן (שם + ת.ז.)
8. לראות סטטוס לכל הדרכה: בתוקף (ירוק) / פג (אדום) + ימים לפי/אחרי expiry.
9. לסנן את רשימת העובדים/ההדרכות לפי: חברה, מקצוע, סטטוס הדרכה (valid/expired/expiring-in-30d), טווח תאריכים.
10. לייצא את הרשימה המסוננת ב-3 פורמטים: PDF (רגולציה), CSV (אקסל), JSON (אינטגרציה).
11. כל mutation (create/update/delete) נרשמת ב-`audit_events` עם payload diff.
12. Soft-delete: מחיקת עובד/קבלן/הדרכה מסמנת `deleted_at`, לא מוחקת פיזית. כל query מסננת deleted.

---

## Out of scope (Phase 2+)

- ❌ **Equipment management** — 10 קטגוריות + multi-check-per-item (Phase 2)
- ❌ **Safety tours + dual signatures** (work_manager + safety_assistant) — Phase 3
- ❌ **Safety Score engine** (Cemento formula 1:1) — Phase 4
- ❌ **Defects tagged "בטיחות"** + megaphone + documentation collection — Phase 3
- ❌ **Project Registration form** (פנקס הקבלנים — יזם, מנהלים, מען) — Phase 3
- ❌ **Daily work diary** (יומן עבודה יומי — חומרים, ציוד, מזג אוויר) — Phase 4
- ❌ **Offline mode** (IndexedDB + sync queue) — Phase 5
- ❌ **Vision AI OCR** של תסקירים / תעודות הדרכה — Phase 4 (AI Assistant)
- ❌ **Cemento migration import** (PDF parser) — Phase 2 אחרי 10+ concierge migrations
- ❌ **ת.ז. algorithmic validation** (Luhn variant ישראלי) — Phase 2 דרך `identity_router.py`
- ❌ **Field-level encryption** של PII — SOC2 Stage
- ❌ **PAdES cryptographic signatures** — SOC2 Stage; Phase 1 משתמש ב-pattern הקיים של handover (canvas PNG + signer_user_id + timestamp)
- ❌ **Retention enforcement** (block delete before `retention_until`) — השדה ייכתב, enforcement ב-SOC2 Stage
- ❌ **Custom equipment categories** ב-Safety Score — Phase 4

---

## Phased execution (DO NOT SKIP)

```
Phase 1a (backend foundation)    — ~1 week
Phase 1b (backend routes + audit) — ~1 week
Phase 1c (frontend UI)             — ~1.5 weeks
Phase 1d (export + filters + E2E) — ~0.5 week

STOP after each phase. Push to staging. Report. Wait for my approval.
```

---

## STEP 0 — INVESTIGATE FIRST (read-only, no code)

Before writing any code, confirm the following files exist and their line numbers are still accurate:

```
grep -n "class ManagementSubRole" backend/contractor_ops/schemas.py
# Expected: line ~32

grep -n "MANAGEMENT_ROLES" backend/contractor_ops/router.py
# Expected: line ~413

grep -n "def require_roles" backend/contractor_ops/router.py
# Expected: function definition

grep -n "def _check_project_access" backend/contractor_ops/router.py
# Expected: line ~337

grep -n "def _audit" backend/contractor_ops/router.py
# Expected: line ~433

grep -n "def _now" backend/contractor_ops/router.py
# Expected: line ~103

grep -n "workTabs" frontend/src/pages/ProjectControlPage.js
# Expected: line ~3497 + handleWorkTab line ~3506

grep -n "const qcService" frontend/src/services/api.js
# Expected: line ~1182 (we mirror this pattern for safetyService)

grep -n "ENABLE_" backend/config.py | head -20
# Confirm the env-based feature flag pattern

grep -n "feature_flags" backend/contractor_ops/config_router.py
# Confirm shape of /api/config/features response
```

**Report back:** paste the grep output so we confirm line numbers BEFORE opening any file for editing.
**DO NOT write code until STEP 0 is confirmed.**

---

## Phase 1a — Backend Foundation

### Task 1 — Add feature flag

**File:** `backend/config.py`

Add near other `ENABLE_*` flags (around line 67-185):

```python
ENABLE_SAFETY_MODULE = _env_bool("ENABLE_SAFETY_MODULE", False)
```

**File:** `backend/contractor_ops/config_router.py`

In the `/api/config/features` endpoint response (lines 8-18), add to the `feature_flags` dict:

```python
"safety_module_enabled": ENABLE_SAFETY_MODULE,
```

Import at top:
```python
from config import ENABLE_SAFETY_MODULE
```

### Task 2 — Pydantic schemas

**File:** `backend/contractor_ops/schemas.py`

Append at the end of the file, under a new section header:

```python
# ============================================================
# SAFETY MODULE (Phase 1: Contractors + Workers + Trainings)
# ============================================================

class ContractorCompanyBase(BaseModel):
    project_id: str
    name: str = Field(..., min_length=1, max_length=200)
    registry_number: Optional[str] = None  # רשם הקבלנים (optional, user-typed)
    is_placeholder: bool = False            # "אין חברה" flag — seeded per project

class ContractorCompanyCreate(ContractorCompanyBase):
    pass

class ContractorCompanyUpdate(BaseModel):
    name: Optional[str] = None
    registry_number: Optional[str] = None

class ContractorCompany(ContractorCompanyBase):
    id: str
    # Audit
    created_at: str
    created_by: str
    updated_at: str
    updated_by: str
    # Soft-delete
    deleted_at: Optional[str] = None
    deleted_by: Optional[str] = None
    deletion_reason: Optional[str] = None
    # Retention (regulatory — 7 years for safety records)
    retention_until: Optional[str] = None


class WorkerBase(BaseModel):
    project_id: str
    contractor_company_id: str              # FK. For "אין חברה" = placeholder company id.
    full_name: str = Field(..., min_length=2, max_length=150)
    id_number: str = Field(..., min_length=5, max_length=20)  # ת.ז. / passport. Free string in Phase 1.
    phone: Optional[str] = None              # normalized via phone_utils in router
    trade: Optional[str] = None              # מקצוע (e.g. "חשמלאי", "קבלן טיח")
    photo_url: Optional[str] = None

class WorkerCreate(WorkerBase):
    pass

class WorkerUpdate(BaseModel):
    contractor_company_id: Optional[str] = None
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    phone: Optional[str] = None
    trade: Optional[str] = None
    photo_url: Optional[str] = None

class Worker(WorkerBase):
    id: str
    # Masked for list endpoints; full only on /workers/{id} profile for management.
    # (router computes id_number_masked on the fly from id_number[-4:]; not stored)
    created_at: str
    created_by: str
    updated_at: str
    updated_by: str
    deleted_at: Optional[str] = None
    deleted_by: Optional[str] = None
    deletion_reason: Optional[str] = None
    retention_until: Optional[str] = None

class WorkerListItem(BaseModel):
    """Shape returned by GET /workers list (masked PII)."""
    id: str
    project_id: str
    contractor_company_id: str
    full_name: str
    id_number_masked: str   # e.g. "****1234"
    phone: Optional[str] = None
    trade: Optional[str] = None
    photo_url: Optional[str] = None
    training_summary: dict  # {"valid": 3, "expired": 1, "expiring_30d": 1}


class WorkerTrainingTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    default_valid_months: Optional[int] = None  # None = once-lifetime
    regulatory_source: Optional[str] = None      # e.g. "תקנה 3 לתקנות..."
    allows_translator: bool = False              # הדרכה שמותר מתורגמן (למשל ערבית/רוסית)

class WorkerTrainingTypeCreate(WorkerTrainingTypeBase):
    pass

class WorkerTrainingType(WorkerTrainingTypeBase):
    id: str
    is_seeded: bool = False  # seeded (system) vs. custom (tenant)
    created_at: str
    created_by: str


class WorkerTrainingSubmissionMethod(str, Enum):
    SCANNED = "scanned"     # סרוק מסמך חיצוני
    IN_APP = "in_app"       # חתום באפליקציה

class WorkerTrainingBase(BaseModel):
    project_id: str
    worker_id: str
    training_type_id: str
    submission_method: WorkerTrainingSubmissionMethod
    signed_or_certified_date: str           # ISO date — מתי נחתם/הוסמך
    valid_months: int = Field(..., ge=0)    # 0 = once-lifetime; override of default
    # Translator (optional)
    translator_name: Optional[str] = None
    translator_id: Optional[str] = None
    # Storage
    document_url: Optional[str] = None       # scanned PDF/image (required if submission_method=scanned)
    signature_url: Optional[str] = None      # canvas PNG (required if submission_method=in_app)
    signer_user_id: Optional[str] = None     # required if in_app

class WorkerTrainingCreate(WorkerTrainingBase):
    pass

class WorkerTraining(WorkerTrainingBase):
    id: str
    expires_at: Optional[str] = None   # computed from signed_or_certified_date + valid_months
    status: str                          # "valid" | "expired" | "expiring_30d" | "once_lifetime"
    created_at: str
    created_by: str
    updated_at: str
    updated_by: str
    deleted_at: Optional[str] = None
    deleted_by: Optional[str] = None
    deletion_reason: Optional[str] = None
    retention_until: Optional[str] = None
```

**Use existing imports at top of file** — `BaseModel`, `Field`, `Optional`, `Enum` are already imported. Add `datetime` import only if not present.

### Task 3 — MongoDB indices

**File:** `backend/server.py` (create_index block, lines 501-616)

Add after existing indices, before the final block:

```python
# ============ SAFETY MODULE (Phase 1) ============
# contractor_companies
await db.contractor_companies.create_index([("project_id", 1), ("deleted_at", 1)])
await db.contractor_companies.create_index([("project_id", 1), ("name", 1)])
await db.contractor_companies.create_index([("project_id", 1), ("is_placeholder", 1)])

# workers
await db.workers.create_index([("project_id", 1), ("deleted_at", 1)])
await db.workers.create_index([("contractor_company_id", 1), ("deleted_at", 1)])
await db.workers.create_index([("project_id", 1), ("id_number", 1)])  # dedupe lookup

# worker_training_types — seeded + custom, small
await db.worker_training_types.create_index([("name", 1)], unique=True)

# worker_trainings
await db.worker_trainings.create_index([("worker_id", 1), ("deleted_at", 1)])
await db.worker_trainings.create_index([("project_id", 1), ("expires_at", 1)])
await db.worker_trainings.create_index([("project_id", 1), ("training_type_id", 1)])
await db.worker_trainings.create_index([("project_id", 1), ("deleted_at", 1), ("expires_at", 1)])
```

**Total: 11 indices.**

### Task 4 — Seed worker_training_types (baseline)

**File:** `backend/contractor_ops/safety_seed.py` (create new file)

Create a function to seed the baseline training types on first boot:

```python
"""Seeds baseline worker_training_types. Idempotent — safe to re-run."""
import uuid
from .router import _now

BASELINE_TYPES = [
    {"name": "הדרכת אתר (בטיחות כללית)", "default_valid_months": 12, "regulatory_source": "תקנות בטיחות בעבודה (עבודות בנייה) התשמ\"ח-1988", "allows_translator": True},
    {"name": "עבודה בגובה", "default_valid_months": 24, "regulatory_source": "תקנות הבטיחות בעבודה (עבודה בגובה) התשס\"ז-2007", "allows_translator": True},
    {"name": "הדרכת סיכונים מקצועיים", "default_valid_months": 12, "regulatory_source": "תקנות ארגון הפיקוח על העבודה (מסירת מידע והדרכת עובדים) התשנ\"ט-1999", "allows_translator": True},
    {"name": "הדרכת עובד חדש", "default_valid_months": 0, "regulatory_source": "סעיף 8 לחוק ארגון הפיקוח על העבודה התשי\"ד-1954", "allows_translator": True},  # 0 = once-lifetime
    {"name": "עגורנאי — רישיון", "default_valid_months": 24, "regulatory_source": "תקנות הבטיחות בעבודה (עגורנים צריחים) התשכ\"ז-1966", "allows_translator": False},
    {"name": "מפעיל מלגזה", "default_valid_months": 24, "regulatory_source": "תקנות הבטיחות בעבודה (גיהות תעסוקתית ובריאות העובדים במתכת) התשס\"א-2001", "allows_translator": False},
    {"name": "עזרה ראשונה", "default_valid_months": 24, "regulatory_source": "תקנות ארגון הפיקוח על העבודה (מסירת מידע והדרכת עובדים) התשנ\"ט-1999", "allows_translator": False},
    {"name": "חשמלאי — רישיון", "default_valid_months": 0, "regulatory_source": "חוק החשמל התשי\"ד-1954", "allows_translator": False},
]

async def seed_training_types(db):
    """Inserts baseline types if they don't already exist (matched by name)."""
    now = _now()
    for t in BASELINE_TYPES:
        existing = await db.worker_training_types.find_one({"name": t["name"]})
        if existing:
            continue
        await db.worker_training_types.insert_one({
            "_id": str(uuid.uuid4()),
            "is_seeded": True,
            "created_at": now,
            "created_by": "system",
            **t,
        })
```

**Hook into `backend/server.py` startup** — add after index creation:

```python
# Seed safety training types (idempotent)
from contractor_ops.safety_seed import seed_training_types
await seed_training_types(db)
```

### Task 5 — Helper: compute training status

**File:** `backend/contractor_ops/safety_utils.py` (create new file)

```python
"""Utilities for safety module — status computation, PII masking."""
from datetime import datetime, timedelta, timezone
from typing import Optional

def compute_training_status(signed_or_certified_date: str, valid_months: int) -> tuple[Optional[str], str]:
    """
    Returns (expires_at_iso, status).
    status ∈ {"valid", "expired", "expiring_30d", "once_lifetime"}.
    valid_months = 0 means once-lifetime (no expiry).
    """
    if valid_months == 0:
        return None, "once_lifetime"
    try:
        signed = datetime.fromisoformat(signed_or_certified_date.replace("Z", "+00:00"))
    except Exception:
        # Defensive — treat as today
        signed = datetime.now(timezone.utc)
    expires = signed + timedelta(days=valid_months * 30)  # approx — acceptable for display
    now = datetime.now(timezone.utc)
    expires_iso = expires.isoformat()
    if expires < now:
        return expires_iso, "expired"
    if (expires - now) <= timedelta(days=30):
        return expires_iso, "expiring_30d"
    return expires_iso, "valid"


def mask_id_number(id_number: str) -> str:
    """Returns last 4 masked: '123456789' → '****6789'."""
    if not id_number:
        return ""
    tail = id_number[-4:] if len(id_number) >= 4 else id_number
    return f"****{tail}"


def retention_until_7_years() -> str:
    """Returns ISO string 7 years from now (regulatory retention for safety records)."""
    return (datetime.now(timezone.utc) + timedelta(days=365 * 7)).isoformat()
```

---

## Phase 1b — Backend Routes + Audit

### Task 6 — Safety router (main)

**File:** `backend/contractor_ops/safety_router.py` (create new file)

```python
"""Safety module router — Phase 1 (contractors, workers, trainings)."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from config import ENABLE_SAFETY_MODULE
from .schemas import (
    ContractorCompanyCreate, ContractorCompanyUpdate, ContractorCompany,
    WorkerCreate, WorkerUpdate, Worker, WorkerListItem,
    WorkerTrainingTypeCreate, WorkerTrainingType,
    WorkerTrainingCreate, WorkerTraining,
    WorkerTrainingSubmissionMethod,
)
from .router import (
    get_db, get_current_user,
    _check_project_access, _check_project_read_access,
    _get_project_role, _is_super_admin,
    _now, _audit,
    MANAGEMENT_ROLES, require_roles,
)
from .safety_utils import compute_training_status, mask_id_number, retention_until_7_years
from .phone_utils import normalize_israeli_phone

router = APIRouter(prefix="/api/safety", tags=["safety"])


def _require_feature_enabled():
    """Guard every endpoint — feature flag check."""
    if not ENABLE_SAFETY_MODULE:
        raise HTTPException(status_code=404, detail="Safety module not enabled")


# ============ CONTRACTOR COMPANIES ============

@router.post("/contractor-companies", response_model=ContractorCompany)
async def create_contractor_company(
    payload: ContractorCompanyCreate,
    user: dict = Depends(require_roles('project_manager', 'management_team')),
    db = Depends(get_db),
):
    _require_feature_enabled()
    await _check_project_access(user, payload.project_id)
    doc_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": doc_id,
        **payload.dict(),
        "created_at": now, "created_by": user["id"],
        "updated_at": now, "updated_by": user["id"],
        "deleted_at": None, "deleted_by": None, "deletion_reason": None,
        "retention_until": retention_until_7_years(),
    }
    await db.contractor_companies.insert_one(doc)
    await _audit("contractor_company", doc_id, "create", user["id"], {
        "project_id": payload.project_id,
        "name": payload.name,
        "is_placeholder": payload.is_placeholder,
    })
    return {**doc, "id": doc_id}


@router.get("/contractor-companies", response_model=list[ContractorCompany])
async def list_contractor_companies(
    project_id: str = Query(...),
    include_deleted: bool = Query(False),
    user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    _require_feature_enabled()
    await _check_project_read_access(user, project_id)
    q = {"project_id": project_id}
    if not include_deleted:
        q["deleted_at"] = None
    if include_deleted and not _is_super_admin(user):
        raise HTTPException(403, "include_deleted requires super_admin")
    docs = await db.contractor_companies.find(q).sort("name", 1).to_list(1000)
    return [{**d, "id": d["_id"]} for d in docs]


@router.put("/contractor-companies/{company_id}", response_model=ContractorCompany)
async def update_contractor_company(
    company_id: str,
    payload: ContractorCompanyUpdate,
    user: dict = Depends(require_roles('project_manager', 'management_team')),
    db = Depends(get_db),
):
    _require_feature_enabled()
    existing = await db.contractor_companies.find_one({"_id": company_id, "deleted_at": None})
    if not existing:
        raise HTTPException(404)
    await _check_project_access(user, existing["project_id"])
    if existing.get("is_placeholder"):
        raise HTTPException(400, "Cannot modify placeholder 'אין חברה'")
    patch = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    patch["updated_at"] = _now()
    patch["updated_by"] = user["id"]
    await db.contractor_companies.update_one({"_id": company_id}, {"$set": patch})
    await _audit("contractor_company", company_id, "update", user["id"], patch)
    doc = await db.contractor_companies.find_one({"_id": company_id})
    return {**doc, "id": doc["_id"]}


@router.delete("/contractor-companies/{company_id}")
async def soft_delete_contractor_company(
    company_id: str,
    user: dict = Depends(require_roles('project_manager', 'management_team')),
    db = Depends(get_db),
):
    _require_feature_enabled()
    existing = await db.contractor_companies.find_one({"_id": company_id, "deleted_at": None})
    if not existing:
        raise HTTPException(404)
    await _check_project_access(user, existing["project_id"])
    if existing.get("is_placeholder"):
        raise HTTPException(400, "Cannot delete placeholder 'אין חברה'")
    # Cascade check: company must have zero active workers
    active_workers = await db.workers.count_documents({
        "contractor_company_id": company_id, "deleted_at": None
    })
    if active_workers > 0:
        raise HTTPException(400, f"Company has {active_workers} active workers. Remove them first.")
    await db.contractor_companies.update_one(
        {"_id": company_id},
        {"$set": {"deleted_at": _now(), "deleted_by": user["id"], "deletion_reason": "user"}}
    )
    await _audit("contractor_company", company_id, "soft_delete", user["id"], {"reason": "user"})
    return {"ok": True}


# ============ WORKERS ============

@router.post("/workers", response_model=Worker)
async def create_worker(
    payload: WorkerCreate,
    user: dict = Depends(require_roles('project_manager', 'management_team')),
    db = Depends(get_db),
):
    _require_feature_enabled()
    await _check_project_access(user, payload.project_id)
    # Validate company exists in same project
    company = await db.contractor_companies.find_one({
        "_id": payload.contractor_company_id,
        "project_id": payload.project_id,
        "deleted_at": None,
    })
    if not company:
        raise HTTPException(400, "Contractor company not found in this project")
    # Normalize phone
    phone_e164 = None
    if payload.phone:
        try:
            norm = normalize_israeli_phone(payload.phone)
            phone_e164 = norm.get("phone_e164")
        except Exception:
            phone_e164 = payload.phone  # fallback — don't block on validation
    doc_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": doc_id,
        **payload.dict(),
        "phone": phone_e164,
        "created_at": now, "created_by": user["id"],
        "updated_at": now, "updated_by": user["id"],
        "deleted_at": None, "deleted_by": None, "deletion_reason": None,
        "retention_until": retention_until_7_years(),
    }
    await db.workers.insert_one(doc)
    await _audit("worker", doc_id, "create", user["id"], {
        "project_id": payload.project_id,
        "contractor_company_id": payload.contractor_company_id,
        "full_name": payload.full_name,
        "id_number_last4": payload.id_number[-4:],  # PII masked in audit
        "trade": payload.trade,
    })
    return {**doc, "id": doc_id}


@router.get("/workers", response_model=list[WorkerListItem])
async def list_workers(
    project_id: str = Query(...),
    contractor_company_id: Optional[str] = Query(None),
    trade: Optional[str] = Query(None),
    training_status: Optional[str] = Query(None),  # valid|expired|expiring_30d
    user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    _require_feature_enabled()
    await _check_project_read_access(user, project_id)
    q = {"project_id": project_id, "deleted_at": None}
    if contractor_company_id:
        q["contractor_company_id"] = contractor_company_id
    if trade:
        q["trade"] = trade
    workers = await db.workers.find(q).sort("full_name", 1).to_list(5000)

    # Batch-fetch training summaries (one query, grouped)
    worker_ids = [w["_id"] for w in workers]
    trainings = await db.worker_trainings.find({
        "worker_id": {"$in": worker_ids}, "deleted_at": None
    }).to_list(50000)
    summary_by_worker = {}
    for t in trainings:
        _, status = compute_training_status(t["signed_or_certified_date"], t["valid_months"])
        bucket = summary_by_worker.setdefault(t["worker_id"], {"valid": 0, "expired": 0, "expiring_30d": 0, "once_lifetime": 0})
        bucket[status] = bucket.get(status, 0) + 1

    result = []
    for w in workers:
        summary = summary_by_worker.get(w["_id"], {"valid": 0, "expired": 0, "expiring_30d": 0, "once_lifetime": 0})
        # Post-filter by training_status if requested
        if training_status == "valid" and summary["valid"] == 0:
            continue
        if training_status == "expired" and summary["expired"] == 0:
            continue
        if training_status == "expiring_30d" and summary["expiring_30d"] == 0:
            continue
        result.append({
            "id": w["_id"],
            "project_id": w["project_id"],
            "contractor_company_id": w["contractor_company_id"],
            "full_name": w["full_name"],
            "id_number_masked": mask_id_number(w["id_number"]),
            "phone": w.get("phone"),
            "trade": w.get("trade"),
            "photo_url": w.get("photo_url"),
            "training_summary": summary,
        })
    return result


@router.get("/workers/{worker_id}", response_model=Worker)
async def get_worker_detail(
    worker_id: str,
    user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Returns FULL id_number — management roles only."""
    _require_feature_enabled()
    worker = await db.workers.find_one({"_id": worker_id, "deleted_at": None})
    if not worker:
        raise HTTPException(404)
    await _check_project_access(user, worker["project_id"])  # management only
    return {**worker, "id": worker["_id"]}


@router.put("/workers/{worker_id}", response_model=Worker)
async def update_worker(
    worker_id: str,
    payload: WorkerUpdate,
    user: dict = Depends(require_roles('project_manager', 'management_team')),
    db = Depends(get_db),
):
    _require_feature_enabled()
    existing = await db.workers.find_one({"_id": worker_id, "deleted_at": None})
    if not existing:
        raise HTTPException(404)
    await _check_project_access(user, existing["project_id"])
    patch = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    if "phone" in patch:
        try:
            patch["phone"] = normalize_israeli_phone(patch["phone"]).get("phone_e164")
        except Exception:
            pass
    patch["updated_at"] = _now()
    patch["updated_by"] = user["id"]
    # Audit: mask PII
    audit_patch = {**patch}
    if "id_number" in audit_patch:
        audit_patch["id_number_last4"] = audit_patch.pop("id_number")[-4:]
    await db.workers.update_one({"_id": worker_id}, {"$set": patch})
    await _audit("worker", worker_id, "update", user["id"], audit_patch)
    doc = await db.workers.find_one({"_id": worker_id})
    return {**doc, "id": doc["_id"]}


@router.delete("/workers/{worker_id}")
async def soft_delete_worker(
    worker_id: str,
    user: dict = Depends(require_roles('project_manager', 'management_team')),
    db = Depends(get_db),
):
    _require_feature_enabled()
    existing = await db.workers.find_one({"_id": worker_id, "deleted_at": None})
    if not existing:
        raise HTTPException(404)
    await _check_project_access(user, existing["project_id"])
    await db.workers.update_one(
        {"_id": worker_id},
        {"$set": {"deleted_at": _now(), "deleted_by": user["id"], "deletion_reason": "user"}}
    )
    # Cascade soft-delete workers' trainings
    await db.worker_trainings.update_many(
        {"worker_id": worker_id, "deleted_at": None},
        {"$set": {"deleted_at": _now(), "deleted_by": user["id"], "deletion_reason": "worker_cascade"}}
    )
    await _audit("worker", worker_id, "soft_delete", user["id"], {"reason": "user"})
    return {"ok": True}


# ============ WORKER TRAINING TYPES (read-only for now; custom in Phase 2) ============

@router.get("/training-types", response_model=list[WorkerTrainingType])
async def list_training_types(
    user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    _require_feature_enabled()
    docs = await db.worker_training_types.find({}).sort("name", 1).to_list(500)
    return [{**d, "id": d["_id"]} for d in docs]


# ============ WORKER TRAININGS ============

@router.post("/trainings", response_model=WorkerTraining)
async def create_training(
    payload: WorkerTrainingCreate,
    user: dict = Depends(require_roles('project_manager', 'management_team')),
    db = Depends(get_db),
):
    _require_feature_enabled()
    await _check_project_access(user, payload.project_id)
    # Validate worker in same project
    worker = await db.workers.find_one({
        "_id": payload.worker_id, "project_id": payload.project_id, "deleted_at": None
    })
    if not worker:
        raise HTTPException(400, "Worker not found in this project")
    # Validate training type exists
    tt = await db.worker_training_types.find_one({"_id": payload.training_type_id})
    if not tt:
        raise HTTPException(400, "Training type not found")
    # Enforce submission method requirements
    if payload.submission_method == WorkerTrainingSubmissionMethod.SCANNED:
        if not payload.document_url:
            raise HTTPException(400, "document_url required for scanned submission")
    elif payload.submission_method == WorkerTrainingSubmissionMethod.IN_APP:
        if not payload.signature_url or not payload.signer_user_id:
            raise HTTPException(400, "signature_url + signer_user_id required for in-app")

    expires_at, status = compute_training_status(payload.signed_or_certified_date, payload.valid_months)
    doc_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": doc_id,
        **payload.dict(),
        "expires_at": expires_at,
        "status": status,
        "created_at": now, "created_by": user["id"],
        "updated_at": now, "updated_by": user["id"],
        "deleted_at": None, "deleted_by": None, "deletion_reason": None,
        "retention_until": retention_until_7_years(),
    }
    await db.worker_trainings.insert_one(doc)
    await _audit("worker_training", doc_id, "create", user["id"], {
        "worker_id": payload.worker_id,
        "training_type_id": payload.training_type_id,
        "submission_method": payload.submission_method.value,
        "expires_at": expires_at,
    })
    return {**doc, "id": doc_id}


@router.get("/trainings", response_model=list[WorkerTraining])
async def list_trainings(
    project_id: str = Query(...),
    worker_id: Optional[str] = Query(None),
    training_type_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),  # valid|expired|expiring_30d|once_lifetime
    user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    _require_feature_enabled()
    await _check_project_read_access(user, project_id)
    q = {"project_id": project_id, "deleted_at": None}
    if worker_id:
        q["worker_id"] = worker_id
    if training_type_id:
        q["training_type_id"] = training_type_id
    docs = await db.worker_trainings.find(q).sort("signed_or_certified_date", -1).to_list(5000)
    # Recompute status on read (drift-safe)
    result = []
    for d in docs:
        expires_at, st = compute_training_status(d["signed_or_certified_date"], d["valid_months"])
        if status and st != status:
            continue
        result.append({**d, "id": d["_id"], "expires_at": expires_at, "status": st})
    return result


@router.delete("/trainings/{training_id}")
async def soft_delete_training(
    training_id: str,
    user: dict = Depends(require_roles('project_manager', 'management_team')),
    db = Depends(get_db),
):
    _require_feature_enabled()
    existing = await db.worker_trainings.find_one({"_id": training_id, "deleted_at": None})
    if not existing:
        raise HTTPException(404)
    await _check_project_access(user, existing["project_id"])
    await db.worker_trainings.update_one(
        {"_id": training_id},
        {"$set": {"deleted_at": _now(), "deleted_by": user["id"], "deletion_reason": "user"}}
    )
    await _audit("worker_training", training_id, "soft_delete", user["id"], {"reason": "user"})
    return {"ok": True}
```

### Task 7 — Register router in server

**File:** `backend/server.py`

Find where other routers are registered (search for `app.include_router(`), add:

```python
from contractor_ops.safety_router import router as safety_router
app.include_router(safety_router)
```

### Task 8 — Auto-seed "אין חברה" placeholder on project creation

**File:** `backend/contractor_ops/router.py`

Find the project creation endpoint (search `@router.post("/projects"` or similar). After project document is inserted but before returning, add:

```python
# Seed "אין חברה" placeholder for safety module (no-op if safety disabled — still seed, cheap)
from .safety_seed import seed_no_company_placeholder
await seed_no_company_placeholder(db, project_id=new_project_id, user_id=user["id"])
```

**File:** `backend/contractor_ops/safety_seed.py` (extend existing file)

```python
async def seed_no_company_placeholder(db, project_id: str, user_id: str):
    """Creates 'אין חברה' placeholder for a new project. Idempotent."""
    existing = await db.contractor_companies.find_one({"project_id": project_id, "is_placeholder": True})
    if existing:
        return
    import uuid
    now = _now()
    doc = {
        "_id": str(uuid.uuid4()),
        "project_id": project_id,
        "name": "אין חברה",
        "registry_number": None,
        "is_placeholder": True,
        "created_at": now, "created_by": user_id,
        "updated_at": now, "updated_by": user_id,
        "deleted_at": None, "deleted_by": None, "deletion_reason": None,
        "retention_until": None,
    }
    await db.contractor_companies.insert_one(doc)
```

**STOP. PUSH TO STAGING. RUN VERIFY STEP 1-3. WAIT FOR APPROVAL BEFORE PHASE 1c.**

---

## Phase 1c — Frontend UI

### Task 9 — safetyService in api.js

**File:** `frontend/src/services/api.js`

Add a new export near `qcService` (around line 1182, mirror its shape):

```javascript
export const safetyService = {
  // Contractor companies
  listContractorCompanies: (projectId) =>
    api.get(`/api/safety/contractor-companies`, { params: { project_id: projectId } }),
  createContractorCompany: (data) =>
    api.post(`/api/safety/contractor-companies`, data),
  updateContractorCompany: (id, data) =>
    api.put(`/api/safety/contractor-companies/${id}`, data),
  deleteContractorCompany: (id) =>
    api.delete(`/api/safety/contractor-companies/${id}`),

  // Workers
  listWorkers: (projectId, filters = {}) =>
    api.get(`/api/safety/workers`, { params: { project_id: projectId, ...filters } }),
  getWorker: (id) => api.get(`/api/safety/workers/${id}`),
  createWorker: (data) => api.post(`/api/safety/workers`, data),
  updateWorker: (id, data) => api.put(`/api/safety/workers/${id}`, data),
  deleteWorker: (id) => api.delete(`/api/safety/workers/${id}`),

  // Training types (read-only Phase 1)
  listTrainingTypes: () => api.get(`/api/safety/training-types`),

  // Trainings
  listTrainings: (projectId, filters = {}) =>
    api.get(`/api/safety/trainings`, { params: { project_id: projectId, ...filters } }),
  createTraining: (data) => api.post(`/api/safety/trainings`, data),
  deleteTraining: (id) => api.delete(`/api/safety/trainings/${id}`),
};
```

### Task 10 — Tab registration in ProjectControlPage

**File:** `frontend/src/pages/ProjectControlPage.js`

At the top with other lucide imports:
```javascript
import { /* existing */, ShieldAlert } from 'lucide-react';
```

Locate `workTabs` array (around line 3497) and add:

```javascript
{
  id: 'safety',
  label: 'בטיחות ויומן עבודה',
  icon: ShieldAlert,
  hidden: !['project_manager', 'management_team'].includes(myRole)
          || !features?.safety_module_enabled,
},
```

Locate `handleWorkTab` dispatcher (around line 3506) and route `'safety'` to render the new page component (see Task 11).

### Task 11 — SafetyModule page

**File:** `frontend/src/pages/SafetyModule.js` (create new file)

Single-page layout with 3 sections inside (collapsible), lazy-loaded from ProjectControlPage:

```javascript
import React, { useState, useEffect, useMemo } from 'react';
import { toast } from 'sonner';
import { ChevronDown, ChevronRight, Plus, Building2, User, GraduationCap } from 'lucide-react';
import { safetyService } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import ContractorCompaniesBlock from '../components/safety/ContractorCompaniesBlock';
import AddContractorCompanyModal from '../components/safety/AddContractorCompanyModal';
import AddWorkerModal from '../components/safety/AddWorkerModal';
import AddTrainingModal from '../components/safety/AddTrainingModal';
import SafetyFiltersBar from '../components/safety/SafetyFiltersBar';
import SafetyExportMenu from '../components/safety/SafetyExportMenu';

export default function SafetyModule({ projectId, myRole }) {
  const { user } = useAuth();
  const isManagement = ['project_manager', 'management_team'].includes(myRole);

  const [companies, setCompanies] = useState([]);
  const [workers, setWorkers] = useState([]);
  const [trainingTypes, setTrainingTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ contractor_company_id: null, trade: null, training_status: null });

  const [addCompanyOpen, setAddCompanyOpen] = useState(false);
  const [addWorkerForCompany, setAddWorkerForCompany] = useState(null);
  const [addTrainingForWorker, setAddTrainingForWorker] = useState(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [c, w, t] = await Promise.all([
        safetyService.listContractorCompanies(projectId),
        safetyService.listWorkers(projectId, filters),
        safetyService.listTrainingTypes(),
      ]);
      setCompanies(c.data);
      setWorkers(w.data);
      setTrainingTypes(t.data);
    } catch (e) {
      toast.error('טעינת נתוני בטיחות נכשלה');
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, [projectId, JSON.stringify(filters)]);

  const workersByCompany = useMemo(() => {
    const map = {};
    for (const w of workers) {
      (map[w.contractor_company_id] ||= []).push(w);
    }
    return map;
  }, [workers]);

  if (loading) return <div className="p-4 text-center" dir="rtl">טוען...</div>;

  return (
    <div dir="rtl" className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">בטיחות ויומן עבודה</h2>
        <div className="flex gap-2">
          {isManagement && (
            <button
              onClick={() => setAddCompanyOpen(true)}
              className="px-3 py-2 bg-orange-500 text-white rounded-md flex items-center gap-1 text-sm"
            >
              <Plus className="w-4 h-4" /> קבלן משנה
            </button>
          )}
          <SafetyExportMenu projectId={projectId} filters={filters} />
        </div>
      </div>

      <SafetyFiltersBar
        companies={companies}
        filters={filters}
        setFilters={setFilters}
      />

      {companies.length === 0 && (
        <div className="text-center text-gray-500 py-8">
          אין קבלני משנה עדיין. לחץ "קבלן משנה" כדי להוסיף.
        </div>
      )}

      {companies.map(c => (
        <ContractorCompaniesBlock
          key={c.id}
          company={c}
          workers={workersByCompany[c.id] || []}
          isManagement={isManagement}
          onAddWorker={() => setAddWorkerForCompany(c)}
          onAddTraining={(w) => setAddTrainingForWorker(w)}
          onRefresh={loadAll}
        />
      ))}

      {addCompanyOpen && (
        <AddContractorCompanyModal
          projectId={projectId}
          onClose={() => setAddCompanyOpen(false)}
          onCreated={() => { setAddCompanyOpen(false); loadAll(); }}
        />
      )}
      {addWorkerForCompany && (
        <AddWorkerModal
          projectId={projectId}
          company={addWorkerForCompany}
          onClose={() => setAddWorkerForCompany(null)}
          onCreated={() => { setAddWorkerForCompany(null); loadAll(); }}
        />
      )}
      {addTrainingForWorker && (
        <AddTrainingModal
          projectId={projectId}
          worker={addTrainingForWorker}
          trainingTypes={trainingTypes}
          onClose={() => setAddTrainingForWorker(null)}
          onCreated={() => { setAddTrainingForWorker(null); loadAll(); }}
        />
      )}
    </div>
  );
}
```

### Task 12 — Component: ContractorCompaniesBlock (collapsible)

**File:** `frontend/src/components/safety/ContractorCompaniesBlock.js` (create)

Single expandable card per company. Collapse rules per concept decision 4:
- Empty block → collapsed default
- < 3 workers → expanded default
- ≥ 3 workers → collapsed default

Display:
- Company header (name + placeholder badge if `is_placeholder` + worker count)
- Expand arrow
- When expanded: list of workers with training summary badges (valid/expired/expiring_30d)
- Each worker row → click opens training list modal OR inline expand

```javascript
import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Plus, UserCircle } from 'lucide-react';
import WorkerRow from './WorkerRow';

export default function ContractorCompaniesBlock({
  company, workers, isManagement, onAddWorker, onAddTraining, onRefresh
}) {
  const defaultCollapsed = workers.length === 0 || workers.length >= 3;
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <div className="bg-white border rounded-lg shadow-sm">
      <div
        className="flex items-center justify-between p-3 cursor-pointer"
        onClick={() => setCollapsed(c => !c)}
      >
        <div className="flex items-center gap-2">
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          <span className="font-semibold">{company.name}</span>
          {company.is_placeholder && (
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">מיוחד</span>
          )}
          <span className="text-sm text-gray-500">({workers.length})</span>
        </div>
        {isManagement && (
          <button
            onClick={(e) => { e.stopPropagation(); onAddWorker(); }}
            className="text-sm text-orange-600 flex items-center gap-1 hover:bg-orange-50 px-2 py-1 rounded"
          >
            <Plus className="w-3 h-3" /> עובד
          </button>
        )}
      </div>
      {!collapsed && (
        <div className="border-t">
          {workers.length === 0 ? (
            <div className="p-3 text-sm text-gray-400 text-center">אין עובדים</div>
          ) : (
            workers.map(w => (
              <WorkerRow
                key={w.id}
                worker={w}
                isManagement={isManagement}
                onAddTraining={() => onAddTraining(w)}
                onRefresh={onRefresh}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
```

### Task 13 — Component: WorkerRow

**File:** `frontend/src/components/safety/WorkerRow.js` (create)

Each worker row shows: photo/placeholder, full_name, trade, 3 badges (valid/expired/expiring), click to expand trainings inline.

```javascript
import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Plus, UserCircle, AlertCircle, CheckCircle2, Clock } from 'lucide-react';
import { safetyService } from '../../services/api';
import { toast } from 'sonner';

export default function WorkerRow({ worker, isManagement, onAddTraining, onRefresh }) {
  const [expanded, setExpanded] = useState(false);
  const [trainings, setTrainings] = useState(null);

  const { valid = 0, expired = 0, expiring_30d = 0 } = worker.training_summary || {};

  const loadTrainings = async () => {
    try {
      const res = await safetyService.listTrainings(worker.project_id, { worker_id: worker.id });
      setTrainings(res.data);
    } catch (e) {
      toast.error('טעינת הדרכות נכשלה');
    }
  };

  useEffect(() => { if (expanded && trainings === null) loadTrainings(); }, [expanded]);

  return (
    <div className="border-b last:border-b-0">
      <div className="flex items-center justify-between p-3 hover:bg-gray-50 cursor-pointer"
           onClick={() => setExpanded(e => !e)}>
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {expanded ? <ChevronDown className="w-4 h-4 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 flex-shrink-0" />}
          <UserCircle className="w-8 h-8 text-gray-400 flex-shrink-0" />
          <div className="min-w-0">
            <div className="font-medium truncate">{worker.full_name}</div>
            <div className="text-xs text-gray-500">
              {worker.trade || '—'} · {worker.id_number_masked}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {expired > 0 && <span className="flex items-center gap-0.5 text-red-600"><AlertCircle className="w-3 h-3" />{expired}</span>}
          {expiring_30d > 0 && <span className="flex items-center gap-0.5 text-amber-600"><Clock className="w-3 h-3" />{expiring_30d}</span>}
          {valid > 0 && <span className="flex items-center gap-0.5 text-green-600"><CheckCircle2 className="w-3 h-3" />{valid}</span>}
        </div>
      </div>
      {expanded && (
        <div className="bg-gray-50 border-t p-3">
          {isManagement && (
            <button
              onClick={onAddTraining}
              className="mb-2 text-sm text-orange-600 flex items-center gap-1 hover:bg-orange-50 px-2 py-1 rounded"
            >
              <Plus className="w-3 h-3" /> הוסף הדרכה
            </button>
          )}
          {trainings === null ? (
            <div className="text-xs text-gray-400">טוען...</div>
          ) : trainings.length === 0 ? (
            <div className="text-xs text-gray-400">אין הדרכות מתועדות</div>
          ) : (
            <div className="space-y-1">
              {trainings.map(t => (
                <TrainingPill key={t.id} training={t} isManagement={isManagement} onDeleted={() => { loadTrainings(); onRefresh(); }} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TrainingPill({ training, isManagement, onDeleted }) {
  const color = {
    valid: 'bg-green-50 border-green-300 text-green-700',
    expired: 'bg-red-50 border-red-300 text-red-700',
    expiring_30d: 'bg-amber-50 border-amber-300 text-amber-700',
    once_lifetime: 'bg-blue-50 border-blue-300 text-blue-700',
  }[training.status] || 'bg-gray-50 border-gray-200 text-gray-600';
  return (
    <div className={`flex items-center justify-between px-2 py-1 border-r-4 rounded text-xs ${color}`}>
      <div>
        <span className="font-medium">{training.training_type_name || training.training_type_id}</span>
        {training.expires_at && (
          <span className="ms-2 text-gray-500">
            פג: {new Date(training.expires_at).toLocaleDateString('he-IL')}
          </span>
        )}
      </div>
      {isManagement && (
        <button
          onClick={async () => {
            if (!window.confirm('למחוק הדרכה זו?')) return;
            try {
              await safetyService.deleteTraining(training.id);
              onDeleted();
            } catch (e) { toast.error('מחיקה נכשלה'); }
          }}
          className="text-red-500 hover:text-red-700 text-xs"
        >✕</button>
      )}
    </div>
  );
}
```

### Task 14 — Modals

**Files to create:**
- `frontend/src/components/safety/AddContractorCompanyModal.js` — form: name (required), registry_number (optional)
- `frontend/src/components/safety/AddWorkerModal.js` — form: full_name, id_number, phone, trade, photo_url (optional) — uses imageCompress for photo
- `frontend/src/components/safety/AddTrainingModal.js` — **DUAL-TAB**:
  - Tab 1: "סרוק מסמך" → date picker (תאריך הסמכה) + valid_months + upload doc
  - Tab 2: "חתום באפליקציה" → date picker auto-filled today (תאריך חתימה) + valid_months + signature canvas + translator optional
  - Submit routes to `submission_method: 'scanned'|'in_app'`
- `frontend/src/components/safety/SafetyFiltersBar.js` — dropdowns: company, trade, training status
- `frontend/src/components/safety/SafetyExportMenu.js` — dropdown with 3 options: PDF / CSV / JSON

**Pattern — use existing Radix Dialog wrapper from codebase.** Do not introduce a new dialog library. Every form submit uses axios via safetyService. Success → `toast.success`; error → `toast.error`.

**Image compression:** use existing `frontend/src/utils/imageCompress.js` for photo_url in AddWorkerModal (800KB / 1600px / JPEG 0.7).

**Signature canvas:** reuse the pattern from handover signatures. Search for existing signature component:
```
grep -rn "canvas" frontend/src/components/ | grep -i sign | head -10
```
Use the same component if found; otherwise a simple `<canvas>` with mouse/touch events is fine.

---

## Phase 1d — Export + Filters + E2E

### Task 15 — Backend export endpoints

**File:** `backend/contractor_ops/safety_router.py` (append to existing file)

```python
from fastapi.responses import StreamingResponse, Response
import csv, io, json

@router.get("/export/workers")
async def export_workers(
    project_id: str = Query(...),
    format: str = Query("json"),  # json | csv | pdf
    contractor_company_id: Optional[str] = Query(None),
    trade: Optional[str] = Query(None),
    training_status: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    _require_feature_enabled()
    await _check_project_read_access(user, project_id)
    # Reuse list_workers logic (call internally)
    rows = await list_workers(project_id, contractor_company_id, trade, training_status, user, db)
    if format == "json":
        return rows
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["שם מלא", "ת.ז. (מוצפנת)", "טלפון", "מקצוע", "חברה", "בתוקף", "פגו", "פגים בקרוב"])
        companies = {c["_id"]: c["name"] for c in await db.contractor_companies.find({"project_id": project_id}).to_list(1000)}
        for r in rows:
            s = r.get("training_summary", {})
            w.writerow([r["full_name"], r["id_number_masked"], r.get("phone") or "", r.get("trade") or "",
                        companies.get(r["contractor_company_id"], ""),
                        s.get("valid", 0), s.get("expired", 0), s.get("expiring_30d", 0)])
        await _audit("worker_export", project_id, "export_csv", user["id"], {"row_count": len(rows)})
        return Response(content=buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="workers-{project_id}.csv"'})
    if format == "pdf":
        # Defer to render service — reuse pattern from qc/handover PDF rendering
        from services.pdf_render import render_workers_pdf  # create this helper in services/
        pdf_bytes = await render_workers_pdf(project_id, rows, db)
        await _audit("worker_export", project_id, "export_pdf", user["id"], {"row_count": len(rows)})
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="workers-{project_id}.pdf"'})
    raise HTTPException(400, f"Unsupported format: {format}")
```

**File:** `backend/services/pdf_render.py` (extend existing service OR create helper)

Use the **existing** PDF rendering pattern from handover/qc (search for current PDF services):
```
grep -rn "def render" backend/services/ | grep -i pdf
grep -rn "weasyprint\|reportlab\|pdfkit" backend/ | head -10
```

Follow whatever PDF stack is already in use. DO NOT add a new library.

Basic template (`backend/templates/workers_export.html`) — Hebrew RTL, company groupings, training summary per worker. Use same CSS/font stack as existing handover templates.

### Task 16 — Frontend export menu implementation

**File:** `frontend/src/components/safety/SafetyExportMenu.js` (created in Task 14 — implementation)

```javascript
import React, { useState } from 'react';
import { Download } from 'lucide-react';
import { getAuthHeader } from '../../services/api';

export default function SafetyExportMenu({ projectId, filters }) {
  const [open, setOpen] = useState(false);

  const doExport = async (format) => {
    setOpen(false);
    const params = new URLSearchParams({
      project_id: projectId,
      format,
      ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v))
    });
    const url = `/api/safety/export/workers?${params.toString()}`;
    const res = await fetch(url, { headers: getAuthHeader() });
    if (!res.ok) { alert('ייצוא נכשל'); return; }
    if (format === 'json') {
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      triggerDownload(blob, `workers-${projectId}.json`);
    } else {
      const blob = await res.blob();
      triggerDownload(blob, `workers-${projectId}.${format}`);
    }
  };

  const triggerDownload = (blob, filename) => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="relative">
      <button onClick={() => setOpen(o => !o)} className="px-3 py-2 border rounded-md flex items-center gap-1 text-sm">
        <Download className="w-4 h-4" /> ייצוא
      </button>
      {open && (
        <div className="absolute left-0 mt-1 bg-white border rounded shadow-md z-10">
          <button onClick={() => doExport('pdf')} className="block w-full text-right px-4 py-2 text-sm hover:bg-gray-50">PDF</button>
          <button onClick={() => doExport('csv')} className="block w-full text-right px-4 py-2 text-sm hover:bg-gray-50">CSV (אקסל)</button>
          <button onClick={() => doExport('json')} className="block w-full text-right px-4 py-2 text-sm hover:bg-gray-50">JSON</button>
        </div>
      )}
    </div>
  );
}
```

### Task 17 — E2E test script

**File:** `backend/tests/test_safety_phase1.py` (create new)

Pytest-style; run against a throwaway test DB:

```python
# Pseudocode — adapt to existing test harness
def test_safety_e2e(client, make_user, make_project):
    pm = make_user(role="project_manager")
    proj = make_project(owner=pm)
    # 1. create company
    r = client.post("/api/safety/contractor-companies",
                   json={"project_id": proj.id, "name": "קבלן חשמל בע״מ"},
                   headers=pm.auth)
    assert r.status_code == 200
    company_id = r.json()["id"]
    # 2. verify "אין חברה" placeholder exists for this project
    r = client.get(f"/api/safety/contractor-companies?project_id={proj.id}", headers=pm.auth)
    placeholders = [c for c in r.json() if c["is_placeholder"]]
    assert len(placeholders) == 1
    # 3. create worker
    r = client.post("/api/safety/workers", json={
        "project_id": proj.id, "contractor_company_id": company_id,
        "full_name": "יוסי כהן", "id_number": "123456789", "trade": "חשמלאי",
    }, headers=pm.auth)
    worker_id = r.json()["id"]
    # 4. list workers → id_number_masked = "****6789"
    r = client.get(f"/api/safety/workers?project_id={proj.id}", headers=pm.auth)
    assert r.json()[0]["id_number_masked"] == "****6789"
    # 5. add training (scanned)
    training_types = client.get("/api/safety/training-types", headers=pm.auth).json()
    tt_id = next(t["id"] for t in training_types if "אתר" in t["name"])
    r = client.post("/api/safety/trainings", json={
        "project_id": proj.id, "worker_id": worker_id, "training_type_id": tt_id,
        "submission_method": "scanned",
        "signed_or_certified_date": "2026-04-01T00:00:00+00:00",
        "valid_months": 12,
        "document_url": "https://fake/doc.pdf",
    }, headers=pm.auth)
    assert r.status_code == 200
    assert r.json()["status"] in ["valid", "expiring_30d"]
    # 6. export CSV
    r = client.get(f"/api/safety/export/workers?project_id={proj.id}&format=csv", headers=pm.auth)
    assert r.status_code == 200
    assert "יוסי כהן" in r.text
    assert "123456789" not in r.text  # PII masked
    # 7. audit trail exists
    events = await db.audit_events.find({"entity_type": {"$in": ["worker", "worker_training", "contractor_company"]}}).to_list(100)
    assert len(events) >= 4  # company-create, worker-create, training-create, export
    # 8. soft-delete cascade
    r = client.delete(f"/api/safety/workers/{worker_id}", headers=pm.auth)
    assert r.status_code == 200
    # worker's trainings also soft-deleted
    r = client.get(f"/api/safety/trainings?project_id={proj.id}&worker_id={worker_id}", headers=pm.auth)
    assert len(r.json()) == 0  # all filtered out by deleted_at
```

---

## Relevant files

### Backend (existing — reference only)
- `backend/config.py` (lines 67-185) — env-based feature flags
- `backend/contractor_ops/config_router.py` (lines 8-18) — `/api/config/features`
- `backend/contractor_ops/router.py`:
  - line ~103 — `_now()` (UTC ISO string)
  - line ~337 — `_check_project_access`
  - line ~324 — `_check_project_read_access`
  - line ~372 — `_get_project_role`
  - line ~413 — `MANAGEMENT_ROLES`
  - line ~433 — `_audit()`
  - `require_roles` — search for def
- `backend/contractor_ops/schemas.py`:
  - lines 32-37 — `ManagementSubRole` (ALREADY EXISTS — use `sub_role`)
  - lines 61-65 — `Role`
  - line ~305 — Tasks pattern (schema style to mirror)
- `backend/contractor_ops/tasks_router.py`:
  - lines 30-37 — canonical route protection pattern
- `backend/contractor_ops/phone_utils.py` — `normalize_israeli_phone()`
- `backend/services/object_storage.py` — if uploading docs/signatures, use `save_bytes` + presigned URL (15-min TTL)
- `backend/contractor_ops/upload_safety.py` — for file validation
- `backend/server.py` (lines 501-616) — create_index block
- `backend/tests/` — existing test harness to extend

### Backend (new files)
- `backend/contractor_ops/safety_router.py`
- `backend/contractor_ops/safety_seed.py`
- `backend/contractor_ops/safety_utils.py`
- `backend/tests/test_safety_phase1.py`
- `backend/templates/workers_export.html` (for PDF)

### Frontend (existing — reference only)
- `frontend/src/services/api.js` (around line 1182 — `qcService` pattern)
- `frontend/src/pages/ProjectControlPage.js`:
  - line ~3497 — `workTabs` array
  - line ~3506 — `handleWorkTab` dispatcher
  - line ~3295 — `proj.my_role` canonical
- `frontend/src/contexts/AuthContext.js` — `useAuth()` → `{ user, features, ... }`
- `frontend/src/utils/imageCompress.js` — for photo upload
- Existing signature canvas component — grep `canvas` in components/

### Frontend (new files)
- `frontend/src/pages/SafetyModule.js`
- `frontend/src/components/safety/ContractorCompaniesBlock.js`
- `frontend/src/components/safety/WorkerRow.js`
- `frontend/src/components/safety/AddContractorCompanyModal.js`
- `frontend/src/components/safety/AddWorkerModal.js`
- `frontend/src/components/safety/AddTrainingModal.js`
- `frontend/src/components/safety/SafetyFiltersBar.js`
- `frontend/src/components/safety/SafetyExportMenu.js`

---

## DO NOT

- ❌ **Do not touch** the existing defects/QC/handover routers, collections, or components. The safety module is fully isolated.
- ❌ **Do not add** a new Pydantic style — mirror Tasks pattern, not QC (which uses dict).
- ❌ **Do not write new auth helpers** — use `require_roles`, `_check_project_access`, `_check_project_read_access` from `contractor_ops/router.py`. Period.
- ❌ **Do not skip** `_audit()` on any mutation. SOC2 compliance from day 1.
- ❌ **Do not store** `datetime` objects — always ISO string via `_now()`. Consistency with rest of codebase.
- ❌ **Do not use** `ObjectId` — string UUIDs only. `str(uuid.uuid4())`.
- ❌ **Do not use** `now_il()` or any TZ other than UTC.
- ❌ **Do not hard-delete** anything. All deletes are soft (`deleted_at` + `deleted_by` + `deletion_reason`).
- ❌ **Do not expose** full `id_number` in list endpoints. Only `/workers/{id}` returns full (management-only via `_check_project_access`).
- ❌ **Do not log** full `id_number`, phone, or name to console in production. Audit payloads use `id_number_last4`.
- ❌ **Do not write** your own PDF generator. Use the existing stack (search first, reuse helper).
- ❌ **Do not introduce** Redux, Zustand, React Hook Form, Formik, i18next, date-picker libs, or any new top-level deps. AuthContext + component state + Radix + Sonner + lucide are enough.
- ❌ **Do not add** `WebkitOverflowScrolling: 'touch'` — kills iOS.
- ❌ **Do not** use `modal={true}` on Radix Dialog — causes pointer-events: none bleed.
- ❌ **Do not enable** the feature flag in production. `ENABLE_SAFETY_MODULE` stays `false` until explicit approval per tenant.
- ❌ **Do not rename** existing `sub_role` field or `ManagementSubRole` enum values. They exist; do not touch.
- ❌ **Do not modify** `deletion_router.py` in Phase 1. Retention enforcement comes later.
- ❌ **Do not change** Capacitor config or any native files. This is a pure JS/Python change — ships via `./deploy.sh --prod` + Capgo OTA. No `./ship.sh` needed.
- ❌ **Do not over-engineer** — Phase 1 is 4 collections. No "generic safety framework", no abstract base classes.

---

## VERIFY (after each phase)

### After Phase 1a (backend foundation)
```
# 1. Server starts cleanly
cd backend && uvicorn server:app --reload
# expect: no errors, no index conflicts

# 2. Feature flag off → endpoints return 404
curl http://localhost:8000/api/safety/contractor-companies?project_id=test
# expect: 404 "Safety module not enabled"

# 3. Features endpoint includes flag
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/config/features
# expect JSON with: feature_flags.safety_module_enabled: false

# 4. Indices created
mongo brikops --eval 'db.contractor_companies.getIndexes(); db.workers.getIndexes(); db.worker_trainings.getIndexes()'
# expect: 11 safety-related indices total

# 5. Training types seeded
mongo brikops --eval 'db.worker_training_types.countDocuments({is_seeded: true})'
# expect: 8
```

### After Phase 1b (routes)
```
# Enable flag for dev tenant
export ENABLE_SAFETY_MODULE=true
# restart backend

# 1. Unauthorized user → 403
curl -H "Authorization: Bearer $CONTRACTOR_TOKEN" \
  -X POST http://localhost:8000/api/safety/contractor-companies \
  -d '{"project_id":"...","name":"Test"}'
# expect: 403

# 2. PM can create company
curl -H "Authorization: Bearer $PM_TOKEN" \
  -X POST http://localhost:8000/api/safety/contractor-companies \
  -d '{"project_id":"$PROJ","name":"חברת בדיקה"}'
# expect: 200, returns company with id, created_at, retention_until

# 3. "אין חברה" auto-seeded
curl "http://localhost:8000/api/safety/contractor-companies?project_id=$PROJ"
# expect: includes item with is_placeholder=true, name="אין חברה"

# 4. Create worker — ID masked in list
curl -X POST ... /api/safety/workers \
  -d '{"project_id":"$PROJ","contractor_company_id":"$C","full_name":"יוסי","id_number":"123456789"}'
curl .../api/safety/workers?project_id=$PROJ
# expect: id_number_masked="****6789", NO raw id_number

# 5. Get full worker by id → returns full id_number
curl .../api/safety/workers/$W
# expect: id_number="123456789"

# 6. Soft-delete — not actually deleted
curl -X DELETE .../api/safety/workers/$W
mongo brikops --eval "db.workers.findOne({_id: '$W'}).deleted_at"
# expect: ISO timestamp, NOT null

# 7. List excludes deleted
curl .../api/safety/workers?project_id=$PROJ
# expect: $W not in list

# 8. Audit events written
mongo brikops --eval "db.audit_events.find({entity_type: 'worker'}).count()"
# expect: >= 2 (create + soft_delete)

# 9. Cannot delete non-empty company
curl -X DELETE .../api/safety/contractor-companies/$C
# expect: 400 "Company has N active workers"
```

### After Phase 1c (UI)
Manual checklist in app:
1. Log in as PM → open project → expect tab "בטיחות ויומן עבודה" visible with shield icon.
2. Log in as contractor role → tab NOT visible.
3. Set `ENABLE_SAFETY_MODULE=false` → tab NOT visible for PM either.
4. Click tab → SafetyModule page loads, shows "אין חברה" block + any companies.
5. Click "+ קבלן משנה" → modal opens → enter name → submit → company appears in list.
6. Click company row → expands → "+ עובד" button visible to PM.
7. Click "+ עובד" → modal → fill name/ID/trade → submit → worker appears.
8. ID masked in worker row (`****1234`).
9. Click worker row → expands → "+ הוסף הדרכה" button.
10. Click → modal with 2 tabs (`סרוק מסמך` / `חתום באפליקציה`).
11. Tab 1: date picker says "תאריך הסמכה", requires doc upload.
12. Tab 2: date picker says "תאריך חתימה" auto-filled today, requires signature canvas.
13. Submit in either tab → training pill appears with correct color (green valid / amber expiring / red expired).
14. Delete training → confirmation → pill disappears.
15. RTL: all text right-aligned, arrows point correct direction.
16. Mobile (Capacitor on real device): all interactive, no horizontal scroll, tap targets 44px+.

### After Phase 1d (export + E2E)
1. Filter by company → only that company's workers shown.
2. Filter by training_status="expired" → only workers with 1+ expired trainings shown.
3. Click "ייצוא" → 3 options: PDF / CSV / JSON.
4. JSON → downloads `workers-{projectId}.json`, valid JSON, PII masked.
5. CSV → opens in Excel, Hebrew renders, ID masked in column.
6. PDF → opens in reader, RTL layout, Hebrew font renders, groupings by company.
7. Run `pytest backend/tests/test_safety_phase1.py` → all green.
8. mongo: `db.audit_events.find({"action": {"$regex": "^export"}}).count()` ≥ 3.
9. Verify no regressions: existing defects / QC / handover / tasks flows still work.

---

## Hand-off checklist for Replit

- [ ] Confirm STEP 0 grep output pasted in response before any code change
- [ ] Phase 1a → PR #1, deploy staging, reply with VERIFY 1a output
- [ ] Phase 1b → PR #2, deploy staging, reply with VERIFY 1b output
- [ ] Phase 1c → PR #3, deploy staging, reply with VERIFY 1c output
- [ ] Phase 1d → PR #4, deploy staging + prod (flag still off), reply with VERIFY 1d output + test report
- [ ] Final: flag stays `false` in prod env until I say to enable for specific tenant

**Deploy command:** `./deploy.sh --prod` (no native changes in Phase 1 — no `./ship.sh` needed).

---

**Spec authored:** 2026-04-22 by Zahi + Claude, based on exhaustive code investigation of existing BrikOps codebase (22+ MongoDB collections mapped, RBAC + auth helpers + audit patterns verified, Israeli safety regulations cross-referenced, SOC2 Type I prerequisites factored in). Parent concept: `future-features/safety-and-worklog-concept.md`.

---

# PART 2 — v2 AMENDMENTS (supersedes v1 where conflicting)

**Added:** 2026-04-22 after UX review with `ui-ux-pro-max` skill, deep re-examination of 4 Cemento PDFs (317 pages total) from מתחם הסופרים 801/806, and live code review of `ProjectDataExportTab.js`, `ProjectControlPage.js`, `companies_router.py`, and `export_router.py`.

**Why amendments, not rewrite:** Part 1 (tasks 1–17) remains the execution backbone. These amendments correct 4 specific architectural issues surfaced after the original spec was drafted. Where an amendment conflicts with Part 1, **Part 2 wins**.

---

## A1 — Architecture collision: REUSE `project_companies` (do not create `contractor_companies`)

**Original (v1):** Create new collection `contractor_companies` with fields `{project_id, name, trade, registry_number, is_placeholder, ...}`.

**Problem discovered:** BrikOps already has a `project_companies` collection with almost-identical schema, served by `backend/contractor_ops/companies_router.py`, displayed in the existing `SECONDARY_TABS` tab "קבלנים וחברות". Creating a second collection would:
- Duplicate data (same contractor entered twice)
- Force UI to reconcile two lists
- Break the existing tab's value

**Amendment (v2):** Extend `project_companies` with the 6 missing safety-specific fields. Do NOT create `contractor_companies`.

### Fields to add to `project_companies`

All additions are `Optional` with safe defaults so existing documents remain valid without backfill.

| Field | Type | Default | Purpose |
|---|---|---|---|
| `registry_number` | `Optional[str]` | `None` | מספר קבלן רשום (רישוי קבלנים) — regulatory |
| `is_placeholder` | `bool` | `False` | True for auto-seeded "אין חברה" placeholder |
| `safety_contact_id` | `Optional[str]` | `None` | Reference to user with `sub_role=safety_officer` for the company |
| `deleted_at` | `Optional[str]` | `None` | ISO timestamp; non-null = soft-deleted |
| `deleted_by` | `Optional[str]` | `None` | user_id who performed soft-delete |
| `deletion_reason` | `Optional[str]` | `None` | Free-text; required when `deleted_at` is set |
| `retention_until` | `str` | `created_at + 7y` | Computed on insert; informational until Phase 4 TTL |

### Migration (one-time on deploy)

```python
# In companies_router startup or dedicated migration script
now_iso = _now()
result = db.project_companies.update_many(
    {"deleted_at": {"$exists": False}},
    [{"$set": {
        "deleted_at": None,
        "deleted_by": None,
        "deletion_reason": None,
        "is_placeholder": False,
        "retention_until": {"$dateAdd": {
            "startDate": {"$toDate": "$created_at"},
            "unit": "year",
            "amount": 7
        }}
    }}]
)
print(f"migrated {result.modified_count} project_companies documents")
```

### Query filter update

Every existing `companies_router.py` read path gets `deleted_at: null` appended:

```python
# BEFORE
cursor = db.project_companies.find({"project_id": project_id})

# AFTER
cursor = db.project_companies.find({"project_id": project_id, "deleted_at": None})
```

### Index additions

```python
db.project_companies.create_index([("project_id", 1), ("deleted_at", 1)])
db.project_companies.create_index([("project_id", 1), ("registry_number", 1)], sparse=True)
```

### New endpoints on existing `companies_router.py`

```
DELETE /api/projects/{project_id}/companies/{company_id}
  body: { "reason": "string" }
  → soft-delete, _audit, returns 200

POST /api/projects/{project_id}/companies/{company_id}/restore
  → admin + sub_role=safety_officer only, un-sets deleted_at, _audit

GET /api/projects/{project_id}/companies/deleted
  → returns soft-deleted companies (admin only)
```

### Consequences for Part 1

- Task 3: drop the `contractor_companies` collection and its indices. Replace with migration of `project_companies`.
- Tasks 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14: everywhere that says `contractor_companies` (collection, service name, component name) — **rename to `project_companies`**. The safety module reads/writes the same collection the existing "קבלנים וחברות" tab reads/writes. There is ONE source of truth for companies per project.
- Task 12 (`ContractorCompaniesBlock` component) renames to `SafetyContractorBlock` and operates on the existing `projectCompanyService` (already imported in `ProjectControlPage.js` line 10) rather than a new service.

---

## A2 — Filter system (NEW — was missing from v1)

**Original (v1):** Frontend filters implemented client-side in Task 11/16.

**Problem discovered:** For projects with 100+ workers and 500+ trainings (realistic after 6 months), client-side filtering is slow, breaks URL-share pattern, and cannot be re-used by export.

**Amendment (v2):** Server-side multi-dimensional filtering with URL-backed query params. Filters drive the UI list AND the export payload.

### 7 filter dimensions

```python
# backend/schemas/safety.py
class SafetyFilters(BaseModel):
    company_id: Optional[List[str]] = None       # multi-select
    profession: Optional[List[str]] = None       # from tradeService
    category: Optional[List[SafetyCategory]] = None  # enum, 10 values
    status: Optional[List[SafetyStatus]] = None  # open, closed, overdue
    severity: Optional[List[int]] = None         # [1,2,3]
    date_from: Optional[str] = None              # ISO
    date_to: Optional[str] = None
    flags: Optional[List[SafetyFlag]] = None     # has_photos, overdue, no_corrective_action, expiring_30d
    q: Optional[str] = None                      # full-text
    limit: int = Field(50, le=200)
    skip: int = Field(0, ge=0)
```

### 10 seeded safety categories (enum)

```python
class SafetyCategory(str, Enum):
    HEIGHT_WORK = "height_work"              # עבודה בגובה
    SCAFFOLDING = "scaffolding"              # פיגומים
    ELECTRICAL = "electrical"                # עבודת חשמל
    FALLING_OBJECTS = "falling_objects"      # חפצים נופלים
    FLOOR_WALL_OPENINGS = "floor_wall_openings"  # פתחים ברצפה/קיר
    LIFTING_TOWER = "lifting_tower"          # מגדל הרמה
    EXCAVATIONS = "excavations"              # חפירות
    FORMWORK = "formwork"                    # טפסות
    PROTECTIVE_EQUIPMENT = "protective_equipment"  # ציוד מגן אישי
    GENERAL = "general"                      # כללי
```

Hebrew labels live in frontend `i18n.js` (pattern `tCategory(...)`).

### Index additions (adding to Task 3's list)

```python
db.safety_documents.create_index([("project_id", 1), ("deleted_at", 1), ("created_at", -1)])
db.safety_documents.create_index([("project_id", 1), ("company_id", 1)])
db.safety_documents.create_index([("project_id", 1), ("category", 1)])
db.safety_documents.create_index([("project_id", 1), ("severity", 1), ("status", 1)])
db.safety_tasks.create_index([("project_id", 1), ("deleted_at", 1), ("status", 1), ("due_date", 1)])
db.safety_tasks.create_index([("project_id", 1), ("assigned_to", 1)])
db.safety_documents.create_index([("description", "text"), ("worker_name_cache", "text")])
```

### Endpoint signatures (replacing part of Task 6)

```
GET /api/safety/{project_id}/documents
  query: all SafetyFilters fields as repeatable query params
  returns: { items: [...], total: N, filters_echo: {...} }

GET /api/safety/{project_id}/tasks   (same shape)
GET /api/safety/{project_id}/workers (same shape + training_status filter)
```

### URL state sync

Use existing `useSearchParams` hook (already imported in `ProjectControlPage.js` line 6). Filter state ↔ URL round-trip required — a deep-link like `/projects/{id}/safety?category=height_work&severity=2,3&status=open` restores the exact filtered view on refresh.

### New component (NEW Task 14b)

```
frontend/src/components/safety/SafetyFilterSheet.jsx
```

- Opens as `BottomSheetModal` (existing pattern, `ProjectControlPage.js` line 86).
- 7 sections in UX-weight order: Company → Profession → Category → Status → Severity → Date range → Special flags.
- Multi-select uses existing pill pattern from tradeService.
- "Clear all" top-left; "Show N results" sticky bottom, updates live.
- Respects reduced-motion (transform + opacity only).

---

## A3 — Data Export integration (extend existing tab)

**Original (v1):** Task 15 creates new endpoints `/api/safety/export/{pdf,csv,json}` and Task 16 creates a separate export menu inside the safety tab.

**Problem discovered:** BrikOps already has a complete "ייצוא נתונים" tab (`ProjectDataExportTab.js`, 220 lines) that users are familiar with. The `export_router.py` full-Excel generator already has 6 well-structured worksheets. Adding a parallel export UI fragments the experience.

**Amendment (v2):** Extend the EXISTING tab. Keep a minimal shortcut button inside the safety tab that just jumps to the full export tab with safety pre-selected.

### Changes to `export_router.py`

Existing ws1–ws6 unchanged. Append after ws6 (companies), guarded by `ENABLE_SAFETY_MODULE`:

```python
# ws7 — עובדי בטיחות
ws7 = wb.create_sheet("עובדי בטיחות")
_apply_headers(ws7, [
    "שם", "ת.ז. (מסונן)", "חברה", "מקצוע", "טלפון (מסונן)",
    "תאריך תחילת עבודה", "הדרכות תקפות", "סטטוס כללי"
])
for worker in workers:
    ws7.append([
        worker["name"],
        f"****{worker['id_number_last4']}",
        worker["company_name_cache"],
        worker["trade"],
        f"***-{worker['phone_last4']}" if worker.get("phone") else "",
        worker["created_at"],
        worker["valid_trainings_count"],
        worker["overall_status"]
    ])
_set_widths(ws7, [22, 16, 28, 18, 14, 14, 14, 12])
ws7.sheet_view.rightToLeft = True
_set_autofilter(ws7)

# ws8 — הדרכות
ws8 = wb.create_sheet("הדרכות")
_apply_headers(ws8, [
    "עובד", "חברה", "סוג הדרכה", "תאריך הסמכה", "תקף עד",
    "מדריך", "משך (דק')", "מקום", "סטטוס", "קובץ סרוק?"
])
# ... populate from trainings ...

# ws9 — אירועי בטיחות (documentations + tasks unified)
ws9 = wb.create_sheet("אירועי בטיחות")
_apply_headers(ws9, [
    "סוג", "קטגוריה", "מיקום", "חומרה", "סטטוס",
    "תאריך דיווח", "תאריך יעד", "אחראי", "מדווח",
    "פעולה מתקנת", "מס' תמונות", "תיאור"
])
# ... populate from safety_documents + safety_tasks ...
```

Projects without the flag see unchanged 6-sheet output.

### Changes to `ProjectDataExportTab.js`

Append 2 new cards AFTER "Full Excel", BEFORE "Full ZIP". Do NOT modify the existing 3 cards. Both cards live in `frontend/src/components/safety/` and are lazy-imported.

```jsx
{featureFlags?.safety_module_enabled && (
  <>
    <SafetyPdfCard projectId={projectId} projectName={projectName} />
    <FilteredSafetyExportCard projectId={projectId} />
  </>
)}
```

Update existing "Full Excel" subtitle conditionally:

```jsx
{featureFlags?.safety_module_enabled
  ? "9 גיליונות: ליקויים, מסירות, בקרת ביצוע, מבנה, צוות, חברות, עובדי בטיחות, הדרכות, אירועי בטיחות."
  : "6 גיליונות: ליקויים, מסירות, בקרת ביצוע, מבנה, צוות, חברות."}
```

### NEW — פנקס כללי PDF generator

File: `backend/contractor_ops/safety_pdf.py`. Mirrors the 9 sections of the regulatory logbook (תקנות הבטיחות בעבודה, התשע"ט-2019):

1. רישומי זיהוי — project meta, developer, contractor, work manager, safety officer
2. בעלי תפקידים — role-holders + IDs + certifications
3. ציוד בבדיקה תקופתית — Phase 1 placeholder, Phase 2 fills
4. בדיקות תקופתיות מנ"ע — regulatory §§ 20, 50, 84, 122, 125 (Phase 1 placeholder)
5. רישומי מפקח עבודה — visitor log (placeholder)
6. רישומי בודק מוסמך — certified inspector (placeholder)
7. אירועים מיוחדים — from `safety_documents` where category is an incident type
8. נספחים — PDFs attached to safety documents
9. מסירת מידע והדרכה — from `trainings` grouped by worker, chronological

Use `reportlab` + Hebrew font (`noto-sans-hebrew`, already used for defects). RTL layout. Inline photo thumbnails. Generation runs async (polling, same pattern as existing ZIP) — a 93-page logbook takes 30–60s.

---

## A4 — Safety Score on home screen (NEW)

Cemento shows a score gauge; it's a simple, deterministic widget that frames the module's value. Recommend Phase 1 inclusion.

### Formula (server-computed, cached 5min)

```python
def compute_safety_score(project_id: str) -> dict:
    # 1. Training compliance (40%)
    workers_total = count_active_workers(project_id)
    workers_ok = count_workers_with_all_required_valid(project_id)
    training_pct = (workers_ok / workers_total * 100) if workers_total else 100

    # 2. Task timeliness last 90d (25%)
    tasks_90d = query_tasks(project_id, due_in_last_90d=True)
    on_time = sum(1 for t in tasks_90d
                  if t["status"] == "closed" and t["closed_at"] <= t["due_date"])
    on_time_pct = (on_time / len(tasks_90d) * 100) if tasks_90d else 100

    # 3. Periodic inspections (20%) — Phase 1 placeholder = 100
    inspection_pct = 100

    # 4. Absence of open sev-2/3 tasks (15%)
    open_sev23 = count_tasks(project_id, status="open", severity__gte=2)
    sev_pct = (
        100 if open_sev23 == 0
        else 80 if open_sev23 <= 2
        else 60 if open_sev23 <= 5
        else 40 if open_sev23 <= 10
        else 20
    )

    score = round(0.40*training_pct + 0.25*on_time_pct + 0.20*inspection_pct + 0.15*sev_pct)

    return {
        "score": score,
        "band": "excellent" if score >= 85 else "good" if score >= 70 else "warning" if score >= 55 else "poor",
        "breakdown": {
            "training_compliance": round(training_pct),
            "task_timeliness": round(on_time_pct),
            "periodic_inspections": round(inspection_pct),
            "absence_open_high_sev": round(sev_pct),
        }
    }
```

Endpoint: `GET /api/safety/{project_id}/score`. Cached 5min via existing `cachetools` pattern.

UI: circular SVG gauge, color band (emerald ≥85, amber 70–84, orange 55–69, rose <55). Click opens breakdown drawer + "הסבר הנוסחה" modal.

---

## A5 — Spec Readiness checklist (v2)

Before Replit starts, Zahi confirms:

- [ ] A1 — reuse `project_companies` instead of new `contractor_companies`
- [ ] A2 — server-side multi-dim filters (7 dimensions, 10 categories seeded)
- [ ] A3 — extend existing export tab + ws7/ws8/ws9 + פנקס כללי PDF as last sub-phase
- [ ] A4 — Safety Score on home screen
- [ ] Updated Phase-1 task count: 17 → 20 tasks (+ 14b Filter Sheet, 16b PDF generator, 16c Safety Score)
- [ ] ETA revision: 8 → 10 working days (Phase 1d +2 days for PDF + score)

After approval, generate clean single-file v2 spec and hand off to Replit.

---

**v2 amendments authored:** 2026-04-22 by Zahi + Claude. Driven by: (a) direct comparison to 4 Cemento PDFs (801/806 task reports, 172-page regulatory logbook, 93-page training form), (b) live code review of 4 existing BrikOps export/companies files, (c) ui-ux-pro-max skill's Priority 1–10 design rules. Visual mockup: `future-features/safety-phase-1-mockup-v2.html`.
