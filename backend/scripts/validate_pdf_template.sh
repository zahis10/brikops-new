#!/bin/bash

# PDF Template Sprint - Test and Validation Script

set -e

echo "=========================================="
echo "BedekPro PDF Template Sprint - Validation"
echo "=========================================="
echo ""

# Navigate to backend
cd /app/backend

echo "[1/4] Checking dependencies..."
python3 -c "import reportlab; import PIL; print('  ✓ ReportLab and Pillow installed')" || {
    echo "  ✗ Missing dependencies"
    exit 1
}

echo ""
echo "[2/4] Validating JSON schema..."
if [ -f "/app/backend/schemas/report_schema.json" ]; then
    python3 << 'EOF'
import json
with open('/app/backend/schemas/report_schema.json') as f:
    schema = json.load(f)
    print(f"  ✓ Schema loaded successfully")
    print(f"  ✓ Required fields: {', '.join(schema.get('required', []))}")
EOF
else
    echo "  ✗ Schema file not found"
    exit 1
fi

echo ""
echo "[3/4] Generating demo reports..."
python3 /app/backend/scripts/generate_demo_reports.py

echo ""
echo "[4/4] Verifying output files..."
for scenario in short medium long; do
    json_file="/app/backend/reports/demo_report_${scenario}.json"
    pdf_file="/app/backend/reports/demo_report_${scenario}.pdf"
    
    if [ -f "$json_file" ]; then
        size=$(stat -f%z "$json_file" 2>/dev/null || stat -c%s "$json_file" 2>/dev/null || echo "0")
        echo "  ✓ ${scenario} JSON: ${size} bytes"
    else
        echo "  ✗ ${scenario} JSON: not found"
    fi
    
    if [ -f "$pdf_file" ]; then
        size=$(stat -f%z "$pdf_file" 2>/dev/null || stat -c%s "$pdf_file" 2>/dev/null || echo "0")
        echo "  ✓ ${scenario} PDF: ${size} bytes"
    else
        echo "  ✗ ${scenario} PDF: not found"
    fi
done

echo ""
echo "=========================================="
echo "✓ PDF Template Sprint Validation Complete"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review generated PDFs in /app/backend/reports/"
echo "2. Compare with sample PDF visually"
echo "3. Test with real inspection data"
echo ""