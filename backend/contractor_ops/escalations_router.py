import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pymongo.errors import DuplicateKeyError

from contractor_ops.escalations import (
    URGENCIES,
    assigned_body,
    build_spare_context,
    can_escalate,
    escalation_body,
    note_body,
    resolved_body,
)
from contractor_ops.notification_helpers import create_defect_notification
from contractor_ops.router import (
    _audit,
    _get_project_membership,
    _get_project_role,
    get_current_user,
    get_db,
)
from contractor_ops.spare_tiles import compute_spare_status, default_spare_settings


router = APIRouter(prefix='/api')
PM_ROLES = ('project_manager', 'owner')
TEAM_ROLES = PM_ROLES + ('management_team',)


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _project_or_404(db, project_id):
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    if not project:
        raise HTTPException(status_code=404, detail='הפרויקט לא נמצא')
    return project


async def _role_or_403(user, project_id):
    role = await _get_project_role(user, project_id)
    if role not in TEAM_ROLES:
        raise HTTPException(status_code=403, detail='אין הרשאה להקפצות בפרויקט זה')
    membership = await _get_project_membership(user, project_id)
    return role, membership.get('sub_role')


async def _pm_ids(db, project_id):
    rows = await db.project_memberships.find(
        {'project_id': project_id, 'role': 'project_manager'},
        {'_id': 0, 'user_id': 1},
    ).to_list(1000)
    return [row['user_id'] for row in rows if row.get('user_id')]


async def _recipients(esc):
    assigned = esc.get('assigned_to')
    if assigned and assigned.get('id'):
        return [assigned['id']]
    return await _pm_ids(get_db(), esc['project_id'])


def _serialize(doc):
    return {key: value for key, value in doc.items() if key != '_id'}


async def _notify(db, recipients, ntype, action, esc, actor, body):
    return await create_defect_notification(
        db,
        recipients,
        notification_type=ntype,
        action=action,
        task_id=esc['id'],
        task_title=esc['text'][:80],
        project_id=esc['project_id'],
        actor_id=actor['id'],
        actor_name=actor.get('name', ''),
        body=body,
        extra={
            'escalation_id': esc['id'],
            'unit_id': esc['unit_id'],
            'urgency': esc['urgency'],
        },
    )


async def _unit_for_project(db, unit_id, project_id):
    unit = await db.units.find_one(
        {'id': unit_id, 'project_id': project_id},
        {'_id': 0},
    )
    if unit:
        return unit
    candidate = await db.units.find_one({'id': unit_id}, {'_id': 0})
    if not candidate or candidate.get('project_id'):
        return None
    building = await db.buildings.find_one(
        {'id': candidate.get('building_id'), 'project_id': project_id},
        {'_id': 0},
    )
    return candidate if building else None


def _visibility(role, user_id):
    if role == 'management_team':
        return {
            '$or': [
                {'requested_by.id': user_id},
                {'assigned_to.id': user_id},
            ],
        }
    return {}


def _open_unit_escalation(unit_id):
    return {'unit_id': unit_id, 'type': 'spare_tiles', 'status': 'open'}


async def _append_open_note(db, escalation, actor, text, user_id):
    now = _now()
    note = {'by': actor, 'at': now, 'text': text}
    result = await db.field_escalations.update_one(
        {'id': escalation['id'], 'status': 'open'},
        {'$push': {'notes': note}, '$set': {'updated_at': now}},
    )
    modified = getattr(result, 'modified_count', None)
    # Lightweight test doubles do not provide a Mongo result; real Mongo
    # always returns an integer here.
    if isinstance(modified, int) and modified != 1:
        raise HTTPException(status_code=409, detail='ההקפצה כבר טופלה')
    escalation.setdefault('notes', []).append(note)
    escalation['updated_at'] = now
    await _audit('field_escalation', escalation['id'], 'note', user_id, {'text': text})
    await _notify(
        db,
        await _recipients(escalation),
        'field_escalation',
        'escalation_note',
        escalation,
        actor,
        note_body(escalation, actor['name'], text),
    )
    return escalation, True


@router.post('/projects/{project_id}/escalations')
async def create_escalation(
    project_id: str,
    body: dict,
    user: dict = Depends(get_current_user),
    response: Response = None,
):
    db = get_db()
    project = await _project_or_404(db, project_id)
    role, sub_role = await _role_or_403(user, project_id)
    unit_id = body.get('unit_id') if isinstance(body, dict) else None
    unit = await _unit_for_project(db, unit_id, project_id)
    if not unit:
        raise HTTPException(status_code=404, detail='הדירה לא נמצאה')
    spare_status = compute_spare_status(
        unit,
        project.get('spare_settings') or default_spare_settings(),
    )
    if not can_escalate(spare_status):
        raise HTTPException(
            status_code=422,
            detail='אין מה להקפיץ — אין חוסר או מצב גבולי בדירה',
        )
    urgency = body.get('urgency', 'normal')
    if urgency not in URGENCIES:
        raise HTTPException(status_code=422, detail='דחיפות לא חוקית')
    text = str(body.get('text') or '').strip()
    if not 1 <= len(text) <= 500:
        raise HTTPException(status_code=422, detail='יש לכתוב הודעה (עד 500 תווים)')

    now = _now()
    actor = {'id': user['id'], 'name': user.get('name', '')}
    existing = await db.field_escalations.find_one(
        _open_unit_escalation(unit_id)
    )
    if existing:
        existing, _ = await _append_open_note(db, existing, actor, text, user['id'])
        return {'escalation': _serialize(existing), 'appended_note': True}

    building = await db.buildings.find_one({'id': unit.get('building_id')}, {'_id': 0})
    floor = await db.floors.find_one({'id': unit.get('floor_id')}, {'_id': 0})
    escalation = {
        'id': str(uuid.uuid4()),
        'project_id': project_id,
        'type': 'spare_tiles',
        'building_id': unit.get('building_id'),
        'floor_id': unit.get('floor_id'),
        'unit_id': unit_id,
        'labels': {
            'building': (building or {}).get('name', ''),
            'floor': (floor or {}).get('name', ''),
            'unit': unit.get('display_label') or unit.get('unit_no', ''),
        },
        'urgency': urgency,
        'text': text,
        'context': build_spare_context(spare_status),
        'requested_by': {
            'id': user['id'],
            'name': user.get('name', ''),
            'role': role,
            'sub_role': sub_role,
        },
        'assigned_to': None,
        'status': 'open',
        'created_at': now,
        'updated_at': now,
        'resolved_by': None,
        'resolved_at': None,
        'resolution_note': None,
        'notes': [],
    }
    try:
        await db.field_escalations.insert_one(escalation)
    except DuplicateKeyError:
        # Open escalations are unit state shared by every authorized team sender.
        winner = await db.field_escalations.find_one(
            _open_unit_escalation(unit_id)
        )
        if not winner:
            raise HTTPException(status_code=409, detail='ההקפצה כבר טופלה')
        winner, appended = await _append_open_note(
            db, winner, actor, text, user['id'],
        )
        return {
            'escalation': _serialize(winner),
            'appended_note': appended,
        }
    await _audit('field_escalation', escalation['id'], 'create', user['id'], {
        'unit_id': unit_id,
        'urgency': urgency,
    })
    await _notify(
        db,
        await _pm_ids(db, project_id),
        'field_escalation',
        'escalate',
        escalation,
        actor,
        escalation_body(escalation),
    )
    if response is not None:
        response.status_code = 201
    return {'escalation': _serialize(escalation), 'appended_note': False}


@router.get('/projects/{project_id}/escalations')
async def list_escalations(
    project_id: str,
    status: str = Query(default='open'),
    user: dict = Depends(get_current_user),
):
    if not isinstance(status, str):
        status = 'open'
    if status not in ('open', 'resolved', 'all'):
        raise HTTPException(status_code=422, detail='סטטוס לא חוקי')
    db = get_db()
    await _project_or_404(db, project_id)
    role, _sub_role = await _role_or_403(user, project_id)
    base = {
        'project_id': project_id,
        'type': 'spare_tiles',
        **_visibility(role, user['id']),
    }
    now = datetime.now(timezone.utc)
    query = dict(base)
    if status == 'open':
        query['status'] = 'open'
    elif status == 'resolved':
        query['status'] = {'$in': ['done', 'dismissed']}
        query['resolved_at'] = {'$gte': (now - timedelta(days=30)).isoformat()}
    items = await db.field_escalations.find(query, {'_id': 0}).to_list(200)
    if status == 'open':
        items.sort(key=lambda item: (
            item.get('urgency') != 'urgent',
            -(datetime.fromisoformat(item['created_at']).timestamp()),
        ))
    elif status == 'resolved':
        items.sort(key=lambda item: item.get('resolved_at', ''), reverse=True)
    else:
        items.sort(key=lambda item: (
            item.get('status') != 'open',
            item.get('urgency') != 'urgent',
            item.get('created_at', ''),
        ))

    open_query = {**base, 'status': 'open'}
    urgent_query = {**open_query, 'urgency': 'urgent'}
    week_query = {
        **base,
        'status': {'$in': ['done', 'dismissed']},
        'resolved_at': {'$gte': (now - timedelta(days=7)).isoformat()},
    }
    open_count = await db.field_escalations.count_documents(open_query)
    urgent_count = await db.field_escalations.count_documents(urgent_query)
    resolved_week_count = await db.field_escalations.count_documents(week_query)
    return {
        'items': [_serialize(item) for item in items],
        'open_count': open_count,
        'urgent_count': urgent_count,
        'resolved_week_count': resolved_week_count,
        'role': role,
        'can_assign': role in PM_ROLES,
    }


@router.patch('/escalations/{escalation_id}')
async def patch_escalation(
    escalation_id: str,
    body: dict,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    esc = await db.field_escalations.find_one({'id': escalation_id})
    if not esc:
        raise HTTPException(status_code=404, detail='ההקפצה לא נמצאה')
    role, _sub_role = await _role_or_403(user, esc['project_id'])
    action = body.get('action') if isinstance(body, dict) else None
    actor = {'id': user['id'], 'name': user.get('name', '')}
    assigned_id = (esc.get('assigned_to') or {}).get('id')
    requester_id = esc.get('requested_by', {}).get('id')
    is_pm = role in PM_ROLES
    now = _now()

    if action in ('done', 'dismiss'):
        if not is_pm and assigned_id != user['id']:
            raise HTTPException(status_code=403, detail='אין הרשאה לטפל בהקפצה זו')
        if esc.get('status') != 'open':
            raise HTTPException(status_code=409, detail='ההקפצה כבר טופלה')
        note = str(body.get('note') or '').strip()
        if len(note) > 300:
            raise HTTPException(status_code=422, detail='הערת טיפול ארוכה מדי (עד 300 תווים)')
        status_value = 'done' if action == 'done' else 'dismissed'
        fields = {
            'status': status_value,
            'resolved_by': actor,
            'resolved_at': now,
            'resolution_note': note or None,
            'updated_at': now,
        }
        update_result = await db.field_escalations.update_one(
            {'id': escalation_id, 'status': 'open'},
            {'$set': fields},
        )
        modified = getattr(update_result, 'modified_count', None)
        if isinstance(modified, int) and modified != 1:
            raise HTTPException(status_code=409, detail='ההקפצה כבר טופלה')
        esc.update(fields)
        audit_action = 'done' if action == 'done' else 'dismissed'
        await _audit('field_escalation', escalation_id, audit_action, user['id'], {
            'resolution_note': note or None,
        })
        await _notify(
            db,
            [requester_id],
            'field_escalation_resolved',
            'escalation_done' if action == 'done' else 'escalation_dismissed',
            esc,
            actor,
            resolved_body(esc),
        )
    elif action == 'note':
        if not (is_pm or assigned_id == user['id'] or requester_id == user['id']):
            raise HTTPException(status_code=403, detail='אין הרשאה להוסיף הערה להקפצה זו')
        note_text = str(body.get('note') or '').strip()
        if not 1 <= len(note_text) <= 500:
            raise HTTPException(status_code=422, detail='יש לכתוב הערה (עד 500 תווים)')
        note = {'by': actor, 'at': now, 'text': note_text}
        await db.field_escalations.update_one(
            {'id': escalation_id},
            {'$push': {'notes': note}, '$set': {'updated_at': now}},
        )
        esc.setdefault('notes', []).append(note)
        esc['updated_at'] = now
        await _audit('field_escalation', escalation_id, 'note', user['id'], {
            'text': note_text,
        })
        recipients = (
            await _recipients(esc)
            if requester_id == user['id']
            else [requester_id]
        )
        await _notify(
            db,
            recipients,
            'field_escalation',
            'escalation_note',
            esc,
            actor,
            note_body(esc, actor['name'], note_text),
        )
    elif action == 'assign':
        if not is_pm:
            raise HTTPException(status_code=403, detail='אין הרשאה להעביר הקפצה זו')
        if esc.get('status') != 'open':
            raise HTTPException(status_code=409, detail='ההקפצה כבר טופלה')
        assignee_id = body.get('assignee_id')
        assigned_to = None
        if assignee_id is not None:
            membership = await db.project_memberships.find_one({
                'project_id': esc['project_id'],
                'user_id': assignee_id,
                'role': {'$in': ['project_manager', 'management_team']},
            })
            if not membership:
                raise HTTPException(
                    status_code=422,
                    detail='המשתמש אינו חבר צוות ניהול בפרויקט',
                )
            assignee = await db.users.find_one({'id': assignee_id}, {'_id': 0, 'name': 1})
            assigned_to = {'id': assignee_id, 'name': (assignee or {}).get('name', '')}
        fields = {'assigned_to': assigned_to, 'updated_at': now}
        await db.field_escalations.update_one({'id': escalation_id}, {'$set': fields})
        esc.update(fields)
        await _audit('field_escalation', escalation_id, 'assign', user['id'], {
            'assigned_to': assigned_to,
        })
        if assigned_to:
            await _notify(
                db,
                [assignee_id],
                'field_escalation',
                'escalation_assigned',
                esc,
                actor,
                assigned_body(esc, actor['name']),
            )
    else:
        raise HTTPException(status_code=422, detail='פעולה לא חוקית')
    return {'escalation': _serialize(esc)}