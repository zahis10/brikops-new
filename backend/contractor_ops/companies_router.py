import re
import uuid
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from contractor_ops.router import (
    get_db, get_current_user, require_roles,
    _check_project_access, _check_project_read_access, _audit, _now,
)
from contractor_ops.schemas import Company
from contractor_ops.bucket_utils import BUCKET_LABELS

router = APIRouter(prefix="/api")


@router.post("/companies", response_model=Company)
async def create_company(company: Company, user: dict = Depends(require_roles('project_manager', 'management_team'))):
    db = get_db()
    company_id = str(uuid.uuid4())
    doc = {
        'id': company_id, 'name': company.name,
        'trade': company.trade.value if company.trade else None,
        'contact_name': company.contact_name, 'contact_phone': company.contact_phone,
        'contact_email': company.contact_email, 'created_at': _now(),
    }
    await db.companies.insert_one(doc)
    await _audit('company', company_id, 'create', user['id'], {'name': company.name})
    return Company(**{k: v for k, v in doc.items() if k != '_id'})


@router.get("/companies", response_model=List[Company])
async def list_companies(user: dict = Depends(get_current_user)):
    db = get_db()
    companies = await db.companies.find({}, {'_id': 0}).to_list(1000)
    return [Company(**c) for c in companies]


# ── Project-scoped companies ──
@router.post("/projects/{project_id}/companies")
async def create_project_company(project_id: str, body: dict = Body(...), user: dict = Depends(require_roles('project_manager', 'management_team'))):
    db = get_db()
    await _check_project_access(user, project_id)
    name = (body.get('name') or '').strip()
    trade = (body.get('trade') or '').strip() or None
    contact_name = (body.get('contact_name') or '').strip() or None
    contact_phone = (body.get('contact_phone') or '').strip() or None
    if not name:
        raise HTTPException(status_code=422, detail='שם חברה הוא שדה חובה')
    phone_e164 = None
    if contact_phone:
        from .phone_utils import normalize_israeli_phone
        try:
            phone_result = normalize_israeli_phone(contact_phone)
            phone_e164 = phone_result.get('phone_e164') or contact_phone
        except (ValueError, Exception):
            phone_e164 = contact_phone
    company_id = str(uuid.uuid4())
    doc = {
        'id': company_id, 'project_id': project_id,
        'name': name,
        'trade': trade,
        'contact_name': contact_name,
        'contact_phone': phone_e164,
        'contact_phone_raw': contact_phone,
        'contact_email': body.get('contact_email'),
        'created_at': _now(),
    }
    await db.project_companies.insert_one(doc)
    await _audit('project_company', company_id, 'create', user['id'], {'project_id': project_id, 'name': doc['name']})
    return {k: v for k, v in doc.items() if k != '_id'}


@router.get("/projects/{project_id}/companies")
async def list_project_companies(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    await _check_project_read_access(user, project_id)
    companies = await db.project_companies.find({'project_id': project_id, 'deletedAt': {'$exists': False}}, {'_id': 0}).to_list(1000)
    return companies


@router.put("/projects/{project_id}/companies/{company_id}")
async def update_project_company(project_id: str, company_id: str, body: dict = Body(...), user: dict = Depends(require_roles('project_manager', 'management_team'))):
    db = get_db()
    await _check_project_access(user, project_id)
    existing = await db.project_companies.find_one({'id': company_id, 'project_id': project_id, 'deletedAt': {'$exists': False}})
    if not existing:
        raise HTTPException(status_code=404, detail='Company not found')
    update_data = {}
    for field in ('name', 'trade', 'contact_name', 'contact_phone', 'contact_email'):
        if field in body:
            update_data[field] = body[field]
    if update_data:
        await db.project_companies.update_one({'id': company_id}, {'$set': update_data})
    await _audit('project_company', company_id, 'update', user['id'], update_data)
    updated = await db.project_companies.find_one({'id': company_id}, {'_id': 0})
    return updated


@router.delete("/projects/{project_id}/companies/{company_id}")
async def delete_project_company(project_id: str, company_id: str, user: dict = Depends(require_roles('project_manager', 'management_team'))):
    db = get_db()
    await _check_project_access(user, project_id)
    existing = await db.project_companies.find_one({'id': company_id, 'project_id': project_id, 'deletedAt': {'$exists': False}})
    if not existing:
        raise HTTPException(status_code=404, detail='Company not found')
    await db.project_companies.update_one({'id': company_id}, {'$set': {'deletedAt': _now(), 'deletedBy': user['id']}})
    await _audit('project_company', company_id, 'soft_delete', user['id'], {'project_id': project_id, 'name': existing.get('name', '')})
    return {'success': True}


# ── Project-level custom trades ──

def _slugify_hebrew(label: str) -> str:
    slug = label.strip().lower().replace(' ', '_').replace('/', '_')
    slug = re.sub(r'[^a-z0-9_\u0590-\u05ff]', '', slug)
    if not slug:
        slug = f"custom_{uuid.uuid4().hex[:8]}"
    return slug


@router.get("/projects/{project_id}/trades")
async def list_project_trades(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    await _check_project_read_access(user, project_id)
    base_trades = [{'key': k, 'label_he': v, 'source': 'global'} for k, v in BUCKET_LABELS.items()]
    custom_trades = await db.project_trades.find({'project_id': project_id}, {'_id': 0}).to_list(500)
    custom_list = [{'key': t['key'], 'label_he': t['label_he'], 'source': 'project'} for t in custom_trades]
    seen_keys = {t['key'] for t in custom_list}
    merged = [t for t in base_trades if t['key'] not in seen_keys] + custom_list
    merged.sort(key=lambda t: t['label_he'])
    return {'trades': merged}


@router.post("/projects/{project_id}/trades")
async def create_project_trade(project_id: str, body: dict = Body(...), user: dict = Depends(require_roles('project_manager', 'management_team'))):
    db = get_db()
    await _check_project_access(user, project_id)
    label_he = (body.get('label_he') or '').strip()
    if not label_he:
        raise HTTPException(status_code=422, detail='שם תחום הוא שדה חובה')
    key = body.get('key') or _slugify_hebrew(label_he)
    existing_global = key in BUCKET_LABELS
    existing_project = await db.project_trades.find_one({'project_id': project_id, 'key': key})
    if existing_global or existing_project:
        raise HTTPException(status_code=409, detail='תחום עם מפתח זה כבר קיים')
    doc = {
        'id': str(uuid.uuid4()),
        'project_id': project_id,
        'key': key,
        'label_he': label_he,
        'created_by': user['id'],
        'created_at': _now(),
    }
    await db.project_trades.insert_one(doc)
    await _audit('project_trade', doc['id'], 'create', user['id'], {'project_id': project_id, 'key': key, 'label_he': label_he})
    return {k: v for k, v in doc.items() if k != '_id'}


@router.get("/companies/search")
async def search_companies(q: str = Query('', min_length=2), user: dict = Depends(get_current_user)):
    db = get_db()
    memberships = await db.project_memberships.find(
        {'user_id': user['id']}, {'_id': 0, 'project_id': 1}
    ).to_list(500)
    project_ids = [m['project_id'] for m in memberships]
    if not project_ids:
        return {'suggestions': []}
    escaped_q = re.escape(q.strip())
    regex = re.compile(escaped_q, re.IGNORECASE)
    companies = await db.project_companies.find(
        {
            'project_id': {'$in': project_ids},
            'name': {'$regex': regex},
            'deletedAt': {'$exists': False},
        },
        {'_id': 0, 'name': 1, 'trade': 1, 'contact_name': 1, 'contact_phone': 1, 'project_id': 1}
    ).to_list(200)
    seen = {}
    for c in companies:
        norm_name = re.sub(r'\s+', ' ', (c.get('name') or '').strip()).lower()
        if norm_name and norm_name not in seen:
            seen[norm_name] = {
                'name': c.get('name', '').strip(),
                'trade': c.get('trade'),
                'contact_name': c.get('contact_name'),
                'contact_phone': c.get('contact_phone'),
                'source_project_id': c.get('project_id'),
            }
        if len(seen) >= 10:
            break
    return {'suggestions': list(seen.values())}


@router.get("/trades")
async def list_trades():
    trades = []
    for key, label in BUCKET_LABELS.items():
        trades.append({'key': key, 'label_he': label})
    trades.sort(key=lambda t: t['label_he'])
    return {'trades': trades}
