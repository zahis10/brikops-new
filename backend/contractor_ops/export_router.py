import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from contractor_ops.router import get_db, get_current_user, _check_project_read_access
from models import CATEGORIES
from services.object_storage import generate_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

CATEGORY_LABEL = {c['value']: c['label'] for c in CATEGORIES}

STATUS_LABEL = {
    'open': 'פתוח',
    'assigned': 'שויך',
    'in_progress': 'בביצוע',
    'waiting_verify': 'ממתין לאימות',
    'pending_contractor_proof': 'ממתין להוכחת קבלן',
    'pending_manager_approval': 'ממתין לאישור מנהל',
    'returned_to_contractor': 'הוחזר לקבלן',
    'closed': 'סגור',
    'reopened': 'נפתח מחדש',
}

OPEN_STATUSES_APARTMENT = {'open', 'assigned', 'reopened'}
OPEN_STATUSES_BUILDING = {'open', 'assigned', 'reopened', 'in_progress',
                          'pending_contractor_proof', 'pending_manager_approval',
                          'returned_to_contractor', 'waiting_verify'}
IN_PROGRESS_STATUSES = {'in_progress', 'pending_contractor_proof',
                        'pending_manager_approval', 'returned_to_contractor',
                        'waiting_verify'}
CLOSED_STATUSES = {'closed'}
BLOCKING_STATUSES = {'open', 'in_progress'}


class ExportFilters(BaseModel):
    status: Optional[str] = 'all'
    category: Optional[str] = 'all'
    company: Optional[str] = 'all'
    assignee: Optional[str] = 'all'
    created_by: Optional[str] = 'all'
    floor: Optional[str] = 'all'
    unit: Optional[str] = 'all'
    search: Optional[str] = ''


class ExportRequest(BaseModel):
    scope: str
    unit_id: Optional[str] = None
    building_id: Optional[str] = None
    filters: ExportFilters = ExportFilters()


def _apply_filters(tasks, filters: ExportFilters, scope: str = 'unit'):
    result = []
    search_lower = (filters.search or '').strip().lower()
    open_statuses = OPEN_STATUSES_BUILDING if scope == 'building' else OPEN_STATUSES_APARTMENT
    for t in tasks:
        s = t.get('status', 'open')
        if filters.status and filters.status != 'all':
            if filters.status == 'open' and s not in open_statuses:
                continue
            elif filters.status == 'in_progress' and s not in IN_PROGRESS_STATUSES:
                continue
            elif filters.status == 'closed' and s not in CLOSED_STATUSES:
                continue
            elif filters.status == 'blocking' and s not in BLOCKING_STATUSES:
                continue
        if filters.category and filters.category != 'all':
            if t.get('category') != filters.category:
                continue
        if filters.company and filters.company != 'all':
            if t.get('company_id') != filters.company:
                continue
        if filters.assignee and filters.assignee != 'all':
            if t.get('assignee_id') != filters.assignee:
                continue
        if filters.created_by and filters.created_by != 'all':
            if t.get('created_by') != filters.created_by:
                continue
        if filters.floor and filters.floor != 'all':
            if t.get('floor_id') != filters.floor:
                continue
        if filters.unit and filters.unit != 'all':
            if t.get('unit_id') != filters.unit:
                continue
        if search_lower:
            title = (t.get('title') or '').lower()
            desc = (t.get('description') or '').lower()
            if search_lower not in title and search_lower not in desc:
                continue
        result.append(t)
    return result


def _resolve_image_links(task):
    links = []
    for att in (task.get('attachments') or []):
        url = att.get('file_url') or att.get('url') or ''
        if url:
            resolved = generate_url(url) if url.startswith('s3://') else url
            links.append(resolved)
    proof_urls = task.get('proof_urls') or []
    for url in proof_urls:
        if isinstance(url, str) and url:
            resolved = generate_url(url) if url.startswith('s3://') else url
            links.append(resolved)
    return links


def _format_datetime(dt_str):
    if not dt_str:
        return ''
    try:
        if isinstance(dt_str, datetime):
            return dt_str.strftime('%Y-%m-%d %H:%M')
        dt = datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return str(dt_str)[:16] if dt_str else ''


async def _build_lookup_maps(db, tasks):
    user_ids = set()
    company_ids = set()
    for t in tasks:
        if t.get('assignee_id'):
            user_ids.add(t['assignee_id'])
        if t.get('created_by'):
            user_ids.add(t['created_by'])
        if t.get('company_id'):
            company_ids.add(t['company_id'])

    user_map = {}
    if user_ids:
        users = await db.users.find({'id': {'$in': list(user_ids)}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(1000)
        user_map = {u['id']: u.get('name', '') for u in users}

    company_map = {}
    if company_ids:
        companies = await db.companies.find({'id': {'$in': list(company_ids)}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(1000)
        company_map = {c['id']: c.get('name', '') for c in companies}

    return user_map, company_map


async def _build_location_maps(db, tasks):
    floor_ids = set()
    unit_ids = set()
    building_ids = set()
    for t in tasks:
        if t.get('floor_id'):
            floor_ids.add(t['floor_id'])
        if t.get('unit_id'):
            unit_ids.add(t['unit_id'])
        if t.get('building_id'):
            building_ids.add(t['building_id'])

    floor_map = {}
    if floor_ids:
        floors = await db.floors.find({'id': {'$in': list(floor_ids)}}, {'_id': 0, 'id': 1, 'name': 1, 'display_label': 1}).to_list(1000)
        floor_map = {f['id']: f.get('display_label') or f.get('name', '') for f in floors}

    unit_map = {}
    if unit_ids:
        units = await db.units.find({'id': {'$in': list(unit_ids)}}, {'_id': 0, 'id': 1, 'unit_no': 1, 'display_label': 1}).to_list(100000)
        unit_map = {u['id']: u.get('display_label') or u.get('unit_no', '') for u in units}

    building_map = {}
    if building_ids:
        buildings = await db.buildings.find({'id': {'$in': list(building_ids)}}, {'_id': 0, 'id': 1, 'name': 1}).to_list(100)
        building_map = {b['id']: b.get('name', '') for b in buildings}

    return floor_map, unit_map, building_map


def _generate_excel(tasks, project_name, user_map, company_map, floor_map, unit_map, building_map):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = 'ליקויים'
    ws.sheet_view.rightToLeft = True

    headers = [
        'מספר ליקוי', 'פרויקט', 'בניין', 'קומה', 'דירה', 'תחום',
        'כותרת', 'תיאור', 'סטטוס', 'חברה/קבלן', 'תאריך יצירה',
        'תאריך עדכון', 'חוסם מסירה', 'מספר תמונות', 'קישורי תמונות'
    ]

    header_font = Font(name='Arial', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill(start_color='F59E0B', end_color='F59E0B', fill_type='solid')
    header_align = Alignment(horizontal='right', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin', color='D1D5DB'),
        right=Side(style='thin', color='D1D5DB'),
        top=Side(style='thin', color='D1D5DB'),
        bottom=Side(style='thin', color='D1D5DB'),
    )

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    cell_align = Alignment(horizontal='right', vertical='top', wrap_text=True)
    cell_font = Font(name='Arial', size=10)

    for row_idx, task in enumerate(tasks, 2):
        status = task.get('status', 'open')
        is_blocking = status in BLOCKING_STATUSES

        image_links = _resolve_image_links(task)
        image_count = task.get('attachments_count', 0) or len(image_links)
        links_text = '\n'.join(image_links) if image_links else ''

        row_data = [
            task.get('display_number') or task.get('short_ref', ''),
            project_name,
            building_map.get(task.get('building_id', ''), ''),
            floor_map.get(task.get('floor_id', ''), ''),
            unit_map.get(task.get('unit_id', ''), ''),
            CATEGORY_LABEL.get(task.get('category', ''), task.get('category', '')),
            task.get('title', ''),
            task.get('description', ''),
            STATUS_LABEL.get(status, status),
            company_map.get(task.get('company_id', ''), ''),
            _format_datetime(task.get('created_at')),
            _format_datetime(task.get('updated_at')),
            'כן' if is_blocking else 'לא',
            image_count,
            links_text,
        ]

        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = cell_font
            cell.alignment = cell_align
            cell.border = thin_border

        if image_links:
            link_cell = ws.cell(row=row_idx, column=15)
            link_font = Font(name='Arial', size=10, color='0563C1', underline='single')
            if len(image_links) == 1:
                link_cell.hyperlink = image_links[0]
                link_cell.font = link_font
            else:
                for img_idx, img_url in enumerate(image_links):
                    col = 15 + img_idx
                    c = ws.cell(row=row_idx, column=col, value=img_url)
                    c.hyperlink = img_url
                    c.font = link_font
                    c.alignment = cell_align
                    c.border = thin_border
                    if img_idx == 0:
                        if row_idx == 2:
                            ws.cell(row=1, column=col, value='קישורי תמונות').font = header_font
                            ws.cell(row=1, column=col).fill = header_fill
                            ws.cell(row=1, column=col).alignment = header_align
                            ws.cell(row=1, column=col).border = thin_border
                    elif row_idx == 2 or not ws.cell(row=1, column=col).value:
                        hdr = ws.cell(row=1, column=col, value=f'תמונה {img_idx + 1}')
                        hdr.font = header_font
                        hdr.fill = header_fill
                        hdr.alignment = header_align
                        hdr.border = thin_border

    col_widths = [12, 15, 12, 10, 10, 14, 25, 30, 14, 18, 16, 16, 12, 10, 40]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(tasks) + 1}"

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


@router.post("/defects/export")
async def export_defects(req: ExportRequest, user: dict = Depends(get_current_user)):
    db = get_db()

    if req.scope == 'unit':
        if not req.unit_id:
            raise HTTPException(status_code=400, detail='unit_id required for unit scope')
        unit = await db.units.find_one({'id': req.unit_id}, {'_id': 0})
        if not unit:
            raise HTTPException(status_code=404, detail='Unit not found')
        building = await db.buildings.find_one({'id': unit.get('building_id')}, {'_id': 0}) if unit.get('building_id') else None
        project_id = unit.get('project_id') or (building.get('project_id') if building else None)
        if not project_id:
            raise HTTPException(status_code=400, detail='Could not determine project')
        await _check_project_read_access(user, project_id)
        project = await db.projects.find_one({'id': project_id}, {'_id': 0})

        tasks = await db.tasks.find({'unit_id': req.unit_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(100000)
        scope_label = unit.get('display_label') or unit.get('unit_no', '')
        filename_scope = f"apartment_{scope_label}"

    elif req.scope == 'building':
        if not req.building_id:
            raise HTTPException(status_code=400, detail='building_id required for building scope')
        building = await db.buildings.find_one({'id': req.building_id, 'archived': {'$ne': True}}, {'_id': 0})
        if not building:
            raise HTTPException(status_code=404, detail='Building not found')
        project_id = building['project_id']
        await _check_project_read_access(user, project_id)
        project = await db.projects.find_one({'id': project_id}, {'_id': 0})

        tasks = await db.tasks.find({'building_id': req.building_id, 'archived': {'$ne': True}}, {'_id': 0}).to_list(100000)
        scope_label = building.get('name', '')
        filename_scope = f"building_{scope_label}"

    else:
        raise HTTPException(status_code=400, detail='Invalid scope. Use "unit" or "building".')

    project_name = project.get('name', '') if project else ''

    filtered = _apply_filters(tasks, req.filters, scope=req.scope)
    filtered.sort(key=lambda t: t.get('created_at', ''), reverse=True)

    user_map, company_map = await _build_lookup_maps(db, filtered)
    floor_map, unit_map, building_map_loc = await _build_location_maps(db, filtered)

    excel_bytes = _generate_excel(
        filtered, project_name, user_map, company_map,
        floor_map, unit_map, building_map_loc
    )

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    safe_scope = filename_scope.replace(' ', '_').replace('/', '_')
    filename = f"defects_{safe_scope}_{today}.xlsx"

    from urllib.parse import quote
    ascii_filename = f"defects_{req.scope}_{today}.xlsx"
    encoded_filename = quote(filename)
    disposition = f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"

    logger.info(f"[EXPORT] user={user.get('id')} scope={req.scope} tasks={len(filtered)} filename={filename}")

    return StreamingResponse(
        excel_bytes,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': disposition}
    )
