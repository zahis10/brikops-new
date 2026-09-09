import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from contractor_ops import projects_router


def test_unit_without_resolvable_project_returns_404():
    db = MagicMock()
    db.units.find_one = AsyncMock(return_value={
        'id': 'unit-1',
        'floor_id': None,
        'building_id': None,
        'project_id': None,
    })

    async def run():
        with (
            patch.object(projects_router, 'get_db', return_value=db),
            patch.object(
                projects_router,
                '_check_project_read_access',
                new=AsyncMock(),
            ) as access_check,
        ):
            with pytest.raises(HTTPException) as error:
                await projects_router.get_unit_detail(
                    'unit-1',
                    {'id': 'user-1'},
                )
            assert access_check.await_count == 0
            return error.value

    error = asyncio.run(run())
    assert error.status_code == 404
    assert error.detail == 'Unit not found'


class _Cursor:
    async def to_list(self, _limit):
        return []


def _unit_detail_db(escalations):
    db = MagicMock()
    db.units.find_one = AsyncMock(return_value={
        'id': 'unit-1',
        'project_id': 'project-1',
        'building_id': 'building-1',
        'floor_id': 'floor-1',
        'unit_no': '12',
    })
    db.floors.find_one = AsyncMock(return_value={'id': 'floor-1', 'name': 'קומה 1'})
    db.buildings.find_one = AsyncMock(return_value={
        'id': 'building-1', 'name': 'בניין א', 'project_id': 'project-1',
    })
    db.projects.find_one = AsyncMock(return_value={'id': 'project-1', 'name': 'פרויקט'})
    db.tasks.find.return_value = _Cursor()
    db.field_escalations.find_one = AsyncMock(side_effect=escalations)
    return db


def test_unit_detail_open_escalation_wins_and_management_can_escalate():
    open_escalation = {
        'id': 'esc-open',
        'status': 'open',
        'urgency': 'urgent',
        'text': 'להזמין',
        'created_at': '2026-09-04T10:00:00+00:00',
        'requested_by': {'id': 'sender', 'name': 'יוסי'},
        'assigned_to': {'id': 'assignee', 'name': 'דנה'},
        'resolved_by': None,
        'resolved_at': None,
        'resolution_note': None,
        'notes': [{}, {}],
        'context': {
            'short': [{'name': 'ריצוף', 'missing': 2, 'zero': False}],
            'borderline': ['מטבח'],
        },
    }
    db = _unit_detail_db([open_escalation])

    async def run():
        with (
            patch.object(projects_router, 'get_db', return_value=db),
            patch.object(projects_router, '_check_project_read_access', new=AsyncMock()),
            patch.object(
                projects_router,
                '_get_project_role',
                new=AsyncMock(return_value='management_team'),
            ),
        ):
            return await projects_router.get_unit_detail('unit-1', {'id': 'sender'})

    result = asyncio.run(run())
    assert result['spare_can_escalate'] is True
    assert result['spare_escalation']['id'] == 'esc-open'
    assert result['spare_escalation']['notes_count'] == 2
    assert result['spare_escalation']['context_line'] == 'חסר: ריצוף 2 · גבולי: מטבח'
    assert db.field_escalations.find_one.await_count == 1


@pytest.mark.parametrize(
    ('resolved', 'expected'),
    [
        ({
            'id': 'esc-done',
            'status': 'done',
            'urgency': 'normal',
            'text': 'להשלים',
            'created_at': '2026-09-01T10:00:00+00:00',
            'requested_by': {'id': 'sender', 'name': 'יוסי'},
            'assigned_to': None,
            'resolved_by': {'id': 'pm', 'name': 'מנהל'},
            'resolved_at': '2099-09-04T10:00:00+00:00',
            'resolution_note': 'הוזמן',
            'notes': [],
            'context': {'short': [], 'borderline': ['מטבח']},
        }, 'esc-done'),
        (None, None),
    ],
)
def test_unit_detail_recent_resolved_or_none_for_pm(resolved, expected):
    db = _unit_detail_db([None, resolved])

    async def run():
        with (
            patch.object(projects_router, 'get_db', return_value=db),
            patch.object(projects_router, '_check_project_read_access', new=AsyncMock()),
            patch.object(
                projects_router,
                '_get_project_role',
                new=AsyncMock(return_value='project_manager'),
            ),
        ):
            return await projects_router.get_unit_detail('unit-1', {'id': 'pm'})

    result = asyncio.run(run())
    assert result['spare_can_escalate'] is False
    assert (
        result['spare_escalation']['id'] if result['spare_escalation'] else None
    ) == expected
    assert db.field_escalations.find_one.await_count == 2


def test_unrelated_management_unit_detail_has_no_escalation_payload_or_leak():
    db = _unit_detail_db([{
        'id': 'other-escalation',
        'status': 'open',
        'context': {'short': [], 'borderline': []},
    }])
    db.field_escalations.find_one = AsyncMock(return_value=None)

    async def run():
        with (
            patch.object(projects_router, 'get_db', return_value=db),
            patch.object(projects_router, '_check_project_read_access', new=AsyncMock()),
            patch.object(
                projects_router,
                '_get_project_role',
                new=AsyncMock(return_value='management_team'),
            ),
        ):
            return await projects_router.get_unit_detail('unit-1', {'id': 'different-user'})

    result = asyncio.run(run())
    assert result['spare_escalation'] is None
    assert db.field_escalations.find_one.await_args.args[0]['$or'] == [
        {'requested_by.id': 'different-user'},
        {'assigned_to.id': 'different-user'},
    ]


def test_contractor_unit_detail_does_not_query_escalations():
    db = _unit_detail_db([])
    db.field_escalations.find_one = AsyncMock()

    async def run():
        with (
            patch.object(projects_router, 'get_db', return_value=db),
            patch.object(projects_router, '_check_project_read_access', new=AsyncMock()),
            patch.object(
                projects_router,
                '_get_project_role',
                new=AsyncMock(return_value='contractor'),
            ),
        ):
            return await projects_router.get_unit_detail('unit-1', {'id': 'contractor'})

    result = asyncio.run(run())
    assert result['spare_escalation'] is None
    db.field_escalations.find_one.assert_not_called()