"""Batch refactor-safety-split — section moved verbatim from safety_router.py (lines 347-612). MOVE, never edit."""
from contractor_ops.safety._shared import (  # noqa: F401
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_IMAGE_TYPES,
    BaseModel,
    Depends,
    File,
    Form,
    HTTPException,
    Optional,
    Query,
    SAFETY_DELETERS,
    SAFETY_WRITERS,
    SafetyTraining,
    SoftDeleteBody,
    UploadFile,
    _audit,
    _check_project_access,
    _new_id,
    _now,
    _resolve_include_deleted,
    _retention_date,
    check_storage_quota,
    check_upload_bytes,
    check_upload_rate_limit,
    generate_url,
    get_current_user,
    get_db,
    re,
    record_upload,
    require_roles,
    router,
    validate_upload,
)

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
        "worker_signature": None,
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
    if training_type and training_type.strip():
        q["training_type"] = {"$regex": re.escape(training_type.strip()), "$options": "i"}
    if expires_before:
        q["expires_at"] = {"$ne": None, "$lt": expires_before}

    total = await db.safety_trainings.count_documents(q)
    group_agg = await db.safety_trainings.aggregate([
        {"$match": q},
        {"$group": {"_id": {"w": "$worker_id", "t": "$training_type"}}},
        {"$count": "n"},
    ]).to_list(length=1)
    group_total = group_agg[0]["n"] if group_agg else 0
    cursor = db.safety_trainings.find(q, {"_id": 0}).sort("trained_at", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    for it in items:
        k = it.get("certificate_url")
        it["certificate_display_url"] = (generate_url(k) if k else None)
        sig = it.get("worker_signature")
        if sig and sig.get("signature_ref"):
            try:
                sig["signature_display_url"] = generate_url(sig["signature_ref"])
            except Exception:
                sig["signature_display_url"] = None
    return {"items": items, "total": total, "group_total": group_total, "limit": limit, "offset": offset}


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
    k = doc.get("certificate_url")
    doc["certificate_display_url"] = (generate_url(k) if k else None)
    sig = doc.get("worker_signature")
    if sig and sig.get("signature_ref"):
        try:
            sig["signature_display_url"] = generate_url(sig["signature_ref"])
        except Exception:
            sig["signature_display_url"] = None
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


@router.post("/{project_id}/trainings/{training_id}/signature", response_model=SafetyTraining)
async def sign_training(
    project_id: str,
    training_id: str,
    signer_name: str = Form(...),
    signature_type: str = Form(...),
    typed_name: str = Form(None),
    signature_image: UploadFile = File(None),
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    training = await db.safety_trainings.find_one(
        {"id": training_id, "project_id": project_id, "deletedAt": None})
    if not training:
        raise HTTPException(status_code=404, detail="training not found")
    if training.get("worker_signature"):
        raise HTTPException(status_code=409, detail="ההדרכה כבר חתומה")
    name = (signer_name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="יש להזין שם")

    signature_ref = None
    if signature_type == "canvas":
        if signature_image is None:
            raise HTTPException(status_code=422, detail="חסרה תמונת חתימה")
        # Upload-hardening mirror of sign_tour_slot — same helpers, same order.
        check_upload_rate_limit(user["id"])
        validate_upload(signature_image, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES)
        img_bytes = await signature_image.read()
        if len(img_bytes) == 0:
            raise HTTPException(status_code=400, detail="קובץ ריק")
        check_upload_bytes(user["id"], len(img_bytes))
        _proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "org_id": 1})
        _org_id = (_proj or {}).get("org_id")
        await check_storage_quota(_org_id, len(img_bytes))
        from services.object_storage import save_bytes as _save_bytes
        s3_key = f"safety/{project_id}/trainings/{training_id}/sig_worker_{_new_id()}.png"
        signature_ref = _save_bytes(img_bytes, s3_key, "image/png")
        await record_upload(_org_id, len(img_bytes))
    elif signature_type == "typed":
        if not (typed_name or "").strip():
            raise HTTPException(status_code=422, detail="יש להזין שם")
    else:
        raise HTTPException(status_code=422, detail="סוג חתימה לא מוכר")

    now = _now()
    sig = {
        "name": name,
        "signed_at": now,
        "signature_ref": signature_ref,
        "signature_type": signature_type,
        "typed_name": (typed_name.strip() if (signature_type == "typed" and typed_name) else None),
        "captured_by": user["id"],
    }
    # ATOMIC claim (4c pattern): re-assert empty signature → concurrent signer loses.
    # {"worker_signature": None} matches legacy rows missing the field too.
    upd = await db.safety_trainings.update_one(
        {"id": training_id, "project_id": project_id, "deletedAt": None,
         "worker_signature": None},
        {"$set": {"worker_signature": sig}},
    )
    if upd.modified_count == 0:
        raise HTTPException(status_code=409, detail="ההדרכה כבר חתומה")
    await _audit("safety_training", training_id, "signature_added", user["id"], {
        "project_id": project_id, "signature_type": signature_type,
    })
    after = await db.safety_trainings.find_one(
        {"id": training_id, "project_id": project_id}, {"_id": 0})
    s = after.get("worker_signature")
    if s and s.get("signature_ref"):
        try:
            s["signature_display_url"] = generate_url(s["signature_ref"])
        except Exception:
            s["signature_display_url"] = None
    return SafetyTraining(**after)


