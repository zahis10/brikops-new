import asyncio
import os
import sys
import uuid

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from contractor_ops.spare_tiles import (
    SPARE_OVERALL_LABELS,
    compute_spare_status,
    default_spare_settings,
    matrix_spare_summary,
    validate_spare_settings,
)
from contractor_ops import spare_tiles_router


PROFILE_ID = str(uuid.uuid4())


def settings(target=10, margin=10):
    return {
        'categories': [{'name': 'ריצוף יבש', 'measure': 'tiles'}],
        'profiles': [{
            'id': PROFILE_ID,
            'name': '3 חדרים',
            'targets': {} if target == 0 else {'ריצוף יבש': target},
        }],
        'margin_pct': margin,
    }


def status(count=None, notes='', target=10, margin=10, profile_id=PROFILE_ID, entered=False):
    unit = {'spare_profile_id': profile_id}
    if count is not None:
        unit['spare_tiles'] = [{
            'type': 'ריצוף יבש',
            'count': count,
            'notes': notes,
            **({'entered': True} if entered else {}),
        }]
    return compute_spare_status(unit, settings(target, margin))


def test_defaults_are_fresh():
    first = default_spare_settings()
    first['categories'][0]['name'] = 'changed'
    assert default_spare_settings()['categories'][0]['name'] == 'ריצוף יבש'


def test_default_categories_are_all_tiles():
    assert {
        category['measure']
        for category in default_spare_settings()['categories']
    } == {'tiles'}


def test_short_borderline_and_ok():
    short = status(8)
    assert short['overall'] == 'short'
    assert short['categories'][0]['missing'] == 2
    assert status(3, target=3)['overall'] == 'borderline'
    assert status(7, target=5)['overall'] == 'ok'


def test_two_tiles_against_twelve_is_short_by_ten():
    result = status(2, target=12)
    assert result['overall'] == 'short'
    assert result['categories'][0]['missing'] == 10


def test_not_entered_and_zero_with_notes():
    assert status()['overall'] == 'not_entered'
    assert status(0)['overall'] == 'not_entered'
    entered = status(0, notes='נבדק')
    assert entered['categories'][0]['status'] == 'short'
    assert entered['categories'][0]['actual'] == 0


def test_confirmed_zero_is_entered_and_short():
    result = status(0, entered=True)
    row = result['categories'][0]
    assert result['overall'] == 'short'
    assert row['actual'] == 0
    assert row['entered'] is True
    assert row['missing'] == row['target'] == 10
    assert status(0)['categories'][0]['entered'] is False


def test_no_target_and_no_profile():
    confirmed_zero = status(0, target=0, entered=True)
    confirmed_zero_row = confirmed_zero['categories'][0]
    assert confirmed_zero['overall'] == 'short'
    assert confirmed_zero_row == {
        'name': 'ריצוף יבש',
        'measure': 'tiles',
        'target': None,
        'actual': 0,
        'status': 'short',
        'missing': None,
        'entered': True,
    }
    assert status(0, target=0)['overall'] == 'not_entered'
    legacy_note = status(0, notes='legacy note', target=0)
    assert legacy_note['overall'] == 'recorded'
    assert legacy_note['entered_count'] == legacy_note['applicable_count'] == 1
    recorded = status(4, target=0)
    assert recorded['overall'] == 'recorded'
    assert recorded['categories'][0] == {
        'name': 'ריצוף יבש',
        'measure': 'tiles',
        'target': None,
        'actual': 4,
        'status': 'recorded',
        'missing': None,
        'entered': True,
    }
    assert status(4, profile_id=None)['overall'] == 'no_profile'
    assert status(4, profile_id=str(uuid.uuid4()))['overall'] == 'no_profile'


def test_profile_with_empty_categories_has_no_target_overall():
    result = compute_spare_status(
        {'spare_profile_id': PROFILE_ID},
        {
            'categories': [],
            'profiles': [{'id': PROFILE_ID, 'name': 'פרופיל', 'targets': {}}],
            'margin_pct': 10,
        },
    )
    assert result['overall'] == 'no_target'
    assert result['categories'] == []


def test_custom_type_appended_and_overall_precedence():
    config = {
        'categories': [
            {'name': 'א', 'measure': 'tiles'},
            {'name': 'ב', 'measure': 'sqm'},
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
    assert result['categories'][-1]['status'] == 'recorded'
    assert result['overall'] == 'borderline'

    config['profiles'][0]['targets']['א'] = 3
    result = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [{'type': 'א', 'count': 2, 'notes': ''}],
    }, config)
    assert result['overall'] == 'short'


def test_margin_zero_still_has_one_item_band():
    assert status(5, target=5, margin=0)['overall'] == 'borderline'


def test_tracking_only_overall_precedence():
    config = {
        'categories': [
            {'name': 'א', 'measure': 'tiles'},
            {'name': 'ב', 'measure': 'tiles'},
            {'name': 'ג', 'measure': 'tiles'},
        ],
        'profiles': [{'id': PROFILE_ID, 'name': 'מעקב', 'targets': {}}],
        'margin_pct': 10,
    }
    with_short = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [
            {'type': 'א', 'count': 3},
            {'type': 'ג', 'count': 0, 'entered': True},
        ],
    }, config)
    assert with_short['overall'] == 'short'

    recorded = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [{'type': 'א', 'count': 3}],
    }, config)
    assert recorded['overall'] == 'not_entered'
    assert recorded['entered_count'] == 1
    assert recorded['applicable_count'] == 3

    empty = compute_spare_status({'spare_profile_id': PROFILE_ID}, config)
    assert empty['overall'] == 'not_entered'

    complete = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [
            {'type': 'א', 'count': 3},
            {'type': 'ב', 'count': 2},
            {'type': 'ג', 'count': 1},
        ],
    }, config)
    assert complete['overall'] == 'recorded'
    assert complete['entered_count'] == complete['applicable_count'] == 3


def test_spare_overall_labels_for_tracking_only_profiles():
    assert SPARE_OVERALL_LABELS['recorded'] == 'הוזן'
    assert SPARE_OVERALL_LABELS['no_target'] == 'לא הוזן'


def valid_body():
    return {
        'categories': [{'name': 'ריצוף', 'measure': 'tiles'}],
        'profiles': [{'name': '3 חדרים', 'targets': {'ריצוף': 4}}],
        'margin_pct': 10,
    }


@pytest.mark.parametrize('mutate', [
    lambda body: body.update(categories=[
        {'name': 'ריצוף', 'measure': 'tiles'},
        {'name': '  ריצוף  ', 'measure': 'sqm'},
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


def test_cartons_measure_normalizes_to_tiles():
    body = valid_body()
    body['categories'][0]['measure'] = 'cartons'
    result = validate_spare_settings(body)
    assert result['categories'] == [{'name': 'ריצוף', 'measure': 'tiles'}]


def test_unknown_measure_is_rejected():
    body = valid_body()
    body['categories'][0]['measure'] = 'boxes'
    with pytest.raises(HTTPException) as error:
        validate_spare_settings(body)
    assert error.value.status_code == 422
    assert error.value.detail == 'יחידת מידה לא חוקית'


def test_matrix_spare_summary_short_categories_and_missing_total():
    config = {
        'categories': [
            {'name': 'ריצוף יבש', 'measure': 'tiles'},
            {'name': 'חיפוי מטבח', 'measure': 'sqm'},
        ],
        'profiles': [{
            'id': PROFILE_ID,
            'name': 'פרופיל א',
            'targets': {'ריצוף יבש': 12, 'חיפוי מטבח': 5},
        }],
        'margin_pct': 10,
    }
    result = matrix_spare_summary(
        {
            'spare_profile_id': PROFILE_ID,
            'spare_tiles': [
                {'type': 'ריצוף יבש', 'count': 2},
                {'type': 'חיפוי מטבח', 'count': 3},
            ],
        },
        config,
    )
    assert result == {
        'overall': 'short',
        'profile': 'פרופיל א',
        'entered_count': 2,
        'applicable_count': 2,
        'short': [
            {'name': 'ריצוף יבש', 'missing': 10, 'measure': 'tiles'},
            {'name': 'חיפוי מטבח', 'missing': 2, 'measure': 'sqm'},
        ],
        'not_entered': [],
        'borderline': [],
        'recorded': [],
        'unfilled': [],
        'categories_total': 2,
        'missing_total': 12,
    }


def test_matrix_spare_summary_confirmed_zero_without_target():
    result = matrix_spare_summary(
        {
            'spare_profile_id': PROFILE_ID,
            'spare_tiles': [{
                'type': 'ריצוף יבש',
                'count': 0,
                'notes': '',
                'entered': True,
            }],
        },
        settings(target=0),
    )
    assert result['overall'] == 'short'
    assert result['short'] == [{
        'name': 'ריצוף יבש',
        'missing': None,
        'measure': 'tiles',
    }]
    assert result['missing_total'] == 0


def test_matrix_spare_summary_tracking_only_and_no_target_categories():
    tracking_config = {
        'categories': [
            {'name': 'א', 'measure': 'tiles'},
            {'name': 'ב', 'measure': 'tiles'},
            {'name': 'ג', 'measure': 'tiles'},
        ],
        'profiles': [{'id': PROFILE_ID, 'name': 'מעקב', 'targets': {}}],
        'margin_pct': 10,
    }
    tracking = matrix_spare_summary({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [
            {'type': 'א', 'count': 3},
            {'type': 'ב', 'count': 2},
        ],
    }, tracking_config)
    assert tracking['overall'] == 'not_entered'
    assert tracking['recorded'] == ['א', 'ב']
    assert tracking['unfilled'] == ['ג']
    assert tracking['categories_total'] == 3
    assert tracking['entered_count'] == 2
    assert tracking['applicable_count'] == 3

    targets_config = {
        **tracking_config,
        'profiles': [{
            'id': PROFILE_ID,
            'name': 'יעדים',
            'targets': {'א': 1, 'ב': 1},
        }],
    }
    with_targets = matrix_spare_summary({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [
            {'type': 'א', 'count': 3},
            {'type': 'ב', 'count': 3},
        ],
    }, targets_config)
    assert with_targets['overall'] == 'not_entered'
    assert with_targets['recorded'] == []
    assert with_targets['unfilled'] == ['ג']
    assert with_targets['entered_count'] == 2
    assert with_targets['applicable_count'] == 3

    unassigned = matrix_spare_summary({
        'spare_tiles': [
            {'type': 'א', 'count': 3},
            {'type': 'ב', 'count': 2},
        ],
    }, tracking_config)
    assert unassigned['overall'] == 'no_profile'
    assert unassigned['recorded'] == ['א', 'ב']
    assert unassigned['unfilled'] == ['ג']
    assert unassigned['entered_count'] == 2
    assert unassigned['applicable_count'] == 3


def test_progress_counts_every_category_for_targeted_tracking_and_unassigned_units():
    categories = [
        {'name': name, 'measure': 'tiles'}
        for name in ['א', 'ב', 'ג', 'ד', 'ה']
    ]
    targeted = {
        'categories': categories,
        'profiles': [{
            'id': PROFILE_ID,
            'name': 'יעדים',
            'targets': {name: 5 for name in ['א', 'ב', 'ג', 'ד']},
        }],
        'margin_pct': 10,
    }
    partial = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [{'type': 'א', 'count': 8}, {'type': 'ה', 'count': 2}],
    }, targeted)
    assert partial['overall'] == 'not_entered'
    assert partial['entered_count'] == 2
    assert partial['applicable_count'] == 5

    explicit_zero = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [{'type': 'א', 'count': 0, 'entered': True}],
    }, targeted)
    assert explicit_zero['entered_count'] == 1
    assert explicit_zero['overall'] == 'short'

    borderline_before_missing = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [{'type': 'א', 'count': 5}],
    }, targeted)
    assert borderline_before_missing['overall'] == 'borderline'

    summary = matrix_spare_summary({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [{'type': 'א', 'count': 8}, {'type': 'ה', 'count': 2}],
    }, targeted)
    assert summary['unfilled'] == ['ב', 'ג', 'ד']

    complete_targeted = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [
            {'type': name, 'count': 6}
            for name in ['א', 'ב', 'ג', 'ד']
        ] + [{'type': 'ה', 'count': 1}],
    }, targeted)
    assert complete_targeted['overall'] == 'ok'
    assert complete_targeted['entered_count'] == 5
    assert complete_targeted['applicable_count'] == 5

    missing_no_target = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [
            {'type': name, 'count': 6}
            for name in ['א', 'ב', 'ג', 'ד']
        ],
    }, targeted)
    assert missing_no_target['overall'] == 'not_entered'
    assert missing_no_target['entered_count'] == 4
    assert missing_no_target['applicable_count'] == 5

    tracking = {**targeted, 'profiles': [{
        'id': PROFILE_ID, 'name': 'מעקב', 'targets': {},
    }]}
    partial_tracking = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [{'type': name, 'count': 1} for name in ['א', 'ב', 'ג', 'ד']],
    }, tracking)
    assert partial_tracking['overall'] == 'not_entered'
    assert partial_tracking['entered_count'] == 4
    assert partial_tracking['applicable_count'] == 5

    complete_tracking = compute_spare_status({
        'spare_profile_id': PROFILE_ID,
        'spare_tiles': [{'type': name, 'count': 1} for name in ['א', 'ב', 'ג', 'ד', 'ה']],
    }, tracking)
    assert complete_tracking['overall'] == 'recorded'

    unassigned = matrix_spare_summary({
        'spare_tiles': [{'type': 'א', 'count': 1}],
    }, tracking)
    assert unassigned['overall'] == 'no_profile'
    assert unassigned['entered_count'] == 1
    assert unassigned['applicable_count'] == 5
    assert unassigned['unfilled'] == ['ב', 'ג', 'ד', 'ה']


def test_matrix_spare_summary_short_also_surfaces_borderline_categories():
    config = {
        'categories': [
            {'name': 'ריצוף יבש', 'measure': 'tiles'},
            {'name': 'חיפוי מטבח', 'measure': 'sqm'},
        ],
        'profiles': [{
            'id': PROFILE_ID,
            'name': 'פרופיל א',
            'targets': {'ריצוף יבש': 10, 'חיפוי מטבח': 5},
        }],
        'margin_pct': 10,
    }
    result = matrix_spare_summary(
        {
            'spare_profile_id': PROFILE_ID,
            'spare_tiles': [
                {'type': 'ריצוף יבש', 'count': 8},
                {'type': 'חיפוי מטבח', 'count': 5},
            ],
        },
        config,
    )
    assert result['overall'] == 'short'
    assert result['short'] == [
        {'name': 'ריצוף יבש', 'missing': 2, 'measure': 'tiles'},
    ]
    assert result['borderline'] == ['חיפוי מטבח']


def test_matrix_spare_summary_ok():
    result = matrix_spare_summary(
        {
            'spare_profile_id': PROFILE_ID,
            'spare_tiles': [{'type': 'ריצוף יבש', 'count': 12}],
        },
        settings(target=10, margin=10),
    )
    assert result['overall'] == 'ok'
    assert result['profile'] == '3 חדרים'
    assert result['short'] == []
    assert result['borderline'] == []
    assert result['missing_total'] == 0


def test_matrix_spare_summary_no_profile():
    result = matrix_spare_summary(
        {'spare_tiles': [{'type': 'ריצוף יבש', 'count': 2}]},
        settings(),
    )
    assert result['overall'] == 'no_profile'
    assert result['profile'] is None
    assert result['short'] == []


class _Result:
    def __init__(self, modified_count=1):
        self.modified_count = modified_count


class _Cursor:
    def __init__(self, values):
        self.values = values

    async def to_list(self, _limit):
        return self.values


def test_profile_assignment_updates_matching_unit_without_lock(monkeypatch):
    settings = {
        'categories': [{'name': 'ריצוף', 'measure': 'tiles'}],
        'profiles': [{'id': PROFILE_ID, 'name': 'פרופיל', 'targets': {}}],
        'margin_pct': 10,
    }
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
    assert len(Db.units.calls) == 1


def test_stale_settings_editor_is_rejected(monkeypatch):
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