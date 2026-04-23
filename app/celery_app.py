from celery import Celery
from app.config import settings
from app.services.pdf_utils import pdf_to_pages_safe
from app.services.storage import storage
from app.db.database import SessionLocal
from datetime import datetime, timezone, timedelta
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    'alt_f4_bureaucracy',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL.replace('/0', '/1')
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    beat_schedule={
        'recover-stuck-documents': {
            'task': 'app.celery_app.recover_stuck_documents',
            'schedule': 300.0,
            'args': (),
        },
    },
)


def _get_document(db, document_id: int):
    from app.models.document import Document

    return db.query(Document).filter(Document.id == document_id).first()


def _mark_document_retry(document_id: int, error_text: str):
    from app.models.document import DocumentStatusEnum

    db = SessionLocal()
    try:
        doc = _get_document(db, document_id)
        if not doc:
            return

        doc.retry_count = (doc.retry_count or 0) + 1
        doc.error_message = error_text
        doc.error_timestamp = datetime.now(timezone.utc)
        doc.status = DocumentStatusEnum.PROCESSING
        db.commit()
        logger.warning(
            f"Document {document_id} retry {doc.retry_count} scheduled after failure: {error_text}"
        )
    except Exception as exc:
        logger.error(f"Failed to update retry state for document {document_id}: {exc}")
    finally:
        db.close()


def _mark_document_dead_letter(document_id: int, error_text: str, attempt_count: int):
    from app.models.document import DocumentStatusEnum

    db = SessionLocal()
    try:
        doc = _get_document(db, document_id)
        if not doc:
            return

        doc.error_message = error_text
        doc.error_timestamp = datetime.now(timezone.utc)
        doc.status = DocumentStatusEnum.ERROR
        db.commit()
        logger.error(
            f"Document {document_id} permanently failed after {attempt_count} attempts: {error_text}"
        )
    except Exception as exc:
        logger.error(f"Failed to mark document {document_id} as dead-letter: {exc}")
    finally:
        db.close()


@celery_app.task
def recover_stuck_documents():
    from app.models.document import Document, DocumentStatusEnum

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        stuck_documents = db.query(Document).filter(
            Document.status == DocumentStatusEnum.PROCESSING,
            Document.updated_at < cutoff,
        ).all()

        reset_count = 0
        dead_letter_count = 0

        for doc in stuck_documents:
            if (doc.retry_count or 0) >= 3:
                doc.status = DocumentStatusEnum.ERROR
                doc.error_message = "Document stuck in PROCESSING after max retries"
                doc.error_timestamp = datetime.now(timezone.utc)
                dead_letter_count += 1
                logger.error(
                    f"Dead-lettering stuck document {doc.id}: exceeded retry limit"
                )
            else:
                doc.status = DocumentStatusEnum.PENDING
                reset_count += 1
                logger.warning(
                    f"Reset stuck document {doc.id} to PENDING (retry_count={doc.retry_count or 0})"
                )

        if reset_count or dead_letter_count:
            db.commit()

        return {
            'reset_documents': reset_count,
            'dead_letter_documents': dead_letter_count,
            'checked_at': datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error(f"recover_stuck_documents failed: {exc}")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def example_task(x):
    """Example Celery task"""
    return x * 2

@celery_app.task(bind=True, max_retries=3)
def convert_pdf_to_images_task(
    self,
    pdf_path: str,
    document_id: int,
    dpi: int = 300
):
    """
    Celery task to convert PDF pages to PNG images and store in MinIO.
    
    Args:
        pdf_path: Temporary path to uploaded PDF
        document_id: Database document ID for tracking
        dpi: Output DPI (default 300)
        
    Returns:
        Dict with status, pages_converted, and minio paths
    """
    try:
        logger.info(f"Starting PDF conversion for document {document_id}")
        
        # Convert PDF to images
        images, error = pdf_to_pages_safe(pdf_path, dpi=dpi)
        
        if error:
            logger.error(f"PDF conversion failed: {error}")
            raise Exception(error)
        
        if not images:
            raise Exception("No pages were converted from PDF")
        
        # Upload each image to MinIO
        import io
        minio_paths = []
        for page_num, img in enumerate(images):
            try:
                # Save image to temporary bytes
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                
                # Create MinIO object name
                object_name = f"documents/{document_id}/page_{page_num:03d}.png"
                
                # Upload to MinIO
                path = storage.upload_file(
                    file_data=img_bytes.getvalue(),
                    file_name=object_name,
                    bucket_key="processed",
                    content_type="image/png"
                )
                
                minio_paths.append(path)
                logger.debug(f"Uploaded page {page_num} to {path}")
                
            except Exception as e:
                logger.error(f"Failed to upload page {page_num}: {str(e)}")
                raise
        
        # Clean up temporary PDF file
        try:
            Path(pdf_path).unlink()
            logger.debug(f"Cleaned up temporary file: {pdf_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up {pdf_path}: {str(e)}")
        
        result = {
            "status": "success",
            "document_id": document_id,
            "pages_converted": len(images),
            "minio_paths": minio_paths
        }
        
        logger.info(f"Successfully converted {len(images)} pages for document {document_id}")
        return result
        
    except Exception as exc:
        logger.error(f"Task failed: {str(exc)}")
        raise self.retry(exc=exc, countdown=5 ** self.request.retries)


@celery_app.task
def classify_converted_pages_task(document_id: int, minio_paths: list):
    """
    After PDF conversion, classify each page using document_classification service.
    
    Args:
        document_id: Database document ID
        minio_paths: List of MinIO paths to converted images
    """
    from app.services.document_classification import DocumentClassificationService
    
    try:
        logger.info(f"Starting classification for document {document_id}")
        
        classifier = DocumentClassificationService()
        results = []
        
        for page_num, minio_path in enumerate(minio_paths):
            try:
                # Download image from MinIO temporarily
                bucket, object_name = minio_path.split('/', 1)
                local_path = f"/tmp/classify_{document_id}_{page_num}.png"
                
                # Get from MinIO
                storage.client.fget_object(bucket, object_name, local_path)
                
                # Classify the page
                result, errors = classifier.classify(local_path)
                
                if result:
                    results.append({
                        "page": page_num,
                        "type": result.tip_document.value,
                        "confidence": result.confidence,
                        "reasoning": result.reasoning
                    })
                else:
                    logger.warning(f"Classification failed for page {page_num}: {errors}")
                
                # Clean up
                Path(local_path).unlink()
                
            except Exception as e:
                logger.error(f"Failed to classify page {page_num}: {str(e)}")
        
        logger.info(f"Classification complete for document {document_id}")
        return {
            "status": "success",
            "document_id": document_id,
            "classifications": results
        }
        
    except Exception as e:
        logger.error(f"Classification task failed: {str(e)}")
        return {
            "status": "error",
            "document_id": document_id,
            "error": str(e)
        }


@celery_app.task
def extract_invoice_from_pages_task(document_id: int, minio_paths: list):
    """
    Extract invoice data from converted pages.
    
    Args:
        document_id: Database document ID
        minio_paths: List of MinIO paths to converted images
    """
    from app.services.invoice_extraction import InvoiceExtractionService
    
    try:
        logger.info(f"Starting invoice extraction for document {document_id}")
        
        extractor = InvoiceExtractionService()
        extracted_data = None
        
        # Usually invoices are single-page, but try all pages
        for page_num, minio_path in enumerate(minio_paths):
            try:
                bucket, object_name = minio_path.split('/', 1)
                local_path = f"/tmp/invoice_{document_id}_{page_num}.png"
                
                storage.client.fget_object(bucket, object_name, local_path)
                
                # Extract invoice data
                invoice_data, errors, confidence = extractor.extract_invoice_data(
                    local_path,
                    language="ro"
                )
                
                if invoice_data and confidence > 0.7:
                    extracted_data = {
                        "page": page_num,
                        "data": invoice_data.dict(),
                        "confidence": confidence
                    }
                    logger.info(f"Successfully extracted invoice from page {page_num}")
                    break  # Stop after first successful extraction
                
                Path(local_path).unlink()
                
            except Exception as e:
                logger.error(f"Failed to extract from page {page_num}: {str(e)}")
        
        return {
            "status": "success" if extracted_data else "no_invoice_found",
            "document_id": document_id,
            "extracted_data": extracted_data
        }
        
    except Exception as e:
        logger.error(f"Invoice extraction task failed: {str(e)}")
        return {
            "status": "error",
            "document_id": document_id,
            "error": str(e)
        }


@celery_app.task
def index_document_in_meilisearch_task(document_id: int):
    """
    NV-020: Index a document in MeiliSearch after processing completes.
    
    This task is called at the end of process_document_task to ensure
    the document is searchable with indexed fields:
    - Searchable: tip_document, furnizor, nr_factura, data, cod_nomenclator
    - Filterable: tip_document, status, data
    
    Args:
        document_id: Database document ID to index
        
    Returns:
        Dict with indexing status
    """
    from app.models.document import Document
    from app.services.search import SearchService
    
    try:
        logger.info(f"Indexing document {document_id} in MeiliSearch")
        
        db = SessionLocal()
        try:
            # Fetch document and related extracted data
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                logger.warning(f"Document {document_id} not found for indexing")
                return {
                    "status": "document_not_found",
                    "document_id": document_id
                }
            
            # Fetch extracted data as dictionary
            from app.models.document import ExtractedData
            extracted_rows = db.query(ExtractedData).filter(
                ExtractedData.document_id == document_id
            ).all()
            
            extracted_dict = {}
            for row in extracted_rows:
                extracted_dict[row.field_name] = row.field_value
            
            # Prepare document for indexing
            search_service = SearchService()
            doc_for_index = search_service.prepare_document_for_indexing(doc, extracted_dict)
            
            # Add to index
            result = search_service.add_documents([doc_for_index])
            
            logger.info(f"Successfully indexed document {document_id}")
            return {
                "status": "success",
                "document_id": document_id,
                "indexed_fields": list(doc_for_index.keys())
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to index document {document_id}: {str(e)}")
        return {
            "status": "error",
            "document_id": document_id,
            "error": str(e)
        }


@celery_app.task(bind=True, max_retries=3)
def process_document_task(self, document_id: int):
    """Orchestrates the full NV-014 pipeline for a single document."""
    from app.models.document import Document, DocumentStatusEnum, DocumentPage, ExtractedData
    from app.services.document_classification import DocumentClassificationService
    from app.services.invoice_extraction import InvoiceExtractionService
    from app.services.nomenclator_suggestion import NomenclatorSuggestionService
    from app.schemas_nomenclator import NomenclatorSuggestionRequest
    from datetime import datetime
    import io
    import os

    db = SessionLocal()
    doc = None
    temp_files = []

    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        doc.status = DocumentStatusEnum.PROCESSING
        db.commit()

        # Download PDF from MinIO
        if not doc.file_path or "/" not in doc.file_path:
            raise ValueError("Invalid document file_path in DB")

        bucket_name, object_name = doc.file_path.split("/", 1)
        pdf_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf_tmp.close()
        temp_files.append(pdf_tmp.name)
        storage.client.fget_object(bucket_name, object_name, pdf_tmp.name)

        # Convert PDF to page images
        images, error = pdf_to_pages_safe(pdf_tmp.name, dpi=300)
        if error or not images:
            raise RuntimeError(f"PDF to image conversion failed: {error or 'no pages'}")

        # Store page images and DB page records
        minio_pages = []
        for idx, img in enumerate(images):
            out = io.BytesIO()
            img.save(out, format="PNG")
            out.seek(0)
            page_object = f"documents/{document_id}/page_{idx:03d}.png"
            page_minio_path = storage.upload_file(
                file_data=out.getvalue(),
                file_name=page_object,
                bucket_key="processed",
                content_type="image/png"
            )

            page_record = DocumentPage(
                document_id=document_id,
                page_number=idx,
                image_path=page_minio_path,
            )
            db.add(page_record)
            minio_pages.append(page_minio_path)

        doc.page_count = len(minio_pages)
        doc.status = DocumentStatusEnum.CLASSIFIED
        db.commit()

        # Classification (first page)
        if minio_pages:
            first_bucket, first_obj = minio_pages[0].split("/", 1)
            first_local = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            first_local.close()
            temp_files.append(first_local.name)
            storage.client.fget_object(first_bucket, first_obj, first_local.name)

            classifier = DocumentClassificationService()
            classification, classification_errors = classifier.classify(first_local.name)
            if classification:
                doc.document_type = classification.tip_document.value
                doc.confidence = classification.confidence
                doc.status = DocumentStatusEnum.EXTRACTED
                db.commit()

        # Extract invoice data
        extractor = InvoiceExtractionService()
        extracted_metadata = {}

        for minio_page in minio_pages:
            bucket_name, object_name = minio_page.split("/", 1)
            page_local = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            page_local.close()
            temp_files.append(page_local.name)
            storage.client.fget_object(bucket_name, object_name, page_local.name)

            invoice_data, extract_errors, extract_confidence = extractor.extract_invoice_data(
                page_local.name,
                language="ro"
            )

            if invoice_data:
                extracted_metadata = invoice_data.dict()
                # map some fields back to Document
                doc.amount = float(invoice_data.total)
                if invoice_data.currency is None:
                    doc.currency = "RON"
                doc.document_number = invoice_data.nr_factura or doc.document_number

                for key, value in extracted_metadata.items():
                    db.add(ExtractedData(
                        document_id=document_id,
                        field_name=key,
                        field_value=str(value),
                        extraction_confidence=extract_confidence,
                    ))

                doc.status = DocumentStatusEnum.VALIDATED
                db.commit()
                break

        # Nomenclator suggestion
        nomenclator_service = NomenclatorSuggestionService()
        request_body = NomenclatorSuggestionRequest(
            document_type=(doc.document_type or "other"),
            title=doc.title,
            description=doc.description,
            extracted_metadata=extracted_metadata,
            language="ro"
        )

        suggestion_result = nomenclator_service.suggest_nomenclator(request_body, num_suggestions=3)
        if suggestion_result.success and suggestion_result.primary_suggestion:
            doc.status = DocumentStatusEnum.ARCHIVED
            doc.archived_at = datetime.now()
        else:
            # still success but mark completed pipeline
            doc.status = DocumentStatusEnum.ARCHIVED
            doc.archived_at = datetime.now()

        # Final commit
        db.commit()

        try:
            from app.services.graph_service import populate_graph_for_document

            populate_graph_for_document(document_id)
        except Exception as exc:
            logger.error(
                "Graph population failed for document %s: %s",
                document_id,
                exc,
            )

        # NV-020: Index document in MeiliSearch
        try:
            index_result = index_document_in_meilisearch_task.apply_async(
                args=[document_id],
                countdown=0
            )
            logger.info(f"Scheduled indexing task for document {document_id}: {index_result.id}")
        except Exception as exc:
            logger.error(
                "Indexing task scheduling failed for document %s: %s",
                document_id,
                exc,
            )

        return {
            "status": "done",
            "document_id": document_id,
            "pages_processed": len(minio_pages),
            "extracted_metadata": extracted_metadata,
            "nomenclator_suggestion": suggestion_result.dict() if suggestion_result else None
        }

    except Exception as exc:
        error_text = str(exc)
        logger.error(f"process_document_task({document_id}) failed: {error_text}")

        if doc:
            _mark_document_retry(document_id, error_text)

        if self.request.retries < self.max_retries:
            backoff_schedule = [60, 300, 900]
            countdown = backoff_schedule[self.request.retries] if self.request.retries < len(backoff_schedule) else backoff_schedule[-1]
            raise self.retry(exc=exc, countdown=countdown)

        # Final failure after max retries
        if doc:
            _mark_document_dead_letter(document_id, error_text, self.request.retries + 1)
        raise

    finally:
        # Cleanup local temp files
        for f in temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass