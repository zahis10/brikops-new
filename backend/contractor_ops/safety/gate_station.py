"""Batch qrg2-station — PUBLIC guard-station endpoints (no auth).

The guard's phone opens /station/{station_token} in the browser and this
module powers it: resolve the station → check scanned worker/guest codes →
manual name search. STANDALONE router (like gate_public): must never import
get_current_user. Mounted in server.py behind ENABLE_SAFETY_MODULE.

Privacy contract: station responses expose ONLY what the guard needs —
worker/guest name + photo display URL + Hebrew reasons. No phones, no id
numbers, no raw storage refs. Foreign-project tokens/workers resolve to the
SAME neutral invalid as unknown codes (no enumeration). Every check is
logged via _log_scan with the additive scanned_via/station_token_id fields.
"""
import logging
import re
import time

from fastapi import APIRouter, HTTPException, Query, Request, Response

from contractor_ops.router import get_db
from contractor_ops.safety.gate_public import (
    _guest_status_payload,
    _log_scan,
    _photo_display,
    _worker_gate_result,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/station", tags=["gate-station-public"])

# In-module, in-memory throttles (same style as gate_public._check_throttle):
# per STATION TOKEN 300/min (morning rush) AND per XFF-IP 120/min backstop
# (invalid-token spray). The global /api limiter exempts /api/station/ (B4).
STATION_TOKEN_LIMIT = 300
STATION_IP_LIMIT = 120
STATION_RATE_WINDOW_SECONDS = 60
_hits = {}  # key -> (window_start_monotonic, count)
_HITS_MAX = 10000


def _bump(key: str, limit: int):
    now = time.monotonic()
    win_start, count = _hits.get(key, (now, 0))
    if now - win_start >= STATION_RATE_WINDOW_SECONDS:
        win_start, count = now, 0
    count += 1
    if len(_hits) >= _HITS_MAX and key not in _hits:
        _hits.clear()  # crude but bounded; resets all windows
    _hits[key] = (win_start, count)
    if count > limit:
        raise HTTPException(status_code=429, detail="יותר מדי בקשות — נסה שוב בעוד רגע")


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff and "," in xff:
        xff = xff.split(",")[0].strip()
    return xff.strip() or (request.client.host if request.client else "") or "unknown"


def _throttle(request: Request, station_token: str):
    _bump(f"ip:{_client_ip(request)}", STATION_IP_LIMIT)
    _bump(f"tok:{station_token}", STATION_TOKEN_LIMIT)


async def _resolve_station(db, station_token: str) -> dict:
    """Active station + its project (id/name only). Miss/revoked → neutral 404."""
    st = None
    if station_token and 20 <= len(station_token) <= 128:
        st = await db.gate_station_tokens.find_one(
            {"token": station_token, "status": "active"},
            {"_id": 0, "id": 1, "project_id": 1},
        )
    if not st:
        raise HTTPException(status_code=404, detail="עמדה לא תקפה")
    proj = await db.projects.find_one(
        {"id": st["project_id"]}, {"_id": 0, "id": 1, "name": 1}
    )
    st["project_name"] = (proj or {}).get("name") or ""
    return st


# Trailing token inside a scanned code (full gate URL or bare token).
_TOKEN_RE = re.compile(r"([A-Za-z0-9_-]{20,})\s*$")


def _extract_token(code: str):
    m = _TOKEN_RE.search((code or "").strip())
    return m.group(1) if m else None


_INVALID = {"result": "invalid", "reasons": ["קוד לא תקף"]}

# Guard-facing Hebrew reasons for internal worker decision codes.
_WORKER_REASONS_HE = {
    "blocked": "העובד חסום — אין כניסה",
    "induction_missing": "אין תדריך בטיחות בתוקף",
    "induction_expired": "תדריך הבטיחות פג תוקף",
}


def _noindex(response: Response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


def _worker_check_payload(res: dict, worker: dict) -> dict:
    out = {
        "result": res["state"],
        "kind": "worker",
        "name": worker.get("full_name") or "",
        # decision 2א: photo on green; fail-soft None (initials circle in FE)
        "photo_display_url": _photo_display(worker.get("photo_ref")),
    }
    if res["state"] == "red":
        reasons = [_WORKER_REASONS_HE.get(r, r) for r in res["log_reasons"]]
        if res.get("expired_at"):
            reasons = [f"{reasons[0]} ({res['expired_at']})"]
        out["reasons"] = reasons
    return out


def _guest_check_payload(state_payload: dict) -> dict:
    """Map the existing _guest_status_payload shape to the station shape."""
    name = state_payload.get("guest_name") or ""
    if state_payload.get("state") == "green":
        return {"result": "green", "kind": "guest", "name": name,
                "photo_display_url": None}
    if state_payload.get("state") == "guest_briefing":
        return {"result": "red", "kind": "guest", "name": name,
                "photo_display_url": None,
                "reasons": ["האורח לא חתם על התדריך"]}
    return {"result": "red", "kind": "guest", "name": name,
            "photo_display_url": None,
            "reasons": ["הקוד לא בתוקף להיום"]}


@router.get("/{station_token}/meta")
async def station_meta(station_token: str, request: Request, response: Response):
    _noindex(response)
    _throttle(request, station_token)
    db = get_db()
    st = await _resolve_station(db, station_token)
    return {"project_name": st["project_name"]}


@router.get("/{station_token}/check")
async def station_check(
    station_token: str,
    request: Request,
    response: Response,
    code: str = Query(""),
):
    """Check a scanned code (full gate URL or bare token) against the gate logic."""
    _noindex(response)
    _throttle(request, station_token)
    db = get_db()
    st = await _resolve_station(db, station_token)

    token = _extract_token(code)
    if not token or len(token) > 128:
        await _log_scan(db, project_id=st["project_id"], result="invalid",
                        reasons=["station_bad_code"],
                        scanned_via="station", station_token_id=st["id"])
        return dict(_INVALID)

    # Worker token FIRST, then guest pass; the subject's project MUST equal
    # the station's project — any mismatch is the SAME neutral invalid.
    wet = await db.worker_entry_tokens.find_one(
        {"token": token, "status": "active"}, {"_id": 0}
    )
    if wet:
        if wet["project_id"] != st["project_id"]:
            await _log_scan(db, project_id=st["project_id"], result="invalid",
                            reasons=["station_foreign_project"],
                            scanned_via="station", station_token_id=st["id"])
            return dict(_INVALID)
        worker = await db.safety_workers.find_one(
            {"id": wet["worker_id"], "project_id": wet["project_id"], "deletedAt": None},
            {"_id": 0},
        )
        if not worker:
            await _log_scan(db, project_id=st["project_id"], token_id=wet["id"],
                            result="invalid", reasons=["worker_missing"],
                            scanned_via="station", station_token_id=st["id"])
            return dict(_INVALID)
        res = await _worker_gate_result(db, wet, worker)
        await _log_scan(db, project_id=st["project_id"], worker_id=worker["id"],
                        token_id=wet["id"], result=res["state"],
                        reasons=res["log_reasons"],
                        scanned_via="station", station_token_id=st["id"])
        return _worker_check_payload(res, worker)

    gp = await db.guest_entry_passes.find_one(
        {"token": token, "status": "active"}, {"_id": 0}
    )
    if gp:
        if gp.get("project_id") != st["project_id"]:
            await _log_scan(db, project_id=st["project_id"], result="invalid",
                            reasons=["station_foreign_project"],
                            scanned_via="station", station_token_id=st["id"])
            return dict(_INVALID)
        # Reuse the existing guest decision (log=False — we log the station row)
        state_payload = await _guest_status_payload(db, gp, log=False)
        out = _guest_check_payload(state_payload)
        await _log_scan(db, project_id=st["project_id"], guest_pass_id=gp["id"],
                        result=("green" if out["result"] == "green" else "red"),
                        reasons=(["guest"] if out["result"] == "green"
                                 else (["guest_unsigned"]
                                       if state_payload.get("state") == "guest_briefing"
                                       else ["guest_wrong_date"])),
                        scanned_via="station", station_token_id=st["id"])
        return out

    await _log_scan(db, project_id=st["project_id"], result="invalid",
                    reasons=["token_not_found_or_revoked"],
                    scanned_via="station", station_token_id=st["id"])
    return dict(_INVALID)


@router.get("/{station_token}/search")
async def station_search(
    station_token: str,
    request: Request,
    response: Response,
    q: str = Query(""),
):
    """Manual name search (decision 3א). PII-minimal: 3 fields only, ≤8 items."""
    _noindex(response)
    _throttle(request, station_token)
    db = get_db()
    st = await _resolve_station(db, station_token)

    q = (q or "").strip()
    if len(q) < 2:
        return {"items": []}
    pattern = re.escape(q)[:120]
    cursor = db.safety_workers.find(
        {"project_id": st["project_id"], "deletedAt": None,
         "full_name": {"$regex": pattern, "$options": "i"}},
        {"_id": 0, "id": 1, "full_name": 1, "photo_ref": 1},
    ).limit(8)
    items = []
    async for w in cursor:
        items.append({
            "worker_id": w["id"],
            "name": w.get("full_name") or "",
            "photo_display_url": _photo_display(w.get("photo_ref")),
        })
    return {"items": items}


@router.get("/{station_token}/check-worker")
async def station_check_worker(
    station_token: str,
    request: Request,
    response: Response,
    worker_id: str = Query(""),
):
    """Manual check by worker_id (from /search). Same shape as /check."""
    _noindex(response)
    _throttle(request, station_token)
    db = get_db()
    st = await _resolve_station(db, station_token)

    worker = None
    if worker_id:
        worker = await db.safety_workers.find_one(
            {"id": worker_id, "project_id": st["project_id"], "deletedAt": None},
            {"_id": 0},
        )
    if not worker:
        await _log_scan(db, project_id=st["project_id"], result="invalid",
                        reasons=["station_manual_worker_missing"],
                        scanned_via="station-manual", station_token_id=st["id"])
        return dict(_INVALID)

    # _worker_gate_result only reads project_id from the token doc — the
    # manual path has no worker token, so pass the station's project scope.
    res = await _worker_gate_result(db, {"project_id": st["project_id"]}, worker)
    await _log_scan(db, project_id=st["project_id"], worker_id=worker["id"],
                    result=res["state"], reasons=res["log_reasons"],
                    scanned_via="station-manual", station_token_id=st["id"])
    return _worker_check_payload(res, worker)
