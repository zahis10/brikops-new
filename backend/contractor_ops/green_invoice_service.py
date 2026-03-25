import time
import hashlib
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

GI_TOKEN_SAFETY_MARGIN = 120


class GreenInvoiceError(Exception):
    def __init__(self, message: str, status_code: int = 0, error_code: int = 0, raw: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.raw = raw or {}


_cached_token: Optional[str] = None
_cached_token_expires: float = 0


def _get_config():
    from config import GI_BASE_URL, GI_API_KEY_ID, GI_API_SECRET
    if not GI_BASE_URL or not GI_API_KEY_ID or not GI_API_SECRET:
        raise GreenInvoiceError("Green Invoice credentials not configured")
    return GI_BASE_URL, GI_API_KEY_ID, GI_API_SECRET


def _redact(url: str) -> str:
    return url.split("/api/v1")[-1] if "/api/v1" in url else url


async def get_token() -> str:
    global _cached_token, _cached_token_expires

    if _cached_token and time.time() < _cached_token_expires:
        return _cached_token

    base_url, key_id, secret = _get_config()
    url = f"{base_url}/account/token"
    payload = {"id": key_id, "secret": secret}

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, json=payload)
        except httpx.RequestError as exc:
            logger.error("[GI] Auth request failed: %s", type(exc).__name__)
            raise GreenInvoiceError(f"Auth request failed: {type(exc).__name__}")

    if resp.status_code != 200:
        logger.error("[GI] Auth failed: status=%d", resp.status_code)
        raise GreenInvoiceError("Auth failed", status_code=resp.status_code)

    data = resp.json()
    token = data.get("token")
    expires = data.get("expires", 0)
    if not token:
        raise GreenInvoiceError("Auth response missing token")

    _cached_token = token
    _cached_token_expires = expires - GI_TOKEN_SAFETY_MARGIN
    logger.info("[GI] Token refreshed, expires in %ds", expires - int(time.time()))
    return token


async def _request(method: str, path: str, json_body: dict = None, retry_on_5xx: bool = True) -> dict:
    base_url = _get_config()[0]
    url = f"{base_url}{path}"
    token = await get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(2 if retry_on_5xx else 1):
            try:
                resp = await client.request(method, url, json=json_body, headers=headers)
            except httpx.RequestError as exc:
                logger.error("[GI] Request error %s %s: %s", method, _redact(url), type(exc).__name__)
                raise GreenInvoiceError(f"Request error: {type(exc).__name__}")

            if resp.status_code == 401:
                global _cached_token, _cached_token_expires
                _cached_token = None
                _cached_token_expires = 0
                token = await get_token()
                headers["Authorization"] = f"Bearer {token}"
                continue

            if resp.status_code >= 500 and attempt == 0 and retry_on_5xx:
                logger.warning("[GI] 5xx on %s %s (attempt %d), retrying", method, _redact(url), attempt + 1)
                continue

            break

    data = {}
    try:
        data = resp.json()
    except Exception:
        pass

    if resp.status_code >= 400:
        error_msg = data.get("errorMessage", f"HTTP {resp.status_code}")
        error_code = data.get("errorCode", 0)
        logger.error("[GI] API error %s %s: %d/%d %s", method, _redact(url), resp.status_code, error_code, error_msg)
        raise GreenInvoiceError(error_msg, status_code=resp.status_code, error_code=error_code, raw=data)

    return data


async def create_payment_form(
    client_name: str,
    client_email: str,
    description: str,
    amount: float,
    currency: str = "ILS",
    success_url: str = "",
    failure_url: str = "",
    remarks: str = "",
) -> dict:
    payload = {
        "type": 320,
        "lang": "he",
        "currency": currency,
        "vatType": 0,
        "signed": True,
        "rounding": True,
        "amount": amount,
        "maxPayments": 1,
        "client": {
            "name": client_name,
            "emails": [client_email] if client_email else [],
            "add": True,
        },
        "income": [
            {
                "description": description,
                "quantity": 1,
                "price": amount,
                "currency": currency,
                "vatType": 0,
            }
        ],
        "successUrl": success_url,
        "failureUrl": failure_url,
    }
    if remarks:
        payload["remarks"] = remarks

    logger.info("[GI] Creating payment form: amount=%.2f %s client=%s", amount, currency, client_name)
    result = await _request("POST", "/payments/form", json_body=payload)
    logger.info("[GI] Payment form created: url=%s", result.get("url", "<no url>"))
    return result


async def get_document(document_id: str) -> dict:
    logger.info("[GI] Fetching document: %s", document_id)
    return await _request("GET", f"/documents/{document_id}")


def compute_payload_hash(payload: dict) -> str:
    import json
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
