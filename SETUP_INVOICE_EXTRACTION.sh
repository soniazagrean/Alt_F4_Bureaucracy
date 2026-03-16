#!/usr/bin/env bash
# Quick setup guide for invoice extraction feature

echo "==============================================="
echo "Invoice Extraction (NV-006) - Setup Guide"
echo "==============================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating template..."
    cat > .env.example << 'EOF'
# Google Gemini API
GEMINI_API_KEY=your_google_api_key_here

# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=alt_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# Meilisearch
MEILI_HOST=localhost
MEILI_MASTER_KEY=super_secret_key
EOF
    echo "✅ Created .env.example"
    echo "📝 Copy to .env and add your GEMINI_API_KEY"
else
    echo "✅ .env file found"
fi

echo ""
echo "==============================================="
echo "1. Setup Steps"
echo "==============================================="
echo ""
echo "Step 1: Get Google Gemini API Key"
echo "   - Go to https://ai.google.dev/"
echo "   - Create API key"
echo "   - Add to .env: GEMINI_API_KEY=your_key"
echo ""

echo "Step 2: Install dependencies"
echo "   python -m pip install -r requirements.txt"
echo ""

echo "Step 3: Start the API server"
echo "   python -m uvicorn app.main:app --reload"
echo ""

echo "Step 4: Test the service"
echo "   python test_invoice_extraction.py"
echo ""

echo "==============================================="
echo "2. Quick API Test"
echo "==============================================="
echo ""
echo "Test validation endpoint (no API key needed):"
echo ""
echo 'curl -X GET "http://localhost:8000/api/v1/invoices/validate?nr_factura=FAC-001&data=15.03.2024&furnizor=SC%20EXAMPLE&CUI=1234567890&total=100&TVA=19"'
echo ""

echo "==============================================="
echo "3. Extract Invoice (requires API key)"
echo "==============================================="
echo ""
echo "Place invoice.png in current directory, then:"
echo ""
echo 'curl -X POST "http://localhost:8000/api/v1/invoices/extract" \'
echo '  -F "file=@invoice.png" \'
echo '  -F "language=ro"'
echo ""

echo "==============================================="
echo "4. Available Endpoints"
echo "==============================================="
echo ""
echo "📌 Extract from file:"
echo "   POST /api/v1/invoices/extract"
echo ""
echo "📌 Extract from URL:"
echo "   POST /api/v1/invoices/extract-url"
echo ""
echo "📌 Validate data:"
echo "   GET /api/v1/invoices/validate"
echo ""
echo "📌 Batch extract:"
echo "   POST /api/v1/invoices/batch-extract"
echo ""

echo "==============================================="
echo "5. Documentation"
echo "==============================================="
echo ""
echo "📖 Full documentation: INVOICE_EXTRACTION.md"
echo "📖 Completion report: NV-006_COMPLETION.md"
echo "🧪 Test examples: test_invoice_extraction.py"
echo ""

echo "==============================================="
echo "✅ Setup guide complete!"
echo "==============================================="
