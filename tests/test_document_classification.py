"""Tests for NV-007 — document type classification."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.document_classification import DocumentClassificationService
from app.schemas import DocumentTypeEnum

# ---- unit: prompt content ----

def test_prompt_contains_all_types():
    prompt = DocumentClassificationService._create_classification_prompt()
    required_keys = ["invoice", "contract", "report", "adresa", "cerere", "hcl", "deviz", "protocol"]
    for key in required_keys:
        assert f'"{key}"' in prompt, f"Prompt missing type: {key}"

def test_prompt_is_in_romanian():
    prompt = DocumentClassificationService._create_classification_prompt()
    assert "Factură" in prompt
    assert "Hotărâre" in prompt
    assert "Deviz" in prompt

# ---- unit: response parser ----

def _make_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}

def test_parse_valid_response():
    raw = _make_response('{"tip_document": "hcl", "confidence": 0.95, "reasoning": "Conține antet HCL."}')
    result = DocumentClassificationService._parse_response(raw)
    assert result.tip_document == DocumentTypeEnum.HCL
    assert result.confidence == 0.95

def test_parse_response_with_markdown_fences():
    raw = _make_response('```json\n{"tip_document": "invoice", "confidence": 0.99}\n```')
    result = DocumentClassificationService._parse_response(raw)
    assert result.tip_document == DocumentTypeEnum.INVOICE

def test_parse_unknown_type_falls_back_to_other():
    raw = _make_response('{"tip_document": "chitanta", "confidence": 0.4}')
    result = DocumentClassificationService._parse_response(raw)
    assert result.tip_document == DocumentTypeEnum.OTHER

def test_parse_empty_choices_raises():
    with pytest.raises(ValueError):
        DocumentClassificationService._parse_response({"choices": []})

# ---- integration: full classify() with mocked API ----

@patch.object(DocumentClassificationService, "_call_api")
@patch.object(DocumentClassificationService, "_image_to_base64", return_value="fakebase64")
@patch.object(DocumentClassificationService, "_get_media_type", return_value="image/png")
def test_classify_success(mock_media, mock_b64, mock_api):
    mock_api.return_value = _make_response(
        '{"tip_document": "deviz", "confidence": 0.88, "reasoning": "Tabel cu articole de lucrări."}'
    )
    svc = DocumentClassificationService(api_key="test-key")
    result, errors = svc.classify("/fake/path/doc.png")
    assert errors is None
    assert result.tip_document == DocumentTypeEnum.DEVIZ
    assert result.confidence == pytest.approx(0.88)

@patch.object(DocumentClassificationService, "_call_api", side_effect=Exception("network error"))
@patch.object(DocumentClassificationService, "_image_to_base64", return_value="x")
@patch.object(DocumentClassificationService, "_get_media_type", return_value="image/png")
def test_classify_api_failure(mock_media, mock_b64, mock_api):
    svc = DocumentClassificationService(api_key="test-key")
    result, errors = svc.classify("/fake/path/doc.png")
    assert result is None
    assert errors is not None
    assert "network error" in errors[0]

# ---- parametrize: all 8 doc types round-trip ----

ALL_TYPES = ["invoice", "contract", "report", "correspondence", "decision",
             "protocol", "adresa", "cerere", "hcl", "deviz"]

@pytest.mark.parametrize("doc_type", ALL_TYPES)
@patch.object(DocumentClassificationService, "_call_api")
@patch.object(DocumentClassificationService, "_image_to_base64", return_value="x")
@patch.object(DocumentClassificationService, "_get_media_type", return_value="image/png")
def test_all_types_parse_correctly(mock_media, mock_b64, mock_api, doc_type):
    mock_api.return_value = _make_response(f'{{"tip_document": "{doc_type}", "confidence": 0.9}}')
    svc = DocumentClassificationService(api_key="test-key")
    result, errors = svc.classify("/x.png")
    assert errors is None
    assert result.tip_document.value == doc_type