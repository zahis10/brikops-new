"""S7 — Per-(identifier, IP) brute-force lockout for password login endpoints.

Shared helper used by both /api/auth/login (email+password) and
/api/auth/login-phone (phone+password). All callers MUST:

1. Extract client IP from `request` (use `_resolve_client_ip` below).
2. Compute `identifier` (email for /login, phone_e164 for /login-phone).
3. Call `check_lockout(...)` BEFORE attempting auth — raises 401 with
   Retry-After header if currently locked.
4. On ANY auth failure (not-found, wrong-password, no-password-set, etc.),
   call `record_auth_failure_and_raise(...)` instead of raising directly.
   This increments the per-(identifier, ip) counter, sets lockout_until on
   the 5th failure, and raises a generic 401 — same shape as the locked
   response so attackers cannot enumerate accounts via response codes.
5. On success, call `clear_auth_failures(...)` to reset the counter.

Indexes (created in backend/server.py:create_indexes()):
- auth_failed_identifier_ip_unique: compound unique on (identifier, ip)
- auth_failed_ttl: TTL on last_failure, expireAfterSeconds=86400 (24h)
"""
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request

LOCKOUT_THRESHOLD = 5
LOCKOUT_WINDOW_MIN = 15
LOCKOUT_DURATION_MIN = 15
GENERIC_AUTH_FAIL = "Authentication failed"


def _resolve_client_ip(request: Request) -> str:
    """Extract the originating client IP, preferring the leftmost
    X-Forwarded-For value (set by the load balancer / proxy chain).
    Falls back to the immediate socket peer if the header is absent.
    Returns an empty string if neither is available."""
    xff = request.headers.get('x-forwarded-for', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.client.host if request.client else ''


async def check_lockout(db, identifier: str, client_ip: str) -> None:
    """Raise 401 with Retry-After header if the (identifier, ip) tuple is
    currently locked out. Same status code (401) and detail
    ("Authentication failed") as a wrong-password response — only the
    presence of Retry-After differs."""
    now = datetime.now(timezone.utc)
    record = await db.auth_failed_attempts.find_one(
        {"identifier": identifier, "ip": client_ip},
        {"_id": 0, "lockout_until": 1},
    )
    if not record:
        return
    lockout_until = record.get("lockout_until")
    if not lockout_until:
        return
    # MongoDB returns naive datetimes (UTC). Promote to tz-aware to match `now`.
    if lockout_until.tzinfo is None:
        lockout_until = lockout_until.replace(tzinfo=timezone.utc)
    if lockout_until <= now:
        return
    retry_after_seconds = max(1, int((lockout_until - now).total_seconds()))
    raise HTTPException(
        status_code=401,
        detail=GENERIC_AUTH_FAIL,
        headers={"Retry-After": str(retry_after_seconds)},
    )


async def record_auth_failure_and_raise(db, identifier: str, client_ip: str) -> None:
    """Increment the failure counter, set lockout_until if threshold reached,
    then raise generic 401. Idempotent under concurrent failures (MongoDB
    upsert is atomic per-document).

    SLIDING WINDOW: if the existing first_failure is older than
    LOCKOUT_WINDOW_MIN, the counter is reset to 1 and first_failure is
    updated to `now` BEFORE evaluating the threshold. Without this reset,
    an attacker who paces probes slower than the TTL (24h) could drive
    `count` arbitrarily high while keeping first_failure stale outside the
    window — never tripping the lockout condition. Caught by S7 architect
    review 2026-04-27.

    Important: counter is incremented even when the user does not exist.
    Otherwise an attacker can probe registration status by observing which
    identifiers enter lockout vs which never do."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=LOCKOUT_WINDOW_MIN)

    # Step 1: read existing record to decide reset vs increment.
    existing = await db.auth_failed_attempts.find_one(
        {"identifier": identifier, "ip": client_ip},
        {"_id": 0, "first_failure": 1},
    )
    existing_first = existing.get("first_failure") if existing else None
    if existing_first and existing_first.tzinfo is None:
        existing_first = existing_first.replace(tzinfo=timezone.utc)

    if existing_first and existing_first <= window_start:
        # Window expired — restart the counter at 1, clear any stale lockout.
        await db.auth_failed_attempts.update_one(
            {"identifier": identifier, "ip": client_ip},
            {
                "$set": {"count": 1, "first_failure": now, "last_failure": now},
                "$unset": {"lockout_until": ""},
            },
        )
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAIL)

    # Step 2: standard upsert path — increment count, preserve first_failure
    # for new rows via $setOnInsert.
    await db.auth_failed_attempts.update_one(
        {"identifier": identifier, "ip": client_ip},
        {
            "$inc": {"count": 1},
            "$set": {"last_failure": now},
            "$setOnInsert": {"first_failure": now},
        },
        upsert=True,
    )
    record = await db.auth_failed_attempts.find_one(
        {"identifier": identifier, "ip": client_ip},
        {"_id": 0, "count": 1, "first_failure": 1},
    )
    if record and record.get("count", 0) >= LOCKOUT_THRESHOLD:
        first_failure = record.get("first_failure", now)
        # MongoDB returns naive datetimes (UTC). Promote to tz-aware so the
        # comparison with `window_start` (tz-aware UTC) does not raise
        # TypeError: can't compare offset-naive and offset-aware datetimes.
        if first_failure and first_failure.tzinfo is None:
            first_failure = first_failure.replace(tzinfo=timezone.utc)
        if first_failure and first_failure > window_start:
            await db.auth_failed_attempts.update_one(
                {"identifier": identifier, "ip": client_ip},
                {"$set": {"lockout_until": now + timedelta(minutes=LOCKOUT_DURATION_MIN)}},
            )
    raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAIL)


async def clear_auth_failures(db, identifier: str, client_ip: str) -> None:
    """Delete the failure record on successful authentication.
    Scoped to the IP that succeeded — does not unlock other IPs that may
    also be attacking this identifier (those will still hit lockout)."""
    await db.auth_failed_attempts.delete_one(
        {"identifier": identifier, "ip": client_ip}
    )
