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
# G1 — visitor safety briefing (LOCKED Hebrew constant, version 1).
# Zahi ruling 2026-07-17: a coming batch adds org-level editing of this
# text; the override will live inside get_guest_briefing(). Until then,
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


def get_guest_briefing() -> tuple[str, int, str]:
    """(text, version, hash[:12]) — the ONLY way to access the briefing.

    The future org-level override (management-edited text) plugs in HERE.
    """
    text = GUEST_BRIEFING_TEXT_HE
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return text, GUEST_BRIEFING_VERSION, h


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
