import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from services.pdf_template_service import HebrewPDFTemplate
from utils.image_processor import ImageProcessor

logger = logging.getLogger(__name__)

class EnhancedPDFService:
    """Enhanced PDF service with real image support and DB integration"""
    
    def __init__(self):
        self.template = HebrewPDFTemplate()
        self.image_processor = ImageProcessor()
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports')
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def generate_inspection_report(self, db, inspection_id: str) -> str:
        """Generate PDF report for inspection with real images from DB
        
        Args:
            db: MongoDB database instance
            inspection_id: Inspection ID
            
        Returns:
            URL path to generated PDF
        """
        try:
            logger.info(f'Generating report for inspection: {inspection_id}')
            
            # Fetch inspection data
            inspection = await db.inspections.find_one({'id': inspection_id}, {'_id': 0})
            if not inspection:
                raise ValueError('Inspection not found')
            
            property_data = await db.properties.find_one(
                {'id': inspection['property_id']},
                {'_id': 0}
            )
            tenant = await db.users.find_one(
                {'id': inspection['tenant_id']},
                {'_id': 0}
            )
            
            # Fetch rooms with media and findings
            rooms = await db.rooms.find(
                {'inspection_id': inspection_id},
                {'_id': 0}
            ).to_list(1000)
            
            all_findings = []
            categories_count = {}
            
            for room in rooms:
                # Get findings for this room
                findings = await db.findings.find(
                    {'room_id': room['id']},
                    {'_id': 0}
                ).to_list(1000)
                
                # Get media for this room
                media_assets = await db.media_assets.find(
                    {'room_id': room['id']},
                    {'_id': 0}
                ).to_list(1000)
                
                for finding in findings:
                    # Get category
                    category = finding.get('category', 'שונות')
                    categories_count[category] = categories_count.get(category, 0) + 1
                    
                    # Process images for this finding
                    images = []
                    for idx, media in enumerate(media_assets[:3]):  # Max 3 images per finding
                        # Use full backend URL for image access
                        backend_url = os.environ.get('REACT_APP_BACKEND_URL', '')
                        image_url = f"{backend_url}{media.get('file_url', '')}"
                        
                        # Process image
                        processed_path = self.image_processor.download_and_process_image(
                            image_url,
                            finding['id'],
                            idx
                        )
                        
                        if processed_path:
                            images.append({
                                'path': processed_path,
                                'caption': f"תמונה {idx + 1}"
                            })
                        else:
                            # Use fallback
                            fallback_path = self.image_processor.create_fallback_image(
                                'תמונה לא זמינה'
                            )
                            if fallback_path:
                                images.append({
                                    'path': fallback_path,
                                    'caption': 'תמונה לא זמינה'
                                })
                    
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
                        'total_price': self._estimate_cost(finding.get('severity', 'low')),
                        'images': images  # Real images included
                    }
                    all_findings.append(finding_data)
            
            # Calculate financial summary with rounding
            subtotal = round(sum(f['total_price'] for f in all_findings), 2)
            
            supervision_pct = 10
            supervision_amt = round(subtotal * supervision_pct / 100, 2)
            
            contingency_pct = 0  # Optional
            contingency_amt = round(subtotal * contingency_pct / 100, 2)
            
            before_vat = round(subtotal + supervision_amt + contingency_amt, 2)
            
            vat_pct = 18
            vat_amt = round(before_vat * vat_pct / 100, 2)
            
            grand_total = round(before_vat + vat_amt, 2)
            
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
                    'company_name': 'צע שמי יזמות בע״ם'
                },
                'contact_info': {
                    'email': 'zahis10@gmail.com',
                    'phone': '0507569991',
                    'address': 'יא\' הספורטאים 26, באר שבע',
                    'company_name': 'צע שמי יזמות בע״ם'
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
                    'contingency_pct': contingency_pct,
                    'contingency_amount': contingency_amt,
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
            
            filename = f"inspection_{inspection_id}.pdf"
            stored_ref = self.template.generate_report(report_data, filename)
            
            logger.info(f'Generated inspection report: {stored_ref}')
            return stored_ref
        
        except Exception as e:
            logger.error(f'Failed to generate report: {str(e)}')
            import traceback
            traceback.print_exc()
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
            'low': 300.0,
            'medium': 600.0,
            'high': 1200.0
        }
        return cost_map.get(severity, 500.0)