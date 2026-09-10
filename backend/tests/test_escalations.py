import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from contractor_ops import escalations_router
from contractor_ops.escalations import (
    ESCALATABLE,
    build_spare_context,
    can_escalate,
    context_line,
    default_text,
)


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return self.rows


def sample_status(overall='short'):
    return {
        'overall': overall,
        'categories': [
            {
                'name': 'ריצוף',
                'status': 'short',
                'missing': 2,
                'measure': 'tiles',
                'entered': True,
                'actual': 3,
            },
            {
                'name': 'חיפוי',
                'status': 'short',
                'missing': None,
                'measure': 'sqm',
                'entered': True,
                'actual': 0,
            },
            {'name': 'מטבח', 'status': 'borderline'},
        ],
    }


def sample_escalation(**changes):
    value = {
        'id': 'esc-1',
        'project_id': 'project-1',
        'type': 'spare_tiles',
        'unit_id': 'unit-1',
        'urgency': 'urgent',
        'text': 'להזמין',
        'labels': {'building': 'בניין א', 'floor': '1', 'unit': '12'},
        'context': build_spare_context(sample_status()),
        'requested_by': {
            'id': 'requester',
            'name': 'יוסי',
            'role': 'management_team',
            'sub_role': 'site_manager',
        },
        'assigned_to': None,
        'status': 'open',
        'created_at': '2026-09-04T10:00:00+00:00',
        'updated_at': '2026-09-04T10:00:00+00:00',
        'resolved_by': None,
        'resolved_at': None,
        'resolution_note': None,
        'notes': [],
    }
    value.update(changes)
    return value


def test_spare_context_line_and_default_text_contract():
    context = build_spare_context(sample_status())
    assert context == {
        'short': [
            {'name': 'ריצוף', 'missing': 2, 'measure': 'tiles', 'zero': False},
            {'name': 'חיפוי', 'missing': 0, 'measure': 'sqm', 'zero': True},
        ],
        'borderline': ['מטבח'],
    }
    assert context_line(context) == 'חסר: ריצוף 2, חיפוי (אין ספייר) · גבולי: מטבח'
    assert default_text('urgent', '12', context) == (
        'דחוף להזמין ריצוף ספייר לדירה 12 — חסר 2 סוגים'
    )
    assert default_text('normal', '12', context) == (
        'להשלים ריצוף ספייר לדירה 12 — חסר: ריצוף 2, חיפוי (אין ספייר) · גבולי: מטבח'
    )
    one = {'short': context['short'][:1], 'borderline': []}
    assert default_text('urgent', '12', one) == (
        'דחוף להזמין ריצוף ספייר לדירה 12 — חסר סוג אחד'
    )


@pytest.mark.parametrize(
    'overall',
    ['no_profile', 'short', 'borderline', 'not_entered', 'ok', 'recorded', 'no_target'],
)
def test_can_escalate_only_short_and_borderline(overall):
    assert can_escalate({'overall': overall}) is (overall in ESCALATABLE)


def test_create_happy_path_snapshots_and_notifies_pm(monkeypatch):
    db = MagicMock()
    project = {'id': 'project-1', 'spare_settings': {'profiles': []}}
    unit = {
        'id': 'unit-1',
        'project_id': 'project-1',
        'building_id': 'building-1',
        'floor_id': 'floor-1',
        'display_label': '12א',
    }
    db.projects.find_one = AsyncMock(return_value=project)
    db.units.find_one = AsyncMock(return_value=unit)
    db.field_escalations.find_one = AsyncMock(return_value=None)
    db.field_escalations.insert_one = AsyncMock()
    db.buildings.find_one = AsyncMock(return_value={'id': 'building-1', 'name': 'בניין א'})
    db.floors.find_one = AsyncMock(return_value={'id': 'floor-1', 'name': 'קומה 1'})
    db.project_memberships.find.return_value = Cursor([{'user_id': 'pm-1'}])
    notify = AsyncMock()
    monkeypatch.setattr(escalations_router, 'get_db', lambda: db)
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='management_team'))
    monkeypatch.setattr(
        escalations_router,
        '_get_project_membership',
        AsyncMock(return_value={'role': 'management_team', 'sub_role': 'site_manager'}),
    )
    monkeypatch.setattr(escalations_router, 'compute_spare_status', lambda *_args: sample_status())
    monkeypatch.setattr(escalations_router, '_audit', AsyncMock())
    monkeypatch.setattr(escalations_router, 'create_defect_notification', notify)

    result = asyncio.run(escalations_router.create_escalation(
        'project-1',
        {'unit_id': 'unit-1', 'urgency': 'urgent', 'text': '  להזמין  '},
        {'id': 'requester', 'name': 'יוסי'},
    ))

    assert result['appended_note'] is False
    inserted = db.field_escalations.insert_one.await_args.args[0]
    assert inserted['labels'] == {'building': 'בניין א', 'floor': 'קומה 1', 'unit': '12א'}
    assert inserted['requested_by']['sub_role'] == 'site_manager'
    assert inserted['context']['short'][1]['zero'] is True
    kwargs = notify.await_args.kwargs
    assert notify.await_args.args[1] == ['pm-1']
    assert kwargs['notification_type'] == 'field_escalation'
    assert kwargs['action'] == 'escalate'
    assert kwargs['extra']['unit_id'] == 'unit-1'


def test_create_rejects_role_non_short_and_long_text(monkeypatch):
    db = MagicMock()
    db.projects.find_one = AsyncMock(return_value={'id': 'project-1'})
    monkeypatch.setattr(escalations_router, 'get_db', lambda: db)
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='contractor'))
    with pytest.raises(HTTPException) as error:
        asyncio.run(escalations_router.create_escalation(
            'project-1', {'unit_id': 'unit-1', 'text': 'x'}, {'id': 'c'},
        ))
    assert error.value.status_code == 403

    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='project_manager'))
    monkeypatch.setattr(
        escalations_router, '_get_project_membership',
        AsyncMock(return_value={'role': 'project_manager', 'sub_role': None}),
    )
    db.units.find_one = AsyncMock(return_value={'id': 'unit-1', 'project_id': 'project-1'})
    monkeypatch.setattr(
        escalations_router, 'compute_spare_status',
        lambda *_args: {'overall': 'ok', 'categories': []},
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(escalations_router.create_escalation(
            'project-1', {'unit_id': 'unit-1', 'text': 'x'}, {'id': 'pm'},
        ))
    assert error.value.status_code == 422

    monkeypatch.setattr(escalations_router, 'compute_spare_status', lambda *_args: sample_status())
    with pytest.raises(HTTPException) as error:
        asyncio.run(escalations_router.create_escalation(
            'project-1', {'unit_id': 'unit-1', 'text': 'x' * 501}, {'id': 'pm'},
        ))
    assert error.value.detail == 'יש לכתוב הודעה (עד 500 תווים)'


def test_second_create_appends_note_and_notifies_assignee(monkeypatch):
    db = MagicMock()
    existing = sample_escalation(assigned_to={'id': 'assignee', 'name': 'דנה'})
    db.projects.find_one = AsyncMock(return_value={'id': 'project-1'})
    db.units.find_one = AsyncMock(return_value={'id': 'unit-1', 'project_id': 'project-1'})
    db.buildings.find_one = AsyncMock(return_value={'name': 'בניין א'})
    db.floors.find_one = AsyncMock(return_value={'name': 'קומה 1'})
    db.field_escalations.find_one = AsyncMock(return_value=existing)
    db.field_escalations.update_one = AsyncMock()
    notify = AsyncMock()
    monkeypatch.setattr(escalations_router, 'get_db', lambda: db)
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='management_team'))
    monkeypatch.setattr(
        escalations_router, '_get_project_membership',
        AsyncMock(return_value={'role': 'management_team', 'sub_role': 'site_manager'}),
    )
    monkeypatch.setattr(escalations_router, 'compute_spare_status', lambda *_args: sample_status())
    monkeypatch.setattr(escalations_router, '_audit', AsyncMock())
    monkeypatch.setattr(escalations_router, 'create_defect_notification', notify)

    result = asyncio.run(escalations_router.create_escalation(
        'project-1',
        {'unit_id': 'unit-1', 'urgency': 'normal', 'text': 'הערה'},
        {'id': 'requester', 'name': 'יוסי'},
    ))
    assert result['appended_note'] is True
    db.field_escalations.insert_one.assert_not_called()
    assert notify.await_args.args[1] == ['assignee']
    assert notify.await_args.kwargs['action'] == 'escalation_note'


def test_patch_done_permissions_conflict_and_notification(monkeypatch):
    db = MagicMock()
    esc = sample_escalation()
    db.field_escalations.find_one = AsyncMock(return_value=esc)
    db.field_escalations.update_one = AsyncMock()
    notify = AsyncMock()
    monkeypatch.setattr(escalations_router, 'get_db', lambda: db)
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='project_manager'))
    monkeypatch.setattr(
        escalations_router, '_get_project_membership',
        AsyncMock(return_value={'role': 'project_manager', 'sub_role': None}),
    )
    monkeypatch.setattr(escalations_router, '_audit', AsyncMock())
    monkeypatch.setattr(escalations_router, 'create_defect_notification', notify)
    result = asyncio.run(escalations_router.patch_escalation(
        'esc-1', {'action': 'done', 'note': 'הוזמן'}, {'id': 'pm', 'name': 'מנהל'},
    ))
    assert result['escalation']['status'] == 'done'
    assert result['escalation']['resolved_by'] == {'id': 'pm', 'name': 'מנהל'}
    assert notify.await_args.args[1] == ['requester']
    assert notify.await_args.kwargs['notification_type'] == 'field_escalation_resolved'
    assert 'הוזמן' in notify.await_args.kwargs['body']

    db.field_escalations.find_one = AsyncMock(return_value=sample_escalation(status='done'))
    with pytest.raises(HTTPException) as error:
        asyncio.run(escalations_router.patch_escalation(
            'esc-1', {'action': 'done'}, {'id': 'pm', 'name': 'מנהל'},
        ))
    assert error.value.status_code == 409

    db.field_escalations.find_one = AsyncMock(return_value=sample_escalation())
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='management_team'))
    with pytest.raises(HTTPException) as error:
        asyncio.run(escalations_router.patch_escalation(
            'esc-1', {'action': 'done'}, {'id': 'other', 'name': 'אחר'},
        ))
    assert error.value.status_code == 403


def test_patch_assign_validates_membership_and_notifies(monkeypatch):
    db = MagicMock()
    db.field_escalations.find_one = AsyncMock(return_value=sample_escalation())
    db.field_escalations.update_one = AsyncMock()
    db.project_memberships.find_one = AsyncMock(return_value=None)
    notify = AsyncMock()
    monkeypatch.setattr(escalations_router, 'get_db', lambda: db)
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='project_manager'))
    monkeypatch.setattr(
        escalations_router, '_get_project_membership',
        AsyncMock(return_value={'role': 'project_manager', 'sub_role': None}),
    )
    monkeypatch.setattr(escalations_router, '_audit', AsyncMock())
    monkeypatch.setattr(escalations_router, 'create_defect_notification', notify)
    with pytest.raises(HTTPException) as error:
        asyncio.run(escalations_router.patch_escalation(
            'esc-1', {'action': 'assign', 'assignee_id': 'contractor'}, {'id': 'pm'},
        ))
    assert error.value.detail == 'המשתמש אינו חבר צוות ניהול בפרויקט'

    db.project_memberships.find_one = AsyncMock(return_value={'role': 'management_team'})
    db.users.find_one = AsyncMock(return_value={'name': 'דנה'})
    result = asyncio.run(escalations_router.patch_escalation(
        'esc-1',
        {'action': 'assign', 'assignee_id': 'assignee'},
        {'id': 'pm', 'name': 'מנהל'},
    ))
    assert result['escalation']['assigned_to'] == {'id': 'assignee', 'name': 'דנה'}
    assert notify.await_args.args[1] == ['assignee']
    assert notify.await_args.kwargs['action'] == 'escalation_assigned'

    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='management_team'))
    with pytest.raises(HTTPException) as error:
        asyncio.run(escalations_router.patch_escalation(
            'esc-1', {'action': 'assign', 'assignee_id': None}, {'id': 'requester'},
        ))
    assert error.value.status_code == 403


def test_patch_notes_route_to_other_side_and_unknown_action(monkeypatch):
    db = MagicMock()
    db.field_escalations.find_one = AsyncMock(return_value=sample_escalation())
    db.field_escalations.update_one = AsyncMock()
    db.project_memberships.find.return_value = Cursor([{'user_id': 'pm-1'}])
    notify = AsyncMock()
    monkeypatch.setattr(escalations_router, 'get_db', lambda: db)
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='management_team'))
    monkeypatch.setattr(
        escalations_router, '_get_project_membership',
        AsyncMock(return_value={'role': 'management_team', 'sub_role': None}),
    )
    monkeypatch.setattr(escalations_router, '_audit', AsyncMock())
    monkeypatch.setattr(escalations_router, 'create_defect_notification', notify)
    asyncio.run(escalations_router.patch_escalation(
        'esc-1', {'action': 'note', 'note': 'עוד מידע'}, {'id': 'requester', 'name': 'יוסי'},
    ))
    assert notify.await_args.args[1] == ['pm-1']

    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='project_manager'))
    asyncio.run(escalations_router.patch_escalation(
        'esc-1', {'action': 'note', 'note': 'בטיפול'}, {'id': 'pm', 'name': 'מנהל'},
    ))
    assert notify.await_args.args[1] == ['requester']
    with pytest.raises(HTTPException) as error:
        asyncio.run(escalations_router.patch_escalation(
            'esc-1', {'action': 'other'}, {'id': 'pm'},
        ))
    assert error.value.status_code == 422


def test_list_pm_sorts_urgent_first_and_returns_counts(monkeypatch):
    db = MagicMock()
    normal = sample_escalation(
        id='normal',
        urgency='normal',
        created_at='2026-09-04T12:00:00+00:00',
    )
    urgent_old = sample_escalation(
        id='urgent-old',
        created_at='2026-09-04T10:00:00+00:00',
    )
    urgent_new = sample_escalation(
        id='urgent-new',
        created_at='2026-09-04T11:00:00+00:00',
    )
    db.projects.find_one = AsyncMock(return_value={'id': 'project-1'})
    db.field_escalations.find.return_value = Cursor([normal, urgent_old, urgent_new])
    db.field_escalations.count_documents = AsyncMock(side_effect=[3, 2, 1])
    monkeypatch.setattr(escalations_router, 'get_db', lambda: db)
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='project_manager'))
    monkeypatch.setattr(
        escalations_router, '_get_project_membership',
        AsyncMock(return_value={'role': 'project_manager', 'sub_role': None}),
    )
    result = asyncio.run(escalations_router.list_escalations(
        'project-1', 'open', {'id': 'pm'},
    ))
    assert [item['id'] for item in result['items']] == [
        'urgent-new', 'urgent-old', 'normal',
    ]
    assert (result['open_count'], result['urgent_count'], result['resolved_week_count']) == (3, 2, 1)
    assert result['can_assign'] is True
    find_query = db.field_escalations.find.call_args.args[0]
    assert find_query == {
        'project_id': 'project-1', 'type': 'spare_tiles', 'status': 'open',
    }


def test_list_management_visibility_and_contractor_rejected(monkeypatch):
    db = MagicMock()
    db.projects.find_one = AsyncMock(return_value={'id': 'project-1'})
    db.field_escalations.find.return_value = Cursor([])
    db.field_escalations.count_documents = AsyncMock(return_value=0)
    monkeypatch.setattr(escalations_router, 'get_db', lambda: db)
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='management_team'))
    monkeypatch.setattr(
        escalations_router, '_get_project_membership',
        AsyncMock(return_value={'role': 'management_team', 'sub_role': 'site_manager'}),
    )
    result = asyncio.run(escalations_router.list_escalations(
        'project-1', 'open', {'id': 'member'},
    ))
    assert result['role'] == 'management_team'
    assert result['can_assign'] is False
    assert db.field_escalations.find.call_args.args[0]['$or'] == [
        {'requested_by.id': 'member'},
        {'assigned_to.id': 'member'},
    ]

    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='contractor'))
    with pytest.raises(HTTPException) as error:
        asyncio.run(escalations_router.list_escalations(
            'project-1', 'open', {'id': 'contractor'},
        ))
    assert error.value.status_code == 403


def test_concurrent_creates_leave_one_document_and_append_winner_note(monkeypatch):
    class Field:
        def __init__(self):
            self.document = None
            self.insert_calls = 0

        async def find_one(self, query, *_args, **_kwargs):
            await asyncio.sleep(0)
            return self.document

        async def insert_one(self, document):
            self.insert_calls += 1
            await asyncio.sleep(0)
            if self.document is not None:
                raise DuplicateKeyError('duplicate open escalation')
            self.document = document

        async def update_one(self, _query, update):
            self.document['updated_at'] = update['$set']['updated_at']
            return type('Result', (), {'modified_count': 1})()

    db = MagicMock()
    field = Field()
    db.field_escalations = field
    db.projects.find_one = AsyncMock(return_value={'id': 'project-1'})
    db.units.find_one = AsyncMock(return_value={'id': 'unit-1', 'project_id': 'project-1'})
    db.buildings.find_one = AsyncMock(return_value={'name': 'בניין א'})
    db.floors.find_one = AsyncMock(return_value={'name': 'קומה 1'})
    db.project_memberships.find.return_value = Cursor([{'user_id': 'pm'}])
    notify = AsyncMock()
    monkeypatch.setattr(escalations_router, 'get_db', lambda: db)
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='management_team'))
    monkeypatch.setattr(
        escalations_router, '_get_project_membership',
        AsyncMock(return_value={'role': 'management_team', 'sub_role': 'site_manager'}),
    )
    monkeypatch.setattr(escalations_router, 'compute_spare_status', lambda *_: sample_status())
    monkeypatch.setattr(escalations_router, '_audit', AsyncMock())
    monkeypatch.setattr(escalations_router, 'create_defect_notification', notify)

    async def run():
        return await asyncio.gather(
            escalations_router.create_escalation(
                'project-1', {'unit_id': 'unit-1', 'text': 'הודעה אחת'},
                {'id': 'requester', 'name': 'יוסי'},
            ),
            escalations_router.create_escalation(
                'project-1', {'unit_id': 'unit-1', 'text': 'הודעה שתיים'},
                {'id': 'requester', 'name': 'יוסי'},
            ),
        )

    results = asyncio.run(run())
    assert field.insert_calls == 2
    assert field.document is not None
    assert len(field.document['notes']) == 1
    assert sorted([result['appended_note'] for result in results]) == [False, True]


def test_concurrent_resolution_only_one_request_audits_and_notifies(monkeypatch):
    class Field:
        def __init__(self):
            self.document = sample_escalation()

        async def find_one(self, *_args, **_kwargs):
            await asyncio.sleep(0)
            return self.document

        async def update_one(self, _query, update):
            await asyncio.sleep(0)
            if self.document['status'] != 'open':
                return type('Result', (), {'modified_count': 0})()
            self.document.update(update['$set'])
            return type('Result', (), {'modified_count': 1})()

    db = MagicMock()
    db.field_escalations = Field()
    audit = AsyncMock()
    notify = AsyncMock()
    monkeypatch.setattr(escalations_router, 'get_db', lambda: db)
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='project_manager'))
    monkeypatch.setattr(
        escalations_router, '_get_project_membership',
        AsyncMock(return_value={'role': 'project_manager', 'sub_role': None}),
    )
    monkeypatch.setattr(escalations_router, '_audit', audit)
    monkeypatch.setattr(escalations_router, 'create_defect_notification', notify)

    async def run():
        return await asyncio.gather(
            escalations_router.patch_escalation(
                'esc-1', {'action': 'done'}, {'id': 'pm-1', 'name': 'מנהל 1'},
            ),
            escalations_router.patch_escalation(
                'esc-1', {'action': 'done'}, {'id': 'pm-2', 'name': 'מנהל 2'},
            ),
            return_exceptions=True,
        )

    # The first caller wins the conditional status=open update; the loser
    # must return the documented conflict and produce no second side effect.
    results = asyncio.run(run())
    assert sum(not isinstance(result, HTTPException) for result in results) == 1
    assert sum(isinstance(result, HTTPException) and result.status_code == 409 for result in results) == 1
    assert audit.await_count == 1
    assert notify.await_count == 1


def test_unrelated_management_cannot_append_via_post(monkeypatch):
    db = MagicMock()
    db.projects.find_one = AsyncMock(return_value={'id': 'project-1'})
    db.units.find_one = AsyncMock(return_value={'id': 'unit-1', 'project_id': 'project-1'})
    db.buildings.find_one = AsyncMock(return_value={'name': 'בניין א'})
    db.floors.find_one = AsyncMock(return_value={'name': 'קומה 1'})
    db.field_escalations.find_one = AsyncMock(side_effect=[
        None,  # visibility-filtered existing lookup
        None,  # duplicate-key winner lookup (not visible)
    ])
    db.field_escalations.insert_one = AsyncMock(
        side_effect=DuplicateKeyError('duplicate open escalation'),
    )
    monkeypatch.setattr(escalations_router, 'get_db', lambda: db)
    monkeypatch.setattr(escalations_router, '_get_project_role', AsyncMock(return_value='management_team'))
    monkeypatch.setattr(
        escalations_router, '_get_project_membership',
        AsyncMock(return_value={'role': 'management_team', 'sub_role': 'site_manager'}),
    )
    monkeypatch.setattr(escalations_router, 'compute_spare_status', lambda *_: sample_status())

    with pytest.raises(HTTPException) as error:
        asyncio.run(escalations_router.create_escalation(
            'project-1',
            {'unit_id': 'unit-1', 'text': 'הודעה'},
            {'id': 'unrelated', 'name': 'מנהל אחר'},
        ))
    assert error.value.status_code == 403
    db.field_escalations.update_one.assert_not_called()


def test_open_unique_index_setup_is_best_effort(caplog):
    # Index failures must be logged, not propagated into startup.
    from unittest.mock import patch

    with patch('motor.motor_asyncio.AsyncIOMotorClient', return_value=MagicMock()):
        import server

    collection = MagicMock()
    collection.create_index = AsyncMock(side_effect=RuntimeError('index unavailable'))
    with patch.object(server, 'db', field_escalations=collection):
        asyncio.run(server._ensure_field_escalation_open_index())
    assert 'index unavailable' in caplog.text
    assert 'non-fatal' in caplog.text
    collection.index_information.assert_not_called()
    collection.create_index.assert_awaited_once_with(
        [('unit_id', 1), ('status', 1)],
        name='uniq_open_spare_escalation_per_unit',
        unique=True,
        partialFilterExpression={'type': 'spare_tiles', 'status': 'open'},
    )

    # Success likewise needs no post-create verification.
    collection.create_index = AsyncMock(return_value='uniq_open_spare_escalation_per_unit')
    with patch.object(server, 'db', field_escalations=collection):
        asyncio.run(server._ensure_field_escalation_open_index())
    collection.index_information.assert_not_called()