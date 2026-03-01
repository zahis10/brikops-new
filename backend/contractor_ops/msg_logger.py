import logging
import time as _time
from typing import Optional

logger = logging.getLogger(__name__)


def log_msg_delivery(
    msg_type: str,
    rid: str,
    channel: str,
    result: str,
    external_ms: float = 0,
    provider_status: str = "",
    error_code: str = "",
    phone_masked: str = "",
    fallback_from: str = "",
):
    parts = [
        f"[MSG-DELIVERY] type={msg_type}",
        f"rid={rid}",
        f"channel={channel}",
        f"result={result}",
        f"external_ms={round(external_ms, 1)}",
    ]
    if provider_status:
        parts.append(f"provider_status={provider_status}")
    if error_code:
        parts.append(f"error_code={error_code}")
    if phone_masked:
        parts.append(f"phone={phone_masked}")
    if fallback_from:
        parts.append(f"fallback_from={fallback_from}")

    line = " ".join(parts)

    if result == "failed":
        logger.error(line)
    elif result == "queued":
        logger.info(line)
    else:
        logger.info(line)


def log_msg_queued(
    msg_type: str,
    rid: str,
    phone_masked: str = "",
):
    log_msg_delivery(
        msg_type=msg_type,
        rid=rid,
        channel="pending",
        result="queued",
        phone_masked=phone_masked,
    )


def mask_phone(phone_e164: str) -> str:
    if len(phone_e164) > 8:
        return phone_e164[:6] + "***" + phone_e164[-2:]
    return phone_e164[:4] + "***"


class DeliveryTimer:
    def __init__(self):
        self._t0 = _time.perf_counter()

    def elapsed_ms(self) -> float:
        return round((_time.perf_counter() - self._t0) * 1000, 1)
