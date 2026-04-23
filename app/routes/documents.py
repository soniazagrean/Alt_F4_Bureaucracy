import logging
import hashlib
import uuid
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.dependencies.security import RBACRole, require_roles
from app.db.database import get_db
from app.models.audit import AuditActionEnum
from app.models.document import Document, DocumentStatusEnum, DocumentTypeEnum
from app.models.user import User
from app.services.audit_service import log_audit_event, get_request_ip
from app.services.storage import storage
from app.schemas import DocumentUploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    try:
        logger.info(f"📤 Starting upload for file: {file.filename}")
        
        # 1. Read file content
        contents = await file.read()
        logger.info(f"✓ File read: {len(contents)} bytes")
        
        # 2. Calculate SHA-256 Hash
        file_hash = hashlib.sha256(contents).hexdigest()
        logger.info(f"✓ Hash calculated: {file_hash}")
        
        # 3. Deduplication Check
        existing_doc = db.query(Document).filter(Document.file_hash == file_hash).first()
        if existing_doc:
            logger.warning(f"⚠️  Duplicate file detected: {file_hash}")
            return DocumentUploadResponse(
                id=existing_doc.id,
                filename=existing_doc.title,
                status=existing_doc.status.value,
                message="File already exists (duplicate detected).",
                is_duplicate=True
            )
        
        # 4. Upload to MinIO
        logger.info(f"📦 Uploading to MinIO...")
        try:
            # Use the existing 'storage' instance and method
            storage_path = storage.upload_file(
                file_data=contents, 
                file_name=file.filename, 
                bucket_key="uploads", # Matches your MINIO_BUCKET_UPLOADS
                content_type=file.content_type
            )
            logger.info(f"✓ MinIO upload successful: {storage_path}")
        except Exception as e:
            logger.error(f"❌ MinIO upload error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
    
        # 5. Create Database Record
        logger.info(f"💾 Creating database record...")
        # Note: Using temp values for required fields that are not yet known
        new_doc = Document(
            document_number=f"temp-{uuid.uuid4()}",  # Temporary unique number
            title=file.filename,                     # Use filename as initial title
            document_type=DocumentTypeEnum.OTHER.value,    # Default type
            file_path=storage_path,
            file_size=len(contents),
            mime_type=file.content_type,
            file_hash=file_hash,
            status=DocumentStatusEnum.PENDING,
            created_by_id=current_user.id
        )
        
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)
        logger.info(f"✓ Document record created: ID={new_doc.id}")

        log_audit_event(
            db=db,
            user=current_user,
            action=AuditActionEnum.UPLOAD,
            resource_type="document",
            resource_id=new_doc.id,
            document_id=new_doc.id,
            description="Document uploaded",
            changes={
                "file_name": new_doc.title,
                "file_size": new_doc.file_size,
                "mime_type": new_doc.mime_type,
            },
            ip_address=get_request_ip(request),
        )
        
        # Launch Celery task for document processing
        logger.info(f"🚀 Launching Celery task...")
        document_id = new_doc.id
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        
        from app.celery_app import process_document_task
        try:
            task = process_document_task.delay(document_id)
            logger.info(f"✓ Celery task launched: task_id={task.id}")
        except Exception as e:
            logger.error(f"❌ Celery task launch error: {str(e)}", exc_info=True)
            # Don't fail upload if Celery fails, but log it
        
        logger.info(f"✓ Upload complete for document ID={new_doc.id}")
        return DocumentUploadResponse(
            id=new_doc.id,
            filename=new_doc.title,
            status=new_doc.status.value,
            message="File uploaded successfully. Processing started.",
            is_duplicate=False
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in upload_document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/upload-pdf")
async def upload_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    try:
        if file.content_type != "application/pdf" and not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are accepted")
        
        contents = await file.read()
        file_hash = hashlib.sha256(contents).hexdigest()
        
        existing_doc = db.query(Document).filter(Document.file_hash == file_hash).first()
        if existing_doc:
            return JSONResponse(
                status_code=409,
                content={
                    "status": "error",
                    "message": "PDF already exists in the system.",
                    "document_id": existing_doc.id
                }
            )

        storage_path = storage.upload_file(
            file_data=contents, 
            file_name=file.filename, 
            bucket_key="uploads", 
            content_type=file.content_type
        )

        new_doc = Document(
            document_number=f"pdf-{uuid.uuid4()}",  
            title=file.filename,                     
            document_type=DocumentTypeEnum.OTHER.value, 
            file_path=storage_path,
            file_size=len(contents),
            mime_type=file.content_type,
            file_hash=file_hash,
            status=DocumentStatusEnum.PENDING,
            created_by_id=current_user.id
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        log_audit_event(
            db=db,
            user=current_user,
            action=AuditActionEnum.UPLOAD,
            resource_type="document",
            resource_id=new_doc.id,
            document_id=new_doc.id,
            description="Document uploaded",
            changes={
                "file_name": new_doc.title,
                "file_size": new_doc.file_size,
                "mime_type": new_doc.mime_type,
            },
            ip_address=get_request_ip(request),
        )

        document_id = new_doc.id
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        
        logger.info(f"Processing PDF upload: {file.filename} (doc_id={document_id})")

        from app.celery_app import process_document_task

        process_task = process_document_task.delay(document_id)

        return JSONResponse({
            "status": "processing",
            "document_id": document_id,
            "filename": file.filename,
            "task_id": process_task.id,
            "message": "Document processing started (NV-014 pipeline). Check task status with the provided task_id"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/{document_id}/process")
async def process_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.celery_app import process_document_task

    task = process_document_task.delay(document_id)
    return JSONResponse({
        "status": "processing",
        "document_id": document_id,
        "task_id": task.id,
        "message": "Document processing task started"
    })


@router.get("/task-status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    from app.celery_app import celery_app
    
    try:
        task = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": task.status,
        }
        
        if task.status == "SUCCESS":
            response["result"] = task.result
        elif task.status == "FAILURE":
            response["error"] = str(task.info)
        elif task.status in ["STARTED", "RETRY"]:
            response["message"] = "Processing in progress..."
        
        return JSONResponse(response)
        
    except Exception as e:
        logger.error(f"Error checking task status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking status: {str(e)}")