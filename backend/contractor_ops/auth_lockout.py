"""Per-(identifier, IP) brute-force lockout for password login endpoints."""
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request

LOCKOUT_THRESHOLD = 5
LOCKOUT_WINDOW_MIN = 15
LOCKOUT_DURATION_MIN = 15
GENERIC_AUTH_FAIL = "Authentication failed"


def _resolve_client_ip(request: Request) -> str:
    xff = request.headers.get('x-forwarded-for', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.client.host if request.client else ''


async def check_lockout(db, identifier: str, client_ip: str) -> None:
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
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=LOCKOUT_WINDOW_MIN)

    existing = await db.auth_failed_attempts.find_one(
        {"identifier": identifier, "ip": client_ip},
        {"_id": 0, "first_failure": 1},
    )
    existing_first = existing.get("first_failure") if existing else None
    if existing_first and existing_first.tzinfo is None:
        existing_first = existing_first.replace(tzinfo=timezone.utc)

    if existing_first and existing_first <= window_start:
        await db.auth_failed_attempts.update_one(
            {"identifier": identifier, "ip": client_ip},
            {
                "$set": {"count": 1, "first_failure": now, "last_failure": now},
                "$unset": {"lockout_until": ""},
            },
        )
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAIL)

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
        if first_failure and first_failure.tzinfo is None:
            first_failure = first_failure.replace(tzinfo=timezone.utc)
        if first_failure and first_failure > window_start:
            await db.auth_failed_attempts.update_one(
                {"identifier": identifier, "ip": client_ip},
                {"$set": {"lockout_until": now + timedelta(minutes=LOCKOUT_DURATION_MIN)}},
            )
    raise HTTPException(status_code=401, detail=GENERIC_AUTH_FAIL)


async def clear_auth_failures(db, identifier: str, client_ip: str) -> None:
    await db.auth_failed_attempts.delete_one(
        {"identifier": identifier, "ip": client_ip}
    )
