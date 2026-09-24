"""Monthly quantities: pure calculation followed by read-only input loading."""
import logging
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone

from fastapi import HTTPException
from contractor_ops.utils.timezone import IL_TZ
from contractor_ops.execution_matrix_router import _resolve_visible_stages, _unit_sort_key
from contractor_ops.qc_router import _get_template
from contractor_ops.bucket_utils import BUCKET_LABELS

MONTH_RE = r'^\d{4}-(0[1-9]|1[0-2])$'
HEBREW_MONTHS = ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 'יולי', 'אוגוסט',
                 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר']
BASELINE = 'baseline'
TRADE_STAGE_KEYWORDS = {
    'plumbing': ['אינסטלצ'], 'electrical': ['חשמל'], 'flooring': ['ריצוף', 'חיפוי'],
    'painting': ['צבע'], 'aluminum': ['אלומיניום'], 'hvac': ['מיזוג'],
    'doors': ['דלת'], 'glazing': ['חלון', 'זכוכית'], 'metalwork': ['מסגר'],
    'carpentry_kitchen': ['נגר', 'מטבח'], 'bathroom_cabinets': ['ארונות'],
    'structural': ['שלד'], 'finishes': ['גמר', 'טיח', 'גבס']}


def _dt(value):
    try:
        value = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None


def _month_parts(month):
    if not isinstance(month, str) or not re.fullmatch(MONTH_RE, month) or month[:4] == '0000':
        raise HTTPException(422, 'חודש לא תקין (YYYY-MM)')
    return int(month[:4]), int(month[5:])


def month_label(month):
    year, number = _month_parts(month)
    return f'{HEBREW_MONTHS[number - 1]} {year}'


def next_month(month):
    year, number = _month_parts(month)
    return f'{year + (number == 12):04d}-{number % 12 + 1:02d}'


def prev_month(month):
    year, number = _month_parts(month)
    return f'{year - (number == 1):04d}-{(number - 2) % 12 + 1:02d}'


def current_il_month(now=None):
    return (_dt(now) if now is not None else datetime.now(timezone.utc)).astimezone(IL_TZ).strftime('%Y-%m')


def month_bounds_utc(month):
    try:
        return tuple(datetime(*_month_parts(m), 1, tzinfo=IL_TZ).astimezone(timezone.utc).isoformat()
                     for m in (month, next_month(month)))
    except (ValueError, OverflowError):
        raise HTTPException(422, 'חודש לא תקין (YYYY-MM)')


def completion_event(cell):
    if cell.get('status') != 'completed':
        return None
    audit = cell.get('audit') or []
    event = next((e for e in reversed(audit) if e.get('status_after') == 'completed'
                  and e.get('status_before') != 'completed'), None)
    timestamp = event.get('timestamp') if event else cell.get('last_updated_at')
    stamp = _dt(timestamp)
    if stamp is None:
        return None
    qc = event.get('source') == 'qc_sync' if event else bool(cell.get('synced_from_qc'))
    return {'completed_at': stamp.isoformat(), 'source': 'qc' if qc else 'manual',
            'actor_name': (event or (audit[-1] if audit else {})).get('actor_name', '')}


def default_settings():
    return {'stage_companies': {}, 'contractor_visible': False, 'updated_at': None, 'updated_by': None}


def validate_settings(body, stage_ids, company_ids):
    mapping = body.get('stage_companies', {})
    if not isinstance(mapping, dict) or any(
        stage not in stage_ids or (company is not None and
        (not isinstance(company, str) or company not in company_ids)) for stage, company in mapping.items()
    ):
        raise HTTPException(422, 'שלב או קבלן לא קיימים בפרויקט')
    return {'stage_companies': dict(mapping), 'contractor_visible': bool(body.get('contractor_visible', False))}


def suggest_stage_companies(stages, companies):
    result = {}
    for stage in stages:
        matches = []
        for company in companies:
            words = TRADE_STAGE_KEYWORDS.get(company.get('trade'), [(company.get('trade_label') or '')[:4]])
            if any(word and word in stage.get('title', '') for word in words):
                matches.append(company['id'])
        if len(matches) == 1:
            result[stage['id']] = matches[0]
    return result


def paid_keys(snapshots):
    paid = {}
    for snapshot in sorted(snapshots, key=lambda s: s['month']):
        for key in snapshot.get('baseline_keys', []):
            paid[tuple(key)] = BASELINE
        for company in snapshot.get('contractors', []):
            for stage in company.get('stages', []):
                for unit_id in stage.get('unit_ids_this_month', []):
                    paid[(stage['stage_id'], unit_id)] = snapshot['month']
        for correction in snapshot.get('corrections', []):
            paid.pop((correction['stage_id'], correction['unit_id']), None)
    return paid


def build_account(month, *, stages, units, buildings, floors, cells, companies,
                  settings, snapshots, runs_by_floor, runs_by_unit, now):
    start_iso, end_iso = month_bounds_utc(month)
    start, end = _dt(start_iso), _dt(end_iso)
    closed = {s['month'] for s in snapshots}
    last_closed = max(closed) if closed else None
    next_closable = next_month(last_closed) if last_closed else month
    applying = month == next_closable and bool(snapshots)
    mapping, paid = settings.get('stage_companies', {}), paid_keys(snapshots)
    ub, bb, fb = ({x['id']: x for x in rows} for rows in (units, buildings, floors))
    ordered_units = sorted(units, key=lambda u: _unit_sort_key(u, bb, fb))
    ordered_buildings = sorted(buildings, key=lambda b: _unit_sort_key({'building_id': b['id']}, bb, fb))
    events = {(c['stage_id'], c['unit_id']): completion_event(c) for c in cells}
    # Reopening is a state check over ALL cells, not a mapped/event-only subset.
    done = {(c['stage_id'], c['unit_id']) for c in cells if c.get('status') == 'completed'}
    companies_by_id = {c['id']: c for c in companies}
    contractors, baseline = {}, []

    def contractor(cid, historical=None):
        if cid not in contractors:
            c = historical or companies_by_id.get(cid, {})
            contractors[cid] = {'company_id': cid, 'name': c.get('name', ''), 'trade': c.get('trade', ''),
                                'stages': [], 'totals': dict.fromkeys(('this_month', 'cumulative', 'qc', 'manual'), 0),
                                'corrections': []}
        return contractors[cid]

    for stage in stages:
        sid, cid = stage['id'], mapping.get(stage['id'])
        if not cid:
            continue
        target, evidence = contractor(cid), []
        for unit in ordered_units:
            key = (sid, unit['id'])
            event = events.get(key)
            if not event:
                continue
            stamp = _dt(event['completed_at'])
            if not snapshots and stamp < start:
                baseline.append(list(key))
            if key in paid or not (start <= stamp < end or (applying and stamp < start)):
                continue
            floor = fb.get(unit.get('floor_id'), {})
            evidence.append({**event, 'unit_id': unit['id'], 'unit_no': unit.get('unit_no', ''),
                'building_name': bb.get(unit.get('building_id'), {}).get('name', ''),
                'building_id': unit.get('building_id'), 'floor_number': floor.get('floor_number'),
                'floor_id': unit.get('floor_id'), 'stage_id': sid,
                'completed_date_il': stamp.astimezone(IL_TZ).strftime('%Y-%m-%d'),
                'late_from_month': current_il_month(stamp) if stamp < start else None,
                'qc_run_id': runs_by_unit.get(unit['id']) if stage.get('scope') == 'unit'
                else runs_by_floor.get(unit.get('floor_id'))})
        still = {uid for (s, uid) in paid if s == sid and (s, uid) in done}
        cumulative = len(still) + len(evidence)
        qc = sum(e['source'] == 'qc' for e in evidence)
        by_building = []
        for building in ordered_buildings:
            ids = {u['id'] for u in units if u.get('building_id') == building['id']}
            rows = [e for e in evidence if e['unit_id'] in ids]
            bqc = sum(e['source'] == 'qc' for e in rows)
            by_building.append({'building_id': building['id'], 'building_name': building.get('name', ''),
                'total_units': len(ids), 'this_month': len(rows), 'cumulative': len(still & ids) + len(rows),
                'qc_count': bqc, 'manual_count': len(rows) - bqc})
        target['stages'].append({'stage_id': sid, 'title': stage.get('title', ''),
            'this_month': len(evidence), 'cumulative': cumulative, 'still_paid': len(still),
            'total_units': len(units), 'pct': round(100 * cumulative / len(units)) if units else 0,
            'qc_count': qc, 'manual_count': len(evidence) - qc, 'by_building': by_building,
            'unit_ids_this_month': [e['unit_id'] for e in evidence], 'evidence': evidence})
        for key, amount in [('this_month', len(evidence)), ('cumulative', cumulative),
                            ('qc', qc), ('manual', len(evidence) - qc)]:
            target['totals'][key] += amount
    if applying:
        for (sid, uid), counted in paid.items():
            if (sid, uid) in done:
                continue
            historical, old_stage, old_evidence = None, {}, {}
            if counted != BASELINE:
                snap = next(s for s in snapshots if s['month'] == counted)
                for c in snap.get('contractors', []):
                    for st in c.get('stages', []):
                        if st['stage_id'] == sid and uid in st.get('unit_ids_this_month', []):
                            historical, old_stage = c, st
                            old_evidence = next((e for e in st.get('evidence', []) if e['unit_id'] == uid), {})
            cid = historical['company_id'] if historical else mapping.get(sid)
            if not cid:
                continue
            unit = ub.get(uid, {})
            stage = next((s for s in stages if s['id'] == sid), {})
            contractor(cid, historical)['corrections'].append({
                'stage_id': sid, 'stage_title': old_stage.get('title', stage.get('title', '')),
                'unit_id': uid, 'unit_no': old_evidence.get('unit_no', unit.get('unit_no', '')),
                'building_name': old_evidence.get('building_name', bb.get(unit.get('building_id'), {}).get('name', '')),
                'company_id': cid, 'company_name': contractor(cid, historical)['name'],
                'counted_in_month': counted, 'reason': 'reopened'})
    result = sorted(contractors.values(), key=lambda c: c['name'])
    return {'month': month, 'label': month_label(month), 'status': 'open',
        'bounds': {'start': start_iso, 'end': end_iso}, 'closable': month == next_closable
        and month <= current_il_month(now) and month not in closed,
        'next_closable': next_closable, 'last_closed': last_closed, 'applying': applying,
        'unmapped_stages': [{'id': s['id'], 'title': s.get('title', '')} for s in stages if not mapping.get(s['id'])],
        'kpis': {**{k: sum(c['totals'][k] for c in result) for k in ('this_month', 'qc', 'manual')},
                 'corrections': sum(len(c['corrections']) for c in result)},
        'totals': {'units': len(units), 'stages': len(stages)}, 'contractors': result,
        'baseline_keys': baseline, 'settings_snapshot': {'stage_companies': dict(mapping)}}


def build_snapshot(account, project, user, note, now):
    doc = deepcopy({k: account[k] for k in ('month', 'label', 'kpis', 'contractors', 'unmapped_stages',
                    'totals', 'baseline_keys', 'settings_snapshot')})
    doc.update({'id': str(uuid.uuid4()), 'project_id': project['id'],
        'project': {'id': project['id'], 'name': project.get('name', '')}, 'project_name': project.get('name', ''),
        'closed_at': _dt(now).isoformat(),
        'closed_date_il': _dt(now).astimezone(IL_TZ).strftime('%Y-%m-%d'),
        'closed_by': {'id': user['id'], 'name': user.get('name', '')},
        'note': str(note or '').strip()[:500] or None, 'status': 'closed',
        'previous_month': account.get('last_closed') or BASELINE,
        'corrections': deepcopy([r for c in account['contractors'] for r in c['corrections']])})
    return doc


async def load_inputs(db, project_id):
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    config = await db.execution_matrix.find_one({'project_id': project_id, 'deletedAt': None}, {'_id': 0}) or {}
    tpl = await _get_template(db, project_id=project_id)
    stages = _resolve_visible_stages(config, tpl)
    units = await db.units.find({'project_id': project_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(2000)
    floor_ids = list({u['floor_id'] for u in units if u.get('floor_id')})
    building_ids = list({u['building_id'] for u in units if u.get('building_id')})
    floors = await db.floors.find({'id': {'$in': floor_ids}, 'archived': {'$ne': True}}, {'_id': 0}).to_list(500) if floor_ids else []
    buildings = await db.buildings.find({'id': {'$in': building_ids}, 'archived': {'$ne': True}}, {'_id': 0}).to_list(100) if building_ids else []
    cells = await db.execution_matrix_cells.find({'project_id': project_id}, {'_id': 0}).to_list(None)
    companies = await db.project_companies.find({'project_id': project_id, 'deletedAt': {'$exists': False}}, {'_id': 0}).to_list(None)
    trades = await db.project_trades.find({'project_id': project_id}, {'_id': 0}).to_list(None)
    labels = {**BUCKET_LABELS, **{t['key']: t.get('label_he', '') for t in trades if t.get('key')}}
    companies = [{**c, 'trade_label': labels.get(c.get('trade'), c.get('trade_label', c.get('trade', '')))} for c in companies]
    snapshots = await db.monthly_progress_closes.find({'project_id': project_id}, {'_id': 0}).sort('month', 1).to_list(None)
    runs_by_floor, runs_by_unit = {}, {}
    if floor_ids:
        async for r in db.qc_runs.find({'project_id': project_id, 'floor_id': {'$in': floor_ids},
                                       'scope': {'$ne': 'unit'}}, {'_id': 0, 'id': 1, 'floor_id': 1}):
            runs_by_floor[r['floor_id']] = r['id']
    if units:
        async for r in db.qc_runs.find({'project_id': project_id, 'unit_id': {'$in': [u['id'] for u in units]},
                                       'scope': 'unit'}, {'_id': 0, 'id': 1, 'unit_id': 1}):
            runs_by_unit[r['unit_id']] = r['id']
    return {'project': project, 'stages': stages, 'units': units, 'floors': floors, 'buildings': buildings,
            'cells': cells, 'companies': companies, 'settings': project.get('monthly_close_settings') or default_settings(),
            'snapshots': snapshots, 'runs_by_floor': runs_by_floor, 'runs_by_unit': runs_by_unit}


async def ensure_indexes(db):
    try:
        await db.monthly_progress_closes.create_index([('project_id', 1), ('month', 1)],
                                                      unique=True, name='uniq_project_month')
        # A second first-close request may choose another month: prohibit branching.
        await db.monthly_progress_closes.create_index([('project_id', 1), ('previous_month', 1)],
            unique=True, name='uniq_project_close_predecessor', partialFilterExpression={'previous_month': {'$exists': True}})
    except Exception:
        logging.getLogger(__name__).exception('Monthly close indexes could not be created')