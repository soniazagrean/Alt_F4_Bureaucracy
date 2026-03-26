from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
import hashlib
from app.db.database import get_db
from app.models.document import Document, DocumentStatusEnum, DocumentTypeEnum
from app.services.storage import storage  # <--- Import the singleton instance
from app.schemas import DocumentUploadResponse
import uuid

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