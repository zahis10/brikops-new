from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import uuid
import logging

from contractor_ops.router import get_db, get_current_user, require_roles, _now, _audit, _check_project_access, _check_structure_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["archive"])

UNDO_WINDOW_MINUTES = 10
HARD_DELETE_RETENTION_DAYS = 7

def _active(query: dict) -> dict:
    q = dict(query)
    q['archived'] = {'$ne': True}
    return q


class ArchiveRequest(BaseModel):
    reason: Optional[str] = None


class HardDeleteRequest(BaseModel):
    typed_confirmation: str
    stepup_token: Optional[str] = None


async def _get_dependency_counts(db, entity_type: str, entity_id: str) -> dict:
    counts = {}
    if entity_type == 'building':
        counts['floors'] = await db.floors.count_documents({'building_id': entity_id, 'archived': {'$ne': True}})
        counts['units'] = await db.units.count_documents({'building_id': entity_id, 'archived': {'$ne': True}})
        counts['tasks'] = await db.tasks.count_documents({'building_id': entity_id})
    elif entity_type == 'floor':
        counts['units'] = await db.units.count_documents({'floor_id': entity_id, 'archived': {'$ne': True}})
        counts['tasks'] = await db.tasks.count_documents({'floor_id': entity_id})
    elif entity_type == 'unit':
        counts['tasks'] = await db.tasks.count_documents({'unit_id': entity_id})
    return counts


@router.post("/buildings/{building_id}/archive")
async def archive_building(building_id: str, body: ArchiveRequest = ArchiveRequest(), user: dict = Depends(get_current_user)):
    db = get_db()
    building = await db.buildings.find_one({'id': building_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not building:
        raise HTTPException(status_code=404, detail='בניין לא נמצא')
    await _check_structure_admin(user, building['project_id'])

    ts = _now()
    archive_meta = {
        'archived': True, 'archived_at': ts,
        'archived_by': user['id'], 'archived_reason': body.reason or 'manual',
    }

    deps = await _get_dependency_counts(db, 'building', building_id)

    await db.buildings.update_one({'id': building_id}, {'$set': archive_meta})

    floors = await db.floors.find({'building_id': building_id, 'archived': {'$ne': True}}, {'_id': 0, 'id': 1}).to_list(10000)
    floor_ids = [f['id'] for f in floors]
    if floor_ids:
        cascade_meta = {**archive_meta, 'archived_reason': f'cascade:building:{building_id}'}
        await db.floors.update_many({'building_id': building_id, 'archived': {'$ne': True}}, {'$set': cascade_meta})
        await db.units.update_many({'building_id': building_id, 'archived': {'$ne': True}}, {'$set': cascade_meta})

    await _audit('building', building_id, 'archive', user['id'], {
        'project_id': building['project_id'], 'reason': body.reason,
        'cascaded_floors': len(floor_ids),
        'dependencies': deps,
    })
    logger.info(f"[ARCHIVE] type=building id={building_id} by={user['id']} cascaded_floors={len(floor_ids)} deps={deps}")
    return {'success': True, 'archived': building_id, 'dependencies': deps, 'cascaded_floors': len(floor_ids)}


@router.post("/floors/{floor_id}/archive")
async def archive_floor(floor_id: str, body: ArchiveRequest = ArchiveRequest(), user: dict = Depends(get_current_user)):
    db = get_db()
    floor = await db.floors.find_one({'id': floor_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not floor:
        raise HTTPException(status_code=404, detail='קומה לא נמצאה')
    await _check_structure_admin(user, floor['project_id'])

    ts = _now()
    archive_meta = {
        'archived': True, 'archived_at': ts,
        'archived_by': user['id'], 'archived_reason': body.reason or 'manual',
    }

    deps = await _get_dependency_counts(db, 'floor', floor_id)

    await db.floors.update_one({'id': floor_id}, {'$set': archive_meta})
    await db.units.update_many({'floor_id': floor_id, 'archived': {'$ne': True}}, {'$set': {
        **archive_meta, 'archived_reason': f'cascade:floor:{floor_id}',
    }})

    cascaded_units = await db.units.count_documents({'floor_id': floor_id, 'archived': True, 'archived_reason': f'cascade:floor:{floor_id}'})

    await _audit('floor', floor_id, 'archive', user['id'], {
        'project_id': floor['project_id'], 'building_id': floor['building_id'],
        'reason': body.reason, 'cascaded_units': cascaded_units, 'dependencies': deps,
    })
    logger.info(f"[ARCHIVE] type=floor id={floor_id} by={user['id']} cascaded_units={cascaded_units} deps={deps}")
    return {'success': True, 'archived': floor_id, 'dependencies': deps, 'cascaded_units': cascaded_units}


@router.post("/units/{unit_id}/archive")
async def archive_unit(unit_id: str, body: ArchiveRequest = ArchiveRequest(), user: dict = Depends(get_current_user)):
    db = get_db()
    unit = await db.units.find_one({'id': unit_id, 'archived': {'$ne': True}}, {'_id': 0})
    if not unit:
        raise HTTPException(status_code=404, detail='דירה לא נמצאה')
    await _check_structure_admin(user, unit['project_id'])

    ts = _now()
    deps = await _get_dependency_counts(db, 'unit', unit_id)

    await db.units.update_one({'id': unit_id}, {'$set': {
        'archived': True, 'archived_at': ts,
        'archived_by': user['id'], 'archived_reason': body.reason or 'manual',
    }})

    await _audit('unit', unit_id, 'archive', user['id'], {
        'project_id': unit['project_id'], 'floor_id': unit.get('floor_id'),
        'reason': body.reason, 'dependencies': deps,
    })
    logger.info(f"[ARCHIVE] type=unit id={unit_id} by={user['id']} deps={deps}")
    return {'success': True, 'archived': unit_id, 'dependencies': deps}


@router.post("/buildings/{building_id}/restore")
async def restore_building(building_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    building = await db.buildings.find_one({'id': building_id, 'archived': True}, {'_id': 0})
    if not building:
        raise HTTPException(status_code=404, detail='בניין לא נמצא בארכיון')
    await _check_structure_admin(user, building['project_id'])

    unset_fields = {'archived': '', 'archived_at': '', 'archived_by': '', 'archived_reason': ''}
    await db.buildings.update_one({'id': building_id}, {'$unset': unset_fields})
    await db.floors.update_many(
        {'building_id': building_id, 'archived_reason': f'cascade:building:{building_id}'},
        {'$unset': unset_fields}
    )
    await db.units.update_many(
        {'building_id': building_id, 'archived_reason': f'cascade:building:{building_id}'},
        {'$unset': unset_fields}
    )

    await _audit('building', building_id, 'restore', user['id'], {'project_id': building['project_id']})
    logger.info(f"[RESTORE] type=building id={building_id} by={user['id']}")
    return {'success': True, 'restored': building_id}


@router.post("/floors/{floor_id}/restore")
async def restore_floor(floor_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    floor = await db.floors.find_one({'id': floor_id, 'archived': True}, {'_id': 0})
    if not floor:
        raise HTTPException(status_code=404, detail='קומה לא נמצאה בארכיון')
    await _check_structure_admin(user, floor['project_id'])

    parent_building = await db.buildings.find_one({'id': floor['building_id']}, {'_id': 0})
    if parent_building and parent_building.get('archived'):
        raise HTTPException(status_code=409, detail='לא ניתן לשחזר קומה כשהבניין מאורכב. שחזר את הבניין קודם.')

    unset_fields = {'archived': '', 'archived_at': '', 'archived_by': '', 'archived_reason': ''}
    await db.floors.update_one({'id': floor_id}, {'$unset': unset_fields})
    await db.units.update_many(
        {'floor_id': floor_id, 'archived_reason': f'cascade:floor:{floor_id}'},
        {'$unset': unset_fields}
    )

    await _audit('floor', floor_id, 'restore', user['id'], {
        'project_id': floor['project_id'], 'building_id': floor['building_id'],
    })
    logger.info(f"[RESTORE] type=floor id={floor_id} by={user['id']}")
    return {'success': True, 'restored': floor_id}


@router.post("/units/{unit_id}/restore")
async def restore_unit(unit_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    unit = await db.units.find_one({'id': unit_id, 'archived': True}, {'_id': 0})
    if not unit:
        raise HTTPException(status_code=404, detail='דירה לא נמצאה בארכיון')
    await _check_structure_admin(user, unit['project_id'])

    parent_floor = await db.floors.find_one({'id': unit['floor_id']}, {'_id': 0})
    if parent_floor and parent_floor.get('archived'):
        raise HTTPException(status_code=409, detail='לא ניתן לשחזר דירה כשהקומה מאורכבת. שחזר את הקומה קודם.')

    unset_fields = {'archived': '', 'archived_at': '', 'archived_by': '', 'archived_reason': ''}
    await db.units.update_one({'id': unit_id}, {'$unset': unset_fields})

    await _audit('unit', unit_id, 'restore', user['id'], {
        'project_id': unit['project_id'], 'floor_id': unit.get('floor_id'),
    })
    logger.info(f"[RESTORE] type=unit id={unit_id} by={user['id']}")
    return {'success': True, 'restored': unit_id}


@router.post("/batches/{batch_id}/undo")
async def undo_batch(batch_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    sample = await db.buildings.find_one({'batch_id': batch_id})
    if not sample:
        sample = await db.floors.find_one({'batch_id': batch_id})
    if not sample:
        sample = await db.units.find_one({'batch_id': batch_id})
    if not sample:
        raise HTTPException(status_code=404, detail='באץ׳ לא נמצא')

    await _check_structure_admin(user, sample['project_id'])

    created_at = sample.get('created_at', '')
    if created_at:
        try:
            created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00')) if isinstance(created_at, str) else created_at
            now = datetime.now(timezone.utc)
            if (now - created_dt).total_seconds() > UNDO_WINDOW_MINUTES * 60:
                raise HTTPException(status_code=410, detail=f'חלון הביטול ({UNDO_WINDOW_MINUTES} דקות) עבר')
        except (ValueError, TypeError):
            pass

    ts = _now()
    archive_meta = {
        'archived': True, 'archived_at': ts,
        'archived_by': user['id'], 'archived_reason': f'undo:batch:{batch_id}',
    }

    b_result = await db.buildings.update_many({'batch_id': batch_id, 'archived': {'$ne': True}}, {'$set': archive_meta})
    f_result = await db.floors.update_many({'batch_id': batch_id, 'archived': {'$ne': True}}, {'$set': archive_meta})
    u_result = await db.units.update_many({'batch_id': batch_id, 'archived': {'$ne': True}}, {'$set': archive_meta})

    total = b_result.modified_count + f_result.modified_count + u_result.modified_count
    await _audit('batch', batch_id, 'undo', user['id'], {
        'project_id': sample['project_id'],
        'buildings_archived': b_result.modified_count,
        'floors_archived': f_result.modified_count,
        'units_archived': u_result.modified_count,
    })
    logger.info(f"[BATCH-UNDO] batch_id={batch_id} by={user['id']} buildings={b_result.modified_count} floors={f_result.modified_count} units={u_result.modified_count}")
    return {
        'success': True, 'batch_id': batch_id,
        'archived_count': total,
        'buildings': b_result.modified_count,
        'floors': f_result.modified_count,
        'units': u_result.modified_count,
    }


@router.get("/projects/{project_id}/archived")
async def get_archived_entities(project_id: str, entity_type: Optional[str] = None, search: Optional[str] = None, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()
    await _check_project_access(user, project_id)

    result = {'buildings': [], 'floors': [], 'units': []}

    if not entity_type or entity_type == 'building':
        q = {'project_id': project_id, 'archived': True}
        if search:
            q['name'] = {'$regex': search, '$options': 'i'}
        buildings = await db.buildings.find(q, {'_id': 0}).to_list(1000)
        for b in buildings:
            deps = await _get_dependency_counts(db, 'building', b['id'])
            b['dependencies'] = deps
        result['buildings'] = buildings

    if not entity_type or entity_type == 'floor':
        q = {'project_id': project_id, 'archived': True}
        if search:
            q['name'] = {'$regex': search, '$options': 'i'}
        floors = await db.floors.find(q, {'_id': 0}).to_list(10000)
        for f in floors:
            deps = await _get_dependency_counts(db, 'floor', f['id'])
            f['dependencies'] = deps
        result['floors'] = floors

    if not entity_type or entity_type == 'unit':
        q = {'project_id': project_id, 'archived': True}
        if search:
            q['$or'] = [
                {'unit_no': {'$regex': search, '$options': 'i'}},
                {'display_label': {'$regex': search, '$options': 'i'}},
            ]
        units = await db.units.find(q, {'_id': 0}).to_list(100000)
        for u in units:
            deps = await _get_dependency_counts(db, 'unit', u['id'])
            u['dependencies'] = deps
        result['units'] = units

    return result


@router.delete("/admin/entities/{entity_type}/{entity_id}/permanent")
async def hard_delete_entity(entity_type: str, entity_id: str, body: HardDeleteRequest, user: dict = Depends(require_roles('project_manager'))):
    db = get_db()

    if user.get('platform_role') != 'super_admin':
        raise HTTPException(status_code=403, detail='רק סופר אדמין יכול למחוק לצמיתות')

    from contractor_ops.stepup_service import has_valid_grant as stepup_has_valid_grant
    if not await stepup_has_valid_grant(user['id'], 'hard_delete'):
        raise HTTPException(status_code=403, detail='נדרש אימות Step-up לפני מחיקה לצמיתות')

    if entity_type not in ('building', 'floor', 'unit'):
        raise HTTPException(status_code=400, detail='סוג ישות לא תקין')

    collection_map = {'building': 'buildings', 'floor': 'floors', 'unit': 'units'}
    collection = db[collection_map[entity_type]]
    entity = await collection.find_one({'id': entity_id, 'archived': True}, {'_id': 0})
    if not entity:
        raise HTTPException(status_code=404, detail='ישות לא נמצאה בארכיון')

    entity_name = entity.get('name') or entity.get('unit_no') or entity.get('display_label') or entity_id
    if body.typed_confirmation.strip() != entity_name.strip():
        raise HTTPException(status_code=422, detail=f'אישור הקלדה לא תואם. הקלד: "{entity_name}"')

    deps = await _get_dependency_counts(db, entity_type, entity_id)
    if deps.get('tasks', 0) > 0:
        raise HTTPException(status_code=409, detail=f'לא ניתן למחוק לצמיתות - ישנן {deps["tasks"]} משימות/ליקויים מקושרים. אפשר רק ארכוב.')

    archived_at_str = entity.get('archived_at', '')
    if not archived_at_str:
        raise HTTPException(status_code=409, detail=f'לא ניתן למחוק - חסר תאריך ארכוב. יש לשחזר ולארכב מחדש.')
    try:
        archived_dt = datetime.fromisoformat(archived_at_str.replace('Z', '+00:00')) if isinstance(archived_at_str, str) else archived_at_str
        now = datetime.now(timezone.utc)
        days_in_archive = (now - archived_dt).days
        if days_in_archive < HARD_DELETE_RETENTION_DAYS:
            remaining = HARD_DELETE_RETENTION_DAYS - days_in_archive
            raise HTTPException(status_code=409, detail=f'מחיקה לצמיתות אפשרית רק אחרי {HARD_DELETE_RETENTION_DAYS} ימים בארכיון. נותרו {remaining} ימים.')
    except (ValueError, TypeError):
        raise HTTPException(status_code=409, detail=f'לא ניתן למחוק - תאריך ארכוב לא תקין. יש לשחזר ולארכב מחדש.')

    if entity_type == 'building':
        await db.units.delete_many({'building_id': entity_id, 'archived': True})
        await db.floors.delete_many({'building_id': entity_id, 'archived': True})
    elif entity_type == 'floor':
        await db.units.delete_many({'floor_id': entity_id, 'archived': True})

    await collection.delete_one({'id': entity_id})

    await _audit(entity_type, entity_id, 'hard_delete', user['id'], {
        'entity_name': entity_name,
        'dependencies': deps,
    })
    logger.info(f"[HARD-DELETE] type={entity_type} id={entity_id} name={entity_name} by={user['id']}")
    return {'success': True, 'deleted': entity_id, 'entity_type': entity_type}
