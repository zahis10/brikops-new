"""
Shared rate-limit primitives for BrikOps backend.

Currently exposes a single helper used by reminder, notification, and QC
routers to throttle user-triggered WhatsApp template sends on a shared
per-user-per-project budget.

Backed by MongoDB collection `reminder_rate_limits` with TTL index on
`expires_at` and unique compound index on (kind, key) — both created in
reminder_service.ensure_indexes() (wired to FastAPI startup hook).

Extracted from reminder_router.py on 2026-05-17 (HIGH-N1 followup) to
allow notification_router and qc_router to share the same budget.
Original implementation shipped 2026-05-16 in commit d0e2942.
"""
import logging
from datetime import datetime, timezone, timedelta

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from contractor_ops.router import get_db

logger = logging.getLogger(__name__)


async def check_reminder_rate_limit(
    kind: str, key: str, max_requests: int, window_seconds: int
) -> bool:
    """
    Per-user rate limit for manual reminder endpoints.
    Returns True if within limit, False if exceeded.
    Fail-open on infra errors (don't block legitimate users on DB hiccups).
    Added 2026-05-16 from pentest HIGH-N1.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    new_expires = now + timedelta(seconds=window_seconds)
    pipeline = [
        {"$set": {
            "count": {"$cond": {
                "if": {"$lte": [{"$ifNull": ["$expires_at", now - timedelta(seconds=1)]}, now]},
                "then": 1,
                "else": {"$add": [{"$ifNull": ["$count", 0]}, 1]},
            }},
            "expires_at": {"$cond": {
                "if": {"$lte": [{"$ifNull": ["$expires_at", now - timedelta(seconds=1)]}, now]},
                "then": new_expires,
                "else": {"$ifNull": ["$expires_at", new_expires]},
            }},
            "updated_at": now,
        }},
    ]
    for attempt in range(2):
        try:
            result = await db.reminder_rate_limits.find_one_and_update(
                {"kind": kind, "key": key},
                pipeline,
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            return result["count"] <= max_requests
        except DuplicateKeyError:
            if attempt == 0:
                continue
            return False  # fail-closed on persistent race
        except Exception as e:
            logger.warning(f"[REMINDER-RL] Rate limit check failed: {e} — allowing request")
            return True  # fail-open on infra errors
    return False
