import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import config
from contractor_ops import billing, billing_router, invoicing


@pytest.fixture(autouse=True)
def billing_enabled(monkeypatch):
    monkeypatch.setattr(billing, 'BILLING_V1_ENABLED', True)


def test_generate_route_absent():
    assert not any(r.path.endswith('/invoice/generate') for r in billing_router.router.routes)


def test_owner_denied(monkeypatch):
    mark_paid = AsyncMock()
    monkeypatch.setattr(invoicing, 'mark_invoice_paid', mark_paid)
    monkeypatch.setattr(config, 'BILLING_SIMULATION_ENABLED', True)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(billing_router.invoice_mark_paid('org', 'invoice', {'id': 'owner', 'platform_role': 'owner'}))
    assert exc.value.status_code == 403
    assert exc.value.detail == 'רק אדמין ראשי'
    mark_paid.assert_not_called()


def test_super_admin_flag_off(monkeypatch):
    mark_paid = AsyncMock()
    monkeypatch.setattr(invoicing, 'mark_invoice_paid', mark_paid)
    monkeypatch.setattr(config, 'BILLING_SIMULATION_ENABLED', False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(billing_router.invoice_mark_paid('org', 'invoice', {'id': 'sa', 'platform_role': 'super_admin'}))
    assert exc.value.status_code == 403
    assert exc.value.detail == 'סימולציית תשלום כבויה בסביבה זו'
    mark_paid.assert_not_called()


def test_super_admin_flag_on(monkeypatch):
    mark_paid = AsyncMock(return_value={'ok': True})
    monkeypatch.setattr(invoicing, 'mark_invoice_paid', mark_paid)
    monkeypatch.setattr(config, 'BILLING_SIMULATION_ENABLED', True)
    result = asyncio.run(billing_router.invoice_mark_paid('org', 'invoice', {'id': 'sa', 'platform_role': 'super_admin'}))
    assert result == {'ok': True}
    mark_paid.assert_awaited_once_with('org', 'invoice', 'sa')


def test_list_simulation_visibility(monkeypatch):
    invoices = [{'id': 'invoice', 'status': 'issued'}]
    monkeypatch.setattr(config, 'BILLING_SIMULATION_ENABLED', True)
    monkeypatch.setattr(invoicing, 'list_invoices', AsyncMock(return_value=invoices))
    monkeypatch.setattr(invoicing, 'check_and_enforce_dunning', AsyncMock())
    monkeypatch.setattr(billing, 'check_org_billing_role', AsyncMock(return_value='owner'))
    for role, expected in [('super_admin', True), ('owner', False)]:
        result = asyncio.run(billing_router.invoice_list('org', {'id': role, 'platform_role': role}))
        assert result == {'invoices': invoices, 'simulation_enabled': expected}