"""Tests for Stream C1 — defect lifecycle bell notifications.

8 tests:
  - 4 tests on create_defect_notification (writes per recipient,
    skips actor, rejects unknown type, empty-recipients short-circuit)
  - 1 test on get_defect_recipients_for_close_request (PM + management_team only)
  - 3 tests on body builders (close-request, approve, reject-with-reason)

Async tests use the inline `asyncio.run(run())` pattern matching
test_billing_v1.py:307,336,366 — codebase has no pytest-asyncio plugin
(per BATCH 6A v2 Finding B).
"""
import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, "/home/runner/workspace/backend")

from contractor_ops import notification_helpers


# ---------------------------------------------------------------------------
# create_defect_notification — 4 tests
# ---------------------------------------------------------------------------

def test_create_defect_notification_writes_one_per_recipient():
    async def run():
        db = MagicMock()
        db.qc_notifications.insert_many = AsyncMock()
        await notification_helpers.create_defect_notification(
            db,
            ["user_pm_1", "user_pm_2"],
            notification_type="defect_close_request",
            action="close_request",
            task_id="task_123",
            task_title="בדיקת חשמל",
            project_id="proj_1",
            actor_id="user_contractor_1",
            actor_name="דני קבלן",
            body="דני קבלן ביקש לסגור ליקוי \"בדיקת חשמל\" — ממתין לאישורך",
        )
        db.qc_notifications.insert_many.assert_called_once()
        inserted = db.qc_notifications.insert_many.call_args[0][0]
        assert len(inserted) == 2, f"Expected 2 docs, got {len(inserted)}"
        for doc in inserted:
            assert doc["notification_type"] == "defect_close_request"
            assert doc["action"] == "close_request"
            assert doc["task_id"] == "task_123"
            assert doc["actor_id"] == "user_contractor_1"
            assert doc["read_at"] is None
            assert doc["body"].startswith("דני קבלן ביקש")
            assert "id" in doc
            assert doc["created_at"]
        # Recipients each get exactly one doc, in input order
        assert [d["user_id"] for d in inserted] == ["user_pm_1", "user_pm_2"]
    asyncio.run(run())


def test_create_defect_notification_skips_actor():
    """Actor must never receive their own notification."""
    async def run():
        db = MagicMock()
        db.qc_notifications.insert_many = AsyncMock()
        await notification_helpers.create_defect_notification(
            db,
            ["user_pm_1", "user_actor"],
            notification_type="defect_close_request",
            action="close_request",
            task_id="t1",
            task_title="x",
            project_id="p1",
            actor_id="user_actor",
            actor_name="A",
            body="x",
        )
        inserted = db.qc_notifications.insert_many.call_args[0][0]
        assert len(inserted) == 1, "Actor must be excluded"
        assert inserted[0]["user_id"] == "user_pm_1"
    asyncio.run(run())


def test_create_defect_notification_unknown_type_skipped():
    async def run():
        db = MagicMock()
        db.qc_notifications.insert_many = AsyncMock()
        result = await notification_helpers.create_defect_notification(
            db,
            ["user_pm_1"],
            notification_type="nonsense_type",
            action="x",
            task_id="t1",
            task_title="x",
            project_id="p1",
            actor_id="actor",
            actor_name="A",
            body="x",
        )
        assert result == []
        db.qc_notifications.insert_many.assert_not_called()
    asyncio.run(run())


def test_create_defect_notification_empty_recipients_no_insert():
    async def run():
        db = MagicMock()
        db.qc_notifications.insert_many = AsyncMock()
        await notification_helpers.create_defect_notification(
            db,
            [],
            notification_type="defect_close_request",
            action="close_request",
            task_id="t1",
            task_title="x",
            project_id="p1",
            actor_id="actor",
            actor_name="A",
            body="x",
        )
        db.qc_notifications.insert_many.assert_not_called()
    asyncio.run(run())


# ---------------------------------------------------------------------------
# get_defect_recipients_for_close_request — 1 test
# ---------------------------------------------------------------------------

def test_get_recipients_returns_pm_and_management_team_only():
    """Should return ONLY project_manager + management_team (not contractors,
    not viewers). Owner is org-level not project-level."""
    async def run():
        db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[
            {"user_id": "pm_1"},
            {"user_id": "mgmt_1"},
            {"user_id": "mgmt_2"},
        ])
        db.project_memberships.find = MagicMock(return_value=mock_cursor)
        recipients = await notification_helpers.get_defect_recipients_for_close_request(
            db, "proj_xyz"
        )
        assert recipients == ["pm_1", "mgmt_1", "mgmt_2"]
        # Verify the query filter restricts to PM + management_team only
        call_args = db.project_memberships.find.call_args
        query = call_args[0][0]
        assert query["project_id"] == "proj_xyz"
        assert set(query["role"]["$in"]) == {"project_manager", "management_team"}
    asyncio.run(run())


# ---------------------------------------------------------------------------
# Body builders — 3 tests
# ---------------------------------------------------------------------------

def test_build_close_request_body_format():
    body = notification_helpers.build_close_request_body("דני קבלן", "בדיקת חשמל")
    assert body == "דני קבלן ביקש לסגור ליקוי \"בדיקת חשמל\" — ממתין לאישורך"
    # Defensive: missing fields fall back to Hebrew defaults
    body2 = notification_helpers.build_close_request_body("", "")
    assert "קבלן" in body2 and "ליקוי" in body2


def test_build_status_change_body_approve():
    body = notification_helpers.build_status_change_body("approve", "בדיקת חשמל")
    assert body == "המנהל אישר את התיקון של \"בדיקת חשמל\""
    # No reason concatenated on approve even if passed
    body2 = notification_helpers.build_status_change_body("approve", "x", reason="ignored")
    assert "ignored" not in body2


def test_build_status_change_body_reject_with_reason():
    body = notification_helpers.build_status_change_body(
        "reject", "בדיקת חשמל", reason="לא תוקן כראוי"
    )
    assert body == "המנהל דחה את התיקון של \"בדיקת חשמל\" — לא תוקן כראוי"
    # Reject without reason still works (no trailing em-dash)
    body2 = notification_helpers.build_status_change_body("reject", "x")
    assert body2 == "המנהל דחה את התיקון של \"x\""
    assert not body2.endswith("—")
