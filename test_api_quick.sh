#!/usr/bin/env bash
# Quick curl tests for invoice extraction endpoints

BASE_URL="http://localhost:8000"

echo "========================================"
echo "Invoice Extraction API - Quick Tests"
echo "========================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Determine which JSON formatter to use
if command -v python3 &> /dev/null; then
    JSON_FORMATTER="python3 -m json.tool"
elif command -v python &> /dev/null; then
    JSON_FORMATTER="python -m json.tool"
elif command -v jq &> /dev/null; then
    JSON_FORMATTER="jq ."
else
    JSON_FORMATTER="cat"
fi

# Test 1: Health check
echo -e "${YELLOW}Test 1: Health Check${NC}"
curl -s -X GET "$BASE_URL/health" | $JSON_FORMATTER
echo ""

# Test 2: Validate invoice data (no API key needed)
echo -e "${YELLOW}Test 2: Validate Invoice Data (Valid)${NC}"
curl -s -X GET "$BASE_URL/api/v1/invoices/validate?nr_factura=FAC-2024-001234&data=15.03.2024&furnizor=SC%20EXAMPLE%20SRL&CUI=1234567890&total=238.00&TVA=38.00" \
  | $JSON_FORMATTER
echo ""

# Test 3: Validate with invalid CUI
echo -e "${YELLOW}Test 3: Validate Invoice Data (Invalid CUI - Non-numeric)${NC}"
curl -s -X GET "$BASE_URL/api/v1/invoices/validate?nr_factura=FAC-2024-001234&data=15.03.2024&furnizor=SC%20EXAMPLE%20SRL&CUI=ABC-NOT-DIGITS&total=238.00&TVA=38.00" \
  | $JSON_FORMATTER
echo ""

# Test 4: Validate with TVA > Total
echo -e "${YELLOW}Test 4: Validate Invoice Data (Invalid TVA > Total)${NC}"
curl -s -X GET "$BASE_URL/api/v1/invoices/validate?nr_factura=FAC-2024-001234&data=15.03.2024&furnizor=SC%20EXAMPLE%20SRL&CUI=1234567890&total=100.00&TVA=150.00" \
  | $JSON_FORMATTER
echo ""

# Test 5: Extract from file (if provided)
if [ -f "invoice.png" ]; then
    echo -e "${YELLOW}Test 5: Extract Invoice from File (invoice.png)${NC}"
    echo "Note: Requires OPENAI_API_KEY to be set in .env"
    curl -s -X POST "$BASE_URL/api/v1/invoices/extract" \
      -F "file=@invoice.png" \
      -F "language=ro" \
      | $JSON_FORMATTER
    echo ""
else
    echo -e "${YELLOW}Test 5: Extract Invoice from File${NC}"
    echo -e "${RED}⚠️  No invoice.png found in current directory${NC}"
    echo "   Place an invoice image as 'invoice.png' to test"
    echo ""
fi

# Test 6: Extract from URL (example)
echo -e "${YELLOW}Test 6: Extract Invoice from URL (Example)${NC}"
echo "Syntax: curl -X POST 'http://localhost:8000/api/v1/invoices/extract-url?image_url=https://example.com/invoice.png&language=ro'"
echo ""

# Test 7: Batch extract (if multiple files exist)
INVOICE_FILES=$(ls invoice*.png 2>/dev/null | wc -l)
if [ "$INVOICE_FILES" -gt 1 ]; then
    echo -e "${YELLOW}Test 7: Batch Extract Multiple Invoices${NC}"
    echo "Note: Requires OPENAI_API_KEY to be set in .env"
    
    # Build form data with multiple files
    CURL_CMD="curl -s -X POST '$BASE_URL/api/v1/invoices/batch-extract' -F 'language=ro'"
    for file in invoice*.png; do
        CURL_CMD="$CURL_CMD -F 'files=@$file'"
    done
    
    eval $CURL_CMD | $JSON_FORMATTER
    echo ""
else
    echo -e "${YELLOW}Test 7: Batch Extract Multiple Invoices${NC}"
    echo -e "${RED}⚠️  Less than 2 invoice files found${NC}"
    echo "   Create multiple invoice*.png files to test batch extraction"
    echo ""
fi

echo "========================================"
echo "💡 Notes:"
echo "========================================"
echo ""
echo "✅ Test 1: Health Check"
echo "   - API is running and healthy"
echo ""
echo "✅ Test 2-4: Validation endpoint (GET)"
echo "   - Query parameters: nr_factura, data, furnizor, CUI, total, TVA"
echo "   - Items array is not required for simple validation"
echo ""
echo "📋 Full Validation Endpoint:"
echo "   - POST /api/v1/invoices/validate-full (accepts JSON with items)"
echo "   - Validates complete invoice including line items"
echo "   - Use: python3 test_extended.py"
echo ""
echo "📄 Test 5: File Extraction"
echo "   - Place an invoice image as 'invoice.png' to test"
echo "   - Requires OPENAI_API_KEY in .env"
echo ""
echo "🔗 Test 6: URL Extraction"
echo "   - Replace image_url with actual invoice URL"
echo "   - Requires OPENAI_API_KEY in .env"
echo ""
echo "📚 Test 7: Batch Extraction"
echo "   - Create multiple invoice files (invoice1.png, invoice2.png, etc.)"
echo "   - Requires OPENAI_API_KEY in .env"
echo ""
echo "========================================"
echo "✅ Quick test suite completed"
echo "========================================"
echo ""
echo "🚀 Next Steps:"
echo "  1. Set OPENAI_API_KEY: export OPENAI_API_KEY='your-key'"
echo "  2. For comprehensive tests: python3 test_extended.py"
echo "  3. Place invoice images in current directory"
echo ""
echo "📖 Full Documentation:"
echo "  - cat INVOICE_EXTRACTION.md"
echo "  - cat NV-006_README.md"
echo ""
