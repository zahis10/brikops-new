"""Batch refactor-safety-split — section moved verbatim from safety_router.py (lines 1101-1330). MOVE, never edit."""
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
    SafetyIncident,
    SafetySeverity,
    SoftDeleteBody,
    VALID_INCIDENT_TYPES,
    _audit,
    _check_project_access,
    _get_project_membership,
    _is_super_admin,
    _new_id,
    _now,
    _resolve_include_deleted,
    _retention_date,
    generate_url,
    get_current_user,
    get_db,
    require_roles,
    router,
)

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
    reported_to_authority: Optional[bool] = None,
    injured_worker_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
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
    if reported_to_authority is not None:
        q["reported_to_authority"] = reported_to_authority
    if injured_worker_id:
        q["injured_worker_id"] = injured_worker_id
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            # pad a date-only "עד תאריך" to end-of-day so it is inclusive.
            # explicit parens: the concat belongs to the true-branch only.
            rng["$lte"] = (date_to + "T23:59:59") if len(date_to) == 10 else date_to
        q["occurred_at"] = rng

    total = await db.safety_incidents.count_documents(q)
    cursor = db.safety_incidents.find(q, {"_id": 0}).sort("occurred_at", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    for it in items:
        it["photo_display_urls"] = [
            (generate_url(k) if k else k) for k in (it.get("photo_urls") or [])
        ]
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
    doc["photo_display_urls"] = [
        (generate_url(k) if k else k) for k in (doc.get("photo_urls") or [])
    ]
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


