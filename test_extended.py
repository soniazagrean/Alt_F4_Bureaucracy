#!/usr/bin/env python3
"""
Extended test suite for invoice extraction with proper validation examples.
Requires the FastAPI server to be running on http://localhost:8000
"""

import json
from pathlib import Path
import requests
from decimal import Decimal


def test_validation_with_items():
    """Test invoice data validation with items included."""
    print("\n" + "="*60)
    print("Test: Invoice Data Validation WITH Items")
    print("="*60)
    
    # Use POST request with JSON data including items
    invoice_data = {
        "nr_factura": "FAC-2024-001234",
        "data": "15.03.2024",
        "furnizor": "SC EXAMPLE SRL",
        "CUI": "1234567890",
        "IBAN": "RO12ABNA1234567890123456",
        "items": [
            {
                "description": "Product A",
                "quantity": 2.0,
                "unit": "buc",
                "unit_price": "100.00",
                "total_price": "200.00"
            }
        ],
        "total": "238.00",
        "TVA": "38.00"
    }
    
    print("\n📝 Validating:")
    print(json.dumps(invoice_data, indent=2))
    
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/invoices/validate-full",
            json=invoice_data
        )
        
        result = response.json()
        print(f"\n📊 Result (Status {response.status_code}):")
        print(json.dumps(result, indent=2))
        
        if result.get("success"):
            print("\n✅ Validation PASSED")
        else:
            print(f"\n⚠️  Validation FAILED")
                
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API on port 8000")
        print("   Make sure to start the server: python -m uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


def test_invalid_invoice():
    """Test validation with invalid invoice data."""
    print("\n" + "="*60)
    print("Test: Invalid Invoice Data (TVA > Total)")
    print("="*60)
    
    invalid_invoice = {
        "nr_factura": "FAC-2024-001234",
        "data": "15.03.2024",
        "furnizor": "SC EXAMPLE SRL",
        "CUI": "1234567890",
        "items": [
            {
                "description": "Product A",
                "quantity": 1.0,
                "unit": "buc",
                "unit_price": "100.00",
                "total_price": "100.00"
            }
        ],
        "total": "100.00",
        "TVA": "150.00"  # Invalid: TVA > total
    }
    
    print("\n📝 Attempting to validate invalid invoice:")
    print(f"   Total: {invalid_invoice['total']}")
    print(f"   TVA: {invalid_invoice['TVA']} (❌ TVA > Total)")
    
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/invoices/validate-full",
            json=invalid_invoice
        )
        
        result = response.json()
        
        if not result.get("success"):
            print(f"\n✅ Correctly rejected:")
            error_msg = result.get('message', 'Unknown error')
            # Display first line of error
            print(f"   Error: {error_msg.split(chr(10))[0]}")
        else:
            print("\n⚠️  Should have failed validation!")
                
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


def test_cui_validation():
    """Test CUI validation with various formats."""
    print("\n" + "="*60)
    print("Test: CUI Validation")
    print("="*60)
    
    test_cases = [
        ("1234567890", True, "Valid: 10 digits"),
        ("123456789", True, "Valid: 9 digits"),
        ("12345678", True, "Valid: 8 digits"),
        ("ABC1234567", False, "Invalid: Contains letters"),
        ("123456", False, "Invalid: Too short (6 digits)"),
        ("12345678901", False, "Invalid: Too long (11 digits)"),
    ]
    
    base_invoice = {
        "nr_factura": "FAC-2024-TEST",
        "data": "15.03.2024",
        "furnizor": "TEST COMPANY",
        "IBAN": "RO12ABNA1234567890123456",
        "items": [{"description": "Test", "quantity": 1, "unit": "buc", "unit_price": "100", "total_price": "100"}],
        "total": "100.00",
        "TVA": "0.00"
    }
    
    try:
        for cui, should_pass, description in test_cases:
            test_invoice = {**base_invoice, "CUI": cui}
            
            response = requests.post(
                "http://localhost:8000/api/v1/invoices/validate-full",
                json=test_invoice
            )
            
            result = response.json()
            is_valid = result.get("success", False)
            
            status = "✅" if (is_valid == should_pass) else "❌"
            print(f"\n{status} CUI: {cui}")
            print(f"   {description}")
            print(f"   Result: {'VALID' if is_valid else 'INVALID'}")
                
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


def test_date_parsing():
    """Test date format parsing."""
    print("\n" + "="*60)
    print("Test: Date Format Parsing")
    print("="*60)
    
    date_formats = [
        ("15.03.2024", "DD.MM.YYYY"),
        ("15/03/2024", "DD/MM/YYYY"),
        ("15-03-2024", "DD-MM-YYYY"),
        ("2024-03-15", "YYYY-MM-DD"),
    ]
    
    base_invoice = {
        "nr_factura": "FAC-2024-TEST",
        "furnizor": "TEST COMPANY",
        "CUI": "1234567890",
        "items": [{"description": "Test", "quantity": 1, "unit": "buc", "unit_price": "100", "total_price": "100"}],
        "total": "100.00",
        "TVA": "0.00"
    }
    
    try:
        for date_str, format_name in date_formats:
            test_invoice = {**base_invoice, "data": date_str}
            
            response = requests.post(
                "http://localhost:8000/api/v1/invoices/validate-full",
                json=test_invoice
            )
            
            result = response.json()
            is_valid = result.get("success", False)
            
            status = "✅" if is_valid else "❌"
            print(f"\n{status} {format_name}: {date_str}")
            if is_valid:
                print(f"   ✅ Parsed successfully")
            else:
                error_msg = result.get('message', 'Unknown error')
                print(f"   ❌ Failed: {error_msg.split(chr(10))[0][:60]}")
                
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")


def test_extraction_endpoint():
    """Show how to use the extraction endpoint."""
    print("\n" + "="*60)
    print("Test: Invoice Extraction Endpoint")
    print("="*60)
    
    print("\n📋 How to use the extraction endpoint:")
    print("""
1. Place an invoice image (PNG/JPG) in the current directory
2. Run the extraction:
   
   curl -X POST "http://localhost:8000/api/v1/invoices/extract" \\
     -F "file=@invoice.png" \\
     -F "language=ro"

3. Response will be:
   {
       "success": true,
       "data": {
           "nr_factura": "...",
           "data": "...",
           "furnizor": "...",
           "CUI": "...",
           "items": [...],
           "total": "...",
           "TVA": "..."
       },
       "confidence": 0.92
   }

Requirements:
- OPENAI_API_KEY environment variable must be set
- Image must be PNG or JPG (max 10MB)
""")


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  Invoice Extraction - Extended Test Suite".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    # Run validation tests
    test_validation_with_items()
    test_invalid_invoice()
    test_cui_validation()
    test_date_parsing()
    
    # Show extraction endpoint
    test_extraction_endpoint()
    
    print("\n" + "="*60)
    print("✅ Extended test suite completed")
    print("="*60)
    print("""
📚 Next Steps:
   1. Review the test results above
   2. Add your invoice images to test extraction
   3. Set OPENAI_API_KEY environment variable
   4. Run ./test_api_quick.sh for quick API tests
   5. Read INVOICE_EXTRACTION.md for full documentation
    """)


if __name__ == "__main__":
    main()
