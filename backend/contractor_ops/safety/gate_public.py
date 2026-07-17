"""Batch qrg1-entry-gate — PUBLIC worker entry-gate status endpoint.

STANDALONE router (NOT the authed safety router): scanned by guards with no
BrikOps account, so there is NO auth dependency here — this module must never
import get_current_user. Registered in server.py behind ENABLE_SAFETY_MODULE.

Privacy contract (locked): the payload NEVER contains phone, id numbers, the
full document, or any other worker. Green exposes only first name, photo
display URL, project name, induction validity and yellow warnings. Every
invalid cause (bad token / revoked / deleted worker) returns the SAME neutral
{state:"invalid"} body — no enumeration.
"""
import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response, HTTPException

from contractor_ops.router import get_db
from services.object_storage import generate_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gate", tags=["gate-public"])

# Lightweight in-memory per-IP throttle (no new dep): 60 req/min → 429.
GATE_RATE_LIMIT = 60
GATE_RATE_WINDOW_SECONDS = 60
_hits = {}  # ip -> (window_start_monotonic, count)
_HITS_MAX = 10000


def _check_throttle(ip: str):
    now = time.monotonic()
    win_start, count = _hits.get(ip, (now, 0))
    if now - win_start >= GATE_RATE_WINDOW_SECONDS:
        win_start, count = now, 0
    count += 1
    if len(_hits) >= _HITS_MAX and ip not in _hits:
        _hits.clear()  # crude but bounded; resets all windows
    _hits[ip] = (win_start, count)
    if count > GATE_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="יותר מדי בקשות — נסה שוב בעוד רגע")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first_name(full_name: str) -> str:
    return (full_name or "").strip().split()[0] if (full_name or "").strip() else ""


def _photo_display(ref):
    if not ref:
        return None
    try:
        return generate_url(ref)
    except Exception:
        return None


async def _log_scan(db, *, project_id=None, worker_id=None, token_id=None,
                    result, reasons, guest_pass_id=None):
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "worker_id": worker_id,
            "token_id": token_id,
            "ts": _now(),
            "result": result,
            "reasons": reasons,
        }
        # qrg-guest: extra key ONLY on guest rows — worker rows stay
        # byte-compatible with the qrg1/fix1 contract.
        if guest_pass_id is not None:
            doc["guest_pass_id"] = guest_pass_id
        await db.gate_scan_log.insert_one(doc)
    except Exception as e:  # scan logging must never break the gate page
        logger.error(f"[GATE] scan log insert failed: {e}")


_INVALID = {"state": "invalid"}


@router.get("/{token}")
async def gate_status(token: str, request: Request, response: Response):
    """Live entry-gate status for a scanned worker QR. Public, no auth."""
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    # qrg1-fix1 B4: behind nginx/CF the raw client.host is the proxy — derive
    # the throttle key exactly like the global limiter (server.py).
    xff = request.headers.get("x-forwarded-for", "")
    if xff and "," in xff:
        xff = xff.split(",")[0].strip()
    ip = xff.strip() or (request.client.host if request.client else "") or "unknown"
    _check_throttle(ip)

    db = get_db()

    tok = None
    if token and 20 <= len(token) <= 128:
        tok = await db.worker_entry_tokens.find_one(
            {"token": token, "status": "active"}, {"_id": 0}
        )
    if not tok:
        # qrg-guest G4: worker-token miss → try an active guest pass before
        # the neutral invalid. Worker branch below stays UNCHANGED.
        gp = None
        if token and 20 <= len(token) <= 128:
            gp = await db.guest_entry_passes.find_one(
                {"token": token, "status": "active"}, {"_id": 0}
            )
        if gp:
            return await _guest_status_payload(db, gp, log=True)
        await _log_scan(db, result="invalid", reasons=["token_not_found_or_revoked"])
        return _INVALID

    worker = await db.safety_workers.find_one(
        {"id": tok["worker_id"], "project_id": tok["project_id"], "deletedAt": None},
        {"_id": 0},
    )
    if not worker:
        await _log_scan(
            db, project_id=tok["project_id"], token_id=tok["id"],
            result="invalid", reasons=["worker_missing"],
        )
        return _INVALID

    project_id = tok["project_id"]
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "name": 1})
    project_name = (proj or {}).get("name") or ""

    blocked = (worker.get("blocked") or {})
    if blocked.get("is_blocked"):
        await _log_scan(
            db, project_id=project_id, worker_id=worker["id"], token_id=tok["id"],
            result="red", reasons=["blocked"],
        )
        return {
            "state": "red",
            "reason": "blocked",
            "first_name": _first_name(worker.get("full_name")),
            "project_name": project_name,
        }

    # Induction validity — same logic/constant as the workers-list aggregation
    # (fix4): max expires_at over SIGNED induction trainings, not deleted.
    from contractor_ops.safety.induction import INDUCTION_TRAINING_TYPE
    today = datetime.now(timezone.utc).date().isoformat()
    agg = await db.safety_trainings.aggregate([
        {"$match": {
            "project_id": project_id,
            "deletedAt": None,
            "training_type": INDUCTION_TRAINING_TYPE,
            "worker_id": worker["id"],
            "worker_signature": {"$ne": None},
        }},
        {"$group": {"_id": "$worker_id", "max_expires": {"$max": "$expires_at"}}},
    ]).to_list(length=1)
    induction_valid_until = agg[0].get("max_expires") if agg else None

    if not induction_valid_until or str(induction_valid_until)[:10] < today:
        payload = {
            "state": "red",
            "reason": "induction",
            "first_name": _first_name(worker.get("full_name")),
            "project_name": project_name,
        }
        reasons = ["induction_expired" if induction_valid_until else "induction_missing"]
        if induction_valid_until:
            payload["expired_at"] = str(induction_valid_until)[:10]
        await _log_scan(
            db, project_id=project_id, worker_id=worker["id"], token_id=tok["id"],
            result="red", reasons=reasons,
        )
        return payload

    # Yellow warnings — OTHER training types whose latest expiry has passed.
    warnings = []
    other = await db.safety_trainings.aggregate([
        {"$match": {
            "project_id": project_id,
            "deletedAt": None,
            "worker_id": worker["id"],
            "training_type": {"$ne": INDUCTION_TRAINING_TYPE},
            "expires_at": {"$ne": None},
        }},
        {"$group": {"_id": "$training_type", "max_expires": {"$max": "$expires_at"}}},
    ]).to_list(length=50)
    for row in other:
        exp = str(row.get("max_expires") or "")[:10]
        if exp and exp < today:
            warnings.append({"type": row["_id"], "expired_at": exp})

    await _log_scan(
        db, project_id=project_id, worker_id=worker["id"], token_id=tok["id"],
        result="green", reasons=(["warnings"] if warnings else []),
    )
    return {
        "state": "green",
        "first_name": _first_name(worker.get("full_name")),
        "photo_display_url": _photo_display(worker.get("photo_ref")),
        "project_name": project_name,
        "induction_valid_until": str(induction_valid_until)[:10],
        "warnings": warnings,
    }


# =====================================================================
# qrg-guest — guest branch helpers + public sign endpoint (G4/G5)
# =====================================================================
GUEST_SIG_MAX_BYTES = 600 * 1024  # hard cap — public write, no user quota
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


async def _guest_status_payload(db, gp: dict, *, log: bool) -> dict:
    """Shared G4/G5 response shape. NEVER includes signature_ref/URL or any
    PII beyond guest first name + company (public contract)."""
    from contractor_ops.safety.guest import get_guest_briefing
    from contractor_ops.utils.timezone import israel_today

    briefing = gp.get("briefing") or {}
    if not briefing.get("signed"):
        text, version, _h = get_guest_briefing()
        if log:
            await _log_scan(
                db, project_id=gp.get("project_id"), guest_pass_id=gp["id"],
                result="red", reasons=["guest_unsigned"],
            )
        return {
            "state": "guest_briefing",
            "guest_name": gp.get("guest_name"),
            "guest_company": gp.get("guest_company"),
            "briefing_text": text,
            "briefing_version": version,
        }

    today = israel_today()
    if gp.get("valid_on") == today:
        if log:
            await _log_scan(
                db, project_id=gp.get("project_id"), guest_pass_id=gp["id"],
                result="green", reasons=["guest"],
            )
        return {
            "state": "green",
            "reason": "guest",
            "guest_name": gp.get("guest_name"),
            "guest_company": gp.get("guest_company"),
            "valid_on": gp.get("valid_on"),
        }

    if log:
        await _log_scan(
            db, project_id=gp.get("project_id"), guest_pass_id=gp["id"],
            result="red", reasons=["guest_wrong_date"],
        )
    return {
        "state": "red",
        "reason": "guest_date",
        "guest_name": gp.get("guest_name"),
        "valid_on": gp.get("valid_on"),
    }


@router.post("/{token}/guest-sign")
async def guest_sign(token: str, request: Request, response: Response):
    """Guest signs the visitor briefing — the FIRST public WRITE endpoint.

    Safe only with the full binding list: token-gated, sign-once-lock (409),
    600KB hard cap, PNG magic bytes + content-type, per-IP throttle, and the
    same no-PII/no-signature-URL public contract as the GET.
    """
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    xff = request.headers.get("x-forwarded-for", "")
    if xff and "," in xff:
        xff = xff.split(",")[0].strip()
    ip = xff.strip() or (request.client.host if request.client else "") or "unknown"
    _check_throttle(ip)

    db = get_db()

    gp = None
    if token and 20 <= len(token) <= 128:
        gp = await db.guest_entry_passes.find_one(
            {"token": token, "status": "active"}, {"_id": 0}
        )
    if not gp:
        # neutral 404 — no enumeration between unknown/revoked/worker tokens
        raise HTTPException(status_code=404, detail="קוד לא תקף")
    if (gp.get("briefing") or {}).get("signed"):
        raise HTTPException(status_code=409, detail="התדריך כבר נחתם")

    form = await request.form()
    signer_name = str(form.get("signer_name") or "").strip()
    if not signer_name:
        raise HTTPException(status_code=422, detail="יש להזין שם החותם")
    if len(signer_name) > 120:
        raise HTTPException(status_code=422, detail="שם החותם ארוך מדי")
    sig = form.get("signature_image")
    if sig is None or isinstance(sig, str):
        raise HTTPException(status_code=422, detail="חסרה תמונת חתימה")
    if sig.content_type and sig.content_type != "image/png":
        raise HTTPException(status_code=422, detail="סוג קובץ לא נתמך — PNG בלבד")
    # Hard byte cap BEFORE accepting: read cap+1 so an oversized body is
    # rejected by length without buffering more than the cap.
    img_bytes = await sig.read(GUEST_SIG_MAX_BYTES + 1)
    if len(img_bytes) > GUEST_SIG_MAX_BYTES:
        raise HTTPException(status_code=422, detail="קובץ החתימה גדול מדי (עד 600KB)")
    if len(img_bytes) < len(_PNG_MAGIC) or not img_bytes.startswith(_PNG_MAGIC):
        raise HTTPException(status_code=422, detail="סוג קובץ לא נתמך — PNG בלבד")

    from services.object_storage import save_bytes
    from contractor_ops.safety.guest import get_guest_briefing
    _text, version, briefing_hash = get_guest_briefing()
    s3_key = f"safety/{gp['project_id']}/guest-passes/{gp['id']}/sig.png"
    signature_ref = save_bytes(img_bytes, s3_key, "image/png")

    # SIGN-ONCE-LOCK at the DB level: re-assert unsigned inside the filter so
    # two concurrent signs cannot both win (draft-mutation race pattern).
    res = await db.guest_entry_passes.update_one(
        {"id": gp["id"], "status": "active", "briefing.signed": False},
        {"$set": {"briefing": {
            "signed": True,
            "signed_at": _now(),
            "signer_name": signer_name,
            "signature_ref": signature_ref,
            "briefing_version": version,
            "briefing_hash": briefing_hash,
        }}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=409, detail="התדריך כבר נחתם")

    fresh = await db.guest_entry_passes.find_one({"id": gp["id"]}, {"_id": 0})
    return await _guest_status_payload(db, fresh, log=True)
