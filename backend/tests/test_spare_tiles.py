import asyncio
import os
import sys
import uuid

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from contractor_ops.spare_tiles import (
    compute_spare_status,
    default_spare_settings,
    validate_spare_settings,
)
from contractor_ops import spare_tiles_router


PROFILE_ID = str(uuid.uuid4())


def settings(target=10, margin=10):
    return {
        'categories': [{'name': 'ריצוף יבש', 'measure': 'tiles'}],
        'profiles': [{'id': PROFILE_ID, 'name': '3 חדרים', 'targets': {'ריצוף יבש': target}}],
        'margin_pct': margin,
    }


def status(count=None, notes='', target=10, margin=10, profile_id=PROFILE_ID):
    unit = {'spare_profile_id': profile_id}
    if count is not None:
        unit['spare_tiles'] = [{'type': 'ריצוף יבש', 'count': count, 'notes': notes}]
    return compute_spare_status(unit, settings(target, margin))


def test_defaults_are_fresh():
    first = default_spare_settings()
    first['categories'][0]['name'] = 'changed'
    assert default_spare_settings()['categories'][0]['name'] == 'ריצוף יבש'


def test_short_borderline_and_ok():
    short = status(8)
    assert short['overall'] == 'short'
    assert short['categories'][0]['missing'] == 2
    assert status(3, target=3)['overall'] == 'borderline'
    assert status(7, target=5)['overall'] == 'ok'


def test_not_entered_and_zero_with_notes():
    assert status()['overall'] == 'not_entered'
    assert status(0)['overall'] == 'not_entered'
    entered = status(0, notes='נבדק')
    assert entered['categories'][0]['status'] == 'short'
    assert entered['categories'][0]['actual'] == 0


def test_no_target_and_no_profile():
    assert status(4, target=0)['overall'] == 'no_target'
    assert status(4, profile_id=None)['overall'] == 'no_profile'
    assert status(4, profile_id=str(uuid.uuid4()))['overall'] == 'no_profile'


def test_custom_type_appended_and_overall_precedence():
    config = {
        'categories': [
            {'name': 'א', 'measure': 'tiles'},
            {'name': 'ב', 'measure': 'cartons'},
        ],
        'profiles': [{
            'id': PROFILE_ID,
            'name': 'פרופיל',
            'targets': {'א': 2, 'ב': 5},
        }],
        'margin_pct': 10,
    }
    result = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [
            {'type': 'א', 'count': 2, 'notes': ''},
            {'type': 'מותאם', 'count': 4, 'notes': ''},
        ],
    }, config)
    assert [row['name'] for row in result['categories']] == ['א', 'ב', 'מותאם']
    assert result['categories'][-1]['status'] == 'no_target'
    assert result['overall'] == 'not_entered'

    config['profiles'][0]['targets']['א'] = 3
    result = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [{'type': 'א', 'count': 2, 'notes': ''}],
    }, config)
    assert result['overall'] == 'short'


def test_margin_zero_still_has_one_item_band():
    assert status(5, target=5, margin=0)['overall'] == 'borderline'


def valid_body():
    return {
        'categories': [{'name': 'ריצוף', 'measure': 'tiles'}],
        'profiles': [{'name': '3 חדרים', 'targets': {'ריצוף': 4}}],
        'margin_pct': 10,
    }


@pytest.mark.parametrize('mutate', [
    lambda body: body.update(categories=[
        {'name': 'ריצוף', 'measure': 'tiles'},
        {'name': '  ריצוף  ', 'measure': 'cartons'},
    ]),
    lambda body: body.update(profiles=[
        {'name': str(index), 'targets': {}} for index in range(11)
    ]),
    lambda body: body['categories'][0].update(measure='units'),
    lambda body: body['profiles'][0]['targets'].update({'ריצוף': -1}),
    lambda body: body['categories'][0].update(name='א' * 51),
    lambda body: body['profiles'][0].update(name='א' * 41),
    lambda body: body['profiles'][0]['targets'].update({'ריצוף': 10001}),
])
def test_validation_rejections(mutate):
    body = valid_body()
    mutate(body)
    with pytest.raises(HTTPException) as error:
        validate_spare_settings(body)
    assert error.value.status_code == 422


def test_validation_preserves_uuid_and_drops_deleted_category_targets():
    body = valid_body()
    body['profiles'][0]['id'] = PROFILE_ID
    body['profiles'][0]['targets']['קטגוריה שנמחקה'] = 8
    result = validate_spare_settings(body)
    assert result['profiles'][0]['id'] == PROFILE_ID
    assert result['profiles'][0]['targets'] == {'ריצוף': 4}


class _Result:
    def __init__(self, modified_count=1):
        self.modified_count = modified_count


class _Cursor:
    def __init__(self, values):
        self.values = values

    async def to_list(self, _limit):
        return self.values


class _Locks:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.acquire_calls = []
        self.release_calls = []
        self.current = None

    async def insert_one(self, document):
        self.acquire_calls.append(document)
        if self.current is not None:
            raise spare_tiles_router.DuplicateKeyError('busy')
        response = next(self.responses)
        if response == 'owner':
            self.current = dict(document)
            return _Result()
        if isinstance(response, dict):
            raise spare_tiles_router.DuplicateKeyError('busy')

    async def find_one(self, query, _projection):
        if self.current and self.current.get('token') == query.get('token'):
            return {'_id': query['_id']}
        return None

    async def delete_one(self, query):
        self.release_calls.append(query)
        if self.current and self.current.get('token') == query.get('token'):
            self.current = None


def test_project_lock_releases_token_when_the_protected_work_raises():
    locks = _Locks(['owner'])

    class Db:
        spare_tile_locks = locks

    async def protected():
        with pytest.raises(RuntimeError):
            async with spare_tiles_router._project_write_lock(Db(), 'project'):
                raise RuntimeError('boom')

    asyncio.run(protected())
    assert len(locks.acquire_calls) == 1
    assert locks.release_calls[0]['_id'] == 'project'
    assert locks.release_calls[0]['token'] == locks.acquire_calls[0]['token']


def test_project_lock_retries_after_another_writer_then_acquires(monkeypatch):
    locks = _Locks([{'token': 'other-writer'}, 'owner'])

    class Db:
        spare_tile_locks = locks

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(spare_tiles_router.asyncio, 'sleep', no_wait)

    async def protected():
        async with spare_tiles_router._project_write_lock(Db(), 'project'):
            pass

    asyncio.run(protected())
    assert len(locks.acquire_calls) == 2
    assert locks.acquire_calls[0]['_id'] == 'project'
    assert len(locks.release_calls) == 1


def test_mutex_is_not_stolen_after_simulated_time_passage(monkeypatch):
    locks = _Locks(['owner', 'owner'])

    class Db:
        spare_tile_locks = locks

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(spare_tiles_router.asyncio, 'sleep', no_wait)

    async def protected():
        async with spare_tiles_router._project_write_lock(Db(), 'project') as first:
            assert 'expires_at' not in locks.current
            await spare_tiles_router.asyncio.sleep(60 * 60 * 24)
            with pytest.raises(HTTPException) as error:
                async with spare_tiles_router._project_write_lock(Db(), 'project'):
                    pass
            assert error.value.status_code == 409
            await first.assert_owned()
        async with spare_tiles_router._project_write_lock(Db(), 'project'):
            pass

    asyncio.run(protected())
    assert len(locks.release_calls) == 2


def test_profile_assignment_holds_the_project_lease_for_its_write(monkeypatch):
    settings = {
        'categories': [{'name': 'ריצוף', 'measure': 'tiles'}],
        'profiles': [{'id': PROFILE_ID, 'name': 'פרופיל', 'targets': {}}],
        'margin_pct': 10,
    }
    locks = _Locks(['owner'])

    class Projects:
        async def find_one(self, *_args):
            return {'id': 'project', 'spare_settings': settings}

    class Units:
        def __init__(self):
            self.calls = []

        def find(self, *_args):
            return _Cursor([{'id': 'unit', 'spare_profile_id': None}])

        async def update_many(self, query, update):
            self.calls.append((query, update))
            return _Result(1)

    class Db:
        projects = Projects()
        units = Units()
        spare_tile_locks = locks

    async def allow_write(*_args):
        return None

    async def no_audit(*_args):
        return None

    monkeypatch.setattr(spare_tiles_router, 'get_db', lambda: Db())
    monkeypatch.setattr(spare_tiles_router, '_require_write', allow_write)
    monkeypatch.setattr(spare_tiles_router, '_audit', no_audit)
    result = asyncio.run(spare_tiles_router.patch_spare_profile_units(
        'project', PROFILE_ID, {'add': ['unit'], 'remove': []}, {'id': 'user'},
    ))
    assert result == {'added': 1, 'removed': 0}
    assert len(locks.acquire_calls) == 1
    assert len(locks.release_calls) == 1


def test_stale_settings_editor_is_rejected_after_lock_reload(monkeypatch):
    locks = _Locks(['owner'])
    current_settings = {
        'categories': [{'name': 'ריצוף', 'measure': 'tiles'}],
        'profiles': [],
        'margin_pct': 10,
        'updated_at': '2026-09-03T12:00:00+00:00',
        'updated_by': 'other',
    }

    class Projects:
        def __init__(self):
            self.update_calls = []

        async def find_one(self, *_args):
            return {'id': 'project', 'spare_settings': current_settings}

        async def update_one(self, query, update):
            self.update_calls.append((query, update))
            return _Result(1)

    class Db:
        projects = Projects()
        spare_tile_locks = locks

    async def allow_write(*_args):
        return None

    db = Db()
    monkeypatch.setattr(spare_tiles_router, 'get_db', lambda: db)
    monkeypatch.setattr(spare_tiles_router, '_require_write', allow_write)
    with pytest.raises(HTTPException) as error:
        asyncio.run(spare_tiles_router.put_spare_settings(
            'project',
            {
                'categories': [{'name': 'ריצוף', 'measure': 'tiles'}],
                'profiles': [],
                'margin_pct': 10,
                'updated_at': '2026-09-03T11:00:00+00:00',
            },
            {'id': 'user'},
        ))
    assert error.value.status_code == 409
    assert db.projects.update_calls == []
    assert len(locks.acquire_calls) == 1
    assert len(locks.release_calls) == 1