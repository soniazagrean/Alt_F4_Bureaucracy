#!/usr/bin/env python3
"""
Example script demonstrating invoice extraction functionality.
Run this to test the invoice extraction service.
"""

import asyncio
import httpx
import json
from pathlib import Path


async def test_extract_invoice_from_file():
    """Test extracting invoice data from a file."""
    print("\n=== Test 1: Extract Invoice from File ===")
    
    # Note: Replace with actual invoice file path
    invoice_file = Path("sample_invoice.png")
    
    if not invoice_file.exists():
        print(f"⚠️  Sample file {invoice_file} not found. Skipping this test.")
        print("   Place a PNG/JPG invoice at the location above to test.")
        return
    
    try:
        async with httpx.AsyncClient() as client:
            with open(invoice_file, "rb") as f:
                files = {"file": (invoice_file.name, f, "image/png")}
                
                response = await client.post(
                    "http://localhost:8000/api/v1/invoices/extract",
                    files=files,
                    params={"language": "ro"}
                )
            
            result = response.json()
            
            print(f"Status Code: {response.status_code}")
            print(f"Response:")
            print(json.dumps(result, indent=2, default=str))
            
            if result.get("success"):
                data = result["data"]
                print(f"\n✅ Successfully extracted invoice:")
                print(f"   Invoice #: {data['nr_factura']}")
                print(f"   Date: {data['data']}")
                print(f"   Supplier: {data['furnizor']}")
                print(f"   Total: {data['total']} RON")
                print(f"   VAT: {data['TVA']} RON")
                print(f"   Confidence: {result.get('confidence', 'N/A')}")
            else:
                print(f"\n❌ Extraction failed:")
                print(f"   Errors: {result.get('errors')}")
                
    except httpx.ConnectError:
        print("❌ Cannot connect to API. Make sure the FastAPI server is running on port 8000")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


async def test_validate_invoice_data():
    """Test invoice data validation."""
    print("\n=== Test 2: Validate Invoice Data ===")
    
    # Test valid data
    print("\n📝 Testing valid invoice data:")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8000/api/v1/invoices/validate",
                params={
                    "nr_factura": "FAC-2024-001234",
                    "data": "15.03.2024",
                    "furnizor": "SC EXAMPLE SRL",
                    "CUI": "1234567890",
                    "total": 238.00,
                    "TVA": 38.00
                }
            )
            
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            
            if result.get("success"):
                print("✅ Valid invoice data")
            else:
                print(f"⚠️  Validation failed: {result.get('message')}")
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    # Test invalid data (VAT > total)
    print("\n📝 Testing invalid invoice data (TVA > total):")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:8000/api/v1/invoices/validate",
                params={
                    "nr_factura": "FAC-2024-001234",
                    "data": "15.03.2024",
                    "furnizor": "SC EXAMPLE SRL",
                    "CUI": "1234567890",
                    "total": 100.00,
                    "TVA": 150.00  # Invalid: TVA > total
                }
            )
            
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            
            if not result.get("success"):
                print("✅ Correctly rejected invalid data")
            else:
                print("⚠️  Should have rejected this data")
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")


async def test_extract_from_url():
    """Test extracting invoice data from a URL."""
    print("\n=== Test 3: Extract from URL ===")
    
    # Example URL (replace with actual invoice URL)
    invoice_url = "https://example.com/invoice.png"
    
    print(f"⚠️  This test requires a valid invoice URL.")
    print(f"   Example: {invoice_url}")
    print("   Replace URL and uncomment the code to test.")
    
    # Uncomment below to test with actual URL
    # try:
    #     async with httpx.AsyncClient() as client:
    #         response = await client.post(
    #             "http://localhost:8000/api/v1/invoices/extract-url",
    #             params={
    #                 "image_url": invoice_url,
    #                 "language": "ro"
    #             }
    #         )
    #     
    #         result = response.json()
    #         print(json.dumps(result, indent=2, default=str))
    # except Exception as e:
    #     print(f"❌ Error: {str(e)}")


async def test_batch_extract():
    """Test batch extraction of multiple invoices."""
    print("\n=== Test 4: Batch Extract Multiple Invoices ===")
    
    invoice_files = list(Path(".").glob("invoice*.png"))
    
    if not invoice_files:
        print("⚠️  No invoice files found (invoice*.png)")
        print("   Create test files and try again.")
        return
    
    print(f"Found {len(invoice_files)} invoice files for batch processing")
    
    try:
        async with httpx.AsyncClient() as client:
            files = [
                ("files", (f.name, open(f, "rb"), "image/png"))
                for f in invoice_files
            ]
            
            response = await client.post(
                "http://localhost:8000/api/v1/invoices/batch-extract",
                files=files,
                params={"language": "ro"}
            )
            
            result = response.json()
            print(f"\nBatch Results:")
            print(f"Total: {result['total']}")
            print(f"Successful: {result['successful']}")
            print(f"Failed: {result['total'] - result['successful']}")
            
            for item in result["results"]:
                print(f"\n  📄 {item['filename']}")
                if "result" in item and item["result"].get("success"):
                    print(f"     ✅ Success - Invoice: {item['result']['data']['nr_factura']}")
                else:
                    print(f"     ❌ Failed - {item.get('error', item['result'].get('errors'))}")
                    
    except Exception as e:
        print(f"❌ Error: {str(e)}")


async def test_pydantic_validation():
    """Test Pydantic schema validation directly."""
    print("\n=== Test 5: Pydantic Schema Validation ===")
    
    from app.schemas_invoice import InvoiceData, InvoiceItem
    from datetime import datetime
    from decimal import Decimal
    
    # Test creating valid invoice
    print("\n📝 Creating valid invoice object:")
    try:
        item = InvoiceItem(
            description="Product A",
            quantity=2.0,
            unit="buc",
            unit_price=Decimal("100.00"),
            total_price=Decimal("200.00")
        )
        
        invoice = InvoiceData(
            nr_factura="FAC-2024-001",
            data="15.03.2024",
            furnizor="SC EXAMPLE SRL",
            CUI="1234567890",
            IBAN="RO12 ABNA 1234 5678 9012 3456",
            items=[item],
            total=Decimal("238.00"),
            TVA=Decimal("38.00")
        )
        
        print("✅ Valid invoice created successfully")
        print(f"   Invoice: {invoice.nr_factura}")
        print(f"   Date: {invoice.data}")
        print(f"   Total: {invoice.total} RON")
        
    except Exception as e:
        print(f"❌ Validation error: {str(e)}")
    
    # Test invalid CUI
    print("\n📝 Testing invalid CUI (non-numeric):")
    try:
        invoice = InvoiceData(
            nr_factura="FAC-2024-001",
            data="15.03.2024",
            furnizor="SC EXAMPLE SRL",
            CUI="ABC123XYZ",  # Invalid: not all digits
            items=[],
            total=Decimal("100.00"),
            TVA=Decimal("19.00")
        )
        print("⚠️  Should have failed validation")
    except Exception as e:
        print(f"✅ Correctly rejected: {str(e)}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Invoice Extraction Service - Test Suite")
    print("=" * 60)
    
    print("\n⚠️  Make sure the FastAPI server is running:")
    print("   python -m uvicorn app.main:app --reload")
    
    print("\n⚠️  Set your GEMINI_API_KEY in .env before running extractions")
    
    # Test direct Pydantic validation (no API needed)
    await test_pydantic_validation()
    
    # Test API endpoints (requires running server)
    await test_validate_invoice_data()
    await test_extract_invoice_from_file()
    await test_extract_from_url()
    await test_batch_extract()
    
    print("\n" + "=" * 60)
    print("Test suite completed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
