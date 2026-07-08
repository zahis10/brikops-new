"""Batch refactor-safety-split — section moved verbatim from safety_router.py (lines 2007-2482). MOVE, never edit."""
from contractor_ops.safety._shared import (  # noqa: F401
    BaseModel,
    Depends,
    EQUIPMENT_CATEGORIES,
    Field,
    HTTPException,
    Literal,
    Optional,
    Query,
    SAFETY_DELETERS,
    SAFETY_WRITERS,
    SafetyEquipment,
    SafetyEquipmentCheck,
    SoftDeleteBody,
    _audit,
    _check_project_access,
    _new_id,
    _now,
    _resolve_include_deleted,
    _retention_date,
    datetime,
    generate_url,
    get_current_user,
    get_db,
    model_validator,
    re,
    require_roles,
    router,
    timedelta,
)

# =====================================================================
# Equipment CRUD (כשירות ציוד) — Phase 3a
# Item collection + append-only check history (trainings pattern; 7yr on checks).
# =====================================================================
# ⚠️ DRAFT REGULATORY VALUES — pending verification against the actual תקנות.
# period_days are placeholder regulatory values; check_status/expiry math
# depends on them; verify before customer-facing use.
DEFAULT_EQUIPMENT_CHECKS: dict = {
    "lifting_accessories": [("תסקיר בודק מוסמך", 180)],
    "lifting_platform":    [("תסקיר בודק מוסמך", 180)],
    "electrical_panel":    [("בדיקת חשמלאי מוסמך", 365), ("בדיקת מפסק מגן / פחת", 7)],
    "air_compressor":      [("תסקיר בודק מוסמך", 365)],
    "formwork":            [("בדיקה לפני יציקה", None)],
    "forklift":            [("תסקיר בודק מוסמך", 365), ("טסט שנתי", 365)],
    "temporary_power":     [("בדיקת חשמלאי מוסמך", 180)],
    "crane_regular":       [("תסקיר בודק מוסמך", 180)],
    "tower_crane":         [("תסקיר בודק מוסמך", 425), ("בדיקת אנכיות ומסילה", 365)],
    "scaffolding":         [("בדיקת מנהל עבודה", 7)],
}


class SafetyEquipmentCreate(BaseModel):
    category: str = Field(..., min_length=2, max_length=60)
    internal_code: str = Field(..., min_length=1, max_length=60)
    description: Optional[str] = Field(None, max_length=300)
    serial_number: Optional[str] = Field(None, max_length=60)
    manufacturer: Optional[str] = Field(None, max_length=120)


class SafetyEquipmentUpdate(BaseModel):
    category: Optional[str] = Field(None, min_length=2, max_length=60)
    internal_code: Optional[str] = Field(None, min_length=1, max_length=60)
    description: Optional[str] = Field(None, max_length=300)
    serial_number: Optional[str] = Field(None, max_length=60)
    manufacturer: Optional[str] = Field(None, max_length=120)
    status: Optional[Literal["active", "decommissioned"]] = None


class SafetyEquipmentCheckCreate(BaseModel):
    check_name: str = Field(..., min_length=2, max_length=120)
    period_days: Optional[int] = Field(None, ge=1, le=3650)
    performed_at: str                              # "YYYY-MM-DD"
    expires_at: Optional[str] = None               # explicit override, same regex
    performed_by_name: Optional[str] = Field(None, max_length=120)
    license_number: Optional[str] = Field(None, max_length=60)
    result: Literal["pass", "fail", "conditional"] = "pass"
    notes: Optional[str] = Field(None, max_length=500)
    document_ref: Optional[str] = None             # permanent key from /upload

    @model_validator(mode="after")
    def _validate_dates(self):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.performed_at or ""):
            raise ValueError("תאריך ביצוע לא תקין (נדרש YYYY-MM-DD)")
        if self.expires_at is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.expires_at):
            raise ValueError("תאריך תפוגה לא תקין (נדרש YYYY-MM-DD)")
        return self


async def _equipment_latest_checks(db, project_id: str, equipment_ids: list) -> dict:
    """
    ONE aggregation over safety_equipment_checks → {equipment_id: {check_name: latest_doc}}.
    Latest = newest non-deleted check per (equipment_id, check_name) by performed_at.
    No N+1 per-item queries (red line).
    """
    if not equipment_ids:
        return {}
    pipeline = [
        {"$match": {
            "project_id": project_id,
            "equipment_id": {"$in": equipment_ids},
            "deletedAt": None,
        }},
        {"$sort": {"performed_at": -1, "created_at": -1}},
        {"$group": {
            "_id": {"equipment_id": "$equipment_id", "check_name": "$check_name"},
            "doc": {"$first": "$$ROOT"},
        }},
    ]
    out: dict = {}
    async for row in db.safety_equipment_checks.aggregate(pipeline):
        d = row["doc"]
        d.pop("_id", None)
        out.setdefault(d["equipment_id"], {})[d["check_name"]] = d
    return out


def _build_check_status(category: str, latest_by_name: dict, today: str) -> list:
    """
    Union of default tracks (mandatory) + tracks present in history → status entries.
    state: "missing" (never performed) | "valid" (no expiry or expires_at >= today) | "expired".
    """
    defaults = DEFAULT_EQUIPMENT_CHECKS.get(category, [])
    default_periods = {name: period for name, period in defaults}
    ordered_names = [name for name, _ in defaults] + [
        n for n in latest_by_name.keys() if n not in default_periods
    ]
    entries = []
    seen = set()
    for name in ordered_names:
        if name in seen:
            continue
        seen.add(name)
        latest = latest_by_name.get(name)
        if latest is not None and latest.get("period_days") is not None:
            period = latest.get("period_days")
        elif name in default_periods:
            period = default_periods[name]
        else:
            period = None
        expires_at = latest.get("expires_at") if latest else None
        performed_at = latest.get("performed_at") if latest else None
        doc_ref = latest.get("document_ref") if latest else None
        if latest is None:
            state = "missing"
        elif not expires_at or expires_at >= today:
            state = "valid"
        else:
            state = "expired"
        entries.append({
            "check_name": name,
            "period_days": period,
            "latest_performed_at": performed_at,
            "expires_at": expires_at,
            "document_display_url": (generate_url(doc_ref) if doc_ref else None),
            "state": state,
        })
    return entries


@router.post("/{project_id}/equipment", status_code=201, response_model=SafetyEquipment)
async def create_equipment(
    project_id: str,
    payload: SafetyEquipmentCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    code = payload.internal_code.strip()
    existing = await db.safety_equipment.find_one({
        "project_id": project_id,
        "deletedAt": None,
        "internal_code": {"$regex": f"^{re.escape(code)}$", "$options": "i"},
    })
    if existing:
        raise HTTPException(status_code=409, detail="קוד פריט כבר קיים בפרויקט")

    category = payload.category.strip()
    doc = {
        "id": _new_id(),
        "project_id": project_id,
        "category": category,
        "is_custom_category": category not in EQUIPMENT_CATEGORIES,
        "internal_code": code,
        "description": payload.description,
        "serial_number": payload.serial_number,
        "manufacturer": payload.manufacturer,
        "status": "active",
        "created_at": _now(),
        "created_by": user["id"],
        "updated_at": None,
        "deletedAt": None,
        "deletedBy": None,
        "deletion_reason": None,
        "retention_until": None,
    }
    await db.safety_equipment.insert_one(doc)
    await _audit("safety_equipment", doc["id"], "created", user["id"], {
        "project_id": project_id, "after": {k: v for k, v in doc.items() if k != "_id"},
    })
    return SafetyEquipment(**doc)


@router.get("/{project_id}/equipment")
async def list_equipment(
    project_id: str,
    category: Optional[str] = None,
    status_: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    include_deleted: bool = False,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    query = {"project_id": project_id}
    include_deleted = _resolve_include_deleted(include_deleted, user)
    if not include_deleted:
        query["deletedAt"] = None
    if category and category.strip():
        query["category"] = category.strip()
    if status_ and status_.strip():
        query["status"] = status_.strip()
    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"internal_code": rx}, {"description": rx}]

    total = await db.safety_equipment.count_documents(query)
    cursor = (
        db.safety_equipment.find(query, {"_id": 0})
        .sort([("category", 1), ("internal_code", 1)])
        .skip(offset).limit(limit)
    )
    items = await cursor.to_list(length=limit)
    ids = [it["id"] for it in items]
    latest_map = await _equipment_latest_checks(db, project_id, ids)
    today = _now()[:10]
    for it in items:
        it["check_status"] = _build_check_status(it["category"], latest_map.get(it["id"], {}), today)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{project_id}/equipment/summary")
async def equipment_summary(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    cursor = db.safety_equipment.find(
        {"project_id": project_id, "deletedAt": None, "status": "active"}, {"_id": 0}
    )
    items = await cursor.to_list(length=None)
    ids = [it["id"] for it in items]
    latest_map = await _equipment_latest_checks(db, project_id, ids)
    today = _now()[:10]

    buckets: dict = {}
    for it in items:
        cat = it["category"]
        b = buckets.setdefault(cat, {
            "category": cat,
            "is_custom": cat not in EQUIPMENT_CATEGORIES,
            "total": 0, "expired": 0, "ok": 0,
        })
        b["total"] += 1
        statuses = _build_check_status(cat, latest_map.get(it["id"], {}), today)
        # "expired" bucket deliberately INCLUDES missing tracks AND zero-track
        # items (never-checked = not fit; zero tracks possible only in custom
        # categories — Zahi 2026-07-07).
        if not statuses or any(s["state"] in ("expired", "missing") for s in statuses):
            b["expired"] += 1
        else:
            b["ok"] += 1

    result = sorted(buckets.values(), key=lambda x: x["category"])
    return {"items": result, "total": len(items)}


@router.get("/{project_id}/equipment/{equipment_id}")
async def get_equipment(
    project_id: str,
    equipment_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)
    doc = await db.safety_equipment.find_one(
        {"id": equipment_id, "project_id": project_id, "deletedAt": None}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="equipment not found")
    latest_map = await _equipment_latest_checks(db, project_id, [equipment_id])
    today = _now()[:10]
    doc["check_status"] = _build_check_status(doc["category"], latest_map.get(equipment_id, {}), today)
    return doc


@router.patch("/{project_id}/equipment/{equipment_id}", response_model=SafetyEquipment)
async def update_equipment(
    project_id: str,
    equipment_id: str,
    payload: SafetyEquipmentUpdate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_equipment.find_one(
        {"id": equipment_id, "project_id": project_id, "deletedAt": None}
    )
    if not before:
        raise HTTPException(status_code=404, detail="equipment not found")

    updates = payload.model_dump(exclude_unset=True)
    if updates.get("internal_code") is not None:
        code = updates["internal_code"].strip()
        dup = await db.safety_equipment.find_one({
            "project_id": project_id,
            "deletedAt": None,
            "id": {"$ne": equipment_id},
            "internal_code": {"$regex": f"^{re.escape(code)}$", "$options": "i"},
        })
        if dup:
            raise HTTPException(status_code=409, detail="קוד פריט כבר קיים בפרויקט")
        updates["internal_code"] = code
    if updates.get("category") is not None:
        cat = updates["category"].strip()
        updates["category"] = cat
        updates["is_custom_category"] = cat not in EQUIPMENT_CATEGORIES
    updates["updated_at"] = _now()

    await db.safety_equipment.update_one(
        {"id": equipment_id, "project_id": project_id, "deletedAt": None}, {"$set": updates}
    )
    after = await db.safety_equipment.find_one({"id": equipment_id}, {"_id": 0})
    await _audit("safety_equipment", equipment_id, "updated", user["id"], {
        "project_id": project_id,
        "before": {k: v for k, v in before.items() if k != "_id"},
        "after": after,
    })
    return SafetyEquipment(**after)


@router.delete("/{project_id}/equipment/{equipment_id}", status_code=204)
async def delete_equipment(
    project_id: str,
    equipment_id: str,
    body: SoftDeleteBody,
    user: dict = Depends(require_roles(*SAFETY_DELETERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=400, detail="deletion_reason is required")
    before = await db.safety_equipment.find_one(
        {"id": equipment_id, "project_id": project_id, "deletedAt": None}
    )
    if not before:
        raise HTTPException(status_code=404, detail="equipment not found")

    now = _now()
    retention = _retention_date(now)
    await db.safety_equipment.update_one(
        {"id": equipment_id, "project_id": project_id, "deletedAt": None}, {"$set": {
            "deletedAt": now,
            "deletedBy": user["id"],
            "deletion_reason": body.reason.strip(),
            "retention_until": retention,
        }}
    )
    # Check history is NOT deleted (regulatory 7yr retention).
    await _audit("safety_equipment", equipment_id, "deleted", user["id"], {
        "project_id": project_id, "deletion_reason": body.reason.strip(),
        "retention_until": retention,
    })


@router.post("/{project_id}/equipment/{equipment_id}/checks", status_code=201, response_model=SafetyEquipmentCheck)
async def create_equipment_check(
    project_id: str,
    equipment_id: str,
    payload: SafetyEquipmentCheckCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    equipment = await db.safety_equipment.find_one(
        {"id": equipment_id, "project_id": project_id, "deletedAt": None}
    )
    if not equipment:
        raise HTTPException(status_code=404, detail="equipment not found")
    if equipment.get("status") != "active":
        raise HTTPException(status_code=409, detail="לא ניתן לרשום בדיקה לפריט שהוצא משימוש")

    performed_at = payload.performed_at
    if payload.expires_at is not None:
        expires_at = payload.expires_at
    elif payload.period_days is not None:
        expires_at = (datetime.fromisoformat(performed_at) + timedelta(days=payload.period_days)).date().isoformat()
    else:
        expires_at = None
    if expires_at is not None and expires_at <= performed_at:
        raise HTTPException(status_code=422, detail="תאריך תפוגה חייב להיות אחרי תאריך הבדיקה")

    doc = {
        "id": _new_id(),
        "project_id": project_id,
        "equipment_id": equipment_id,
        "check_name": payload.check_name.strip(),
        "period_days": payload.period_days,
        "performed_at": performed_at,
        "expires_at": expires_at,
        "performed_by_name": payload.performed_by_name,
        "license_number": payload.license_number,
        "result": payload.result,
        "notes": payload.notes,
        "document_ref": payload.document_ref,
        "created_at": _now(),
        "created_by": user["id"],
        "deletedAt": None,
        "deletedBy": None,
        "deletion_reason": None,
        "retention_until": _retention_date(performed_at),   # 7yr from performed_at
    }
    await db.safety_equipment_checks.insert_one(doc)
    await _audit("safety_equipment_check", doc["id"], "check_recorded", user["id"], {
        "project_id": project_id, "equipment_id": equipment_id,
        "check_name": doc["check_name"], "result": doc["result"],
        "has_document": bool(doc.get("document_ref")),
    })
    resp = {k: v for k, v in doc.items() if k != "_id"}
    resp["document_display_url"] = generate_url(doc["document_ref"]) if doc.get("document_ref") else None
    return SafetyEquipmentCheck(**resp)


@router.get("/{project_id}/equipment/{equipment_id}/checks")
async def list_equipment_checks(
    project_id: str,
    equipment_id: str,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    include_deleted: bool = False,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)
    equipment = await db.safety_equipment.find_one(
        {"id": equipment_id, "project_id": project_id, "deletedAt": None}
    )
    if not equipment:
        raise HTTPException(status_code=404, detail="equipment not found")

    query = {"project_id": project_id, "equipment_id": equipment_id}
    include_deleted = _resolve_include_deleted(include_deleted, user)
    if not include_deleted:
        query["deletedAt"] = None

    total = await db.safety_equipment_checks.count_documents(query)
    cursor = (
        db.safety_equipment_checks.find(query, {"_id": 0})
        .sort([("performed_at", -1), ("created_at", -1)])
        .skip(offset).limit(limit)
    )
    items = await cursor.to_list(length=limit)
    for it in items:
        k = it.get("document_ref")
        it["document_display_url"] = generate_url(k) if k else None
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.delete("/{project_id}/equipment/{equipment_id}/checks/{check_id}", status_code=204)
async def delete_equipment_check(
    project_id: str,
    equipment_id: str,
    check_id: str,
    body: SoftDeleteBody,
    user: dict = Depends(require_roles(*SAFETY_DELETERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=400, detail="deletion_reason is required")
    before = await db.safety_equipment_checks.find_one(
        {"id": check_id, "project_id": project_id, "equipment_id": equipment_id, "deletedAt": None}
    )
    if not before:
        raise HTTPException(status_code=404, detail="check not found")
    now = _now()
    await db.safety_equipment_checks.update_one(
        {"id": check_id, "project_id": project_id,
         "equipment_id": equipment_id, "deletedAt": None}, {"$set": {
            "deletedAt": now,
            "deletedBy": user["id"],
            "deletion_reason": body.reason.strip(),
        }}
    )
    await _audit("safety_equipment_check", check_id, "check_deleted", user["id"], {
        "project_id": project_id, "equipment_id": equipment_id,
        "deletion_reason": body.reason.strip(),
    })


