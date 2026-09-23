import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import config
from contractor_ops import billing, billing_router, green_invoice_service, invoicing


PAYMENT = {
    'method': 'card',
    'reference': 'tx2',
    'card_last4': '4580',
    'amount': 2550.0,
}


class FakeRequest:
    def __init__(self, body):
        self._body = body
        self.client = SimpleNamespace(host='127.0.0.1')
        self.headers = {}
        self.query_params = {}

    async def json(self):
        return self._body


def _cursor(items=None):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=list(items or []))
    return cursor


def _db():
    db = MagicMock()
    db.invoices.find_one = AsyncMock()
    db.invoices.insert_one = AsyncMock()
    db.invoices.update_one = AsyncMock(
        return_value=MagicMock(matched_count=1)
    )
    db.invoices.find = MagicMock(return_value=_cursor())
    db.invoice_line_items.find = MagicMock(return_value=_cursor())
    db.invoice_line_items.insert_many = AsyncMock()
    db.audit_events.insert_one = AsyncMock()
    db.subscriptions.find_one = AsyncMock()
    db.subscriptions.update_one = AsyncMock()
    db.gi_webhook_log.count_documents = AsyncMock(return_value=0)
    db.gi_webhook_log.find_one = AsyncMock(return_value=None)
    db.gi_webhook_log.insert_one = AsyncMock()
    db.organizations.update_one = AsyncMock()
    return db


@pytest.fixture(autouse=True)
def billing_enabled(monkeypatch):
    monkeypatch.setattr(billing, 'BILLING_V1_ENABLED', True)
    billing_router._webhook_call_times.clear()


# T1
def test_generate_invoice_requires_payment_keyword():
    with pytest.raises(TypeError):
        invoicing.generate_invoice('org', '2026-09', 'actor')


# T2
def test_generate_invoice_rejects_empty_reference_before_db(monkeypatch):
    db = _db()
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)
    with pytest.raises(
        ValueError, match='^חשבונית מופקת רק אחרי תשלום שאושר$'
    ):
        asyncio.run(invoicing.generate_invoice(
            'org', '2026-09', 'actor',
            payment={'method': 'card', 'reference': ''},
        ))
    db.invoices.find_one.assert_not_awaited()


# T3
def test_validate_payment_rejects_cash():
    with pytest.raises(
        ValueError, match='^חשבונית מופקת רק אחרי תשלום שאושר$'
    ):
        invoicing._validate_payment({'method': 'cash', 'reference': 'tx'})


# T4
def test_validate_payment_rejects_non_dict():
    with pytest.raises(
        ValueError, match='^חשבונית מופקת רק אחרי תשלום שאושר$'
    ):
        invoicing._validate_payment('tx')


# T5
def test_validate_payment_accepts_both_real_caller_shapes():
    assert invoicing._validate_payment({
        'method': 'card', 'reference': 'tx1',
        'card_last4': '', 'amount': 0,
    }) == {
        'method': 'card', 'reference': 'tx1',
        'card_last4': '', 'amount': 0.0,
    }
    assert invoicing._validate_payment(PAYMENT) == PAYMENT


# T6
def test_generate_invoice_persists_payment_proof_and_passes_normalized_payment(
    monkeypatch,
):
    db = _db()
    db.invoices.find_one.side_effect = [
        None,
        {'gi_download_url': 'u'},
    ]
    preview = {
        'total_amount': 100.0,
        'due_at': '2026-10-07T23:59:59+00:00',
        'line_items': [],
    }
    build_preview = AsyncMock(return_value=preview)
    create_gi = AsyncMock(return_value='gi1')
    send_email = AsyncMock()
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)
    monkeypatch.setattr(invoicing, 'build_invoice_preview', build_preview)
    monkeypatch.setattr(invoicing, '_try_create_gi_document', create_gi)
    monkeypatch.setattr(invoicing, 'send_invoice_email', send_email)

    result = asyncio.run(invoicing.generate_invoice(
        'org', '2026-09', 'actor', payment=PAYMENT
    ))

    inserted = db.invoices.insert_one.await_args.args[0]
    assert inserted['payment_method'] == 'card'
    assert inserted['payment_reference'] == 'tx2'
    assert inserted['payment_amount'] == 2550.0
    assert inserted['status'] == 'issued'
    assert result['gi_document_id'] == 'gi1'
    assert result['gi_download_url'] == 'u'
    assert create_gi.await_count == 1
    assert create_gi.await_args.kwargs['payment'] == PAYMENT


# T7
def test_generate_invoice_refuses_existing_void_invoice(monkeypatch):
    db = _db()
    db.invoices.find_one.return_value = {'id': 'inv', 'status': 'void'}
    create_gi = AsyncMock()
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)
    monkeypatch.setattr(invoicing, '_try_create_gi_document', create_gi)

    with pytest.raises(
        ValueError,
        match='^קיימת חשבונית מבוטלת לתקופה זו — נדרש טיפול ידני$',
    ):
        asyncio.run(invoicing.generate_invoice(
            'org', '2026-09', 'actor', payment=PAYMENT
        ))
    db.invoices.insert_one.assert_not_awaited()
    create_gi.assert_not_awaited()


# T8
def test_existing_paid_invoice_backfills_gi_with_payment(monkeypatch):
    db = _db()
    existing = {
        'id': 'inv', 'status': 'paid', 'total_amount': 100.0,
        'period_ym': '2026-09',
    }
    db.invoices.find_one.return_value = existing
    create_gi = AsyncMock(return_value='gi1')
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)
    monkeypatch.setattr(invoicing, '_try_create_gi_document', create_gi)

    result = asyncio.run(invoicing.generate_invoice(
        'org', '2026-09', 'actor', payment=PAYMENT
    ))

    assert result['gi_document_id'] == 'gi1'
    assert create_gi.await_count == 1
    assert create_gi.await_args.kwargs['payment'] == PAYMENT


# T9
def test_create_document_includes_valid_card_last4_and_payment_date(monkeypatch):
    request = AsyncMock(return_value={'id': 'd'})
    monkeypatch.setattr(green_invoice_service, '_request', request)

    asyncio.run(green_invoice_service.create_document(
        'Client', 'client@example.com', 'Service', 100.0,
        payment={'card_last4': '4580', 'date': '2026-09-22'},
    ))

    payload = request.await_args.kwargs['json_body']
    assert payload['payment'] == [{
        'type': 3,
        'price': 100.0,
        'currency': 'ILS',
        'date': '2026-09-22',
        'cardNum': '4580',
    }]


# T10
def test_create_document_never_emits_placeholder_card_number(monkeypatch):
    for payment in (
        {'card_last4': ''},
        {'card_last4': None},
        {'card_last4': '12'},
        None,
    ):
        request = AsyncMock(return_value={'id': 'd'})
        monkeypatch.setattr(green_invoice_service, '_request', request)
        asyncio.run(green_invoice_service.create_document(
            'Client', 'client@example.com', 'Service', 100.0,
            payment=payment,
        ))
        payload = request.await_args.kwargs['json_body']
        assert 'cardNum' not in payload['payment'][0]
        assert '0000' not in json.dumps(payload)


# T11
def test_parse_gi_remarks():
    assert green_invoice_service.parse_gi_remarks(
        'org_id=A invoice_id=B tx=C'
    ) == {
        'org_id': 'A', 'cycle': 'monthly', 'invoice_id': 'B', 'tx': 'C',
    }
    assert green_invoice_service.parse_gi_remarks(
        'org_id=A cycle=yearly'
    ) == {
        'org_id': 'A', 'cycle': 'yearly', 'invoice_id': '', 'tx': '',
    }
    defaults = {
        'org_id': '', 'cycle': 'monthly', 'invoice_id': '', 'tx': '',
    }
    for remarks in ('', None, 'garbage'):
        assert green_invoice_service.parse_gi_remarks(remarks) == defaults


def _prepare_gi_webhook(monkeypatch, verified_doc):
    db = _db()
    get_document = AsyncMock(return_value=verified_doc)
    mark_paid = AsyncMock(return_value={
        'paid_until': '2026-10-31', 'status': 'active',
    })
    monkeypatch.setattr(billing_router, 'get_db', lambda: db)
    monkeypatch.setattr(config, 'GI_BASE_URL', 'http://gi.test')
    monkeypatch.setattr(config, 'GI_WEBHOOK_SECRET', '')
    monkeypatch.setattr(
        green_invoice_service, 'get_document', get_document
    )
    monkeypatch.setattr(billing, 'mark_paid', mark_paid)
    return db, get_document, mark_paid


# T12
def test_gi_webhook_ignores_api_created_document(monkeypatch):
    db, get_document, mark_paid = _prepare_gi_webhook(monkeypatch, {
        'status': 'paid',
        'remarks': 'org_id=A invoice_id=B',
        'total': 100,
    })

    result = asyncio.run(
        billing_router.billing_webhook_greeninvoice(FakeRequest({'id': 'd'}))
    )

    assert result == {'status': 'ok'}
    get_document.assert_awaited_once_with('d')
    mark_paid.assert_not_awaited()
    log_row = db.gi_webhook_log.insert_one.await_args.args[0]
    assert log_row['result'] == 'api_created_doc'
    assert log_row['invoice_id'] == 'B'


# T13
def test_gi_webhook_still_processes_manual_document(monkeypatch):
    db, _, mark_paid = _prepare_gi_webhook(monkeypatch, {
        'status': 'paid',
        'remarks': 'org_id=A cycle=monthly',
        'total': 100,
    })

    result = asyncio.run(
        billing_router.billing_webhook_greeninvoice(FakeRequest({'id': 'd'}))
    )

    assert result == {'status': 'ok'}
    assert mark_paid.await_args.args[:4] == (
        'A', 'gi_webhook', None, 'monthly'
    )
    log_row = db.gi_webhook_log.insert_one.await_args.args[0]
    assert log_row['result'] == 'success'


def _void_db(status):
    db = _db()
    original = {
        'id': 'inv',
        'org_id': 'org',
        'status': status,
        'period_ym': '2026-09',
        'total_amount': 100.0,
        'gi_document_id': 'gi1',
    }
    updated = {**original, 'status': 'void', 'void_reason': 'טעות'}
    db.invoices.find_one.side_effect = [original, updated]
    return db


# T14
def test_void_issued_invoice_writes_audit_without_subscription_change(
    monkeypatch,
):
    db = _void_db('issued')
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)

    result = asyncio.run(invoicing.void_invoice(
        'org', 'inv', 'sa', 'טעות', '60011'
    ))

    query, update = db.invoices.update_one.await_args.args
    assert query == {
        'id': 'inv',
        'org_id': 'org',
        'status': {'$in': ['issued', 'past_due']},
    }
    assert update['$set']['status'] == 'void'
    assert update['$set']['void_reason'] == 'טעות'
    assert update['$set']['voided_by'] == 'sa'
    assert update['$set']['gi_cancel_document_id'] == '60011'
    audit = db.audit_events.insert_one.await_args.args[0]
    assert audit['action'] == 'invoice_voided'
    assert audit['payload']['before_status'] == 'issued'
    db.subscriptions.update_one.assert_not_awaited()
    assert result['status'] == 'void'
    assert result['line_items'] == []


# T15
def test_void_past_due_invoice(monkeypatch):
    db = _void_db('past_due')
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)

    result = asyncio.run(invoicing.void_invoice(
        'org', 'inv', 'sa', 'טעות'
    ))

    assert db.invoices.update_one.await_args.args[1]['$set']['status'] == 'void'
    audit = db.audit_events.insert_one.await_args.args[0]
    assert audit['payload']['before_status'] == 'past_due'
    assert result['status'] == 'void'


# T16
def test_void_paid_invoice_is_rejected(monkeypatch):
    db = _void_db('paid')
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)
    with pytest.raises(
        ValueError, match='^לא ניתן לבטל חשבונית ששולמה$'
    ):
        asyncio.run(invoicing.void_invoice(
            'org', 'inv', 'sa', 'טעות'
        ))
    db.invoices.update_one.assert_not_awaited()


# T17
def test_void_missing_invoice_is_rejected(monkeypatch):
    db = _db()
    db.invoices.find_one.return_value = None
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)
    with pytest.raises(ValueError, match='^חשבונית לא נמצאה$'):
        asyncio.run(invoicing.void_invoice(
            'org', 'inv', 'sa', 'טעות'
        ))
    db.invoices.update_one.assert_not_awaited()


# T18
def test_void_already_void_invoice_is_rejected(monkeypatch):
    db = _void_db('void')
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)
    with pytest.raises(
        ValueError, match='^לא ניתן לבטל חשבונית בסטטוס void$'
    ):
        asyncio.run(invoicing.void_invoice(
            'org', 'inv', 'sa', 'טעות'
        ))
    db.invoices.update_one.assert_not_awaited()


# T19
def test_void_requires_nonblank_reason_before_db(monkeypatch):
    for reason in ('', '   ', None):
        db = _db()
        monkeypatch.setattr(invoicing, 'get_db', lambda: db)
        with pytest.raises(ValueError, match='^נדרשת סיבה לביטול$'):
            asyncio.run(invoicing.void_invoice(
                'org', 'inv', 'sa', reason
            ))
        db.invoices.find_one.assert_not_awaited()


# T20
def test_mark_invoice_paid_rejects_void_invoice(monkeypatch):
    db = _db()
    db.invoices.find_one.return_value = {
        'id': 'inv', 'org_id': 'org', 'status': 'void'
    }
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)
    with pytest.raises(
        ValueError,
        match='^לא ניתן לסמן חשבונית בסטטוס void כשולם$',
    ):
        asyncio.run(invoicing.mark_invoice_paid('org', 'inv', 'sa'))


# T21
def test_dunning_queries_only_actionable_statuses_and_skips_void(monkeypatch):
    db = _db()
    db.invoices.find.side_effect = [_cursor(), _cursor()]
    db.invoices.find_one.return_value = {
        'id': 'inv', 'status': 'void', 'period_ym': '2026-09'
    }
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)

    result = asyncio.run(invoicing.check_and_enforce_dunning('org'))

    assert result == {'transitioned': [], 'enforced': []}
    filters = [call.args[0] for call in db.invoices.find.call_args_list]
    assert filters == [
        {'org_id': 'org', 'status': 'issued'},
        {'org_id': 'org', 'status': 'past_due'},
    ]
    db.invoices.update_one.assert_not_awaited()


# T22
def test_void_route_exists():
    assert any(
        route.path.endswith('/invoices/{invoice_id}/void')
        for route in billing_router.router.routes
    )


# T23
def test_void_route_denies_owner(monkeypatch):
    void_invoice = AsyncMock()
    monkeypatch.setattr(invoicing, 'void_invoice', void_invoice)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(billing_router.invoice_void(
            'org', 'inv', FakeRequest({'reason': 'טעות'}),
            {'id': 'owner', 'platform_role': 'owner'},
        ))
    assert exc.value.status_code == 403
    assert exc.value.detail == 'רק אדמין ראשי'
    void_invoice.assert_not_awaited()


# T24
def test_void_route_calls_service_for_super_admin(monkeypatch):
    void_invoice = AsyncMock(return_value={'status': 'void'})
    monkeypatch.setattr(invoicing, 'void_invoice', void_invoice)

    result = asyncio.run(billing_router.invoice_void(
        'org', 'inv',
        FakeRequest({
            'reason': 'טעות',
            'gi_cancel_document_id': '60011',
        }),
        {'id': 'sa', 'platform_role': 'super_admin'},
    ))

    assert result == {'status': 'void'}
    void_invoice.assert_awaited_once_with(
        'org', 'inv', 'sa', 'טעות', '60011'
    )


# T25
def test_void_route_validates_body_and_maps_service_error(monkeypatch):
    void_invoice = AsyncMock()
    monkeypatch.setattr(invoicing, 'void_invoice', void_invoice)
    user = {'id': 'sa', 'platform_role': 'super_admin'}

    for body in ({}, {'reason': 'x' * 301}):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(billing_router.invoice_void(
                'org', 'inv', FakeRequest(body), user
            ))
        assert exc.value.status_code == 400
        assert exc.value.detail == 'נדרשת סיבה לביטול (עד 300 תווים)'
    void_invoice.assert_not_awaited()

    void_invoice.side_effect = ValueError('x')
    with pytest.raises(HTTPException) as exc:
        asyncio.run(billing_router.invoice_void(
            'org', 'inv', FakeRequest({'reason': 'טעות'}), user
        ))
    assert exc.value.status_code == 400
    assert exc.value.detail == 'x'


# T26
def test_void_route_hidden_when_billing_disabled(monkeypatch):
    void_invoice = AsyncMock()
    monkeypatch.setattr(invoicing, 'void_invoice', void_invoice)
    monkeypatch.setattr(billing, 'BILLING_V1_ENABLED', False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(billing_router.invoice_void(
            'org', 'inv', FakeRequest({'reason': 'טעות'}),
            {'id': 'sa', 'platform_role': 'super_admin'},
        ))
    assert exc.value.status_code == 404
    void_invoice.assert_not_awaited()


# T27 (ADDENDUM-1)
def test_void_invoice_detects_concurrent_status_change(monkeypatch):
    db = _db()
    db.invoices.find_one.return_value = {
        'id': 'inv',
        'org_id': 'org',
        'status': 'issued',
        'period_ym': '2026-09',
        'total_amount': 100.0,
    }
    db.invoices.update_one = AsyncMock(
        return_value=MagicMock(matched_count=0)
    )
    monkeypatch.setattr(invoicing, 'get_db', lambda: db)

    with pytest.raises(
        ValueError,
        match='^החשבונית השתנתה בינתיים — רענן ונסה שוב$',
    ):
        asyncio.run(invoicing.void_invoice(
            'org', 'inv', 'sa', 'טעות'
        ))
    db.audit_events.insert_one.assert_not_awaited()