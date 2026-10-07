"""Monthly accounts exclude matrix metadata without mutating stored settings."""
from copy import deepcopy
from contractor_ops.monthly_close import account_stages, known_settings, validate_settings


def test_account_stages_keeps_status_and_legacy_in_order():
    stages = [{'id': 'legacy'}, {'id': 'tag', 'type': 'tag'},
              {'id': 'status', 'type': 'status'}, {'id': 'tag2', 'type': 'tag'}]
    original = deepcopy(stages)
    assert account_stages(stages) == [stages[0], stages[2]]
    assert stages == original


def test_known_settings_filters_stale_ids_without_mutation():
    settings = {'stage_companies': {'work': 'c1', 'unassigned': None,
                                   'tag': None, 'deleted': 'c2'},
                'contractor_visible': True, 'updated_at': '2026-10-07',
                'updated_by': 'pm'}
    original = deepcopy(settings)
    clean = known_settings(settings, [{'id': 'work'}, {'id': 'unassigned'}])
    assert clean == {**settings, 'stage_companies': {'work': 'c1', 'unassigned': None}}
    assert settings == original
    assert clean['stage_companies'] is not settings['stage_companies']


def test_settings_round_trip_accepts_cleaned_tag_mapping():
    stages = account_stages([{'id': 'work'}, {'id': 'custom_tag', 'type': 'tag'}])
    stale = {'stage_companies': {'work': 'c1', 'custom_tag': None},
             'contractor_visible': True}
    clean = known_settings(stale, stages)
    assert validate_settings(clean, {s['id'] for s in stages}, {'c1'}) == {
        'stage_companies': {'work': 'c1'}, 'contractor_visible': True}
