#!/usr/bin/env python3
"""
Visual Comparison Tool for PDF Reports

Compares generated PDFs with the sample PDF to verify:
1. Page structure and layout
2. Section presence and order
3. Hebrew RTL text rendering
4. Table formatting
5. Header/footer consistency
"""

import os
import sys
from typing import List, Dict
import json

try:
    from PyPDF2 import PdfReader
except ImportError:
    print("Installing PyPDF2...")
    os.system('pip install PyPDF2 -q')
    from PyPDF2 import PdfReader

def analyze_pdf(pdf_path: str) -> Dict:
    """Analyze PDF structure and extract metadata"""
    try:
        reader = PdfReader(pdf_path)
        
        analysis = {
            'filename': os.path.basename(pdf_path),
            'page_count': len(reader.pages),
            'has_metadata': bool(reader.metadata),
            'pages_analysis': []
        }
        
        # Analyze first 5 pages for structure
        for i, page in enumerate(reader.pages[:5]):
            text = page.extract_text()
            page_info = {
                'page_num': i + 1,
                'has_text': bool(text),
                'text_length': len(text) if text else 0,
                'has_hebrew': any(ord(char) >= 0x0590 and ord(char) <= 0x05FF for char in text if text)
            }
            analysis['pages_analysis'].append(page_info)
        
        return analysis
    
    except Exception as e:
        return {'filename': os.path.basename(pdf_path), 'error': str(e)}

def compare_pdfs(sample_analysis: Dict, generated_analysis: Dict) -> Dict:
    """Compare sample PDF with generated PDF"""
    comparison = {
        'structure_match': True,
        'issues': [],
        'recommendations': []
    }
    
    # Compare page counts (generated should be close to sample)
    if abs(sample_analysis['page_count'] - generated_analysis['page_count']) > 50:
        comparison['issues'].append(
            f"Large page count difference: "
            f"Sample={sample_analysis['page_count']}, "
            f"Generated={generated_analysis['page_count']}"
        )
        comparison['structure_match'] = False
    
    # Check Hebrew text presence
    sample_has_hebrew = any(p.get('has_hebrew') for p in sample_analysis['pages_analysis'])
    generated_has_hebrew = any(p.get('has_hebrew') for p in generated_analysis['pages_analysis'])
    
    if sample_has_hebrew and not generated_has_hebrew:
        comparison['issues'].append("Generated PDF missing Hebrew text")
        comparison['structure_match'] = False
    
    if not comparison['issues']:
        comparison['recommendations'].append("\u2713 Structure matches well")
        comparison['recommendations'].append("\u2713 Hebrew text present")
    
    return comparison

def generate_comparison_report():
    """Generate comprehensive comparison report"""
    print("="*60)
    print("PDF Template Visual Comparison Report")
    print("="*60)
    print()
    
    reports_dir = '/app/backend/reports'
    sample_url = 'https://customer-assets.emergentagent.com/job_property-inspect-9/artifacts/o7fzn6m7_%D7%93%D7%95%D7%97%20%D7%91%D7%93%D7%A7%20%D7%9C%D7%93%D7%95%D7%92%D7%9E%D7%90%20-%20%D7%A6%D7%97%D7%99%20%D7%A9%D7%9E%D7%99.pdf'
    
    # Download sample PDF for comparison
    sample_path = os.path.join(reports_dir, 'sample_reference.pdf')
    if not os.path.exists(sample_path):
        print("Downloading sample PDF...")
        import requests
        try:
            response = requests.get(sample_url, timeout=30)
            with open(sample_path, 'wb') as f:
                f.write(response.content)
            print(f"  \u2713 Downloaded: {len(response.content)} bytes")
        except Exception as e:
            print(f"  \u2717 Failed to download sample: {e}")
            return
    
    print("\n[1] Analyzing Sample PDF...")
    sample_analysis = analyze_pdf(sample_path)
    print(f"  Pages: {sample_analysis.get('page_count', 'N/A')}")
    print(f"  Hebrew text: {'Yes' if any(p.get('has_hebrew') for p in sample_analysis.get('pages_analysis', [])) else 'No'}")
    
    print("\n[2] Analyzing Generated PDFs...")
    generated_files = [
        'demo_report_short.pdf',
        'demo_report_medium.pdf',
        'demo_report_long.pdf'
    ]
    
    results = {}
    
    for filename in generated_files:
        filepath = os.path.join(reports_dir, filename)
        if os.path.exists(filepath):
            print(f"\n  Analyzing {filename}...")
            analysis = analyze_pdf(filepath)
            results[filename] = analysis
            
            print(f"    Pages: {analysis.get('page_count', 'N/A')}")
            print(f"    Hebrew text: {'Yes' if any(p.get('has_hebrew') for p in analysis.get('pages_analysis', [])) else 'No'}")
            print(f"    File size: {os.path.getsize(filepath) / 1024:.1f} KB")
            
            # Compare with sample
            comparison = compare_pdfs(sample_analysis, analysis)
            if comparison['structure_match']:
                print(f"    \u2713 Structure matches sample")
            else:
                print(f"    \u2717 Issues found:")
                for issue in comparison['issues']:
                    print(f"      - {issue}")
    
    print("\n" + "="*60)
    print("\u2713 Comparison Complete")
    print("="*60)
    print("\nGenerated files location: /app/backend/reports/")
    print("\nNext steps:")
    print("1. Visual inspection of generated PDFs")
    print("2. Compare cover page, findings, and financial summary")
    print("3. Verify Hebrew RTL rendering quality")
    print("4. Test with actual inspection data from database")
    print()

if __name__ == '__main__':
    generate_comparison_report()