#!/usr/bin/env python3
"""
PDF Production Gate - P0 Blocker Tests
Generate real PDFs from database inspections
"""

import sys
import os
import asyncio
import json
from datetime import datetime

sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from services.enhanced_pdf_service_v2 import EnhancedPDFService

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

async def find_inspections_by_size():
    """Find small, medium, and large inspections from DB"""
    inspections = await db.inspections.find({}, {'_id': 0}).to_list(1000)
    
    # Calculate size (number of findings) for each
    sized_inspections = []
    
    for inspection in inspections:
        rooms = await db.rooms.find({'inspection_id': inspection['id']}, {'_id': 0}).to_list(1000)
        
        total_findings = 0
        for room in rooms:
            findings_count = await db.findings.count_documents({'room_id': room['id']})
            total_findings += findings_count
        
        sized_inspections.append({
            'inspection': inspection,
            'findings_count': total_findings
        })
    
    # Sort by findings count
    sized_inspections.sort(key=lambda x: x['findings_count'])
    
    # Select small, medium, large
    result = {
        'small': None,
        'medium': None,
        'large': None
    }
    
    if len(sized_inspections) >= 1:
        result['small'] = sized_inspections[0]['inspection']
    
    if len(sized_inspections) >= 2:
        mid_idx = len(sized_inspections) // 2
        result['medium'] = sized_inspections[mid_idx]['inspection']
    
    if len(sized_inspections) >= 3:
        result['large'] = sized_inspections[-1]['inspection']
    
    return result

async def generate_production_pdfs():
    """Generate PDFs from real database inspections"""
    print("="*60)
    print("PDF Production Gate - Real Data Generation")
    print("="*60)
    print()
    
    # Initialize PDF service
    pdf_service = EnhancedPDFService()
    
    # Find suitable inspections
    print("[1/3] Finding inspections in database...")
    inspections = await find_inspections_by_size()
    
    results = []
    
    for size_label, inspection in inspections.items():
        if not inspection:
            print(f"  ⚠ No {size_label} inspection found")
            continue
        
        inspection_id = inspection['id']
        print(f"\\n[2/3] Generating {size_label.upper()} PDF for inspection: {inspection_id}")
        
        # Get findings count
        rooms = await db.rooms.find({'inspection_id': inspection_id}, {'_id': 0}).to_list(1000)
        findings_count = 0
        for room in rooms:
            findings_count += await db.findings.count_documents({'room_id': room['id']})
        
        print(f"  - Property: {inspection.get('property_id')}")
        print(f"  - Status: {inspection.get('status')}")
        print(f"  - Findings: {findings_count}")
        
        try:
            # Generate PDF
            pdf_url = await pdf_service.generate_inspection_report(db, inspection_id)
            
            # Get file size
            pdf_filename = f"inspection_{inspection_id}.pdf"
            pdf_path = os.path.join('/app/backend/reports', pdf_filename)
            
            if os.path.exists(pdf_path):
                file_size = os.path.getsize(pdf_path)
                print(f"  ✓ Generated: {pdf_filename} ({file_size / 1024:.1f} KB)")
                
                results.append({
                    'size_category': size_label,
                    'inspection_id': inspection_id,
                    'findings_count': findings_count,
                    'pdf_filename': pdf_filename,
                    'file_size_kb': round(file_size / 1024, 1),
                    'status': 'success'
                })
            else:
                print(f"  ✗ PDF file not found: {pdf_filename}")
                results.append({
                    'size_category': size_label,
                    'inspection_id': inspection_id,
                    'status': 'file_not_found'
                })
        
        except Exception as e:
            print(f"  ✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append({
                'size_category': size_label,
                'inspection_id': inspection_id,
                'status': 'error',
                'error': str(e)
            })
    
    # Save results
    results_file = '/app/backend/reports/production_gate_results.json'
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'total_generated': len([r for r in results if r.get('status') == 'success']),
            'results': results
        }, f, ensure_ascii=False, indent=2)
    
    print("\\n" + "="*60)
    print("✓ Production PDF Generation Complete")
    print("="*60)
    print(f"\\nResults saved to: {results_file}")
    print(f"Generated PDFs location: /app/backend/reports/")
    print()
    
    # Print summary
    print("Summary:")
    for result in results:
        if result.get('status') == 'success':
            print(f"  ✓ {result['size_category'].upper()}: {result['pdf_filename']} "
                  f"({result['findings_count']} findings, {result['file_size_kb']} KB)")
        else:
            print(f"  ✗ {result['size_category'].upper()}: {result.get('status')}")
    
    print()
    
    client.close()

if __name__ == '__main__':
    asyncio.run(generate_production_pdfs())
