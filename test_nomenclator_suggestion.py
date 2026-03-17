#!/usr/bin/env python3
"""
Test suite for nomenclator archive classification and suggestion (NV-008).
Tests the LLM prompt engineering for archive classification with Romanian nomenclator.
"""

import asyncio
import httpx
import json
from pathlib import Path
from typing import Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test API endpoint
BASE_URL = "http://localhost:8080/api/v1/nomenclator"


async def test_get_standards():
    """Test getting nomenclator standards reference."""
    print("\n=== Test 1: Get Nomenclator Standards ===")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/standards")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Successfully retrieved nomenclator standards")
            print(f"   Standard: {data.get('standard', 'Unknown')}")
            print(f"   Version: {data.get('version', 'Unknown')}")
            
            # Print first 300 chars of nomenclator
            nomen = data.get('romanian_nomenclator', '')[:300]
            print(f"   Nomenclator preview: {nomen}...")
            
            return True
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


async def test_suggest_invoice():
    """Test nomenclator suggestion for an invoice document."""
    print("\n=== Test 2: Suggest Nomenclator for Invoice ===")
    
    request_payload = {
        "document_type": "invoice",
        "title": "Invoice from ABC Supplier Ltd.",
        "description": "Monthly invoice for IT services and support",
        "extracted_metadata": {
            "nr_factura": "INV-2024-001",
            "data": "2024-01-15",
            "furnished": "ABC Supplier Ltd.",
            "total": 5000.00,
            "currency": "RON",
            "TVA": 950.00,
            "items": ["IT Support Services", "Software Licenses"],
            "IBAN": "RO12ABCD0000123456789"
        },
        "language": "ro"
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{BASE_URL}/suggest",
                json=request_payload,
                params={"num_suggestions": 3}
            )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                print(f"✅ Successfully generated suggestions")
                print(f"   Total suggestions: {len(data.get('suggestions', []))}")
                
                primary = data.get("primary_suggestion")
                if primary:
                    print(f"\n   Primary Suggestion:")
                    print(f"     - Code: {primary.get('cod_nomenclator')}")
                    print(f"     - Folder: {primary.get('dosar_propus')}")
                    print(f"     - Retention: {primary.get('termen_pastrare')}")
                    print(f"     - Confidentiality: {primary.get('nivel_confidentialitate')}")
                    print(f"     - Confidence: {primary.get('confidence', 0):.2%}")
                    print(f"     - Rationale: {primary.get('rationale', '')[:150]}...")
                
                print(f"\n   Processing time: {data.get('processing_time_ms', 0):.1f}ms")
                
                # Print all suggestions
                for idx, suggestion in enumerate(data.get("suggestions", []), 1):
                    print(f"\n   Suggestion {idx}:")
                    print(f"     - Code: {suggestion.get('cod_nomenclator')}")
                    print(f"     - Folder: {suggestion.get('dosar_propus')}")
                    print(f"     - Confidence: {suggestion.get('confidence', 0):.2%}")
                
                return True
            else:
                print(f"❌ Request failed: {data.get('message', 'Unknown error')}")
                if data.get('errors'):
                    for error in data['errors']:
                        print(f"   Error: {error}")
                return False
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
            
    except httpx.TimeoutException:
        print("❌ Request timeout (>120s) - LLM may be slow or service unavailable")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


async def test_suggest_contract():
    """Test nomenclator suggestion for a contract document."""
    print("\n=== Test 3: Suggest Nomenclator for Contract ===")
    
    request_payload = {
        "document_type": "contract",
        "title": "Service Agreement with Vendor XYZ",
        "description": "Annual software maintenance and support contract",
        "extracted_metadata": {
            "contract_number": "CNT-2023-0456",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "parties": ["Company Name", "Vendor XYZ Corp"],
            "value": 25000.00,
            "currency": "RON",
            "scope": "Software maintenance and technical support"
        },
        "language": "ro"
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{BASE_URL}/suggest",
                json=request_payload,
                params={"num_suggestions": 2}
            )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                print(f"✅ Successfully generated {len(data.get('suggestions', []))} suggestions")
                
                primary = data.get("primary_suggestion")
                if primary:
                    print(f"\n   Primary Suggestion:")
                    print(f"     - Code: {primary.get('cod_nomenclator')} (Legal/Contracts category)")
                    print(f"     - Folder: {primary.get('dosar_propus')}")
                    print(f"     - Retention: {primary.get('termen_pastrare')} (should be 10_years for contracts)")
                    print(f"     - Confidentiality: {primary.get('nivel_confidentialitate')}")
                    print(f"     - Confidence: {primary.get('confidence', 0):.2%}")
                
                return True
            else:
                print(f"❌ Request failed: {data.get('message')}")
                return False
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


async def test_suggest_decision():
    """Test nomenclator suggestion for a decision/protocol document."""
    print("\n=== Test 4: Suggest Nomenclator for Decision/Protocol ===")
    
    request_payload = {
        "document_type": "decision",
        "title": "Board Decision - Q1 2024 Strategic Plan",
        "description": "Board of Directors decision on strategic initiatives",
        "extracted_metadata": {
            "decision_number": "DEC-2024-001",
            "date": "2024-01-10",
            "subject": "Strategic initiatives for 2024",
            "attendees": 12,
            "voting": "Unanimous"
        },
        "language": "ro"
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{BASE_URL}/suggest",
                json=request_payload,
                params={"num_suggestions": 2}
            )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                print(f"✅ Successfully generated suggestions")
                
                primary = data.get("primary_suggestion")
                if primary:
                    print(f"\n   Primary Suggestion:")
                    print(f"     - Code: {primary.get('cod_nomenclator')} (Administrative category)")
                    print(f"     - Folder: {primary.get('dosar_propus')}")
                    print(f"     - Retention: {primary.get('termen_pastrare')}")
                    print(f"     - Confidence: {primary.get('confidence', 0):.2%}")
                
                return True
            else:
                print(f"❌ Request failed: {data.get('message')}")
                return False
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


async def test_batch_suggestion():
    """Test batch nomenclator suggestions for multiple documents."""
    print("\n=== Test 5: Batch Nomenclator Suggestions ===")
    
    requests_payload = [
        {
            "document_type": "invoice",
            "title": "Invoice from Supplier A",
            "extracted_metadata": {"amount": 3000, "currency": "RON"},
            "language": "ro"
        },
        {
            "document_type": "report",
            "title": "Monthly Activity Report",
            "extracted_metadata": {"period": "January 2024"},
            "language": "ro"
        }
    ]
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{BASE_URL}/suggest-batch",
                json=requests_payload,
                params={"num_suggestions": 2}
            )
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"✅ Processed {len(data)} documents")
            
            for idx, result in enumerate(data, 1):
                success = result.get("success", False)
                suggestions_count = len(result.get("suggestions", []))
                primary = result.get("primary_suggestion", {})
                
                print(f"\n   Document {idx}:")
                print(f"     - Success: {success}")
                print(f"     - Suggestions: {suggestions_count}")
                if primary:
                    print(f"     - Primary code: {primary.get('cod_nomenclator')}")
                    print(f"     - Confidence: {primary.get('confidence', 0):.2%}")
            
            return True
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


async def run_all_tests():
    """Run all nomenclator suggestion tests."""
    print("=" * 70)
    print("NOMENCLATOR ARCHIVE SUGGESTION TESTS (NV-008)")
    print("Romanian Standard (I-VII) Classification with LLM Prompt Engineering")
    print("=" * 70)
    
    results = []
    
    # Test 1: Get standards
    results.append(("Get Standards", await test_get_standards()))
    
    # Test 2: Invoice suggestion
    results.append(("Suggest for Invoice", await test_suggest_invoice()))
    
    # Test 3: Contract suggestion
    results.append(("Suggest for Contract", await test_suggest_contract()))
    
    # Test 4: Decision suggestion
    results.append(("Suggest for Decision", await test_suggest_decision()))
    
    # Test 5: Batch suggestions
    results.append(("Batch Suggestions", await test_batch_suggestion()))
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10s} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {total - passed} test(s) failed")
    
    return passed == total


if __name__ == "__main__":
    print("\n⚠️  Make sure the FastAPI server is running on localhost:8000")
    print("    Run: python -m uvicorn app.main:app --reload\n")
    
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
