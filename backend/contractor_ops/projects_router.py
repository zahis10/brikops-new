import re
import uuid
import secrets
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Query, Body, Request
from contractor_ops.router import (
    get_db, get_current_user, require_roles, require_super_admin,
    _check_project_access, _check_project_read_access, _check_structure_admin,
    _get_project_role, _audit, _now, _is_super_admin, _priority_sort_key, logger,
)
from contractor_ops.billing import get_user_org, get_subscription
from contractor_ops.schemas import (
    Project, Building, Floor, Unit, Task,
    BulkFloorRequest, BulkUnitRequest, InsertFloorRequest,
)

router = APIRouter(prefix="/api")


async def _create_or_update_quota_request(
    db,
    project_id: str,
    org_id: str,
    requester_user: dict,
    requested_total_units: int,
    direction: str,
) -> dict:
    now = _now()
    existing = await db.unit_quota_requests.find_one(
        {'project_id': project_id, 'status': 'pending'},
        {'_id': 0}
    )

    if existing:
        if direction == 'increase' and requested_total_units > existing.get('requested_total_units', 0):
            await db.unit_quota_requests.update_one(
                {'id': existing['id']},
                {'$set': {
                    'requested_total_units': requested_total_units,
                    'updated_at': now,
                }}
            )
            existing['requested_total_units'] = requested_total_units
        return existing

    project = await db.projects.find_one(
        {'id': project_id},
        {'_id': 0, 'name': 1, 'total_units': 1}
    )
    request_doc = {
        'id': str(uuid.uuid4()),
        'project_id': project_id,
        'project_name_snapshot': project.get('name', '') if project else '',
        'org_id': org_id,
        'requester_user_id': requester_user['id'],
        'requester_user_name': requester_user.get('full_name', '') or requester_user.get('email', ''),
        'current_total_units': project.get('total_units', 0) if project else 0,
        'requested_total_units': requested_total_units,
        'direction': direction,
        'reason': '',
        'status': 'pending',
        'created_at': now,
        'updated_at': now,
        'resolved_at': None,
        'resolved_by_user_id': None,
        'admin_note': '',
    }
    await db.unit_quota_requests.insert_one(request_doc)
    logger.info(
        "[QUOTA-REQUEST] Created pending request id=%s project=%s requester=%s requested=%s direction=%s",
        request_doc['id'], project_id, requester_user['id'], requested_total_units, direction
    )
    return request_doc


async def _check_unit_quota(db, project_id: str, num_to_add: int, requester_user: dict) -> None:
    project = await db.projects.find_one(
        {'id': project_id},
        {'_id': 0, 'total_units': 1, 'org_id': 1, 'name': 1}
    )
    if not project:
        return
    total_units = project.get('total_units')
    if total_units is None or total_units < 1:
        return

    current_count = await db.units.count_documents({
        'project_id': project_id,
        'archived': {'$ne': True}
    })
    if current_count + num_to_add > total_units:
        requested_total = current_count + num_to_add
        try:
            await _create_or_update_quota_request(
                db,
                project_id=project_id,
                org_id=project.get('org_id', ''),
                requester_user=requester_user,
                requested_total_units=requested_total,
                direction='increase',
            )
        except Exception as e:
            logger.error("[QUOTA-REQUEST] Failed to create request: %s", e)

        raise HTTPException(
            status_code=400,
            detail=f'חרגת מהכמות המוצהרת של הדירות ({total_units}). בקשתך להגדלה נשלחה לאישור — תקבל הודעה כשתאושר.'
        )


def _natural_sort_key(name: str):
    parts = re.split(r'(\d+)', name or '')
    result = []
    for p in parts:
        try:
            result.append((0, int(p)))
        except ValueError:
            result.append((1, p))
    return result


def _is_numeric_unit(unit_no: str) -> bool:
    try:
        int(unit_no)
        return True
    except (ValueError, TypeError):
        return False


def _compute_insert_sort_index(floors: list, insert_after_floor_id, strict: bool = False):
    if not floors:
        return 0
    sorted_floors = sorted(floors, key=lambda f: f.get('sort_index', 0))
    if insert_after_floor_id == '__start__':
        return sorted_floors[0].get('sort_index', 0) - 1
    for i, f in enumerate(sorted_floors):
        if f['id'] == insert_after_floor_id:
            after_si = f.get('sort_index', 0)
            if i + 1 < len(sorted_floors):
                next_si = sorted_floors[i + 1].get('sort_index', 0)
                return (after_si + next_si) // 2
            else:
                return after_si + 1000
    if strict:
        raise HTTPException(status_code=422, detail='insert_after_floor_id not found in building')
    return max(f.get('sort_index', 0) for f in sorted_floors) + 1000


async def _compute_building_resequence(db, building_id: str):
    floors = await db.floors.find({'building_id': building_id}, {'_id': 0}).sort('sort_index', 1).to_list(1000)
    floor_changes = []
    unit_changes = []
    global_counter = 0

    for idx, f in enumerate(floors):
        new_si = (idx + 1) * 1000
        old_si = f.get('sort_index', 0)
        if old_si != new_si:
            floor_changes.append({
                'type': 'floor',
                'id': f['id'],
                'name': f['name'],
                'old_sort_index': old_si,
                'new_sort_index': new_si,
            })
        units = await db.units.find({'floor_id': f['id']}, {'_id': 0}).sort('sort_index', 1).to_list(10000)
        numeric_in_floor = 0
        for uidx, u in enumerate(units):
            if _is_numeric_unit(u['unit_no']):
                global_counter += 1
                numeric_in_floor += 1
                new_unit_no = str(global_counter)
                new_si_u = numeric_in_floor * 10
                if u['unit_no'] != new_unit_no:
                    unit_changes.append({
                        'type': 'unit',
                        'id': u['id'],
                        'floor_id': f['id'],
                        'floor_name': f['name'],
                        'old_unit_no': u['unit_no'],
                        'new_unit_no': new_unit_no,
                        'new_sort_index': new_si_u,
                        'new_display_label': new_unit_no,
                    })
                else:
                    pass
            else:
                pass

    return floor_changes, unit_changes


@router.post("/projects", response_model=Project)
async def create_project(project: Project, user: dict = Depends(require_roles('project_manager'))):
    if project.total_units is None or not isinstance(project.total_units, int) or project.total_units < 1:
        raise HTTPException(status_code=400, detail='חובה להזין את כמות יחידות הדיור בפרויקט (מההיתר)')
    db = get_db()
    if not _is_super_admin(user):
        org = await get_user_org(user['id'])
        if org:
            sub = await get_subscription(org['id'])
            if sub and sub.get('status') == 'trialing':
                existing_count = await db.projects.count_documents({'org_id': org['id']})
                if existing_count >= 1:
                    raise HTTPException(
                        status_code=403,
                        detail='בתקופת הניסיון ניתן ליצור פרויקט אחד בלבד. לפרויקטים נוספים יש לשדרג את המנוי.'
                    )
    existing = await db.projects.find_one({'code': project.code})
    if existing:
        raise HTTPException(status_code=400, detail='Project code already exists')
    project_id = str(uuid.uuid4())
    ts = _now()
    org = await get_user_org(user['id'])
    join_code = None
    for _jc_attempt in range(10):
        candidate = f"BRK-{secrets.randbelow(9000) + 1000}"
        if not await db.projects.find_one({'join_code': candidate}):
            join_code = candidate
            break
    doc = {
        'id': project_id, 'name': project.name, 'code': project.code,
        'description': project.description, 'status': project.status.value if project.status else 'active',
        'client_name': project.client_name, 'start_date': project.start_date,
        'end_date': project.end_date, 'created_by': user['id'],
        'org_id': org['id'] if org else None,
        'join_code': join_code,
        'total_units': project.total_units,
        'created_at': ts, 'updated_at': ts,
    }
    await db.projects.insert_one(doc)
    template_updates = {}
    qc_tpl = await db.qc_templates.find_one(
        {"type": "qc", "is_default": True, "is_active": True},
        sort=[("version", -1)],
    )
    if qc_tpl:
        template_updates["qc_template_version_id"] = qc_tpl["id"]
        template_updates["qc_template_family_id"] = qc_tpl["family_id"]
    ho_tpl = await db.qc_templates.find_one(
        {"type": "handover", "is_default": True, "is_active": True},
        sort=[("version", -1)],
    )
    if ho_tpl:
        template_updates["handover_template_version_id"] = ho_tpl["id"]
        template_updates["handover_template_family_id"] = ho_tpl["family_id"]
    if template_updates:
        await db.projects.update_one({"id": project_id}, {"$set": template_updates})
        doc.update(template_updates)
    await db.project_memberships.update_one(
        {'project_id': project_id, 'user_id': user['id']},
        {'$set': {'id': str(uuid.uuid4()), 'project_id': project_id, 'user_id': user['id'], 'role': 'project_manager', 'created_at': ts}},
        upsert=True
    )
    await _audit('project', project_id, 'create', user['id'], {'name': project.name, 'code': project.code})
    return Project(**{k: v for k, v in doc.items() if k != '_id'})


@router.put("/projects/{project_id}/onboarding-complete")
async def mark_onboarding_complete(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    await _check_project_access(user, project_id)
    await db.projects.update_one(
        {'id': project_id},
        {'$set': {'onboarding_complete': True, 'onboarding_completed_at': _now()}}
    )
    await _audit('project', project_id, 'onboarding_complete', user['id'], {})
    return {'success': True}


@router.post("/projects/{project_id}/assign-pm")
async def assign_pm(project_id: str, body: dict, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    target_user_id = body.get('user_id')
    if not target_user_id:
        raise HTTPException(status_code=400, detail='user_id is required')
    target = await db.users.find_one({'id': target_user_id})
    if not target:
        raise HTTPException(status_code=404, detail='User not found')
    await db.users.update_one(
        {'id': target_user_id},
        {'$set': {'role': 'project_manager', 'project_id': project_id, 'updated_at': _now()}}
    )
    await db.project_memberships.update_one(
        {'project_id': project_id, 'user_id': target_user_id},
        {'$set': {'id': str(uuid.uuid4()), 'project_id': project_id, 'user_id': target_user_id, 'role': 'project_manager', 'created_at': _now()}},
        upsert=True
    )
    await _audit('user', target_user_id, 'assign_pm', user['id'], {'project_id': project_id, 'project_name': project.get('name')})
    return {'success': True, 'message': f'User {target.get("name")} assigned as PM to project {project.get("name")}'}


@router.get("/projects/{project_id}/available-pms")
async def list_available_pms(project_id: str, search: Optional[str] = Query(None), user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    existing_pm_ids = await db.project_memberships.distinct('user_id', {
        'project_id': project_id, 'role': 'project_manager'
    })
    query = {
        'id': {'$nin': existing_pm_ids},
        'user_status': {'$nin': ['rejected', 'suspended', 'pending_pm_approval']},
    }
    users = await db.users.find(query, {'_id': 0, 'password_hash': 0}).to_list(500)
    if search:
        search_lower = search.lower()
        users = [u for u in users if
                 search_lower in (u.get('name', '') or '').lower() or
                 search_lower in (u.get('email', '') or '').lower() or
                 search_lower in (u.get('phone_e164', '') or '').lower() or
                 search_lower in (u.get('phone', '') or '').lower()]
    return users


@router.get("/projects")
async def list_projects(user: dict = Depends(get_current_user)):
    db = get_db()
    if _is_super_admin(user):
        projects = await db.projects.find({}, {'_id': 0}).to_list(1000)
        enriched = []
        for p in projects:
            proj = Project(**p).dict()
            proj['my_role'] = 'project_manager'
            proj['my_sub_role'] = None
            enriched.append(proj)
        return enriched
    else:
        memberships = await db.project_memberships.find({'user_id': user['id']}, {'_id': 0}).to_list(1000)
        membership_map = {m['project_id']: m for m in memberships}
        project_ids = list(membership_map.keys())
        if not project_ids:
            return []
        projects = await db.projects.find({'id': {'$in': project_ids}}, {'_id': 0}).to_list(1000)
        enriched = []
        for p in projects:
            proj = Project(**p).dict()
            mem = membership_map.get(p['id'], {})
            proj['my_role'] = mem.get('role', 'viewer')
            proj['my_sub_role'] = mem.get('sub_role', None)
            if mem.get('role') == 'contractor':
                proj['my_trade_key'] = mem.get('contractor_trade_key')
            if proj.get('my_role') not in ('project_manager', 'owner'):
                proj.pop('join_code', None)
            enriched.append(proj)
        return enriched


@router.get("/projects/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    await _check_project_read_access(user, project_id)
    proj = Project(**project).dict()
    if _is_super_admin(user):
        proj['my_role'] = 'project_manager'
        proj['my_sub_role'] = None
    else:
        membership = await db.project_memberships.find_one(
            {'user_id': user['id'], 'project_id': project_id}, {'_id': 0}
        )
        proj['my_role'] = membership.get('role', 'viewer') if membership else 'viewer'
        proj['my_sub_role'] = membership.get('sub_role', None) if membership else None
        if membership and membership.get('role') == 'contractor':
            proj['my_trade_key'] = membership.get('contractor_trade_key')
        if proj.get('my_role') not in ('project_manager', 'owner'):
            proj.pop('join_code', None)
    return proj


@router.post("/projects/{project_id}/buildings", response_model=Building)
async def create_building(project_id: str, building: Building, user: dict = Depends(get_current_user)):
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    await _check_structure_admin(user, project_id)
    building_id = str(uuid.uuid4())
    doc = {
        'id': building_id, 'project_id': project_id, 'name': building.name,
        'code': building.code, 'floors_count': building.floors_count or 0,
        'created_at': _now(),
    }
    await db.buildings.insert_one(doc)
    await _audit('building', building_id, 'create', user['id'], {'project_id': project_id, 'name': building.name})
    return Building(**{k: v for k, v in doc.items() if k != '_id'})


@router.get("/projects/{project_id}/buildings", response_model=List[Building])
async def list_buildings(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    buildings = await db.buildings.find({'project_id': project_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(1000)
    buildings.sort(key=lambda b: (b.get('sort_index', 0), _natural_sort_key(b.get('name', ''))))
    return [Building(**b) for b in buildings]


@router.post("/buildings/{building_id}/floors", response_model=Floor)
async def create_floor(building_id: str, floor: Floor, user: dict = Depends(get_current_user)):
    db = get_db()
    building = await db.buildings.find_one({'id': building_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not building:
        raise HTTPException(status_code=404, detail='Building not found')
    await _check_structure_admin(user, building['project_id'])

    is_numeric_floor = False
    try:
        floor_num_val = int(floor.name)
        is_numeric_floor = True
    except (ValueError, TypeError):
        floor_num_val = 0

    if is_numeric_floor:
        floor.floor_number = floor_num_val

    existing_floors = await db.floors.find({'building_id': building_id, 'archived': {'$ne': True}}, {'_id': 0}).sort('sort_index', 1).to_list(1000)

    if floor.insert_after_floor_id and existing_floors:
        floor.sort_index = _compute_insert_sort_index(existing_floors, floor.insert_after_floor_id, strict=True)
    elif is_numeric_floor and existing_floors:
        insert_before = None
        for ef in existing_floors:
            ef_num = None
            try:
                ef_num = int(ef.get('name', ''))
            except (ValueError, TypeError):
                try:
                    ef_num = int(ef.get('floor_number', 0))
                except (ValueError, TypeError):
                    pass
            if ef_num is not None and ef_num > floor_num_val:
                insert_before = ef
                break
        if insert_before:
            floor.sort_index = insert_before.get('sort_index', 1000) - 1
        else:
            max_si = max(ef.get('sort_index', 0) for ef in existing_floors)
            floor.sort_index = max_si + 1000
    elif floor.sort_index is None:
        if existing_floors:
            max_si = max(ef.get('sort_index', 0) for ef in existing_floors)
            floor.sort_index = max_si + 1000
        else:
            floor.sort_index = floor.floor_number * 1000

    floor_id = str(uuid.uuid4())
    ts = _now()
    doc = {
        'id': floor_id, 'building_id': building_id, 'project_id': building['project_id'],
        'name': floor.name, 'floor_number': floor.floor_number,
        'sort_index': floor.sort_index,
        'display_label': floor.display_label or floor.name,
        'kind': floor.kind.value if floor.kind else None,
        'created_at': ts,
    }
    await db.floors.insert_one(doc)

    unit_count = floor.unit_count if floor.unit_count and floor.unit_count > 0 else 0
    created_units = []
    if unit_count > 0:
        await _check_unit_quota(db, building['project_id'], unit_count, user)
        all_units = await db.units.find({'building_id': building_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(100000)
        max_numeric = 0
        for u in all_units:
            try:
                n = int(u['unit_no'])
                if n > max_numeric:
                    max_numeric = n
            except (ValueError, TypeError):
                pass
        for i in range(unit_count):
            unit_no = str(max_numeric + i + 1)
            unit_id = str(uuid.uuid4())
            unit_doc = {
                'id': unit_id, 'floor_id': floor_id, 'building_id': building_id,
                'project_id': building['project_id'], 'unit_no': unit_no,
                'unit_type': 'apartment', 'status': 'available',
                'sort_index': (i + 1) * 10,
                'display_label': unit_no,
                'created_at': ts,
            }
            await db.units.insert_one(unit_doc)
            created_units.append(unit_no)

    reseq_floor_changes, reseq_unit_changes = await _compute_building_resequence(db, building_id)
    for c in reseq_floor_changes:
        await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})
    if reseq_unit_changes:
        for c in reseq_unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': f"__tmp_{c['id']}",
                'display_label': f"__tmp_{c['id']}",
            }})
        for c in reseq_unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': c['new_unit_no'],
                'display_label': c['new_display_label'],
                'sort_index': c['new_sort_index'],
            }})

    await _audit('floor', floor_id, 'create', user['id'], {
        'building_id': building_id, 'name': floor.name,
        'sort_index': doc['sort_index'], 'unit_count': unit_count,
        'created_units': created_units,
        'units_renumbered': len(reseq_unit_changes),
    })
    return Floor(**{k: v for k, v in doc.items() if k != '_id'})


@router.get("/buildings/{building_id}/floors", response_model=List[Floor])
async def list_floors(building_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    floors = await db.floors.find({'building_id': building_id, 'archived': {'$ne': True}}, {'_id': 0}).sort('sort_index', 1).to_list(1000)
    return [Floor(**f) for f in floors]


@router.post("/floors/{floor_id}/units")
async def create_unit(floor_id: str, unit: Unit, user: dict = Depends(get_current_user)):
    db = get_db()
    floor = await db.floors.find_one({'id': floor_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not floor:
        raise HTTPException(status_code=404, detail='Floor not found')
    await _check_structure_admin(user, floor['project_id'])
    building_id = floor['building_id']
    project_id = floor['project_id']
    ts = _now()

    unit_count = unit.unit_count if unit.unit_count and unit.unit_count > 0 else 0

    if unit_count > 0:
        await _check_unit_quota(db, project_id, unit_count, user)
        all_units = await db.units.find({'building_id': building_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(100000)
        max_numeric = 0
        for u in all_units:
            try:
                n = int(u['unit_no'])
                if n > max_numeric:
                    max_numeric = n
            except (ValueError, TypeError):
                pass

        existing_floor_units = await db.units.find({'floor_id': floor_id, 'archived': {'$ne': True}}, {'_id': 0}).sort('sort_index', -1).to_list(1000)
        base_sort = (existing_floor_units[0].get('sort_index', 0) + 10) if existing_floor_units else 10

        created = []
        for i in range(unit_count):
            unit_no = str(max_numeric + i + 1)
            unit_id = str(uuid.uuid4())
            doc = {
                'id': unit_id, 'floor_id': floor_id, 'building_id': building_id,
                'project_id': project_id, 'unit_no': unit_no,
                'unit_type': 'apartment', 'status': 'available',
                'sort_index': base_sort + (i * 10),
                'display_label': unit_no, 'created_at': ts,
            }
            if unit.unit_type_tag:
                doc['unit_type_tag'] = unit.unit_type_tag
            if unit.unit_note:
                doc['unit_note'] = unit.unit_note[:200]
            await db.units.insert_one(doc)
            created.append(unit_no)
            await _audit('unit', unit_id, 'create', user['id'], {'floor_id': floor_id, 'unit_no': unit_no})

        reseq_floor_changes, reseq_unit_changes = await _compute_building_resequence(db, building_id)
        for c in reseq_floor_changes:
            await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})
        if reseq_unit_changes:
            for c in reseq_unit_changes:
                await db.units.update_one({'id': c['id']}, {'$set': {
                    'unit_no': f"__tmp_{c['id']}", 'display_label': f"__tmp_{c['id']}",
                }})
            for c in reseq_unit_changes:
                await db.units.update_one({'id': c['id']}, {'$set': {
                    'unit_no': c['new_unit_no'], 'display_label': c['new_unit_no'],
                    'sort_index': c.get('new_sort_index', 0),
                }})

        return {'created': len(created), 'units': created}

    if not unit.unit_no:
        raise HTTPException(status_code=400, detail='יש להזין מספר דירה או כמות דירות')
    await _check_unit_quota(db, project_id, 1, user)
    existing = await db.units.find_one({
        'project_id': project_id, 'building_id': building_id,
        'floor_id': floor_id, 'unit_no': unit.unit_no,
        'archived': {'$ne': True},
    })
    if existing:
        raise HTTPException(status_code=400, detail='Unit number already exists on this floor')
    if unit.sort_index is None:
        max_unit = await db.units.find_one({'floor_id': floor_id, 'archived': {'$ne': True}}, sort=[('sort_index', -1)])
        unit.sort_index = (max_unit.get('sort_index', 0) + 10) if max_unit else 10
    unit_id = str(uuid.uuid4())
    doc = {
        'id': unit_id, 'floor_id': floor_id, 'building_id': building_id,
        'project_id': project_id, 'unit_no': unit.unit_no,
        'unit_type': unit.unit_type.value if unit.unit_type else 'apartment',
        'status': unit.status.value if unit.status else 'available',
        'sort_index': unit.sort_index,
        'display_label': unit.display_label or unit.unit_no, 'created_at': ts,
    }
    if unit.unit_type_tag:
        doc['unit_type_tag'] = unit.unit_type_tag
    if unit.unit_note:
        doc['unit_note'] = unit.unit_note[:200]
    await db.units.insert_one(doc)
    await _audit('unit', unit_id, 'create', user['id'], {'floor_id': floor_id, 'unit_no': unit.unit_no})
    return Unit(**{k: v for k, v in doc.items() if k != '_id'})


@router.get("/floors/{floor_id}/units", response_model=List[Unit])
async def list_units_by_floor(floor_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    units = await db.units.find({'floor_id': floor_id, 'archived': {'$ne': True}}, {'_id': 0}).sort('sort_index', 1).to_list(1000)
    return [Unit(**u) for u in units]


@router.patch("/units/{unit_id}")
async def patch_unit(unit_id: str, body: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    unit_doc = await db.units.find_one({'id': unit_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not unit_doc:
        raise HTTPException(status_code=404, detail='Unit not found')
    await _check_structure_admin(user, unit_doc['project_id'])
    updates = {}
    if 'unit_type_tag' in body:
        val = body['unit_type_tag']
        updates['unit_type_tag'] = val if val else None
    if 'unit_note' in body:
        val = body['unit_note']
        updates['unit_note'] = val[:200] if val else None
    if 'spare_tiles_count' in body:
        val = body['spare_tiles_count']
        if val is None:
            updates['spare_tiles_count'] = None
        else:
            try:
                parsed = int(val)
                if parsed < 0:
                    raise HTTPException(status_code=422, detail='spare_tiles_count must be >= 0')
                updates['spare_tiles_count'] = parsed
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail='spare_tiles_count must be an integer')
    if 'spare_tiles_notes' in body:
        val = body['spare_tiles_notes']
        updates['spare_tiles_notes'] = val[:500] if val else None
    if not updates:
        raise HTTPException(status_code=400, detail='No valid fields to update')
    await db.units.update_one({'id': unit_id}, {'$set': updates})
    await _audit('unit', unit_id, 'update', user['id'], updates)
    updated = await db.units.find_one({'id': unit_id}, {'_id': 0})
    return Unit(**updated)


SPARE_TILES_BASE_TYPES = [
    'ריצוף יבש',
    'ריצוף מרפסות',
    'חיפוי אמבטיות',
    'ריצוף אמבטיות',
    'חיפוי מטבח',
]


@router.patch("/units/{unit_id}/spare-tiles")
async def patch_unit_spare_tiles(unit_id: str, body: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    unit_doc = await db.units.find_one({'id': unit_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not unit_doc:
        raise HTTPException(status_code=404, detail='Unit not found')
    role = await _get_project_role(user, unit_doc['project_id'])
    if role not in ('project_manager', 'owner', 'management_team'):
        raise HTTPException(status_code=403, detail='אין הרשאה לעדכן ריצוף ספייר')

    if 'spare_tiles' not in body:
        raise HTTPException(status_code=400, detail='spare_tiles field is required')

    raw = body['spare_tiles']
    if not isinstance(raw, list):
        raise HTTPException(status_code=422, detail='spare_tiles must be an array')
    if len(raw) > 20:
        raise HTTPException(status_code=422, detail='מקסימום 20 סוגי ריצוף')

    validated = []
    seen_types = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise HTTPException(status_code=422, detail='Each spare tile entry must be an object')
        tile_type = entry.get('type', '')
        if not isinstance(tile_type, str) or not tile_type.strip():
            raise HTTPException(status_code=422, detail='type is required for each tile entry')
        tile_type = tile_type.strip()
        if len(tile_type) > 50:
            raise HTTPException(status_code=422, detail='שם סוג ריצוף ארוך מדי (מקסימום 50 תווים)')
        if tile_type.lower() in seen_types:
            raise HTTPException(status_code=422, detail=f'סוג ריצוף כפול: {tile_type}')
        seen_types.add(tile_type.lower())

        count = entry.get('count', 0)
        try:
            count = int(count)
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail='count must be an integer')
        if count < 0:
            raise HTTPException(status_code=422, detail='count must be >= 0')

        notes = entry.get('notes', '') or ''
        if not isinstance(notes, str):
            notes = str(notes)
        notes = notes.strip()
        if len(notes) > 500:
            raise HTTPException(status_code=422, detail='הערה ארוכה מדי (מקסימום 500 תווים)')

        validated.append({'type': tile_type, 'count': count, 'notes': notes})

    total_count = sum(e['count'] for e in validated)
    all_notes = ', '.join(f"{e['type']}: {e['notes']}" for e in validated if e['notes'])
    await db.units.update_one({'id': unit_id}, {'$set': {
        'spare_tiles': validated,
        'spare_tiles_count': total_count if validated else None,
        'spare_tiles_notes': all_notes[:500] if all_notes else None,
    }})
    await _audit('unit', unit_id, 'update_spare_tiles', user['id'], {'spare_tiles': validated})
    updated = await db.units.find_one({'id': unit_id}, {'_id': 0})
    return Unit(**updated)


@router.post("/floors/bulk")
async def bulk_create_floors(body: BulkFloorRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    await _check_structure_admin(user, body.project_id)
    building = await db.buildings.find_one({'id': body.building_id, 'project_id': body.project_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not building:
        raise HTTPException(status_code=404, detail='Building not found in this project')
    if body.from_floor > body.to_floor:
        raise HTTPException(status_code=422, detail='from_floor must be <= to_floor')
    if body.to_floor - body.from_floor > 200:
        raise HTTPException(status_code=422, detail='Maximum 200 floors per batch')

    existing_floors = await db.floors.find({'building_id': body.building_id, 'archived': {'$ne': True}}, {'_id': 0}).sort('sort_index', 1).to_list(1000)

    batch_count = body.to_floor - body.from_floor + 1
    if body.insert_after_floor_id:
        sorted_ef = sorted(existing_floors, key=lambda f: f.get('sort_index', 0))
        if body.insert_after_floor_id == '__start__':
            first_si = sorted_ef[0].get('sort_index', 0) if sorted_ef else 1000
            base_si = first_si - batch_count - 1
        else:
            target = next((f for f in sorted_ef if f['id'] == body.insert_after_floor_id), None)
            if not target:
                raise HTTPException(status_code=422, detail='insert_after_floor_id not found in building')
            after_si = target.get('sort_index', 0)
            idx = sorted_ef.index(target)
            if idx + 1 < len(sorted_ef):
                next_si = sorted_ef[idx + 1].get('sort_index', 0)
                gap = next_si - after_si
                base_si = after_si + 1
            else:
                base_si = after_si + 1
    else:
        base_si = (max(f.get('sort_index', 0) for f in existing_floors) + 1000) if existing_floors else 0

    if body.dry_run:
        would_create = 0
        would_skip = 0
        for num in range(body.from_floor, body.to_floor + 1):
            existing = await db.floors.find_one({'building_id': body.building_id, 'floor_number': num, 'archived': {'$ne': True}})
            if existing:
                would_skip += 1
            else:
                would_create += 1
        return {'dry_run': True, 'would_create': would_create, 'would_skip': would_skip, 'message': f'תצוגה מקדימה: {would_create} קומות חדשות, {would_skip} דילוגים'}

    batch_id = body.batch_id or str(uuid.uuid4())[:12]
    created = []
    skipped = 0
    ts = _now()
    create_idx = 0
    for num in range(body.from_floor, body.to_floor + 1):
        existing = await db.floors.find_one({
            'building_id': body.building_id,
            'floor_number': num,
            'archived': {'$ne': True},
        })
        if existing:
            skipped += 1
            continue
        floor_id = str(uuid.uuid4())
        si = base_si + create_idx
        doc = {
            'id': floor_id,
            'building_id': body.building_id,
            'project_id': body.project_id,
            'name': f'קומה {num}',
            'floor_number': num,
            'sort_index': si,
            'display_label': f'קומה {num}',
            'kind': 'basement' if num < 0 else ('ground' if num == 0 else 'residential'),
            'created_at': ts,
            'batch_id': batch_id,
        }
        await db.floors.insert_one(doc)
        created.append({'id': floor_id, 'name': doc['name'], 'floor_number': num, 'sort_index': si})
        create_idx += 1

    reseq_floor_changes, reseq_unit_changes = await _compute_building_resequence(db, body.building_id)
    for c in reseq_floor_changes:
        await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})
    if reseq_unit_changes:
        for c in reseq_unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': f"__tmp_{c['id']}",
                'display_label': f"__tmp_{c['id']}",
            }})
        for c in reseq_unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': c['new_unit_no'],
                'display_label': c['new_display_label'],
                'sort_index': c['new_sort_index'],
            }})

    await _audit('building', body.building_id, 'bulk_create_floors', user['id'], {
        'project_id': body.project_id,
        'from_floor': body.from_floor,
        'to_floor': body.to_floor,
        'created_count': len(created),
        'skipped_count': skipped,
        'batch_id': batch_id,
        'insert_after_floor_id': body.insert_after_floor_id,
    })

    msg = f'נוצרו {len(created)} קומות'
    if skipped > 0:
        msg += f', דולגו {skipped} קומות קיימות'

    return {'created_count': len(created), 'skipped_count': skipped, 'items': created, 'message': msg, 'batch_id': batch_id}


@router.post("/units/bulk")
async def bulk_create_units(body: BulkUnitRequest, user: dict = Depends(get_current_user)):
    import time as _time
    rid = str(uuid.uuid4())[:8]
    t0 = _time.time()
    db = get_db()
    await _check_structure_admin(user, body.project_id)
    building = await db.buildings.find_one({'id': body.building_id, 'project_id': body.project_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not building:
        raise HTTPException(status_code=404, detail='Building not found in this project')
    if body.from_floor > body.to_floor:
        raise HTTPException(status_code=422, detail='from_floor must be <= to_floor')
    if body.units_per_floor < 1 or body.units_per_floor > 100:
        raise HTTPException(status_code=422, detail='units_per_floor must be between 1 and 100')
    total_floors = body.to_floor - body.from_floor + 1
    if total_floors > 200:
        raise HTTPException(status_code=422, detail='Maximum 200 floors per batch')

    all_floors = await db.floors.find({'building_id': body.building_id, 'archived': {'$ne': True}}, {'_id': 0}).sort('sort_index', 1).to_list(1000)
    existing_numeric_units = await db.units.find({'building_id': body.building_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(100000)
    max_existing = 0
    for eu in existing_numeric_units:
        if _is_numeric_unit(eu.get('unit_no', '')):
            max_existing = max(max_existing, int(eu['unit_no']))
    global_counter = max_existing

    target_floors = [f for f in all_floors if body.from_floor <= f['floor_number'] <= body.to_floor]

    if body.dry_run:
        would_create = 0
        would_skip = 0
        temp_counter = global_counter
        for floor in target_floors:
            for unit_idx in range(body.units_per_floor):
                if body.unit_prefix:
                    unit_num = body.unit_start_number + unit_idx
                    unit_no = f'{body.unit_prefix}{str(unit_num).zfill(body.unit_number_padding) if body.unit_number_padding > 0 else str(unit_num)}'
                else:
                    temp_counter += 1
                    unit_no = str(temp_counter)
                existing = await db.units.find_one({'floor_id': floor['id'], 'unit_no': unit_no, 'archived': {'$ne': True}})
                if existing:
                    would_skip += 1
                else:
                    would_create += 1
        return {'dry_run': True, 'would_create': would_create, 'would_skip': would_skip, 'message': f'תצוגה מקדימה: {would_create} דירות חדשות, {would_skip} דילוגים'}

    would_create_total = 0
    pre_count_counter = global_counter
    for floor in target_floors:
        for unit_idx in range(body.units_per_floor):
            if body.unit_prefix:
                unit_num = body.unit_start_number + unit_idx
                unit_no = f'{body.unit_prefix}{str(unit_num).zfill(body.unit_number_padding) if body.unit_number_padding > 0 else str(unit_num)}'
            else:
                pre_count_counter += 1
                unit_no = str(pre_count_counter)
            existing = await db.units.find_one({'floor_id': floor['id'], 'unit_no': unit_no, 'archived': {'$ne': True}})
            if not existing:
                would_create_total += 1
    if would_create_total > 0:
        await _check_unit_quota(db, body.project_id, would_create_total, user)

    batch_id = body.batch_id or str(uuid.uuid4())[:12]
    created = []
    skipped = 0
    ts = _now()

    for floor in target_floors:
        existing_floor_units = await db.units.find({'floor_id': floor['id'], 'archived': {'$ne': True}}, {'_id': 0}).to_list(10000)
        floor_unit_count = len(existing_floor_units)

        for unit_idx in range(body.units_per_floor):
            if body.unit_prefix:
                unit_num = body.unit_start_number + unit_idx
                unit_no = f'{body.unit_prefix}{str(unit_num).zfill(body.unit_number_padding) if body.unit_number_padding > 0 else str(unit_num)}'
            else:
                global_counter += 1
                unit_no = str(global_counter)

            existing = await db.units.find_one({
                'floor_id': floor['id'],
                'unit_no': unit_no,
                'archived': {'$ne': True},
            })
            if existing:
                skipped += 1
                continue

            unit_id = str(uuid.uuid4())
            si = (floor_unit_count + unit_idx + 1) * 10
            doc = {
                'id': unit_id,
                'floor_id': floor['id'],
                'building_id': body.building_id,
                'project_id': body.project_id,
                'unit_no': unit_no,
                'unit_type': 'apartment',
                'status': 'available',
                'sort_index': si,
                'display_label': unit_no,
                'created_at': ts,
                'batch_id': batch_id,
            }
            await db.units.insert_one(doc)
            created.append({'id': unit_id, 'unit_no': unit_no, 'floor_number': floor['floor_number']})

    await _audit('building', body.building_id, 'bulk_create_units', user['id'], {
        'project_id': body.project_id,
        'from_floor': body.from_floor,
        'to_floor': body.to_floor,
        'units_per_floor': body.units_per_floor,
        'created_count': len(created),
        'skipped_count': skipped,
        'batch_id': batch_id,
    })

    elapsed_ms = round((_time.time() - t0) * 1000, 1)
    units_requested = len(target_floors) * body.units_per_floor
    logger.info(
        f"[BULK-UNITS] rid={rid} project_id={body.project_id} building_id={body.building_id} "
        f"floors_matched={len(target_floors)} units_per_floor={body.units_per_floor} "
        f"units_requested={units_requested} units_created={len(created)} skipped={skipped} "
        f"errors=[] elapsed_ms={elapsed_ms}"
    )

    msg = f'נוצרו {len(created)} דירות'
    if skipped > 0:
        msg += f', דולגו {skipped} דירות קיימות'

    return {'created_count': len(created), 'skipped_count': skipped, 'items': created, 'message': msg, 'batch_id': batch_id}


@router.get("/projects/{project_id}/hierarchy")
async def get_project_hierarchy(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    await _check_project_read_access(user, project_id)

    buildings = await db.buildings.find({'project_id': project_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(1000)
    building_names = [b.get('name', '?') for b in buildings]
    logger.info(f"[HIERARCHY:ACCESS] user={user['id']} project={project_id} buildings={len(buildings)} names={building_names}")
    all_floors = await db.floors.find({'project_id': project_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(10000)

    building_ids = [b['id'] for b in buildings]
    floor_ids = [f['id'] for f in all_floors]

    all_units = []
    if floor_ids:
        all_units = await db.units.find({'floor_id': {'$in': floor_ids}, 'archived': {'$ne': True}}, {'_id': 0}).to_list(100000)

    units_by_floor = {}
    for u in all_units:
        fid = u['floor_id']
        if fid not in units_by_floor:
            units_by_floor[fid] = []
        raw_unit_no = u['unit_no']
        raw_display = u.get('display_label', raw_unit_no)
        if _is_numeric_unit(raw_unit_no):
            eff = raw_unit_no
        else:
            eff = raw_display or raw_unit_no
        unit_entry = {
            'id': u['id'],
            'unit_no': raw_unit_no,
            'unit_type': u.get('unit_type', 'apartment'),
            'status': u.get('status', 'available'),
            'sort_index': u.get('sort_index', 0),
            'display_label': raw_display,
            'effective_label': eff,
        }
        if u.get('unit_type_tag'):
            unit_entry['unit_type_tag'] = u['unit_type_tag']
        if u.get('unit_note'):
            unit_entry['unit_note'] = u['unit_note']
        units_by_floor[fid].append(unit_entry)

    for fid in units_by_floor:
        units_by_floor[fid].sort(key=lambda x: x['sort_index'])

    floors_by_building = {}
    for f in all_floors:
        bid = f['building_id']
        if bid not in floors_by_building:
            floors_by_building[bid] = []
        floors_by_building[bid].append({
            'id': f['id'],
            'name': f['name'],
            'floor_number': f['floor_number'],
            'sort_index': f.get('sort_index', f['floor_number'] * 1000),
            'display_label': f.get('display_label', f['name']),
            'kind': f.get('kind'),
            'units': units_by_floor.get(f['id'], []),
        })

    for bid in floors_by_building:
        floors_by_building[bid].sort(key=lambda x: x['sort_index'])

    buildings.sort(key=lambda b: (b.get('sort_index', 0), _natural_sort_key(b.get('name', ''))))
    hierarchy_buildings = []
    for b in buildings:
        hierarchy_buildings.append({
            'id': b['id'],
            'name': b['name'],
            'code': b.get('code'),
            'floors': floors_by_building.get(b['id'], []),
        })

    return {
        'project_id': project_id,
        'project_name': project['name'],
        'buildings': hierarchy_buildings,
    }


@router.get("/units/{unit_id}/tasks", response_model=List[Task])
async def list_unit_tasks(unit_id: str,
                          status: Optional[str] = Query(None),
                          category: Optional[str] = Query(None),
                          user: dict = Depends(get_current_user)):
    db = get_db()
    query = {'unit_id': unit_id}
    if status:
        query['status'] = status
    if category:
        query['category'] = category
    tasks = await db.tasks.find(query, {'_id': 0}).sort('created_at', -1).to_list(1000)
    tasks = sorted(tasks, key=_priority_sort_key)
    from services.object_storage import resolve_urls_in_doc
    result = []
    for t in tasks:
        td = Task(**t).dict()
        resolve_urls_in_doc(td)
        result.append(td)
    return result


@router.get("/units/{unit_id}")
async def get_unit_detail(unit_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    unit = await db.units.find_one({'id': unit_id}, {'_id': 0})
    if not unit:
        raise HTTPException(status_code=404, detail='Unit not found')
    floor = await db.floors.find_one({'id': unit.get('floor_id')}, {'_id': 0}) if unit.get('floor_id') else None
    building = await db.buildings.find_one({'id': unit.get('building_id')}, {'_id': 0}) if unit.get('building_id') else None
    project_id = unit.get('project_id') or (building.get('project_id') if building else None)
    project = await db.projects.find_one({'id': project_id}, {'_id': 0}) if project_id else None
    if project_id:
        await _check_project_read_access(user, project_id)

    effective_label = unit.get('display_label') or unit.get('unit_no', '')
    try:
        int(unit.get('unit_no', ''))
        effective_label = unit.get('display_label') or unit.get('unit_no', '')
    except (ValueError, TypeError):
        effective_label = unit.get('display_label') or unit.get('unit_no', '')

    tasks = await db.tasks.find({'unit_id': unit_id}, {'_id': 0}).to_list(10000)
    by_status = {}
    for t in tasks:
        s = t.get('status', 'open')
        by_status[s] = by_status.get(s, 0) + 1

    return {
        'unit': {
            **unit,
            'effective_label': effective_label,
        },
        'floor': {'id': floor['id'], 'name': floor.get('name', '')} if floor else None,
        'building': {'id': building['id'], 'name': building.get('name', '')} if building else None,
        'project': {'id': project['id'], 'name': project.get('name', ''), 'code': project.get('code', '')} if project else None,
        'kpi': {
            'total': len(tasks),
            'open': by_status.get('open', 0) + by_status.get('assigned', 0) + by_status.get('reopened', 0),
            'in_progress': by_status.get('in_progress', 0) + by_status.get('waiting_verify', 0) + by_status.get('pending_contractor_proof', 0) + by_status.get('pending_manager_approval', 0),
            'closed': by_status.get('closed', 0),
        },
    }


@router.post("/buildings/{building_id}/resequence")
async def resequence_building(building_id: str, body: dict = Body(...), user: dict = Depends(get_current_user)):
    db = get_db()
    building = await db.buildings.find_one({'id': building_id}, {'_id': 0})
    if not building:
        raise HTTPException(status_code=404, detail='Building not found')
    await _check_structure_admin(user, building['project_id'])
    dry_run = body.get('dry_run', False)

    floor_changes, unit_changes = await _compute_building_resequence(db, building_id)

    if dry_run:
        return {
            'dry_run': True,
            'floors_affected': len(floor_changes),
            'units_affected': len(unit_changes),
            'floor_changes': floor_changes,
            'unit_changes': unit_changes,
        }
    for c in floor_changes:
        await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})
    if unit_changes:
        for c in unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': f"__tmp_{c['id']}",
                'display_label': f"__tmp_{c['id']}",
            }})
        for c in unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': c['new_unit_no'],
                'display_label': c['new_display_label'],
                'sort_index': c['new_sort_index'],
            }})
    await _audit('building', building_id, 'resequence', user['id'], {
        'floors_affected': len(floor_changes),
        'units_affected': len(unit_changes),
        'floor_changes': floor_changes,
        'unit_changes': unit_changes,
    })
    return {
        'success': True,
        'floors_affected': len(floor_changes),
        'units_affected': len(unit_changes),
        'floor_changes': floor_changes,
        'unit_changes': unit_changes,
    }


@router.post("/projects/{project_id}/insert-floor")
async def insert_floor(project_id: str, body: InsertFloorRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    await _check_structure_admin(user, project_id)
    building = await db.buildings.find_one({'id': body.building_id, 'project_id': project_id})
    if not building:
        raise HTTPException(status_code=404, detail='Building not found in this project')

    floors = await db.floors.find({'building_id': body.building_id}, {'_id': 0}).sort('sort_index', 1).to_list(1000)
    if body.insert_after_floor_id:
        insert_si = _compute_insert_sort_index(floors, body.insert_after_floor_id, strict=True)
    elif body.insert_at_index is not None:
        insert_si = body.insert_at_index
    else:
        insert_si = (max(f.get('sort_index', 0) for f in floors) + 1000) if floors else 0

    floors_to_shift = [f for f in floors if f.get('sort_index', 0) >= insert_si]
    floor_shift_changes = []
    for f in floors_to_shift:
        old_si = f.get('sort_index', 0)
        new_si = old_si + 1000
        floor_shift_changes.append({
            'type': 'floor',
            'id': f['id'],
            'name': f['name'],
            'old_sort_index': old_si,
            'new_sort_index': new_si,
        })

    if body.dry_run:
        for c in floor_shift_changes:
            await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})
        temp_floor_id = '__preview__'
        temp_floor_doc = {
            'id': temp_floor_id, 'building_id': body.building_id, 'project_id': project_id,
            'name': body.name, 'floor_number': insert_si // 1000,
            'sort_index': insert_si,
            'display_label': body.display_label or body.name,
            'kind': body.kind.value if body.kind else None,
            'created_at': _now(),
        }
        await db.floors.insert_one(temp_floor_doc)
        _, unit_changes = await _compute_building_resequence(db, body.building_id)
        await db.floors.delete_one({'id': temp_floor_id})
        for c in floor_shift_changes:
            await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['old_sort_index']}})
        return {
            'dry_run': True,
            'new_floor_name': body.name,
            'insert_at_index': insert_si,
            'floors_affected': len(floor_shift_changes),
            'units_affected': len(unit_changes),
            'floor_changes': floor_shift_changes,
            'unit_changes': unit_changes,
        }

    for c in floor_shift_changes:
        await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})

    floor_id = str(uuid.uuid4())
    ts = _now()
    new_floor_doc = {
        'id': floor_id, 'building_id': body.building_id, 'project_id': project_id,
        'name': body.name, 'floor_number': insert_si // 1000,
        'sort_index': insert_si,
        'display_label': body.display_label or body.name,
        'kind': body.kind.value if body.kind else None,
        'created_at': ts,
    }
    await db.floors.insert_one(new_floor_doc)

    reseq_floor_changes, reseq_unit_changes = await _compute_building_resequence(db, body.building_id)
    for c in reseq_floor_changes:
        await db.floors.update_one({'id': c['id']}, {'$set': {'sort_index': c['new_sort_index']}})
    if reseq_unit_changes:
        for c in reseq_unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': f"__tmp_{c['id']}",
                'display_label': f"__tmp_{c['id']}",
            }})
        for c in reseq_unit_changes:
            await db.units.update_one({'id': c['id']}, {'$set': {
                'unit_no': c['new_unit_no'],
                'display_label': c['new_display_label'],
                'sort_index': c['new_sort_index'],
            }})

    await _audit('building', body.building_id, 'insert_floor', user['id'], {
        'project_id': project_id,
        'new_floor_id': floor_id,
        'new_floor_name': body.name,
        'insert_at_index': insert_si,
        'floors_shifted': len(floor_shift_changes),
        'units_renumbered': len(reseq_unit_changes),
        'floor_changes': floor_shift_changes,
        'unit_changes': reseq_unit_changes,
    })
    return {
        'success': True,
        'new_floor': {k: v for k, v in new_floor_doc.items() if k != '_id'},
        'floors_shifted': len(floor_shift_changes),
        'units_renumbered': len(reseq_unit_changes),
    }


@router.get("/buildings/{building_id}/defects-summary")
async def building_defects_summary(building_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    building = await db.buildings.find_one({'id': building_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not building:
        raise HTTPException(status_code=404, detail='Building not found')
    project_id = building['project_id']
    await _check_project_read_access(user, project_id)
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')

    floors = await db.floors.find(
        {'building_id': building_id, 'archived': {'$ne': True}}, {'_id': 0}
    ).sort('sort_index', 1).to_list(1000)

    floor_ids = [f['id'] for f in floors]
    units = []
    if floor_ids:
        units = await db.units.find(
            {'floor_id': {'$in': floor_ids}, 'archived': {'$ne': True}}, {'_id': 0}
        ).to_list(100000)

    units_by_floor = {}
    unit_ids = []
    for u in units:
        fid = u['floor_id']
        if fid not in units_by_floor:
            units_by_floor[fid] = []
        units_by_floor[fid].append(u)
        unit_ids.append(u['id'])

    for fid in units_by_floor:
        units_by_floor[fid].sort(key=lambda x: x.get('sort_index', 0))

    tasks = await db.tasks.find(
        {'building_id': building_id, 'archived': {'$ne': True}},
        {'_id': 0, 'unit_id': 1, 'status': 1, 'category': 1}
    ).to_list(100000)

    defects_by_unit = {}
    categories_by_unit = {}
    for t in tasks:
        uid = t.get('unit_id')
        if not uid:
            continue
        if uid not in defects_by_unit:
            defects_by_unit[uid] = {}
            categories_by_unit[uid] = set()
        s = t.get('status', 'open')
        defects_by_unit[uid][s] = defects_by_unit[uid].get(s, 0) + 1
        cat = t.get('category')
        if cat:
            categories_by_unit[uid].add(cat)

    open_statuses = {'open', 'assigned', 'reopened'}
    in_progress_statuses = {'in_progress', 'pending_contractor_proof', 'pending_manager_approval', 'returned_to_contractor'}
    waiting_verify_statuses = {'waiting_verify'}
    closed_statuses = {'closed'}

    def compute_counts(status_map):
        open_count = sum(status_map.get(s, 0) for s in open_statuses)
        in_progress = sum(status_map.get(s, 0) for s in in_progress_statuses)
        waiting = sum(status_map.get(s, 0) for s in waiting_verify_statuses)
        closed = sum(status_map.get(s, 0) for s in closed_statuses)
        total = sum(status_map.values())
        return {
            'open': open_count,
            'in_progress': in_progress,
            'waiting_verify': waiting,
            'closed': closed,
            'total': total,
        }

    floor_results = []
    for f in floors:
        floor_units = units_by_floor.get(f['id'], [])
        unit_results = []
        for u in floor_units:
            status_map = defects_by_unit.get(u['id'], {})
            unit_entry = {
                'id': u['id'],
                'unit_no': u.get('unit_no', ''),
                'display_label': u.get('display_label') or u.get('unit_no', ''),
                'unit_type': u.get('unit_type', 'apartment'),
                'defect_counts': compute_counts(status_map),
                'categories': sorted(categories_by_unit.get(u['id'], set())),
            }
            if u.get('unit_type_tag'):
                unit_entry['unit_type_tag'] = u['unit_type_tag']
            if u.get('unit_note'):
                unit_entry['unit_note'] = u['unit_note']
            unit_results.append(unit_entry)
        floor_results.append({
            'id': f['id'],
            'name': f.get('name', ''),
            'floor_number': f.get('floor_number', 0),
            'display_label': f.get('display_label') or f.get('name', ''),
            'units': unit_results,
        })

    return {
        'building': {
            'id': building['id'],
            'name': building.get('name', ''),
            'code': building.get('code'),
        },
        'project': {
            'id': project['id'],
            'name': project.get('name', ''),
            'code': project.get('code', ''),
        },
        'floors': floor_results,
    }


@router.put("/projects/{project_id}/qc-template")
async def assign_project_qc_template(project_id: str, request: Request, user: dict = Depends(require_super_admin)):
    db = get_db()
    project = await db.projects.find_one({"id": project_id}, {"_id": 0, "id": 1, "name": 1})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    body = await request.json()
    template_version_id = body.get("template_version_id")
    if not template_version_id:
        raise HTTPException(status_code=400, detail="template_version_id is required")

    tpl = await db.qc_templates.find_one({"id": template_version_id}, {"_id": 0, "id": 1, "name": 1, "version": 1, "family_id": 1})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template version not found")

    family_id = tpl.get("family_id")

    active_runs = await db.qc_runs.count_documents({"project_id": project_id})
    warning = None
    if active_runs > 0:
        warning = f"לפרויקט יש {active_runs} ביצועים קיימים. שינוי תבנית ישפיע רק על בדיקות חדשות."

    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "qc_template_version_id": template_version_id,
            "qc_template_family_id": family_id,
        }}
    )
    logger.info(f"[QC-TPL] Assigned template={template_version_id} family={family_id} to project={project_id} by user={user['id']}")

    return {
        "success": True,
        "project_id": project_id,
        "template_version_id": template_version_id,
        "template_family_id": family_id,
        "template_name": tpl["name"],
        "template_version": tpl["version"],
        "warning": warning,
    }


@router.get("/projects/{project_id}/qc-template")
async def get_project_qc_template(project_id: str, user: dict = Depends(get_current_user)):
    if not _is_super_admin(user):
        db_check = get_db()
        membership = await db_check.project_memberships.find_one({
            'user_id': user['id'],
            'project_id': project_id,
        })
        if not membership:
            raise HTTPException(status_code=403, detail='אין לך גישה לפרויקט זה')
        allowed_roles = ['owner', 'project_manager', 'management_team']
        if membership.get('role') not in allowed_roles:
            raise HTTPException(status_code=403, detail='אין הרשאה לצפות בתבנית QC')
    db = get_db()
    project = await db.projects.find_one(
        {"id": project_id},
        {"_id": 0, "id": 1, "qc_template_version_id": 1, "qc_template_family_id": 1}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    version_id = project.get("qc_template_version_id")
    family_id = project.get("qc_template_family_id")

    if not version_id:
        return {
            "assigned": False,
            "template_version_id": None,
            "template_family_id": None,
            "template_name": None,
            "template_version": None,
        }

    tpl = await db.qc_templates.find_one(
        {"id": version_id},
        {"_id": 0, "id": 1, "name": 1, "version": 1, "family_id": 1}
    )
    if not tpl:
        return {
            "assigned": True,
            "template_version_id": version_id,
            "template_family_id": family_id,
            "template_name": "(נמחקה)",
            "template_version": None,
        }

    resolved_family = family_id or tpl.get("family_id")

    return {
        "assigned": True,
        "template_version_id": version_id,
        "template_family_id": resolved_family,
        "template_name": tpl["name"],
        "template_version": tpl["version"],
    }
