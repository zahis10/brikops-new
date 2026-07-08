"""Batch refactor-safety-split — section moved verbatim from safety_router.py (lines 171-346). MOVE, never edit."""
from contractor_ops.safety._shared import (  # noqa: F401
    BaseModel,
    Depends,
    Field,
    HTTPException,
    Optional,
    Query,
    SAFETY_DELETERS,
    SAFETY_WRITERS,
    SafetyWorker,
    SoftDeleteBody,
    _audit,
    _check_project_access,
    _ensure_company_or_placeholder,
    _hash_id_number,
    _new_id,
    _now,
    _resolve_include_deleted,
    _retention_date,
    get_current_user,
    get_db,
    re,
    require_roles,
    router,
)

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
    profession: Optional[str] = None,
    company_id: Optional[str] = None,
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
    if profession and profession.strip():
        q["profession"] = {"$regex": re.escape(profession.strip()), "$options": "i"}
    if company_id:
        q["company_id"] = company_id

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


