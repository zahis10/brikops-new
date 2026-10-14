"""Floor payment calculations: pure fixtures, no database."""
import pytest
from fastapi import HTTPException
from openpyxl import load_workbook
from test_monthly_close import inputs, event
from test_contract_items import item
from contractor_ops.monthly_close import build_account
from contractor_ops.contract_items import validate_item, attach_contract_items
from contractor_ops.monthly_close_export import build_monthly_close_xlsx


ARGS = dict(stages={'s1'}, company_ids={'c1'}, unit_type_tags=set(), floor_ids={'f1', 'f2'})


def test_validation():
    for change in ({'source': 'measured'}, {'basis': 'x'}, {'qty_by_floor': {'missing': 3}},
                   {'qty_by_floor': {'f1': 0}}, {'price_by_floor': {'f1': 3}}):
        with pytest.raises(HTTPException) as exc:
            validate_item(item(basis='floor', **change) if 'basis' not in change else item(**change), **ARGS)
        assert exc.value.status_code == 422
    body = item(basis='floor', qty=1)
    del body['unit']
    clean = validate_item(body, **ARGS)
    assert (clean['basis'], clean['unit'], clean['qty_by_unit_type']) == ('floor', 'קומה', None)
    assert validate_item({**body, 'qty_by_floor': {'f2': 120}}, **ARGS)['qty_by_floor'] == {'f2': 120}
    with pytest.raises(HTTPException) as exc:
        validate_item(body, existing=item(), **ARGS)
    assert exc.value.status_code == 422


def account_for(payment, fractions, irrelevant=False, previous=None):
    ins = inputs([event('u1')])
    if irrelevant:
        ins['cells'].append(event('u6', status='not_relevant'))
    account = build_account('2026-09', **ins)
    stage = account['contractors'][0]['stages'][0]
    stage.update(unit_fractions=fractions, prev_fractions=previous or {}, unit_ids_this_month=[], still_unit_ids=[])
    return attach_contract_items(account, {**ins, 'contract_items': [payment]})


def test_weighted_floors_and_not_relevant():
    payment = item(basis='floor', qty=80, unit='מ״ק', unit_price=400, qty_by_floor={'f2': 120})
    shares = {'u1': 1, 'u2': 1, 'u3': 1, 'u4': 0.5}
    row = account_for(payment, shares)['contractors'][0]['items'][0]
    assert tuple(row[k] for k in ('this_month_qty', 'this_month_amount', 'cumulative_qty',
                                 'floors_this_month', 'floors_total')) == (100, 40000, 100, 1.17, 2)
    assert account_for(payment, shares, True)['contractors'][0]['items'][0]['this_month_qty'] == 110
    row = account_for({**payment, 'price_by_floor': {'f2': 500}}, shares)['contractors'][0]['items'][0]
    assert row['this_month_amount'] == 42000
    row = account_for(payment, {'u1': 0.5}, previous={'u1': 1})['contractors'][0]['items'][0]
    assert (row['this_month_qty'], row['this_month_amount'], row['floors_this_month']) == (-13.33, -5333.33, -0.17)


def test_lump_export_and_legacy():
    account = account_for(item(basis='floor', qty=1, unit='קומה', unit_price=50000),
                          {'u1': 1, 'u2': 1, 'u3': 1})
    contractor = account['contractors'][0]
    row = contractor['items'][0]
    assert (row['this_month_qty'], row['this_month_amount']) == (1, 50000)
    sheet = load_workbook(build_monthly_close_xlsx({'id': 'p1'}, account, contractor, '')).worksheets[0]
    assert sheet['C5'].value == 'קומה' and sheet['J5'].value.endswith('קומות')
    legacy = item()
    del legacy['basis']
    row = account_for(legacy, {'u1': 1, 'u2': 0.5})['contractors'][0]['items'][0]
    assert (row['this_month_qty'], row['cumulative_qty'], row['this_month_amount']) == (57, 57, None)
