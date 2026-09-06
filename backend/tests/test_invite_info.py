import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from contractor_ops import onboarding_router


def _invite_info_endpoint():
    router = onboarding_router.create_onboarding_router(
        lambda: None,
        lambda *_roles: lambda: None,
    )
    return next(
        route.endpoint
        for route in router.routes
        if getattr(route, 'path', '') == '/api/invites/{invite_id}/info'
        and 'GET' in getattr(route, 'methods', set())
    )


@pytest.mark.parametrize(
    ('invite_language', 'expected_language'),
    [('ar', 'ar'), (None, 'he')],
)
def test_invite_info_returns_preferred_language(
    monkeypatch,
    invite_language,
    expected_language,
):
    db = MagicMock()
    db.invites.find_one = AsyncMock(return_value={
        'id': 'invite-1',
        'project_id': 'project-1',
        'status': 'pending',
        'expires_at': '2999-01-01T00:00:00+00:00',
        'role': 'contractor',
        **(
            {'preferred_language': invite_language}
            if invite_language is not None
            else {}
        ),
    })
    db.projects.find_one = AsyncMock(return_value={
        'id': 'project-1',
        'name': 'Project',
    })
    monkeypatch.setattr(onboarding_router, 'get_db', lambda: db)

    result = asyncio.run(_invite_info_endpoint()('invite-1'))

    assert result['preferred_language'] == expected_language
    assert result['invite_id'] == 'invite-1'
    assert result['role'] == 'contractor'