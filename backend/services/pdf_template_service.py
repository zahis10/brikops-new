import os
import io
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether, Frame, PageTemplate
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import requests

logger = logging.getLogger(__name__)

class HebrewPDFTemplate:
    """Production-grade Hebrew RTL PDF template matching sample structure"""
    
    # Page dimensions and margins (A4)
    PAGE_WIDTH, PAGE_HEIGHT = A4
    MARGIN_TOP = 2*cm
    MARGIN_BOTTOM = 2.5*cm
    MARGIN_RIGHT = 2*cm
    MARGIN_LEFT = 2*cm
    
    # Brand colors (from logo analysis)
    COLOR_NAVY = colors.HexColor('#0F2A4A')
    COLOR_GOLD = colors.HexColor('#D4AF37')
    COLOR_TEXT = colors.HexColor('#1A1A1A')
    COLOR_GRAY = colors.HexColor('#666666')
    
    def __init__(self, logo_url: Optional[str] = None):
        self.logo_url = logo_url or 'https://customer-assets.emergentagent.com/job_property-inspect-9/artifacts/z1yg9asb_LOGO.png'
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Register Hebrew fonts
        self._register_fonts()
        
    def _register_fonts(self):
        """Register Hebrew-capable fonts"""
        try:
            # Try to use system fonts that support Hebrew
            # DejaVu Sans has excellent Hebrew support
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
            ]
            
            if os.path.exists(font_paths[0]):
                pdfmetrics.registerFont(TTFont('HebrewFont', font_paths[0]))
                pdfmetrics.registerFont(TTFont('HebrewFont-Bold', font_paths[1]))
            
        except Exception as e:
            logger.warning(f'Could not register custom fonts: {e}')
    
    def _create_styles(self):
        """Create paragraph styles for Hebrew RTL text"""
        styles = getSampleStyleSheet()
        
        # Title style
        styles.add(ParagraphStyle(
            name='HebrewTitle',
            fontName='HebrewFont-Bold',
            fontSize=24,
            alignment=TA_CENTER,
            textColor=self.COLOR_NAVY,
            spaceAfter=20,
            leading=30
        ))
        
        # Section header
        styles.add(ParagraphStyle(
            name='HebrewSection',
            fontName='HebrewFont-Bold',
            fontSize=16,
            alignment=TA_RIGHT,
            textColor=self.COLOR_NAVY,
            spaceAfter=12,
            spaceBefore=12,
            leading=20
        ))
        
        # Body text
        styles.add(ParagraphStyle(
            name='HebrewBody',
            fontName='HebrewFont',
            fontSize=11,
            alignment=TA_RIGHT,
            textColor=self.COLOR_TEXT,
            spaceAfter=6,
            leading=14
        ))
        
        # Table header
        styles.add(ParagraphStyle(
            name='HebrewTableHeader',
            fontName='HebrewFont-Bold',
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.white,
            leading=12
        ))
        
        # Table cell
        styles.add(ParagraphStyle(
            name='HebrewTableCell',
            fontName='HebrewFont',
            fontSize=10,
            alignment=TA_RIGHT,
            textColor=self.COLOR_TEXT,
            leading=12
        ))
        
        return styles
    
    def _download_logo(self) -> Optional[str]:
        """Download logo to temp location"""
        try:
            response = requests.get(self.logo_url, timeout=10)
            if response.status_code == 200:
                logo_path = os.path.join(self.output_dir, 'temp_logo.png')
                with open(logo_path, 'wb') as f:
                    f.write(response.content)
                return logo_path
        except Exception as e:
            logger.error(f'Failed to download logo: {e}')
        return None
    
    def _add_header_footer(self, canvas_obj, doc, page_num: int, total_pages: int, contact_info: Dict):
        """Add consistent header and footer to each page"""
        canvas_obj.saveState()
        
        # Header - Logo and company name
        logo_path = self._download_logo()
        if logo_path and os.path.exists(logo_path):
            try:
                canvas_obj.drawImage(
                    logo_path,
                    self.PAGE_WIDTH/2 - 2*cm,
                    self.PAGE_HEIGHT - self.MARGIN_TOP + 0.5*cm,
                    width=4*cm,
                    height=1.5*cm,
                    preserveAspectRatio=True,
                    mask='auto'
                )
            except:
                pass
        
        # Company name
        canvas_obj.setFont('HebrewFont-Bold', 12)
        canvas_obj.setFillColor(self.COLOR_NAVY)
        canvas_obj.drawCentredString(
            self.PAGE_WIDTH/2,
            self.PAGE_HEIGHT - self.MARGIN_TOP - 0.3*cm,
            'בונים אמון - יוצרים עתיד'
        )
        
        canvas_obj.setFont('HebrewFont', 10)
        canvas_obj.drawCentredString(
            self.PAGE_WIDTH/2,
            self.PAGE_HEIGHT - self.MARGIN_TOP - 0.8*cm,
            contact_info.get('company_name', 'צע שמי יזמות בע״מ')
        )
        
        # Footer - Contact info and page number
        canvas_obj.setFont('HebrewFont', 9)
        canvas_obj.setFillColor(self.COLOR_GRAY)
        
        footer_y = self.MARGIN_BOTTOM - 0.5*cm
        
        # Email and phone
        contact_line = f"{contact_info.get('email', '')} | {contact_info.get('phone', '')}"
        canvas_obj.drawCentredString(self.PAGE_WIDTH/2, footer_y, contact_line)
        
        # Address
        canvas_obj.drawCentredString(
            self.PAGE_WIDTH/2,
            footer_y - 0.5*cm,
            f"כתובת: {contact_info.get('address', '')}"
        )
        
        # Page number
        canvas_obj.drawRightString(
            self.PAGE_WIDTH - self.MARGIN_LEFT,
            footer_y - 1*cm,
            f'עמוד {page_num} מתוך {total_pages}'
        )
        
        canvas_obj.restoreState()
    
    def generate_report(self, report_data: Dict[str, Any], output_filename: str) -> str:
        """Generate complete inspection report PDF
        
        Args:
            report_data: Complete report data matching JSON schema
            output_filename: Output PDF filename
            
        Returns:
            Stored ref (s3://... or /reports/...) for the generated PDF
        """
        import io as _io
        from services.object_storage import save_bytes, is_s3_mode
        
        styles = self._create_styles()
        
        story = []
        story.extend(self._build_cover_page(report_data, styles))
        story.append(PageBreak())
        story.extend(self._build_regulatory_section(report_data, styles))
        story.append(PageBreak())
        story.extend(self._build_property_description(report_data, styles))
        story.append(PageBreak())
        story.extend(self._build_findings_summary(report_data, styles))
        story.append(PageBreak())
        story.extend(self._build_detailed_findings(report_data, styles))
        story.extend(self._build_financial_summary(report_data, styles))
        story.append(PageBreak())
        story.extend(self._build_citations_appendix(report_data, styles))
        story.append(PageBreak())
        story.extend(self._build_audit_appendix(report_data, styles))
        story.append(PageBreak())
        story.extend(self._build_closing_section(report_data, styles))
        
        total_pages = len(story) // 10 + 1
        
        def add_page_elements(canvas_obj, doc):
            page_num = doc.page
            self._add_header_footer(
                canvas_obj, doc, page_num, total_pages,
                report_data.get('contact_info', {})
            )
        
        buf = _io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            rightMargin=self.MARGIN_RIGHT,
            leftMargin=self.MARGIN_LEFT,
            topMargin=self.MARGIN_TOP + 1.5*cm,
            bottomMargin=self.MARGIN_BOTTOM + 1*cm
        )
        doc.build(story, onFirstPage=add_page_elements, onLaterPages=add_page_elements)
        pdf_bytes = buf.getvalue()
        
        if is_s3_mode():
            stored_ref = save_bytes(pdf_bytes, f"reports/{output_filename}", "application/pdf")
            logger.info(f'Generated PDF report → S3: {stored_ref} ({len(pdf_bytes)} bytes)')
            return stored_ref
        else:
            output_path = os.path.join(self.output_dir, output_filename)
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            logger.info(f'Generated PDF report → local: {output_path} ({len(pdf_bytes)} bytes)')
            return output_path
    
    def _build_cover_page(self, data: Dict, styles) -> List:
        """Build cover page with title, client info, and legal disclaimer"""
        story = []
        meta = data.get('report_meta', {})
        
        # Title
        story.append(Spacer(1, 2*cm))
        story.append(Paragraph('חוות דעת הנדסית - בדק בית', styles['HebrewTitle']))
        story.append(Spacer(1, 1*cm))
        
        # Property address
        story.append(Paragraph(
            f"כתובת: {data.get('property_details', {}).get('address', '')}",
            styles['HebrewSection']
        ))
        
        # Date
        story.append(Paragraph(
            f"תאריך: {meta.get('report_date', datetime.now().strftime('%d/%m/%Y'))}",
            styles['HebrewBody']
        ))
        story.append(Spacer(1, 1*cm))
        
        # Legal disclaimer
        disclaimer = (
            'אני נותן חוות דעתי זו במקום עדות בבית משפט. אני מצהיר בזאת, כי ידוע לי היטב '
            'שלעניין הוראות החוק הפלילי בדבר עדות שקר בבית משפט. דין חוות דעת זו, כשהיא '
            'חתומה על ידי, כדין עדות בשבועה שנתתי בבית משפט.'
        )
        story.append(Paragraph(disclaimer, styles['HebrewBody']))
        story.append(Spacer(1, 1*cm))
        
        # Report details table
        details_data = [
            ['שם המזמין:', meta.get('client_name', '')],
            ['תאריך ביקור בנכס:', meta.get('inspection_date', '')],
            ['שם הבודק:', meta.get('inspector_name', '')]
        ]
        
        details_table = Table(details_data, colWidths=[8*cm, 8*cm])
        details_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'HebrewFont', 11),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey)
        ]))
        story.append(details_table)
        
        return story
    
    def _build_regulatory_section(self, data: Dict, styles) -> List:
        """Build regulatory background section"""
        story = []
        
        story.append(Paragraph('חוות הדעת מסתמכת על:', styles['HebrewSection']))
        
        standards = [
            'תקן ישראלי 1918 - "בדיקת מבנים"',
            'תקן ישראלי 466 - "דלתות ותריסים"',
            'תקנות הבניה (בידוד תרמי)',
            'חוק המכר (דירות), תשל"ג-1973'
        ]
        
        for std in standards:
            story.append(Paragraph(f'• {std}', styles['HebrewBody']))
        
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph('ידע כללי עבור הדייר:', styles['HebrewSection']))
        
        warranty_text = (
            'תקופת הבדק: 12 חודשים ממועד מסירת הדירה. '
            'תקופת האחריות: 7 שנים ממועד מסירת הדירה.'
        )
        story.append(Paragraph(warranty_text, styles['HebrewBody']))
        
        return story
    
    def _build_property_description(self, data: Dict, styles) -> List:
        """Build property description section"""
        story = []
        prop = data.get('property_details', {})
        
        story.append(Paragraph('תיאור הנכס:', styles['HebrewSection']))
        
        prop_data = [
            ['סוג הנכס:', prop.get('property_type', 'דירת מגורים')],
            ['מספר חדרים:', str(prop.get('rooms_count', ''))],
            ['הנכס מאוכלס:', 'כן' if prop.get('occupied') else 'לא'],
            ['חיבור לחשמל:', 'יש' if prop.get('electricity') else 'אין'],
            ['חיבור למים:', 'יש' if prop.get('water') else 'אין']
        ]
        
        prop_table = Table(prop_data, colWidths=[8*cm, 8*cm])
        prop_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'HebrewFont', 11),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        story.append(prop_table)
        
        return story
    
    def _build_findings_summary(self, data: Dict, styles) -> List:
        """Build findings summary table by category"""
        story = []
        summary = data.get('categories_summary', [])
        
        total_findings = sum(cat.get('count', 0) for cat in summary)
        story.append(Paragraph(f'רשימת ממצאים ({total_findings})', styles['HebrewSection']))
        story.append(Spacer(1, 0.5*cm))
        
        # Build summary table
        table_data = [['#', 'קטגוריה', 'סה"כ ממצאים']]
        
        for idx, cat in enumerate(summary, 1):
            table_data.append([
                str(idx),
                cat.get('category_name', ''),
                str(cat.get('count', 0))
            ])
        
        summary_table = Table(table_data, colWidths=[2*cm, 10*cm, 4*cm])
        summary_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'HebrewFont-Bold', 11),
            ('FONT', (0, 1), (-1, -1), 'HebrewFont', 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white)
        ]))
        story.append(summary_table)
        
        return story
    
    def _build_detailed_findings(self, data: Dict, styles) -> List:
        """Build detailed findings section with images"""
        story = []
        findings = data.get('findings', [])
        
        for idx, finding in enumerate(findings, 1):
            story.append(PageBreak())
            story.append(Paragraph(
                f"{idx}. {finding.get('category', '')}",
                styles['HebrewSection']
            ))
            story.append(Spacer(1, 0.3*cm))
            
            # Finding details table
            details_data = [
                ['מיקום', 'המלצה', 'תקן', 'מחיר'],
                [
                    finding.get('location', ''),
                    finding.get('recommendation', ''),
                    finding.get('standard_ref', ''),
                    f"₪{finding.get('total_price', 0)}"
                ]
            ]
            
            details_table = Table(details_data, colWidths=[4*cm, 6*cm, 3*cm, 3*cm])
            details_table.setStyle(TableStyle([
                ('FONT', (0, 0), (-1, 0), 'HebrewFont-Bold', 10),
                ('FONT', (0, 1), (-1, -1), 'HebrewFont', 9),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_NAVY),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white)
            ]))
            story.append(details_table)
            story.append(Spacer(1, 0.5*cm))
            
            # Images - Real rendering
            images = finding.get('images', [])
            if images:
                story.append(Paragraph('תמונות:', styles['HebrewBody']))
                story.append(Spacer(1, 0.3*cm))
                
                # Render up to 3 images per finding
                for img_data in images[:3]:
                    img_path = img_data.get('path')
                    if img_path and os.path.exists(img_path):
                        try:
                            # Get optimal dimensions
                            from PIL import Image as PILImage
                            with PILImage.open(img_path) as pil_img:
                                width_px, height_px = pil_img.size
                                aspect_ratio = width_px / height_px
                                
                                # Calculate dimensions to fit in page
                                max_width = 14*cm
                                max_height = 10*cm
                                
                                if aspect_ratio > 1:  # Wider than tall
                                    img_width = min(max_width, width_px * cm / 72)
                                    img_height = img_width / aspect_ratio
                                else:  # Taller than wide
                                    img_height = min(max_height, height_px * cm / 72)
                                    img_width = img_height * aspect_ratio
                                
                                # Add image to PDF
                                img_obj = Image(
                                    img_path,
                                    width=img_width,
                                    height=img_height
                                )
                                story.append(img_obj)
                                
                                # Add caption if present
                                caption = img_data.get('caption', '')
                                if caption:
                                    story.append(Paragraph(
                                        caption,
                                        styles['HebrewBody']
                                    ))
                                
                                story.append(Spacer(1, 0.3*cm))
                        
                        except Exception as e:
                            logger.error(f'Error adding image to PDF: {str(e)}')
                            # Add fallback text
                            story.append(Paragraph(
                                'תמונה לא זמינה',
                                styles['HebrewBody']
                            ))
                    else:
                        # Image file missing
                        story.append(Paragraph(
                            'תמונה לא נמצאה',
                            styles['HebrewBody']
                        ))
        
        return story
    
    def _build_financial_summary(self, data: Dict, styles) -> List:
        """Build financial summary with calculations"""
        story = []
        financial = data.get('financial_summary', {})
        
        story.append(PageBreak())
        story.append(Paragraph('הערכה כספית', styles['HebrewSection']))
        story.append(Spacer(1, 0.5*cm))
        
        # Itemized costs from findings
        table_data = [['#', 'תיאור', 'כמות', 'יחידה', 'מחיר ליח\'', 'סה"כ (₪)']]
        
        for idx, finding in enumerate(data.get('findings', []), 1):
            table_data.append([
                str(idx),
                finding.get('category', ''),
                str(finding.get('qty', 1)),
                finding.get('unit', 'קומפ\''),
                f"₪{finding.get('unit_price', 0)}",
                f"₪{finding.get('total_price', 0)}"
            ])
        
        # Subtotal
        subtotal = financial.get('subtotal', 0)
        table_data.append(['', '', '', '', 'סה"כ ביניים:', f"₪{subtotal}"])
        
        # Engineering supervision
        supervision_pct = financial.get('supervision_pct', 10)
        supervision_amt = financial.get('supervision_amount', subtotal * supervision_pct / 100)
        table_data.append(['', '', '', '', f'פיקוח הנדסי ({supervision_pct}%):', f"₪{supervision_amt}"])
        
        # Before VAT
        before_vat = financial.get('before_vat', subtotal + supervision_amt)
        table_data.append(['', '', '', '', 'סה"כ לפני מע"מ:', f"₪{before_vat}"])
        
        # VAT
        vat_pct = financial.get('vat_pct', 18)
        vat_amt = financial.get('vat_amount', before_vat * vat_pct / 100)
        table_data.append(['', '', '', '', f'מע"מ ({vat_pct}%):', f"₪{vat_amt}"])
        
        # Grand total
        grand_total = financial.get('grand_total', before_vat + vat_amt)
        table_data.append(['', '', '', '', 'סה"כ כולל מע"מ:', f"₪{grand_total}"])
        
        financial_table = Table(table_data, colWidths=[1.5*cm, 5*cm, 2*cm, 2*cm, 3*cm, 3*cm])
        financial_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'HebrewFont-Bold', 10),
            ('FONT', (0, 1), (-1, -1), 'HebrewFont', 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (-2, -4), (-1, -1), colors.lightgrey),
            ('FONT', (-2, -1), (-1, -1), 'HebrewFont-Bold', 11)
        ]))
        story.append(financial_table)
        
        return story
    
    def _build_citations_appendix(self, data: Dict, styles) -> List:
        """Build citations appendix showing contract and regulation references"""
        story = []
        
        story.append(Paragraph('הפניות לחוזה ותקנים', styles['HebrewSection']))
        story.append(Spacer(1, 0.5*cm))
        
        # Get findings with citations
        findings_with_citations = [
            f for f in data.get('findings', [])
            if f.get('citations') and len(f.get('citations', [])) > 0
        ]
        
        if not findings_with_citations:
            story.append(Paragraph(
                'אין הפניות לחוזה או תקנים עבור ממצאים אלו.',
                styles['HebrewBody']
            ))
            return story
        
        # Build citations table
        for idx, finding in enumerate(findings_with_citations, 1):
            story.append(Paragraph(
                f"{idx}. {finding.get('category', '')} - {finding.get('location', '')}",
                styles['HebrewSection']
            ))
            story.append(Spacer(1, 0.3*cm))
            
            citations = finding.get('citations', [])
            
            # Contract/Spec citations
            contract_citations = [c for c in citations if c.get('citation_type') in ['contract_clause', 'specification']]
            if contract_citations:
                story.append(Paragraph('<b>הפניה לחוזה/מפרט:</b>', styles['HebrewBody']))
                
                for citation in contract_citations:
                    clause = citation.get('clause', {})
                    document = citation.get('document', {})
                    
                    citation_text = f"• מסמך: {document.get('filename', 'לא ידוע')}"
                    if clause.get('clause_number'):
                        citation_text += f" | סעיף: {clause['clause_number']}"
                    if clause.get('page_number'):
                        citation_text += f" | עמוד: {clause['page_number']}"
                    if citation.get('confidence'):
                        citation_text += f" | ביטחון: {citation['confidence']}"
                    
                    story.append(Paragraph(citation_text, styles['HebrewBody']))
                    
                    # Show clause text if available
                    if clause.get('clause_text'):
                        clause_preview = clause['clause_text'][:200] + '...'
                        story.append(Paragraph(
                            f'<i>{clause_preview}</i>',
                            styles['HebrewBody']
                        ))
                
                story.append(Spacer(1, 0.3*cm))
            
            # Regulation citations
            regulation_citations = [c for c in citations if c.get('citation_type') == 'regulation']
            if regulation_citations:
                story.append(Paragraph('<b>הפניה לתקנים:</b>', styles['HebrewBody']))
                
                for citation in regulation_citations:
                    regulation = citation.get('regulation', {})
                    
                    reg_text = "• "
                    if regulation.get('standard_id'):
                        reg_text += f"{regulation['standard_id']}"
                    elif regulation.get('law_id'):
                        reg_text += f"{regulation['law_id']}"
                    
                    if regulation.get('title'):
                        reg_text += f" - {regulation['title']}"
                    
                    if regulation.get('section'):
                        reg_text += f" | {regulation['section']}"
                    
                    if citation.get('confidence'):
                        reg_text += f" | ביטחון: {citation['confidence']}"
                    
                    story.append(Paragraph(reg_text, styles['HebrewBody']))
                
                story.append(Spacer(1, 0.3*cm))
            
            story.append(Spacer(1, 0.5*cm))
        
        return story
    
    def _build_audit_appendix(self, data: Dict, styles) -> List:
        """Build audit trail appendix with evidence integrity metadata"""
        story = []
        
        story.append(Paragraph('נספח ראיות ועקבות ביקורת', styles['HebrewSection']))
        story.append(Spacer(1, 0.5*cm))
        
        # Document uploads audit
        documents = data.get('documents', [])
        if documents:
            story.append(Paragraph('<b>מסמכים שהועלו:</b>', styles['HebrewBody']))
            story.append(Spacer(1, 0.3*cm))
            
            doc_table_data = [
                ['מסמך', 'תאריך העלאה', 'מעלה', 'Checksum (SHA-256)']
            ]
            
            for doc in documents:
                doc_table_data.append([
                    doc.get('filename', '')[:30],
                    doc.get('uploaded_at', '')[:10],
                    doc.get('uploader_name', 'N/A'),
                    doc.get('checksum', '')[:16] + '...'
                ])
            
            doc_table = Table(doc_table_data, colWidths=[5*cm, 3*cm, 3*cm, 5*cm])
            doc_table.setStyle(TableStyle([
                ('FONT', (0, 0), (-1, 0), 'HebrewFont-Bold', 9),
                ('FONT', (0, 1), (-1, -1), 'HebrewFont', 8),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_NAVY),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white)
            ]))
            story.append(doc_table)
            story.append(Spacer(1, 0.5*cm))
        
        # Reviewer approvals audit
        approvals = data.get('approvals', [])
        if approvals:
            story.append(Paragraph('<b>אישורי בודק:</b>', styles['HebrewBody']))
            story.append(Spacer(1, 0.3*cm))
            
            for approval in approvals:
                approval_text = f"• {approval.get('action', '')} על ידי {approval.get('reviewer_name', '')} ב-{approval.get('timestamp', '')[:16]}"
                story.append(Paragraph(approval_text, styles['HebrewBody']))
            
            story.append(Spacer(1, 0.5*cm))
        
        # Report generation metadata
        report_meta = data.get('report_meta', {})
        story.append(Paragraph('<b>מטא-דאטה של הדוח:</b>', styles['HebrewBody']))
        story.append(Spacer(1, 0.3*cm))
        
        meta_items = [
            f"• תאריך יצירת דוח: {report_meta.get('report_date', 'לא ידוע')}",
            f"• תאריך ביקור: {report_meta.get('inspection_date', 'לא ידוע')}",
            f"• בודק: {report_meta.get('inspector_name', 'לא ידוע')}",
            f"• מזמין: {report_meta.get('client_name', 'לא ידוע')}"
        ]
        
        for item in meta_items:
            story.append(Paragraph(item, styles['HebrewBody']))
        
        story.append(Spacer(1, 0.5*cm))
        
        # Integrity declaration
        integrity_text = (
            'כל המסמכים והראיות המצורפים לדוח זה מאוחסנים עם חתימה דיגיטלית (SHA-256 checksum) '
            'ונשמרים ברישום ביקורת בלתי ניתן לשינוי. '
            'כל שינוי במסמך מקורי יגרום לאי-התאמה של ה-checksum וידווח באופן אוטומטי.'
        )
        story.append(Paragraph(f'<i>{integrity_text}</i>', styles['HebrewBody']))
        
        return story
    
    def _build_closing_section(self, data: Dict, styles) -> List:
        """Build closing notes and inspector declaration"""
        story = []
        meta = data.get('report_meta', {})
        
        story.append(Paragraph('הערות להערכה כספית', styles['HebrewSection']))
        
        notes = data.get('closing_notes', [])
        for note in notes:
            story.append(Paragraph(f'• {note}', styles['HebrewBody']))
        
        story.append(Spacer(1, 1*cm))
        
        # Inspector declaration
        declaration = (
            'הנני מצהיר בזאת כי אין לי כל עניין אישי בנכס הנדון וכי הערכה זו נעשה עפ"י מיטב '
            'ידיעתי, הבנתי, וניסיוני המקצועי.'
        )
        story.append(Paragraph(declaration, styles['HebrewBody']))
        story.append(Spacer(1, 0.5*cm))
        
        story.append(Paragraph(
            f"בכבוד רב, {meta.get('inspector_name', '')}",
            styles['HebrewBody']
        ))
        story.append(Paragraph(
            meta.get('company_name', ''),
            styles['HebrewBody']
        ))
        
        return story