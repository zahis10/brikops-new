from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Request
from typing import Optional, List
from datetime import datetime
import uuid

from contractor_ops.router import (
    get_db, get_current_user, require_roles,
    _check_project_access, _get_project_membership, _get_project_role,
    _audit, _now, _is_super_admin,
    get_notification_engine, _get_task_link,
    _get_contractor_trade_key, _trades_match,
    MANAGEMENT_ROLES, logger,
    PRIORITY_SORT_MAP, _priority_sort_key,
)
from contractor_ops.msg_logger import mask_phone
from contractor_ops.schemas import (
    Task, TaskCreate, TaskUpdate, TaskAssign, TaskStatusChange,
    TaskUpdateCreate, TaskUpdateResponse,
    TaskStatus, VALID_TRANSITIONS, Priority, Category,
    ManagerDecisionRequest,
)
from contractor_ops.bucket_utils import compute_task_bucket, BUCKET_LABELS, CATEGORY_TO_BUCKET, TRADE_MAP
from contractor_ops.task_image_guard import require_task_image, NO_IMAGE_ERROR_CODE, NO_IMAGE_MESSAGE

router = APIRouter(prefix="/api")


@router.post("/tasks", response_model=Task)
async def create_task(task: TaskCreate, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    pid = (task.project_id or '').strip()
    if not pid:
        raise HTTPException(status_code=400, detail={'error_code': 'INVALID_PROJECT_ID', 'message': 'project_id is required'})
    task.project_id = pid
    await _check_project_access(user, pid)
    project = await db.projects.find_one({'id': pid}, {'_id': 0})
    if not project:
        raise HTTPException(status_code=400, detail={'error_code': 'PROJECT_NOT_FOUND', 'message': 'Project not found'})
    project_status = project.get('status', 'active')
    if project_status in ('draft', 'payment_pending', 'suspended'):
        raise HTTPException(status_code=403, detail=f'Project is {project_status}. Cannot create tasks.')
    if task.building_id:
        building_doc = await db.buildings.find_one({'id': task.building_id, 'project_id': task.project_id, 'archived': {'$ne': True}}, {'_id': 0})
        if not building_doc:
            raise HTTPException(status_code=404, detail='Building not found in this project')
    if task.floor_id:
        floor_doc = await db.floors.find_one({'id': task.floor_id, 'building_id': task.building_id, 'archived': {'$ne': True}}, {'_id': 0})
        if not floor_doc:
            raise HTTPException(status_code=404, detail='Floor not found in this building')
    if task.unit_id:
        unit_doc = await db.units.find_one({'id': task.unit_id, 'floor_id': task.floor_id, 'archived': {'$ne': True}}, {'_id': 0})
        if not unit_doc:
            raise HTTPException(status_code=404, detail='Unit not found on this floor')
    task_id = str(uuid.uuid4())
    ts = _now()
    if task.assignee_id:
        raise HTTPException(
            status_code=400,
            detail={'error_code': NO_IMAGE_ERROR_CODE, 'message': NO_IMAGE_MESSAGE},
        )
    initial_status = 'open'
    from pymongo import ReturnDocument
    counter_doc = await db.counters.find_one_and_update(
        {'_id': f'task_seq:{task.project_id}'},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    display_number = counter_doc['seq']
    doc = {
        'id': task_id, 'project_id': task.project_id, 'building_id': task.building_id,
        'floor_id': task.floor_id, 'unit_id': task.unit_id,
        'title': task.title, 'description': task.description,
        'category': task.category.value if task.category else 'general',
        'priority': task.priority.value if task.priority else 'medium',
        'status': initial_status, 'company_id': task.company_id,
        'assignee_id': task.assignee_id, 'due_date': task.due_date,
        'created_by': user['id'], 'created_at': ts, 'updated_at': ts,
        'short_ref': task_id[:8],
        'display_number': display_number,
        'attachments_count': 0, 'comments_count': 0,
    }
    await db.tasks.insert_one(doc)
    await db.task_status_history.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id,
        'old_status': None, 'new_status': initial_status,
        'changed_by': user['id'], 'note': 'Task created', 'created_at': ts,
    })
    await _audit('task', task_id, 'create', user['id'], {'title': task.title, 'project_id': task.project_id})

    notification_status = None
    engine = get_notification_engine()
    if engine and task.assignee_id:
        try:
            task_link = _get_task_link(task_id)
            job = await engine.enqueue(task_id, 'task_created', user['id'], task_link=task_link)
            if job and job.get('status') == 'queued':
                result = await engine.process_job(job)
                notification_status = {
                    'sent': True,
                    'channel': result.get('channel', 'unknown'),
                    'job_id': result.get('job_id', job.get('id', '')),
                    'provider_message_id': result.get('provider_message_id', ''),
                }
            elif job:
                notification_status = {'sent': False, 'reason': 'duplicate', 'job_id': job.get('id', '')}
        except Exception as e:
            logger.warning(f"[NOTIFY] Auto-enqueue failed for task_created: {e}")
            notification_status = {'sent': False, 'reason': str(e)[:200]}

    task_result = Task(**{k: v for k, v in doc.items() if k != '_id'}).dict()
    if notification_status:
        task_result['notification_status'] = notification_status
    return task_result


async def _build_bucket_maps(db, project_id=None):
    membership_trade_map = {}
    if project_id:
        memberships = await db.project_memberships.find(
            {'project_id': project_id, 'role': 'contractor', 'contractor_trade_key': {'$exists': True, '$ne': None}},
            {'_id': 0, 'user_id': 1, 'contractor_trade_key': 1}
        ).to_list(10000)
        for m in memberships:
            membership_trade_map[m['user_id']] = m['contractor_trade_key']

    contractor_map = {}
    users = await db.users.find(
        {'role': 'contractor'},
        {'_id': 0, 'id': 1, 'specialties': 1}
    ).to_list(10000)
    for u in users:
        specs = u.get('specialties') or []
        trade = next((s for s in specs if s != 'general'), specs[0] if specs else None)
        if trade:
            contractor_map[u['id']] = trade

    company_map = {}
    companies = await db.companies.find({}, {'_id': 0, 'id': 1, 'trade': 1}).to_list(10000)
    for c in companies:
        if c.get('trade'):
            company_map[c['id']] = c['trade']

    return contractor_map, company_map, membership_trade_map


@router.get("/tasks", response_model=List[Task])
async def list_tasks(
    project_id: Optional[str] = Query(None),
    building_id: Optional[str] = Query(None),
    floor_id: Optional[str] = Query(None),
    unit_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    status_in: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    unassigned: Optional[bool] = Query(None),
    bucket_key: Optional[str] = Query(None),
    overdue: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    query = {}
    if project_id:
        query['project_id'] = project_id
    if building_id:
        query['building_id'] = building_id
    if floor_id:
        query['floor_id'] = floor_id
    if unit_id:
        query['unit_id'] = unit_id
    if status:
        query['status'] = status
    elif status_in:
        statuses = [s.strip() for s in status_in.split(',') if s.strip()]
        if len(statuses) == 1:
            query['status'] = statuses[0]
        elif statuses:
            query['status'] = {'$in': statuses}
    if unassigned:
        query['$or'] = [{'assignee_id': None}, {'assignee_id': {'$exists': False}}, {'assignee_id': ''}]
    elif assignee_id:
        if assignee_id == 'me':
            query['assignee_id'] = user['id']
        else:
            query['assignee_id'] = assignee_id
    if company_id:
        query['company_id'] = company_id
    if overdue:
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        query['due_date'] = {'$lt': now_iso, '$exists': True, '$ne': None}
        if 'status' not in query:
            query['status'] = {'$nin': ['closed']}
    if q:
        import re as _re_mod
        q_escaped = _re_mod.escape(q)
        text_or = [
            {'title': {'$regex': q_escaped, '$options': 'i'}},
            {'description': {'$regex': q_escaped, '$options': 'i'}},
        ]
        if '$or' in query:
            existing_or = query.pop('$or')
            query.setdefault('$and', []).extend([{'$or': existing_or}, {'$or': text_or}])
        else:
            query['$or'] = text_or
    is_contractor = user['role'] == 'contractor'
    if not is_contractor and project_id:
        proj_role = await _get_project_role(user, project_id)
        if proj_role == 'contractor':
            is_contractor = True
    if is_contractor:
        query['assignee_id'] = user['id']

    tasks = await db.tasks.find(query, {'_id': 0}).sort('created_at', -1).to_list(10000)

    if bucket_key:
        contractor_map, company_map, membership_trade_map = await _build_bucket_maps(db, project_id)
        tasks = [t for t in tasks if compute_task_bucket(t, contractor_map, company_map, membership_trade_map)['bucket_key'] == bucket_key]

    tasks = sorted(tasks, key=_priority_sort_key)

    from services.object_storage import resolve_urls_in_doc
    result = []
    for t in tasks:
        td = Task(**t).dict()
        resolve_urls_in_doc(td)
        result.append(td)
    return result


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        logger.info(f"[GET_TASK] 404 task_not_found task_id={task_id} user_id={user['id']}")
        raise HTTPException(status_code=404, detail='הליקוי לא נמצא')
    membership = await _get_project_membership(user, task['project_id'])
    is_assignee = task.get('assignee_id') == user['id']
    is_contractor = membership['role'] == 'contractor' or user['role'] == 'contractor'
    logger.info(f"[GET_TASK] task_id={task_id} user_id={user['id']} membership_role={membership['role']} user_role={user.get('role')} is_contractor={is_contractor} is_assignee={is_assignee} assignee_id={task.get('assignee_id')}")
    if is_contractor and not is_assignee:
        logger.info(f"[GET_TASK] 404 contractor_not_assignee task_id={task_id} user_id={user['id']}")
        raise HTTPException(status_code=404, detail='הליקוי לא נמצא')
    if membership['role'] == 'none' and not is_assignee:
        logger.info(f"[GET_TASK] 403 no_membership_not_assignee task_id={task_id} user_id={user['id']}")
        raise HTTPException(status_code=403, detail='No access to this task')
    task_data = Task(**task).dict()
    from services.object_storage import resolve_urls_in_doc
    resolve_urls_in_doc(task_data)
    task_data['user_project_role'] = membership['role'] if membership['role'] != 'none' else ('contractor' if is_assignee else 'none')
    task_data['user_project_sub_role'] = membership.get('sub_role')
    
    # Add location names
    proj = await db.projects.find_one({'id': task['project_id']}, {'_id': 0, 'name': 1})
    task_data['project_name'] = proj['name'] if proj else ''
    
    if task.get('building_id'):
        bld = await db.buildings.find_one({'id': task['building_id']}, {'_id': 0, 'name': 1})
        task_data['building_name'] = bld['name'] if bld else ''
    
    if task.get('floor_id'):
        fl = await db.floors.find_one({'id': task['floor_id']}, {'_id': 0, 'name': 1, 'number': 1})
        task_data['floor_name'] = fl.get('name') or str(fl.get('number', '')) if fl else ''
    
    if task.get('unit_id'):
        un = await db.units.find_one({'id': task['unit_id']}, {'_id': 0})
        task_data['unit_name'] = (un.get('display_label') or un.get('name') or un.get('unit_no') or str(un.get('number', ''))) if un else ''

    if task.get('assignee_id'):
        assignee_mem = await db.project_memberships.find_one(
            {'project_id': task['project_id'], 'user_id': task['assignee_id']},
            {'_id': 0, 'user_name': 1, 'company_id': 1}
        )
        if assignee_mem:
            a_name = assignee_mem.get('user_name', '')
            if not a_name:
                a_user = await db.users.find_one({'id': task['assignee_id']}, {'_id': 0, 'name': 1})
                a_name = a_user.get('name', '') if a_user else ''
            task_data['assignee_name'] = a_name
            a_company_id = assignee_mem.get('company_id') or task.get('company_id')
            if a_company_id:
                comp = await db.project_companies.find_one({'id': a_company_id, 'deletedAt': {'$exists': False}}, {'_id': 0, 'name': 1})
                if not comp:
                    comp = await db.companies.find_one({'id': a_company_id}, {'_id': 0, 'name': 1})
                task_data['assignee_company_name'] = comp.get('name', '') if comp else ''

    return task_data


@router.patch("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, update: TaskUpdate, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    project_role = await _get_project_role(user, task['project_id'])
    if project_role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail='Only management can update tasks')
    update_data = {k: v for k, v in update.dict(exclude_unset=True).items() if v is not None}
    if 'priority' in update_data and hasattr(update_data['priority'], 'value'):
        update_data['priority'] = update_data['priority'].value
    if 'category' in update_data and hasattr(update_data['category'], 'value'):
        update_data['category'] = update_data['category'].value
    update_data['updated_at'] = _now()
    await db.tasks.update_one({'id': task_id}, {'$set': update_data})
    await _audit('task', task_id, 'update', user['id'], update_data)
    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    return Task(**updated)


@router.patch("/tasks/{task_id}/assign")
async def assign_task(task_id: str, assignment: TaskAssign, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    project_role = await _get_project_role(user, task['project_id'])
    if project_role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail='Only management can assign tasks')

    assignee = await db.users.find_one({'id': assignment.assignee_id}, {'_id': 0})
    if not assignee:
        raise HTTPException(status_code=404, detail='Assignee not found')

    assignee_membership = await db.project_memberships.find_one({
        'project_id': task['project_id'], 'user_id': assignment.assignee_id
    })
    if not assignee_membership:
        raise HTTPException(status_code=404, detail='Assignee is not a member of this project')

    assignee_trade_key = assignee_membership.get('contractor_trade_key')

    if assignee_membership.get('role') == 'contractor':
        if not assignee_trade_key:
            raise HTTPException(status_code=409, detail={
                'code': 'CONTRACTOR_NO_TRADE',
                'message': 'חסר תחום מקצועי לקבלן. יש לשייך תחום תחילה.',
            })

    await require_task_image(db, task_id)

    if not assignment.company_id:
        raise HTTPException(status_code=400, detail='company_id is required')

    effective_company_id = assignment.company_id
    company = await db.project_companies.find_one({'id': effective_company_id, 'project_id': task['project_id'], 'deletedAt': {'$exists': False}}, {'_id': 0})
    if not company:
        raise HTTPException(status_code=400, detail='company_id חייב להיות חברת פרויקט תקפה')
    category_synced = False
    task_category = task.get('category')
    if assignee_trade_key and not _trades_match(task_category, assignee_trade_key):
        if not assignment.force_category_change:
            task_cat_label = TRADE_MAP.get(task_category, task_category)
            trade_label = TRADE_MAP.get(assignee_trade_key, assignee_trade_key)
            raise HTTPException(
                status_code=409,
                detail={
                    'error': 'trade_mismatch',
                    'message': f'תחום הליקוי ({task_cat_label}) לא תואם לתחום הקבלן ({trade_label})',
                    'task_category': task_category,
                    'contractor_trade': assignee_trade_key,
                    'task_category_label': task_cat_label,
                    'contractor_trade_label': trade_label,
                }
            )
        category_synced = True

    ts = _now()
    old_status = task['status']
    new_status = 'assigned' if old_status == 'open' else old_status

    update_fields = {
        'company_id': effective_company_id,
        'assignee_id': assignment.assignee_id,
        'status': new_status,
        'updated_at': ts,
    }
    if category_synced:
        update_fields['category'] = assignee_trade_key
    await db.tasks.update_one({'id': task_id}, {'$set': update_fields})

    if old_status != new_status:
        await db.task_status_history.insert_one({
            'id': str(uuid.uuid4()), 'task_id': task_id,
            'old_status': old_status, 'new_status': new_status,
            'changed_by': user['id'], 'note': f'Assigned to {assignee.get("name", "")}',
            'created_at': ts,
        })
        await db.task_updates.insert_one({
            'id': str(uuid.uuid4()), 'task_id': task_id, 'user_id': user['id'],
            'user_name': user.get('name', ''),
            'content': f'שויך ל{assignee.get("name", "")} ({company.get("name", "")})',
            'update_type': 'status_change', 'old_status': old_status,
            'new_status': new_status, 'created_at': ts,
        })

    audit_details = {
        'company_id': effective_company_id,
        'assignee_id': assignment.assignee_id,
        'assignee_name': assignee.get('name', ''),
    }
    if category_synced:
        audit_details['category_changed'] = True
        audit_details['old_category'] = task_category
        audit_details['new_category'] = assignee_trade_key
        audit_details['reason'] = 'PM confirmed category change on cross-trade assignment'
    await _audit('task', task_id, 'assign', user['id'], audit_details)

    notification_status = None
    engine = get_notification_engine()
    if engine:
        try:
            task_link = _get_task_link(task_id)
            job = await engine.enqueue(task_id, 'task_assigned', user['id'], task_link=task_link)
            if not job:
                notification_status = {'sent': False, 'provider_status': 'failed', 'error': 'לא ניתן להוסיף הודעה לתור'}
            elif job.get('status') == 'failed':
                notification_status = {'sent': False, 'provider_status': 'failed', 'error': job.get('error', 'אין מספר וואטסאפ תקין לקבלן')}
            elif job.get('status') == 'queued':
                target_phone = job.get('target_phone', '')
                phone_masked = mask_phone(target_phone) if target_phone else ''
                proc_result = await engine.process_job(job)
                proc_status = proc_result.get('status', 'unknown')
                notification_status = {
                    'sent': proc_status in ('sent', 'delivered'),
                    'provider_status': proc_status,
                    'channel': proc_result.get('channel', 'unknown'),
                    'job_id': proc_result.get('job_id', job.get('id', '')),
                    'provider_message_id': proc_result.get('provider_message_id', ''),
                    'to_phone_masked': phone_masked,
                }
                if proc_result.get('error'):
                    notification_status['error'] = proc_result['error'][:200]
            else:
                notification_status = {'sent': False, 'provider_status': 'duplicate', 'error': 'הודעה כבר נשלחה', 'job_id': job.get('id', '')}
        except Exception as e:
            logger.warning(f"[NOTIFY] Auto-enqueue failed for assign: {e}")
            notification_status = {'sent': False, 'provider_status': 'failed', 'error': str(e)[:200]}

    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    result = Task(**updated).dict()
    if category_synced:
        result['category_synced'] = True
        result['synced_category'] = assignee_trade_key
    if notification_status:
        result['notification_status'] = notification_status
    return result


@router.post("/tasks/{task_id}/status", response_model=Task)
async def change_task_status(task_id: str, change: TaskStatusChange, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')

    current_status = TaskStatus(task['status'])
    target_status = change.status

    project_role = await _get_project_role(user, task['project_id'])
    effective_role = project_role if project_role != 'none' else user['role']

    if effective_role == 'viewer' or user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers cannot change task status')

    if effective_role == 'contractor' or user['role'] == 'contractor':
        if target_status == TaskStatus.closed:
            raise HTTPException(status_code=403, detail='Contractors cannot close tasks. Use /contractor-proof to submit for approval.')
        contractor_allowed = {
            TaskStatus.assigned: [TaskStatus.in_progress],
            TaskStatus.in_progress: [TaskStatus.waiting_verify, TaskStatus.pending_contractor_proof],
        }
        if target_status not in contractor_allowed.get(current_status, []):
            raise HTTPException(status_code=403, detail='Contractors can only move assigned->in_progress or in_progress->pending_contractor_proof')

    allowed = VALID_TRANSITIONS.get(current_status, [])
    if target_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {current_status.value} -> {target_status.value}. Allowed: {[s.value for s in allowed]}"
        )

    ts = _now()
    await db.tasks.update_one({'id': task_id}, {'$set': {'status': target_status.value, 'updated_at': ts}})
    await db.task_status_history.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id,
        'old_status': current_status.value, 'new_status': target_status.value,
        'changed_by': user['id'], 'note': change.note or '', 'created_at': ts,
    })
    await db.task_updates.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id, 'user_id': user['id'],
        'user_name': user.get('name', ''), 'content': change.note or f'Status changed to {target_status.value}',
        'update_type': 'status_change', 'old_status': current_status.value,
        'new_status': target_status.value, 'created_at': ts,
    })
    await _audit('task', task_id, 'status_change', user['id'], {
        'old': current_status.value, 'new': target_status.value, 'note': change.note
    })

    notify_events = {
        'waiting_verify': 'status_waiting_verify',
        'closed': 'status_closed',
    }
    event_type = notify_events.get(target_status.value)
    if event_type:
        engine = get_notification_engine()
        if engine:
            try:
                task_link = _get_task_link(task_id)
                job = await engine.enqueue(task_id, event_type, user['id'], task_link=task_link)
                if job and job.get('status') == 'queued':
                    await engine.process_job(job)
            except Exception as e:
                logger.warning(f"[NOTIFY] Auto-enqueue failed for status_change: {e}")

    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    return Task(**updated)


@router.post("/tasks/{task_id}/reopen", response_model=Task)
async def reopen_task(task_id: str, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    if task['status'] != 'closed':
        raise HTTPException(status_code=400, detail='Only closed tasks can be reopened')
    ts = _now()
    await db.tasks.update_one({'id': task_id}, {'$set': {'status': 'reopened', 'updated_at': ts}})
    await db.task_status_history.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id,
        'old_status': 'closed', 'new_status': 'reopened',
        'changed_by': user['id'], 'note': 'Task reopened', 'created_at': ts,
    })
    await db.task_updates.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id, 'user_id': user['id'],
        'user_name': user.get('name', ''), 'content': 'Task reopened',
        'update_type': 'status_change', 'old_status': 'closed',
        'new_status': 'reopened', 'created_at': ts,
    })
    await _audit('task', task_id, 'reopen', user['id'], {})
    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    return Task(**updated)


@router.post("/tasks/{task_id}/contractor-proof")
async def contractor_proof(
    task_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')

    project_role = await _get_project_role(user, task['project_id'])
    if project_role != 'contractor' and user['role'] != 'contractor':
        raise HTTPException(status_code=403, detail='Only contractors can submit proof')
    if task.get('assignee_id') != user['id']:
        raise HTTPException(status_code=404, detail='הליקוי לא נמצא')
    trade_key = await _get_contractor_trade_key(db, user['id'], task['project_id'])
    if not _trades_match(task.get('category'), trade_key):
        raise HTTPException(status_code=404, detail='הליקוי לא נמצא')

    current_status = task.get('status', '')
    PROOF_ALLOWED_STATUSES = ('open', 'assigned', 'in_progress', 'pending_contractor_proof', 'returned_to_contractor')
    if current_status not in PROOF_ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f'לא ניתן להעלות הוכחה כשסטטוס הליקוי הוא {current_status}')

    form = await request.form()
    all_files = []
    note = None
    for key in form:
        val = form.getlist(key)
        for v in val:
            if hasattr(v, 'filename') and v.filename:
                all_files.append(v)
            elif key == 'note' and isinstance(v, str):
                note = v
    if not all_files:
        raise HTTPException(status_code=400, detail='At least one proof file is required')

    from services.storage_service import StorageService
    storage = StorageService()
    proof_urls = []
    for i, upload_file in enumerate(all_files):
        result = await storage.upload_file_with_details(upload_file, f"proof_{task_id}_{i}")
        proof_urls.append(result.file_url)

    ts = _now()
    old_status = current_status
    new_status = 'pending_manager_approval'
    proof_content = note or 'הוכחת תיקון הועלתה'

    for url in proof_urls:
        update_id = str(uuid.uuid4())
        doc = {
            'id': update_id, 'task_id': task_id, 'user_id': user['id'],
            'user_name': user.get('name', ''), 'content': proof_content,
            'update_type': 'attachment', 'attachment_url': url,
            'old_status': old_status, 'new_status': new_status,
            'created_at': ts,
        }
        await db.task_updates.insert_one(doc)

    await db.tasks.update_one({'id': task_id}, {'$set': {
        'status': new_status, 'updated_at': ts,
        'proof_urls': proof_urls,
    }, '$inc': {'attachments_count': len(proof_urls)}})

    await db.task_status_history.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id,
        'old_status': old_status, 'new_status': new_status,
        'changed_by': user['id'], 'note': proof_content, 'created_at': ts,
    })

    membership = await _get_project_membership(user, task['project_id'])
    await _audit('task', task_id, 'contractor_proof_uploaded', user['id'], {
        'old_status': old_status, 'new_status': new_status,
        'actor_project_role': membership['role'],
        'note': note or '', 'proof_urls': proof_urls,
    })

    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    return {
        'success': True,
        'task': Task(**updated).dict(),
        'proof_url': proof_urls[0] if proof_urls else '',
        'proof_urls': proof_urls,
        'message': 'הוכחת תיקון נשלחה לאישור מנהל',
    }


@router.delete("/tasks/{task_id}/proof/{proof_id}")
async def delete_proof(task_id: str, proof_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='הליקוי לא נמצא')

    project_role = await _get_project_role(user, task['project_id'])
    if not _is_super_admin(user) and project_role != 'project_manager':
        raise HTTPException(status_code=403, detail='רק מנהל פרויקט יכול למחוק הוכחות')

    try:
        body = await request.json()
        reason = body.get('reason', '')
    except Exception:
        reason = ''
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail='חובה לציין סיבה למחיקה')

    proof = await db.task_updates.find_one({'id': proof_id, 'task_id': task_id, 'attachment_url': {'$exists': True}, 'deletedAt': {'$exists': False}}, {'_id': 0})
    if not proof:
        raise HTTPException(status_code=404, detail='הוכחה לא נמצאה')

    await db.task_updates.update_one({'id': proof_id, 'task_id': task_id}, {'$set': {'deletedAt': _now(), 'deletedBy': user['id'], 'deleteReason': reason.strip()}})

    uploader = await db.users.find_one({'id': proof.get('user_id')}, {'_id': 0, 'name': 1})
    await _audit('task', task_id, 'proof_soft_deleted', user['id'], {
        'proof_id': proof_id,
        'deleted_attachment_url': proof.get('attachment_url'),
        'original_uploader_id': proof.get('user_id'),
        'original_uploader_name': uploader.get('name', '') if uploader else '',
        'original_content': proof.get('content', ''),
        'original_created_at': proof.get('created_at', ''),
        'reason': reason.strip(),
    })

    return {'success': True, 'message': 'הוכחה נמחקה בהצלחה'}


@router.post("/tasks/{task_id}/manager-decision")
async def manager_decision(task_id: str, body: ManagerDecisionRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')

    project_role = await _get_project_role(user, task['project_id'])
    if project_role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail='Only management team or PM can approve/reject tasks')

    current_status = task.get('status', '')
    if current_status != 'pending_manager_approval':
        raise HTTPException(status_code=400, detail=f'Task must be in pending_manager_approval status, currently: {current_status}')

    decision = body.decision.lower()
    if decision not in ('approve', 'reject'):
        raise HTTPException(status_code=400, detail='Decision must be approve or reject')

    if decision == 'reject' and not body.reason:
        raise HTTPException(status_code=400, detail='Rejection reason is required')

    ts = _now()
    old_status = current_status

    if decision == 'approve':
        new_status = 'closed'
        audit_action = 'manager_approved_closed'
        update_content = 'תיקון אושר וסגור'
    else:
        new_status = 'returned_to_contractor'
        audit_action = 'manager_rejected_returned'
        update_content = f'הוחזר לקבלן: {body.reason}'

    await db.tasks.update_one({'id': task_id}, {'$set': {
        'status': new_status, 'updated_at': ts,
    }})

    await db.task_status_history.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id,
        'old_status': old_status, 'new_status': new_status,
        'changed_by': user['id'], 'note': update_content, 'created_at': ts,
    })

    await db.task_updates.insert_one({
        'id': str(uuid.uuid4()), 'task_id': task_id, 'user_id': user['id'],
        'user_name': user.get('name', ''), 'content': update_content,
        'update_type': 'status_change', 'old_status': old_status,
        'new_status': new_status, 'created_at': ts,
    })

    membership = await _get_project_membership(user, task['project_id'])
    await _audit('task', task_id, audit_action, user['id'], {
        'old_status': old_status, 'new_status': new_status,
        'decision': decision, 'reason': body.reason or '',
        'actor_project_role': membership['role'],
        'actor_sub_role': membership.get('sub_role'),
    })

    event_type = 'manager_approved' if decision == 'approve' else 'manager_rejected'
    engine = get_notification_engine()
    if engine:
        try:
            task_link = _get_task_link(task_id)
            job = await engine.enqueue(task_id, event_type, user['id'],
                                       custom_message=body.reason or '', task_link=task_link)
            if job and job.get('status') == 'queued':
                await engine.process_job(job)
        except Exception as e:
            logger.warning(f"[NOTIFY] manager-decision notification failed: {e}")

    updated = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    return {
        'success': True,
        'task': Task(**updated).dict(),
        'decision': decision,
        'message': 'תיקון אושר וסגור' if decision == 'approve' else f'תיקון נדחה: {body.reason}',
    }


@router.post("/tasks/{task_id}/updates", response_model=TaskUpdateResponse)
async def add_task_update(task_id: str, update: TaskUpdateCreate, user: dict = Depends(get_current_user)):
    db = get_db()
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers cannot add updates')
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    membership = await _get_project_membership(user, task['project_id'])
    is_assignee = task.get('assignee_id') == user['id']
    if membership['role'] == 'none' and not is_assignee:
        raise HTTPException(status_code=403, detail='No access to this task')
    update_id = str(uuid.uuid4())
    ts = _now()
    doc = {
        'id': update_id, 'task_id': task_id, 'user_id': user['id'],
        'user_name': user.get('name', ''), 'content': update.content,
        'update_type': update.update_type.value if update.update_type else 'comment',
        'attachment_url': update.attachment_url,
        'old_status': update.old_status.value if update.old_status else None,
        'new_status': update.new_status.value if update.new_status else None,
        'created_at': ts,
    }
    await db.task_updates.insert_one(doc)
    await db.tasks.update_one({'id': task_id}, {'$inc': {'comments_count': 1}, '$set': {'updated_at': ts}})
    await _audit('task_update', update_id, 'create', user['id'], {'task_id': task_id})
    return TaskUpdateResponse(**{k: v for k, v in doc.items() if k != '_id'})


@router.get("/tasks/{task_id}/updates", response_model=List[TaskUpdateResponse])
async def list_task_updates(task_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0, 'project_id': 1, 'assignee_id': 1})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    membership = await _get_project_membership(user, task['project_id'])
    is_assignee = task.get('assignee_id') == user['id']
    if membership['role'] == 'none' and not is_assignee:
        raise HTTPException(status_code=403, detail='No access to this task')
    updates = await db.task_updates.find({'task_id': task_id, 'deletedAt': {'$exists': False}}, {'_id': 0}).sort('created_at', -1).to_list(1000)
    from services.object_storage import resolve_urls_in_doc
    for u in updates:
        resolve_urls_in_doc(u)
    return [TaskUpdateResponse(**u) for u in updates]


@router.post("/tasks/{task_id}/attachments")
async def upload_task_attachment(task_id: str, request: Request, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    import time as _time
    t_start = _time.time()
    ct = request.headers.get('content-type', '')
    has_boundary = 'boundary=' in ct
    logger.info(f"[ATTACH:ENTER] task={task_id} filename={file.filename} ct_has_boundary={has_boundary} ct={ct[:120]}")

    db = get_db()
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers cannot upload attachments')
    task = await db.tasks.find_one({'id': task_id}, {'_id': 0})
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    logger.info(f"[ATTACH:TASK_FOUND] task={task_id} elapsed={_time.time()-t_start:.2f}s")

    file_ct = file.content_type or ''
    if not file_ct.startswith('image/'):
        logger.warning(f"[ATTACH:REJECTED] task={task_id} filename={file.filename} content_type={file_ct} reason=not_image")
        raise HTTPException(status_code=400, detail={'error_code': 'INVALID_TASK_IMAGE', 'message': 'ניתן לצרף תמונות בלבד'})

    raw = await file.read()
    if len(raw) == 0:
        logger.warning(f"[ATTACH:REJECTED] task={task_id} filename={file.filename} reason=empty_file")
        raise HTTPException(status_code=400, detail={'error_code': 'INVALID_TASK_IMAGE', 'message': 'ניתן לצרף תמונות בלבד'})

    from PIL import Image as _PILImage
    import io as _io
    try:
        img = _PILImage.open(_io.BytesIO(raw))
        img.verify()
    except Exception as pil_err:
        logger.warning(f"[ATTACH:REJECTED] task={task_id} filename={file.filename} reason=pillow_decode_failed error={pil_err}")
        raise HTTPException(status_code=400, detail={'error_code': 'INVALID_TASK_IMAGE', 'message': 'ניתן לצרף תמונות בלבד'})

    await file.seek(0)
    logger.info(f"[ATTACH:VALIDATED] task={task_id} filename={file.filename} size={len(raw)} content_type={file_ct}")

    from services.storage_service import StorageService
    storage = StorageService()
    result = await storage.upload_file_with_details(file, f"task_{task_id}")
    logger.info(f"[ATTACH:STORED] task={task_id} file_url={result.file_url} elapsed={_time.time()-t_start:.2f}s")

    ts = _now()
    update_id = str(uuid.uuid4())
    doc = {
        'id': update_id, 'task_id': task_id, 'user_id': user['id'],
        'user_name': user.get('name', ''), 'content': f'Attachment: {file.filename}',
        'update_type': 'attachment', 'attachment_url': result.file_url,
        'content_type': file.content_type or '', 'file_name': file.filename or '',
        'created_at': ts,
    }
    await db.task_updates.insert_one(doc)
    await db.tasks.update_one({'id': task_id}, {
        '$inc': {'attachments_count': 1},
        '$set': {'updated_at': ts},
    })
    await _audit('task_attachment', update_id, 'upload', user['id'], {
        'task_id': task_id, 'filename': file.filename, 'file_url': result.file_url,
    })
    logger.info(f"[ATTACH:DB_DONE] task={task_id} elapsed={_time.time()-t_start:.2f}s")

    existing_count = await db.task_updates.count_documents({
        'task_id': task_id, 'update_type': 'attachment',
    })
    if existing_count == 1:
        engine = get_notification_engine()
        if engine:
            try:
                task_link = _get_task_link(task_id)
                img_result = await engine.attach_image_to_notification(
                    task_id=task_id, attachment_id=update_id,
                    image_url=result.file_url, actor_id=user['id'],
                    task_link=task_link,
                )
                if img_result:
                    if img_result.get('status') == 'queued' and img_result.get('event_type') == 'media_followup':
                        await engine.process_job(img_result)
            except Exception as e:
                logger.warning(f"[NOTIFY-IMG] attach_image_to_notification failed: {e}")
    logger.info(f"[ATTACH:COMPLETE] task={task_id} update_id={update_id} total_elapsed={_time.time()-t_start:.2f}s")

    from services.object_storage import resolve_url
    return {'id': update_id, 'file_url': resolve_url(result.file_url), 'thumbnail_url': resolve_url(result.thumbnail_url), 'filename': file.filename}


@router.get("/updates/feed", response_model=List[TaskUpdateResponse])
async def updates_feed(
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    user_project_ids = await db.project_memberships.distinct(
        'project_id', {'user_id': user['id']}
    )
    if not user_project_ids:
        return []
    if project_id:
        if project_id not in user_project_ids:
            raise HTTPException(status_code=403, detail='No access to this project')
        task_ids = await db.tasks.distinct('id', {'project_id': project_id})
    else:
        task_ids = await db.tasks.distinct('id', {'project_id': {'$in': user_project_ids}})
    if not task_ids:
        return []
    query = {'task_id': {'$in': task_ids}}
    updates = await db.task_updates.find(query, {'_id': 0}).sort('created_at', -1).to_list(limit)
    from services.object_storage import resolve_urls_in_doc
    for u in updates:
        resolve_urls_in_doc(u)
    return [TaskUpdateResponse(**u) for u in updates]
