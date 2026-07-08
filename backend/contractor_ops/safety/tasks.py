"""Batch refactor-safety-split — section moved verbatim from safety_router.py (lines 854-1100). MOVE, never edit."""
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
    SafetySeverity,
    SafetyTask,
    SafetyTaskStatus,
    SoftDeleteBody,
    _audit,
    _check_project_access,
    _get_project_role,
    _new_id,
    _now,
    _resolve_include_deleted,
    _retention_date,
    datetime,
    get_current_user,
    get_db,
    require_roles,
    router,
    timezone,
)

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
        if ref.get("kind", "defect") == "observation":
            raise HTTPException(status_code=422, detail="לא ניתן לפתוח משימה מתקנת על תיעוד")

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
    severity: Optional[SafetySeverity] = None,
    company_id: Optional[str] = None,
    overdue: Optional[bool] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    include_deleted: bool = False,
    user: dict = Depends(get_current_user),
):
    """List safety tasks.

    NOTE: when both overdue=true and status=<x> are sent, overdue WINS — its
    status $in (open/in_progress) overwrites the explicit status filter. The FE
    disables the status select while "באיחור" is on. overdue reuses the exact
    same semantics as the score's overdue bucket.
    """
    db = get_db()
    await _check_project_access(user, project_id)

    q = {"project_id": project_id}
    include_deleted = _resolve_include_deleted(include_deleted, user)
    if not include_deleted:
        q["deletedAt"] = None
    if status_:      q["status"] = status_.value
    if assignee_id:  q["assignee_id"] = assignee_id
    if document_id:  q["document_id"] = document_id
    if severity:     q["severity"] = severity.value
    if company_id:   q["company_id"] = company_id
    if overdue:
        now_iso = datetime.now(timezone.utc).isoformat()
        q["due_at"] = {"$ne": None, "$lt": now_iso}
        q["status"] = {"$in": ["open", "in_progress"]}

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


