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


VALID_EXPORT_FORMATS = {'excel', 'pdf'}


class ExportRequest(BaseModel):
    scope: str
    unit_id: Optional[str] = None
    building_id: Optional[str] = None
    filters: ExportFilters = ExportFilters()
    format: Optional[str] = 'excel'


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


MAX_IMAGES_PER_DEFECT = 4
PDF_IMAGE_MAX_WIDTH_CM = 7
PDF_IMAGE_MAX_HEIGHT_CM = 5


ALLOWED_IMAGE_HOSTS = {
    'brikops-prod-files.s3.eu-central-1.amazonaws.com',
    'brikops-prod-files.s3.amazonaws.com',
    's3.eu-central-1.amazonaws.com',
    's3.amazonaws.com',
    'localhost',
}


def _is_safe_image_url(url):
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ''
        if host in ALLOWED_IMAGE_HOSTS:
            return True
        if host.endswith('.amazonaws.com'):
            return True
        return False
    except Exception:
        return False


def _fetch_image_for_pdf(url):
    import requests as http_requests
    from PIL import Image as PILImage
    try:
        fetch_url = url
        if not fetch_url.startswith('http'):
            return None
        if not _is_safe_image_url(fetch_url):
            logger.warning(f'[PDF] Blocked unsafe image URL: {url[:80]}')
            return None
        resp = http_requests.get(fetch_url, timeout=8)
        if resp.status_code != 200:
            logger.warning(f'[PDF] Image fetch failed: {resp.status_code} for {url[:80]}')
            return None
        img = PILImage.open(io.BytesIO(resp.content))
        if img.mode not in ('RGB',):
            img = img.convert('RGB')
        max_px = 800
        if img.width > max_px or img.height > max_px:
            img.thumbnail((max_px, max_px), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=75, optimize=True)
        buf.seek(0)
        return buf
    except Exception as e:
        logger.warning(f'[PDF] Image processing failed: {e} for {url[:80]}')
        return None


def _generate_pdf(tasks, project_name, scope_label, scope_type, user_map, company_map,
                  floor_map, unit_map, building_map, filters_desc=None):
    import os
    import arabic_reshaper
    from bidi.algorithm import get_display
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    fonts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts')
    try:
        pdfmetrics.registerFont(TTFont('Rubik', os.path.join(fonts_dir, 'Rubik-Regular.ttf')))
    except Exception:
        pass

    def heb(text):
        if not text:
            return ''
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)

    AMBER = colors.HexColor('#F59E0B')
    AMBER_LIGHT = colors.HexColor('#FEF3C7')
    AMBER_DARK = colors.HexColor('#B45309')
    SLATE_700 = colors.HexColor('#334155')
    SLATE_500 = colors.HexColor('#64748B')
    SLATE_200 = colors.HexColor('#E2E8F0')
    WHITE = colors.white

    style_title = ParagraphStyle('PDFTitle', fontName='Rubik', fontSize=18,
                                  alignment=TA_CENTER, textColor=SLATE_700, leading=24)
    style_subtitle = ParagraphStyle('PDFSubtitle', fontName='Rubik', fontSize=11,
                                     alignment=TA_CENTER, textColor=SLATE_500, leading=15)
    style_filter = ParagraphStyle('PDFFilter', fontName='Rubik', fontSize=9,
                                   alignment=TA_CENTER, textColor=AMBER_DARK, leading=12)
    style_field_label = ParagraphStyle('PDFFieldLabel', fontName='Rubik', fontSize=9,
                                        alignment=TA_RIGHT, textColor=SLATE_500, leading=12)
    style_field_value = ParagraphStyle('PDFFieldValue', fontName='Rubik', fontSize=10,
                                        alignment=TA_RIGHT, textColor=SLATE_700, leading=13)
    style_defect_title = ParagraphStyle('PDFDefectTitle', fontName='Rubik', fontSize=12,
                                         alignment=TA_RIGHT, textColor=SLATE_700, leading=16)
    style_count = ParagraphStyle('PDFCount', fontName='Rubik', fontSize=9,
                                  alignment=TA_CENTER, textColor=SLATE_500, leading=12)

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4,
                            leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    elements = []

    scope_heb = heb('בניין') if scope_type == 'building' else heb('דירה')
    elements.append(Paragraph(heb('דו״ח ליקויים'), style_title))
    elements.append(Spacer(1, 4 * mm))

    info_line = f'{project_name} · {scope_heb}: {scope_label}'
    elements.append(Paragraph(heb(info_line), style_subtitle))

    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    elements.append(Paragraph(heb(f'תאריך: {today_str}'), style_subtitle))
    elements.append(Spacer(1, 3 * mm))

    if filters_desc:
        elements.append(Paragraph(heb(f'סינון: {filters_desc}'), style_filter))
        elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(heb(f'סה״כ ליקויים: {len(tasks)}'), style_count))
    elements.append(Spacer(1, 6 * mm))

    for idx, task in enumerate(tasks):
        status = task.get('status', 'open')
        is_blocking = status in BLOCKING_STATUSES

        title_text = task.get('title', '')
        number = task.get('display_number') or task.get('short_ref', '')
        prefix = f'#{number} ' if number else ''
        elements.append(Paragraph(heb(f'{prefix}{title_text}'), style_defect_title))
        elements.append(Spacer(1, 2 * mm))

        fields = [
            ('תחום', CATEGORY_LABEL.get(task.get('category', ''), task.get('category', ''))),
            ('סטטוס', STATUS_LABEL.get(status, status)),
            ('בניין', building_map.get(task.get('building_id', ''), '')),
            ('קומה', floor_map.get(task.get('floor_id', ''), '')),
            ('דירה', unit_map.get(task.get('unit_id', ''), '')),
            ('חברה/קבלן', company_map.get(task.get('company_id', ''), '')),
            ('תאריך יצירה', _format_datetime(task.get('created_at'))),
            ('תאריך עדכון', _format_datetime(task.get('updated_at'))),
            ('חוסם מסירה', 'כן' if is_blocking else 'לא'),
        ]

        desc = task.get('description', '')
        if desc:
            fields.insert(1, ('תיאור', desc))

        field_rows = []
        for label, value in fields:
            if not value:
                continue
            field_rows.append([
                Paragraph(heb(str(value)), style_field_value),
                Paragraph(heb(label), style_field_label),
            ])

        if field_rows:
            avail_w = doc.width
            tbl = Table(field_rows, colWidths=[avail_w * 0.7, avail_w * 0.3])
            tbl.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(tbl)

        image_links = _resolve_image_links(task)
        rendered_images = 0
        if image_links:
            elements.append(Spacer(1, 2 * mm))
            for img_url in image_links[:MAX_IMAGES_PER_DEFECT]:
                img_buf = _fetch_image_for_pdf(img_url)
                if img_buf:
                    try:
                        from PIL import Image as PILImage
                        pil_img = PILImage.open(io.BytesIO(img_buf.getvalue()))
                        iw, ih = pil_img.size
                        max_w = PDF_IMAGE_MAX_WIDTH_CM * cm
                        max_h = PDF_IMAGE_MAX_HEIGHT_CM * cm
                        scale = min(max_w / iw, max_h / ih, 1.0)
                        draw_w = iw * scale
                        draw_h = ih * scale
                        img_buf.seek(0)
                        rl_img = RLImage(img_buf, width=draw_w, height=draw_h)
                        rl_img.hAlign = 'RIGHT'
                        elements.append(rl_img)
                        elements.append(Spacer(1, 2 * mm))
                        rendered_images += 1
                    except Exception as e:
                        logger.warning(f'[PDF] Image render failed: {e}')
            skipped = len(image_links) - min(len(image_links), MAX_IMAGES_PER_DEFECT)
            if skipped > 0 or (len(image_links) > 0 and rendered_images < min(len(image_links), MAX_IMAGES_PER_DEFECT)):
                note_count = len(image_links) - rendered_images
                if note_count > 0:
                    elements.append(Paragraph(
                        heb(f'({note_count} תמונות נוספות לא מוצגות)'), style_count))

        sep_tbl = Table([['']], colWidths=[doc.width])
        sep_tbl.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(Spacer(1, 3 * mm))
        elements.append(sep_tbl)
        elements.append(Spacer(1, 4 * mm))

    doc.build(elements)
    output.seek(0)
    return output


def _build_filters_description(filters: ExportFilters):
    parts = []
    if filters.status and filters.status != 'all':
        status_labels = {'open': 'פתוחים', 'closed': 'סגורים', 'blocking': 'חוסמי מסירה', 'in_progress': 'בטיפול'}
        parts.append(f'סטטוס: {status_labels.get(filters.status, filters.status)}')
    if filters.category and filters.category != 'all':
        parts.append(f'תחום: {CATEGORY_LABEL.get(filters.category, filters.category)}')
    if filters.search:
        parts.append(f'חיפוש: {filters.search}')
    if filters.company and filters.company != 'all':
        parts.append('חברה: מסוננת')
    if filters.assignee and filters.assignee != 'all':
        parts.append('אחראי: מסונן')
    if filters.floor and filters.floor != 'all':
        parts.append('קומה: מסוננת')
    if filters.unit and filters.unit != 'all':
        parts.append('דירה: מסוננת')
    return ' · '.join(parts) if parts else None


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
    def _sort_key(t):
        v = t.get('created_at', '')
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)
    filtered.sort(key=_sort_key, reverse=True)

    user_map, company_map = await _build_lookup_maps(db, filtered)
    floor_map, unit_map, building_map_loc = await _build_location_maps(db, filtered)

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    safe_scope = filename_scope.replace(' ', '_').replace('/', '_')
    from urllib.parse import quote

    export_format = (req.format or 'excel').lower()
    if export_format not in VALID_EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f'Invalid format. Use "excel" or "pdf".')

    if export_format == 'pdf':
        filters_desc = _build_filters_description(req.filters)
        pdf_bytes = _generate_pdf(
            filtered, project_name, scope_label, req.scope,
            user_map, company_map, floor_map, unit_map, building_map_loc,
            filters_desc=filters_desc
        )
        filename = f"defects_{safe_scope}_{today}.pdf"
        ascii_filename = f"defects_{req.scope}_{today}.pdf"
        encoded_filename = quote(filename)
        disposition = f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"
        logger.info(f"[EXPORT-PDF] user={user.get('id')} scope={req.scope} tasks={len(filtered)} filename={filename}")
        return StreamingResponse(
            pdf_bytes,
            media_type='application/pdf',
            headers={'Content-Disposition': disposition}
        )

    excel_bytes = _generate_excel(
        filtered, project_name, user_map, company_map,
        floor_map, unit_map, building_map_loc
    )

    filename = f"defects_{safe_scope}_{today}.xlsx"
    ascii_filename = f"defects_{req.scope}_{today}.xlsx"
    encoded_filename = quote(filename)
    disposition = f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"

    logger.info(f"[EXPORT] user={user.get('id')} scope={req.scope} tasks={len(filtered)} filename={filename}")

    return StreamingResponse(
        excel_bytes,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': disposition}
    )
