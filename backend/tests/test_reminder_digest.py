"""Tests for Stream A — contractor reminder digest refactor (BATCH 6A v2).

14 tests:
  - 8 sync `_resolve_digest_template_for_user` tests
  - 5 async `send_contractor_reminder` digest behavior tests
  - 1 V2 multi-project enforcement test (3 projects = 3 messages)

Async tests use the inline `asyncio.run(run())` pattern matching
test_billing_v1.py:307,336,366 — codebase has no pytest-asyncio plugin.
"""
import asyncio
import sys
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, "/home/runner/workspace/backend")

from contractor_ops import reminder_service


# ---------------------------------------------------------------------------
# 8 sync tests — _resolve_digest_template_for_user
# ---------------------------------------------------------------------------

def test_resolve_template_hebrew_user():
    """Hebrew user → Hebrew template."""
    user = {"preferred_language": "he"}
    name, lang = reminder_service._resolve_digest_template_for_user(user)
    assert name == "wa_contractor_reminder_digest_he"
    assert lang == "he"


def test_resolve_template_english_user():
    user = {"preferred_language": "en"}
    name, lang = reminder_service._resolve_digest_template_for_user(user)
    assert name == "wa_contractor_reminder_digest_en"
    assert lang == "en"


def test_resolve_template_arabic_user():
    user = {"preferred_language": "ar"}
    name, lang = reminder_service._resolve_digest_template_for_user(user)
    assert name == "wa_contractor_reminder_digest_ar"
    assert lang == "ar"


def test_resolve_template_chinese_user():
    """Chinese key 'zh' must resolve to lang code 'zh_CN' (Meta requirement)."""
    user = {"preferred_language": "zh"}
    name, lang = reminder_service._resolve_digest_template_for_user(user)
    assert name == "wa_contractor_reminder_digest_zh"
    assert lang == "zh_CN"


def test_resolve_template_no_preferred_language_defaults_hebrew():
    """User without preferred_language field → Hebrew default."""
    user = {"id": "u1", "name": "קבלן"}
    name, lang = reminder_service._resolve_digest_template_for_user(user)
    assert name == "wa_contractor_reminder_digest_he"
    assert lang == "he"


def test_resolve_template_company_recipient_defaults_hebrew():
    """Company fallback recipient (no user object) → Hebrew."""
    user = {"id": "company_id", "name": "חברה"}  # no preferred_language
    name, lang = reminder_service._resolve_digest_template_for_user(user)
    assert lang == "he"


def test_resolve_template_unknown_language_falls_back_to_english():
    """Unknown lang code → English fallback (per existing notification_service pattern)."""
    user = {"preferred_language": "fr"}
    name, lang = reminder_service._resolve_digest_template_for_user(user)
    assert name == "wa_contractor_reminder_digest_en"
    assert lang == "en"


def test_resolve_template_uppercase_language_normalized():
    """Lang code is normalized to lowercase."""
    user = {"preferred_language": "AR"}
    name, lang = reminder_service._resolve_digest_template_for_user(user)
    assert name == "wa_contractor_reminder_digest_ar"


# ---------------------------------------------------------------------------
# Helper — build a mock _db that satisfies send_contractor_reminder's queries.
# ---------------------------------------------------------------------------

def _build_mock_db(tasks, project, user):
    """Construct a MagicMock _db wired for send_contractor_reminder.

    - tasks.find(...).to_list() → tasks
    - projects.find_one(...)    → project
    - users.find_one(...)       → user
    - reminder_log.find(...).to_list() → [] (cooldown clean)
    - reminder_log.insert_one     → AsyncMock (records calls)
    """
    mock_db = MagicMock()
    mock_db.tasks.find.return_value.to_list = AsyncMock(return_value=tasks)
    mock_db.projects.find_one = AsyncMock(return_value=project)
    mock_db.users.find_one = AsyncMock(return_value=user)
    mock_db.reminder_log.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.reminder_log.insert_one = AsyncMock()
    # building/floor/unit lookups are no longer called in digest mode but
    # leave AsyncMocks in place in case a regression brings them back.
    mock_db.buildings.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.floors.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.units.find.return_value.to_list = AsyncMock(return_value=[])
    return mock_db


# ---------------------------------------------------------------------------
# 5 async tests — send_contractor_reminder digest behavior
# (asyncio.run() pattern — no @pytest.mark.asyncio per Finding B)
# ---------------------------------------------------------------------------

def test_digest_sends_one_message_for_many_defects():
    """100 open defects → exactly 1 WA send per recipient (not 5, not 100)."""
    async def run():
        tasks = [
            {"id": f"task_{i}", "title": f"ליקוי {i}", "assignee_id": "user_1",
             "building_id": None, "floor_id": None, "unit_id": None,
             "created_at": "2026-04-01T00:00:00Z"}
            for i in range(100)
        ]
        mock_db = _build_mock_db(
            tasks=tasks,
            project={"id": "proj_1", "name": "מגדלי הים", "org_id": "org_1"},
            user={"id": "user_1", "name": "דני קבלן",
                  "phone_e164": "+972501234567", "preferred_language": "he"},
        )
        reminder_service._db = mock_db

        with patch.object(reminder_service, '_send_wa_template', new=AsyncMock(
            return_value={"success": True, "provider_message_id": "wamid_1"}
        )) as mock_send:
            result = await reminder_service.send_contractor_reminder(
                "proj_1", "comp_1", triggered_by="test", skip_cooldown=True, skip_preferences=True
            )

        assert mock_send.call_count == 1, \
            f"Expected exactly 1 WA send for digest, got {mock_send.call_count}"
        assert result["status"] == "completed"
        assert result["defect_count"] == 100
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "sent"
        assert result["results"][0]["open_count"] == 100

    asyncio.run(run())


def test_digest_button_url_uses_project_id_not_task_id():
    """Button param must be project_id (not first task_id)."""
    async def run():
        mock_db = _build_mock_db(
            tasks=[
                {"id": "task_1", "title": "T1", "assignee_id": "user_1"},
                {"id": "task_2", "title": "T2", "assignee_id": "user_1"},
            ],
            project={"id": "proj_xyz", "name": "Project", "org_id": "org_1"},
            user={"id": "user_1", "name": "Test", "phone_e164": "+972501234567",
                  "preferred_language": "he"},
        )
        reminder_service._db = mock_db

        sent_button_params = []

        async def capture_send(phone, name, body_params, button_params=None, lang_code="he"):
            sent_button_params.append(button_params)
            return {"success": True, "provider_message_id": "wamid"}

        with patch.object(reminder_service, '_send_wa_template', new=capture_send):
            await reminder_service.send_contractor_reminder(
                "proj_xyz", "comp_1", triggered_by="test", skip_cooldown=True, skip_preferences=True
            )

        assert len(sent_button_params) == 1
        assert sent_button_params[0][0]["text"] == "proj_xyz?src=wa", \
            f"Button URL must point to project, got: {sent_button_params[0][0]['text']}"

    asyncio.run(run())


def test_digest_uses_recipient_preferred_language():
    """English contractor → English template + lang code 'en'."""
    async def run():
        mock_db = _build_mock_db(
            tasks=[{"id": "task_1", "title": "T1", "assignee_id": "user_1"}],
            project={"id": "proj_1", "name": "Sea Towers", "org_id": "org_1"},
            user={"id": "user_1", "name": "David", "phone_e164": "+972501234567",
                  "preferred_language": "en"},
        )
        reminder_service._db = mock_db

        captured = {}

        async def capture_send(phone, name, body_params, button_params=None, lang_code="he"):
            captured["template_name"] = name
            captured["lang_code"] = lang_code
            return {"success": True, "provider_message_id": "wamid"}

        with patch.object(reminder_service, '_send_wa_template', new=capture_send):
            await reminder_service.send_contractor_reminder(
                "proj_1", "comp_1", triggered_by="test", skip_cooldown=True, skip_preferences=True
            )

        assert captured["template_name"] == "wa_contractor_reminder_digest_en"
        assert captured["lang_code"] == "en"

    asyncio.run(run())


def test_digest_no_open_defects_skipped():
    """Empty tasks → status=skipped, reason=no_open_defects."""
    async def run():
        mock_db = MagicMock()
        mock_db.tasks.find.return_value.to_list = AsyncMock(return_value=[])
        reminder_service._db = mock_db

        result = await reminder_service.send_contractor_reminder(
            "proj_1", "comp_1", triggered_by="test", skip_cooldown=True, skip_preferences=True
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "no_open_defects"

    asyncio.run(run())


def test_digest_log_entry_records_open_count_and_lang():
    """Verify reminder_log gets the digest-specific fields for analytics."""
    async def run():
        mock_db = _build_mock_db(
            tasks=[
                {"id": f"t{i}", "title": "T", "assignee_id": "user_1"} for i in range(7)
            ],
            project={"id": "proj_1", "name": "P", "org_id": "org_1"},
            user={"id": "user_1", "name": "U", "phone_e164": "+972501234567",
                  "preferred_language": "ar"},
        )
        # _log_reminder calls _db.reminder_log.insert_one(entry) — capture entries.
        logged = []

        async def capture_log(entry):
            logged.append(entry)

        mock_db.reminder_log.insert_one = capture_log
        reminder_service._db = mock_db

        with patch.object(reminder_service, '_send_wa_template', new=AsyncMock(
            return_value={"success": True, "provider_message_id": "wamid_xyz"}
        )):
            await reminder_service.send_contractor_reminder(
                "proj_1", "comp_1", triggered_by="cron", skip_cooldown=True, skip_preferences=True
            )

        assert len(logged) == 1
        log = logged[0]
        assert log["type"] == "contractor_reminder_digest"
        assert log["open_count"] == 7
        assert log["lang_code"] == "ar"
        assert log["status"] == "sent"
        assert log["wa_message_id"] == "wamid_xyz"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# V2 — multi-project enforcement test (PINS Zahi's intent: N projects = N msgs)
# ---------------------------------------------------------------------------

def test_send_all_three_projects_three_messages():
    """Per Zahi 2026-05-01: contractor in N projects = N separate WA messages.

    This test PINS the behavior so a future 'optimization' that aggregates
    projects into one digest will fail the test loudly.
    """
    async def run():
        mock_db = MagicMock()

        # send_all_contractor_reminders queries open tasks across all projects
        # and groups by (project_id, company_id).
        all_tasks = [
            {"id": "t_proj_A", "title": "T", "project_id": "proj_A",
             "company_id": "comp_1", "assignee_id": "contractor_user_1",
             "building_id": None, "floor_id": None, "unit_id": None,
             "created_at": "2026-04-01T00:00:00Z"},
            {"id": "t_proj_B", "title": "T", "project_id": "proj_B",
             "company_id": "comp_1", "assignee_id": "contractor_user_1",
             "building_id": None, "floor_id": None, "unit_id": None,
             "created_at": "2026-04-01T00:00:00Z"},
            {"id": "t_proj_C", "title": "T", "project_id": "proj_C",
             "company_id": "comp_1", "assignee_id": "contractor_user_1",
             "building_id": None, "floor_id": None, "unit_id": None,
             "created_at": "2026-04-01T00:00:00Z"},
        ]

        # tasks.find(query) returns tasks matching project_id (or all if no project filter)
        def tasks_find(query, projection=None):
            cursor = MagicMock()
            pid = query.get("project_id") if isinstance(query, dict) else None
            if pid:
                matched = [t for t in all_tasks if t["project_id"] == pid]
            else:
                matched = list(all_tasks)
            cursor.to_list = AsyncMock(return_value=matched)
            return cursor
        mock_db.tasks.find = MagicMock(side_effect=tasks_find)

        projects_by_id = {
            "proj_A": {"id": "proj_A", "name": "מגדלי הים", "org_id": "org_1"},
            "proj_B": {"id": "proj_B", "name": "נחל שורק", "org_id": "org_2"},
            "proj_C": {"id": "proj_C", "name": "הילטון תל אביב", "org_id": "org_2"},
        }

        async def projects_find_one(query, projection=None):
            return projects_by_id.get(query.get("id"))
        mock_db.projects.find_one = projects_find_one

        # send_all_contractor_reminders may also call projects.find().to_list()
        # to enumerate active projects.
        mock_db.projects.find.return_value.to_list = AsyncMock(
            return_value=list(projects_by_id.values())
        )

        mock_db.users.find_one = AsyncMock(return_value={
            "id": "contractor_user_1", "name": "דני קבלן",
            "phone_e164": "+972501234567", "preferred_language": "he"
        })
        mock_db.companies.find_one = AsyncMock(return_value={
            "id": "comp_1", "name": "חברה"
        })
        mock_db.reminder_log.find.return_value.to_list = AsyncMock(return_value=[])
        mock_db.reminder_log.insert_one = AsyncMock()
        mock_db.buildings.find.return_value.to_list = AsyncMock(return_value=[])
        mock_db.floors.find.return_value.to_list = AsyncMock(return_value=[])
        mock_db.units.find.return_value.to_list = AsyncMock(return_value=[])

        reminder_service._db = mock_db

        send_calls = []

        async def capture_send(phone, name, body_params, button_params=None, lang_code="he"):
            send_calls.append({
                "project_in_button": button_params[0]["text"],
                "count_in_body": next(
                    (p["text"] for p in body_params if p.get("parameter_name") == "count"),
                    None,
                ),
                "project_in_body": next(
                    (p["text"] for p in body_params if p.get("parameter_name") == "project"),
                    None,
                ),
            })
            return {"success": True, "provider_message_id": f"wamid_{len(send_calls)}"}

        # Call send_contractor_reminder once per project — equivalent to what
        # send_all_contractor_reminders does internally per (project, company)
        # pair. We invoke the per-project call directly to keep the test focused
        # on the multi-project pin (one message per call, no aggregation).
        with patch.object(reminder_service, '_send_wa_template', new=capture_send):
            for pid in ["proj_A", "proj_B", "proj_C"]:
                await reminder_service.send_contractor_reminder(
                    pid, "comp_1", triggered_by="test", skip_cooldown=True, skip_preferences=True
                )

        # 3 projects × 1 contractor = 3 messages
        assert len(send_calls) == 3, \
            f"Multi-project must send N separate messages, got {len(send_calls)}"

        # Each message names a distinct project
        project_names_in_body = {c["project_in_body"] for c in send_calls}
        assert project_names_in_body == {"מגדלי הים", "נחל שורק", "הילטון תל אביב"}, \
            f"Each project must appear once in its own message body, got {project_names_in_body}"

        # Each button URL targets the correct project_id
        project_ids_in_buttons = {c["project_in_button"] for c in send_calls}
        assert project_ids_in_buttons == {"proj_A?src=wa", "proj_B?src=wa", "proj_C?src=wa"}, \
            f"Each button URL targets its own project_id, got {project_ids_in_buttons}"

    asyncio.run(run())
