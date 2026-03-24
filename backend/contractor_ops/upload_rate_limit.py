import time
import threading
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_upload_counts: dict[str, list[float]] = {}
_lock = threading.Lock()
_request_counter = 0

MAX_UPLOADS_PER_MINUTE = 30
WINDOW_SECONDS = 60
CLEANUP_EVERY_N = 100


def _cleanup_expired(now: float):
    cutoff = now - WINDOW_SECONDS * 2
    expired = [k for k, v in _upload_counts.items() if not v or v[-1] < cutoff]
    for k in expired:
        del _upload_counts[k]


def check_upload_rate_limit(user_id: str):
    global _request_counter
    now = time.monotonic()

    with _lock:
        _request_counter += 1
        if _request_counter % CLEANUP_EVERY_N == 0:
            _cleanup_expired(now)

        timestamps = _upload_counts.get(user_id, [])
        cutoff = now - WINDOW_SECONDS
        timestamps = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= MAX_UPLOADS_PER_MINUTE:
            logger.warning(f"[RATE_LIMIT] upload blocked user={user_id} count={len(timestamps)}/{MAX_UPLOADS_PER_MINUTE}")
            raise HTTPException(
                status_code=429,
                detail="יותר מדי העלאות. נסה שוב בעוד דקה",
            )

        timestamps.append(now)
        _upload_counts[user_id] = timestamps
