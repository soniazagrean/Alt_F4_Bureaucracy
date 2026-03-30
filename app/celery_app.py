from celery import Celery
from app.config import settings
from app.services.pdf_utils import pdf_to_pages_safe
from app.services.storage import storage
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    'alt_f4_bureaucracy',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@celery_app.task
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