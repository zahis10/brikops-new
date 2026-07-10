"""
Safety module router — Phase 1 Part 1 (Foundation) + Part 2 (Backend Core).

Part 1: feature flag wiring, healthz, ensure_safety_indexes (20 indices).
Part 2: 25 CRUD endpoints (Workers/Trainings/Documents/Tasks/Incidents) +
        7-dim Documents filter + photo/PDF upload helper + audit on every write.

Registration in server.py is GATED by ENABLE_SAFETY_MODULE env flag.
When flag is off, this module is never imported and endpoints 404.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Literal
import hashlib
import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
import io
import time as _time

from services.object_storage import generate_url

from contractor_ops.router import (
    get_current_user, get_db, _now, _audit,
    _check_project_access, _get_project_role, _get_project_membership,
    _is_super_admin, require_roles,
)
from contractor_ops.schemas import (
    SafetyWorker, SafetyTraining, SafetyDocument, SafetyTask, SafetyIncident,
    SafetyCategory, SafetySeverity, SafetyDocumentStatus, SafetyDocumentKind,
    SafetyTaskStatus,
    SafetyTour, SafetyTourType, SafetyTourStatus, SafetyTourItem, SafetyTourSignature,
    SafetyEquipment, SafetyEquipmentCheck, EQUIPMENT_CATEGORIES,
)
from contractor_ops.upload_rate_limit import (
    check_upload_rate_limit, check_upload_bytes, check_content_length,
)
from contractor_ops.upload_quota import check_storage_quota, record_upload
from contractor_ops.upload_safety import (
    validate_upload, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES,
    SAFETY_STORED_REF_RE,
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
# Shared request bodies
# =====================================================================
class SoftDeleteBody(BaseModel):
    reason: Optional[str] = None


