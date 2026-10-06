"""Project-scoped contract item authoring; never writes execution data."""
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError
from contractor_ops.monthly_close_router import _access, _require
from contractor_ops.monthly_close import load_inputs, current_il_month, _month_parts
from contractor_ops.router import get_db, get_current_user, _now, _audit
from contractor_ops.contract_items import validate_item, _number

router = APIRouter(prefix='/api')
DUPLICATE = 'קוד הסעיף כבר קיים אצל הקבלן הזה'


def _tags(inputs):
    return sorted({u['unit_type_tag'] for u in inputs.get('units', []) if u.get('unit_type_tag')})


async def _context(project_id, user, write=False):
    db = get_db()
    access = await _access(user, project_id, db)
    if write:
        _require(access, write=True)
    return db, access


async def _item(db, project_id, item_id):
    doc = await db.contract_items.find_one({'id': item_id, 'project_id': project_id}, {'_id': 0})
    if not doc:
        raise HTTPException(404, 'הסעיף לא נמצא')
    return doc


async def _clean(db, project_id, body, existing=None):
    inputs = await load_inputs(db, project_id)
    clean = validate_item(body, stages={s['id'] for s in inputs['stages']},
        company_ids={c['id'] for c in inputs['companies']}, unit_type_tags=_tags(inputs), existing=existing)
    if clean['code']:
        query = dict(project_id=project_id, company_id=clean['company_id'], code=clean['code'], active=True)
        if existing:
            query['id'] = {'$ne': existing['id']}
        if await db.contract_items.find_one(query, {'_id': 0, 'id': 1}):
            raise HTTPException(409, DUPLICATE)
    return clean


@router.get('/projects/{project_id}/contract-items')
async def list_items(project_id: str, user: dict = Depends(get_current_user)):
    db, access = await _context(project_id, user)
    inputs = await load_inputs(db, project_id)
    items = inputs.get('contract_items') or []
    if access['role'] == 'contractor':
        items = [i for i in items if i.get('company_id') == access['company_id']]
    return {'items': items, 'unit_type_tags': _tags(inputs),
            'stages': [{k: s.get(k) for k in ('id', 'title', 'scope')} for s in inputs['stages']],
            'can_write': access['can_write']}


@router.post('/projects/{project_id}/contract-items')
async def create_item(project_id: str, body: dict, user: dict = Depends(get_current_user)):
    db, _ = await _context(project_id, user, True)
    clean = await _clean(db, project_id, body)
    now = _now()
    doc = dict(clean, id=str(uuid4()), project_id=project_id, measurements={}, active=True,
               created_at=now, created_by=user['id'], updated_at=now, updated_by=user['id'], deactivated_at=None)
    try:
        await db.contract_items.insert_one(dict(doc))
    except DuplicateKeyError:
        raise HTTPException(409, DUPLICATE)
    await _audit('contract_item', doc['id'], 'create', user['id'],
                 {k: doc[k] for k in ('company_id', 'code', 'description', 'source', 'stage_id')})
    return doc


@router.patch('/projects/{project_id}/contract-items/{item_id}')
async def update_item(project_id: str, item_id: str, body: dict, user: dict = Depends(get_current_user)):
    db, _ = await _context(project_id, user, True)
    doc = await _item(db, project_id, item_id)
    if body.get('active') is False:
        changes, action = {'active': False, 'deactivated_at': _now()}, 'deactivate'
    else:
        changes, action = await _clean(db, project_id, {**doc, **body}, doc), 'update'
    changes.update(updated_at=_now(), updated_by=user['id'])
    try:
        await db.contract_items.update_one({'id': item_id, 'project_id': project_id}, {'$set': changes})
    except DuplicateKeyError:
        raise HTTPException(409, DUPLICATE)
    await _audit('contract_item', item_id, action, user['id'], changes)
    return {**doc, **changes}


@router.put('/projects/{project_id}/contract-items/{item_id}/measurements/{month}')
async def set_measurement(project_id: str, item_id: str, month: str, body: dict,
                          user: dict = Depends(get_current_user)):
    db, _ = await _context(project_id, user, True)
    _month_parts(month)
    doc = await _item(db, project_id, item_id)
    if doc.get('source') != 'measured' or not doc.get('active'):
        raise HTTPException(422, 'הקלדה אפשרית רק בסעיף נמדד')
    if await db.monthly_progress_closes.find_one({'project_id': project_id, 'month': month}):
        raise HTTPException(409, 'החודש כבר נסגר')
    if month > current_il_month():
        raise HTTPException(422, 'אי אפשר להקליד לחודש עתידי')
    qty = body.get('qty')
    qty = 0 if qty is None else _number(qty, 0, 1000000, 'כמות לא תקינה')
    note = body.get('note', '')
    if not isinstance(note, str) or len(note) > 300:
        raise HTTPException(422, 'הערה לא תקינה')
    entry = {'qty': qty, 'note': note, 'by': {'id': user['id'], 'name': user.get('name', '')}, 'at': _now()}
    path = f'measurements.{month}'
    change = {'$set': {path: entry}} if qty else {'$unset': {path: ''}}
    result = await db.contract_items.update_one(
        {'id': item_id, 'project_id': project_id, 'active': True, 'source': 'measured'}, change)
    if result.matched_count == 0:
        raise HTTPException(422, 'הקלדה אפשרית רק בסעיף נמדד')
    await _audit('contract_item', item_id, 'measure', user['id'], {'month': month, 'qty': qty})
    entries = dict(doc.get('measurements') or {})
    if qty:
        entries[month] = entry
    else:
        entries.pop(month, None)
    return {**doc, 'measurements': entries}
