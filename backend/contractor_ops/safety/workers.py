"""Batch refactor-safety-split — section moved verbatim from safety_router.py (lines 171-346). MOVE, never edit."""
from contractor_ops.safety._shared import (  # noqa: F401
    BaseModel,
    Depends,
    Field,
    HTTPException,
    Optional,
    Query,
    SAFETY_DELETERS,
    SAFETY_STORED_REF_RE,
    SAFETY_WRITERS,
    SafetyWorker,
    SoftDeleteBody,
    _audit,
    _check_project_access,
    _ensure_company_or_placeholder,
    _hash_id_number,
    _new_id,
    _now,
    generate_url,
    _resolve_include_deleted,
    _retention_date,
    get_current_user,
    get_db,
    logger,
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
    photo_ref: Optional[str] = None


class SafetyWorkerUpdate(BaseModel):
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    profession: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    company_id: Optional[str] = None
    photo_ref: Optional[str] = None


# Photo refs are user-supplied and rendered as <img src> to every project member
# (and feed the QR fitness screen), so the write-time shape gate is the SSRF
# guard. THE shared safety-ref pattern (upload_safety.SAFETY_STORED_REF_RE) —
# the SAME compiled object as work_diary_router._PHOTO_REF_RE and the PDF SSRF
# gate, so drift is impossible (batch d4a fold-in 2e; d3-fix2 lesson: BOTH
# storage backends — /api/uploads/ AND s3://).
_WORKER_PHOTO_REF_RE = SAFETY_STORED_REF_RE


def _validate_worker_photo_ref(project_id: str, ref):
    """422 unless ref is a safety/{THIS project}/ storage key. None passes (clear)."""
    if ref is None:
        return
    m = _WORKER_PHOTO_REF_RE.match(ref or "")
    if not m or m.group(1) != project_id or ".." in ref:
        raise HTTPException(status_code=422, detail="הפניית תמונה לא חוקית")


def _photo_display(ref):
    """Regenerate a per-GET display URL from the stored key; fail-soft → None."""
    if not ref:
        return None
    try:
        return generate_url(ref)
    except Exception:
        return None


@router.post("/{project_id}/workers", status_code=201, response_model=SafetyWorker)
async def create_worker(
    project_id: str,
    payload: SafetyWorkerCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    _validate_worker_photo_ref(project_id, payload.photo_ref)

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
        "photo_ref": payload.photo_ref,
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
    # qrg1: entry token auto-created on worker creation; WA auto-send is
    # entirely behind WA_ENTRY_QR_ENABLED (default off). Never fails creation.
    try:
        from contractor_ops.safety.gate import ensure_entry_token, maybe_send_entry_qr
        tok = await ensure_entry_token(db, project_id, doc["id"])
        await maybe_send_entry_qr(db, project_id, doc, tok)
    except Exception as e:
        logger.error(f"[GATE] entry-token bootstrap failed worker={doc['id']}: {e}")

    result = SafetyWorker(**doc)
    result.photo_display_url = _photo_display(doc.get("photo_ref"))
    return result


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
    # strip the hash from list responses too; regen the photo display URL per-GET
    for it in items:
        it.pop("id_number_hash", None)
        it["photo_display_url"] = _photo_display(it.get("photo_ref"))

    # ind2-fix4 E1 (additive): per-worker induction status — max expires_at
    # over SIGNED induction trainings, ONE aggregation for the page (no N+1).
    from contractor_ops.safety.induction import INDUCTION_TRAINING_TYPE
    worker_ids = [it["id"] for it in items if it.get("id")]
    valid_map = {}
    if worker_ids:
        agg = await db.safety_trainings.aggregate([
            {"$match": {
                "project_id": project_id,
                "deletedAt": None,
                "training_type": INDUCTION_TRAINING_TYPE,
                "worker_id": {"$in": worker_ids},
                "worker_signature": {"$ne": None},
            }},
            {"$group": {"_id": "$worker_id", "max_expires": {"$max": "$expires_at"}}},
        ]).to_list(length=len(worker_ids))
        valid_map = {row["_id"]: row.get("max_expires") for row in agg}
    for it in items:
        it["induction_valid_until"] = valid_map.get(it.get("id"))

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
    doc["photo_display_url"] = _photo_display(doc.get("photo_ref"))
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
    if "photo_ref" in updates:
        # null clears the photo; a non-null ref must pass the shape gate
        _validate_worker_photo_ref(project_id, updates["photo_ref"])
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
    result = SafetyWorker(**after)
    result.photo_display_url = _photo_display(after.get("photo_ref"))
    return result


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

    # qrg1: removing a worker revokes all its entry tokens → gate page invalid.
    try:
        from contractor_ops.safety.gate import revoke_entry_tokens
        await revoke_entry_tokens(db, project_id, worker_id)
    except Exception as e:
        logger.error(f"[GATE] token revoke failed worker={worker_id}: {e}")


