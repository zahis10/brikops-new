"""Contract quantities layered over the unchanged monthly progress engine."""
import logging
import math
from fastapi import HTTPException


def _number(value, low, high, detail, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise HTTPException(422, detail)
    if value < low or value > high or (positive and value == 0):
        raise HTTPException(422, detail)
    return float(value)


def validate_item(body, *, stages, company_ids, unit_type_tags, existing=None):
    def text(key, maximum, default=''):
        value = body.get(key, default)
        if not isinstance(value, str) or len(value.strip()) > maximum:
            raise HTTPException(422, 'נדרש תיאור לסעיף' if key == 'description' else 'ערך לא תקין')
        return value.strip()
    description = text('description', 120)
    if not description:
        raise HTTPException(422, 'נדרש תיאור לסעיף')
    source, company, stage = body.get('source'), body.get('company_id'), body.get('stage_id')
    if source not in ('stage', 'measured'):
        raise HTTPException(422, 'סוג סעיף לא תקין')
    if body.get('basis', 'unit') != 'unit':
        raise HTTPException(422, 'כמות לקומה — בשלב הבא')
    if not isinstance(company, str) or company not in company_ids:
        raise HTTPException(422, 'הקבלן לא בפרויקט')
    if source == 'stage' and (not isinstance(stage, str) or stage not in stages):
        raise HTTPException(422, 'שלב לא קיים')
    stage = stage if source == 'stage' else None
    if existing and any(existing.get(k) != v for k, v in
                        [('company_id', company), ('source', source), ('stage_id', stage)]):
        raise HTTPException(422, 'אי אפשר לשנות שלב או קבלן — צור סעיף חדש')
    qty = _number(body.get('qty', 1), 0, 1000000, 'כמות לא תקינה', True)
    price = body.get('unit_price')
    if price is not None:
        price = _number(price, 0, 10000000, 'מחיר לא תקין')
    def overrides(key, maximum, positive):
        values = body.get(key)
        if values is None:
            return None
        if not isinstance(values, dict):
            raise HTTPException(422, 'ערך לא תקין')
        for tag, value in values.items():
            if tag not in unit_type_tags:
                raise HTTPException(422, 'סוג דירה לא קיים בפרויקט')
            _number(value, 0, maximum, 'כמות לא תקינה' if positive else 'מחיר לא תקין', positive)
        return dict(values) or None
    quantities = overrides('qty_by_unit_type', 1000000, True)
    prices = overrides('price_by_unit_type', 10000000, False)
    if prices and price is None:
        raise HTTPException(422, 'נדרש מחיר ברירת מחדל')
    unit = text('unit', 20, 'דירה' if source == 'stage' and qty == 1 and not quantities else 'יח׳')
    if not unit:
        raise HTTPException(422, 'נדרשת יחידה')
    code = body.get('code')
    code = text('code', 40) if code is not None else None
    return dict(company_id=company, source=source, stage_id=stage, basis='unit', code=code or None,
                description=description, unit=unit, qty=qty, qty_by_unit_type=quantities,
                unit_price=price, price_by_unit_type=prices)


def _line(item, stage=None, **values):
    result = {k: item.get(k) for k in ('source', 'code', 'description', 'unit', 'qty',
                                      'qty_by_unit_type', 'unit_price', 'price_by_unit_type')}
    result.update(item_id=item.get('id'), stage_id=(stage or {}).get('stage_id'),
                  stage_title=(stage or {}).get('title'), units_this_month=0, corrections=0,
                  measurement=None, evidence_rows=None)
    result.update(values)
    return {k: round(v, 2) if isinstance(v, float) else v for k, v in result.items()}


def attach_contract_items(account, inputs):
    items = [i for i in inputs.get('contract_items') or [] if i.get('active', True)]
    month = account['month']
    before = [s for s in inputs.get('snapshots') or [] if s.get('month', '') < month]
    previous = max(before, key=lambda s: s['month']) if before else {}
    tags = {u.get('id'): u.get('unit_type_tag') for u in inputs.get('units') or []}
    for c in account.get('contractors') or []:
        cid = c['company_id']
        c['account_no'] = 1 + sum(any(p.get('company_id') == cid for p in s.get('contractors', [])) for s in before)
        prev_c = next((p for p in previous.get('contractors', []) if p.get('company_id') == cid), {})
        prev_lines = {l['item_id']: l for l in prev_c.get('items', []) if l.get('item_id')}
        mine = [i for i in items if i.get('company_id') == cid]
        lines, start = [], 1
        for stage in c.get('stages') or []:
            sid, size = stage.get('stage_id'), len(stage.get('evidence') or [])
            evidence = [start, start + size - 1] if size else None
            start += size
            still = set(stage.get('still_unit_ids') or [])
            counted = still | set(stage.get('unit_ids_this_month') or [])
            corrections = sum(r.get('stage_id') == sid for r in c.get('corrections') or [])
            stage_items = [i for i in mine if i.get('source') == 'stage' and i.get('stage_id') == sid]
            extra = dict(units_this_month=len(stage.get('unit_ids_this_month') or []),
                         corrections=corrections, evidence_rows=evidence)
            if not stage_items and mine:
                prev_stage = next((s for s in prev_c.get('stages', []) if s.get('stage_id') == sid), {})
                prev = prev_stage.get('cumulative', stage.get('still_paid', 0))
                total = stage.get('cumulative', 0)
                lines.append(_line(dict(source='stage_units', unit='דירות', qty=1,
                    description=f"{stage.get('title', '')} (שלב בלי סעיף)"), stage,
                    prev_cumulative_qty=prev, cumulative_qty=total, this_month_qty=total - prev,
                    prev_cumulative_amount=None, cumulative_amount=None, this_month_amount=None, **extra))
            for item in stage_items:
                def sums(ids):
                    quantities = [(item.get('qty_by_unit_type') or {}).get(tags.get(uid), item['qty']) for uid in ids]
                    prices = [(item.get('price_by_unit_type') or {}).get(tags.get(uid), item.get('unit_price')) for uid in ids]
                    return sum(quantities), None if item.get('unit_price') is None else sum(q * p for q, p in zip(quantities, prices))
                total, amount = sums(sorted(counted))
                prev_qty, prev_amt = sums(sorted(still))
                prior = prev_lines.get(item['id'])
                if prior:
                    prev_qty, prev_amt = prior.get('cumulative_qty', 0), prior.get('cumulative_amount')
                lines.append(_line(item, stage, prev_cumulative_qty=prev_qty, cumulative_qty=total,
                    this_month_qty=total - prev_qty, prev_cumulative_amount=prev_amt, cumulative_amount=amount,
                    this_month_amount=None if amount is None else amount - (prev_amt or 0), **extra))
        for item in (i for i in mine if i.get('source') == 'measured'):
            entries = item.get('measurements') or {}
            entry, prior = entries.get(month), prev_lines.get(item['id'])
            prev_qty = prior.get('cumulative_qty', 0) if prior else sum(e.get('qty', 0) for m, e in entries.items() if m < month)
            qty, price = (entry or {}).get('qty', 0), item.get('unit_price')
            prev_amt = prior.get('cumulative_amount') if prior else (None if price is None else prev_qty * price)
            lines.append(_line(item, prev_cumulative_qty=prev_qty, this_month_qty=qty,
                cumulative_qty=prev_qty + qty, prev_cumulative_amount=prev_amt, measurement=entry,
                this_month_amount=None if price is None else (prev_qty + qty) * price - (prev_amt or 0),
                cumulative_amount=None if price is None else (prev_qty + qty) * price))
        c['items'], c['has_items'] = lines, bool(mine)
        priced = [l for l in lines if l['cumulative_amount'] is not None]
        c['totals_money'] = {k: round(sum(l[f'{k}_amount'] for l in priced), 2)
                             for k in ('this_month', 'cumulative')} if priced else None
    return account


async def ensure_indexes(db):
    try:
        await db.contract_items.create_index([('project_id', 1), ('company_id', 1), ('active', 1)],
                                             name='contract_items_company')
        await db.contract_items.create_index([('project_id', 1), ('company_id', 1), ('code', 1)],
            name='uniq_contract_item_code', unique=True,
            partialFilterExpression={'code': {'$type': 'string'}, 'active': True})
    except Exception:
        logging.getLogger(__name__).exception('Contract item index creation failed')
