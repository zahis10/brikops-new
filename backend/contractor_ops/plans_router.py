import uuid
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form, Body
from contractor_ops.router import (
    get_db, get_current_user, _check_project_read_access,
    _get_project_membership, _audit, _now,
    PLAN_DISCIPLINES, PLAN_UPLOAD_ROLES,
)

router = APIRouter(prefix="/api")


@router.get("/projects/{project_id}/plans")
async def list_project_plans(
    project_id: str,
    discipline: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    query = {
        'project_id': project_id,
        'deletedAt': {'$exists': False},
        'status': {'$ne': 'archived'},
    }
    if discipline:
        query['discipline'] = discipline
    plans = await db.project_plans.find(query, {'_id': 0}).sort('created_at', -1).to_list(500)
    from services.object_storage import resolve_urls_in_doc
    for p in plans:
        uploader = await db.users.find_one({'id': p.get('uploaded_by')}, {'_id': 0, 'name': 1})
        p['uploaded_by_name'] = uploader.get('name', '') if uploader else ''
        resolve_urls_in_doc(p)
    return plans


@router.get("/projects/{project_id}/plans/archive")
async def list_project_plans_archive(
    project_id: str,
    discipline: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    query = {
        'project_id': project_id,
        'deletedAt': {'$exists': False},
        'status': 'archived',
    }
    if discipline:
        query['discipline'] = discipline
    plans = await db.project_plans.find(query, {'_id': 0}).sort('archived_at', -1).to_list(500)
    from services.object_storage import resolve_urls_in_doc
    for p in plans:
        uploader = await db.users.find_one({'id': p.get('uploaded_by')}, {'_id': 0, 'name': 1})
        p['uploaded_by_name'] = uploader.get('name', '') if uploader else ''
        archiver = await db.users.find_one({'id': p.get('archived_by')}, {'_id': 0, 'name': 1})
        p['archived_by_name'] = archiver.get('name', '') if archiver else ''
        resolve_urls_in_doc(p)
    return plans


@router.post("/projects/{project_id}/plans")
async def upload_project_plan(
    project_id: str,
    file: UploadFile = File(...),
    discipline: str = Form(...),
    note: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    await _check_project_read_access(user, project_id)

    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    if requester_role not in PLAN_UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail='אין לך הרשאה להעלות תוכניות')

    custom_disciplines = await db.project_disciplines.find(
        {'project_id': project_id}, {'_id': 0, 'key': 1}
    ).to_list(100)
    custom_keys = {d['key'] for d in custom_disciplines}
    all_valid = set(PLAN_DISCIPLINES) | custom_keys
    if discipline not in all_valid:
        raise HTTPException(status_code=422, detail=f'תחום לא תקין. אפשרויות: {", ".join(sorted(all_valid))}')

    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')

    from services.storage_service import StorageService
    storage = StorageService()
    result = await storage.upload_file_with_details(file, f"project_plan_{project_id}_{discipline}")

    plan_id = str(uuid.uuid4())
    plan_doc = {
        'id': plan_id,
        'project_id': project_id,
        'discipline': discipline,
        'file_url': result.file_url,
        'original_filename': file.filename,
        'file_size': result.file_size,
        'uploaded_by': user['id'],
        'note': note or '',
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.project_plans.insert_one(plan_doc)
    plan_doc.pop('_id', None)

    await _audit('project_plan', plan_id, 'upload', user['id'], {
        'discipline': discipline,
        'filename': file.filename,
        'project_id': project_id,
    })

    from services.object_storage import resolve_urls_in_doc
    return resolve_urls_in_doc(dict(plan_doc))


@router.get("/projects/{project_id}/plans/{plan_id}/history")
async def get_project_plan_history(
    project_id: str,
    plan_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)

    current = await db.project_plans.find_one({
        'id': plan_id,
        'project_id': project_id,
        'deletedAt': {'$exists': False},
    }, {'_id': 0})
    if not current:
        raise HTTPException(status_code=404, detail='תוכנית לא נמצאה')

    from services.object_storage import resolve_urls_in_doc

    chain = []
    visited = set()
    cursor = current

    while cursor and len(chain) < 50:
        if cursor['id'] in visited:
            break
        visited.add(cursor['id'])
        uploader = await db.users.find_one({'id': cursor.get('uploaded_by')}, {'_id': 0, 'name': 1})
        cursor['uploaded_by_name'] = uploader.get('name', '') if uploader else ''
        resolve_urls_in_doc(cursor)
        chain.append(cursor)

        prev_id = cursor.get('replaces_plan_id')
        if not prev_id:
            break
        cursor = await db.project_plans.find_one({
            'id': prev_id,
            'project_id': project_id,
            'deletedAt': {'$exists': False},
        }, {'_id': 0})

    return {'plan_id': plan_id, 'project_id': project_id, 'versions': chain}


@router.post("/projects/{project_id}/plans/{plan_id}/replace")
async def replace_project_plan(
    project_id: str,
    plan_id: str,
    file: UploadFile = File(...),
    note: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    await _check_project_read_access(user, project_id)
    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    if requester_role not in PLAN_UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail='אין לך הרשאה להחליף תוכניות')

    old_plan = await db.project_plans.find_one({
        'id': plan_id,
        'project_id': project_id,
        'deletedAt': {'$exists': False},
        'status': {'$ne': 'archived'},
    })
    if not old_plan:
        raise HTTPException(status_code=404, detail='תוכנית פעילה לא נמצאה')

    discipline = old_plan['discipline']

    from services.storage_service import StorageService
    storage = StorageService()
    result = await storage.upload_file_with_details(file, f"project_plan_{project_id}_{discipline}")

    new_plan_id = str(uuid.uuid4())
    ts = _now()
    new_plan_doc = {
        'id': new_plan_id,
        'project_id': project_id,
        'discipline': discipline,
        'file_url': result.file_url,
        'original_filename': file.filename,
        'file_size': result.file_size,
        'uploaded_by': user['id'],
        'note': note or '',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'replaces_plan_id': plan_id,
    }
    await db.project_plans.insert_one(new_plan_doc)
    new_plan_doc.pop('_id', None)

    await db.project_plans.update_one({'id': plan_id}, {'$set': {
        'status': 'archived',
        'archive_reason': 'replaced',
        'archived_at': ts,
        'archived_by': user['id'],
        'replaced_by_plan_id': new_plan_id,
    }})

    await _audit('project_plan', new_plan_id, 'project_plan_replace_upload', user['id'], {
        'project_id': project_id,
        'discipline': discipline,
        'filename': file.filename,
        'replaces_plan_id': plan_id,
        'old_filename': old_plan.get('original_filename', ''),
    })
    await _audit('project_plan', plan_id, 'project_plan_replaced', user['id'], {
        'project_id': project_id,
        'discipline': discipline,
        'replaced_by_plan_id': new_plan_id,
        'new_filename': file.filename,
    })

    from services.object_storage import resolve_urls_in_doc
    return resolve_urls_in_doc(dict(new_plan_doc))


@router.patch("/projects/{project_id}/plans/{plan_id}/archive")
async def archive_project_plan(
    project_id: str,
    plan_id: str,
    body: dict = Body(default={}),
    user: dict = Depends(get_current_user),
):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    await _check_project_read_access(user, project_id)
    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    if requester_role not in PLAN_UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail='אין לך הרשאה לארכב תוכניות')

    plan = await db.project_plans.find_one({
        'id': plan_id,
        'project_id': project_id,
        'deletedAt': {'$exists': False},
        'status': {'$ne': 'archived'},
    })
    if not plan:
        raise HTTPException(status_code=404, detail='תוכנית לא נמצאה או כבר בארכיון')

    ts = _now()
    await db.project_plans.update_one({'id': plan_id}, {'$set': {
        'status': 'archived',
        'archive_reason': 'manual',
        'archived_at': ts,
        'archived_by': user['id'],
        'archive_note': (body.get('note') or '').strip(),
    }})

    await _audit('project_plan', plan_id, 'project_plan_archived', user['id'], {
        'project_id': project_id,
        'discipline': plan.get('discipline', ''),
        'filename': plan.get('original_filename', ''),
        'archive_reason': 'manual',
    })

    return {'success': True}


@router.patch("/projects/{project_id}/plans/{plan_id}/restore")
async def restore_project_plan(
    project_id: str,
    plan_id: str,
    user: dict = Depends(get_current_user),
):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    await _check_project_read_access(user, project_id)
    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    if requester_role not in PLAN_UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail='אין לך הרשאה לשחזר תוכניות')

    plan = await db.project_plans.find_one({
        'id': plan_id,
        'project_id': project_id,
        'deletedAt': {'$exists': False},
        'status': 'archived',
    })
    if not plan:
        raise HTTPException(status_code=404, detail='תוכנית לא נמצאה בארכיון')

    await db.project_plans.update_one({'id': plan_id}, {'$unset': {
        'status': '',
        'archive_reason': '',
        'archived_at': '',
        'archived_by': '',
        'archive_note': '',
    }})

    await _audit('project_plan', plan_id, 'project_plan_restored', user['id'], {
        'project_id': project_id,
        'discipline': plan.get('discipline', ''),
        'filename': plan.get('original_filename', ''),
    })

    return {'success': True}


@router.get("/projects/{project_id}/units/{unit_id}/plans")
async def list_unit_plans(
    project_id: str,
    unit_id: str,
    discipline: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)
    unit = await db.units.find_one({'id': unit_id, 'project_id': project_id})
    if not unit:
        raise HTTPException(status_code=404, detail='דירה לא נמצאה בפרויקט זה')
    query = {'project_id': project_id, 'unit_id': unit_id}
    if discipline:
        query['discipline'] = discipline
    plans = await db.unit_plans.find(query, {'_id': 0}).sort('created_at', -1).to_list(500)
    from services.object_storage import resolve_urls_in_doc
    for p in plans:
        uploader = await db.users.find_one({'id': p.get('uploaded_by')}, {'_id': 0, 'name': 1})
        p['uploaded_by_name'] = uploader.get('name', '') if uploader else ''
        resolve_urls_in_doc(p)
    return plans


@router.post("/projects/{project_id}/units/{unit_id}/plans")
async def upload_unit_plan(
    project_id: str,
    unit_id: str,
    file: UploadFile = File(...),
    discipline: str = Form(...),
    note: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    await _check_project_read_access(user, project_id)

    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    if requester_role not in PLAN_UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail='אין לך הרשאה להעלות תוכניות')

    custom_disciplines = await db.project_disciplines.find(
        {'project_id': project_id}, {'_id': 0, 'key': 1}
    ).to_list(100)
    custom_keys = {d['key'] for d in custom_disciplines}
    all_valid = set(PLAN_DISCIPLINES) | custom_keys
    if discipline not in all_valid:
        raise HTTPException(status_code=422, detail=f'תחום לא תקין. אפשרויות: {", ".join(sorted(all_valid))}')

    unit = await db.units.find_one({'id': unit_id, 'project_id': project_id})
    if not unit:
        raise HTTPException(status_code=404, detail='דירה לא נמצאה בפרויקט זה')

    from services.storage_service import StorageService
    storage = StorageService()
    result = await storage.upload_file_with_details(file, f"plan_{unit_id}_{discipline}")

    plan_id = str(uuid.uuid4())
    plan_doc = {
        'id': plan_id,
        'project_id': project_id,
        'unit_id': unit_id,
        'discipline': discipline,
        'file_url': result.file_url,
        'original_filename': file.filename,
        'file_size': result.file_size,
        'uploaded_by': user['id'],
        'note': note or '',
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    await db.unit_plans.insert_one(plan_doc)
    plan_doc.pop('_id', None)

    await _audit('unit_plan', plan_id, 'upload', user['id'], {
        'discipline': discipline,
        'filename': file.filename,
        'unit_id': unit_id,
        'project_id': project_id,
    })

    from services.object_storage import resolve_urls_in_doc
    return resolve_urls_in_doc(dict(plan_doc))


@router.get("/projects/{project_id}/disciplines")
async def list_project_disciplines(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)
    defaults = [{'key': d, 'label': d, 'source': 'default'} for d in PLAN_DISCIPLINES]
    custom = await db.project_disciplines.find(
        {'project_id': project_id}, {'_id': 0}
    ).to_list(100)
    for c in custom:
        c.pop('project_id', None)
    return defaults + [{'key': c['key'], 'label': c.get('label', c['key']), 'source': 'custom'} for c in custom]


@router.post("/projects/{project_id}/disciplines")
async def add_project_discipline(
    project_id: str,
    body: dict = Body(...),
    user: dict = Depends(get_current_user),
):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    await _check_project_read_access(user, project_id)
    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    if requester_role not in PLAN_UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail='אין לך הרשאה להוסיף תחומים')

    label = (body.get('label') or '').strip()
    if not label:
        raise HTTPException(status_code=422, detail='שם תחום נדרש')
    import re
    key = re.sub(r'[^a-z0-9_]', '_', label.lower().strip()).strip('_')
    key = re.sub(r'_+', '_', key)
    if not key:
        key = 'custom_' + str(uuid.uuid4())[:8]

    if key in PLAN_DISCIPLINES:
        raise HTTPException(status_code=409, detail='תחום ברירת מחדל כבר קיים')
    existing = await db.project_disciplines.find_one({'project_id': project_id, 'key': key})
    if existing:
        raise HTTPException(status_code=409, detail='תחום זה כבר קיים בפרויקט')

    doc = {
        'id': str(uuid.uuid4()),
        'project_id': project_id,
        'key': key,
        'label': label,
        'source': 'custom',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'created_by': user['id'],
    }
    await db.project_disciplines.insert_one(doc)
    doc.pop('_id', None)

    await _audit('project_discipline', doc['id'], 'project_discipline_add', user['id'], {
        'project_id': project_id,
        'key': key,
        'label': label,
    })

    return {'key': key, 'label': label, 'source': 'custom'}


@router.delete("/projects/{project_id}/plans/{plan_id}")
async def delete_project_plan(
    project_id: str,
    plan_id: str,
    body: dict = Body(...),
    user: dict = Depends(get_current_user),
):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    await _check_project_read_access(user, project_id)
    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    if requester_role not in PLAN_UPLOAD_ROLES:
        raise HTTPException(status_code=403, detail='אין לך הרשאה למחוק תוכניות')

    reason = (body.get('reason') or '').strip()
    if not reason:
        raise HTTPException(status_code=422, detail='חובה לציין סיבה למחיקה')

    plan = await db.project_plans.find_one({'id': plan_id, 'project_id': project_id, 'deletedAt': {'$exists': False}})
    if not plan:
        raise HTTPException(status_code=404, detail='תוכנית לא נמצאה')

    await db.project_plans.update_one({'id': plan_id}, {'$set': {'deletedAt': _now(), 'deletedBy': user['id'], 'deleteReason': reason}})

    await _audit('project_plan', plan_id, 'project_plan_soft_delete', user['id'], {
        'project_id': project_id,
        'discipline': plan.get('discipline', ''),
        'filename': plan.get('original_filename', ''),
        'reason': reason,
        'original_uploader': plan.get('uploaded_by', ''),
    })

    return {'success': True}
