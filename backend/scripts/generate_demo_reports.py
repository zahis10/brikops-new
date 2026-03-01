import sys
import os
import json
from datetime import datetime

sys.path.insert(0, '/app/backend')

from services.pdf_template_service import HebrewPDFTemplate

def generate_demo_report(scenario='medium'):
    """
    Generate demo report for testing
    
    Args:
        scenario: 'short' (5 findings), 'medium' (15 findings), or 'long' (30 findings)
    """
    
    # Base findings templates
    findings_templates = [
        {
            'category': 'דלת כניסה',
            'location': 'מבואת כניסה',
            'recommendation': 'סדק קל במסגרת הדלת, יש לתקן',
            'standard_ref': 'תקן 466',
            'unit': 'קומפ\'',
            'qty': 1,
            'unit_price': 400,
            'total_price': 400
        },
        {
            'category': 'אביזרי חשמל',
            'location': 'סלון',
            'recommendation': 'שקע חשמל לא מושלם כראוי, יש להחליף',
            'standard_ref': 'תקן 1918',
            'unit': 'קומפ\'',
            'qty': 2,
            'unit_price': 200,
            'total_price': 400
        },
        {
            'category': 'עבודות טיח',
            'location': 'חדר שינה',
            'recommendation': 'סדקים בקיר, יש לתקן ולצבוע מחדש',
            'standard_ref': 'תקן 1918',
            'unit': 'מ׳ר',
            'qty': 3,
            'unit_price': 150,
            'total_price': 450
        },
        {
            'category': 'אלומיניום',
            'location': 'מרפסת',
            'recommendation': 'נעילת חלון לא תקינה, יש לתקן',
            'standard_ref': 'תקן 466',
            'unit': 'קומפ\'',
            'qty': 1,
            'unit_price': 350,
            'total_price': 350
        },
        {
            'category': 'ריצוף',
            'location': 'מטבח',
            'recommendation': 'אריח רופף, יש להחליף',
            'standard_ref': 'תקן 1918',
            'unit': 'מ׳ר',
            'qty': 2,
            'unit_price': 250,
            'total_price': 500
        }
    ]
    
    # Determine number of findings based on scenario
    scenario_counts = {
        'short': 5,
        'medium': 15,
        'long': 30
    }
    
    findings_count = scenario_counts.get(scenario, 15)
    
    # Generate findings by repeating templates
    findings = []
    for i in range(findings_count):
        template = findings_templates[i % len(findings_templates)].copy()
        template['id'] = f'finding_{i+1}'
        findings.append(template)
    
    # Calculate totals
    subtotal = sum(f['total_price'] for f in findings)
    supervision_pct = 10
    supervision_amt = subtotal * supervision_pct / 100
    before_vat = subtotal + supervision_amt
    vat_pct = 18
    vat_amt = before_vat * vat_pct / 100
    grand_total = before_vat + vat_amt
    
    # Build categories summary
    categories = {}
    for f in findings:
        cat = f['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    categories_summary = [
        {'category_name': cat, 'count': count}
        for cat, count in categories.items()
    ]
    
    # Complete report data
    report_data = {
        'report_meta': {
            'report_date': datetime.now().strftime('%Y-%m-%d'),
            'inspection_date': '2024-02-15',
            'client_name': 'דוח לדוגמא - ' + scenario.upper(),
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
            'address': 'רחוב הרצל 15, תל אביב',
            'apt_number': '12',
            'property_type': 'דירת מגורים',
            'rooms_count': 4,
            'occupied': False,
            'electricity': True,
            'water': True
        },
        'categories_summary': categories_summary,
        'findings': findings,
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
            'המחירים מבוססים על מחירון שוק נוכחי',
            'תיקונים יבוצעו על ידי קבלן מוסמך',
            'ממולץ לבצע בדיקה מקיפה לאחר התיקונים'
        ]
    }
    
    return report_data

def main():
    """Generate all three demo scenarios"""
    print('Generating BedekPro demo reports...')
    
    template = HebrewPDFTemplate()
    
    scenarios = ['short', 'medium', 'long']
    
    for scenario in scenarios:
        print(f'\nGenerating {scenario} report...')
        
        # Generate report data
        report_data = generate_demo_report(scenario)
        
        # Save JSON
        json_filename = f'demo_report_{scenario}.json'
        with open(f'/app/backend/reports/{json_filename}', 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        print(f'  ✓ Saved JSON: {json_filename}')
        
        # Generate PDF
        pdf_filename = f'demo_report_{scenario}.pdf'
        try:
            pdf_path = template.generate_report(report_data, pdf_filename)
            print(f'  ✓ Generated PDF: {pdf_filename}')
        except Exception as e:
            print(f'  ✗ Error generating PDF: {str(e)}')
            import traceback
            traceback.print_exc()
    
    print('\n✓ Demo report generation complete!')
    print(f'\nOutput directory: /app/backend/reports/')

if __name__ == '__main__':
    main()