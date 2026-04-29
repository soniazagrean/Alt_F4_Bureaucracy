"""Tests for invoice extraction service end-to-end pipeline."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

from app.services.invoice_extraction import InvoiceExtractionService
from app.schemas_invoice import InvoiceData


@pytest.fixture
def invoice_service():
    """Fixture for invoice extraction service with mocked API key."""
    return InvoiceExtractionService(api_key="dummy_key")


@pytest.fixture
def fixture_dir():
    """Fixture for test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def invoice_sample_data(fixture_dir):
    """Load the expected invoice sample data."""
    with open(fixture_dir / "invoice_sample.json", "r") as f:
        return json.load(f)


@pytest.mark.parametrize("pdf_filename", [
    "invoice_valid.png",
    "invoice_no_stamp.png",
    "invoice_wrong_vat.png"
])
def test_invoice_extraction_pipeline(invoice_service, fixture_dir, pdf_filename, invoice_sample_data):
    """Test end-to-end invoice extraction pipeline for each PDF fixture."""
    pdf_path = fixture_dir / "invoices" / pdf_filename

    # Mock the OpenAI API response to return the sample data
    mock_response = {
        "choices": [{
            "message": {
                "content": json.dumps(invoice_sample_data)
            }
        }]
    }

    with patch.object(invoice_service, '_call_openai_api', return_value=mock_response):
        # Extract invoice data
        invoice_data, errors, confidence = invoice_service.extract_invoice_data(str(pdf_path))

        # Assert extraction succeeded
        assert invoice_data is not None, f"Extraction failed for {pdf_filename}: {errors}"
        assert errors is None, f"Errors present for {pdf_filename}: {errors}"
        assert confidence > 0, f"Invalid confidence for {pdf_filename}: {confidence}"

        # Assert returned dict is non-empty and contains required top-level keys
        data_dict = invoice_data.model_dump()
        required_keys = ["nr_factura", "data", "furnizor", "CUI", "items", "total", "TVA"]
        for key in required_keys:
            assert key in data_dict, f"Missing required key '{key}' in {pdf_filename}"
            assert data_dict[key] is not None, f"Required key '{key}' is None in {pdf_filename}"

        # Validate against Pydantic schema
        try:
            validated_invoice = InvoiceData.model_validate(data_dict)
            assert validated_invoice is not None
        except ValidationError as e:
            pytest.fail(f"Pydantic validation failed for {pdf_filename}: {e}")

        # For invoice_valid.png, cross-check key fields against fixture
        if pdf_filename == "invoice_valid.png":
            assert validated_invoice.nr_factura == invoice_sample_data["nr_factura"]
            assert str(validated_invoice.total) == str(invoice_sample_data["total"])
            assert str(validated_invoice.TVA) == str(invoice_sample_data["TVA"])
            assert validated_invoice.furnizor == invoice_sample_data["furnizor"]
            assert validated_invoice.CUI == invoice_sample_data["CUI"]


def test_invoice_extraction_validation_error(invoice_service, fixture_dir):
    """Test that malformed extraction results raise ValidationError."""
    pdf_path = fixture_dir / "invoices" / "invoice_valid.png"

    # Mock API to return malformed data that will fail validation
    malformed_data = {
        "nr_factura": "",  # Empty invoice number - invalid
        "data": "invalid_date",
        "furnizor": "Test Supplier",
        "CUI": "not_numeric",  # Invalid CUI
        "items": [],  # Empty items list - invalid
        "total": -100,  # Negative total - invalid
        "TVA": 50
    }

    mock_response = {
        "choices": [{
            "message": {
                "content": json.dumps(malformed_data)
            }
        }]
    }

    with patch.object(invoice_service, '_call_openai_api', return_value=mock_response):
        # Extract invoice data
        invoice_data, errors, confidence = invoice_service.extract_invoice_data(str(pdf_path))

        # Assert extraction failed due to validation
        assert invoice_data is None, "Extraction should have failed for malformed data"
        assert errors is not None, "Errors should be present for malformed data"
        assert isinstance(errors, list), "Errors should be a list"
        assert len(errors) > 0, "At least one error should be present"


def test_invoice_extraction_normalizes_aliases_and_numeric_formats(invoice_service):
    """Test that common alias keys and localized numeric formats are normalized before validation."""
    messy_data = {
        "invoice_number": "FAC-2026/002",
        "invoice_date": "29.04.2026",
        "supplier": "SC ACME INDUSTRIES SRL",
        "tax_id": "RO12345678",
        "iban": "ro49 aaaa 1b31 0075 9384 0000",
        "currency": "ron",
        "items": [
            {
                "description": "Software license",
                "qty": "2",
                "price": "2,590.50 RON",
                "amount": "5,181.00 RON",
            }
        ],
        "total_amount": "5,181.00 RON",
        "vat": "981,00 RON",
    }

    mock_response = {
        "choices": [{
            "message": {
                "content": json.dumps(messy_data)
            }
        }]
    }

    with patch.object(invoice_service, '_image_to_base64', return_value="ZmFrZV9pbWFnZV9ieXRlcw=="), \
         patch.object(invoice_service, '_get_image_media_type', return_value="image/png"), \
         patch.object(invoice_service, '_call_openai_api', return_value=mock_response):
        invoice_data, errors, confidence = invoice_service.extract_invoice_data("dummy.png")

        assert invoice_data is not None, f"Normalization should have rescued the payload: {errors}"
        assert errors is None
        assert confidence > 0
        assert invoice_data.nr_factura == "FAC-2026/002"
        assert invoice_data.furnizor == "SC ACME INDUSTRIES SRL"
        assert invoice_data.CUI == "12345678"
        assert invoice_data.currency == "RON"
        assert str(invoice_data.total) == "5181.00"
        assert str(invoice_data.TVA) == "981.00"
        assert len(invoice_data.items) == 1
        assert str(invoice_data.items[0].unit_price) == "2590.50"
        assert str(invoice_data.items[0].total_price) == "5181.00"
