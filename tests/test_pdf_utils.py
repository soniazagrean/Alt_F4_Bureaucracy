
import os
import pytest
from app.services.pdf_utils import pdf_to_pages, pdf_to_pages_safe, PDFConversionError

SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "sample.pdf")

def test_pdf_to_pages_default():
    images = pdf_to_pages(SAMPLE_PDF)
    assert isinstance(images, list), "Should return a list"
    assert len(images) > 0, "Should return at least one image"
    for img in images:
        assert img.mode == "RGB", "Image mode should be RGB"
        assert img.size[0] > 0 and img.size[1] > 0, "Image size should be positive"
        assert img.info.get("dpi") == (300, 300) or img.info.get("dpi") == (300.0, 300.0), "Default resolution must be 300 DPI"

def test_pdf_to_pages_custom_dpi():
    images = pdf_to_pages(SAMPLE_PDF, dpi=150)
    assert isinstance(images, list)
    assert len(images) > 0
    # Lower DPI should result in smaller images
    images_300 = pdf_to_pages(SAMPLE_PDF, dpi=300)
    assert images_300[0].size[0] > images[0].size[0]

def test_pdf_to_pages_page_range():
    images = pdf_to_pages(SAMPLE_PDF, start_page=0, end_page=1)
    assert len(images) == 1, "Should return only one page image"

def test_pdf_to_pages_invalid_file():
    with pytest.raises(FileNotFoundError):
        pdf_to_pages("not_a_real_file.pdf")

def test_pdf_to_pages_invalid_page():
    # Should raise if start_page is out of range
    with pytest.raises(PDFConversionError):
        pdf_to_pages(SAMPLE_PDF, start_page=100)

def test_pdf_to_pages_safe_success():
    images, error = pdf_to_pages_safe(SAMPLE_PDF)
    assert error is None
    assert isinstance(images, list)
    assert len(images) > 0

def test_pdf_to_pages_safe_error():
    images, error = pdf_to_pages_safe("not_a_real_file.pdf")
    assert images is None
    assert error is not None
