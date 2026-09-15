"""Hourly presence history and platform activity aggregations.

Presence is intentionally kept separate from ``users.last_seen_at``.  The
latter remains the inexpensive, throttled recency stamp used by the existing
activity score; this module stores one upserted document for each user's UTC
hour so admin views can present activity in Israel time.
"""

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

IL_TZ = ZoneInfo("Asia/Jerusalem")
UTC = timezone.utc
RETENTION_DAYS = 90


def _as_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime, treating naive values as UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def hour_key(dt_utc: datetime) -> str:
    """Return the canonical UTC hour bucket key for ``dt_utc``."""
    return _as_utc(dt_utc).strftime("%Y-%m-%dT%H")


def _parse_iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _as_utc(value)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return _as_utc(parsed)


def should_stamp(last_seen_iso: str | None, now: datetime) -> bool:
    """Whether a throttled presence request should write a new stamp.

    A request starts a new history bucket even when the ten-minute
    ``last_seen_at`` throttle has not elapsed.  Invalid old data is treated as
    stale rather than allowing it to suppress presence history.
    """
    if not last_seen_iso:
        return True
    try:
        seen = _parse_iso(last_seen_iso)
    except (TypeError, ValueError, OverflowError):
        return True
    current = _as_utc(now)
    if hour_key(seen) != hour_key(current):
        return True
    return current - seen > timedelta(minutes=10)


async def record_presence(db, user_id: str, now: datetime) -> None:
    """Best-effort upsert of a user's current UTC-hour presence bucket."""
    try:
        current = _as_utc(now)
        bucket = hour_key(current)
        hour_start = current.replace(minute=0, second=0, microsecond=0)
        iso_now = current.isoformat()
        await db.user_activity_hours.update_one(
            {"user_id": user_id, "hour_utc": bucket},
            {
                "$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "hour_utc": bucket,
                    "first_seen_at": iso_now,
                    "expires_at": hour_start + timedelta(days=RETENTION_DAYS),
                },
                "$set": {"last_seen_at": iso_now},
                "$inc": {"hits": 1},
            },
            upsert=True,
        )
    except Exception:
        # Presence must never delay or fail an authenticated request.
        logger.debug("Could not record hourly presence for user %s", user_id, exc_info=True)


def _il_date_bounds(days: int, now: datetime) -> tuple[date, date, str]:
    current_il = _as_utc(now).astimezone(IL_TZ)
    today = current_il.date()
    start = today - timedelta(days=max(1, days) - 1)
    local_midnight = datetime.combine(start, time.min, tzinfo=IL_TZ)
    return start, today, hour_key(local_midnight.astimezone(UTC))


def _parse_bucket(value: Any) -> datetime | None:
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%dT%H")
        return parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError, OverflowError):
        return None


async def hours_by_user(
    db, user_ids: list, days: int, now: datetime
) -> dict:
    """Map users to distinct active Israel hours for the inclusive date range."""
    ids = list(dict.fromkeys(uid for uid in user_ids if uid))
    result = {uid: {} for uid in ids}
    if not ids:
        return result

    start_date, today, from_key = _il_date_bounds(days, now)
    cursor = db.user_activity_hours.find(
        {"user_id": {"$in": ids}, "hour_utc": {"$gte": from_key}},
        {"_id": 0, "user_id": 1, "hour_utc": 1},
    )
    buckets: dict[str, dict[str, set[int]]] = {
        uid: {} for uid in ids
    }
    for row in await cursor.to_list(None):
        uid = row.get("user_id")
        if uid not in buckets:
            continue
        bucket_dt = _parse_bucket(row.get("hour_utc"))
        if bucket_dt is None:
            continue
        local = bucket_dt.astimezone(IL_TZ)
        local_date = local.date()
        if not start_date <= local_date <= today:
            continue
        day = local_date.isoformat()
        buckets[uid].setdefault(day, set()).add(local.hour)

    for uid, days_map in buckets.items():
        result[uid] = {
            day: sorted(hours)
            for day, hours in sorted(days_map.items())
        }
    return result


def _eligible_user_query() -> dict:
    return {
        "is_demo": {"$ne": True},
        "platform_role": {"$ne": "super_admin"},
    }


async def _eligible_users(db, org_id: str | None = None) -> list[dict]:
    """Fetch customer users, optionally restricted to an organization."""
    user_query = _eligible_user_query()
    member_ids: set[str] | None = None
    if org_id:
        memberships = await db.organization_memberships.find(
            {"org_id": org_id},
            {"_id": 0, "user_id": 1},
        ).to_list(None)
        member_ids = {
            row.get("user_id") for row in memberships if row.get("user_id")
        }
        if not member_ids:
            return []
        user_query["id"] = {"$in": list(member_ids)}

    users = await db.users.find(
        user_query,
        {
            "_id": 0,
            "id": 1,
            "name": 1,
            "role": 1,
            "is_demo": 1,
            "platform_role": 1,
            "last_seen_at": 1,
            "org_id": 1,
            "org_name": 1,
        },
    ).to_list(None)
    # Keep the Python check as a guard for lightweight test doubles and old
    # Mongo-compatible stores that do not implement $ne exactly.
    return [
        user for user in users
        if user.get("is_demo") is not True
        and user.get("platform_role") != "super_admin"
        and (member_ids is None or user.get("id") in member_ids)
    ]


async def platform_heatmap(
    db, days: int, now: datetime, org_id: str | None
) -> dict:
    """Aggregate distinct eligible users by Israel date and hour."""
    start_date, today, from_key = _il_date_bounds(days, now)
    eligible = await _eligible_users(db, org_id)
    eligible_ids = {user.get("id") for user in eligible if user.get("id")}

    distinct: dict[tuple[date, int], set[str]] = {}
    if eligible_ids:
        cursor = db.user_activity_hours.find(
            {
                "user_id": {"$in": list(eligible_ids)},
                "hour_utc": {"$gte": from_key},
            },
            {"_id": 0, "user_id": 1, "hour_utc": 1},
        )
        for row in await cursor.to_list(None):
            uid = row.get("user_id")
            if uid not in eligible_ids:
                continue
            bucket_dt = _parse_bucket(row.get("hour_utc"))
            if bucket_dt is None:
                continue
            local = bucket_dt.astimezone(IL_TZ)
            local_date = local.date()
            if not start_date <= local_date <= today:
                continue
            distinct.setdefault((local_date, local.hour), set()).add(uid)

    day_rows = []
    hour_totals = [0] * 24
    max_users = 0
    peak = None
    for offset in range(max(1, days)):
        day = today - timedelta(days=offset)
        hours = [
            len(distinct.get((day, hour), set()))
            for hour in range(24)
        ]
        day_max = max(hours, default=0)
        max_users = max(max_users, day_max)
        for hour, count in enumerate(hours):
            hour_totals[hour] += count
            if count > (peak["users"] if peak else 0):
                peak = {
                    "date": day.isoformat(),
                    "hour": hour,
                    "users": count,
                }
        day_rows.append(
            {
                "date": day.isoformat(),
                "weekday": (day.weekday() + 1) % 7,
                "hours": hours,
                "distinct_users": len(
                    set().union(
                        *(
                            distinct.get((day, hour), set())
                            for hour in range(24)
                        )
                    )
                ),
            }
        )

    return {
        "tz": "Asia/Jerusalem",
        "days": day_rows,
        "hour_totals": hour_totals,
        "peak": peak,
        "max": max_users,
    }


def _user_seen_at(user: dict) -> datetime | None:
    try:
        return _parse_iso(user.get("last_seen_at"))
    except (TypeError, ValueError, OverflowError):
        return None


async def _organization_details(db, user_ids: list[str]) -> tuple[dict, dict]:
    if not user_ids:
        return {}, {}
    memberships = await db.organization_memberships.find(
        {"user_id": {"$in": user_ids}},
        {"_id": 0, "user_id": 1, "org_id": 1},
    ).to_list(None)
    user_orgs: dict[str, str] = {}
    org_ids = set()
    for membership in memberships:
        uid = membership.get("user_id")
        oid = membership.get("org_id")
        if uid in user_ids and oid and uid not in user_orgs:
            user_orgs[uid] = oid
            org_ids.add(oid)
    org_docs = await db.organizations.find(
        {"id": {"$in": list(org_ids)}},
        {"_id": 0, "id": 1, "name": 1},
    ).to_list(None) if org_ids else []
    org_names = {org.get("id"): org.get("name", "") for org in org_docs}
    return user_orgs, org_names


async def active_now(db, minutes: int, now: datetime) -> dict:
    """Return customer users seen recently, with a 200-row response cap.

    ``users.last_seen_at`` is throttled to ten minutes, so a "15 minutes"
    active window is accurate to within that throttle.
    """
    current = _as_utc(now)
    threshold = current - timedelta(minutes=minutes)
    cursor = db.users.find(
        {
            **_eligible_user_query(),
            "last_seen_at": {"$gte": threshold.isoformat()},
        },
        {
            "_id": 0,
            "id": 1,
            "name": 1,
            "role": 1,
            "last_seen_at": 1,
            "org_id": 1,
            "org_name": 1,
            "is_demo": 1,
            "platform_role": 1,
        },
    )
    users = []
    for user in await cursor.to_list(None):
        if user.get("is_demo") is True or user.get("platform_role") == "super_admin":
            continue
        seen = _user_seen_at(user)
        if seen is not None and seen >= threshold:
            users.append((seen, user))
    users.sort(key=lambda item: item[0], reverse=True)
    total_count = len(users)
    visible_users = users[:200]
    user_ids = [user.get("id") for _, user in visible_users if user.get("id")]
    user_orgs, org_names = await _organization_details(db, user_ids)

    response_users = []
    for _, user in visible_users:
        uid = user.get("id")
        org_id = user_orgs.get(uid, user.get("org_id"))
        org_name = org_names.get(org_id, user.get("org_name", ""))
        response_users.append(
            {
                "user_id": uid,
                "name": user.get("name", ""),
                "role": user.get("role", ""),
                "org_id": org_id,
                "org_name": org_name,
                "last_seen_at": user.get("last_seen_at"),
            }
        )
    return {
        "minutes": minutes,
        "count": total_count,
        "users": response_users,
    }


async def ensure_indexes(db) -> None:
    """Create hourly-history indexes without making startup fail."""
    try:
        await db.user_activity_hours.create_index(
            [("user_id", 1), ("hour_utc", 1)],
            unique=True,
            name="uniq_user_hour",
        )
        await db.user_activity_hours.create_index(
            [("hour_utc", 1), ("user_id", 1)],
            name="hour_user",
        )
        await db.user_activity_hours.create_index(
            "expires_at",
            expireAfterSeconds=0,
            name="ttl_expires_at",
        )
    except Exception:
        logger.exception("Failed to create user_activity_hours indexes (non-fatal)")