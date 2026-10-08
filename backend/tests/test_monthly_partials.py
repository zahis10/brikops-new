"""Partial apartment payments: pure in-memory regression coverage."""
import pytest
from contractor_ops.contract_items import attach_contract_items
from contractor_ops.monthly_partials import apply_partials, partial_pct
from test_monthly_close import inputs


def fixture(status='partial', pct=70, prior=None, applying=True, completed=False):
    data = inputs()
    data['cells'] = [{'unit_id': 'u4', 'stage_id': 's1', 'status': status, 'progress_pct': pct,
                      'audit': [{'actor_name': 'מנהל'}], 'last_updated_at': '2026-09-06T10:00:00+00:00'}]
    if prior is not None:
        data['snapshots'] = [{'month': '2026-08', 'contractors': [{'company_id': 'c1',
            'stages': [{'stage_id': 's1', 'partial_paid': {'u4': prior}}]}]}]
    stage = {'stage_id': 's1', 'title': 'אינסטלציה', 'total_units': 6, 'still_unit_ids': [],
             'unit_ids_this_month': ['u4'] if completed else [],
             'evidence': [{'unit_id': 'u4'}] if completed else []}
    account = {'month': '2026-09', 'applying': applying, 'contractors': [
        {'company_id': 'c1', 'name': 'קבלן', 'stages': [stage], 'corrections': []}]}
    return account, data, stage


@pytest.mark.parametrize('cell,expected', [
    ({'status': 'completed', 'progress_pct': 70}, 0),
    ({'status': 'partial', 'progress_pct': 70}, 70),
    ({'status': 'in_progress', 'progress_pct': 70}, 70),
    ({'status': 'pending_review', 'progress_pct': 70}, 70),
    ({'status': 'not_done', 'progress_pct': 70}, 0),
    ({'status': 'not_relevant', 'progress_pct': 70}, 0),
    ({'status': 'partial', 'progress_pct': None}, 0),
    ({'status': 'partial', 'progress_pct': 0}, 0),
    ({'status': 'partial', 'progress_pct': 100}, 0),
    (None, 0),
])
def test_partial_pct(cell, expected):
    assert partial_pct(cell) == expected


def test_first_month_partial():
    account, data, stage = fixture(applying=False)
    assert apply_partials(account, data) is account
    assert (stage['this_month'], stage['cumulative'], stage['pct']) == (0.7, 0.7, 12)
    assert stage['partials'] == [{'unit_id': 'u4', 'unit_no': '4', 'floor_id': 'f2',
        'floor_number': 2, 'building_id': 'b2', 'building_name': 'מגדל ב', 'stage_id': 's1',
        'pct': 70, 'prior_pct': 0, 'delta': 0.7, 'source': 'manual',
        'actor_name': 'מנהל', 'updated_at': '2026-09-06T10:00:00+00:00'}]
    assert stage['partial_paid'] == {'u4': 70} and stage['partial_count'] == 1
    assert account['contractors'][0]['totals'] == {'this_month': 0.7, 'cumulative': 0.7}
    assert account['kpis'] == {'this_month': 0.7, 'corrections': 0}
    assert not account['contractors'][0]['corrections']


def test_completion_pays_remaining_share():
    account, data, stage = fixture('completed', None, prior=70, completed=True)
    apply_partials(account, data)
    assert stage['evidence'] == [{'unit_id': 'u4', 'prior_pct': 70, 'fraction': 0.3}]
    assert (stage['this_month'], stage['cumulative']) == (0.3, 1.0)
    assert stage['partial_paid'] == {} and stage['partials'] == []
    assert stage['unit_fractions'] == {'u4': 1.0}
    assert stage['prev_fractions'] == {'u4': 0.7}


def test_reduction_adds_negative_correction():
    account, data, stage = fixture(pct=50, prior=70)
    apply_partials(account, data)
    corrections = account['contractors'][0]['corrections']
    assert len(corrections) == 1
    assert {k: corrections[0][k] for k in ('reason', 'delta', 'pct', 'prior_pct')} == {
        'reason': 'partial_reduced', 'delta': -0.2, 'pct': 50, 'prior_pct': 70}
    assert corrections[0]['counted_in_month'] == '2026-08'
    assert (stage['this_month'], stage['cumulative']) == (0, 0.5)
    assert stage['partial_paid'] == {'u4': 50}
    assert account['kpis']['corrections'] == 1


def test_inactive_month_keeps_paid_share():
    account, data, stage = fixture(pct=90, prior=70, applying=False)
    apply_partials(account, data)
    assert stage['partials'] == [] and account['contractors'][0]['corrections'] == []
    assert stage['cumulative'] == 0.7 and stage['partial_paid'] == {'u4': 70}
    assert stage['this_month'] == 0


def test_completed_elsewhere_keeps_paid_share():
    account, data, stage = fixture('completed', None, prior=40)
    apply_partials(account, data)
    assert stage['cumulative'] == 0.4 and stage['partial_paid'] == {'u4': 40}
    assert stage['partials'] == [] and stage['evidence'] == []
    assert account['contractors'][0]['corrections'] == []


def test_weighted_contract_items_and_legacy_fallback():
    account, data, stage = fixture()
    stage.update(still_unit_ids=['u1'], unit_ids_this_month=['u2'], this_month=0.7,
                 unit_fractions={'u1': 1.0, 'u4': 0.7}, prev_fractions={'u1': 1.0})
    data['contract_items'] = [{'id': 'i1', 'company_id': 'c1', 'source': 'stage',
        'stage_id': 's1', 'qty': 1, 'unit': 'דירה', 'unit_price': 5000}]
    attach_contract_items(account, data)
    line = account['contractors'][0]['items'][0]
    assert (line['this_month_qty'], line['this_month_amount']) == (0.7, 3500.0)
    assert (line['cumulative_qty'], line['cumulative_amount']) == (1.7, 8500.0)
    assert line['units_this_month'] == 0.7
    for key in ('unit_fractions', 'prev_fractions', 'this_month'):
        stage.pop(key)
    attach_contract_items(account, data)
    line = account['contractors'][0]['items'][0]
    assert (line['this_month_qty'], line['this_month_amount']) == (1, 5000.0)
    assert (line['cumulative_qty'], line['cumulative_amount']) == (2, 10000.0)
    assert line['units_this_month'] == 1
