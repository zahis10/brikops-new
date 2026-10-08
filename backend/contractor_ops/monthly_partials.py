"""#612 — partial payment per apartment.

A matrix cell may carry progress_pct (1..99). The account counts an apartment-stage as a fraction:
1.0 when the cell is 'completed'; progress_pct/100 while the cell is neither 'completed' nor
'not_done'/'not_relevant' (QC states such as 'pending_review' keep the share); otherwise 0.
Only the DIFFERENCE from what earlier accounts paid enters a month: 0→70% pays 70%, 70→100% pays
the remaining 30%, 70→50% adds a correction row of −20%. The cumulative share of an apartment never
exceeds 100%. Runs after build_account and before attach_contract_items; reads cells/units/snapshots
and writes only into the account dict.
"""
from contractor_ops.execution_matrix_router import _unit_sort_key

STOP = ('completed', 'not_done', 'not_relevant')


def partial_pct(cell):
    """The cell's current share in percent while it is a partial payment, else 0."""
    if not cell or cell.get('status') in STOP:
        return 0
    pct = cell.get('progress_pct')
    return int(pct) if isinstance(pct, (int, float)) and 0 < pct < 100 else 0


def _unit_row(unit, buildings, floors):
    floor = floors.get(unit.get('floor_id'), {})
    return {'unit_id': unit['id'], 'unit_no': unit.get('unit_no', ''), 'floor_id': unit.get('floor_id'),
            'floor_number': floor.get('floor_number'), 'building_id': unit.get('building_id'),
            'building_name': buildings.get(unit.get('building_id'), {}).get('name', '')}


def _actor(cell):
    audit = (cell or {}).get('audit') or []
    return (audit[-1].get('actor_name') if audit else '') or ''


def apply_partials(account, inputs):
    contractors = account.get('contractors') or []
    if not contractors:
        return account
    month = account['month']
    snapshots = inputs.get('snapshots') or []
    active = not snapshots or bool(account.get('applying'))
    before = [s for s in snapshots if s.get('month', '') < month]
    previous = max(before, key=lambda s: s['month']) if before else {}
    cells = {(c['stage_id'], c['unit_id']): c for c in inputs.get('cells') or []}
    buildings = {b['id']: b for b in inputs.get('buildings') or []}
    floors = {f['id']: f for f in inputs.get('floors') or []}
    units = sorted(inputs.get('units') or [], key=lambda u: _unit_sort_key(u, buildings, floors))
    for c in contractors:
        prev_c = next((p for p in previous.get('contractors', []) if p.get('company_id') == c['company_id']), {})
        for stage in c.get('stages') or []:
            sid = stage['stage_id']
            prev_stage = next((s for s in prev_c.get('stages', []) if s.get('stage_id') == sid), {})
            prior = {k: int(v) for k, v in (prev_stage.get('partial_paid') or {}).items() if v}
            still = set(stage.get('still_unit_ids') or [])
            fractions = {uid: 1.0 for uid in still | set(stage.get('unit_ids_this_month') or [])}
            prev_fractions = {uid: 1.0 for uid in still}
            for uid, pct in prior.items():
                prev_fractions.setdefault(uid, pct / 100)
            for row in stage.get('evidence') or []:
                pct = prior.get(row['unit_id'], 0)
                row['prior_pct'] = pct
                row['fraction'] = round(1 - pct / 100, 4)
            partials, reductions = [], []
            for unit in units:
                uid = unit['id']
                if uid in fractions:
                    continue
                cell, was = cells.get((sid, uid)), prior.get(uid, 0)
                if cell and cell.get('status') == 'completed':
                    if was:                       # completed, but counted in another month: keep the paid share
                        fractions[uid] = was / 100
                    continue
                now = partial_pct(cell) if active else was
                if not now and not was:
                    continue
                if now:
                    fractions[uid] = now / 100
                if now == was:
                    continue
                row = {**_unit_row(unit, buildings, floors), 'stage_id': sid, 'pct': now, 'prior_pct': was,
                       'delta': round((now - was) / 100, 4), 'source': 'manual',
                       'actor_name': _actor(cell), 'updated_at': (cell or {}).get('last_updated_at')}
                (partials if row['delta'] > 0 else reductions).append(row)
            stage['partials'] = partials
            stage['partial_count'] = sum(1 for f in fractions.values() if 0 < f < 1)
            stage['partial_paid'] = {uid: int(round(f * 100)) for uid, f in fractions.items() if 0 < f < 1}
            stage['unit_fractions'] = fractions
            stage['prev_fractions'] = prev_fractions
            stage['this_month'] = round(sum(r['fraction'] for r in stage.get('evidence') or [])
                                        + sum(r['delta'] for r in partials), 2)
            stage['cumulative'] = round(sum(fractions.values()), 2)
            total_units = stage.get('total_units') or 0
            stage['pct'] = round(100 * stage['cumulative'] / total_units) if total_units else 0
            for r in reductions:
                c.setdefault('corrections', []).append({**r, 'stage_title': stage.get('title', ''),
                    'company_id': c['company_id'], 'company_name': c.get('name', ''),
                    'counted_in_month': previous.get('month'), 'reason': 'partial_reduced'})
        totals = c.setdefault('totals', {})
        totals['this_month'] = round(sum(s.get('this_month', 0) for s in c.get('stages') or []), 2)
        totals['cumulative'] = round(sum(s.get('cumulative', 0) for s in c.get('stages') or []), 2)
    kpis = account.setdefault('kpis', {})
    kpis['this_month'] = round(sum((c.get('totals') or {}).get('this_month', 0) for c in contractors), 2)
    kpis['corrections'] = sum(len(c.get('corrections') or []) for c in contractors)
    return account
