"""Batch refactor-safety-split — section moved verbatim from safety_router.py (lines 1331-2006). MOVE, never edit."""
from contractor_ops.safety._shared import (  # noqa: F401
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_IMAGE_TYPES,
    BaseModel,
    Depends,
    Field,
    File,
    Form,
    HTTPException,
    List,
    Literal,
    Optional,
    Query,
    SAFETY_DELETERS,
    SAFETY_WRITERS,
    SafetyCategory,
    SafetyDocumentStatus,
    SafetySeverity,
    SafetyTour,
    SafetyTourStatus,
    SafetyTourType,
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
    model_validator,
    re,
    record_upload,
    require_roles,
    router,
    validate_upload,
)

# =====================================================================
# Tours CRUD (סיורי בטיחות) — Phase 2 step 4a
# A tour = a checklist walk of the site. Items are pass/fail/na; a FAILED
# item auto-opens a linked safety defect. Signatures are batch 4c (slots only).
# =====================================================================
DEFAULT_TOUR_CHECKLIST = [
    ("פיגומים — תקינות, משטחי עבודה ומאחזי יד", "scaffolding"),
    ("עבודה בגובה — רתמות, קווי חיים, אבטחת פתחים", "heights"),
    ("מעקות ופתחים ברצפות ובקירות", "heights"),
    ("חשמל — לוחות, כבלים מאריכים, הארקות ומפסקי פחת", "electrical_safety"),
    ("ציוד הרמה — עגורנים, אביזרי הרמה ותסקירים", "lifting"),
    ("חפירות ודיפון — יציבות, גישה וגידור", "excavation"),
    ("אש — מטפים, אחסון חומרים דליקים, עבודות ריתוך", "fire_safety"),
    ("ציוד מגן אישי — קסדות, נעלי בטיחות, אפודים זוהרים", "ppe"),
    ("סדר וניקיון — דרכי גישה ופינוי פסולת", "site_housekeeping"),
    ("חומרים מסוכנים — אחסון, שילוט וגיליונות בטיחות", "hazardous_materials"),
    ("שילוט ותמרור באתר", "other"),
    ("דרכי גישה ומילוט תקינות ופנויות", "other"),
    ("עזרה ראשונה — ערכות וזמינות מגיש עזרה ראשונה", "other"),
]


def _regen_tour_photo_urls(tour: dict) -> dict:
    """Regenerate per-GET presigned display URLs for every item's photos.
    Mirrors list_documents/list_incidents: permanent keys persisted, presigned
    URLs computed on read and never stored."""
    for it in (tour.get("items") or []):
        it["photo_display_urls"] = [
            (generate_url(k) if k else k) for k in (it.get("photo_urls") or [])
        ]
    # 4c: per-GET presigned display URL for each of the 3 signature slots that
    # holds a canvas PNG (fail-soft, exactly like item photos — a bad key must
    # never break the read).
    for _slot in ("work_manager_signature", "safety_assistant_signature", "safety_officer_signature"):
        sig = tour.get(_slot)
        if sig and sig.get("signature_ref"):
            try:
                sig["signature_display_url"] = generate_url(sig["signature_ref"])
            except Exception:
                sig["signature_display_url"] = None
    return tour


class SafetyTourCreate(BaseModel):
    tour_type: SafetyTourType
    custom_name: Optional[str] = Field(None, max_length=120)
    tour_date: str                       # "YYYY-MM-DD"

    @model_validator(mode="after")
    def _validate(self):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.tour_date or ""):
            raise ValueError("תאריך סיור לא תקין")
        if self.tour_type == SafetyTourType.custom and not (self.custom_name or "").strip():
            raise ValueError("יש להזין שם לסיור מותאם")
        return self


class SafetyTourMetaUpdate(BaseModel):    # draft-only meta edit
    tour_date: Optional[str] = None
    custom_name: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self):
        if self.tour_date is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.tour_date):
            raise ValueError("תאריך סיור לא תקין")
        return self


class SafetyTourItemUpdate(BaseModel):
    result: Literal["pass", "fail", "na"]
    note: Optional[str] = None
    photo_urls: Optional[List[str]] = None       # permanent keys from /upload
    severity: Optional[SafetySeverity] = None    # REQUIRED when result=fail
    defect_title: Optional[str] = Field(None, max_length=200)


class SafetyTourItemAdd(BaseModel):              # ad-hoc item during a walk
    label: str = Field(..., min_length=2, max_length=200)
    category: SafetyCategory = SafetyCategory.other


@router.post("/{project_id}/tours", status_code=201, response_model=SafetyTour)
async def create_tour(
    project_id: str,
    payload: SafetyTourCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    items = [
        {
            "id": _new_id(), "label": lbl, "category": cat, "result": None,
            "note": None, "photo_urls": [], "defect_id": None,
            "answered_at": None, "answered_by": None,
        }
        for (lbl, cat) in DEFAULT_TOUR_CHECKLIST
    ]
    custom_name = (
        payload.custom_name.strip()
        if payload.tour_type == SafetyTourType.custom and payload.custom_name
        else None
    )
    doc = {
        "id": _new_id(),
        "project_id": project_id,
        "tour_type": payload.tour_type.value,
        "custom_name": custom_name,
        "tour_date": payload.tour_date,
        "status": SafetyTourStatus.draft.value,
        "items": items,
        "work_manager_signature": None,
        "safety_assistant_signature": None,
        "safety_officer_signature": None,
        "submitted_at": None,
        "signed_at": None,
        "created_at": _now(),
        "created_by": user["id"],
        "updated_at": None,
        "deletedAt": None,
        "deletedBy": None,
        "deletion_reason": None,
        "retention_until": None,
    }
    await db.safety_tours.insert_one(doc)
    await _audit("safety_tour", doc["id"], "created", user["id"], {
        "project_id": project_id, "after": {k: v for k, v in doc.items() if k != "_id"},
    })
    return SafetyTour(**_regen_tour_photo_urls(doc))


@router.get("/{project_id}/tours")
async def list_tours(
    project_id: str,
    status_: Optional[SafetyTourStatus] = Query(None, alias="status"),
    tour_type: Optional[SafetyTourType] = None,
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
    if status_:    q["status"] = status_.value
    if tour_type:  q["tour_type"] = tour_type.value
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = (date_to + "T23:59:59") if len(date_to) == 10 else date_to
        q["tour_date"] = rng

    total = await db.safety_tours.count_documents(q)
    cursor = (
        db.safety_tours.find(q, {"_id": 0})
        .sort([("tour_date", -1), ("created_at", -1)])
        .skip(offset).limit(limit)
    )
    items = await cursor.to_list(length=limit)
    for t in items:
        _regen_tour_photo_urls(t)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{project_id}/tours/{tour_id}", response_model=SafetyTour)
async def get_tour(
    project_id: str,
    tour_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)
    doc = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id, "deletedAt": None})
    if not doc:
        raise HTTPException(status_code=404, detail="tour not found")
    return SafetyTour(**_regen_tour_photo_urls(doc))


@router.patch("/{project_id}/tours/{tour_id}", response_model=SafetyTour)
async def update_tour_meta(
    project_id: str,
    tour_id: str,
    payload: SafetyTourMetaUpdate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="tour not found")
    if before.get("status") != "draft":
        raise HTTPException(status_code=409, detail="לא ניתן לערוך סיור שהוגש")

    updates = payload.model_dump(exclude_unset=True)
    updates["updated_at"] = _now()
    await db.safety_tours.update_one(
        {"id": tour_id, "project_id": project_id, "deletedAt": None},
        {"$set": updates},
    )
    after = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id})
    await _audit("safety_tour", tour_id, "updated", user["id"], {
        "project_id": project_id, "changes": {k: v for k, v in updates.items() if k != "updated_at"},
    })
    return SafetyTour(**_regen_tour_photo_urls(after))


@router.patch("/{project_id}/tours/{tour_id}/items/{item_id}", response_model=SafetyTour)
async def update_tour_item(
    project_id: str,
    tour_id: str,
    item_id: str,
    payload: SafetyTourItemUpdate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    tour = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id, "deletedAt": None})
    if not tour:
        raise HTTPException(status_code=404, detail="tour not found")
    if tour.get("status") != "draft":
        raise HTTPException(status_code=409, detail="לא ניתן לערוך סיור שהוגש")

    item = next((it for it in (tour.get("items") or []) if it.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="item not found")

    if payload.result == "fail" and payload.severity is None:
        raise HTTPException(status_code=422, detail="יש לבחור חומרה לפריט שנכשל")

    # 1) Targeted arrayFilters update of the item fields (never a whole-items
    #    rewrite — two walkers editing different items must not clobber each other).
    item_set = {
        "items.$[elem].result": payload.result,
        "items.$[elem].answered_at": _now(),
        "items.$[elem].answered_by": user["id"],
        "updated_at": _now(),
    }
    if payload.note is not None:
        item_set["items.$[elem].note"] = payload.note
    if payload.photo_urls is not None:
        item_set["items.$[elem].photo_urls"] = payload.photo_urls
    upd = await db.safety_tours.update_one(
        {"id": tour_id, "project_id": project_id, "deletedAt": None, "status": "draft"},
        {"$set": item_set},
        array_filters=[{"elem.id": item_id}],
    )
    # The top-of-handler read saw draft, but a concurrent submit/delete could
    # have moved the tour out of draft between that read and this write. If the
    # guarded update matched nothing, refuse — never auto-defect on a tour that
    # is no longer editable.
    if upd.matched_count == 0:
        raise HTTPException(status_code=409, detail="לא ניתן לערוך סיור שהוגש")

    # 2) AUTO-DEFECT: a failed item opens exactly one linked safety defect.
    #    Order per spec: item fields first (above), THEN the atomic claim
    #    (pre-gen id + $elemMatch defect_id:None) guarded to the same draft
    #    lifecycle, then insert only if we won the claim (modified_count == 1)
    #    — no double defect on concurrent fails; fail→pass keeps the defect
    #    (human closes it later on the defects tab).
    if payload.result == "fail" and not item.get("defect_id"):
        defect_id = _new_id()
        claim = await db.safety_tours.update_one(
            {"id": tour_id, "project_id": project_id, "deletedAt": None, "status": "draft",
             "items": {"$elemMatch": {"id": item_id, "defect_id": None}}},
            {"$set": {"items.$.defect_id": defect_id}},
        )
        if claim.modified_count == 1:
            photo_keys = (
                payload.photo_urls if payload.photo_urls is not None
                else (item.get("photo_urls") or [])
            )
            title = (payload.defect_title or f"סיור בטיחות: {item['label']}")[:200]
            defect = {
                "id": defect_id,
                "project_id": project_id,
                "kind": "defect",
                "category": item["category"],
                "severity": payload.severity.value,
                "status": SafetyDocumentStatus.open.value,
                "title": title,
                "description": payload.note,
                "location": None,
                "company_id": None,
                "profession": None,
                "assignee_id": None,
                "reporter_id": user["id"],
                "photo_urls": list(photo_keys),
                "attachment_urls": [],
                "found_at": _now(),
                "resolved_at": None,
                "created_at": _now(),
                "created_by": user["id"],
                "updated_at": None,
                "deletedAt": None,
                "deletedBy": None,
                "tour_id": tour_id,
                "tour_item_id": item_id,
            }
            # Cross-collection compensation: we already claimed defect_id on the
            # item. If the defect insert fails, roll the claim back to None so a
            # retry can re-open the defect — otherwise the item would point at a
            # defect that does not exist ("ONE linked defect" must stay durable).
            try:
                await db.safety_documents.insert_one(defect)
            except Exception:
                await db.safety_tours.update_one(
                    {"id": tour_id, "project_id": project_id,
                     "items": {"$elemMatch": {"id": item_id, "defect_id": defect_id}}},
                    {"$set": {"items.$.defect_id": None}},
                )
                raise
            await _audit("safety_document", defect_id, "created", user["id"], {
                "project_id": project_id, "source": "safety_tour", "tour_id": tour_id,
                "after": {k: v for k, v in defect.items() if k != "_id"},
            })

    after = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id})
    after_item = next((it for it in (after.get("items") or []) if it.get("id") == item_id), {})
    await _audit("safety_tour", tour_id, "item_updated", user["id"], {
        "project_id": project_id, "item_id": item_id,
        "result": payload.result, "defect_id": after_item.get("defect_id"),
    })
    return SafetyTour(**_regen_tour_photo_urls(after))


@router.post("/{project_id}/tours/{tour_id}/items", response_model=SafetyTour)
async def add_tour_item(
    project_id: str,
    tour_id: str,
    payload: SafetyTourItemAdd,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    tour = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id, "deletedAt": None})
    if not tour:
        raise HTTPException(status_code=404, detail="tour not found")
    if tour.get("status") != "draft":
        raise HTTPException(status_code=409, detail="לא ניתן לערוך סיור שהוגש")

    new_item = {
        "id": _new_id(), "label": payload.label.strip(), "category": payload.category.value,
        "result": None, "note": None, "photo_urls": [], "defect_id": None,
        "answered_at": None, "answered_by": None,
    }
    upd = await db.safety_tours.update_one(
        {"id": tour_id, "project_id": project_id, "deletedAt": None, "status": "draft"},
        {"$push": {"items": new_item}, "$set": {"updated_at": _now()}},
    )
    # The top-of-handler read saw draft, but a concurrent submit could have moved
    # the tour out of draft before this $push landed — refuse rather than silently
    # no-op with a 200 + "item_added" audit (mirrors update_tour_item's guard).
    if upd.matched_count == 0:
        raise HTTPException(status_code=409, detail="לא ניתן לערוך סיור שהוגש")
    after = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id})
    await _audit("safety_tour", tour_id, "item_added", user["id"], {
        "project_id": project_id, "item_id": new_item["id"], "label": new_item["label"],
    })
    return SafetyTour(**_regen_tour_photo_urls(after))


@router.delete("/{project_id}/tours/{tour_id}/items/{item_id}", response_model=SafetyTour)
async def delete_tour_item(
    project_id: str,
    tour_id: str,
    item_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    tour = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id, "deletedAt": None})
    if not tour:
        raise HTTPException(status_code=404, detail="tour not found")
    if tour.get("status") != "draft":
        raise HTTPException(status_code=409, detail="לא ניתן לערוך סיור שהוגש")

    items = tour.get("items") or []
    item = next((it for it in items if it.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="item not found")
    # The finding is real — mark it, don't erase it (mirrors fail→pass keeping
    # the defect). An item with a defect can never be removed.
    if item.get("defect_id"):
        raise HTTPException(status_code=422, detail="לא ניתן להסיר פריט שנפתח עליו ליקוי")
    if len(items) == 1:
        raise HTTPException(status_code=422, detail="לא ניתן להסיר את הפריט האחרון")

    # The $pull's inner defect_id:None re-asserts the no-defect guard atomically:
    # a racing fail that just claimed a defect between the read above and this
    # write makes the pull a no-op (modified_count == 0) → 422, never a silent
    # erase of a real finding. status:"draft" refuses a concurrent submit.
    upd = await db.safety_tours.update_one(
        {"id": tour_id, "project_id": project_id, "deletedAt": None, "status": "draft"},
        {"$pull": {"items": {"id": item_id, "defect_id": None}},
         "$set": {"updated_at": _now()}},
    )
    if upd.matched_count == 0:
        raise HTTPException(status_code=409, detail="לא ניתן לערוך סיור שהוגש")
    if upd.modified_count == 0:
        raise HTTPException(status_code=422, detail="לא ניתן להסיר פריט שנפתח עליו ליקוי")

    after = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id})
    await _audit("safety_tour", tour_id, "item_removed", user["id"], {
        "project_id": project_id, "item_id": item_id, "label": item.get("label"),
    })
    return SafetyTour(**_regen_tour_photo_urls(after))


@router.post("/{project_id}/tours/{tour_id}/items/mark-remaining-pass", response_model=SafetyTour)
async def mark_remaining_pass(
    project_id: str,
    tour_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    tour = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id, "deletedAt": None})
    if not tour:
        raise HTTPException(status_code=404, detail="tour not found")
    if tour.get("status") != "draft":
        raise HTTPException(status_code=409, detail="לא ניתן לערוך סיור שהוגש")

    remaining = [it for it in (tour.get("items") or []) if it.get("result") is None]
    if not remaining:
        # No-op: nothing unanswered. Return the tour unchanged, no audit.
        return SafetyTour(**_regen_tour_photo_urls(tour))

    # Single targeted arrayFilters update — touches ONLY result==None items.
    # Existing fail/na/pass are untouched and NO defects are created (pass only).
    now = _now()
    upd = await db.safety_tours.update_one(
        {"id": tour_id, "project_id": project_id, "deletedAt": None, "status": "draft"},
        {"$set": {
            "items.$[elem].result": "pass",
            "items.$[elem].answered_at": now,
            "items.$[elem].answered_by": user["id"],
            "updated_at": now,
        }},
        array_filters=[{"elem.result": None}],
    )
    if upd.matched_count == 0:
        raise HTTPException(status_code=409, detail="לא ניתן לערוך סיור שהוגש")

    after = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id})
    await _audit("safety_tour", tour_id, "items_marked_pass", user["id"], {
        "project_id": project_id, "count": len(remaining),
    })
    return SafetyTour(**_regen_tour_photo_urls(after))


@router.post("/{project_id}/tours/{tour_id}/submit", response_model=SafetyTour)
async def submit_tour(
    project_id: str,
    tour_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    tour = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id, "deletedAt": None})
    if not tour:
        raise HTTPException(status_code=404, detail="tour not found")
    if tour.get("status") != "draft":
        raise HTTPException(status_code=409, detail="הסיור כבר הוגש")
    if any(it.get("result") is None for it in (tour.get("items") or [])):
        raise HTTPException(status_code=422, detail="יש לענות על כל הפריטים לפני הגשה")

    now = _now()
    await db.safety_tours.update_one(
        {"id": tour_id, "project_id": project_id, "deletedAt": None},
        {"$set": {"status": "pending_signature", "submitted_at": now, "updated_at": now}},
    )
    after = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id})
    await _audit("safety_tour", tour_id, "submitted", user["id"], {"project_id": project_id})
    return SafetyTour(**_regen_tour_photo_urls(after))


@router.post("/{project_id}/tours/{tour_id}/reopen", response_model=SafetyTour)
async def reopen_tour(
    project_id: str,
    tour_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    tour = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id, "deletedAt": None})
    if not tour:
        raise HTTPException(status_code=404, detail="tour not found")
    if tour.get("status") != "pending_signature":
        raise HTTPException(status_code=409, detail="לא ניתן לפתוח מחדש")

    # 4c: reopening (pending_signature → draft) clears any collected signatures.
    # The content may change after reopen, so an old signature would attest to a
    # different tour. A "signed" tour still cannot be reopened (the 409 above).
    sigs_cleared = sum(1 for s in (
        tour.get("work_manager_signature"),
        tour.get("safety_assistant_signature"),
        tour.get("safety_officer_signature"),
    ) if s)
    await db.safety_tours.update_one(
        {"id": tour_id, "project_id": project_id, "deletedAt": None},
        {"$set": {
            "status": "draft", "submitted_at": None, "signed_at": None,
            "work_manager_signature": None, "safety_assistant_signature": None,
            "safety_officer_signature": None, "updated_at": _now(),
        }},
    )
    after = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id})
    await _audit("safety_tour", tour_id, "reopened", user["id"], {
        "project_id": project_id, "signatures_cleared": sigs_cleared,
    })
    return SafetyTour(**_regen_tour_photo_urls(after))


# 4c signature slots → the tour statuses in which each may be signed. The two
# mandatory slots sign only while pending_signature; the optional safety_officer
# may also add a signature after the tour is already "signed".
_TOUR_SIGN_SLOTS = {
    "work_manager": ("pending_signature",),
    "safety_assistant": ("pending_signature",),
    "safety_officer": ("pending_signature", "signed"),
}


@router.post("/{project_id}/tours/{tour_id}/signatures/{slot}", response_model=SafetyTour)
async def sign_tour_slot(
    project_id: str,
    tour_id: str,
    slot: str,
    signer_name: str = Form(...),
    signature_type: str = Form(...),
    typed_name: str = Form(None),
    signer_user_id: str = Form(None),
    signature_image: UploadFile = File(None),
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    allowed_statuses = _TOUR_SIGN_SLOTS.get(slot)
    if allowed_statuses is None:
        raise HTTPException(status_code=422, detail="סוג חתימה לא מוכר")

    tour = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id, "deletedAt": None})
    if not tour:
        raise HTTPException(status_code=404, detail="tour not found")
    if tour.get("status") not in allowed_statuses:
        raise HTTPException(status_code=409, detail="לא ניתן לחתום בשלב זה")

    field = f"{slot}_signature"
    if tour.get(field):
        raise HTTPException(status_code=409, detail="החתימה כבר קיימת")

    name = (signer_name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="יש להזין שם")

    signature_ref = None
    if signature_type == "canvas":
        if signature_image is None:
            raise HTTPException(status_code=422, detail="חסרה תמונת חתימה")
        # Upload-hardening mirror of handover sign_role — same helpers, same order.
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
        s3_key = f"safety/{project_id}/tours/{tour_id}/sig_{slot}_{_new_id()}.png"
        signature_ref = _save_bytes(img_bytes, s3_key, "image/png")
        await record_upload(_org_id, len(img_bytes))
    elif signature_type == "typed":
        if not (typed_name or "").strip():
            raise HTTPException(status_code=422, detail="יש להזין שם")
    else:
        raise HTTPException(status_code=422, detail="סוג חתימה לא מוכר")

    # sub_role snapshot — FAIL-SOFT: a deleted/changed member must never fail the
    # signature. We do NOT verify the signer is a current member — the writer on
    # the shared device vouches for who is signing.
    sub_role = None
    if signer_user_id:
        try:
            mem = await db.project_memberships.find_one(
                {"project_id": project_id, "user_id": signer_user_id, "deletedAt": None},
                {"_id": 0, "sub_role": 1})
            sub_role = (mem or {}).get("sub_role")
        except Exception:
            sub_role = None

    now = _now()
    sig = {
        "user_id": signer_user_id or None,
        "name": name,
        "sub_role": sub_role,
        "signed_at": now,
        "signature_ref": signature_ref,
        "signature_type": signature_type,
        "typed_name": (typed_name.strip() if (signature_type == "typed" and typed_name) else None),
        "captured_by": user["id"],
    }

    # ATOMIC slot claim (defect-claim style of 4a): re-assert status + empty slot
    # so a concurrent signer of the same slot loses the race → 409.
    upd = await db.safety_tours.update_one(
        {"id": tour_id, "project_id": project_id, "deletedAt": None,
         "status": {"$in": list(allowed_statuses)}, field: None},
        {"$set": {field: sig, "updated_at": now}},
    )
    if upd.modified_count == 0:
        raise HTTPException(status_code=409, detail="החתימה כבר קיימת")

    after = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id})

    # AUTO-FLIP: once BOTH mandatory slots are filled while still pending → signed.
    if (after.get("work_manager_signature") and after.get("safety_assistant_signature")
            and after.get("status") == "pending_signature"):
        flip = await db.safety_tours.update_one(
            {"id": tour_id, "project_id": project_id, "deletedAt": None, "status": "pending_signature"},
            {"$set": {"status": "signed", "signed_at": _now(), "updated_at": _now()}},
        )
        if flip.modified_count == 1:
            await _audit("safety_tour", tour_id, "signed", user["id"], {"project_id": project_id})
            after = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id})

    await _audit("safety_tour", tour_id, "signature_added", user["id"], {
        "project_id": project_id, "slot": slot, "signer_name": name,
        "has_image": bool(signature_ref),
    })
    return SafetyTour(**_regen_tour_photo_urls(after))


@router.delete("/{project_id}/tours/{tour_id}", status_code=204)
async def delete_tour(
    project_id: str,
    tour_id: str,
    body: SoftDeleteBody,
    user: dict = Depends(require_roles(*SAFETY_DELETERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=400, detail="deletion_reason is required for tours")

    before = await db.safety_tours.find_one({"id": tour_id, "project_id": project_id, "deletedAt": None})
    if not before:
        raise HTTPException(status_code=404, detail="tour not found")
    if before.get("deletedAt"):
        return

    now = _now()
    retention = _retention_date(now)
    await db.safety_tours.update_one({"id": tour_id, "project_id": project_id, "deletedAt": None}, {"$set": {
        "deletedAt": now,
        "deletedBy": user["id"],
        "deletion_reason": body.reason.strip(),
        "retention_until": retention,
    }})
    await _audit("safety_tour", tour_id, "deleted", user["id"], {
        "project_id": project_id, "deletion_reason": body.reason.strip(),
        "retention_until": retention,
    })


