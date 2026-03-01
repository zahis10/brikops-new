import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from services.pdf_template_service import HebrewPDFTemplate

logger = logging.getLogger(__name__)

class EnhancedPDFService:
    """Enhanced PDF service using the new Hebrew RTL template"""
    
    def __init__(self):
        self.template = HebrewPDFTemplate()
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports')
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def generate_inspection_report(self, db, inspection_id: str) -> str:
        """Generate PDF report for inspection using new template
        
        Args:
            db: MongoDB database instance
            inspection_id: Inspection ID
            
        Returns:
            URL path to generated PDF
        """
        try:
            # Fetch inspection data
            inspection = await db.inspections.find_one({'id': inspection_id}, {'_id': 0})
            if not inspection:
                raise ValueError('Inspection not found')
            
            property_data = await db.properties.find_one({'id': inspection['property_id']}, {'_id': 0})
            tenant = await db.users.find_one({'id': inspection['tenant_id']}, {'_id': 0})
            
            # Fetch rooms and findings
            rooms = await db.rooms.find({'inspection_id': inspection_id}, {'_id': 0}).to_list(1000)
            
            all_findings = []
            categories_count = {}
            
            for room in rooms:
                findings = await db.findings.find({'room_id': room['id']}, {'_id': 0}).to_list(1000)
                
                for finding in findings:
                    # Get category
                    category = finding.get('category', 'Unknown')
                    categories_count[category] = categories_count.get(category, 0) + 1
                    
                    # Build finding data
                    finding_data = {
                        'id': finding['id'],
                        'category': self._translate_category(category),
                        'location': room.get('name', ''),
                        'recommendation': finding.get('description', ''),
                        'standard_ref': 'תקן 1918',
                        'unit': 'קומפ\'',
                        'qty': 1,
                        'unit_price': self._estimate_cost(finding.get('severity', 'low')),
                        'total_price': self._estimate_cost(finding.get('severity', 'low'))
                    }
                    all_findings.append(finding_data)
            
            # Calculate financial summary
            subtotal = sum(f['total_price'] for f in all_findings)
            supervision_pct = 10
            supervision_amt = subtotal * supervision_pct / 100
            before_vat = subtotal + supervision_amt
            vat_pct = 18
            vat_amt = before_vat * vat_pct / 100
            grand_total = before_vat + vat_amt
            
            # Build categories summary
            categories_summary = [
                {
                    'category_name': self._translate_category(cat),
                    'count': count
                }
                for cat, count in categories_count.items()
            ]
            
            # Build complete report data
            report_data = {
                'report_meta': {
                    'report_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    'inspection_date': inspection.get('created_at', '')[:10],
                    'client_name': tenant.get('name', ''),
                    'inspector_name': 'צחי שמי',
                    'company_name': 'צע שמי יזמות בע״מ'
                },
                'contact_info': {
                    'email': 'zahis10@gmail.com',
                    'phone': '0507569991',
                    'address': 'יא\' הספורטאים 26, באר שבע',
                    'company_name': 'צע שמי יזמות בע״מ'
                },
                'property_details': {
                    'address': property_data.get('address', ''),
                    'apt_number': property_data.get('apt_number', ''),
                    'property_type': 'דירת מגורים',
                    'rooms_count': len(rooms),
                    'occupied': False,
                    'electricity': True,
                    'water': True
                },
                'categories_summary': categories_summary,
                'findings': all_findings,
                'financial_summary': {
                    'subtotal': subtotal,
                    'supervision_pct': supervision_pct,
                    'supervision_amount': supervision_amt,
                    'before_vat': before_vat,
                    'vat_pct': vat_pct,
                    'vat_amount': vat_amt,
                    'grand_total': grand_total
                },
                'closing_notes': [
                    'המחירים מבוססים על הערכה ראשונית',
                    'תיקונים יבוצעו על ידי קבלן מוסמך',
                    'ממולץ לבצע בדיקה מקיפה לאחר התיקונים'
                ]
            }
            
            # Generate PDF
            filename = f"inspection_{inspection_id}.pdf"
            pdf_path = self.template.generate_report(report_data, filename)
            
            logger.info(f'Generated inspection report: {pdf_path}')
            return f"/reports/{filename}"
        
        except Exception as e:
            logger.error(f'Failed to generate report: {str(e)}')
            raise
    
    def _translate_category(self, category_en: str) -> str:
        """Translate category to Hebrew"""
        translations = {
            'wall_damage': 'נזקי קיר',
            'floor_issue': 'בעיות ריצוף',
            'ceiling_stain': 'כתמים בתקרה',
            'fixture_damage': 'נזקי אביזרים',
            'cleanliness': 'ניקיון',
            'door_issue': 'בעיות דלתות',
            'window_issue': 'בעיות חלונות',
            'electrical': 'חשמל',
            'plumbing': 'אינסטלציה'
        }
        return translations.get(category_en, category_en)
    
    def _estimate_cost(self, severity: str) -> float:
        """Estimate repair cost based on severity"""
        cost_map = {
            'low': 300,
            'medium': 600,
            'high': 1200
        }
        return cost_map.get(severity, 500)