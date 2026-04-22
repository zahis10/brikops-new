"""
Safety module router — Phase 1 Part 1 (Foundation) + Part 2 (Backend Core).

Part 1: feature flag wiring, healthz, ensure_safety_indexes (20 indices).
Part 2: 25 CRUD endpoints (Workers/Trainings/Documents/Tasks/Incidents) +
        7-dim Documents filter + photo/PDF upload helper + audit on every write.

Registration in server.py is GATED by ENABLE_SAFETY_MODULE env flag.
When flag is off, this module is never imported and endpoints 404.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import io
import time as _time

from contractor_ops.router import (
    get_current_user, get_db, _now, _audit,
    _check_project_access, _get_project_role, _get_project_membership,
    _is_super_admin, require_roles,
)
from contractor_ops.schemas import (
    SafetyWorker, SafetyTraining, SafetyDocument, SafetyTask, SafetyIncident,
    SafetyCategory, SafetySeverity, SafetyDocumentStatus, SafetyTaskStatus,
)
from contractor_ops.upload_safety import (
    validate_upload, ALLOWED_IMAGE_EXTENSIONS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/safety", tags=["safety"])


# =====================================================================
# Constants
# =====================================================================
SAFETY_WRITERS = ("project_manager", "management_team")
SAFETY_DELETERS = ("project_manager",)
INCIDENT_RETENTION_YEARS = 7

# Upload — accepts images AND PDFs (qc is image-only)
SAFETY_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
    "application/pdf",
}
SAFETY_ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | {".pdf"}
MAX_SAFETY_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

VALID_INCIDENT_TYPES = {"near_miss", "injury", "property_damage"}


# =====================================================================
# Helpers
# =====================================================================
def _new_id() -> str:
    """UUID4 as string. Matches project convention."""
    return str(uuid.uuid4())


def _hash_id_number(id_number: Optional[str]) -> Optional[str]:
    """SHA-256 of stripped Israeli ID / passport. Lookup aid; never returned to client."""
    if not id_number:
        return None
    return hashlib.sha256(id_number.strip().encode("utf-8")).hexdigest()


def _retention_date(from_iso: str) -> str:
    """from_iso + 7 years, ISO string. Used for incident soft-delete (regulatory clock)."""
    dt = datetime.fromisoformat(from_iso.replace("Z", "+00:00"))
    return (dt + timedelta(days=365 * INCIDENT_RETENTION_YEARS)).isoformat()


async def _ensure_company_or_placeholder(
    db, project_id: str, company_id: Optional[str], company_name: Optional[str], actor_id: str
) -> Optional[str]:
    """
    If company_id is provided and exists on this project (non-deleted) — return it.
    If only company_name is provided — create or reuse a placeholder project_companies doc.
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

    name = company_name.strip()
    existing = await db.project_companies.find_one({
        "project_id": project_id,
        "name": name,
        "deletedAt": None,
    })
    if existing:
        return existing["id"]

    new_id = _new_id()
    await db.project_companies.insert_one({
        "id": new_id,
        "project_id": project_id,
        "name": name,
        "is_placeholder": True,
        "created_at": _now(),
        "created_by": actor_id,
        "deletedAt": None,
        "deletedBy": None,
    })
    await _audit("project_company", new_id, "create_placeholder", actor_id, {
        "project_id": project_id, "name": name, "source": "safety",
    })
    return new_id


async def _strip_mongo_id(items: list) -> list:
    """Drop _id from list results (Mongo returns ObjectId which isn't JSON-serializable)."""
    for it in items:
        it.pop("_id", None)
    return items


def _resolve_include_deleted(include_deleted: bool, user: dict) -> bool:
    """
    Spec: include_deleted=true is restricted to super_admin.
    Non-super callers passing include_deleted=true get 403, not silent demotion.
    """
    if include_deleted and not _is_super_admin(user):
        raise HTTPException(status_code=403, detail="include_deleted requires super_admin")
    return include_deleted


# =====================================================================
# healthz (Part 1)
# =====================================================================
@router.get("/healthz")
async def healthz(user: dict = Depends(get_current_user)):
    """
    Liveness check for Safety module.
    Requires auth — never expose module existence to unauthenticated scanners.
    """
    return {"ok": True, "module": "safety", "enabled": True}


# =====================================================================
# Shared request bodies
# =====================================================================
class SoftDeleteBody(BaseModel):
    reason: Optional[str] = None


# =====================================================================
# Workers CRUD
# =====================================================================
class SafetyWorkerCreate(BaseModel):
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    full_name: str = Field(..., min_length=2, max_length=120)
    id_number: Optional[str] = None
    profession: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class SafetyWorkerUpdate(BaseModel):
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    profession: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    company_id: Optional[str] = None


@router.post("/{project_id}/workers", status_code=201, response_model=SafetyWorker)
async def create_worker(
    project_id: str,
    payload: SafetyWorkerCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    resolved_company_id = await _ensure_company_or_placeholder(
        db, project_id, payload.company_id, payload.company_name, user["id"]
    )

    # PII: persist only the SHA-256 hash; never store or return raw id_number.
    doc = {
        "id": _new_id(),
        "project_id": project_id,
        "company_id": resolved_company_id,
        "full_name": payload.full_name.strip(),
        "id_number": None,
        "id_number_hash": _hash_id_number(payload.id_number),
        "profession": payload.profession,
        "phone": payload.phone,
        "notes": payload.notes,
        "created_at": _now(),
        "created_by": user["id"],
        "deletedAt": None,
        "deletedBy": None,
        "deletion_reason": None,
        "retention_until": None,
    }
    await db.safety_workers.insert_one(doc)
    audit_after = {k: v for k, v in doc.items() if k not in ("id_number", "id_number_hash")}
    await _audit("safety_worker", doc["id"], "created", user["id"], {
        "project_id": project_id, "after": audit_after,
    })
    return SafetyWorker(**doc)


@router.get("/{project_id}/workers")
async def list_workers(
    project_id: str,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    include_deleted: bool = False,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    q = {"project_id": project_id}
    include_deleted = _resolve_include_deleted(include_deleted, user)
    if not include_deleted:
        q["deletedAt"] = None

    total = await db.safety_workers.count_documents(q)
    cursor = db.safety_workers.find(q, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    # strip the hash from list responses too
    for it in items:
        it.pop("id_number_hash", None)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{project_id}/workers/{worker_id}", response_model=SafetyWorker)
async def get_worker(
    project_id: str,
    worker_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)
    doc = await db.safety_workers.find_one({"id": worker_id, "project_id": project_id, "deletedAt": None})
    if not doc:
        raise HTTPException(status_code=404, detail="worker not found")
    # PII: never expose hash or any raw id_number
    doc.pop("id_number_hash", None)
    doc["id_number"] = None
    return SafetyWorker(**doc)


@router.patch("/{project_id}/workers/{worker_id}", response_model=SafetyWorker)
async def update_worker(
    project_id: str,
    worker_id: str,
    payload: SafetyWorkerUpdate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_workers.find_one({"id": worker_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="worker not found")
    if before.get("deletedAt"):
        raise HTTPException(status_code=410, detail="worker deleted")

    updates = payload.model_dump(exclude_unset=True)
    if "id_number" in updates:
        # PII: rotate hash only; never persist raw id_number on the document.
        updates["id_number_hash"] = _hash_id_number(updates["id_number"]) if updates["id_number"] else None
        updates["id_number"] = None
    if "company_id" in updates and updates["company_id"]:
        comp = await db.project_companies.find_one({
            "id": updates["company_id"], "project_id": project_id, "deletedAt": None,
        })
        if not comp:
            raise HTTPException(status_code=404, detail="company_id not found on this project")
    updates["updated_at"] = _now()
    updates["updated_by"] = user["id"]

    await db.safety_workers.update_one({"id": worker_id, "project_id": project_id, "deletedAt": None}, {"$set": updates})
    after = await db.safety_workers.find_one({"id": worker_id})
    _STRIP_PII = ("_id", "id_number", "id_number_hash")
    await _audit("safety_worker", worker_id, "updated", user["id"], {
        "project_id": project_id,
        "before": {k: v for k, v in before.items() if k not in _STRIP_PII},
        "after": {k: v for k, v in after.items() if k not in _STRIP_PII},
    })
    return SafetyWorker(**after)


@router.delete("/{project_id}/workers/{worker_id}", status_code=204)
async def delete_worker(
    project_id: str,
    worker_id: str,
    body: SoftDeleteBody = SoftDeleteBody(),
    user: dict = Depends(require_roles(*SAFETY_DELETERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_workers.find_one({"id": worker_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="worker not found")
    if before.get("deletedAt"):
        return

    now = _now()
    await db.safety_workers.update_one({"id": worker_id, "project_id": project_id, "deletedAt": None}, {"$set": {
        "deletedAt": now,
        "deletedBy": user["id"],
        "deletion_reason": body.reason,
        "retention_until": _retention_date(now),
    }})
    await _audit("safety_worker", worker_id, "deleted", user["id"], {
        "project_id": project_id, "deletion_reason": body.reason,
    })


# =====================================================================
# Trainings CRUD
# =====================================================================
class SafetyTrainingCreate(BaseModel):
    worker_id: str
    training_type: str
    trained_at: str
    instructor_name: Optional[str] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    expires_at: Optional[str] = None
    certificate_url: Optional[str] = None


class SafetyTrainingUpdate(BaseModel):
    training_type: Optional[str] = None
    trained_at: Optional[str] = None
    instructor_name: Optional[str] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    expires_at: Optional[str] = None
    certificate_url: Optional[str] = None


@router.post("/{project_id}/trainings", status_code=201, response_model=SafetyTraining)
async def create_training(
    project_id: str,
    payload: SafetyTrainingCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    worker = await db.safety_workers.find_one({
        "id": payload.worker_id,
        "project_id": project_id,
        "deletedAt": None,
    })
    if not worker:
        raise HTTPException(status_code=404, detail="worker not found or deleted")

    doc = {
        "id": _new_id(),
        "project_id": project_id,
        "worker_id": payload.worker_id,
        "training_type": payload.training_type.strip(),
        "instructor_name": payload.instructor_name,
        "duration_minutes": payload.duration_minutes,
        "location": payload.location,
        "trained_at": payload.trained_at,
        "expires_at": payload.expires_at,
        "certificate_url": payload.certificate_url,
        "created_at": _now(),
        "created_by": user["id"],
        "deletedAt": None,
        "deletedBy": None,
    }
    await db.safety_trainings.insert_one(doc)
    await _audit("safety_training", doc["id"], "created", user["id"], {
        "project_id": project_id, "after": {k: v for k, v in doc.items() if k != "_id"},
    })
    return SafetyTraining(**doc)


@router.get("/{project_id}/trainings")
async def list_trainings(
    project_id: str,
    worker_id: Optional[str] = None,
    training_type: Optional[str] = None,
    expires_before: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    include_deleted: bool = False,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    q = {"project_id": project_id}
    include_deleted = _resolve_include_deleted(include_deleted, user)
    if not include_deleted:
        q["deletedAt"] = None
    if worker_id:
        q["worker_id"] = worker_id
    if training_type:
        q["training_type"] = training_type
    if expires_before:
        q["expires_at"] = {"$ne": None, "$lt": expires_before}

    total = await db.safety_trainings.count_documents(q)
    cursor = db.safety_trainings.find(q, {"_id": 0}).sort("trained_at", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{project_id}/trainings/{training_id}", response_model=SafetyTraining)
async def get_training(
    project_id: str,
    training_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)
    doc = await db.safety_trainings.find_one({"id": training_id, "project_id": project_id, "deletedAt": None})
    if not doc:
        raise HTTPException(status_code=404, detail="training not found")
    return SafetyTraining(**doc)


@router.patch("/{project_id}/trainings/{training_id}", response_model=SafetyTraining)
async def update_training(
    project_id: str,
    training_id: str,
    payload: SafetyTrainingUpdate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_trainings.find_one({"id": training_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="training not found")
    if before.get("deletedAt"):
        raise HTTPException(status_code=410, detail="training deleted")

    updates = payload.model_dump(exclude_unset=True)
    updates["updated_at"] = _now()
    updates["updated_by"] = user["id"]

    await db.safety_trainings.update_one({"id": training_id, "project_id": project_id, "deletedAt": None}, {"$set": updates})
    after = await db.safety_trainings.find_one({"id": training_id})
    await _audit("safety_training", training_id, "updated", user["id"], {
        "project_id": project_id,
        "before": {k: v for k, v in before.items() if k != "_id"},
        "after": {k: v for k, v in after.items() if k != "_id"},
    })
    return SafetyTraining(**after)


@router.delete("/{project_id}/trainings/{training_id}", status_code=204)
async def delete_training(
    project_id: str,
    training_id: str,
    body: SoftDeleteBody = SoftDeleteBody(),
    user: dict = Depends(require_roles(*SAFETY_DELETERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_trainings.find_one({"id": training_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="training not found")
    if before.get("deletedAt"):
        return
    now = _now()
    await db.safety_trainings.update_one({"id": training_id, "project_id": project_id, "deletedAt": None}, {"$set": {
        "deletedAt": now,
        "deletedBy": user["id"],
        "deletion_reason": body.reason,
        "retention_until": _retention_date(now),
    }})
    await _audit("safety_training", training_id, "deleted", user["id"], {
        "project_id": project_id, "deletion_reason": body.reason,
    })


# =====================================================================
# Documents CRUD + 7-dim filter
# =====================================================================
class SafetyDocumentCreate(BaseModel):
    category: SafetyCategory
    severity: SafetySeverity
    title: str = Field(..., min_length=2, max_length=200)
    found_at: str
    description: Optional[str] = None
    location: Optional[str] = None
    company_id: Optional[str] = None
    profession: Optional[str] = None
    assignee_id: Optional[str] = None
    photo_urls: List[str] = Field(default_factory=list)
    attachment_urls: List[str] = Field(default_factory=list)


class SafetyDocumentUpdate(BaseModel):
    category: Optional[SafetyCategory] = None
    severity: Optional[SafetySeverity] = None
    status: Optional[SafetyDocumentStatus] = None
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    company_id: Optional[str] = None
    profession: Optional[str] = None
    assignee_id: Optional[str] = None
    photo_urls: Optional[List[str]] = None
    attachment_urls: Optional[List[str]] = None
    resolved_at: Optional[str] = None


@router.post("/{project_id}/documents", status_code=201, response_model=SafetyDocument)
async def create_document(
    project_id: str,
    payload: SafetyDocumentCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    if payload.company_id:
        comp = await db.project_companies.find_one({
            "id": payload.company_id, "project_id": project_id, "deletedAt": None,
        })
        if not comp:
            raise HTTPException(status_code=404, detail="company_id not found on this project")

    doc = {
        "id": _new_id(),
        "project_id": project_id,
        "category": payload.category.value,
        "severity": payload.severity.value,
        "status": SafetyDocumentStatus.open.value,
        "title": payload.title.strip(),
        "description": payload.description,
        "location": payload.location,
        "company_id": payload.company_id,
        "profession": payload.profession,
        "assignee_id": payload.assignee_id,
        "reporter_id": user["id"],          # SERVER-SET, never trust client
        "photo_urls": payload.photo_urls,
        "attachment_urls": payload.attachment_urls,
        "found_at": payload.found_at,
        "resolved_at": None,
        "created_at": _now(),
        "created_by": user["id"],
        "updated_at": None,
        "deletedAt": None,
        "deletedBy": None,
    }
    await db.safety_documents.insert_one(doc)
    await _audit("safety_document", doc["id"], "created", user["id"], {
        "project_id": project_id, "after": {k: v for k, v in doc.items() if k != "_id"},
    })
    return SafetyDocument(**doc)


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
):
    db = get_db()
    await _check_project_access(user, project_id)

    q = {"project_id": project_id}
    include_deleted = _resolve_include_deleted(include_deleted, user)
    if not include_deleted:
        q["deletedAt"] = None
    if category:    q["category"] = category.value
    if severity:    q["severity"] = severity.value
    if status_:     q["status"] = status_.value
    if company_id:  q["company_id"] = company_id
    if assignee_id: q["assignee_id"] = assignee_id
    if reporter_id: q["reporter_id"] = reporter_id
    if date_from or date_to:
        q["found_at"] = {}
        if date_from: q["found_at"]["$gte"] = date_from
        if date_to:   q["found_at"]["$lte"] = date_to

    total = await db.safety_documents.count_documents(q)
    cursor = db.safety_documents.find(q, {"_id": 0}).sort("found_at", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    filters_applied = {k: v for k, v in {
        "category": category.value if category else None,
        "severity": severity.value if severity else None,
        "status": status_.value if status_ else None,
        "company_id": company_id, "assignee_id": assignee_id, "reporter_id": reporter_id,
        "date_from": date_from, "date_to": date_to,
    }.items() if v}
    return {"items": items, "total": total, "limit": limit, "offset": offset,
            "filters_applied": filters_applied}


@router.get("/{project_id}/documents/{document_id}", response_model=SafetyDocument)
async def get_document(
    project_id: str,
    document_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)
    doc = await db.safety_documents.find_one({"id": document_id, "project_id": project_id, "deletedAt": None})
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return SafetyDocument(**doc)


@router.patch("/{project_id}/documents/{document_id}", response_model=SafetyDocument)
async def update_document(
    project_id: str,
    document_id: str,
    payload: SafetyDocumentUpdate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_documents.find_one({"id": document_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="document not found")
    if before.get("deletedAt"):
        raise HTTPException(status_code=410, detail="document deleted")

    updates = payload.model_dump(exclude_unset=True)

    # Coerce enum values to strings for Mongo
    if "category" in updates and updates["category"] is not None:
        updates["category"] = updates["category"].value if hasattr(updates["category"], "value") else updates["category"]
    if "severity" in updates and updates["severity"] is not None:
        updates["severity"] = updates["severity"].value if hasattr(updates["severity"], "value") else updates["severity"]
    if "status" in updates and updates["status"] is not None:
        updates["status"] = updates["status"].value if hasattr(updates["status"], "value") else updates["status"]

    if "company_id" in updates and updates["company_id"]:
        comp = await db.project_companies.find_one({
            "id": updates["company_id"], "project_id": project_id, "deletedAt": None,
        })
        if not comp:
            raise HTTPException(status_code=404, detail="company_id not found on this project")

    updates["updated_at"] = _now()
    updates["updated_by"] = user["id"]

    await db.safety_documents.update_one({"id": document_id, "project_id": project_id, "deletedAt": None}, {"$set": updates})
    after = await db.safety_documents.find_one({"id": document_id})
    await _audit("safety_document", document_id, "updated", user["id"], {
        "project_id": project_id,
        "before": {k: v for k, v in before.items() if k != "_id"},
        "after": {k: v for k, v in after.items() if k != "_id"},
    })
    return SafetyDocument(**after)


@router.delete("/{project_id}/documents/{document_id}", status_code=204)
async def delete_document(
    project_id: str,
    document_id: str,
    body: SoftDeleteBody = SoftDeleteBody(),
    user: dict = Depends(require_roles(*SAFETY_DELETERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_documents.find_one({"id": document_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="document not found")
    if before.get("deletedAt"):
        return
    now = _now()
    await db.safety_documents.update_one({"id": document_id, "project_id": project_id, "deletedAt": None}, {"$set": {
        "deletedAt": now,
        "deletedBy": user["id"],
        "deletion_reason": body.reason,
        "retention_until": _retention_date(now),
    }})
    await _audit("safety_document", document_id, "deleted", user["id"], {
        "project_id": project_id, "deletion_reason": body.reason,
    })


# =====================================================================
# Tasks CRUD + status transition guard
# =====================================================================
class SafetyTaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    severity: SafetySeverity
    document_id: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    company_id: Optional[str] = None
    due_at: Optional[str] = None


class SafetyTaskUpdate(BaseModel):
    title: Optional[str] = None
    severity: Optional[SafetySeverity] = None
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    company_id: Optional[str] = None
    due_at: Optional[str] = None
    status: Optional[SafetyTaskStatus] = None
    corrective_action: Optional[str] = None
    verification_photo_urls: Optional[List[str]] = None


def _assert_transition_allowed(
    current: str, next_status: str, project_role: str, payload_dict: dict
) -> None:
    """Enforce status transition rules. Raises 409 on invalid transition."""
    if current == next_status:
        return  # idempotent
    # Spec: open → in_progress → completed; any → cancelled; reverse = 409
    allowed = {
        "open": {"in_progress", "cancelled"},
        "in_progress": {"completed", "cancelled"},
        "completed": {"cancelled"},
        "cancelled": set(),
    }
    if next_status not in allowed.get(current, set()):
        raise HTTPException(status_code=409, detail={
            "current_status": current,
            "requested": next_status,
            "reason": "transition not allowed",
        })
    if next_status == "completed":
        ca = payload_dict.get("corrective_action")
        if not ca or not str(ca).strip():
            raise HTTPException(status_code=409, detail={
                "current_status": current,
                "requested": next_status,
                "reason": "corrective_action is required to mark a task completed",
            })
    if next_status == "cancelled":
        if project_role != "project_manager":
            raise HTTPException(status_code=409, detail={
                "current_status": current,
                "requested": next_status,
                "reason": "only project_manager may cancel a task",
            })


@router.post("/{project_id}/tasks", status_code=201, response_model=SafetyTask)
async def create_task(
    project_id: str,
    payload: SafetyTaskCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    if payload.document_id:
        ref = await db.safety_documents.find_one({
            "id": payload.document_id, "project_id": project_id, "deletedAt": None,
        })
        if not ref:
            raise HTTPException(status_code=404, detail="document_id not found or deleted")

    if payload.company_id:
        comp = await db.project_companies.find_one({
            "id": payload.company_id, "project_id": project_id, "deletedAt": None,
        })
        if not comp:
            raise HTTPException(status_code=404, detail="company_id not found on this project")

    doc = {
        "id": _new_id(),
        "project_id": project_id,
        "document_id": payload.document_id,
        "title": payload.title.strip(),
        "description": payload.description,
        "status": SafetyTaskStatus.open.value,
        "severity": payload.severity.value,
        "assignee_id": payload.assignee_id,
        "company_id": payload.company_id,
        "due_at": payload.due_at,
        "completed_at": None,
        "corrective_action": None,
        "verification_photo_urls": [],
        "created_at": _now(),
        "created_by": user["id"],
        "updated_at": None,
        "deletedAt": None,
        "deletedBy": None,
    }
    await db.safety_tasks.insert_one(doc)
    await _audit("safety_task", doc["id"], "created", user["id"], {
        "project_id": project_id, "after": {k: v for k, v in doc.items() if k != "_id"},
    })
    return SafetyTask(**doc)


@router.get("/{project_id}/tasks")
async def list_tasks(
    project_id: str,
    status_: Optional[SafetyTaskStatus] = Query(None, alias="status"),
    assignee_id: Optional[str] = None,
    document_id: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    include_deleted: bool = False,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    q = {"project_id": project_id}
    include_deleted = _resolve_include_deleted(include_deleted, user)
    if not include_deleted:
        q["deletedAt"] = None
    if status_:      q["status"] = status_.value
    if assignee_id:  q["assignee_id"] = assignee_id
    if document_id:  q["document_id"] = document_id

    total = await db.safety_tasks.count_documents(q)
    cursor = db.safety_tasks.find(q, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{project_id}/tasks/{task_id}", response_model=SafetyTask)
async def get_task(
    project_id: str,
    task_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)
    doc = await db.safety_tasks.find_one({"id": task_id, "project_id": project_id, "deletedAt": None})
    if not doc:
        raise HTTPException(status_code=404, detail="task not found")
    return SafetyTask(**doc)


@router.patch("/{project_id}/tasks/{task_id}", response_model=SafetyTask)
async def update_task(
    project_id: str,
    task_id: str,
    payload: SafetyTaskUpdate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_tasks.find_one({"id": task_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="task not found")
    if before.get("deletedAt"):
        raise HTTPException(status_code=410, detail="task deleted")

    updates = payload.model_dump(exclude_unset=True)

    # Coerce enums
    if "severity" in updates and updates["severity"] is not None:
        updates["severity"] = updates["severity"].value if hasattr(updates["severity"], "value") else updates["severity"]

    next_status_raw = updates.get("status")
    if next_status_raw is not None:
        next_status = next_status_raw.value if hasattr(next_status_raw, "value") else next_status_raw
        project_role = await _get_project_role(user, project_id)
        _assert_transition_allowed(before.get("status", "open"), next_status, project_role, updates)
        updates["status"] = next_status
        if next_status == "completed":
            updates["completed_at"] = _now()

    if "company_id" in updates and updates["company_id"]:
        comp = await db.project_companies.find_one({
            "id": updates["company_id"], "project_id": project_id, "deletedAt": None,
        })
        if not comp:
            raise HTTPException(status_code=404, detail="company_id not found on this project")

    updates["updated_at"] = _now()
    updates["updated_by"] = user["id"]

    await db.safety_tasks.update_one({"id": task_id, "project_id": project_id, "deletedAt": None}, {"$set": updates})
    after = await db.safety_tasks.find_one({"id": task_id})
    await _audit("safety_task", task_id, "updated", user["id"], {
        "project_id": project_id,
        "before": {k: v for k, v in before.items() if k != "_id"},
        "after": {k: v for k, v in after.items() if k != "_id"},
    })
    return SafetyTask(**after)


@router.delete("/{project_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    project_id: str,
    task_id: str,
    body: SoftDeleteBody = SoftDeleteBody(),
    user: dict = Depends(require_roles(*SAFETY_DELETERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_tasks.find_one({"id": task_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="task not found")
    if before.get("deletedAt"):
        return
    now = _now()
    await db.safety_tasks.update_one({"id": task_id, "project_id": project_id, "deletedAt": None}, {"$set": {
        "deletedAt": now,
        "deletedBy": user["id"],
        "deletion_reason": body.reason,
        "retention_until": _retention_date(now),
    }})
    await _audit("safety_task", task_id, "deleted", user["id"], {
        "project_id": project_id, "deletion_reason": body.reason,
    })


# =====================================================================
# Incidents CRUD + 7yr retention from occurred_at
# =====================================================================
class SafetyIncidentCreate(BaseModel):
    incident_type: str
    severity: SafetySeverity
    occurred_at: str
    description: str = Field(..., min_length=2)
    location: Optional[str] = None
    injured_worker_id: Optional[str] = None
    witnesses: List[str] = Field(default_factory=list)
    photo_urls: List[str] = Field(default_factory=list)
    medical_record_urls: List[str] = Field(default_factory=list)
    reported_to_authority: bool = False
    authority_report_ref: Optional[str] = None


class SafetyIncidentUpdate(BaseModel):
    incident_type: Optional[str] = None
    severity: Optional[SafetySeverity] = None
    occurred_at: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    injured_worker_id: Optional[str] = None
    witnesses: Optional[List[str]] = None
    photo_urls: Optional[List[str]] = None
    medical_record_urls: Optional[List[str]] = None
    reported_to_authority: Optional[bool] = None
    authority_report_ref: Optional[str] = None
    status: Optional[str] = None  # incident lifecycle: draft|reported|closed


@router.post("/{project_id}/incidents", status_code=201, response_model=SafetyIncident)
async def create_incident(
    project_id: str,
    payload: SafetyIncidentCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    if payload.incident_type not in VALID_INCIDENT_TYPES:
        raise HTTPException(status_code=400, detail=f"invalid incident_type; must be one of {sorted(VALID_INCIDENT_TYPES)}")

    if payload.injured_worker_id:
        worker = await db.safety_workers.find_one({
            "id": payload.injured_worker_id, "project_id": project_id, "deletedAt": None,
        })
        if not worker:
            raise HTTPException(status_code=404, detail="injured_worker_id not found or deleted")

    doc = {
        "id": _new_id(),
        "project_id": project_id,
        "incident_type": payload.incident_type,
        "severity": payload.severity.value,
        "occurred_at": payload.occurred_at,
        "description": payload.description,
        "location": payload.location,
        "injured_worker_id": payload.injured_worker_id,
        "witnesses": payload.witnesses,
        "photo_urls": payload.photo_urls,
        "medical_record_urls": payload.medical_record_urls,
        "reported_to_authority": payload.reported_to_authority,
        "authority_report_ref": payload.authority_report_ref,
        "status": "draft",
        "created_at": _now(),
        "created_by": user["id"],
        "updated_at": None,
        "deletedAt": None,
        "deletedBy": None,
        "deletion_reason": None,
        "retention_until": None,
    }
    await db.safety_incidents.insert_one(doc)
    await _audit("safety_incident", doc["id"], "created", user["id"], {
        "project_id": project_id, "after": {k: v for k, v in doc.items() if k != "_id"},
    })
    return SafetyIncident(**doc)


@router.get("/{project_id}/incidents")
async def list_incidents(
    project_id: str,
    incident_type: Optional[str] = None,
    severity: Optional[SafetySeverity] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    include_deleted: bool = False,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    q = {"project_id": project_id}
    include_deleted = _resolve_include_deleted(include_deleted, user)
    if not include_deleted:
        q["deletedAt"] = None
    if incident_type: q["incident_type"] = incident_type
    if severity:      q["severity"] = severity.value

    total = await db.safety_incidents.count_documents(q)
    cursor = db.safety_incidents.find(q, {"_id": 0}).sort("occurred_at", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{project_id}/incidents/{incident_id}", response_model=SafetyIncident)
async def get_incident(
    project_id: str,
    incident_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)
    doc = await db.safety_incidents.find_one({"id": incident_id, "project_id": project_id, "deletedAt": None})
    if not doc:
        raise HTTPException(status_code=404, detail="incident not found")
    return SafetyIncident(**doc)


@router.patch("/{project_id}/incidents/{incident_id}", response_model=SafetyIncident)
async def update_incident(
    project_id: str,
    incident_id: str,
    payload: SafetyIncidentUpdate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_incidents.find_one({"id": incident_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="incident not found")
    if before.get("deletedAt"):
        raise HTTPException(status_code=410, detail="incident deleted")

    # Once status != "draft", only project_manager OR safety_officer sub-role may edit
    if before.get("status", "draft") != "draft":
        membership = await _get_project_membership(user, project_id)
        is_pm = membership.get("role") == "project_manager"
        is_safety_officer = membership.get("sub_role") == "safety_officer"
        if not (is_pm or is_safety_officer or _is_super_admin(user)):
            raise HTTPException(
                status_code=403,
                detail="Only project_manager or safety_officer may edit a non-draft incident",
            )

    updates = payload.model_dump(exclude_unset=True)
    if "severity" in updates and updates["severity"] is not None:
        updates["severity"] = updates["severity"].value if hasattr(updates["severity"], "value") else updates["severity"]
    if "incident_type" in updates and updates["incident_type"] is not None:
        if updates["incident_type"] not in VALID_INCIDENT_TYPES:
            raise HTTPException(status_code=400, detail=f"invalid incident_type")
    if "injured_worker_id" in updates and updates["injured_worker_id"]:
        worker = await db.safety_workers.find_one({
            "id": updates["injured_worker_id"], "project_id": project_id, "deletedAt": None,
        })
        if not worker:
            raise HTTPException(status_code=404, detail="injured_worker_id not found or deleted")

    updates["updated_at"] = _now()
    updates["updated_by"] = user["id"]

    await db.safety_incidents.update_one({"id": incident_id, "project_id": project_id, "deletedAt": None}, {"$set": updates})
    after = await db.safety_incidents.find_one({"id": incident_id})
    await _audit("safety_incident", incident_id, "updated", user["id"], {
        "project_id": project_id,
        "before": {k: v for k, v in before.items() if k != "_id"},
        "after": {k: v for k, v in after.items() if k != "_id"},
    })
    return SafetyIncident(**after)


@router.delete("/{project_id}/incidents/{incident_id}", status_code=204)
async def delete_incident(
    project_id: str,
    incident_id: str,
    body: SoftDeleteBody,
    user: dict = Depends(require_roles(*SAFETY_DELETERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=400, detail="deletion_reason is required for incidents")

    before = await db.safety_incidents.find_one({"id": incident_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="incident not found")
    if before.get("deletedAt"):
        return

    # Retention from OCCURRED_AT, not now (regulatory clock)
    retention = _retention_date(before["occurred_at"])
    await db.safety_incidents.update_one({"id": incident_id, "project_id": project_id, "deletedAt": None}, {"$set": {
        "deletedAt": _now(),
        "deletedBy": user["id"],
        "deletion_reason": body.reason.strip(),
        "retention_until": retention,
    }})
    await _audit("safety_incident", incident_id, "deleted", user["id"], {
        "project_id": project_id, "deletion_reason": body.reason.strip(),
        "retention_until": retention,
    })


# =====================================================================
# Score & Exports — Phase 1 Part 3 (Backend Advanced)
# =====================================================================
_SCORE_CACHE: dict = {}  # {project_id: (timestamp, payload)}
_SCORE_TTL_SECONDS = 300  # 5 minutes


async def _compute_safety_score(db, project_id: str) -> dict:
    """
    Compute 0-100 safety score from live state. Higher = safer.

    Penalties (subtracted from 100):
      - open severity-3 documents: -10 each
      - open severity-2 documents: -5 each
      - open severity-1 documents: -2 each
      - tasks past due_at and not completed/cancelled: -5 each
      - incidents in last 90 days: -15 each
      - workers with no in-force training (no expires_at >= today): -3 each

    Floored at 0. Returns dict with `score` + `breakdown` + `computed_at`.
    """
    now = datetime.now(timezone.utc)
    today_iso = now.date().isoformat()
    cutoff_90d = (now - timedelta(days=90)).isoformat()

    open_doc_filter = {
        "project_id": project_id,
        "deletedAt": None,
        "status": {"$in": ["open", "in_progress"]},
    }
    open_sev3 = await db.safety_documents.count_documents({**open_doc_filter, "severity": "3"})
    open_sev2 = await db.safety_documents.count_documents({**open_doc_filter, "severity": "2"})
    open_sev1 = await db.safety_documents.count_documents({**open_doc_filter, "severity": "1"})

    overdue_tasks = await db.safety_tasks.count_documents({
        "project_id": project_id,
        "deletedAt": None,
        "status": {"$nin": ["completed", "cancelled"]},
        "due_at": {"$lt": now.isoformat(), "$ne": None},
    })

    recent_incidents = await db.safety_incidents.count_documents({
        "project_id": project_id,
        "deletedAt": None,
        "occurred_at": {"$gte": cutoff_90d},
    })

    worker_ids = await db.safety_workers.find(
        {"project_id": project_id, "deletedAt": None}, {"_id": 0, "id": 1}
    ).to_list(length=10000)
    worker_ids_list = [w["id"] for w in worker_ids]
    untrained_workers = 0
    if worker_ids_list:
        in_force = await db.safety_trainings.aggregate([
            {"$match": {
                "project_id": project_id,
                "deletedAt": None,
                "worker_id": {"$in": worker_ids_list},
                "$or": [{"expires_at": None}, {"expires_at": {"$gte": today_iso}}],
            }},
            {"$group": {"_id": "$worker_id"}},
        ]).to_list(length=10000)
        trained_set = {row["_id"] for row in in_force}
        untrained_workers = sum(1 for wid in worker_ids_list if wid not in trained_set)

    penalty = (
        open_sev3 * 10
        + open_sev2 * 5
        + open_sev1 * 2
        + overdue_tasks * 5
        + recent_incidents * 15
        + untrained_workers * 3
    )
    score = max(0, 100 - penalty)

    return {
        "project_id": project_id,
        "score": score,
        "breakdown": {
            "open_sev3": open_sev3,
            "open_sev2": open_sev2,
            "open_sev1": open_sev1,
            "overdue_tasks": overdue_tasks,
            "recent_incidents": recent_incidents,
            "untrained_workers": untrained_workers,
            "total_workers": len(worker_ids_list),
        },
        "computed_at": now.isoformat(),
    }


def _strip_pii(records: list) -> list:
    """Remove PII fields from worker records before any export."""
    cleaned = []
    for r in records:
        c = {k: v for k, v in r.items() if k not in ("_id", "id_number", "id_number_hash")}
        cleaned.append(c)
    return cleaned


@router.get("/{project_id}/score")
async def get_safety_score(
    project_id: str,
    refresh: bool = Query(False),
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    """Return safety score 0-100 with 5-min in-process cache. Management-only."""
    db = get_db()
    await _check_project_access(user, project_id)

    cached = _SCORE_CACHE.get(project_id)
    if cached and not refresh and (_time.time() - cached[0]) < _SCORE_TTL_SECONDS:
        await _audit("safety_score", project_id, "served_cached", user["id"], {
            "project_id": project_id,
            "score": cached[1]["score"],
        })
        return {**cached[1], "cached": True}

    payload = await _compute_safety_score(db, project_id)
    _SCORE_CACHE[project_id] = (_time.time(), payload)

    await _audit("safety_score", project_id, "computed", user["id"], {
        "project_id": project_id,
        "score": payload["score"],
        "refresh": refresh,
    })
    return {**payload, "cached": False}


async def _gather_export_data(db, project_id: str, doc_filter_extra: Optional[dict] = None):
    """Fetch all data needed for exports. Strips PII from workers."""
    workers = await db.safety_workers.find(
        {"project_id": project_id, "deletedAt": None}, {"_id": 0}
    ).to_list(length=100000)
    workers = _strip_pii(workers)

    trainings = await db.safety_trainings.find(
        {"project_id": project_id, "deletedAt": None}, {"_id": 0}
    ).to_list(length=100000)

    doc_q = {"project_id": project_id, "deletedAt": None}
    if doc_filter_extra:
        doc_q.update(doc_filter_extra)
    documents = await db.safety_documents.find(doc_q, {"_id": 0}).to_list(length=100000)

    tasks = await db.safety_tasks.find(
        {"project_id": project_id, "deletedAt": None}, {"_id": 0}
    ).to_list(length=100000)

    incidents = await db.safety_incidents.find(
        {"project_id": project_id, "deletedAt": None}, {"_id": 0}
    ).to_list(length=100000)

    company_ids = {r.get("company_id") for r in workers + documents + tasks if r.get("company_id")}
    company_map = {}
    if company_ids:
        companies = await db.project_companies.find(
            {"id": {"$in": list(company_ids)}, "deletedAt": None},
            {"_id": 0, "id": 1, "name": 1},
        ).to_list(length=10000)
        company_map = {c["id"]: c.get("name", "") for c in companies}

    user_ids = set()
    for src in (documents, tasks, incidents):
        for r in src:
            for f in ("assignee_id", "reporter_id", "created_by"):
                if r.get(f):
                    user_ids.add(r[f])
    user_map = {}
    if user_ids:
        users = await db.users.find(
            {"id": {"$in": list(user_ids)}}, {"_id": 0, "id": 1, "name": 1}
        ).to_list(length=10000)
        user_map = {u["id"]: u.get("name", "") for u in users}

    return workers, trainings, documents, tasks, incidents, company_map, user_map


def _build_safety_excel(
    project_name, workers, trainings, documents, tasks, incidents, company_map, user_map
):
    """Build 3-sheet Hebrew RTL Excel: Documents, Tasks, Workers+Trainings."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from services.safety_pdf import (
        CATEGORY_HE, SEVERITY_HE, DOC_STATUS_HE, TASK_STATUS_HE, INCIDENT_TYPE_HE,
    )

    wb = Workbook()

    header_font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="F59E0B", end_color="F59E0B", fill_type="solid")
    header_align = Alignment(horizontal="right", vertical="center", wrap_text=True)
    cell_font = Font(name="Arial", size=10)
    cell_align = Alignment(horizontal="right", vertical="top", wrap_text=True)
    thin = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )

    def _fmt_dt(s):
        if not s:
            return ""
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(s)[:16]

    def _add_sheet(title, headers, rows, widths):
        ws = wb.create_sheet(title)
        ws.sheet_view.rightToLeft = True
        for i, h in enumerate(headers, 1):
            c = ws.cell(row=1, column=i, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = header_align
            c.border = thin
        for r_idx, row in enumerate(rows, 2):
            for c_idx, val in enumerate(row, 1):
                c = ws.cell(row=r_idx, column=c_idx, value=val)
                c.font = cell_font
                c.alignment = cell_align
                c.border = thin
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        if rows:
            ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"

    # remove default
    wb.remove(wb.active)

    # Sheet 1: Documents
    doc_rows = []
    for d in documents:
        doc_rows.append([
            d.get("title", ""),
            CATEGORY_HE.get(d.get("category", ""), d.get("category", "")),
            SEVERITY_HE.get(d.get("severity", ""), ""),
            DOC_STATUS_HE.get(d.get("status", ""), d.get("status", "")),
            d.get("location", ""),
            company_map.get(d.get("company_id", ""), ""),
            user_map.get(d.get("assignee_id", ""), ""),
            user_map.get(d.get("reporter_id", ""), ""),
            _fmt_dt(d.get("found_at")),
            _fmt_dt(d.get("created_at")),
            _fmt_dt(d.get("resolved_at")),
            d.get("description", ""),
        ])
    _add_sheet(
        "ליקויים",
        ["כותרת", "קטגוריה", "חומרה", "סטטוס", "מיקום", "חברה",
         "אחראי", "מדווח", "נמצא בתאריך", "נוצר", "נפתר", "תיאור"],
        doc_rows,
        [25, 16, 10, 12, 18, 18, 16, 16, 18, 18, 18, 35],
    )

    # Sheet 2: Tasks
    task_rows = []
    for t in tasks:
        task_rows.append([
            t.get("title", ""),
            TASK_STATUS_HE.get(t.get("status", ""), t.get("status", "")),
            SEVERITY_HE.get(t.get("severity", ""), ""),
            user_map.get(t.get("assignee_id", ""), ""),
            company_map.get(t.get("company_id", ""), ""),
            _fmt_dt(t.get("due_at")),
            _fmt_dt(t.get("completed_at")),
            _fmt_dt(t.get("created_at")),
            t.get("corrective_action", ""),
        ])
    _add_sheet(
        "משימות",
        ["כותרת", "סטטוס", "חומרה", "אחראי", "חברה", "יעד",
         "הושלם", "נוצר", "פעולה מתקנת"],
        task_rows,
        [25, 12, 10, 16, 18, 18, 18, 18, 30],
    )

    # Sheet 3: Workers + Trainings (NO id_number / id_number_hash)
    worker_rows = []
    worker_name_map = {w["id"]: w.get("full_name", "") for w in workers}
    trainings_by_worker = {}
    for tr in trainings:
        trainings_by_worker.setdefault(tr.get("worker_id"), []).append(tr)

    for w in workers:
        wid = w["id"]
        w_trainings = trainings_by_worker.get(wid, [])
        types = ", ".join(sorted({tr.get("training_type", "") for tr in w_trainings if tr.get("training_type")}))
        latest_expiry = ""
        valid_expiries = [tr.get("expires_at") for tr in w_trainings if tr.get("expires_at")]
        if valid_expiries:
            latest_expiry = max(valid_expiries)[:10]
        worker_rows.append([
            w.get("full_name", ""),
            w.get("profession", ""),
            company_map.get(w.get("company_id", ""), ""),
            w.get("phone", ""),
            types,
            latest_expiry,
            _fmt_dt(w.get("created_at")),
        ])
    _add_sheet(
        "עובדים והדרכות",
        ["שם מלא", "מקצוע", "חברה", "טלפון", "סוגי הדרכות",
         "תוקף הדרכה אחרונה", "תאריך כניסה"],
        worker_rows,
        [22, 16, 20, 14, 30, 18, 18],
    )

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


@router.get("/{project_id}/export/excel")
async def export_safety_excel(
    project_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    """3-sheet Hebrew RTL Excel export. Management-only. PII stripped."""
    db = get_db()
    await _check_project_access(user, project_id)

    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    project_name = project.get("name", "project")

    workers, trainings, documents, tasks, incidents, company_map, user_map = \
        await _gather_export_data(db, project_id)

    buf = _build_safety_excel(
        project_name, workers, trainings, documents, tasks, incidents, company_map, user_map
    )

    await _audit("safety_export", project_id, "excel_exported", user["id"], {
        "project_id": project_id,
        "documents": len(documents),
        "tasks": len(tasks),
        "workers": len(workers),
    })

    filename = f"safety_{project_id[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{project_id}/export/filtered")
async def export_safety_filtered(
    project_id: str,
    category: Optional[SafetyCategory] = None,
    severity: Optional[SafetySeverity] = None,
    status_: Optional[SafetyDocumentStatus] = Query(None, alias="status"),
    company_id: Optional[str] = None,
    assignee_id: Optional[str] = None,
    reporter_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    """Excel export of documents matching the same 7-dim filter as list_documents."""
    db = get_db()
    await _check_project_access(user, project_id)

    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    project_name = project.get("name", "project")

    extra = {}
    if category:    extra["category"] = category.value
    if severity:    extra["severity"] = severity.value
    if status_:     extra["status"] = status_.value
    if company_id:  extra["company_id"] = company_id
    if assignee_id: extra["assignee_id"] = assignee_id
    if reporter_id: extra["reporter_id"] = reporter_id
    if date_from or date_to:
        rng = {}
        if date_from: rng["$gte"] = date_from
        if date_to:   rng["$lte"] = date_to
        extra["found_at"] = rng

    workers, trainings, documents, tasks, incidents, company_map, user_map = \
        await _gather_export_data(db, project_id, doc_filter_extra=extra)

    buf = _build_safety_excel(
        project_name, workers, trainings, documents, tasks, incidents, company_map, user_map
    )

    await _audit("safety_export", project_id, "filtered_exported", user["id"], {
        "project_id": project_id,
        "filters": extra,
        "matched_documents": len(documents),
    })

    filename = f"safety_filtered_{project_id[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{project_id}/export/pdf-register")
async def export_safety_pdf_register(
    project_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    """Generate the 9-section Hebrew 'פנקס כללי' PDF. Management-only."""
    db = get_db()
    await _check_project_access(user, project_id)

    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    workers, trainings, documents, tasks, incidents, company_map, user_map = \
        await _gather_export_data(db, project_id)

    score = await _compute_safety_score(db, project_id)

    from services.safety_pdf import generate_pnkas_pdf
    pdf_bytes = generate_pnkas_pdf(
        project=project,
        score=score,
        workers=workers,
        trainings=trainings,
        documents=documents,
        tasks=tasks,
        incidents=incidents,
        company_map=company_map,
        user_map=user_map,
    )

    await _audit("safety_export", project_id, "pdf_register_exported", user["id"], {
        "project_id": project_id,
        "score": score["score"],
        "documents": len(documents),
        "incidents": len(incidents),
    })

    filename = f"pnkas_{project_id[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =====================================================================
# Photo / PDF upload helper (one endpoint for all resources)
# =====================================================================
@router.post("/{project_id}/upload")
async def upload_safety_file(
    project_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    validate_upload(file, SAFETY_ALLOWED_EXTENSIONS, SAFETY_ALLOWED_CONTENT_TYPES)

    content = await file.read()
    if len(content) > MAX_SAFETY_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="הקובץ גדול מדי (מקסימום 10MB)")

    content_type = file.content_type or "application/octet-stream"
    if content_type == "application/pdf":
        ext = "pdf"
    else:
        ext = content_type.split("/")[-1]
        if ext == "jpeg":
            ext = "jpg"

    file_id = _new_id()
    key = f"safety/{project_id}/{file_id}.{ext}"

    from services.object_storage import save_bytes as obj_save_bytes, generate_url as obj_generate_url
    stored_ref = obj_save_bytes(content, key, content_type)
    url = obj_generate_url(stored_ref)

    await _audit("safety_upload", file_id, "upload", user["id"], {
        "project_id": project_id,
        "filename": file.filename,
        "key": key,
        "size": len(content),
        "content_type": content_type,
    })

    return {
        "id": file_id,
        "url": url,
        "stored_ref": stored_ref,
        "filename": file.filename,
        "content_type": content_type,
        "size": len(content),
    }


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
    # safety_workers — 3
    await db.safety_workers.create_index(
        [("project_id", 1), ("deletedAt", 1)],
        background=True, name="idx_sw_project_deleted",
    )
    await db.safety_workers.create_index(
        [("project_id", 1), ("company_id", 1)],
        background=True, name="idx_sw_project_company",
    )
    await db.safety_workers.create_index(
        [("project_id", 1), ("id_number", 1)],
        background=True, sparse=True, name="idx_sw_project_idnum",
    )
    # safety_trainings — 3
    await db.safety_trainings.create_index(
        [("project_id", 1), ("worker_id", 1)],
        background=True, name="idx_st_project_worker",
    )
    await db.safety_trainings.create_index(
        [("project_id", 1), ("expires_at", 1)],
        background=True, sparse=True, name="idx_st_project_expires",
    )
    await db.safety_trainings.create_index(
        [("project_id", 1), ("training_type", 1)],
        background=True, name="idx_st_project_type",
    )
    # safety_documents — 5
    await db.safety_documents.create_index(
        [("project_id", 1), ("deletedAt", 1), ("created_at", -1)],
        background=True, name="idx_sd_project_deleted_created",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("status", 1)],
        background=True, name="idx_sd_project_status",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("severity", 1)],
        background=True, name="idx_sd_project_severity",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("category", 1)],
        background=True, name="idx_sd_project_category",
    )
    await db.safety_documents.create_index(
        [("project_id", 1), ("company_id", 1)],
        background=True, sparse=True, name="idx_sd_project_company",
    )
    # safety_tasks — 4
    await db.safety_tasks.create_index(
        [("project_id", 1), ("deletedAt", 1), ("due_at", 1)],
        background=True, name="idx_stk_project_deleted_due",
    )
    await db.safety_tasks.create_index(
        [("project_id", 1), ("status", 1)],
        background=True, name="idx_stk_project_status",
    )
    await db.safety_tasks.create_index(
        [("project_id", 1), ("assignee_id", 1)],
        background=True, sparse=True, name="idx_stk_project_assignee",
    )
    await db.safety_tasks.create_index(
        [("document_id", 1)],
        background=True, sparse=True, name="idx_stk_document",
    )
    # safety_incidents — 3 (7yr retention-critical)
    await db.safety_incidents.create_index(
        [("project_id", 1), ("occurred_at", -1)],
        background=True, name="idx_si_project_occurred",
    )
    await db.safety_incidents.create_index(
        [("project_id", 1), ("severity", 1)],
        background=True, name="idx_si_project_severity",
    )
    await db.safety_incidents.create_index(
        [("retention_until", 1)],
        background=True, sparse=True, name="idx_si_retention",
    )
    # project_companies — 2 safety-related (shared collection)
    await db.project_companies.create_index(
        [("project_id", 1), ("safety_contact_id", 1)],
        background=True, sparse=True, name="idx_pc_project_safety_contact",
    )
    await db.project_companies.create_index(
        [("project_id", 1), ("is_placeholder", 1)],
        background=True, sparse=True, name="idx_pc_project_placeholder",
    )

    logger.info("Safety indices ensured (20 total across 6 collections)")
