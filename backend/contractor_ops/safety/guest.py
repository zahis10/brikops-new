"""Batch qrg-guest — one-day GUEST entry passes (authed admin side).

A PM/MT issues a dated guest pass (name + company); the guest opens the same
public /gate/:token link, reads the visitor safety briefing (G1 constant
below) and signs it inline — the signature turns the QR green for the chosen
day only. The PUBLIC endpoints (GET branch + guest-sign) live in
gate_public.py; this module holds the locked briefing + the SAFETY_WRITERS
CRUD, reusing the worker QR helpers from gate.py.
"""
import hashlib
import io
import re

from contractor_ops.safety._shared import (  # noqa: F401
    BaseModel,
    Depends,
    HTTPException,
    Optional,
    Query,
    SAFETY_WRITERS,
    _audit,
    _check_project_access,
    _new_id,
    _now,
    generate_url,
    get_current_user,
    get_db,
    logger,
    require_roles,
    router,
)
from contractor_ops.safety.gate import (
    _gate_url,
    _new_token,
    _qr_png_bytes,
)
from contractor_ops.utils.timezone import israel_today
from fastapi.responses import StreamingResponse

# =====================================================================
# G1 — visitor safety briefing (v1 Hebrew constant — the DEFAULT).
# qrg-briefing-edit: an org-level override (guest_briefing_texts) plugs
# in through get_guest_briefing(db, org_id) — the ONLY access point.
# NO call site may read the constant directly — helper only.
# =====================================================================
GUEST_BRIEFING_VERSION = 1
GUEST_BRIEFING_TEXT_HE = (
    "תדריך בטיחות למבקרים — אתר בנייה\n"
    "1. חובה לחבוש קסדת מגן ולנעול נעלי בטיחות בכל שטח האתר.\n"
    "2. המבקר/ת ילווה/תלווה על ידי נציג מטעם האתר ולא יסתובב/תסתובב באזורי\n"
    "   העבודה ללא ליווי.\n"
    "3. חל איסור להיכנס לאזורים מגודרים, לשטחי הרמה או לתחום פעולת מנופים.\n"
    "4. יש לציית לשילוט הבטיחות ולהנחיות מנהל העבודה בכל עת.\n"
    "5. בכל מקרה חירום יש להתפנות לנקודת הכינוס ולפעול לפי הוראות הצוות.\n"
    "בחתימתי אני מאשר/ת שקראתי והבנתי את הוראות הבטיחות באתר ואפעל לפיהן."
)


def _briefing_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


async def get_guest_briefing(db, org_id: str | None) -> tuple[str, int, str]:
    """(text, version, hash[:12]) — the ONLY way to access the briefing.

    qrg-briefing-edit E1: looks up the org override in guest_briefing_texts;
    found → (doc.text, doc.version, sha256[:12]); none (or no org_id) → the
    v1 constant tuple. Evidence integrity is unchanged — every signature
    keeps recording the version+hash of the text that was signed.
    """
    if org_id:
        doc = await db.guest_briefing_texts.find_one(
            {"org_id": org_id}, {"_id": 0, "text": 1, "version": 1}
        )
        if doc and doc.get("text"):
            return doc["text"], int(doc.get("version") or 2), _briefing_hash(doc["text"])
    return GUEST_BRIEFING_TEXT_HE, GUEST_BRIEFING_VERSION, _briefing_hash(GUEST_BRIEFING_TEXT_HE)


# =====================================================================
# Helpers
# =====================================================================
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _store_guest_qr_png(project_id: str, pass_doc: dict) -> str:
    """Same key-at-rest pattern as the worker QR, guest-passes prefix."""
    from services.object_storage import save_bytes
    png = _qr_png_bytes(_gate_url(pass_doc["token"]))
    key = f"safety/{project_id}/guest-passes/{pass_doc['id']}/qr.png"
    return save_bytes(png, key, "image/png")


def _pass_list_item(p: dict) -> dict:
    briefing = p.get("briefing") or {}
    return {
        "id": p["id"],
        "guest_name": p.get("guest_name"),
        "guest_company": p.get("guest_company"),
        "valid_on": p.get("valid_on"),
        "status": p.get("status"),
        "signed": bool(briefing.get("signed")),
        "signed_at": briefing.get("signed_at"),
        "qr_display_url": generate_url(p["qr_ref"]) if p.get("qr_ref") else None,
        # qrg-share-fix S4a: the shareable link for re-share from the list.
        # Authed-only response (SAFETY_WRITERS) — same audience that can
        # already fetch qr.png. The RAW token field is deliberately NOT added.
        "gate_url": _gate_url(p["token"]) if p.get("token") else None,
        "created_at": p.get("created_at"),
    }


# =====================================================================
# G3 — authed endpoints (SAFETY_WRITERS only)
# =====================================================================
class GuestPassCreate(BaseModel):
    guest_name: str
    guest_company: str
    valid_on: Optional[str] = None


@router.post("/{project_id}/guest-passes", status_code=201)
async def create_guest_pass(
    project_id: str,
    body: GuestPassCreate,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    name = (body.guest_name or "").strip()
    company = (body.guest_company or "").strip()
    if not (2 <= len(name) <= 120):
        raise HTTPException(status_code=422, detail="יש להזין שם אורח (2–120 תווים)")
    if not (1 <= len(company) <= 120):
        raise HTTPException(status_code=422, detail="יש להזין חברה/תפקיד (עד 120 תווים)")
    valid_on = (body.valid_on or "").strip() or israel_today()
    if not _DATE_RE.match(valid_on):
        raise HTTPException(status_code=422, detail="תאריך לא תקין — פורמט נדרש YYYY-MM-DD")
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "org_id": 1})
    doc = {
        "id": _new_id(),
        "token": _new_token(),
        "org_id": (proj or {}).get("org_id"),
        "project_id": project_id,
        "guest_name": name,
        "guest_company": company,
        "valid_on": valid_on,
        "status": "active",
        "created_by": user["id"],
        "created_at": _now(),
        "revoked_at": None,
        "qr_ref": None,
        "briefing": {
            "signed": False,
            "signed_at": None,
            "signer_name": None,
            "signature_ref": None,
            "briefing_version": None,
            "briefing_hash": None,
        },
    }
    try:
        doc["qr_ref"] = _store_guest_qr_png(project_id, doc)
    except Exception as e:  # QR storage is best-effort; the pass must exist
        logger.error(f"[GATE] guest QR store failed for pass {doc['id']}: {e}")
    await db.guest_entry_passes.insert_one(doc)
    doc.pop("_id", None)
    await _audit("guest_entry_pass", doc["id"], "guest_pass_created", user["id"], {
        "project_id": project_id, "guest_name": name, "valid_on": valid_on,
    })
    return {
        "id": doc["id"],
        "token": doc["token"],
        "gate_url": _gate_url(doc["token"]),
        "qr_display_url": generate_url(doc["qr_ref"]) if doc.get("qr_ref") else None,
        "guest_name": name,
        "guest_company": company,
        "valid_on": valid_on,
        "status": "active",
        "created_at": doc["created_at"],
    }


@router.get("/{project_id}/guest-passes")
async def list_guest_passes(
    project_id: str,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    """Issued passes for the project, newest-first (re-share / audit)."""
    db = get_db()
    await _check_project_access(user, project_id)
    q = {"project_id": project_id}
    total = await db.guest_entry_passes.count_documents(q)
    rows = await db.guest_entry_passes.find(q, {"_id": 0}) \
        .sort("created_at", -1).skip(offset).limit(limit).to_list(length=limit)
    return {
        "items": [_pass_list_item(p) for p in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/{project_id}/guest-passes/{pass_id}/revoke")
async def revoke_guest_pass(
    project_id: str,
    pass_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    p = await db.guest_entry_passes.find_one(
        {"id": pass_id, "project_id": project_id}, {"_id": 0, "id": 1, "status": 1}
    )
    if not p:
        raise HTTPException(status_code=404, detail="קוד אורח לא נמצא")
    await db.guest_entry_passes.update_one(
        {"id": pass_id, "project_id": project_id},
        {"$set": {"status": "revoked", "revoked_at": _now()}},
    )
    await _audit("guest_entry_pass", pass_id, "guest_pass_revoked", user["id"], {
        "project_id": project_id,
    })
    return {"id": pass_id, "status": "revoked"}


@router.get("/{project_id}/guest-passes/{pass_id}/qr.png")
async def get_guest_qr_png(
    project_id: str,
    pass_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    """QR PNG bytes for the share sheet / print — same as worker entry-qr.png."""
    db = get_db()
    await _check_project_access(user, project_id)
    p = await db.guest_entry_passes.find_one(
        {"id": pass_id, "project_id": project_id}, {"_id": 0, "token": 1}
    )
    if not p:
        raise HTTPException(status_code=404, detail="קוד אורח לא נמצא")
    png = _qr_png_bytes(_gate_url(p["token"]))
    return StreamingResponse(
        io.BytesIO(png), media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="guest-qr.png"'},
    )


# =====================================================================
# qrg-briefing-edit E2 — org-level briefing text (project-scoped API).
# Gate: EXACTLY the induction-template edit chain (_resolve_project_org_edit
# — super_admin / org owner / org_admin / PM-of-project; MT read-only).
# =====================================================================
BRIEFING_MIN_CHARS = 50
BRIEFING_MAX_CHARS = 4000


class GuestBriefingSave(BaseModel):
    text: str


@router.get("/{project_id}/guest-briefing")
async def get_project_guest_briefing(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Same read audience as the induction-template content GET: managers
    (can_edit) OR SAFETY_WRITERS with project access."""
    from contractor_ops.safety.induction import _resolve_project_org_edit
    org_id, can_edit = await _resolve_project_org_edit(user, project_id)
    if not can_edit:
        if user.get("role") not in SAFETY_WRITERS:
            raise HTTPException(status_code=403, detail="אין הרשאה לצפייה בתדריך האורחים")
        await _check_project_access(user, project_id)
    if not org_id:
        raise HTTPException(status_code=404, detail="הפרויקט לא נמצא")
    db = get_db()
    doc = await db.guest_briefing_texts.find_one({"org_id": org_id}, {"_id": 0})
    text, version, _h = await get_guest_briefing(db, org_id)
    return {
        "text": text,
        "version": version,
        "is_custom": bool(doc),
        "can_edit": can_edit,
    }


@router.put("/{project_id}/guest-briefing")
async def save_project_guest_briefing(
    project_id: str,
    payload: GuestBriefingSave,
    user: dict = Depends(get_current_user),
):
    from contractor_ops.safety.induction import _resolve_project_org_edit
    org_id, can_edit = await _resolve_project_org_edit(user, project_id)
    if not org_id:
        raise HTTPException(status_code=404, detail="הפרויקט לא נמצא")
    if not can_edit:
        raise HTTPException(status_code=403, detail="רק הנהלת הארגון יכולה לערוך את תדריך האורחים")
    text = (payload.text or "").strip()
    if len(text) < BRIEFING_MIN_CHARS:
        raise HTTPException(status_code=422, detail=f"נוסח התדריך קצר מדי — נדרשים לפחות {BRIEFING_MIN_CHARS} תווים")
    if len(text) > BRIEFING_MAX_CHARS:
        raise HTTPException(status_code=422, detail=f"נוסח התדריך ארוך מדי — עד {BRIEFING_MAX_CHARS} תווים")
    db = get_db()
    # ATOMIC version bump (pipeline update): v1 is the code constant, so on
    # insert $ifNull seeds 1 and the +1 makes the FIRST override version 2;
    # concurrent PUTs each get a UNIQUE monotonic increment (no read-then-
    # write race, no lost update).
    from pymongo import ReturnDocument
    doc = await db.guest_briefing_texts.find_one_and_update(
        {"org_id": org_id},
        [{"$set": {
            "org_id": org_id,
            "text": text,
            "version": {"$add": [{"$ifNull": ["$version", 1]}, 1]},
            "updated_by": user["id"],
            "updated_at": _now(),
        }}],
        upsert=True,
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0, "version": 1},
    )
    new_version = int(doc["version"])
    await _audit("guest_briefing_text", org_id, "guest_briefing_updated", user["id"], {
        "org_id": org_id, "version": new_version,
    })
    return {"text": text, "version": new_version, "is_custom": True, "can_edit": True}


@router.delete("/{project_id}/guest-briefing")
async def reset_project_guest_briefing(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Removes the org override — guests go back to the built-in v1 text."""
    from contractor_ops.safety.induction import _resolve_project_org_edit
    org_id, can_edit = await _resolve_project_org_edit(user, project_id)
    if not org_id:
        raise HTTPException(status_code=404, detail="הפרויקט לא נמצא")
    if not can_edit:
        raise HTTPException(status_code=403, detail="רק הנהלת הארגון יכולה לאפס את תדריך האורחים")
    db = get_db()
    res = await db.guest_briefing_texts.delete_one({"org_id": org_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="אין נוסח מותאם — התדריך כבר בברירת המחדל")
    await _audit("guest_briefing_text", org_id, "guest_briefing_reset", user["id"], {
        "org_id": org_id,
    })
    text, version, _h = await get_guest_briefing(db, org_id)
    return {"text": text, "version": version, "is_custom": False, "can_edit": True}
