import logging
import hashlib
import uuid
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.document import Document, DocumentStatusEnum, DocumentTypeEnum
from app.services.storage import storage
from app.schemas import DocumentUploadResponse

from app.celery_app import convert_pdf_to_images_task

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. Read file content
    contents = await file.read()
    
    # 2. Calculate SHA-256 Hash
    file_hash = hashlib.sha256(contents).hexdigest()
    
    # 3. Deduplication Check
    existing_doc = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing_doc:
        return DocumentUploadResponse(
            id=existing_doc.id,
            filename=existing_doc.title,
            status=existing_doc.status.value,
            message="File already exists (duplicate detected).",
            is_duplicate=True
        )
    
    # 4. Upload to MinIO
    try:
        # Use the existing 'storage' instance and method
        storage_path = storage.upload_file(
            file_data=contents, 
            file_name=file.filename, 
            bucket_key="uploads", # Matches your MINIO_BUCKET_UPLOADS
            content_type=file.content_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
    
    # 5. Create Database Record
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
        created_by_id=1  # Placeholder: Assumes user ID 1 exists
    )
    
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    return DocumentUploadResponse(
        id=new_doc.id,
        filename=new_doc.title,
        status=new_doc.status.value,
        message="File uploaded successfully.",
        is_duplicate=False
    )

@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
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
            created_by_id=1  
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        document_id = new_doc.id
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        
        logger.info(f"Processing PDF upload: {file.filename} (doc_id={document_id})")
        
        conversion_task = convert_pdf_to_images_task.delay(
            pdf_path=tmp_path,
            document_id=document_id,
            dpi=300
        )
        
        return JSONResponse({
            "status": "processing",
            "document_id": document_id,
            "filename": file.filename,
            "conversion_task_id": conversion_task.id,
            "message": "PDF conversion started. Check task status with the provided task_id"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
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