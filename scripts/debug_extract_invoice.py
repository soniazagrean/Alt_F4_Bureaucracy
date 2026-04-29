#!/usr/bin/env python3
"""Debug invoice extraction for a document/page.

Usage (from project root, with docker-compose services available):
  docker compose run --rm fastapi python scripts/debug_extract_invoice.py --document-id 123 --page 1 --language ro

Or run locally in venv:
  python scripts/debug_extract_invoice.py --image-path streamlit_app/test_documents/invoice_acme_2025-001.png --language ro
"""
import argparse
import tempfile
import os
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.services.storage import storage
from app.services.invoice_extraction import InvoiceExtractionService
from app.services.pdf_utils import pdf_to_pages


def download_page_image(db, document_id: int, page_number: int) -> str:
    from app.models.document import DocumentPage, Document

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise SystemExit(f"Document {document_id} not found in DB")

    # find requested page or fallback to first page
    page = db.query(DocumentPage).filter(DocumentPage.document_id == document_id, DocumentPage.page_number == page_number).first()
    if not page:
        # fallback to file_path
        if not doc.file_path:
            raise SystemExit("No page image or file_path available for this document")
        return download_object_to_tmp(doc.file_path)
    return download_object_to_tmp(page.image_path)


def download_object_to_tmp(object_path: str) -> str:
    # object_path expected as 'bucket/object_name'
    _, obj = object_path.split('/', 1)
    fd, tmp_path = tempfile.mkstemp(suffix='.' + obj.split('.')[-1])
    os.close(fd)
    storage.download_file(object_path, tmp_path)
    return tmp_path


def resolve_input_path(input_path: str) -> str:
    path = Path(input_path)
    if path.exists():
        return str(path)

    repo_relative = ROOT / input_path
    if repo_relative.exists():
        return str(repo_relative)

    raise FileNotFoundError(f"Input file not found: {input_path}")


def materialize_image(input_path: str) -> str:
    resolved_path = resolve_input_path(input_path)
    suffix = Path(resolved_path).suffix.lower()

    if suffix == '.pdf':
        pages = pdf_to_pages(resolved_path, dpi=200, start_page=0, end_page=1)
        if not pages:
            raise SystemExit(f"No pages could be rendered from PDF: {resolved_path}")
        fd, tmp_path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        pages[0].save(tmp_path, format='PNG')
        return tmp_path

    return resolved_path


def run_debug(image_path: str, language: str):
    svc = InvoiceExtractionService()

    print(f"Using image: {image_path}")

    # Run full extraction (includes validation)
    invoice_data, errors, confidence = svc.extract_invoice_data(image_path, language=language)

    print('\n--- Extraction Outcome ---')
    print('confidence:', confidence)
    if invoice_data is not None:
        print('InvoiceData (validated):')
        try:
            # pydantic model -> dict
            print(json.dumps(invoice_data.dict(), indent=2, ensure_ascii=False))
        except Exception:
            print(repr(invoice_data))
    else:
        print('Validation errors / Extraction errors:')
        print(json.dumps(errors or ['unknown'], indent=2, ensure_ascii=False))

    # Also call lower-level API to get raw response for debugging
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        import base64
        image_b64 = base64.standard_b64encode(image_bytes).decode('utf-8')
        prompt = svc._create_extraction_prompt(language)
        raw = svc._call_openai_api(image_b64, svc._get_image_media_type(image_path), prompt)
        print('\n--- Raw OpenAI response (truncated) ---')
        try:
            print(json.dumps(raw, indent=2)[:4000])
        except Exception:
            print(str(raw)[:4000])

        print('\n--- Parsed JSON from OpenAI (if any) ---')
        try:
            parsed, conf = svc._parse_openai_response(raw)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except Exception as e:
            print('Parse error:', str(e))
    except Exception as e:
        print('Could not call OpenAI API or parse raw response:', str(e))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--document-id', type=int, help='Document id from DB')
    parser.add_argument('--page', type=int, default=1, help='Page number to fetch (default 1)')
    parser.add_argument('--image-path', type=str, help='Local image path to test')
    parser.add_argument('--language', type=str, default='ro', help='Language hint (ro/en)')

    args = parser.parse_args()

    tmp_image = None
    db = None
    try:
        if args.document_id and not args.image_path:
            db = SessionLocal()
            tmp_image = download_page_image(db, args.document_id, args.page)
            run_debug(tmp_image, args.language)
        elif args.image_path:
            tmp_image = materialize_image(args.image_path)
            run_debug(tmp_image, args.language)
        else:
            parser.print_help()
    finally:
        if db:
            db.close()
        if tmp_image and os.path.exists(tmp_image):
            try:
                os.unlink(tmp_image)
            except Exception:
                pass


if __name__ == '__main__':
    main()
