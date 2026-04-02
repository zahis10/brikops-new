import re
import uuid
import logging
import calendar
from datetime import datetime, timezone, timedelta
from typing import Optional, List

logger = logging.getLogger(__name__)

INVOICE_DUE_DAYS = 7
GRACE_DAYS = 7

VALID_INVOICE_STATUSES = {'draft', 'issued', 'paid', 'past_due', 'void'}

_PERIOD_RE = re.compile(r'^(\d{4})-(0[1-9]|1[0-2])$')

_db = None


def set_invoicing_db(db):
    global _db
    _db = db


def get_db():
    if _db is None:
        raise RuntimeError("Invoicing DB not initialized")
    return _db


def _now():
    return datetime.now(timezone.utc).isoformat()


def _now_dt():
    return datetime.now(timezone.utc)


def validate_period_ym(period_ym: str) -> tuple:
    m = _PERIOD_RE.match(period_ym)
    if not m:
        raise ValueError("period_ym must be YYYY-MM with month 01-12")
    return int(m.group(1)), int(m.group(2))


def _end_of_month_utc(year: int, month: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)


def _compute_due_at(year: int, month: int) -> str:
    eom = _end_of_month_utc(year, month)
    due = eom + timedelta(days=INVOICE_DUE_DAYS)
    return due.isoformat()


async def ensure_indexes():
    db = get_db()
    await db.invoices.create_index(
        [('org_id', 1), ('period_ym', 1)],
        unique=True,
        name='idx_invoices_org_period_unique'
    )
    await db.invoices.create_index([('org_id', 1), ('status', 1)])
    await db.invoice_line_items.create_index([('invoice_id', 1)])


async def build_invoice_preview(org_id: str, period_ym: str) -> dict:
    year, month = validate_period_ym(period_ym)
    db = get_db()

    active_pbs = await db.project_billing.find(
        {'org_id': org_id, 'status': 'active'},
        {'_id': 0}
    ).to_list(1000)

    project_ids = [pb['project_id'] for pb in active_pbs]
    projects = {}
    if project_ids:
        proj_docs = await db.projects.find(
            {'id': {'$in': project_ids}},
            {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(1000)
        projects = {p['id']: p.get('name', '') for p in proj_docs}

    line_items = []
    total = 0
    for pb in active_pbs:
        mt = pb.get('monthly_total', 0)
        total += mt
        line_items.append({
            'project_id': pb['project_id'],
            'project_name_snapshot': projects.get(pb['project_id'], ''),
            'plan_id_snapshot': pb.get('plan_id'),
            'tier_code_snapshot': pb.get('tier_code', 'none'),
            'contracted_units_snapshot': pb.get('contracted_units', 0),
            'project_fee_snapshot': pb.get('project_fee_snapshot', 0),
            'tier_fee_snapshot': pb.get('tier_fee_snapshot', 0),
            'license_fee_snapshot': pb.get('license_fee', 0),
            'units_fee_snapshot': pb.get('units_fee', 0),
            'price_per_unit': pb.get('price_per_unit', 20),
            'units_count': pb.get('contracted_units', 0),
            'monthly_total_snapshot': mt,
        })

    return {
        'org_id': org_id,
        'period_ym': period_ym,
        'total_amount': total,
        'currency': 'ILS',
        'due_at': _compute_due_at(year, month),
        'line_items': line_items,
    }


async def _try_create_gi_document(db, org_id: str, invoice_id: str, amount: float, period_ym: str, paid_until: str = "", card_last4: str = ""):
    from config import GI_BASE_URL
    if not GI_BASE_URL or amount <= 0:
        logger.info("[INVOICING:GI] Skipped — GI not configured or amount=0. invoice=%s amount=%s gi_configured=%s", invoice_id, amount, bool(GI_BASE_URL))
        return None
    logger.info("[INVOICING:GI] Starting GI document creation for invoice %s org=%s amount=%s", invoice_id, org_id, amount)
    from contractor_ops.green_invoice_service import create_or_get_client, create_document
    org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'name': 1, 'billing': 1, 'tax_id': 1})
    org_name = org.get('name', '') if org else ''
    billing_data = org.get('billing', {}) if org else {}
    billing_email = billing_data.get('billing_email', '')
    if not billing_email:
        owner = await db.users.find_one({'org_id': org_id, 'role': {'$in': ['owner', 'admin']}}, {'_id': 0, 'email': 1})
        billing_email = owner.get('email', '') if owner else ''
    tax_id = org.get('tax_id', '') if org else ''
    gi_client_id = billing_data.get('gi_client_id', '')
    if not gi_client_id:
        gi_client_id = await create_or_get_client(org_name or 'BrikOps Client', billing_email, tax_id)
        await db.organizations.update_one(
            {'id': org_id},
            {'$set': {'billing.gi_client_id': gi_client_id}}
        )
    if paid_until:
        try:
            pu_dt = datetime.fromisoformat(paid_until.replace('Z', '+00:00'))
            gi_description = f"מנוי חודשי BrikOps — {pu_dt.month:02d}/{pu_dt.year}"
        except Exception:
            gi_description = f"מנוי BrikOps — {period_ym}"
    else:
        gi_description = f"מנוי BrikOps — {period_ym}"
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    gi_doc = await create_document(
        client_name=org_name or 'BrikOps Client',
        client_email=billing_email,
        description=gi_description,
        amount=amount,
        currency='ILS',
        remarks=f"org_id={org_id} invoice_id={invoice_id}",
        client_id=gi_client_id,
        payment_date=today_str,
        card_last4=card_last4,
    )
    gi_document_id = gi_doc.get('id', '')
    gi_download_url = gi_doc.get('url', {}).get('he', '')
    if gi_document_id:
        update_fields = {'gi_document_id': gi_document_id, 'gi_download_url': gi_download_url, 'updated_at': _now()}
        await db.invoices.update_one(
            {'id': invoice_id},
            {'$set': update_fields}
        )
    logger.info("[INVOICING:GI] SUCCESS doc_id=%s for invoice %s", gi_document_id or '(none)', invoice_id)
    return gi_document_id


async def generate_invoice(org_id: str, period_ym: str, created_by: str, paid_until: str = "", card_last4: str = "", override_amount: float = None) -> dict:
    year, month = validate_period_ym(period_ym)
    db = get_db()

    existing = await db.invoices.find_one(
        {'org_id': org_id, 'period_ym': period_ym},
        {'_id': 0}
    )
    if existing:
        items = await db.invoice_line_items.find(
            {'invoice_id': existing['id']},
            {'_id': 0}
        ).to_list(1000)
        existing['line_items'] = items
        if not existing.get('gi_document_id'):
            try:
                gi_id = await _try_create_gi_document(db, org_id, existing['id'], existing.get('total_amount', 0), period_ym, paid_until=paid_until, card_last4=card_last4)
                if gi_id:
                    existing['gi_document_id'] = gi_id
            except Exception as e:
                logger.warning("[INVOICING:GI] Backfill FAILED for existing invoice %s: %s", existing['id'], str(e))
        return existing

    preview = await build_invoice_preview(org_id, period_ym)

    final_amount = preview['total_amount']
    if override_amount is not None:
        logger.info("[INVOICE] Using override amount=%.2f instead of computed=%.2f for org=%s period=%s", override_amount, final_amount, org_id, period_ym)
        final_amount = override_amount

    ts = _now()
    invoice_id = str(uuid.uuid4())
    invoice_doc = {
        'id': invoice_id,
        'org_id': org_id,
        'period_ym': period_ym,
        'status': 'issued',
        'total_amount': final_amount,
        'currency': 'ILS',
        'issued_at': ts,
        'due_at': preview['due_at'],
        'paid_at': None,
        'created_by': created_by,
        'created_at': ts,
        'updated_at': ts,
    }

    try:
        await db.invoices.insert_one(invoice_doc)
    except Exception as e:
        if 'duplicate key' in str(e).lower() or 'E11000' in str(e):
            existing = await db.invoices.find_one(
                {'org_id': org_id, 'period_ym': period_ym},
                {'_id': 0}
            )
            if existing:
                items = await db.invoice_line_items.find(
                    {'invoice_id': existing['id']},
                    {'_id': 0}
                ).to_list(1000)
                existing['line_items'] = items
                return existing
        raise

    item_docs = []
    for li in preview['line_items']:
        item_doc = {
            'id': str(uuid.uuid4()),
            'invoice_id': invoice_id,
            **li,
            'created_at': ts,
        }
        item_docs.append(item_doc)

    if item_docs:
        await db.invoice_line_items.insert_many(item_docs)

    period_end = (_end_of_month_utc(year, month) + timedelta(days=7)).isoformat()
    await db.subscriptions.update_one(
        {'org_id': org_id},
        {'$set': {
            'status': 'active',
            'paid_until': period_end,
            'updated_at': ts,
        }},
        upsert=True,
    )

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'invoice',
        'entity_id': invoice_id,
        'action': 'invoice_generated',
        'actor_id': created_by,
        'payload': {
            'org_id': org_id,
            'period_ym': period_ym,
            'total_amount': final_amount,
            'line_item_count': len(item_docs),
            'subscription_paid_until': period_end,
        },
        'created_at': ts,
    })

    invoice_doc.pop('_id', None)
    for doc in item_docs:
        doc.pop('_id', None)
    invoice_doc['line_items'] = item_docs

    from config import GI_BASE_URL
    logger.info("[INVOICING:GI] About to attempt GI. invoice=%s amount=%s gi_configured=%s", invoice_id, final_amount, bool(GI_BASE_URL))
    try:
        gi_document_id = await _try_create_gi_document(db, org_id, invoice_id, final_amount, period_ym, paid_until=paid_until, card_last4=card_last4)
        if gi_document_id:
            invoice_doc['gi_document_id'] = gi_document_id
    except Exception as e:
        logger.warning("[INVOICING:GI] FAILED for invoice %s: %s", invoice_id, str(e))

    logger.info(f"[INVOICING] Generated invoice {invoice_id} for org {org_id} period {period_ym}, total={final_amount}, paid_until={period_end}")
    return invoice_doc


async def get_invoice(org_id: str, invoice_id: str) -> Optional[dict]:
    db = get_db()
    inv = await db.invoices.find_one(
        {'id': invoice_id, 'org_id': org_id},
        {'_id': 0}
    )
    if not inv:
        return None
    items = await db.invoice_line_items.find(
        {'invoice_id': invoice_id},
        {'_id': 0}
    ).to_list(1000)
    inv['line_items'] = items
    return inv


async def list_invoices(org_id: str) -> List[dict]:
    db = get_db()
    invoices = await db.invoices.find(
        {'org_id': org_id},
        {'_id': 0}
    ).sort('period_ym', -1).to_list(1000)
    return invoices


async def mark_invoice_paid(org_id: str, invoice_id: str, actor_id: str) -> dict:
    db = get_db()
    inv = await db.invoices.find_one(
        {'id': invoice_id, 'org_id': org_id},
        {'_id': 0}
    )
    if not inv:
        raise ValueError("חשבונית לא נמצאה")
    if inv['status'] not in ('issued', 'past_due'):
        raise ValueError(f"לא ניתן לסמן חשבונית בסטטוס {inv['status']} כשולם")

    ts = _now()
    before_status = inv['status']

    year, month = validate_period_ym(inv['period_ym'])
    paid_until = _end_of_month_utc(year, month).isoformat()

    await db.invoices.update_one(
        {'id': invoice_id},
        {'$set': {
            'status': 'paid',
            'paid_at': ts,
            'updated_at': ts,
        }}
    )

    await db.subscriptions.update_one(
        {'org_id': org_id},
        {'$set': {
            'status': 'active',
            'paid_until': paid_until,
            'updated_at': ts,
        }}
    )

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'invoice',
        'entity_id': invoice_id,
        'action': 'invoice_marked_paid',
        'actor_id': actor_id,
        'payload': {
            'org_id': org_id,
            'period_ym': inv['period_ym'],
            'total_amount': inv['total_amount'],
            'before_status': before_status,
            'after_status': 'paid',
            'paid_until': paid_until,
        },
        'created_at': ts,
    })

    logger.info(f"[INVOICING] Invoice {invoice_id} marked paid for org {org_id}, paid_until={paid_until}")

    updated = await db.invoices.find_one({'id': invoice_id}, {'_id': 0})
    items = await db.invoice_line_items.find(
        {'invoice_id': invoice_id}, {'_id': 0}
    ).to_list(1000)
    updated['line_items'] = items
    return updated


async def check_and_enforce_dunning(org_id: str) -> dict:
    db = get_db()
    now = _now_dt()
    result = {'transitioned': [], 'enforced': []}

    issued_invoices = await db.invoices.find(
        {'org_id': org_id, 'status': 'issued'},
        {'_id': 0}
    ).to_list(1000)

    for inv in issued_invoices:
        due_dt = datetime.fromisoformat(inv['due_at'])
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=timezone.utc)
        if now > due_dt:
            await db.invoices.update_one(
                {'id': inv['id'], 'status': 'issued'},
                {'$set': {'status': 'past_due', 'updated_at': _now()}}
            )
            result['transitioned'].append({
                'invoice_id': inv['id'],
                'period_ym': inv['period_ym'],
                'from': 'issued',
                'to': 'past_due',
            })
            logger.info(f"[INVOICING] Invoice {inv['id']} transitioned issued→past_due for org {org_id}")

    latest_invoice = await db.invoices.find_one(
        {"org_id": org_id},
        sort=[("period_ym", -1)]
    )

    past_due_invoices = await db.invoices.find(
        {'org_id': org_id, 'status': 'past_due'},
        {'_id': 0}
    ).to_list(1000)

    for inv in past_due_invoices:
        due_dt = datetime.fromisoformat(inv['due_at'])
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=timezone.utc)
        grace_end = due_dt + timedelta(days=GRACE_DAYS)
        if now > grace_end:
            if latest_invoice and latest_invoice["status"] not in ("past_due",) and inv["period_ym"] != latest_invoice["period_ym"]:
                logger.info(f"[INVOICING] Skipping paid_until clear for old invoice {inv['id']} (period {inv['period_ym']}); latest period {latest_invoice['period_ym']} is {latest_invoice['status']}")
                continue
            sub = await db.subscriptions.find_one(
                {'org_id': org_id}, {'_id': 0, 'paid_until': 1}
            )
            if sub and sub.get('paid_until'):
                await db.subscriptions.update_one(
                    {'org_id': org_id},
                    {'$set': {'paid_until': None, 'updated_at': _now()}}
                )
                result['enforced'].append({
                    'invoice_id': inv['id'],
                    'period_ym': inv['period_ym'],
                    'action': 'cleared_paid_until',
                })
                logger.info(f"[INVOICING] Cleared paid_until for org {org_id} due to past_due invoice {inv['id']} past grace")

    return result
