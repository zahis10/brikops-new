"""Batch refactor-safety-split — section moved verbatim from safety_router.py (lines 613-853). MOVE, never edit."""
from contractor_ops.safety._shared import (  # noqa: F401
    BaseModel,
    Depends,
    Field,
    HTTPException,
    List,
    Optional,
    Query,
    SAFETY_DELETERS,
    SAFETY_WRITERS,
    SafetyCategory,
    SafetyDocument,
    SafetyDocumentKind,
    SafetyDocumentStatus,
    SafetySeverity,
    SoftDeleteBody,
    _audit,
    _check_project_access,
    _new_id,
    _now,
    _resolve_include_deleted,
    _retention_date,
    generate_url,
    get_current_user,
    get_db,
    model_validator,
    require_roles,
    router,
)

# =====================================================================
# Documents CRUD + 7-dim filter
# =====================================================================
class SafetyDocumentCreate(BaseModel):
    kind: SafetyDocumentKind = SafetyDocumentKind.defect
    category: SafetyCategory
    severity: Optional[SafetySeverity] = None
    title: str = Field(..., min_length=2, max_length=200)
    found_at: str
    description: Optional[str] = None
    location: Optional[str] = None
    company_id: Optional[str] = None
    profession: Optional[str] = None
    assignee_id: Optional[str] = None
    photo_urls: List[str] = Field(default_factory=list)
    attachment_urls: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_kind_severity(self):
        if self.kind == SafetyDocumentKind.defect and self.severity is None:
            raise ValueError("יש לבחור חומרה לליקוי")
        if self.kind == SafetyDocumentKind.observation and self.severity is not None:
            raise ValueError("לתיעוד אין חומרה")
        return self


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
        "kind": payload.kind.value,
        "category": payload.category.value,
        "severity": payload.severity.value if payload.severity else None,
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
    kind: Optional[SafetyDocumentKind] = None,
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
    if kind == SafetyDocumentKind.observation:
        q["kind"] = "observation"
    elif kind == SafetyDocumentKind.defect:
        q["kind"] = {"$ne": "observation"}   # covers legacy pre-backfill docs
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
    for it in items:
        it["photo_display_urls"] = [
            (generate_url(k) if k else k) for k in (it.get("photo_urls") or [])
        ]
    filters_applied = {k: v for k, v in {
        "kind": kind.value if kind else None,
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
    doc["photo_display_urls"] = [
        (generate_url(k) if k else k) for k in (doc.get("photo_urls") or [])
    ]
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

    if before.get("kind", "defect") == "observation":
        blocked = {"status", "severity", "resolved_at"} & set(
            payload.model_dump(exclude_unset=True).keys()
        )
        if blocked:
            raise HTTPException(status_code=422, detail="שדות סטטוס/חומרה אינם רלוונטיים לתיעוד")

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


