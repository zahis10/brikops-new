import re
from copy import deepcopy
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from contractor_ops.router import (
    _audit,
    _check_project_read_access,
    _get_project_role,
    get_current_user,
    get_db,
)
from contractor_ops.spare_tiles import default_spare_settings, validate_spare_settings


router = APIRouter(prefix='/api')
WRITE_ROLES = ('project_manager', 'owner')


async def _project_or_404(db, project_id):
    project = await db.projects.find_one({'id': project_id}, {'_id': 0})
    if not project:
        raise HTTPException(status_code=404, detail='הפרויקט לא נמצא')
    return project


async def _require_write(user, project_id):
    role = await _get_project_role(user, project_id)
    if role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail='רק מנהל הפרויקט יכול לשנות הגדרות ושיוך ריצוף ספייר')


async def _can_write(user, project_id):
    return await _get_project_role(user, project_id) in WRITE_ROLES


async def _settings_with_counts(db, project_id, settings):
    result = deepcopy(settings)
    profile_ids = {profile['id'] for profile in result.get('profiles', [])}
    counts = {profile_id: 0 for profile_id in profile_ids}
    unassigned = 0
    units = await db.units.find(
        {'project_id': project_id, 'archived': {'$ne': True}},
        {'_id': 0, 'spare_profile_id': 1},
    ).to_list(100000)
    for unit in units:
        profile_id = unit.get('spare_profile_id')
        if profile_id in counts:
            counts[profile_id] += 1
        else:
            unassigned += 1
    for profile in result.get('profiles', []):
        profile['assigned_units'] = counts[profile['id']]
    result['unassigned_units'] = unassigned
    return result


@router.get('/projects/{project_id}/spare-settings')
async def get_spare_settings(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    project = await _project_or_404(db, project_id)
    await _check_project_read_access(user, project_id)
    settings = project.get('spare_settings') or default_spare_settings()
    response = await _settings_with_counts(db, project_id, settings)
    response['can_write'] = await _can_write(user, project_id)
    return response


@router.put('/projects/{project_id}/spare-settings')
async def put_spare_settings(project_id: str, body: dict, user: dict = Depends(get_current_user)):
    db = get_db()
    await _project_or_404(db, project_id)
    await _require_write(user, project_id)
    expected_updated_at = body.get('updated_at') if isinstance(body, dict) else None
    settings = validate_spare_settings(body)
    project = await _project_or_404(db, project_id)
    stored_settings = project.get('spare_settings')
    had_settings_field = 'spare_settings' in project
    has_stored_settings = isinstance(stored_settings, dict)
    current_updated_at = stored_settings.get('updated_at') if has_stored_settings else None
    if has_stored_settings and expected_updated_at != current_updated_at:
        raise HTTPException(
            status_code=409,
            detail='הגדרות ריצוף הספייר השתנו, יש לטעון מחדש',
        )
    old_profile_ids = {
        profile.get('id')
        for profile in (stored_settings or {}).get('profiles', [])
        if isinstance(profile, dict) and profile.get('id')
    }
    retained_ids = {profile['id'] for profile in settings['profiles']}
    deleted_ids = old_profile_ids - retained_ids
    if deleted_ids:
        assigned_count = await db.units.count_documents({
            'project_id': project_id,
            'archived': {'$ne': True},
            'spare_profile_id': {'$in': list(deleted_ids)},
        })
        if assigned_count:
            raise HTTPException(
                status_code=409,
                detail=f'יש להסיר תחילה {assigned_count} דירות מהפרופיל',
            )

    settings['updated_at'] = datetime.now(timezone.utc).isoformat()
    settings['updated_by'] = user['id']
    if has_stored_settings:
        update_filter = {
            'id': project_id,
            'spare_settings.updated_at': current_updated_at,
        }
    else:
        update_filter = {'id': project_id}
        if had_settings_field:
            update_filter['spare_settings'] = stored_settings
        else:
            update_filter['spare_settings'] = {'$exists': False}
    update_result = await db.projects.update_one(
        update_filter,
        {'$set': {'spare_settings': settings}},
    )
    if update_result.modified_count != 1:
        raise HTTPException(
            status_code=409,
            detail='הגדרות ריצוף הספייר השתנו, יש לטעון מחדש',
        )
    await _audit('project', project_id, 'spare_settings_updated', user['id'], {
        'categories_count': len(settings['categories']),
        'profiles_count': len(settings['profiles']),
    })
    response = await _settings_with_counts(db, project_id, settings)
    response['can_write'] = True
    return response


def _natural_name_key(document):
    return [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r'(\d+)', document.get('name', ''))
    ]


@router.get('/projects/{project_id}/spare-assignments')
async def get_spare_assignments(
    project_id: str,
    building_id: str = Query(default=None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _project_or_404(db, project_id)
    await _check_project_read_access(user, project_id)
    buildings = await db.buildings.find(
        {'project_id': project_id, 'archived': {'$ne': True}},
        {'_id': 0},
    ).to_list(1000)
    buildings.sort(key=lambda item: (item.get('sort_index', 0), _natural_name_key(item)))
    building_options = [{'id': item['id'], 'name': item.get('name', '')} for item in buildings]

    if not building_id:
        return {'buildings': building_options, 'floors': []}
    if not any(item['id'] == building_id for item in buildings):
        raise HTTPException(status_code=404, detail='הבניין לא נמצא בפרויקט')

    floors = await db.floors.find(
        {
            'project_id': project_id,
            'building_id': building_id,
            'archived': {'$ne': True},
        },
        {'_id': 0},
    ).to_list(10000)
    floors.sort(key=lambda item: item.get('sort_index', item.get('floor_number', 0) * 1000))
    floor_ids = [floor['id'] for floor in floors]
    units = []
    if floor_ids:
        units = await db.units.find(
            {
                'project_id': project_id,
                'floor_id': {'$in': floor_ids},
                'archived': {'$ne': True},
            },
            {'_id': 0},
        ).to_list(100000)
    units_by_floor = {floor_id: [] for floor_id in floor_ids}
    for unit in units:
        units_by_floor[unit['floor_id']].append(unit)
    for floor_units in units_by_floor.values():
        floor_units.sort(key=lambda item: item.get('sort_index', 0))

    return {
        'buildings': building_options,
        'floors': [
            {
                'id': floor['id'],
                'name': floor.get('name', ''),
                'sort': floor.get('sort_index', floor.get('floor_number', 0) * 1000),
                'units': [
                    {
                        'id': unit['id'],
                        'unit_no': unit.get('unit_no', ''),
                        'display_label': unit.get('display_label'),
                        'spare_profile_id': unit.get('spare_profile_id'),
                    }
                    for unit in units_by_floor[floor['id']]
                ],
            }
            for floor in floors
        ],
    }


def _normalize_unit_ids(value, field_name):
    if not isinstance(value, list):
        raise HTTPException(status_code=422, detail=f'{field_name} חייב להיות מערך')
    normalized = []
    for unit_id in value:
        if not isinstance(unit_id, str) or not unit_id.strip():
            raise HTTPException(status_code=422, detail='מזהה דירה אינו חוקי')
        normalized.append(unit_id.strip())
    if len(set(normalized)) != len(normalized):
        raise HTTPException(status_code=422, detail='אין לשלוח מזהי דירות כפולים')
    return normalized


@router.patch('/projects/{project_id}/spare-profiles/{profile_id}/units')
async def patch_spare_profile_units(
    project_id: str,
    profile_id: str,
    body: dict,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _project_or_404(db, project_id)
    await _require_write(user, project_id)
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail='הבקשה חייבת להיות אובייקט')
    add_ids = _normalize_unit_ids(body.get('add'), 'add')
    remove_ids = _normalize_unit_ids(body.get('remove'), 'remove')
    if len(add_ids) + len(remove_ids) > 2000:
        raise HTTPException(status_code=422, detail='ניתן לעדכן עד 2000 דירות בבקשה')
    overlap = set(add_ids) & set(remove_ids)
    if overlap:
        raise HTTPException(status_code=422, detail='לא ניתן להוסיף ולהסיר אותה דירה')

    project = await _project_or_404(db, project_id)
    profiles = (project.get('spare_settings') or {}).get('profiles', [])
    if not any(isinstance(profile, dict) and profile.get('id') == profile_id for profile in profiles):
        raise HTTPException(status_code=404, detail='פרופיל ריצוף ספייר לא נמצא')

    requested_ids = add_ids + remove_ids
    units = []
    if requested_ids:
        units = await db.units.find(
            {
                'id': {'$in': requested_ids},
                'project_id': project_id,
                'archived': {'$ne': True},
            },
            {'_id': 0, 'id': 1, 'spare_profile_id': 1},
        ).to_list(2000)
    units_by_id = {unit['id']: unit for unit in units}
    offending = [unit_id for unit_id in requested_ids if unit_id not in units_by_id]
    if offending:
        raise HTTPException(
            status_code=422,
            detail=f"מזהי דירות לא חוקיים: {', '.join(offending)}",
        )

    actual_add_ids = [
        unit_id for unit_id in add_ids
        if units_by_id[unit_id].get('spare_profile_id') != profile_id
    ]
    actual_remove_ids = [
        unit_id for unit_id in remove_ids
        if units_by_id[unit_id].get('spare_profile_id') == profile_id
    ]
    added = 0
    removed = 0
    if actual_add_ids:
        add_result = await db.units.update_many(
            {
                'id': {'$in': actual_add_ids},
                'project_id': project_id,
                'archived': {'$ne': True},
                'spare_profile_id': {'$ne': profile_id},
            },
            {'$set': {'spare_profile_id': profile_id}},
        )
        added = add_result.modified_count
    if actual_remove_ids:
        remove_result = await db.units.update_many(
            {
                'id': {'$in': actual_remove_ids},
                'project_id': project_id,
                'archived': {'$ne': True},
                'spare_profile_id': profile_id,
            },
            {'$set': {'spare_profile_id': None}},
        )
        removed = remove_result.modified_count

    result = {'added': added, 'removed': removed}
    await _audit('project', project_id, 'spare_profile_units_updated', user['id'], {
        'profile_id': profile_id,
        **result,
    })
    return result