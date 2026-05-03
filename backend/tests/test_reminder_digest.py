"""Tests for Stream A — contractor reminder digest refactor.

BATCH 6A v2 baseline (14 tests) + BATCH 6B v2 follow-up (9 new):
  - 8 sync `_resolve_digest_template_for_user` tests
  - 5 async `send_contractor_reminder` digest behavior tests (refactored
    to the new (project_id, assignee_user_id) signature — Bug A fix)
  - 1 V2 multi-project enforcement test (3 projects = 3 messages)
  ----- BATCH 6B v2 additions: -----
  - 5 regression tests pinning Bugs A, C, D, E + WA toggle off
  - 2 dormant edge-case tests (new-user exception via created_at)
  - 2 orphan-fallback tests (no assignee_id → company phone)

Async tests use the inline `asyncio.run(run())` pattern matching
test_billing_v1.py:307,336,366 — codebase has no pytest-asyncio plugin.
"""
import asyncio
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, "/home/runner/workspace/backend")

from contractor_ops import reminder_service


# ---------------------------------------------------------------------------
# Tiny helpers shared by tests
# ---------------------------------------------------------------------------

def _now_dt():
    return datetime.now(timezone.utc)


def _recent_iso(days_ago: int = 1) -> str:
    return (_now_dt() - timedelta(days=days_ago)).isoformat()


def _eligible_user(uid="user_1", name="קבלן", lang="he"):
    """Return a user dict that survives the 3-tier eligibility gate
    (WA enabled, recent login, default reminder prefs)."""
    return {
        "id": uid,
        "name": name,
        "phone_e164": "+972501234567",
        "preferred_language": lang,
        "whatsapp_notifications_enabled": True,
        "last_login_at": _recent_iso(1),
    }


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
    - reminder_log.find_one(...) → None (cooldown clean — V2 path)
    - reminder_log.find(...).to_list() → [] (legacy compat)
    - reminder_log.insert_one     → AsyncMock (records calls)
    """
    mock_db = MagicMock()
    mock_db.tasks.find.return_value.to_list = AsyncMock(return_value=tasks)
    mock_db.projects.find_one = AsyncMock(return_value=project)
    mock_db.users.find_one = AsyncMock(return_value=user)
    mock_db.reminder_log.find_one = AsyncMock(return_value=None)
    mock_db.reminder_log.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.reminder_log.insert_one = AsyncMock()
    mock_db.companies.find_one = AsyncMock(return_value=None)
    # building/floor/unit lookups are no longer called in digest mode but
    # leave AsyncMocks in place in case a regression brings them back.
    mock_db.buildings.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.floors.find.return_value.to_list = AsyncMock(return_value=[])
    mock_db.units.find.return_value.to_list = AsyncMock(return_value=[])
    return mock_db


# ---------------------------------------------------------------------------
# 5 async tests — send_contractor_reminder digest behavior
# (asyncio.run() pattern — no @pytest.mark.asyncio per Finding B)
# Refactored for BATCH 6B v2 — signature now (project_id, assignee_user_id).
# ---------------------------------------------------------------------------

def test_digest_sends_one_message_for_many_defects():
    """100 open defects → exactly 1 WA send per recipient (not 5, not 100)."""
    async def run():
        tasks = [
            {"id": f"task_{i}", "title": f"ליקוי {i}", "assignee_id": "user_1",
             "company_id": "comp_1",
             "created_at": "2026-04-01T00:00:00Z"}
            for i in range(100)
        ]
        mock_db = _build_mock_db(
            tasks=tasks,
            project={"id": "proj_1", "name": "מגדלי הים", "org_id": "org_1"},
            user=_eligible_user("user_1", "דני קבלן"),
        )
        reminder_service._db = mock_db

        with patch.object(reminder_service, '_send_wa_template', new=AsyncMock(
            return_value={"success": True, "provider_message_id": "wamid_1"}
        )) as mock_send:
            result = await reminder_service.send_contractor_reminder(
                "proj_1", "user_1", triggered_by="test",
                skip_cooldown=True, skip_preferences=True
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
                {"id": "task_1", "title": "T1", "assignee_id": "user_1", "company_id": "c1"},
                {"id": "task_2", "title": "T2", "assignee_id": "user_1", "company_id": "c1"},
            ],
            project={"id": "proj_xyz", "name": "Project", "org_id": "org_1"},
            user=_eligible_user("user_1", "Test"),
        )
        reminder_service._db = mock_db

        sent_button_params = []

        async def capture_send(phone, name, body_params, button_params=None, lang_code="he"):
            sent_button_params.append(button_params)
            return {"success": True, "provider_message_id": "wamid"}

        with patch.object(reminder_service, '_send_wa_template', new=capture_send):
            await reminder_service.send_contractor_reminder(
                "proj_xyz", "user_1", triggered_by="test",
                skip_cooldown=True, skip_preferences=True
            )

        assert len(sent_button_params) == 1
        assert sent_button_params[0][0]["text"] == "proj_xyz?src=wa", \
            f"Button URL must point to project, got: {sent_button_params[0][0]['text']}"

    asyncio.run(run())


def test_digest_uses_recipient_preferred_language():
    """English contractor → English template + lang code 'en'."""
    async def run():
        mock_db = _build_mock_db(
            tasks=[{"id": "task_1", "title": "T1", "assignee_id": "user_1", "company_id": "c1"}],
            project={"id": "proj_1", "name": "Sea Towers", "org_id": "org_1"},
            user=_eligible_user("user_1", "David", lang="en"),
        )
        reminder_service._db = mock_db

        captured = {}

        async def capture_send(phone, name, body_params, button_params=None, lang_code="he"):
            captured["template_name"] = name
            captured["lang_code"] = lang_code
            return {"success": True, "provider_message_id": "wamid"}

        with patch.object(reminder_service, '_send_wa_template', new=capture_send):
            await reminder_service.send_contractor_reminder(
                "proj_1", "user_1", triggered_by="test",
                skip_cooldown=True, skip_preferences=True
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
            "proj_1", "user_1", triggered_by="test",
            skip_cooldown=True, skip_preferences=True
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "no_open_defects"

    asyncio.run(run())


def test_digest_log_entry_records_open_count_and_lang():
    """Verify reminder_log gets the digest-specific fields for analytics."""
    async def run():
        mock_db = _build_mock_db(
            tasks=[
                {"id": f"t{i}", "title": "T", "assignee_id": "user_1", "company_id": "c1"}
                for i in range(7)
            ],
            project={"id": "proj_1", "name": "P", "org_id": "org_1"},
            user=_eligible_user("user_1", "U", lang="ar"),
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
                "proj_1", "user_1", triggered_by="cron",
                skip_cooldown=True, skip_preferences=True
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
# V2 multi-project enforcement test (PINS Zahi's intent: N projects = N msgs)
# ---------------------------------------------------------------------------

def test_send_all_three_projects_three_messages():
    """Per Zahi 2026-05-01: contractor in N projects = N separate WA messages."""
    async def run():
        mock_db = MagicMock()

        all_tasks = [
            {"id": "t_proj_A", "title": "T", "project_id": "proj_A",
             "company_id": "comp_1", "assignee_id": "contractor_user_1",
             "created_at": "2026-04-01T00:00:00Z"},
            {"id": "t_proj_B", "title": "T", "project_id": "proj_B",
             "company_id": "comp_1", "assignee_id": "contractor_user_1",
             "created_at": "2026-04-01T00:00:00Z"},
            {"id": "t_proj_C", "title": "T", "project_id": "proj_C",
             "company_id": "comp_1", "assignee_id": "contractor_user_1",
             "created_at": "2026-04-01T00:00:00Z"},
        ]

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

        # Bug C — projects must include `status: "active"` to be picked up.
        projects_by_id = {
            "proj_A": {"id": "proj_A", "name": "מגדלי הים", "org_id": "org_1", "status": "active"},
            "proj_B": {"id": "proj_B", "name": "נחל שורק", "org_id": "org_2", "status": "active"},
            "proj_C": {"id": "proj_C", "name": "הילטון תל אביב", "org_id": "org_2", "status": "active"},
        }

        async def projects_find_one(query, projection=None):
            return projects_by_id.get(query.get("id"))
        mock_db.projects.find_one = projects_find_one

        mock_db.projects.find.return_value.to_list = AsyncMock(
            return_value=list(projects_by_id.values())
        )

        mock_db.users.find_one = AsyncMock(return_value=_eligible_user(
            "contractor_user_1", "דני קבלן"
        ))
        mock_db.companies.find_one = AsyncMock(return_value={
            "id": "comp_1", "name": "חברה"
        })
        mock_db.reminder_log.find_one = AsyncMock(return_value=None)
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

        with patch.object(reminder_service, '_send_wa_template', new=capture_send):
            for pid in ["proj_A", "proj_B", "proj_C"]:
                await reminder_service.send_contractor_reminder(
                    pid, "contractor_user_1", triggered_by="test",
                    skip_cooldown=True, skip_preferences=True
                )

        assert len(send_calls) == 3, \
            f"Multi-project must send N separate messages, got {len(send_calls)}"

        project_names_in_body = {c["project_in_body"] for c in send_calls}
        assert project_names_in_body == {"מגדלי הים", "נחל שורק", "הילטון תל אביב"}

        project_ids_in_buttons = {c["project_in_button"] for c in send_calls}
        assert project_ids_in_buttons == {"proj_A?src=wa", "proj_B?src=wa", "proj_C?src=wa"}

    asyncio.run(run())


# ===========================================================================
# BATCH 6B v2 — 5 regression tests pinning the production bugs
# ===========================================================================

def test_bug_a_user_in_two_companies_same_project_gets_one_digest():
    """Bug A regression: contractor with tasks in same project tagged under
    2 companies must receive ONE digest with count=2, not two messages."""
    async def run():
        # 2 tasks in proj_1, both assigned to user_1, but different companies.
        all_tasks = [
            {"id": "t1", "title": "T1", "project_id": "proj_1",
             "assignee_id": "user_1", "company_id": "comp_a", "created_at": "2026-04-01T00:00:00Z"},
            {"id": "t2", "title": "T2", "project_id": "proj_1",
             "assignee_id": "user_1", "company_id": "comp_b", "created_at": "2026-04-01T00:00:00Z"},
        ]
        mock_db = MagicMock()

        # send_all_contractor_reminders queries by project only;
        # send_contractor_reminder queries by (project, assignee).
        def tasks_find(query, projection=None):
            cursor = MagicMock()
            pid = query.get("project_id") if isinstance(query, dict) else None
            aid = query.get("assignee_id") if isinstance(query, dict) else None
            matched = [t for t in all_tasks if t["project_id"] == pid]
            if aid:
                matched = [t for t in matched if t["assignee_id"] == aid]
            cursor.to_list = AsyncMock(return_value=matched)
            return cursor
        mock_db.tasks.find = MagicMock(side_effect=tasks_find)

        mock_db.projects.find.return_value.to_list = AsyncMock(return_value=[
            {"id": "proj_1", "name": "מגדלי הים", "status": "active"}
        ])
        mock_db.projects.find_one = AsyncMock(return_value={
            "id": "proj_1", "name": "מגדלי הים", "org_id": "org_1"
        })
        mock_db.users.find_one = AsyncMock(return_value=_eligible_user("user_1", "דני"))
        mock_db.reminder_log.find_one = AsyncMock(return_value=None)
        mock_db.reminder_log.insert_one = AsyncMock()
        reminder_service._db = mock_db

        send_calls = []

        async def capture_send(phone, name, body_params, button_params=None, lang_code="he"):
            send_calls.append({
                "count": next((p["text"] for p in body_params if p.get("parameter_name") == "count"), None),
            })
            return {"success": True, "provider_message_id": f"wamid_{len(send_calls)}"}

        with patch.object(reminder_service, '_send_wa_template', new=capture_send):
            summary = await reminder_service.send_all_contractor_reminders()

        assert len(send_calls) == 1, \
            f"Bug A regression: same user across 2 companies must collapse to ONE digest, got {len(send_calls)}"
        assert send_calls[0]["count"] == "2", \
            f"Digest must aggregate both defects (count=2), got count={send_calls[0]['count']}"
        assert summary["sent"] == 1

    asyncio.run(run())


def test_bug_c_inactive_projects_filtered_out():
    """Bug C regression: suspended/archived projects must NOT trigger sends."""
    async def run():
        mock_db = MagicMock()
        # Capture the filter passed to projects.find — that's the assertion.
        captured_filter = {}

        def projects_find(query, projection=None):
            captured_filter.update(query)
            cursor = MagicMock()
            cursor.to_list = AsyncMock(return_value=[])  # nothing eligible
            return cursor
        mock_db.projects.find = MagicMock(side_effect=projects_find)

        reminder_service._db = mock_db
        summary = await reminder_service.send_all_contractor_reminders()

        assert captured_filter.get("status") == "active", \
            f"Bug C regression: filter must restrict to status=active, got {captured_filter}"
        # archived guard present
        archived_clauses = captured_filter.get("$or", [])
        assert any("archived" in c for c in archived_clauses), \
            f"Bug C regression: filter must guard archived flag, got {captured_filter}"
        assert summary["sent"] == 0  # no eligible projects, no sends

    asyncio.run(run())


def test_bug_d_dormant_user_skipped():
    """Bug D regression: user inactive >45 days must be skipped (no WA cost)."""
    async def run():
        dormant_user = _eligible_user("user_dormant", "ישן")
        # Override last_login_at to 90 days ago — clearly dormant.
        dormant_user["last_login_at"] = (_now_dt() - timedelta(days=90)).isoformat()
        # Override created_at to also be old so the new-user exception doesn't apply.
        dormant_user["created_at"] = (_now_dt() - timedelta(days=120)).isoformat()

        mock_db = _build_mock_db(
            tasks=[{"id": "t1", "title": "T", "assignee_id": "user_dormant", "company_id": "c1"}],
            project={"id": "proj_1", "name": "P", "org_id": "org_1"},
            user=dormant_user,
        )
        reminder_service._db = mock_db

        with patch.object(reminder_service, '_send_wa_template', new=AsyncMock()) as mock_send:
            result = await reminder_service.send_contractor_reminder(
                "proj_1", "user_dormant", triggered_by="cron",
                skip_cooldown=True, skip_preferences=False  # eligibility ON
            )

        assert mock_send.call_count == 0, "Dormant user must NOT receive WA"
        assert result["status"] == "skipped"
        assert result["reason"] == "user_dormant"

    asyncio.run(run())


def test_bug_e_wa_toggle_disabled_skipped():
    """Bug E regression: whatsapp_notifications_enabled=False must skip digest."""
    async def run():
        opted_out_user = _eligible_user("user_opt_out", "אופט-אאוט")
        opted_out_user["whatsapp_notifications_enabled"] = False

        mock_db = _build_mock_db(
            tasks=[{"id": "t1", "title": "T", "assignee_id": "user_opt_out", "company_id": "c1"}],
            project={"id": "proj_1", "name": "P", "org_id": "org_1"},
            user=opted_out_user,
        )
        reminder_service._db = mock_db

        with patch.object(reminder_service, '_send_wa_template', new=AsyncMock()) as mock_send:
            result = await reminder_service.send_contractor_reminder(
                "proj_1", "user_opt_out", triggered_by="cron",
                skip_cooldown=True, skip_preferences=False
            )

        assert mock_send.call_count == 0, "WA-disabled user must NOT receive digest"
        assert result["status"] == "skipped"
        assert result["reason"] == "wa_disabled"

    asyncio.run(run())


def test_cooldown_user_keyed_skips_second_send():
    """Bug A cooldown re-key: a recent log entry for (project, user) blocks
    the next send within COOLDOWN_HOURS, regardless of company_id."""
    async def run():
        mock_db = _build_mock_db(
            tasks=[{"id": "t1", "title": "T", "assignee_id": "user_1", "company_id": "c1"}],
            project={"id": "proj_1", "name": "P", "org_id": "org_1"},
            user=_eligible_user("user_1"),
        )
        # find_one returns a row → cooldown HIT.
        mock_db.reminder_log.find_one = AsyncMock(return_value={
            "id": "rem_existing", "type": "contractor_reminder_digest",
            "project_id": "proj_1", "recipient_user_id": "user_1",
            "sent_at": _recent_iso(0).replace("+00:00", "Z"),
        })
        reminder_service._db = mock_db

        with patch.object(reminder_service, '_send_wa_template', new=AsyncMock()) as mock_send:
            result = await reminder_service.send_contractor_reminder(
                "proj_1", "user_1", triggered_by="cron",
                skip_cooldown=False, skip_preferences=True
            )

        assert mock_send.call_count == 0, "Cooldown HIT must block send"
        assert result["status"] == "skipped"
        assert result["reason"] == "cooldown"

    asyncio.run(run())


# ===========================================================================
# BATCH 6B v2 — 2 dormant edge-case tests (V2 new-user exception)
# ===========================================================================

def test_dormant_new_user_no_login_recent_created_not_dormant():
    """V2 edge case: brand-new invite (no last_login_at, created < 45d ago)
    must NOT be treated as dormant. Otherwise fresh users would never get
    their first reminder."""
    async def run():
        new_user = {
            "id": "user_new",
            "name": "חדש",
            "phone_e164": "+972501234567",
            "preferred_language": "he",
            "whatsapp_notifications_enabled": True,
            # No last_login_at — never logged in yet.
            "created_at": (_now_dt() - timedelta(days=3)).isoformat(),
        }
        # Direct helper test (no DB needed).
        assert reminder_service._is_user_dormant(new_user) is False, \
            "New user (created 3d ago, no login) must NOT be dormant"

        # Full integration: send must succeed.
        mock_db = _build_mock_db(
            tasks=[{"id": "t1", "title": "T", "assignee_id": "user_new", "company_id": "c1"}],
            project={"id": "proj_1", "name": "P", "org_id": "org_1"},
            user=new_user,
        )
        reminder_service._db = mock_db
        with patch.object(reminder_service, '_send_wa_template', new=AsyncMock(
            return_value={"success": True, "provider_message_id": "wamid"}
        )) as mock_send:
            result = await reminder_service.send_contractor_reminder(
                "proj_1", "user_new", triggered_by="cron",
                skip_cooldown=True, skip_preferences=False
            )
        assert mock_send.call_count == 1
        assert result["status"] == "completed"

    asyncio.run(run())


def test_dormant_old_user_no_login_old_created_is_dormant():
    """V2 edge case: account created >45d ago that has never logged in
    is dormant (fallback to created_at when last_login_at missing)."""
    async def run():
        stale_invite = {
            "id": "user_stale",
            "name": "ישן",
            "phone_e164": "+972501234567",
            "whatsapp_notifications_enabled": True,
            "created_at": (_now_dt() - timedelta(days=180)).isoformat(),
            # No last_login_at.
        }
        assert reminder_service._is_user_dormant(stale_invite) is True, \
            "Old invite (created 180d ago, never logged in) must be dormant"

    asyncio.run(run())


# ===========================================================================
# BATCH 6B v2 — 2 orphan-fallback tests
# (tasks with company_id but no assignee_id → company phone)
# ===========================================================================

def test_orphan_fallback_sends_to_company_phone():
    """Tasks without assignee_id but with company_id must be picked up by
    the orphan-fallback path and sent to the company's phone."""
    async def run():
        orphan_tasks = [
            {"id": "t1", "title": "T1", "assignee_id": None, "company_id": "comp_1"},
            {"id": "t2", "title": "T2", "assignee_id": "", "company_id": "comp_1"},
        ]
        mock_db = MagicMock()
        mock_db.tasks.find.return_value.to_list = AsyncMock(return_value=orphan_tasks)
        mock_db.projects.find_one = AsyncMock(return_value={
            "id": "proj_1", "name": "מגדלי הים", "org_id": "org_1"
        })
        mock_db.companies.find_one = AsyncMock(return_value={
            "id": "comp_1", "name": "חברה אבא", "phone_e164": "+972502222222"
        })
        mock_db.reminder_log.find_one = AsyncMock(return_value=None)
        mock_db.reminder_log.insert_one = AsyncMock()
        reminder_service._db = mock_db

        captured = {}

        async def capture_send(phone, name, body_params, button_params=None, lang_code="he"):
            captured["phone"] = phone
            captured["count"] = next(
                (p["text"] for p in body_params if p.get("parameter_name") == "count"), None
            )
            captured["lang_code"] = lang_code
            return {"success": True, "provider_message_id": "wamid_orphan"}

        with patch.object(reminder_service, '_send_wa_template', new=capture_send):
            result = await reminder_service.send_contractor_reminder_to_company(
                "proj_1", "comp_1", triggered_by="cron", skip_cooldown=True
            )

        assert captured["phone"] == "+972502222222", \
            f"Orphan path must send to company phone, got {captured.get('phone')}"
        assert captured["count"] == "2"
        assert captured["lang_code"] == "he", "Orphan path defaults to Hebrew"
        assert result["status"] == "completed"

    asyncio.run(run())


def test_orphan_fallback_no_company_phone_skipped():
    """Orphan fallback must skip cleanly when the company has no phone."""
    async def run():
        mock_db = MagicMock()
        mock_db.tasks.find.return_value.to_list = AsyncMock(return_value=[
            {"id": "t1", "title": "T", "assignee_id": None, "company_id": "comp_no_phone"}
        ])
        mock_db.projects.find_one = AsyncMock(return_value={
            "id": "proj_1", "name": "P", "org_id": "org_1"
        })
        # Company exists but has no phone.
        mock_db.companies.find_one = AsyncMock(return_value={
            "id": "comp_no_phone", "name": "חברה ללא טלפון"
        })
        mock_db.reminder_log.find_one = AsyncMock(return_value=None)
        reminder_service._db = mock_db

        with patch.object(reminder_service, '_send_wa_template', new=AsyncMock()) as mock_send:
            result = await reminder_service.send_contractor_reminder_to_company(
                "proj_1", "comp_no_phone", triggered_by="cron", skip_cooldown=True
            )

        assert mock_send.call_count == 0
        assert result["status"] == "skipped"
        assert result["reason"] == "no_valid_phone"

    asyncio.run(run())
