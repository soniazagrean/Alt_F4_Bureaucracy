#!/usr/bin/env python3
"""
Integration example: Using invoice extraction (NV-006) with nomenclator suggestion (NV-008).
Shows how to combine document extraction and archive classification in a pipeline.
"""

import asyncio
from app.services.invoice_extraction import InvoiceExtractionService
from app.services.nomenclator_suggestion import NomenclatorSuggestionService
from app.schemas_nomenclator import NomenclatorSuggestionRequest
import json


class DocumentProcessingPipeline:
    """Pipeline combining invoice extraction and nomenclator suggestion."""
    
    def __init__(self):
        self.invoice_service = InvoiceExtractionService()
        self.nomenclator_service = NomenclatorSuggestionService()
    
    async def process_invoice_end_to_end(self, image_path: str):
        """
        Complete pipeline for invoice document:
        1. Extract invoice data
        2. Suggest nomenclator classification
        3. Return complete results
        
        Args:
            image_path: Path to invoice image
            
        Returns:
            Dict with extracted data + nomenclator suggestions
        """
        print(f"\n{'='*70}")
        print(f"Processing invoice: {image_path}")
        print(f"{'='*70}")
        
        # Step 1: Extract invoice data
        print("\n[Step 1] Extracting invoice data...")
        invoice_data, extract_errors, extract_confidence = self.invoice_service.extract_invoice_data(
            image_path, 
            language="ro"
        )
        
        if not invoice_data:
            print(f"❌ Failed to extract invoice data")
            print(f"Errors: {extract_errors}")
            return None
        
        print(f"✅ Successfully extracted invoice data")
        print(f"   Invoice #: {invoice_data.nr_factura}")
        print(f"   Total: {invoice_data.total} {invoice_data.currency}")
        print(f"   Confidence: {extract_confidence:.2%}")
        
        # Step 2: Prepare metadata for nomenclator suggestion
        print("\n[Step 2] Preparing nomenclator suggestion...")
        
        # Convert extracted invoice to dictionary for nomenclator
        extracted_metadata = {
            "nr_factura": invoice_data.nr_factura,
            "data": str(invoice_data.data),  # Date
            "furnished": invoice_data.furnished,  # Supplier name
            "client": invoice_data.client,
            "total": invoice_data.total,
            "currency": invoice_data.currency,
            "TVA": invoice_data.TVA,
            "IBAN": invoice_data.IBAN,
            "items": invoice_data.items if hasattr(invoice_data, 'items') else []
        }
        
        # Create nomenclator suggestion request
        suggestion_request = NomenclatorSuggestionRequest(
            document_type="invoice",
            title=f"Invoice {invoice_data.nr_factura} from {invoice_data.furnished}",
            description=f"Invoice dated {invoice_data.data} for amount {invoice_data.total} RON",
            extracted_metadata=extracted_metadata,
            language="ro"
        )
        
        # Step 3: Get nomenclator suggestions
        print("✅ Requesting nomenclator classification...")
        nomenclator_response = self.nomenclator_service.suggest_nomenclator(
            suggestion_request,
            num_suggestions=3
        )
        
        if not nomenclator_response.success:
            print(f"❌ Failed to get nomenclator suggestions")
            print(f"Error: {nomenclator_response.message}")
            return None
        
        print(f"✅ Received {len(nomenclator_response.suggestions)} suggestions")
        
        primary = nomenclator_response.primary_suggestion
        print(f"\n   Primary Suggestion:")
        print(f"     - Code: {primary.cod_nomenclator}")
        print(f"     - Archive Folder: {primary.dosar_propus}")
        print(f"     - Retention: {primary.termen_pastrare}")
        print(f"     - Confidentiality: {primary.nivel_confidentialitate}")
        print(f"     - Confidence: {primary.confidence:.2%}")
        
        # Step 4: Compile complete results
        print("\n[Step 3] Compiling final results...")
        
        complete_result = {
            "document_type": "invoice",
            "extraction_phase": {
                "success": True,
                "data": {
                    "nr_factura": invoice_data.nr_factura,
                    "data": str(invoice_data.data),
                    "furnished": invoice_data.furnished,
                    "client": invoice_data.client,
                    "total": invoice_data.total,
                    "currency": invoice_data.currency,
                    "TVA": invoice_data.TVA
                },
                "confidence": extract_confidence
            },
            "nomenclator_classification": {
                "success": nomenclator_response.success,
                "primary_suggestion": {
                    "cod_nomenclator": primary.cod_nomenclator,
                    "dosar_propus": primary.dosar_propus,
                    "termen_pastrare": primary.termen_pastrare,
                    "nivel_confidentialitate": primary.nivel_confidentialitate,
                    "confidence": primary.confidence,
                    "rationale": primary.rationale
                },
                "alternatives": [
                    {
                        "cod_nomenclator": s.cod_nomenclator,
                        "dosar_propus": s.dosar_propus,
                        "confidence": s.confidence
                    }
                    for s in nomenclator_response.suggestions[1:3]
                ] if len(nomenclator_response.suggestions) > 1 else [],
                "processing_time_ms": nomenclator_response.processing_time_ms
            },
            "storage_instructions": {
                "default_location": primary.dosar_propus,
                "retention_until": self._calculate_retention_date(primary.termen_pastrare),
                "access_level": primary.nivel_confidentialitate,
                "nomenclator_code": primary.cod_nomenclator
            }
        }
        
        print(f"✅ Complete processing successful!")
        print(f"\n{'='*70}")
        print("COMPLETE RESULTS")
        print(f"{'='*70}")
        print(json.dumps(complete_result, indent=2, default=str))
        
        return complete_result
    
    @staticmethod
    def _calculate_retention_date(termen_pastrare: str) -> str:
        """Calculate actual retention date based on retention term."""
        from datetime import datetime, timedelta
        
        today = datetime.now()
        
        terms = {
            "6_months": today + timedelta(days=180),
            "1_year": today + timedelta(days=365),
            "3_years": today + timedelta(days=365*3),
            "5_years": today + timedelta(days=365*5),
            "7_years": today + timedelta(days=365*7),
            "10_years": today + timedelta(days=365*10),
            "permanent": datetime(9999, 12, 31)
        }
        
        retention_date = terms.get(termen_pastrare, today + timedelta(days=365*5))
        return retention_date.strftime("%Y-%m-%d")


async def example_with_sample_data():
    """
    Example using sample invoice data (without actual image file).
    Useful for testing when you don't have an actual invoice image.
    """
    print(f"\n{'='*70}")
    print("NOMENCLATOR SUGGESTION - SAMPLE DATA EXAMPLE")
    print(f"{'='*70}")
    
    service = NomenclatorSuggestionService()
    
    # Create a sample invoice request
    sample_request = NomenclatorSuggestionRequest(
        document_type="invoice",
        title="Invoice from IT Services Company Ltd.",
        description="Monthly invoice for software development and support services",
        extracted_metadata={
            "nr_factura": "INV-2024-001",
            "data": "2024-01-15",
            "furnished": "IT Services Company Ltd.",
            "client": "Our Corporation",
            "total": 5000.00,
            "currency": "RON",
            "TVA": 950.00,
            "IBAN": "RO12ABCD0000123456789",
            "items": [
                "Software Development (40h @ 200 RON/h)",
                "Technical Support",
                "Documentation"
            ]
        },
        language="ro"
    )
    
    print("\nRequesting nomenclator classification...")
    print("Input:")
    print(f"  Document Type: {sample_request.document_type}")
    print(f"  Title: {sample_request.title}")
    print(f"  Amount: {sample_request.extracted_metadata.get('total')} RON")
    
    response = service.suggest_nomenclator(sample_request, num_suggestions=3)
    
    if response.success:
        print(f"\n✅ Successfully generated {len(response.suggestions)} suggestions\n")
        
        for idx, suggestion in enumerate(response.suggestions, 1):
            print(f"Suggestion {idx}:")
            print(f"  - Nomenclator Code: {suggestion.cod_nomenclator}")
            print(f"  - Archive Folder: {suggestion.dosar_propus}")
            print(f"  - Retention Term: {suggestion.termen_pastrare}")
            print(f"  - Confidentiality: {suggestion.nivel_confidentialitate}")
            print(f"  - Confidence: {suggestion.confidence:.1%}")
            print(f"  - Rationale: {suggestion.rationale[:100]}...")
            print()
    else:
        print(f"\n❌ Failed: {response.message}")
        if response.errors:
            for error in response.errors:
                print(f"  - {error}")


if __name__ == "__main__":
    print("""
    DOCUMENT PROCESSING PIPELINE EXAMPLES
    =====================================
    
    This script demonstrates integration between:
    1. Invoice Extraction Service (NV-006)
    2. Nomenclator Suggestion Service (NV-008)
    
    To run with actual invoice image:
        pipeline = DocumentProcessingPipeline()
        result = asyncio.run(pipeline.process_invoice_end_to_end("path/to/invoice.png"))
    
    Running sample data example instead...
    """)
    
    asyncio.run(example_with_sample_data())
