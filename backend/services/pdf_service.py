import os
import io
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    Table, TableStyle, PageBreak, Image, KeepTogether
)
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from bidi.algorithm import get_display
import arabic_reshaper
from models import CATEGORIES

logger = logging.getLogger(__name__)

GOLD = colors.HexColor('#c8a951')
GOLD_DARK = colors.HexColor('#b8962e')
GOLD_LIGHT = colors.HexColor('#f5ecd3')
DARK_TEXT = colors.HexColor('#1e293b')
GRAY_TEXT = colors.HexColor('#475569')
LIGHT_GRAY = colors.HexColor('#f8f9fa')
BORDER_COLOR = colors.HexColor('#d1d5db')
WHITE = colors.white
BLACK = colors.HexColor('#111827')

CATEGORY_MAP = {c['value']: c for c in CATEGORIES}

_fonts_registered = False


def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    try:
        pdfmetrics.registerFont(TTFont('Rubik', '/home/runner/workspace/backend/fonts/Rubik-Regular.ttf'))
    except Exception as e:
        logger.warning(f'Could not register Rubik font: {e}')
    try:
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
    except Exception as e:
        logger.warning(f'Could not register DejaVu-Bold font: {e}')
    try:
        pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
    except Exception as e:
        logger.warning(f'Could not register DejaVu font: {e}')
    _fonts_registered = True


def hebrew(text):
    if not text:
        return ''
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


def fmt_currency(amount):
    if amount is None:
        return '₪0'
    return f'₪{amount:,.0f}'


def _get_styles():
    _register_fonts()
    styles = {}
    styles['title'] = ParagraphStyle(
        'HebrewTitle', fontName='DejaVu-Bold', fontSize=26,
        alignment=TA_CENTER, textColor=GOLD_DARK, leading=34, spaceAfter=6
    )
    styles['subtitle'] = ParagraphStyle(
        'HebrewSubtitle', fontName='Rubik', fontSize=14,
        alignment=TA_CENTER, textColor=GRAY_TEXT, leading=20, spaceAfter=4
    )
    styles['heading1'] = ParagraphStyle(
        'Heading1', fontName='DejaVu-Bold', fontSize=16,
        alignment=TA_RIGHT, textColor=GOLD_DARK, leading=24,
        spaceBefore=10, spaceAfter=6
    )
    styles['heading2'] = ParagraphStyle(
        'Heading2', fontName='DejaVu-Bold', fontSize=13,
        alignment=TA_RIGHT, textColor=DARK_TEXT, leading=18,
        spaceBefore=6, spaceAfter=4
    )
    styles['normal'] = ParagraphStyle(
        'HebrewNormal', fontName='Rubik', fontSize=10,
        alignment=TA_RIGHT, textColor=DARK_TEXT, leading=15
    )
    styles['normal_center'] = ParagraphStyle(
        'HebrewNormalCenter', fontName='Rubik', fontSize=10,
        alignment=TA_CENTER, textColor=DARK_TEXT, leading=15
    )
    styles['small'] = ParagraphStyle(
        'HebrewSmall', fontName='Rubik', fontSize=8,
        alignment=TA_RIGHT, textColor=GRAY_TEXT, leading=11
    )
    styles['bold'] = ParagraphStyle(
        'HebrewBold', fontName='DejaVu-Bold', fontSize=10,
        alignment=TA_RIGHT, textColor=DARK_TEXT, leading=14
    )
    styles['cover_address'] = ParagraphStyle(
        'CoverAddress', fontName='DejaVu-Bold', fontSize=20,
        alignment=TA_CENTER, textColor=DARK_TEXT, leading=28, spaceAfter=8
    )
    styles['cover_detail'] = ParagraphStyle(
        'CoverDetail', fontName='Rubik', fontSize=12,
        alignment=TA_CENTER, textColor=GRAY_TEXT, leading=18, spaceAfter=4
    )
    styles['table_header'] = ParagraphStyle(
        'TableHeader', fontName='DejaVu-Bold', fontSize=10,
        alignment=TA_CENTER, textColor=WHITE, leading=14
    )
    styles['table_cell'] = ParagraphStyle(
        'TableCell', fontName='Rubik', fontSize=9,
        alignment=TA_RIGHT, textColor=DARK_TEXT, leading=13
    )
    styles['table_cell_center'] = ParagraphStyle(
        'TableCellCenter', fontName='Rubik', fontSize=9,
        alignment=TA_CENTER, textColor=DARK_TEXT, leading=13
    )
    styles['footer'] = ParagraphStyle(
        'Footer', fontName='Rubik', fontSize=7,
        alignment=TA_CENTER, textColor=GRAY_TEXT, leading=10
    )
    return styles


class PDFService:
    def __init__(self):
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports')
        self.uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_inspection_report(self, db, inspection_id: str) -> str:
        try:
            inspection = await db.inspections.find_one({'id': inspection_id}, {'_id': 0})
            if not inspection:
                raise ValueError('Inspection not found')

            property_id = inspection.get('property_id')
            property_data = {}
            if property_id:
                property_data = await db.properties.find_one({'id': property_id}, {'_id': 0}) or {}

            expert_profile = None
            expert_profile_id = inspection.get('expert_profile_id')
            if expert_profile_id:
                expert_profile = await db.expert_profiles.find_one({'id': expert_profile_id}, {'_id': 0})

            findings = await db.professional_findings.find(
                {'inspection_id': inspection_id}, {'_id': 0}
            ).to_list(5000)

            all_evidence_ids = []
            for f in findings:
                all_evidence_ids.extend(f.get('evidence_ids', []))
            media_map = {}
            if all_evidence_ids:
                media_assets = await db.media_assets.find(
                    {'id': {'$in': all_evidence_ids}}, {'_id': 0}
                ).to_list(5000)
                media_map = {m['id']: m for m in media_assets}

            filename = f"inspection_{inspection_id}.pdf"
            filepath = os.path.join(self.output_dir, filename)

            styles = _get_styles()
            page_w, page_h = A4
            margin = 2 * cm

            expert_name = ''
            expert_phone = ''
            expert_email = ''
            expert_address = ''
            expert_logo_path = None
            if expert_profile:
                expert_name = expert_profile.get('full_name', '')
                expert_phone = expert_profile.get('phone', '')
                expert_email = expert_profile.get('email', '')
                expert_address = expert_profile.get('address', '')
                logo_url = expert_profile.get('logo_url', '')
                if logo_url:
                    resolved = self._resolve_file_path(logo_url)
                    if resolved and os.path.exists(resolved):
                        expert_logo_path = resolved

            total_pages_holder = [0]

            def header_footer_handler(canvas, doc):
                canvas.saveState()
                page_num = doc.page
                total_pages = total_pages_holder[0] or '?'

                header_y = page_h - 1.2 * cm
                canvas.setStrokeColor(GOLD)
                canvas.setLineWidth(1.5)
                canvas.line(margin, header_y, page_w - margin, header_y)

                if expert_logo_path:
                    try:
                        canvas.drawImage(expert_logo_path, page_w / 2 - 1.2 * cm, header_y + 2 * mm,
                                         width=2.4 * cm, height=1 * cm, preserveAspectRatio=True, mask='auto')
                    except Exception:
                        pass

                footer_y = 1.4 * cm
                canvas.setStrokeColor(GOLD)
                canvas.setLineWidth(1.5)
                canvas.line(margin, footer_y + 14, page_w - margin, footer_y + 14)

                canvas.setFont('Rubik', 7)
                canvas.setFillColor(GRAY_TEXT)

                contact_parts = []
                if expert_email:
                    contact_parts.append(expert_email)
                if expert_phone:
                    contact_parts.append(expert_phone)
                if contact_parts:
                    contact_text = '   |   '.join(contact_parts)
                    canvas.drawCentredString(page_w / 2, footer_y + 4, contact_text)

                if expert_address:
                    addr_text = hebrew(expert_address)
                    canvas.drawCentredString(page_w / 2, footer_y - 6, addr_text)

                page_label = hebrew(f'עמוד {page_num} מתוך {total_pages}')
                canvas.setFont('DejaVu-Bold', 8)
                canvas.setFillColor(DARK_TEXT)
                canvas.drawString(margin, footer_y + 4, page_label)

                canvas.restoreState()

            def make_doc(target):
                d = BaseDocTemplate(target, pagesize=A4,
                                    rightMargin=margin, leftMargin=margin,
                                    topMargin=2.2 * cm, bottomMargin=1.8 * cm)
                f = Frame(margin, 1.8 * cm, page_w - 2 * margin, page_h - 2.8 * cm - 1.2 * cm,
                          id='main', showBoundary=0)
                d.addPageTemplates([PageTemplate(id='main', frames=[f], onPage=header_footer_handler)])
                return d

            def build_story():
                s = []
                s.extend(self._build_cover_page(styles, inspection, property_data, expert_profile))
                s.append(PageBreak())
                s.extend(self._build_property_page(styles, inspection, property_data))
                s.append(PageBreak())
                s.extend(self._build_expert_page(styles, expert_profile))
                s.append(PageBreak())
                s.extend(self._build_standards_page(styles))
                s.append(PageBreak())
                s.extend(self._build_findings_pages(styles, findings, media_map))
                cat_totals = self._calc_category_totals(findings)
                s.append(PageBreak())
                s.extend(self._build_financial_page(styles, cat_totals))
                return s

            temp_buf = io.BytesIO()
            temp_doc = make_doc(temp_buf)
            temp_doc.build(build_story())
            total_pages_holder[0] = temp_doc.page

            from services.object_storage import save_bytes, is_s3_mode

            final_buf = io.BytesIO()
            final_doc = make_doc(final_buf)
            final_doc.build(build_story())
            pdf_bytes = final_buf.getvalue()

            if is_s3_mode():
                stored_ref = save_bytes(pdf_bytes, f"reports/{filename}", "application/pdf")
                logger.info(f'PDF → S3: {stored_ref} ({len(pdf_bytes)} bytes)')
                return stored_ref
            else:
                with open(filepath, 'wb') as f:
                    f.write(pdf_bytes)
                return f"/reports/{filename}"

        except Exception as e:
            logger.error(f'PDF generation error: {str(e)}', exc_info=True)
            raise

    def _build_cover_page(self, styles, inspection, property_data, expert_profile):
        elements = []
        elements.append(Spacer(1, 2 * cm))

        if expert_profile and expert_profile.get('logo_url'):
            logo_path = self._resolve_file_path(expert_profile['logo_url'])
            if logo_path and os.path.exists(logo_path):
                try:
                    img = Image(logo_path, width=5 * cm, height=5 * cm)
                    img.hAlign = 'CENTER'
                    elements.append(img)
                    elements.append(Spacer(1, 0.5 * cm))
                except Exception:
                    pass

        elements.append(Spacer(1, 0.5 * cm))

        line_data = [['']]
        line_table = Table(line_data, colWidths=[14 * cm])
        line_table.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (0, 0), 2, GOLD),
        ]))
        elements.append(line_table)
        elements.append(Spacer(1, 0.5 * cm))

        elements.append(Paragraph(hebrew('חוות דעת הנדסית  בדק בית'), styles['title']))
        elements.append(Spacer(1, 0.3 * cm))

        line_table2 = Table([['']], colWidths=[14 * cm])
        line_table2.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (0, 0), 2, GOLD),
        ]))
        elements.append(line_table2)
        elements.append(Spacer(1, 1 * cm))

        address = property_data.get('address', inspection.get('property_address', ''))
        if address:
            elements.append(Paragraph(hebrew(address), styles['cover_address']))
            elements.append(Spacer(1, 0.5 * cm))

        client_name = property_data.get('client_name', inspection.get('client_name', ''))
        if client_name:
            elements.append(Paragraph(hebrew(f'עבור: {client_name}'), styles['cover_detail']))

        insp_date = inspection.get('inspection_date', '')
        if insp_date:
            elements.append(Paragraph(hebrew(f'תאריך בדיקה: {insp_date}'), styles['cover_detail']))

        elements.append(Spacer(1, 1.5 * cm))

        if expert_profile:
            name = expert_profile.get('full_name', '')
            title = expert_profile.get('title', '')
            if name:
                elements.append(Paragraph(hebrew(name), ParagraphStyle(
                    'ExpertNameCover', fontName='DejaVu-Bold', fontSize=14,
                    alignment=TA_CENTER, textColor=DARK_TEXT, leading=20
                )))
            if title:
                elements.append(Paragraph(hebrew(title), styles['cover_detail']))

            sig_url = expert_profile.get('signature_url')
            if sig_url:
                sig_path = self._resolve_file_path(sig_url)
                if sig_path and os.path.exists(sig_path):
                    try:
                        sig_img = Image(sig_path, width=4 * cm, height=2 * cm)
                        sig_img.hAlign = 'CENTER'
                        elements.append(Spacer(1, 0.5 * cm))
                        elements.append(sig_img)
                    except Exception:
                        pass

        return elements

    def _build_expert_page(self, styles, expert_profile):
        elements = []
        elements.append(Paragraph(hebrew('פרטי המומחה'), styles['heading1']))
        elements.append(Spacer(1, 0.5 * cm))

        if not expert_profile:
            elements.append(Paragraph(hebrew('לא הוגדר פרופיל מומחה'), styles['normal']))
            return elements

        fields = [
            ('שם מלא', expert_profile.get('full_name', '')),
            ('תואר', expert_profile.get('title', '')),
            ('השכלה', expert_profile.get('education', '')),
            ('ניסיון (שנים)', str(expert_profile.get('experience_years', '')) if expert_profile.get('experience_years') else ''),
            ('רישיון', expert_profile.get('license_number', '')),
            ('טלפון', expert_profile.get('phone', '')),
            ('דוא"ל', expert_profile.get('email', '')),
            ('כתובת', expert_profile.get('address', '')),
        ]

        certs = expert_profile.get('certifications', [])
        if certs:
            fields.append(('הסמכות', ', '.join(certs)))

        table_data = []
        for label, value in fields:
            if value:
                table_data.append([
                    Paragraph(hebrew(str(value)), styles['table_cell']),
                    Paragraph(hebrew(label), styles['bold']),
                ])

        if table_data:
            avail_w = A4[0] - 4 * cm
            t = Table(table_data, colWidths=[avail_w * 0.6, avail_w * 0.4])
            t.setStyle(TableStyle([
                ('BACKGROUND', (1, 0), (1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(t)

        declaration = expert_profile.get('declaration_text', '')
        if declaration:
            elements.append(Spacer(1, 1 * cm))
            elements.append(Paragraph(hebrew('הצהרה'), styles['heading2']))
            elements.append(Spacer(1, 0.3 * cm))
            for line in declaration.split('\n'):
                if line.strip():
                    elements.append(Paragraph(hebrew(line.strip()), styles['normal']))
                    elements.append(Spacer(1, 0.15 * cm))

        return elements

    def _build_property_page(self, styles, inspection, property_data):
        elements = []
        elements.append(Paragraph(hebrew('תיאור הנכס'), styles['heading1']))
        elements.append(Spacer(1, 0.5 * cm))

        prop_type = property_data.get('property_type', inspection.get('property_type', ''))
        address = property_data.get('address', inspection.get('property_address', ''))
        project = property_data.get('project', inspection.get('project', ''))
        building = property_data.get('building', inspection.get('building', ''))
        floor = property_data.get('floor', inspection.get('property_floor'))
        apt = property_data.get('apt_number', inspection.get('property_apt_number', ''))
        rooms = property_data.get('num_rooms', inspection.get('property_num_rooms'))
        area = property_data.get('area_sqm', inspection.get('property_area_sqm'))
        client_name = property_data.get('client_name', inspection.get('client_name', ''))
        is_occupied = property_data.get('is_occupied', inspection.get('property_is_occupied'))
        has_elec = property_data.get('has_electricity', inspection.get('property_has_electricity'))
        has_water = property_data.get('has_water', inspection.get('property_has_water'))
        has_gas = property_data.get('has_gas', inspection.get('property_has_gas'))

        yes_no = lambda v: 'כן' if v else 'לא' if v is not None else ''

        details = [
            ('סוג נכס', prop_type),
            ('כתובת', address),
            ('פרויקט', project),
            ('בניין', building),
            ('קומה', str(floor) if floor is not None else ''),
            ('דירה', apt),
            ('מספר חדרים', str(rooms) if rooms is not None else ''),
            ('שטח (מ"ר)', str(area) if area is not None else ''),
            ('שם המזמין', client_name),
            ('מאוכלס', yes_no(is_occupied)),
            ('חשמל', yes_no(has_elec)),
            ('מים', yes_no(has_water)),
            ('גז', yes_no(has_gas)),
        ]

        table_data = []
        for label, value in details:
            if value:
                table_data.append([
                    Paragraph(hebrew(str(value)), styles['table_cell']),
                    Paragraph(hebrew(label), styles['bold']),
                ])

        if table_data:
            avail_w = A4[0] - 4 * cm
            t = Table(table_data, colWidths=[avail_w * 0.6, avail_w * 0.4])
            t.setStyle(TableStyle([
                ('BACKGROUND', (1, 0), (1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(t)

        elements.append(Spacer(1, 0.8 * cm))
        elements.append(Paragraph(hebrew('פרטי הבדיקה'), styles['heading2']))
        elements.append(Spacer(1, 0.3 * cm))

        insp_details = [
            ('תאריך בדיקה', inspection.get('inspection_date', '')),
            ('תאריך מסירה', inspection.get('handover_date', '')),
        ]
        attendees = inspection.get('attendees', [])
        if attendees:
            insp_details.append(('נוכחים', ', '.join(attendees)))
        notes = inspection.get('notes', '')
        if notes:
            insp_details.append(('הערות', notes))

        insp_table_data = []
        for label, value in insp_details:
            if value:
                insp_table_data.append([
                    Paragraph(hebrew(str(value)), styles['table_cell']),
                    Paragraph(hebrew(label), styles['bold']),
                ])

        if insp_table_data:
            avail_w = A4[0] - 4 * cm
            t2 = Table(insp_table_data, colWidths=[avail_w * 0.6, avail_w * 0.4])
            t2.setStyle(TableStyle([
                ('BACKGROUND', (1, 0), (1, -1), LIGHT_GRAY),
                ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(t2)

        return elements

    def _build_findings_pages(self, styles, findings, media_map):
        elements = []
        if not findings:
            elements.append(Paragraph(hebrew('ממצאים'), styles['heading1']))
            elements.append(Paragraph(hebrew('לא נמצאו ממצאים'), styles['normal']))
            return elements

        by_category = {}
        for f in findings:
            cat = f.get('category', 'other')
            by_category.setdefault(cat, []).append(f)

        sorted_cats = sorted(CATEGORIES, key=lambda c: c['display_order'])
        cat_num = 0
        for cat_info in sorted_cats:
            cat_value = cat_info['value']
            if cat_value not in by_category:
                continue
            cat_num += 1
            cat_findings = by_category[cat_value]

            cat_header_style = ParagraphStyle(
                'CatHeader', fontName='DejaVu-Bold', fontSize=14,
                alignment=TA_RIGHT, textColor=GOLD_DARK, leading=20
            )
            elements.append(Paragraph(
                hebrew(f'{cat_num}. {cat_info["label"]}'),
                cat_header_style
            ))
            elements.append(Spacer(1, 0.3 * cm))

            for idx, finding in enumerate(cat_findings, 1):
                finding_num = f'{cat_num}.{idx}'
                card = self._build_finding_card(styles, finding, finding_num, media_map)
                elements.extend(card)
                elements.append(Spacer(1, 0.5 * cm))

            cat_cost = sum((f.get('total_price') or 0) for f in cat_findings)
            if cat_cost > 0:
                avail_w = A4[0] - 4 * cm
                subtotal_data = [[
                    Paragraph(fmt_currency(cat_cost), ParagraphStyle(
                        'CatSubtotal', fontName='DejaVu-Bold', fontSize=10,
                        alignment=TA_CENTER, textColor=GOLD_DARK, leading=14
                    )),
                    Paragraph(hebrew(f'סה"כ {cat_info["label"]}'), ParagraphStyle(
                        'CatSubtotalLabel', fontName='DejaVu-Bold', fontSize=10,
                        alignment=TA_RIGHT, textColor=GOLD_DARK, leading=14
                    )),
                ]]
                st = Table(subtotal_data, colWidths=[avail_w * 0.35, avail_w * 0.65])
                st.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), GOLD_LIGHT),
                    ('GRID', (0, 0), (-1, -1), 0.5, GOLD),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ]))
                elements.append(st)
                elements.append(Spacer(1, 0.6 * cm))

        for cat_value, cat_findings in by_category.items():
            if cat_value in [c['value'] for c in CATEGORIES]:
                continue
            cat_num += 1
            elements.append(Paragraph(
                hebrew(f'{cat_num}. {cat_value}'),
                styles['heading1']
            ))
            elements.append(Spacer(1, 0.3 * cm))
            for idx, finding in enumerate(cat_findings, 1):
                finding_num = f'{cat_num}.{idx}'
                card = self._build_finding_card(styles, finding, finding_num, media_map)
                elements.extend(card)
                elements.append(Spacer(1, 0.5 * cm))

        return elements

    def _build_finding_card(self, styles, finding, finding_num, media_map):
        elements = []
        avail_w = A4[0] - 4 * cm

        header_style = ParagraphStyle(
            'FindingHeader', fontName='DejaVu-Bold', fontSize=11,
            alignment=TA_RIGHT, textColor=BLACK, leading=16
        )
        header_data = [[Paragraph(hebrew(f'ממצא {finding_num}'), header_style)]]
        header_table = Table(header_data, colWidths=[avail_w])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), GOLD),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(header_table)

        label_style = ParagraphStyle(
            'RowLabel', fontName='DejaVu-Bold', fontSize=10,
            alignment=TA_RIGHT, textColor=DARK_TEXT, leading=14
        )
        cell_style = ParagraphStyle(
            'RowCell', fontName='Rubik', fontSize=9,
            alignment=TA_RIGHT, textColor=DARK_TEXT, leading=13
        )

        rows = []

        description = finding.get('description', '')
        if description:
            rows.append([
                Paragraph(hebrew(description), cell_style),
                Paragraph(hebrew('ממצא'), label_style),
            ])

        location = finding.get('location_text') or finding.get('location', '')
        if location:
            rows.append([
                Paragraph(hebrew(location), cell_style),
                Paragraph(hebrew('מיקום'), label_style),
            ])

        recommendation = finding.get('recommendation', '')
        if recommendation:
            rows.append([
                Paragraph(hebrew(recommendation), cell_style),
                Paragraph(hebrew('המלצה'), label_style),
            ])

        standard_ref = finding.get('standard_reference', '')
        if standard_ref:
            rows.append([
                Paragraph(hebrew(standard_ref), cell_style),
                Paragraph(hebrew('תקן'), label_style),
            ])

        unit_price = finding.get('unit_price') or 0
        quantity = finding.get('quantity') or 0
        unit_label = finding.get('unit_label', '') or "קומפ'"
        total_price = finding.get('total_price') or (unit_price * quantity)
        if total_price > 0:
            price_parts = []
            if unit_price > 0:
                price_parts.append(f'מחיר ליחידה: {fmt_currency(unit_price)}')
            if quantity > 0:
                qty_str = f'{quantity:.0f}' if quantity == int(quantity) else f'{quantity}'
                price_parts.append(f'כמות: {qty_str} {unit_label}')
            price_text = ', '.join(price_parts)
            rows.append([
                Paragraph(hebrew(price_text), cell_style),
                Paragraph(hebrew('מחיר'), label_style),
            ])

        if rows:
            label_w = avail_w * 0.18
            value_w = avail_w * 0.82
            t = Table(rows, colWidths=[value_w, label_w])
            row_styles = [
                ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (1, 0), (1, -1), LIGHT_GRAY),
            ]
            t.setStyle(TableStyle(row_styles))
            elements.append(t)

        evidence_ids = finding.get('evidence_ids', [])
        if evidence_ids:
            photo_elements = []
            count = 0
            for eid in evidence_ids:
                if count >= 4:
                    break
                media = media_map.get(eid)
                if not media:
                    continue
                file_url = media.get('file_url', '')
                img_path = self._resolve_file_path(file_url)
                if img_path and os.path.exists(img_path):
                    try:
                        img = Image(img_path, width=5.5 * cm, height=4.2 * cm)
                        photo_elements.append(img)
                        count += 1
                    except Exception as e:
                        logger.warning(f'Could not load image {img_path}: {e}')

            if photo_elements:
                elements.append(Spacer(1, 0.15 * cm))
                if len(photo_elements) == 1:
                    img_table = Table([photo_elements], colWidths=[avail_w])
                elif len(photo_elements) == 2:
                    img_table = Table([photo_elements], colWidths=[avail_w / 2] * 2)
                else:
                    per_row = min(len(photo_elements), 3)
                    row1 = photo_elements[:per_row]
                    img_table = Table([row1], colWidths=[avail_w / per_row] * per_row)
                    if len(photo_elements) > 3:
                        row2 = photo_elements[3:]
                        img_table2 = Table([row2], colWidths=[avail_w / len(row2)] * len(row2))
                        img_table2.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('TOPPADDING', (0, 0), (-1, -1), 2),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                        ]))

                img_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                elements.append(img_table)

        return elements

    def _calc_category_totals(self, findings):
        totals = {}
        for f in findings:
            cat = f.get('category', 'other')
            if cat not in totals:
                totals[cat] = {'count': 0, 'cost': 0}
            totals[cat]['count'] += 1
            price = f.get('total_price') or 0
            if not price:
                up = f.get('unit_price') or 0
                qty = f.get('quantity') or 0
                price = up * qty
            totals[cat]['cost'] += price
        return totals

    def _build_financial_page(self, styles, category_totals):
        elements = []
        elements.append(Paragraph(hebrew('סיכום כספי'), styles['heading1']))
        elements.append(Spacer(1, 0.5 * cm))

        avail_w = A4[0] - 4 * cm
        col_widths = [avail_w * 0.3, avail_w * 0.2, avail_w * 0.5]

        header_style = ParagraphStyle(
            'FinHeader', fontName='DejaVu-Bold', fontSize=10,
            alignment=TA_CENTER, textColor=BLACK, leading=14
        )
        header_row = [
            Paragraph(hebrew('עלות'), header_style),
            Paragraph(hebrew('ממצאים'), header_style),
            Paragraph(hebrew('קטגוריה'), header_style),
        ]
        table_data = [header_row]

        subtotal = 0
        sorted_cats = sorted(CATEGORIES, key=lambda c: c['display_order'])
        for cat_info in sorted_cats:
            cat_value = cat_info['value']
            if cat_value not in category_totals:
                continue
            ct = category_totals[cat_value]
            subtotal += ct['cost']
            table_data.append([
                Paragraph(fmt_currency(ct['cost']), styles['table_cell_center']),
                Paragraph(str(ct['count']), styles['table_cell_center']),
                Paragraph(hebrew(cat_info['label']), styles['table_cell']),
            ])

        for cat_value, ct in category_totals.items():
            if cat_value in [c['value'] for c in CATEGORIES]:
                continue
            subtotal += ct['cost']
            table_data.append([
                Paragraph(fmt_currency(ct['cost']), styles['table_cell_center']),
                Paragraph(str(ct['count']), styles['table_cell_center']),
                Paragraph(hebrew(cat_value), styles['table_cell']),
            ])

        bold_cell = ParagraphStyle(
            'BoldCell', fontName='DejaVu-Bold', fontSize=10,
            alignment=TA_CENTER, textColor=DARK_TEXT, leading=14
        )
        bold_cell_right = ParagraphStyle(
            'BoldCellRight', fontName='DejaVu-Bold', fontSize=10,
            alignment=TA_RIGHT, textColor=DARK_TEXT, leading=14
        )

        table_data.append([
            Paragraph(fmt_currency(subtotal), bold_cell),
            Paragraph('', styles['table_cell_center']),
            Paragraph(hebrew('סה"כ'), bold_cell_right),
        ])

        mgmt_fee = subtotal * 0.10
        table_data.append([
            Paragraph(fmt_currency(mgmt_fee), styles['table_cell_center']),
            Paragraph('', styles['table_cell_center']),
            Paragraph(hebrew('דמי ניהול (10%)'), styles['table_cell']),
        ])

        unforeseen = subtotal * 0.05
        table_data.append([
            Paragraph(fmt_currency(unforeseen), styles['table_cell_center']),
            Paragraph('', styles['table_cell_center']),
            Paragraph(hebrew('בלתי צפוי (5%)'), styles['table_cell']),
        ])

        before_vat = subtotal + mgmt_fee + unforeseen
        vat = before_vat * 0.17
        table_data.append([
            Paragraph(fmt_currency(vat), styles['table_cell_center']),
            Paragraph('', styles['table_cell_center']),
            Paragraph(hebrew('מע"מ (17%)'), styles['table_cell']),
        ])

        grand_total = before_vat + vat
        grand_style = ParagraphStyle(
            'GrandTotal', fontName='DejaVu-Bold', fontSize=12,
            alignment=TA_CENTER, textColor=GOLD_DARK, leading=16
        )
        grand_label = ParagraphStyle(
            'GrandLabel', fontName='DejaVu-Bold', fontSize=12,
            alignment=TA_RIGHT, textColor=GOLD_DARK, leading=16
        )
        table_data.append([
            Paragraph(fmt_currency(grand_total), grand_style),
            Paragraph('', styles['table_cell_center']),
            Paragraph(hebrew('סה"כ כולל מע"מ'), grand_label),
        ])

        t = Table(table_data, colWidths=col_widths)

        style_commands = [
            ('BACKGROUND', (0, 0), (-1, 0), GOLD),
            ('TEXTCOLOR', (0, 0), (-1, 0), BLACK),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, -1), (-1, -1), GOLD_LIGHT),
        ]

        for i in range(1, len(table_data)):
            if i % 2 == 0:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GRAY))

        t.setStyle(TableStyle(style_commands))
        elements.append(t)

        return elements

    def _build_standards_page(self, styles):
        elements = []
        elements.append(Paragraph(hebrew('תקנים ומתודולוגיה'), styles['heading1']))
        elements.append(Spacer(1, 0.5 * cm))

        elements.append(Paragraph(hebrew('הבדיקה בוצעה בהתאם לתקנים הבאים:'), styles['normal']))
        elements.append(Spacer(1, 0.3 * cm))

        standards = [
            'ת"י 1045 - תכנון מגורים',
            'ת"י 23 - בטון',
            'ת"י 12 - פלדה',
            'ת"י 1555 - ריצוף וחיפוי',
            'ת"י 938 - דלתות פנים',
            'ת"י 1474 - אלומיניום חלונות ודלתות',
            'ת"י 1142 - איטום מבנים',
            'ת"י 61 - צנרת מים',
            'ת"י 158 - התקנות חשמל',
            'ת"י 5044 - התקנת מערכות חשמליות',
            'תקנות התכנון והבנייה',
            'חוק המכר (דירות) – תקופת בדק',
        ]

        for std in standards:
            bullet_text = f'• {std}'
            elements.append(Paragraph(hebrew(bullet_text), styles['normal']))
            elements.append(Spacer(1, 0.2 * cm))

        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph(hebrew('מתודולוגיה'), styles['heading2']))
        elements.append(Spacer(1, 0.3 * cm))

        methodology = [
            'הבדיקה כללה סקירה ויזואלית מקיפה של כל חלקי הדירה.',
            'הממצאים מתועדים בצילומים ומסווגים לפי קטגוריות מקצועיות.',
            'לכל ממצא צורף תקן רלוונטי והערכת עלות תיקון.',
            'הדוח אינו כולל בדיקות הרסניות או בדיקות מעבדה אלא אם צוין אחרת.',
        ]

        for line in methodology:
            elements.append(Paragraph(hebrew(f'• {line}'), styles['normal']))
            elements.append(Spacer(1, 0.15 * cm))

        return elements

    def _resolve_file_path(self, url):
        if not url:
            return None
        if url.startswith('/api/uploads/'):
            filename = url.replace('/api/uploads/', '')
            return os.path.join(self.uploads_dir, filename)
        if url.startswith('/uploads/'):
            filename = url.replace('/uploads/', '')
            return os.path.join(self.uploads_dir, filename)
        if url.startswith('uploads/'):
            filename = url.replace('uploads/', '')
            return os.path.join(self.uploads_dir, filename)
        if os.path.isabs(url) and os.path.exists(url):
            return url
        possible = os.path.join(self.uploads_dir, os.path.basename(url))
        if os.path.exists(possible):
            return possible
        return None
