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


MANAGEMENT_ROLES = ('super_admin', 'project_manager', 'management_team')
TRACKABLE_ROLES = ('project_manager', 'management_team', 'contractor', 'viewer')


@router.get("/projects/{project_id}/plans")
async def list_project_plans(
    project_id: str,
    discipline: Optional[str] = Query(None),
    floor_id: Optional[str] = Query(None),
    plan_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
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
    if floor_id:
        query['floor_id'] = floor_id
    if plan_type:
        query['plan_type'] = plan_type
    if search:
        import re
        search_re = re.compile(re.escape(search.strip()), re.IGNORECASE)
        query['$or'] = [
            {'name': {'$regex': search_re}},
            {'original_filename': {'$regex': search_re}},
            {'note': {'$regex': search_re}},
        ]
    plans = await db.project_plans.find(query, {'_id': 0}).sort('created_at', -1).to_list(500)
    from services.object_storage import resolve_urls_in_doc

    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none') if requester_membership else 'none'
    is_manager = requester_role in MANAGEMENT_ROLES or user.get('role') == 'super_admin'

    total_members = 0
    if is_manager and plans:
        total_members = await db.project_memberships.count_documents({
            'project_id': project_id,
            'role': {'$in': list(TRACKABLE_ROLES)},
        })

    plan_ids = [p['id'] for p in plans]
    seen_counts = {}
    if is_manager and plan_ids:
        pipeline = [
            {'$match': {'plan_id': {'$in': plan_ids}}},
            {'$group': {'_id': '$plan_id', 'count': {'$sum': 1}}},
        ]
        async for doc in db.plan_read_receipts.aggregate(pipeline):
            seen_counts[doc['_id']] = doc['count']

    for p in plans:
        uploader = await db.users.find_one({'id': p.get('uploaded_by')}, {'_id': 0, 'name': 1})
        p['uploaded_by_name'] = uploader.get('name', '') if uploader else ''
        resolve_urls_in_doc(p)
        if is_manager:
            p['seen_count'] = seen_counts.get(p['id'], 0)
            p['total_members'] = total_members
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
    name: Optional[str] = Form(None),
    plan_type: Optional[str] = Form('standard'),
    floor_id: Optional[str] = Form(None),
    unit_id: Optional[str] = Form(None),
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

    if plan_type and plan_type not in ('standard', 'tenant_changes'):
        raise HTTPException(status_code=422, detail='סוג תוכנית לא תקין')

    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')

    file_bytes = await file.read()
    file_size = len(file_bytes)
    if file_size > 50 * 1024 * 1024:
        raise HTTPException(status_code=422, detail='קובץ גדול מדי (מקסימום 50MB)')
    await file.seek(0)

    from services.storage_service import StorageService
    storage = StorageService()
    result = await storage.upload_file_with_details(file, f"project_plan_{project_id}_{discipline}")

    plan_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    v1_entry = {
        'version': 1,
        'file_url': result.file_url,
        'file_size': result.file_size,
        'file_type': file.content_type or '',
        'original_filename': file.filename,
        'uploaded_by': user['id'],
        'uploaded_at': ts,
        'note': note or '',
    }
    plan_doc = {
        'id': plan_id,
        'project_id': project_id,
        'discipline': discipline,
        'name': (name or '').strip() or file.filename,
        'file_url': result.file_url,
        'original_filename': file.filename,
        'file_size': result.file_size,
        'file_type': file.content_type or '',
        'uploaded_by': user['id'],
        'note': note or '',
        'plan_type': plan_type or 'standard',
        'floor_id': floor_id or None,
        'unit_id': unit_id or None,
        'created_at': ts,
        'versions': [v1_entry],
        'current_version': 1,
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


@router.post("/projects/{project_id}/plans/{plan_id}/seen")
async def mark_plan_seen(
    project_id: str,
    plan_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)

    plan = await db.project_plans.find_one({
        'id': plan_id,
        'project_id': project_id,
        'deletedAt': {'$exists': False},
        'status': {'$ne': 'archived'},
    }, {'_id': 0, 'id': 1})
    if not plan:
        return {'success': False}

    ts = datetime.now(timezone.utc).isoformat()
    await db.plan_read_receipts.update_one(
        {'plan_id': plan_id, 'user_id': user['id']},
        {
            '$set': {'last_seen_at': ts, 'project_id': project_id},
            '$setOnInsert': {
                'id': str(uuid.uuid4()),
                'first_seen_at': ts,
                'source': 'view',
            },
        },
        upsert=True,
    )
    return {'success': True}


@router.get("/projects/{project_id}/plans/{plan_id}/seen")
async def get_plan_seen_status(
    project_id: str,
    plan_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)

    plan = await db.project_plans.find_one({
        'id': plan_id,
        'project_id': project_id,
        'deletedAt': {'$exists': False},
        'status': {'$ne': 'archived'},
    }, {'_id': 0, 'id': 1})
    if not plan:
        raise HTTPException(status_code=404, detail='תוכנית פעילה לא נמצאה')

    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none') if requester_membership else 'none'
    if requester_role not in MANAGEMENT_ROLES and user.get('role') != 'super_admin':
        raise HTTPException(status_code=403, detail='אין הרשאה לצפות בסטטוס צפייה')

    memberships = await db.project_memberships.find(
        {'project_id': project_id, 'role': {'$in': list(TRACKABLE_ROLES)}},
        {'_id': 0, 'user_id': 1},
    ).to_list(500)
    member_user_ids = [m['user_id'] for m in memberships]

    receipts = await db.plan_read_receipts.find(
        {'plan_id': plan_id, 'user_id': {'$in': member_user_ids}},
        {'_id': 0},
    ).to_list(500)
    seen_user_ids = {r['user_id'] for r in receipts}
    receipt_map = {r['user_id']: r for r in receipts}

    users = await db.users.find(
        {'id': {'$in': member_user_ids}},
        {'_id': 0, 'id': 1, 'name': 1},
    ).to_list(500)
    user_map = {u['id']: u.get('name', '') for u in users}

    seen = []
    unseen = []
    for uid in member_user_ids:
        name = user_map.get(uid, '')
        if uid in seen_user_ids:
            r = receipt_map[uid]
            seen.append({
                'user_id': uid,
                'name': name,
                'first_seen_at': r.get('first_seen_at', ''),
                'last_seen_at': r.get('last_seen_at', ''),
            })
        else:
            unseen.append({'user_id': uid, 'name': name})

    return {
        'plan_id': plan_id,
        'seen_count': len(seen),
        'total_members': len(member_user_ids),
        'seen': seen,
        'unseen': unseen,
    }


@router.post("/projects/{project_id}/plans/{plan_id}/versions")
async def upload_plan_version(
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
        raise HTTPException(status_code=403, detail='אין לך הרשאה להעלות גרסאות')

    plan = await db.project_plans.find_one({
        'id': plan_id,
        'project_id': project_id,
        'deletedAt': {'$exists': False},
        'status': {'$ne': 'archived'},
    })
    if not plan:
        raise HTTPException(status_code=404, detail='תוכנית פעילה לא נמצאה')

    if note and len(note) > 200:
        raise HTTPException(status_code=422, detail='הערה ארוכה מדי (מקסימום 200 תווים)')

    file_bytes = await file.read()
    file_size_check = len(file_bytes)
    if file_size_check > 50 * 1024 * 1024:
        raise HTTPException(status_code=422, detail='קובץ גדול מדי (מקסימום 50MB)')
    await file.seek(0)

    from services.storage_service import StorageService
    storage = StorageService()
    result = await storage.upload_file_with_details(file, f"project_plan_{project_id}_{plan.get('discipline', 'general')}")

    existing_versions = plan.get('versions', [])
    if existing_versions:
        max_ver = max(v.get('version', 1) for v in existing_versions)
    else:
        max_ver = 1

    new_version_num = max_ver + 1
    ts = datetime.now(timezone.utc).isoformat()

    new_version_entry = {
        'version': new_version_num,
        'file_url': result.file_url,
        'file_size': result.file_size,
        'file_type': file.content_type or '',
        'original_filename': file.filename,
        'uploaded_by': user['id'],
        'uploaded_at': ts,
        'note': (note or '').strip(),
    }

    await db.project_plans.update_one({'id': plan_id}, {
        '$push': {'versions': new_version_entry},
        '$set': {
            'file_url': result.file_url,
            'file_size': result.file_size,
            'file_type': file.content_type or '',
            'original_filename': file.filename,
            'current_version': new_version_num,
            'updated_at': ts,
        },
    })

    await _audit('project_plan', plan_id, 'version_upload', user['id'], {
        'project_id': project_id,
        'version': new_version_num,
        'filename': file.filename,
    })

    updated = await db.project_plans.find_one({'id': plan_id}, {'_id': 0})
    from services.object_storage import resolve_urls_in_doc
    return resolve_urls_in_doc(dict(updated))


@router.get("/projects/{project_id}/plans/{plan_id}/versions")
async def get_plan_versions(
    project_id: str,
    plan_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)

    plan = await db.project_plans.find_one({
        'id': plan_id,
        'project_id': project_id,
        'deletedAt': {'$exists': False},
    }, {'_id': 0})
    if not plan:
        raise HTTPException(status_code=404, detail='תוכנית לא נמצאה')

    from services.object_storage import resolve_urls_in_doc

    versions = plan.get('versions', [])
    if not versions:
        versions = [{
            'version': 1,
            'file_url': plan.get('file_url', ''),
            'file_size': plan.get('file_size', 0),
            'file_type': plan.get('file_type', ''),
            'original_filename': plan.get('original_filename', ''),
            'uploaded_by': plan.get('uploaded_by', ''),
            'uploaded_at': plan.get('created_at', ''),
            'note': plan.get('note', ''),
        }]

    versions_sorted = sorted(versions, key=lambda v: v.get('version', 1), reverse=True)

    for v in versions_sorted:
        uploader = await db.users.find_one({'id': v.get('uploaded_by')}, {'_id': 0, 'name': 1})
        v['uploaded_by_name'] = uploader.get('name', '') if uploader else ''
        resolve_urls_in_doc(v)

    return {
        'plan_id': plan_id,
        'current_version': plan.get('current_version', 1),
        'versions': versions_sorted,
    }


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


@router.patch("/projects/{project_id}/plans/{plan_id}")
async def update_project_plan(
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
        raise HTTPException(status_code=403, detail='אין לך הרשאה לערוך תוכניות')

    plan = await db.project_plans.find_one({
        'id': plan_id,
        'project_id': project_id,
        'deletedAt': {'$exists': False},
    })
    if not plan:
        raise HTTPException(status_code=404, detail='תוכנית לא נמצאה')

    allowed_fields = {'name', 'discipline', 'floor_id', 'unit_id', 'plan_type', 'note'}
    updates = {}
    for field in allowed_fields:
        if field in body:
            val = body[field]
            if field == 'plan_type' and val not in ('standard', 'tenant_changes'):
                raise HTTPException(status_code=422, detail='סוג תוכנית לא תקין')
            if field == 'discipline' and val:
                custom_disciplines = await db.project_disciplines.find(
                    {'project_id': project_id}, {'_id': 0, 'key': 1}
                ).to_list(100)
                custom_keys = {d['key'] for d in custom_disciplines}
                all_valid = set(PLAN_DISCIPLINES) | custom_keys
                if val not in all_valid:
                    raise HTTPException(status_code=422, detail=f'תחום לא תקין')
            if field == 'note' and val and len(val) > 200:
                raise HTTPException(status_code=422, detail='הערה ארוכה מדי (מקסימום 200 תווים)')
            updates[field] = val

    if not updates:
        raise HTTPException(status_code=422, detail='לא סופקו שדות לעדכון')

    updates['updated_at'] = datetime.now(timezone.utc).isoformat()
    await db.project_plans.update_one({'id': plan_id}, {'$set': updates})

    await _audit('project_plan', plan_id, 'project_plan_updated', user['id'], {
        'project_id': project_id,
        'updated_fields': list(updates.keys()),
    })

    updated = await db.project_plans.find_one({'id': plan_id}, {'_id': 0})
    from services.object_storage import resolve_urls_in_doc
    return resolve_urls_in_doc(dict(updated))


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
