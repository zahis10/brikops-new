"""
Tests for WhatsApp webhook fixes:
1) GET /webhooks/whatsapp returns challenge as plain text (not int/JSON)
2) POST /webhooks/whatsapp processes multiple statuses (not just the first)
3) process_webhook accepts 'sent' status
4) process_job raises if provider_message_id is empty
5) RBAC: retry uses project_manager/management_team
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_verify_returns_plain_text():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from contractor_ops.notification_router import (
        create_notification_router, set_engine, set_wa_verify_token,
    )

    app = FastAPI()
    set_wa_verify_token("test_token_123")

    def mock_require_roles(*roles):
        async def checker():
            return {'id': 'u1', 'role': 'project_manager', 'platform_role': 'none'}
        return checker

    async def mock_get_user():
        return {'id': 'u1', 'role': 'project_manager', 'platform_role': 'none'}

    router = create_notification_router(mock_require_roles, mock_get_user)
    app.include_router(router)

    client = TestClient(app)

    resp = client.get("/api/webhooks/whatsapp", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "test_token_123",
        "hub.challenge": "1234567890",
    })

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert resp.headers.get("content-type", "").startswith("text/plain"), \
        f"Expected text/plain, got {resp.headers.get('content-type')}"
    assert resp.text == "1234567890", f"Expected '1234567890', got '{resp.text}'"
    print("PASS: verify returns challenge as plain text (not int/JSON)")


def test_verify_rejects_bad_token():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from contractor_ops.notification_router import (
        create_notification_router, set_wa_verify_token,
    )

    app = FastAPI()
    set_wa_verify_token("correct_token")

    def mock_require_roles(*roles):
        async def checker():
            return {'id': 'u1', 'role': 'project_manager'}
        return checker

    async def mock_get_user():
        return {'id': 'u1', 'role': 'project_manager'}

    router = create_notification_router(mock_require_roles, mock_get_user)
    app.include_router(router)
    client = TestClient(app)

    resp = client.get("/api/webhooks/whatsapp", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_token",
        "hub.challenge": "12345",
    })
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    print("PASS: verify rejects bad token with 403")


def test_process_webhook_accepts_sent_status():
    from unittest.mock import AsyncMock, MagicMock

    from contractor_ops.notification_service import NotificationEngine, WhatsAppClient

    mock_db = MagicMock()
    mock_db.notification_jobs = MagicMock()
    mock_db.audit_events = MagicMock()

    mock_job = {
        'id': 'job-1',
        'provider_message_id': 'wamid_123',
        'status': 'queued',
    }
    mock_db.notification_jobs.find_one = AsyncMock(return_value=mock_job)
    mock_db.notification_jobs.update_one = AsyncMock()
    mock_db.audit_events.insert_one = AsyncMock()

    wa_client = WhatsAppClient(enabled=False)
    engine = NotificationEngine(mock_db, wa_client)

    result = asyncio.get_event_loop().run_until_complete(
        engine.process_webhook('wamid_123', 'sent')
    )
    assert result is not None, "process_webhook('sent') returned None — 'sent' should be accepted"
    assert result['status'] == 'sent', f"Expected status 'sent', got '{result['status']}'"
    print("PASS: process_webhook accepts 'sent' status")


def test_post_webhook_processes_multiple_statuses():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from unittest.mock import AsyncMock, MagicMock
    from contractor_ops.notification_router import (
        create_notification_router, set_engine, set_wa_verify_token,
    )
    from contractor_ops.notification_service import NotificationEngine, WhatsAppClient

    mock_db = MagicMock()
    wa_client = WhatsAppClient(enabled=False)
    engine = NotificationEngine(mock_db, wa_client)

    call_count = 0
    async def mock_process_webhook(provider_id, status):
        nonlocal call_count
        call_count += 1
        return {'job_id': f'job-{call_count}', 'status': status}

    engine.process_webhook = mock_process_webhook
    set_engine(engine)

    app = FastAPI()
    def mock_require_roles(*roles):
        async def checker():
            return {'id': 'u1', 'role': 'project_manager'}
        return checker
    async def mock_get_user():
        return {'id': 'u1', 'role': 'project_manager'}

    router = create_notification_router(mock_require_roles, mock_get_user)
    app.include_router(router)
    client = TestClient(app)

    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [
                        {"id": "wamid_aaa", "status": "sent"},
                        {"id": "wamid_bbb", "status": "delivered"},
                        {"id": "wamid_ccc", "status": "read"},
                    ]
                }
            }]
        }]
    }

    resp = client.post("/api/webhooks/whatsapp", json=payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data['processed'] == 3, f"Expected 3 processed, got {data['processed']}"
    assert len(data['results']) == 3, f"Expected 3 results, got {len(data['results'])}"
    print(f"PASS: POST webhook processed {data['processed']} statuses (not just 1)")


def test_process_job_rejects_empty_provider_id():
    from unittest.mock import AsyncMock, MagicMock
    from contractor_ops.notification_service import NotificationEngine, WhatsAppClient

    mock_db = MagicMock()
    mock_db.notification_jobs = MagicMock()
    mock_db.notification_jobs.update_one = AsyncMock()
    mock_db.audit_events = MagicMock()
    mock_db.audit_events.insert_one = AsyncMock()

    wa_client = WhatsAppClient(enabled=True)
    wa_client.send_message = AsyncMock(return_value={
        'success': True,
        'provider_message_id': '',
    })

    engine = NotificationEngine(mock_db, wa_client)

    job = {
        'id': 'job-empty',
        'target_phone': '+972501234567',
        'payload': {'title': 'test'},
        'attempts': 0,
        'max_attempts': 3,
        'created_by': 'user-1',
    }

    result = asyncio.get_event_loop().run_until_complete(engine.process_job(job))
    assert result['status'] in ('failed', 'queued'), \
        f"Expected failed/queued when provider_id empty, got '{result['status']}'"
    assert 'error' in result, "Expected error message in result"
    print(f"PASS: process_job rejects empty provider_message_id (status={result['status']})")


def test_rbac_retry_and_notify_roles():
    import inspect
    from contractor_ops.notification_router import create_notification_router

    captured_roles = {}

    def spy_require_roles(*roles):
        caller = inspect.stack()[1]
        line = caller.lineno
        captured_roles[line] = roles
        async def checker():
            return {'id': 'u1', 'role': 'project_manager', 'platform_role': 'none'}
        return checker

    async def mock_get_user():
        return {'id': 'u1', 'role': 'project_manager', 'platform_role': 'none'}

    create_notification_router(spy_require_roles, mock_get_user)

    all_roles = []
    for line, roles in captured_roles.items():
        all_roles.append(set(roles))

    for role_set in all_roles:
        assert 'owner' not in role_set, f"Found 'owner' in RBAC roles: {role_set}"
        assert 'admin' not in role_set, f"Found 'admin' in RBAC roles: {role_set}"

    has_pm = any('project_manager' in rs for rs in all_roles)
    has_mt = any('management_team' in rs for rs in all_roles)
    assert has_pm, "Expected 'project_manager' in at least one endpoint's RBAC roles"
    assert has_mt, "Expected 'management_team' in at least one endpoint's RBAC roles"
    print(f"PASS: RBAC uses project_manager/management_team (no owner/admin) — {len(all_roles)} endpoints checked")


if __name__ == '__main__':
    print("=" * 60)
    print("WhatsApp + RBAC Fix Tests")
    print("=" * 60)
    test_verify_returns_plain_text()
    test_verify_rejects_bad_token()
    test_process_webhook_accepts_sent_status()
    test_post_webhook_processes_multiple_statuses()
    test_process_job_rejects_empty_provider_id()
    test_rbac_retry_and_notify_roles()
    print("=" * 60)
    print("ALL 6 TESTS PASSED")
    print("=" * 60)
