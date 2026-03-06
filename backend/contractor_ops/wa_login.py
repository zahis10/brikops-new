import os
import secrets
import hashlib
import logging
import time
import httpx
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional

from contractor_ops.phone_utils import normalize_israeli_phone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/wa", tags=["wa-login"])

_db = None

def set_wa_login_db(db):
    global _db
    _db = db

def _get_db():
    if _db is None:
        raise RuntimeError("wa_login DB not initialized")
    return _db

MAGIC_LINK_TTL_MINUTES = 10
COLLECTION = "wa_login_tokens"


class CreateLinkRequest(BaseModel):
    phone: Optional[str] = None
    user_id: Optional[str] = None


class RequestLoginBody(BaseModel):
    phone: str


class SendLoginLinkRequest(BaseModel):
    to_phone: str


def _get_base_url() -> str:
    url = os.environ.get('PUBLIC_APP_URL', '').rstrip('/')
    if url:
        return url
    raw = os.environ.get('REPLIT_DOMAINS', os.environ.get('REPLIT_DEV_DOMAIN', ''))
    if raw:
        if ',' in raw:
            raw = raw.split(',')[0]
        return f"https://{raw}"
    return ''


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def _phone_last4(phone: str) -> str:
    return phone[-4:] if phone and len(phone) >= 4 else "????"


_rate_limits = defaultdict(list)
_RATE_LIMITS_PHONE = [(60, 1), (900, 5)]
_RATE_LIMITS_IP = [(900, 20)]

def _check_rate_limit(key: str, rules: list) -> bool:
    now = time.time()
    _rate_limits[key] = [ts for ts in _rate_limits[key] if now - ts < 900]
    for window_secs, max_count in rules:
        count = sum(1 for ts in _rate_limits[key] if now - ts < window_secs)
        if count >= max_count:
            return False
    return True

def _record_rate_limit(key: str):
    _rate_limits[key].append(time.time())

def _cleanup_rate_limits():
    now = time.time()
    stale = [k for k, v in _rate_limits.items() if not v or now - max(v) > 900]
    for k in stale:
        del _rate_limits[k]


async def _audit_wa_login(event: str, user_id: str = "", phone: str = "", extra: dict = None):
    try:
        db = _get_db()
        doc = {
            "event": event,
            "user_id": user_id,
            "phone_last4": _phone_last4(phone),
            "timestamp": datetime.now(timezone.utc),
        }
        if extra:
            doc.update(extra)
        await db["audit_events"].insert_one(doc)
    except Exception as e:
        logger.warning(f"[WA-LOGIN-AUDIT] Failed to log {event}: {e}")


async def _create_magic_link_internal(phone: str = None, user_id: str = None) -> dict:
    db = _get_db()

    if not phone and not user_id:
        raise HTTPException(status_code=400, detail="phone or user_id required")

    query = {}
    if user_id:
        query["id"] = user_id
    elif phone:
        phone_result = normalize_israeli_phone(phone)
        if not phone_result:
            raise HTTPException(status_code=400, detail="Invalid phone number")
        query["phone_e164"] = phone_result["phone_e164"]

    user = await db["users"].find_one(query)
    if not user:
        return None

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    token_prefix = raw_token[:6]
    now = datetime.now(timezone.utc)

    await db[COLLECTION].insert_one({
        "token_hash": token_hash,
        "token_prefix": token_prefix,
        "user_id": user["id"],
        "phone": user.get("phone_e164", ""),
        "created_at": now,
        "expires_at": now + timedelta(minutes=MAGIC_LINK_TTL_MINUTES),
        "used_at": None,
    })

    base = _get_base_url()
    url = f"{base}/auth/wa?token={raw_token}"

    logger.info(f"[WA-LOGIN] Magic link created for user={user['id']}, prefix={token_prefix}")

    await _audit_wa_login("wa_login_link_created", user_id=user["id"], phone=user.get("phone_e164", ""))

    return {"url": url, "expires_in_minutes": MAGIC_LINK_TTL_MINUTES, "user": user}


async def _send_wa_login_message(phone_e164: str, url: str) -> dict:
    wa_phone_id = os.environ.get("WA_PHONE_NUMBER_ID", "")
    wa_token = os.environ.get("WA_ACCESS_TOKEN", "")

    if not wa_phone_id or not wa_token:
        logger.error("[WA-LOGIN] WhatsApp credentials not configured, cannot send login link")
        return {"sent": False, "error": "wa_not_configured"}

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    token_list = qs.get("token", [])
    if not token_list:
        logger.error("[WA-LOGIN] Could not extract token from URL")
        return {"sent": False, "error": "missing_token_in_url"}
    token = token_list[0]

    to_digits = phone_e164.lstrip("+")

    api_url = f"https://graph.facebook.com/v25.0/{wa_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {wa_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_digits,
        "type": "template",
        "template": {
            "name": os.environ.get('WA_LOGIN_TEMPLATE_HE', 'brikops_login_link_he'),
            "language": {"code": "en"},
            "components": [
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": 0,
                    "parameters": [{"type": "text", "text": token}]
                }
            ]
        }
    }

    try:
        tpl_name = payload['template']['name']
        logger.info(f"[WA-LOGIN] Sending template {tpl_name} to ...{_phone_last4(phone_e164)}, request={payload}")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(api_url, json=payload, headers=headers)

        result = resp.json()
        logger.info(f"[WA-LOGIN] Response status={resp.status_code}, body={result}")
        if resp.status_code == 200:
            msg_id = result.get("messages", [{}])[0].get("id", "unknown")
            logger.info(f"[WA-LOGIN] Login template sent via WhatsApp to ...{_phone_last4(phone_e164)}, wa_msg_id={msg_id}")
            return {"sent": True, "wa_msg_id": msg_id, "request_payload": payload, "response": result}
        else:
            error_msg = result.get("error", {}).get("message", "unknown")
            logger.error(f"[WA-LOGIN] WhatsApp send failed: status={resp.status_code}, error={error_msg}")
            return {"sent": False, "error": error_msg, "request_payload": payload, "response": result}
    except Exception as e:
        logger.error(f"[WA-LOGIN] WhatsApp send exception: {e}")
        return {"sent": False, "error": str(e)}


GENERIC_RESPONSE = {"message": "אם המספר קיים במערכת, נשלח קישור התחברות בוואטסאפ."}


@router.post("/request-login")
async def request_login(body: RequestLoginBody, request: Request):
    client_ip = request.client.host if request.client else "unknown"

    phone_result = normalize_israeli_phone(body.phone)
    if not phone_result:
        return GENERIC_RESPONSE

    phone_e164 = phone_result["phone_e164"]

    phone_key = f"rl:phone:{phone_e164}"
    ip_key = f"rl:ip:{client_ip}"

    if not _check_rate_limit(phone_key, _RATE_LIMITS_PHONE):
        raise HTTPException(status_code=429, detail="נא לנסות שוב מאוחר יותר.")
    if not _check_rate_limit(ip_key, _RATE_LIMITS_IP):
        raise HTTPException(status_code=429, detail="נא לנסות שוב מאוחר יותר.")

    _record_rate_limit(phone_key)
    _record_rate_limit(ip_key)

    _cleanup_rate_limits()

    link_result = await _create_magic_link_internal(phone=phone_e164)

    if link_result and link_result.get("url"):
        user = link_result["user"]
        wa_result = await _send_wa_login_message(phone_e164, link_result["url"])
        await _audit_wa_login(
            "wa_login_link_sent",
            user_id=user["id"],
            phone=phone_e164,
            extra={"channel": "whatsapp", "wa_sent": wa_result.get("sent", False)},
        )

    return GENERIC_RESPONSE


@router.post("/create-link")
async def create_magic_link(body: CreateLinkRequest):
    from config import ENABLE_DEBUG_ENDPOINTS
    if not ENABLE_DEBUG_ENDPOINTS:
        raise HTTPException(status_code=403, detail="Debug endpoints disabled")
    result = await _create_magic_link_internal(phone=body.phone, user_id=body.user_id)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return {"url": result["url"], "expires_in_minutes": result["expires_in_minutes"]}


@router.get("/verify")
async def verify_magic_link(token: str = Query(...)):
    db = _get_db()

    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    doc = await db[COLLECTION].find_one_and_update(
        {
            "token_hash": token_hash,
            "used_at": None,
            "expires_at": {"$gt": now},
        },
        {"$set": {"used_at": now}},
    )

    if not doc:
        existing = await db[COLLECTION].find_one({"token_hash": token_hash})
        if existing and existing.get("used_at"):
            reason = "already_used"
        elif existing and existing["expires_at"] <= now:
            reason = "expired"
        else:
            reason = "not_found"

        await _audit_wa_login(
            "wa_login_failed",
            phone=existing.get("phone", "") if existing else "",
            user_id=existing.get("user_id", "") if existing else "",
            extra={"reason": reason, "token_prefix": existing.get("token_prefix", "") if existing else token[:6]},
        )

        detail_map = {
            "already_used": "הקישור כבר נוצל",
            "expired": "הקישור פג תוקף",
            "not_found": "קישור לא תקין או פג תוקף",
        }
        raise HTTPException(status_code=400, detail=detail_map.get(reason, "קישור לא תקין"))

    user = await db["users"].find_one({"id": doc["user_id"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from contractor_ops.router import _create_token
    from config import is_super_admin_phone
    platform_role = 'super_admin' if is_super_admin_phone(user.get('phone_e164', '')) else user.get('platform_role', 'none')
    jwt_token = _create_token(
        user_id=user["id"],
        email=user.get("email", ""),
        role=user.get("role", "viewer"),
        platform_role=platform_role,
        session_version=user.get("session_version", 0),
        phone_e164=user.get("phone_e164", ""),
    )

    base = _get_base_url()
    redirect_url = f"{base}/auth/wa#token={jwt_token}"

    await _audit_wa_login(
        "wa_login_verified",
        user_id=user["id"],
        phone=user.get("phone_e164", ""),
        extra={"token_prefix": doc.get("token_prefix", "")},
    )

    logger.info(f"[WA-LOGIN] Verified login for user={user['id']}, prefix={doc.get('token_prefix', '')}")

    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/send-login-link")
async def send_login_link_debug(body: SendLoginLinkRequest):
    from config import ENABLE_DEBUG_ENDPOINTS
    if not ENABLE_DEBUG_ENDPOINTS:
        raise HTTPException(status_code=403, detail="Debug endpoints disabled")

    phone_result = normalize_israeli_phone(body.to_phone)
    if not phone_result:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    phone_e164 = phone_result["phone_e164"]

    link_result = await _create_magic_link_internal(phone=phone_e164)
    if not link_result:
        raise HTTPException(status_code=404, detail="User not found for this phone")
    url = link_result["url"]

    wa_result = await _send_wa_login_message(phone_e164, url)

    return {
        "wa_sent": wa_result.get("sent", False),
        "wa_msg_id": wa_result.get("wa_msg_id"),
        "error": wa_result.get("error"),
        "request_payload": wa_result.get("request_payload"),
        "response": wa_result.get("response"),
    }
