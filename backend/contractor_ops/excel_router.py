import uuid

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from contractor_ops.router import get_db, get_current_user, require_roles, _check_project_access, _check_structure_admin, _now, _audit
from contractor_ops.upload_safety import validate_upload, ALLOWED_IMPORT_EXTENSIONS, ALLOWED_IMPORT_TYPES

router = APIRouter(prefix="/api")


# ── Excel import ──
@router.get("/projects/{project_id}/excel-template")
async def download_excel_template(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    await _check_structure_admin(user, project_id)
    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['building_name', 'building_code', 'floor_number', 'unit_no', 'unit_type'])
    writer.writerow(['בניין A', 'A', '1', '101', 'apartment'])
    writer.writerow(['בניין A', 'A', '1', '102', 'apartment'])
    writer.writerow(['בניין A', 'A', '2', '201', 'apartment'])
    from starlette.responses import StreamingResponse
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename=template_{project_id}.csv'}
    )


@router.post("/projects/{project_id}/excel-import")
async def import_excel(project_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    db = get_db()
    await _check_structure_admin(user, project_id)
    validate_upload(file, ALLOWED_IMPORT_EXTENSIONS, ALLOWED_IMPORT_TYPES)
    import io, csv
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except:
        text = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(text))
    results = {'created': [], 'skipped': [], 'errors': []}
    row_num = 0
    ts = _now()
    for row in reader:
        row_num += 1
        bname = row.get('building_name', '').strip()
        bcode = row.get('building_code', '').strip()
        floor_num_str = row.get('floor_number', '').strip()
        unit_no = row.get('unit_no', '').strip()
        unit_type = row.get('unit_type', 'apartment').strip()
        if not bname:
            results['errors'].append({'row': row_num, 'error': 'missing building_name'})
            continue
        if not floor_num_str:
            results['errors'].append({'row': row_num, 'error': 'missing floor_number'})
            continue
        try:
            floor_num = int(floor_num_str)
        except ValueError:
            results['errors'].append({'row': row_num, 'error': 'invalid floor_number'})
            continue
        building = await db.buildings.find_one({'project_id': project_id, 'name': bname})
        if not building:
            bid = str(uuid.uuid4())
            building = {'id': bid, 'project_id': project_id, 'name': bname, 'code': bcode or None, 'floors_count': 0, 'created_at': ts}
            await db.buildings.insert_one(building)
        floor = await db.floors.find_one({'building_id': building['id'], 'floor_number': floor_num})
        if not floor:
            fid = str(uuid.uuid4())
            floor = {'id': fid, 'building_id': building['id'], 'project_id': project_id, 'name': f'קומה {floor_num}', 'floor_number': floor_num, 'created_at': ts}
            await db.floors.insert_one(floor)
        if unit_no:
            existing_unit = await db.units.find_one({'floor_id': floor['id'], 'unit_no': unit_no})
            if existing_unit:
                results['skipped'].append({'row': row_num, 'unit_no': unit_no, 'reason': 'duplicate'})
                continue
            uid = str(uuid.uuid4())
            unit_doc = {'id': uid, 'floor_id': floor['id'], 'building_id': building['id'], 'project_id': project_id, 'unit_no': unit_no, 'unit_type': unit_type if unit_type in ('apartment','commercial','parking','storage') else 'apartment', 'status': 'available', 'created_at': ts}
            await db.units.insert_one(unit_doc)
            results['created'].append({'row': row_num, 'unit_no': unit_no})
        else:
            results['created'].append({'row': row_num, 'note': 'floor only'})
    await _audit('project', project_id, 'excel_import', user['id'], {'created': len(results['created']), 'skipped': len(results['skipped']), 'errors': len(results['errors'])})
    return {'created_count': len(results['created']), 'skipped_count': len(results['skipped']), 'error_count': len(results['errors']), 'details': results}


@router.post("/projects/{project_id}/migrate-sort-index")
async def migrate_sort_index(project_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')
    await _check_structure_admin(user, project_id)
    floors_updated = 0
    units_updated = 0
    buildings = await db.buildings.find({'project_id': project_id}, {'_id': 0}).to_list(1000)
    for building in buildings:
        floors = await db.floors.find({'building_id': building['id']}, {'_id': 0}).sort('floor_number', 1).to_list(1000)
        for idx, f in enumerate(floors):
            si = f['floor_number'] * 1000
            updates = {'sort_index': si}
            if not f.get('display_label'):
                updates['display_label'] = f['name']
            await db.floors.update_one({'id': f['id']}, {'$set': updates})
            floors_updated += 1
            units = await db.units.find({'floor_id': f['id']}, {'_id': 0}).to_list(10000)
            units_sorted = sorted(units, key=lambda u: u.get('unit_no', ''))
            for uidx, u in enumerate(units_sorted):
                u_updates = {'sort_index': (uidx + 1) * 10}
                if not u.get('display_label'):
                    u_updates['display_label'] = u['unit_no']
                await db.units.update_one({'id': u['id']}, {'$set': u_updates})
                units_updated += 1
    await _audit('project', project_id, 'migrate_sort_index', user['id'], {'floors_updated': floors_updated, 'units_updated': units_updated})
    return {'success': True, 'floors_updated': floors_updated, 'units_updated': units_updated}
