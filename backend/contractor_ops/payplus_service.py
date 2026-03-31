import json
import logging
import httpx

from config import (
    PAYPLUS_API_KEY,
    PAYPLUS_SECRET_KEY,
    PAYPLUS_PAYMENT_PAGE_UID,
    PAYPLUS_TERMINAL_UID,
    PAYPLUS_ENV,
    PAYPLUS_CALLBACK_URL,
)

logger = logging.getLogger(__name__)

SANDBOX_URL = "https://restapidev.payplus.co.il/api/v1.0"
PRODUCTION_URL = "https://restapi.payplus.co.il/api/v1.0"


def _base_url() -> str:
    if PAYPLUS_ENV == "production":
        return PRODUCTION_URL
    return SANDBOX_URL


def _auth_headers() -> dict:
    return {
        "Authorization": json.dumps({
            "api_key": PAYPLUS_API_KEY,
            "secret_key": PAYPLUS_SECRET_KEY,
        }),
        "Content-Type": "application/json",
    }


def _callback_url() -> str:
    if PAYPLUS_CALLBACK_URL:
        return PAYPLUS_CALLBACK_URL
    from config import PASSWORD_RESET_BASE_URL
    base = PASSWORD_RESET_BASE_URL.rstrip("/")
    backend_base = base.replace("://app.", "://api.")
    return f"{backend_base}/api/billing/webhook/payplus"


def _frontend_base_url() -> str:
    from config import PASSWORD_RESET_BASE_URL
    return PASSWORD_RESET_BASE_URL.rstrip("/")


class PayPlusError(Exception):
    pass


async def create_payment_page(
    org_id: str,
    org_name: str,
    plan_name: str,
    amount: float,
    customer_email: str,
    customer_name: str,
    customer_phone: str,
) -> dict:
    url = f"{_base_url()}/PaymentPages/generateLink"
    frontend = _frontend_base_url()
    payload = {
        "payment_page_uid": PAYPLUS_PAYMENT_PAGE_UID,
        "charge_method": 1,
        "create_token": True,
        "amount": amount,
        "currency_code": "ILS",
        "vat_type": 0,
        "description": plan_name,
        "more_info": f"org_id={org_id}",
        "customer": {
            "customer_name": customer_name or "לקוח BrikOps",
            "email": customer_email,
            "phone": customer_phone or "",
        },
        "success_url": f"{frontend}/billing/payment-success",
        "failure_url": f"{frontend}/billing/payment-failure",
        "cancel_url": f"{frontend}/billing/payment-cancel",
        "callback_url": _callback_url(),
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=_auth_headers())
            data = resp.json()
    except Exception as e:
        logger.error("[PAYPLUS] create_payment_page failed for org=%s: %s", org_id, e)
        raise PayPlusError(f"PayPlus API error: {e}")

    if resp.status_code != 200 or not data.get("results", {}).get("status") == "success":
        logger.error("[PAYPLUS] create_payment_page bad response org=%s status=%s body=%s", org_id, resp.status_code, data)
        raise PayPlusError(f"PayPlus error: {data.get('results', {}).get('description', 'Unknown error')}")

    result = data.get("data", {})
    page_request_uid = result.get("page_request_uid", "")
    payment_page_link = result.get("payment_page_link", "")

    if not payment_page_link:
        logger.error("[PAYPLUS] No payment_page_link in response org=%s: %s", org_id, data)
        raise PayPlusError("No payment link returned from PayPlus")

    logger.info("[PAYPLUS] Payment page created for org=%s uid=%s", org_id, page_request_uid)
    return {"page_request_uid": page_request_uid, "payment_page_link": payment_page_link}


async def charge_token(
    token_uid: str,
    amount: float,
    org_id: str,
    plan_name: str,
) -> dict:
    url = f"{_base_url()}/Transactions/ChargeByToken"
    payload = {
        "terminal_uid": PAYPLUS_TERMINAL_UID,
        "token_uid": token_uid,
        "amount": amount,
        "currency_code": "ILS",
        "vat_type": 0,
        "more_info": f"org_id={org_id} plan={plan_name}",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=_auth_headers())
            data = resp.json()
    except Exception as e:
        logger.error("[PAYPLUS] charge_token failed for org=%s: %s", org_id, e)
        raise PayPlusError(f"PayPlus charge error: {e}")

    if resp.status_code != 200:
        logger.error("[PAYPLUS] charge_token bad response org=%s status=%s body=%s", org_id, resp.status_code, data)
        raise PayPlusError(f"PayPlus charge error: {data}")

    transaction = data.get("data", {})
    logger.info("[PAYPLUS] Token charge for org=%s tx=%s status=%s",
                org_id, transaction.get("transaction_uid", ""), transaction.get("status_code", ""))
    return {
        "transaction_uid": transaction.get("transaction_uid", ""),
        "status_code": transaction.get("status_code", ""),
    }


async def get_transaction(transaction_uid: str) -> dict:
    url = f"{_base_url()}/Transactions/{transaction_uid}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=_auth_headers())
            data = resp.json()
    except Exception as e:
        logger.error("[PAYPLUS] get_transaction failed tx=%s: %s", transaction_uid, e)
        raise PayPlusError(f"PayPlus get transaction error: {e}")

    logger.info("[PAYPLUS] get_transaction tx=%s status=%s", transaction_uid, resp.status_code)
    return data


async def refund_transaction(transaction_uid: str, amount: float) -> dict:
    url = f"{_base_url()}/Transactions/RefundByTransactionUID"
    payload = {
        "transaction_uid": transaction_uid,
        "amount": amount,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=_auth_headers())
            data = resp.json()
    except Exception as e:
        logger.error("[PAYPLUS] refund_transaction failed tx=%s: %s", transaction_uid, e)
        raise PayPlusError(f"PayPlus refund error: {e}")

    logger.info("[PAYPLUS] refund tx=%s status=%s", transaction_uid, resp.status_code)
    return data
