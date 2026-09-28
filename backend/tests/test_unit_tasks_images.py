import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from contractor_ops import projects_router
from contractor_ops.schemas import Task


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.sort_args = None

    def sort(self, field, direction):
        self.sort_args = (field, direction)
        self.rows = sorted(self.rows, key=lambda row: row.get(field, ''), reverse=direction == -1)
        return self

    async def to_list(self, _limit):
        return self.rows

    def __aiter__(self):
        async def entries():
            for row in self.rows:
                yield row
        return entries()


def test_unit_list_first_photo_count_filter_and_existing_fields():
    tasks = [
        {'id': 'a', 'project_id': 'p', 'unit_id': 'u', 'title': 'ליקוי א',
         'created_at': '2026-09-02', 'attachments_count': 3, 'assignee_id': 'worker'},
        {'id': 'b', 'project_id': 'p', 'unit_id': 'u', 'title': 'ליקוי ב',
         'created_at': '2026-09-01', 'attachments_count': 0},
    ]
    updates = [
        {'task_id': 'a', 'update_type': 'attachment', 'content_type': 'image/jpeg',
         'attachment_url': 's3://photo/new', 'created_at': '2026-09-03'},
        {'task_id': 'a', 'update_type': 'attachment', 'content_type': 'image/png',
         'attachment_url': 's3://photo/old', 'created_at': '2026-09-01'},
        {'task_id': 'a', 'update_type': 'attachment', 'content_type': 'image/webp',
         'attachment_url': 's3://photo/middle', 'created_at': '2026-09-02'},
        {'task_id': 'b', 'update_type': 'attachment', 'content_type': 'application/pdf',
         'attachment_url': '/api/uploads/file.pdf', 'created_at': '2026-09-04'},
        {'task_id': 'b', 'update_type': 'attachment', 'content_type': 'image/png',
         'attachment_url': '/api/uploads/deleted.png', 'created_at': '2026-09-05',
         'deletedAt': '2026-09-06'},
    ]
    db = MagicMock()
    db.units.find_one = AsyncMock(return_value={'id': 'u', 'project_id': 'p'})
    db.tasks.find.return_value = Cursor(tasks)
    db.project_companies.find.return_value = Cursor([])
    db.companies.find.return_value = Cursor([])
    db.project_memberships.find.return_value = Cursor([
        {'user_id': 'worker', 'user_name': 'אחראי', 'company_id': None},
    ])
    db.users.find.return_value = Cursor([])
    image_cursor = None

    def find_images(query, projection):
        nonlocal image_cursor
        assert query == {
            'task_id': {'$in': ['a', 'b']}, 'update_type': 'attachment',
            'content_type': {'$regex': '^image/'}, 'deletedAt': {'$exists': False},
        }
        assert projection == {
            '_id': 0, 'task_id': 1, 'attachment_url': 1, 'created_at': 1,
        }
        image_cursor = Cursor([
            row for row in updates
            if row['task_id'] in query['task_id']['$in']
            and row['update_type'] == 'attachment'
            and row['content_type'].startswith('image/')
            and 'deletedAt' not in row
        ])
        return image_cursor

    db.task_updates.find.side_effect = find_images
    with (
        patch.object(projects_router, 'get_db', return_value=db),
        patch.object(projects_router, '_check_project_read_access', new=AsyncMock()),
        patch('services.object_storage.resolve_url', side_effect=lambda ref: f'/resolved/{ref}') as resolve,
    ):
        result = asyncio.run(projects_router.list_unit_tasks('u', None, None, {'id': 'pm'}))

    by_id = {item['id']: item for item in result}
    assert db.task_updates.find.call_count == 1
    assert image_cursor.sort_args == ('created_at', 1)
    assert by_id['a']['image_url'] == '/resolved/s3://photo/old'
    assert by_id['a']['image_count'] == 3
    assert by_id['b']['image_url'] is None
    assert by_id['b']['image_count'] == 0
    resolve.assert_called_once_with('s3://photo/old')
    for task in tasks:
        assert Task(**task).dict().items() <= by_id[task['id']].items()
    assert by_id['a']['assignee_name'] == 'אחראי'


def test_unit_list_without_tasks_skips_image_query():
    db = MagicMock()
    db.units.find_one = AsyncMock(return_value={'id': 'u', 'project_id': 'p'})
    db.tasks.find.return_value = Cursor([])
    with patch.object(projects_router, 'get_db', return_value=db), patch.object(
        projects_router, '_check_project_read_access', new=AsyncMock()
    ):
        result = asyncio.run(projects_router.list_unit_tasks('u', None, None, {'id': 'pm'}))
    assert result == []
    db.task_updates.find.assert_not_called()


def test_unknown_unit_returns_404_before_tasks_query():
    db = MagicMock()
    db.units.find_one = AsyncMock(return_value=None)
    with patch.object(projects_router, 'get_db', return_value=db), pytest.raises(HTTPException) as exc:
        asyncio.run(projects_router.list_unit_tasks('u', None, None, {'id': 'pm'}))
    assert (exc.value.status_code, exc.value.detail) == (404, 'Unit not found')
    db.tasks.find.assert_not_called()


def test_unauthorized_unit_checks_access_before_tasks_query():
    db = MagicMock()
    db.units.find_one = AsyncMock(return_value={'id': 'u', 'project_id': 'p'})
    access = AsyncMock(side_effect=HTTPException(status_code=403, detail='Forbidden'))
    user = {'id': 'other'}
    with patch.object(projects_router, 'get_db', return_value=db), patch.object(
        projects_router, '_check_project_read_access', new=access
    ), pytest.raises(HTTPException) as exc:
        asyncio.run(projects_router.list_unit_tasks('u', None, None, user))
    assert exc.value.status_code == 403
    access.assert_awaited_once_with(user, 'p')
    db.tasks.find.assert_not_called()


def test_unit_project_falls_back_to_building():
    db = MagicMock()
    db.units.find_one = AsyncMock(return_value={'id': 'u', 'building_id': 'b'})
    db.buildings.find_one = AsyncMock(return_value={'project_id': 'p'})
    db.tasks.find.return_value = Cursor([])
    access = AsyncMock()
    with patch.object(projects_router, 'get_db', return_value=db), patch.object(
        projects_router, '_check_project_read_access', new=access
    ):
        assert asyncio.run(projects_router.list_unit_tasks('u', None, None, {'id': 'pm'})) == []
    db.buildings.find_one.assert_awaited_once_with({'id': 'b'}, {'_id': 0, 'project_id': 1})
    access.assert_awaited_once_with({'id': 'pm'}, 'p')


def test_handover_proof_images_merge_and_other_proofs_are_ignored():
    db = MagicMock()
    db.units.find_one = AsyncMock(return_value={'id': 'u', 'project_id': 'p'})
    db.tasks.find.return_value = Cursor([
        {'id': 'h', 'project_id': 'p', 'title': 'מסירה', 'handover_protocol_id': 'hp',
         'proof_urls': ['s3://a', 's3://b']},
        {'id': 'regular', 'project_id': 'p', 'title': 'רגיל', 'proof_urls': ['s3://orphan']},
    ])
    db.task_updates.find.return_value = Cursor([
        {'task_id': 'h', 'attachment_url': 's3://b', 'created_at': '2026-09-01'},
        {'task_id': 'h', 'attachment_url': 's3://c', 'created_at': '2026-09-02'},
    ])
    with (
        patch.object(projects_router, 'get_db', return_value=db),
        patch.object(projects_router, '_check_project_read_access', new=AsyncMock()),
        patch('services.object_storage.resolve_urls_in_doc', side_effect=lambda doc: doc),
        patch('services.object_storage.resolve_url', side_effect=lambda ref: f'/url/{ref}') as resolve,
    ):
        result = asyncio.run(projects_router.list_unit_tasks('u', None, None, {'id': 'pm'}))
    items = {item['id']: item for item in result}
    assert (items['h']['image_url'], items['h']['image_count']) == ('/url/s3://a', 3)
    assert (items['regular']['image_url'], items['regular']['image_count']) == (None, 0)
    resolve.assert_called_once_with('s3://a')