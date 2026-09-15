import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from contractor_ops import activity_hours
from contractor_ops import router as ops_router


UTC = timezone.utc


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return list(self.rows)


class Collection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.update_one = AsyncMock()
        self.create_index = AsyncMock(return_value="index")
        self.last_query = None

    def find(self, *args, **_kwargs):
        self.last_query = args
        return Cursor(self.rows)


class AggregateCollection(Collection):
    def aggregate(self, *_args, **_kwargs):
        return Cursor([])


class PresenceCollection:
    def __init__(self):
        self.docs = {}

    async def update_one(self, query, update, **_kwargs):
        key = (query["user_id"], query["hour_utc"])
        doc = self.docs.setdefault(key, dict(update["$setOnInsert"]))
        doc.update(update.get("$set", {}))
        for field, increment in update.get("$inc", {}).items():
            doc[field] = doc.get(field, 0) + increment


def test_should_stamp_throttling_and_malformed_values():
    now = datetime(2026, 9, 10, 12, 30, tzinfo=UTC)
    assert activity_hours.should_stamp(None, now) is True
    assert activity_hours.should_stamp((now - timedelta(minutes=5)).isoformat(), now) is False
    assert activity_hours.should_stamp(
        (now - timedelta(minutes=5)).replace(hour=11).isoformat(), now
    ) is True
    assert activity_hours.should_stamp(
        (now - timedelta(minutes=11)).isoformat(), now
    ) is True
    assert activity_hours.should_stamp("not-a-timestamp", now) is True


def test_record_presence_upserts_same_hour_and_swallows_write_failure():
    async def run():
        db = MagicMock()
        db.user_activity_hours = PresenceCollection()
        now = datetime(2026, 9, 10, 11, 20, tzinfo=UTC)
        await activity_hours.record_presence(db, "user-1", now)
        await activity_hours.record_presence(db, "user-1", now + timedelta(minutes=5))
        assert len(db.user_activity_hours.docs) == 1
        doc = db.user_activity_hours.docs[("user-1", "2026-09-10T11")]
        assert doc["first_seen_at"] == now.isoformat()
        assert doc["last_seen_at"] == (now + timedelta(minutes=5)).isoformat()
        assert doc["hits"] == 2
        assert doc["expires_at"] == datetime(
            2026, 12, 9, 11, tzinfo=UTC
        )
        await activity_hours.record_presence(
            db, "user-1", datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
        )
        assert len(db.user_activity_hours.docs) == 2
        assert ("user-1", "2026-09-10T12") in db.user_activity_hours.docs

        db.user_activity_hours.update_one = AsyncMock(
            side_effect=RuntimeError("database unavailable")
        )
        await activity_hours.record_presence(db, "user-1", now)

    asyncio.run(run())


def test_hours_by_user_uses_inclusive_israel_date_bounds():
    async def run():
        db = MagicMock()
        db.user_activity_hours = Collection(
            [
                {"user_id": "u1", "hour_utc": "2026-09-10T11"},
                {"user_id": "u1", "hour_utc": "2026-09-10T12"},
                {"user_id": "u1", "hour_utc": "2026-09-02T11"},
            ]
        )
        result = await activity_hours.hours_by_user(
            db,
            ["u1"],
            7,
            datetime(2026, 9, 10, 12, tzinfo=UTC),
        )
        assert result == {"u1": {"2026-09-10": [14, 15]}}
        assert db.user_activity_hours.last_query[0]["hour_utc"]["$gte"] == "2026-09-03T21"

    asyncio.run(run())


def test_platform_heatmap_deduplicates_dst_buckets_and_excludes_ineligible_users():
    async def run():
        db = MagicMock()
        db.users = Collection(
            [
                {"id": "customer", "name": "Customer", "role": "contractor"},
                {"id": "demo", "is_demo": True},
                {"id": "admin", "platform_role": "super_admin"},
            ]
        )
        db.organization_memberships = Collection(
            [{"org_id": "org-1", "user_id": "customer"}]
        )
        db.user_activity_hours = Collection(
            [
                # Both UTC buckets are 01:00 on the Israel DST fallback day.
                {"user_id": "customer", "hour_utc": "2026-10-24T22"},
                {"user_id": "customer", "hour_utc": "2026-10-24T23"},
                {"user_id": "demo", "hour_utc": "2026-10-24T22"},
                {"user_id": "admin", "hour_utc": "2026-10-24T22"},
            ]
        )
        result = await activity_hours.platform_heatmap(
            db,
            7,
            datetime(2026, 10, 25, 12, tzinfo=UTC),
            "org-1",
        )
        day = next(row for row in result["days"] if row["date"] == "2026-10-25")
        assert day["hours"][1] == 1
        assert day["distinct_users"] == 1
        assert result["peak"] == {"date": "2026-10-25", "hour": 1, "users": 1}
        assert result["max"] == 1
        assert result["tz"] == "Asia/Jerusalem"

    asyncio.run(run())


def test_active_now_filters_sorts_and_reports_total_above_response_cap():
    async def run():
        now = datetime(2026, 9, 10, 12, tzinfo=UTC)
        rows = [
            {
                "id": "new",
                "name": "New",
                "role": "contractor",
                "last_seen_at": (now - timedelta(minutes=5)).isoformat(),
                "org_id": "org-1",
            },
            {
                "id": "old",
                "name": "Old",
                "role": "contractor",
                "last_seen_at": (now - timedelta(minutes=30)).isoformat(),
            },
            {
                "id": "demo",
                "is_demo": True,
                "last_seen_at": (now - timedelta(minutes=2)).isoformat(),
            },
        ]
        rows.extend(
            {
                "id": f"user-{idx}",
                "role": "contractor",
                "last_seen_at": (now - timedelta(minutes=idx % 10)).isoformat(),
            }
            for idx in range(205)
        )
        db = MagicMock()
        db.users = Collection(rows)
        db.organization_memberships = Collection(
            [{"user_id": "new", "org_id": "org-1"}]
        )
        db.organizations = Collection([{"id": "org-1", "name": "Org 1"}])
        result = await activity_hours.active_now(db, 15, now)
        assert result["minutes"] == 15
        assert result["count"] == 206
        assert len(result["users"]) == 200
        assert result["users"][0]["user_id"] == "user-0"
        new = next(user for user in result["users"] if user["user_id"] == "new")
        assert new["org_name"] == "Org 1"

    asyncio.run(run())


def test_activity_indexes_are_best_effort_and_named():
    async def run():
        db = MagicMock()
        db.user_activity_hours.create_index = AsyncMock(
            side_effect=[RuntimeError("index unavailable")]
        )
        await activity_hours.ensure_indexes(db)
        assert db.user_activity_hours.create_index.await_count == 1

    asyncio.run(run())


def test_activity_indexes_successfully_create_unique_lookup_and_ttl_indexes():
    async def run():
        db = MagicMock()
        db.user_activity_hours.create_index = AsyncMock(
            side_effect=["uniq_user_hour", "hour_user", "ttl_expires_at"]
        )

        await activity_hours.ensure_indexes(db)

        calls = db.user_activity_hours.create_index.await_args_list
        assert len(calls) == 3
        assert calls[0].args == ([("user_id", 1), ("hour_utc", 1)],)
        assert calls[0].kwargs == {"unique": True, "name": "uniq_user_hour"}
        assert calls[1].args == ([("hour_utc", 1), ("user_id", 1)],)
        assert calls[1].kwargs == {"name": "hour_user"}
        assert calls[2].args == ("expires_at",)
        assert calls[2].kwargs == {
            "expireAfterSeconds": 0,
            "name": "ttl_expires_at",
        }

    asyncio.run(run())


def test_admin_activity_api_enforces_role_and_parameter_contract(monkeypatch):
    import server
    from contractor_ops import admin_activity_router

    monkeypatch.setattr(server, "_check_rate_limit_global", AsyncMock(return_value=True))
    monkeypatch.setattr(
        admin_activity_router,
        "active_now",
        AsyncMock(return_value={"minutes": 15, "count": 0, "users": []}),
    )
    monkeypatch.setattr(
        admin_activity_router,
        "platform_heatmap",
        AsyncMock(
            return_value={
                "tz": "Asia/Jerusalem",
                "days": [],
                "hour_totals": [0] * 24,
                "peak": None,
                "max": 0,
            }
        ),
    )

    async def contractor_user():
        return {"id": "contractor", "platform_role": "none"}

    async def super_admin_user():
        return {"id": "admin", "platform_role": "super_admin"}

    client = TestClient(server.app, raise_server_exceptions=False)
    server.app.dependency_overrides[server.get_current_user] = contractor_user
    try:
        assert client.get("/api/admin/analytics/active-now").status_code == 403
        assert client.get("/api/admin/analytics/hourly").status_code == 403

        server.app.dependency_overrides[server.get_current_user] = super_admin_user
        active = client.get("/api/admin/analytics/active-now")
        hourly = client.get("/api/admin/analytics/hourly")
        assert active.status_code == 200
        assert hourly.status_code == 200
        assert {"minutes", "count", "users", "generated_at", "today"} <= active.json().keys()
        assert {
            "tz", "days", "hour_totals", "peak", "max", "generated_at", "today"
        } <= hourly.json().keys()

        assert client.get(
            "/api/admin/analytics/active-now", params={"minutes": 3}
        ).status_code == 422
        assert client.get(
            "/api/admin/analytics/hourly", params={"days": 14}
        ).status_code == 422
    finally:
        server.app.dependency_overrides.pop(server.get_current_user, None)


def test_admin_activity_api_without_token_returns_401_from_real_dependency(monkeypatch):
    import server

    monkeypatch.setattr(server, "_check_rate_limit_global", AsyncMock(return_value=True))
    server.app.dependency_overrides.pop(server.get_current_user, None)

    client = TestClient(server.app, raise_server_exceptions=False)
    response = client.get("/api/admin/analytics/active-now")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_user_activity_api_returns_hours_today_and_empty_shape(monkeypatch):
    import server
    from contractor_ops import admin_analytics

    fixed_now = datetime(2026, 9, 10, 12, 30, tzinfo=UTC)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    db = MagicMock()
    db.organizations = Collection([{"id": "org-1", "name": "Org 1"}])
    db.users = Collection(
        [
            {
                "id": "user-1",
                "name": "User One",
                "role": "contractor",
                "last_seen_at": fixed_now.isoformat(),
                "last_login_at": fixed_now.isoformat(),
                "login_count": 3,
            }
        ]
    )
    db.organization_memberships = Collection(
        [{"user_id": "user-1", "org_id": "org-1"}]
    )
    db.user_activity_hours = Collection(
        [
            {"user_id": "user-1", "hour_utc": "2026-09-10T12"},
            {"user_id": "user-1", "hour_utc": "2026-09-09T12"},
        ]
    )
    for collection_name in (
        "tasks",
        "task_status_history",
        "qc_items",
        "handover_protocols",
        "task_updates",
        "notification_jobs",
    ):
        setattr(db, collection_name, AggregateCollection())

    async def super_admin_user():
        return {"id": "admin", "platform_role": "super_admin"}

    monkeypatch.setattr(server, "_check_rate_limit_global", AsyncMock(return_value=True))
    monkeypatch.setattr(admin_analytics, "get_db", lambda: db)
    monkeypatch.setattr(admin_analytics, "datetime", FixedDateTime)
    server.app.dependency_overrides[server.get_current_user] = super_admin_user

    client = TestClient(server.app, raise_server_exceptions=False)
    try:
        response = client.get("/api/admin/analytics/user-activity")
        assert response.status_code == 200
        payload = response.json()
        assert payload["today"] == "2026-09-10"
        assert payload["tz"] == "Asia/Jerusalem"
        assert payload["total_count"] == 1
        row = payload["users"][0]
        assert row["hours"] == {
            "2026-09-09": [15],
            "2026-09-10": [15],
        }
        assert row["hours_today"] == [15]

        db.users.rows = []
        db.organizations.rows = []
        db.organization_memberships.rows = []
        empty_response = client.get("/api/admin/analytics/user-activity")
        assert empty_response.status_code == 200
        assert empty_response.json() == {
            "users": [],
            "total_count": 0,
            "page": 1,
            "limit": 50,
            "orgs": [],
            "today": "2026-09-10",
            "tz": "Asia/Jerusalem",
        }
    finally:
        server.app.dependency_overrides.pop(server.get_current_user, None)


def test_malformed_presence_stamp_is_best_effort_through_current_user(monkeypatch):
    async def run():
        db = MagicMock()
        db.users.find_one = AsyncMock(
            return_value={
                "id": "user-1",
                "role": "contractor",
                "user_status": "active",
                "session_version": 0,
                "last_seen_at": "garbage",
            }
        )
        db.users.update_one = AsyncMock()
        record = AsyncMock()
        monkeypatch.setattr(ops_router, "get_db", lambda: db)
        monkeypatch.setattr(ops_router, "record_presence", record)

        token = ops_router._create_token("user-1", "contractor")
        credentials = type("Credentials", (), {"credentials": token})()
        user = await ops_router.get_current_user(credentials)
        assert user["last_seen_at"].endswith("+00:00")
        db.users.update_one.assert_awaited_once()
        record.assert_awaited_once()

    asyncio.run(run())