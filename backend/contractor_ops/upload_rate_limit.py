import os
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

# BATCH upload-abuse-hardening (2026-05-22) — byte-based rate limit.
# The count limit (30/min) treats a 1KB file and a 50MB file alike;
# this caps the actual VOLUME a single user can push per minute.
# Env-overridable so it can be tuned without a deploy.
MAX_UPLOAD_MB_PER_MINUTE = int(os.environ.get('MAX_UPLOAD_MB_PER_MINUTE', '500'))
MAX_UPLOAD_BYTES_PER_MINUTE = MAX_UPLOAD_MB_PER_MINUTE * 1024 * 1024

# per-user list of (timestamp, bytes) within the rolling window
_upload_bytes: dict[str, list[tuple[float, int]]] = {}


def _cleanup_expired(now: float):
    cutoff = now - WINDOW_SECONDS * 2
    expired = [k for k, v in _upload_counts.items() if not v or v[-1] < cutoff]
    for k in expired:
        del _upload_counts[k]
    # BATCH upload-abuse-hardening — prune the byte ledger too
    b_expired = [k for k, v in _upload_bytes.items()
                 if not v or v[-1][0] < cutoff]
    for k in b_expired:
        del _upload_bytes[k]


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


def check_upload_bytes(user_id: str, incoming_bytes: int):
    """BATCH upload-abuse-hardening (2026-05-22).
    Call this AFTER the uploaded file size is known. Rejects (429)
    when this user's uploaded volume in the rolling 60s window
    would exceed MAX_UPLOAD_BYTES_PER_MINUTE. Uses the REAL byte
    count, not the (spoofable) Content-Length header."""
    now = time.monotonic()
    with _lock:
        entries = _upload_bytes.get(user_id, [])
        cutoff = now - WINDOW_SECONDS
        entries = [(t, n) for (t, n) in entries if t > cutoff]
        window_total = sum(n for (_, n) in entries)
        if window_total + incoming_bytes > MAX_UPLOAD_BYTES_PER_MINUTE:
            logger.warning(
                f"[RATE_LIMIT] upload byte-limit blocked user={user_id} "
                f"window={window_total} incoming={incoming_bytes} "
                f"limit={MAX_UPLOAD_BYTES_PER_MINUTE}"
            )
            raise HTTPException(
                status_code=429,
                detail="העלאת נתח גדול מדי בזמן קצר. נסה שוב בעוד דקה",
            )
        entries.append((now, incoming_bytes))
        _upload_bytes[user_id] = entries


def check_content_length(content_length_header, max_bytes: int):
    """BATCH upload-abuse-hardening (2026-05-22).
    Fast-path reject (413) when the request advertises a body larger
    than max_bytes — avoids buffering an oversized upload. The
    header is advisory/spoofable, so this is an optimisation only;
    the real enforcement stays the post-read size check."""
    if not content_length_header:
        return
    try:
        declared = int(content_length_header)
    except (TypeError, ValueError):
        return
    if declared > max_bytes:
        raise HTTPException(
            status_code=413,
            detail="קובץ גדול מדי (מקסימום 50MB)",
        )
