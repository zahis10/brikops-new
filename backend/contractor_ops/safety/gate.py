"""Batch qrg1-entry-gate — authed admin side of the worker entry-gate.

Tokens (worker_entry_tokens), QR PNG generation/storage, manual block,
scan-log admin list, and the flagged WhatsApp auto-send. The PUBLIC status
endpoint lives in gate_public.py (separate router, no auth import).
"""
import io
import re
import secrets

from pymongo.errors import DuplicateKeyError

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
from fastapi.responses import StreamingResponse


# =====================================================================
# Token helpers
# =====================================================================
def _new_token() -> str:
    """Opaque, ≥32 url-safe chars, never derived from worker data."""
    return secrets.token_urlsafe(24)  # 24 bytes → 32 url-safe chars


def _gate_url(token: str) -> str:
    from contractor_ops.router import get_public_base_url
    base = get_public_base_url()
    return f"{base}/gate/{token}" if base else f"/gate/{token}"


def _qr_png_bytes(url: str) -> bytes:
    import qrcode
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _store_qr_png(project_id: str, token_doc: dict) -> str:
    """Generate + persist the QR PNG per the key-at-rest pattern; return stored_ref."""
    from services.object_storage import save_bytes
    png = _qr_png_bytes(_gate_url(token_doc["token"]))
    key = f"safety/{project_id}/entry-qr/{token_doc['id']}.png"
    return save_bytes(png, key, "image/png")


async def ensure_entry_token(db, project_id: str, worker_id: str) -> dict:
    """Return the worker's ACTIVE token for this project, creating one if missing.

    Ensure-on-demand covers pre-existing workers (first send/print/status access).
    """
    tok = await db.worker_entry_tokens.find_one(
        {"project_id": project_id, "worker_id": worker_id, "status": "active"},
        {"_id": 0},
    )
    if tok:
        return tok
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "org_id": 1})
    doc = {
        "id": _new_id(),
        "token": _new_token(),
        "org_id": (proj or {}).get("org_id"),
        "project_id": project_id,
        "worker_id": worker_id,
        "status": "active",
        "created_at": _now(),
        "revoked_at": None,
        "rotated_from": None,
        "qr_ref": None,
    }
    try:
        doc["qr_ref"] = _store_qr_png(project_id, doc)
    except Exception as e:  # QR storage is best-effort; the token must exist
        logger.error(f"[GATE] QR store failed for token {doc['id']}: {e}")
    try:
        await db.worker_entry_tokens.insert_one(doc)
    except DuplicateKeyError:
        # concurrent ensure won the race — return the existing active token
        tok = await db.worker_entry_tokens.find_one(
            {"project_id": project_id, "worker_id": worker_id, "status": "active"},
            {"_id": 0},
        )
        if tok:
            return tok
        raise
    doc.pop("_id", None)
    return doc


async def rotate_entry_token(db, project_id: str, worker_id: str) -> dict:
    """Revoke all active tokens and issue a fresh one (new QR)."""
    now = _now()
    old = await db.worker_entry_tokens.find_one(
        {"project_id": project_id, "worker_id": worker_id, "status": "active"},
        {"_id": 0, "id": 1},
    )
    await db.worker_entry_tokens.update_many(
        {"project_id": project_id, "worker_id": worker_id, "status": "active"},
        {"$set": {"status": "revoked", "revoked_at": now}},
    )
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "org_id": 1})
    doc = {
        "id": _new_id(),
        "token": _new_token(),
        "org_id": (proj or {}).get("org_id"),
        "project_id": project_id,
        "worker_id": worker_id,
        "status": "active",
        "created_at": now,
        "revoked_at": None,
        "rotated_from": (old or {}).get("id"),
        "qr_ref": None,
    }
    try:
        doc["qr_ref"] = _store_qr_png(project_id, doc)
    except Exception as e:
        logger.error(f"[GATE] QR store failed for rotated token {doc['id']}: {e}")
    for _ in range(3):
        try:
            await db.worker_entry_tokens.insert_one(doc)
            doc.pop("_id", None)
            return doc
        except DuplicateKeyError:
            # concurrent rotate/ensure inserted an active token between our
            # revoke and insert — revoke it too and retry (last writer wins)
            doc.pop("_id", None)
            await db.worker_entry_tokens.update_many(
                {"project_id": project_id, "worker_id": worker_id, "status": "active"},
                {"$set": {"status": "revoked", "revoked_at": _now()}},
            )
    # heavy contention: converge on whichever concurrent rotate won the slot
    while True:
        tok = await db.worker_entry_tokens.find_one(
            {"project_id": project_id, "worker_id": worker_id, "status": "active"},
            {"_id": 0},
        )
        if tok:
            return tok
        # our final revoke may have cleared the slot — try to claim it
        try:
            await db.worker_entry_tokens.insert_one(doc)
            doc.pop("_id", None)
            return doc
        except DuplicateKeyError:
            doc.pop("_id", None)
            continue


async def revoke_entry_tokens(db, project_id: str, worker_id: str):
    """Revoke ALL tokens of a worker on this project (worker removal)."""
    await db.worker_entry_tokens.update_many(
        {"project_id": project_id, "worker_id": worker_id, "status": "active"},
        {"$set": {"status": "revoked", "revoked_at": _now()}},
    )


# =====================================================================
# WhatsApp auto-send (behind WA_ENTRY_QR_ENABLED — default FALSE)
# =====================================================================
async def maybe_send_entry_qr(db, project_id: str, worker: dict, token_doc: dict) -> dict:
    """Auto-send the entry QR via WA template on worker creation.

    Entirely behind WA_ENTRY_QR_ENABLED: when the flag is off (default) this
    returns WITHOUT touching the WA sender at all (V6 zero-calls guarantee).
    Never raises — a send failure must not fail worker creation.
    """
    from config import WA_ENTRY_QR_ENABLED, WA_TEMPLATE_WORKER_ENTRY_QR
    if not WA_ENTRY_QR_ENABLED:
        return {"skipped": "flag_off"}
    try:
        from contractor_ops.notification_service import (
            NotificationEngine, validate_e164,
        )
        phone = NotificationEngine._normalize_israeli_phone(worker.get("phone") or "")
        if not phone or not validate_e164(phone):
            return {"skipped": "no_valid_phone"}
        qr_url = generate_url(token_doc.get("qr_ref")) if token_doc.get("qr_ref") else None
        # Local-storage refs come back relative (/api/uploads/...) — the WA
        # image header requires an absolute https URL, so prefix the public base.
        if qr_url and not qr_url.startswith("http"):
            from contractor_ops.router import get_public_base_url
            base = get_public_base_url()
            qr_url = f"{base}{qr_url}" if base else None
        proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "name": 1})
        first = (worker.get("full_name") or "").strip().split()[0] if worker.get("full_name") else ""
        body_params = [
            {"parameter_name": "worker_name", "text": first},
            {"parameter_name": "project_name", "text": (proj or {}).get("name") or ""},
        ]
        from contractor_ops.reminder_service import _send_wa_template
        result = await _send_wa_template(
            phone, WA_TEMPLATE_WORKER_ENTRY_QR, body_params,
            header_image_url=qr_url,
        )
        return {"sent": True, "result": result}
    except Exception as e:
        logger.error(f"[GATE] entry-QR auto-send failed worker={worker.get('id')}: {e}")
        return {"skipped": "send_failed", "error": str(e)[:200]}


# =====================================================================
# Authed endpoints (safety router — PM/MT/super_admin)
# =====================================================================
@router.post("/{project_id}/workers/{worker_id}/entry-token")
async def get_or_create_entry_token(
    project_id: str,
    worker_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    """Ensure-on-demand: return the active entry token + gate URL + QR display URL."""
    db = get_db()
    await _check_project_access(user, project_id)
    worker = await db.safety_workers.find_one(
        {"id": worker_id, "project_id": project_id, "deletedAt": None}, {"_id": 0, "id": 1}
    )
    if not worker:
        raise HTTPException(status_code=404, detail="worker not found")
    tok = await ensure_entry_token(db, project_id, worker_id)
    return {
        "token": tok["token"],
        "gate_url": _gate_url(tok["token"]),
        "qr_display_url": generate_url(tok["qr_ref"]) if tok.get("qr_ref") else None,
        "created_at": tok["created_at"],
    }


@router.post("/{project_id}/workers/{worker_id}/entry-token/rotate")
async def rotate_entry_token_endpoint(
    project_id: str,
    worker_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    worker = await db.safety_workers.find_one(
        {"id": worker_id, "project_id": project_id, "deletedAt": None}, {"_id": 0, "id": 1}
    )
    if not worker:
        raise HTTPException(status_code=404, detail="worker not found")
    tok = await rotate_entry_token(db, project_id, worker_id)
    await _audit("worker_entry_token", tok["id"], "rotated", user["id"], {
        "project_id": project_id, "worker_id": worker_id, "rotated_from": tok.get("rotated_from"),
    })
    return {
        "token": tok["token"],
        "gate_url": _gate_url(tok["token"]),
        "qr_display_url": generate_url(tok["qr_ref"]) if tok.get("qr_ref") else None,
        "created_at": tok["created_at"],
    }


@router.get("/{project_id}/workers/{worker_id}/entry-qr.png")
async def get_entry_qr_png(
    project_id: str,
    worker_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    """The QR PNG bytes (for the native share sheet / print view). Ensures a token."""
    db = get_db()
    await _check_project_access(user, project_id)
    worker = await db.safety_workers.find_one(
        {"id": worker_id, "project_id": project_id, "deletedAt": None}, {"_id": 0, "id": 1}
    )
    if not worker:
        raise HTTPException(status_code=404, detail="worker not found")
    tok = await ensure_entry_token(db, project_id, worker_id)
    png = _qr_png_bytes(_gate_url(tok["token"]))
    return StreamingResponse(
        io.BytesIO(png), media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="entry-qr.png"'},
    )


class WorkerBlockBody(BaseModel):
    is_blocked: bool
    reason: Optional[str] = None


@router.patch("/{project_id}/workers/{worker_id}/block")
async def set_worker_block(
    project_id: str,
    worker_id: str,
    body: WorkerBlockBody,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)
    before = await db.safety_workers.find_one(
        {"id": worker_id, "project_id": project_id, "deletedAt": None}, {"_id": 0}
    )
    if not before:
        raise HTTPException(status_code=404, detail="worker not found")
    blocked = {
        "is_blocked": body.is_blocked,
        "reason": (body.reason or "").strip() or None,
        "by": user["id"],
        "at": _now(),
    }
    await db.safety_workers.update_one(
        {"id": worker_id, "project_id": project_id, "deletedAt": None},
        {"$set": {"blocked": blocked}},
    )
    await _audit("safety_worker", worker_id, "worker_block_change", user["id"], {
        "project_id": project_id,
        "before": before.get("blocked"),
        "after": blocked,
    })
    return {"id": worker_id, "blocked": blocked}


@router.get("/{project_id}/gate-scans")
async def list_gate_scans(
    project_id: str,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    worker_id: str | None = Query(None),
    result: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    """Newest-first scan log for the project. PM/MT/super_admin only.

    qrg1-fix1 B3: optional filters (worker/result/date range) + a "summary"
    aggregation over the same filter. Existing keys stay byte-compatible.
    """
    db = get_db()
    await _check_project_access(user, project_id)
    q = {"project_id": project_id}
    if worker_id:
        q["worker_id"] = worker_id
    if result is not None:
        if result not in ("green", "red", "invalid"):
            raise HTTPException(422, "תוצאה לא חוקית — יש לבחור מאושר, אין כניסה או לא תקף")
        q["result"] = result
    _DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    ts_range = {}
    if date_from is not None:
        if not _DATE_RE.match(date_from):
            raise HTTPException(422, "תאריך התחלה לא תקין — פורמט נדרש YYYY-MM-DD")
        ts_range["$gte"] = f"{date_from}T00:00:00"
    if date_to is not None:
        if not _DATE_RE.match(date_to):
            raise HTTPException(422, "תאריך סיום לא תקין — פורמט נדרש YYYY-MM-DD")
        ts_range["$lte"] = f"{date_to}T23:59:59.999999"
    if ts_range:
        q["ts"] = ts_range
    # ONE aggregation over the SAME filtered q (not paginated) → counts per result.
    summary = {"green": 0, "red": 0, "invalid": 0, "total": 0}
    async for row in db.gate_scan_log.aggregate([
        {"$match": q},
        {"$group": {"_id": "$result", "n": {"$sum": 1}}},
    ]):
        if row["_id"] in summary:
            summary[row["_id"]] = row["n"]
        summary["total"] += row["n"]
    total = await db.gate_scan_log.count_documents(q)
    items = await db.gate_scan_log.find(q, {"_id": 0}).sort("ts", -1).skip(offset).limit(limit).to_list(length=limit)
    # Resolve worker names for display (no PII beyond the name).
    worker_ids = list({it["worker_id"] for it in items if it.get("worker_id")})
    names = {}
    if worker_ids:
        cursor = db.safety_workers.find(
            {"id": {"$in": worker_ids}}, {"_id": 0, "id": 1, "full_name": 1}
        )
        async for w in cursor:
            names[w["id"]] = w.get("full_name")
    for it in items:
        it["worker_name"] = names.get(it.get("worker_id"))
    return {"items": items, "total": total, "limit": limit, "offset": offset, "summary": summary}
