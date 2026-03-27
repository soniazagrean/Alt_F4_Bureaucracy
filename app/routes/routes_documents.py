# app/routes/routes_documents.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import tempfile

from app.db.database import get_db
from app.models.document import Document, DocumentStatusEnum
from app.schemas_classification import ClassificationResponse
from app.services.document_classification import DocumentClassificationService
from app.services.storage import StorageService   # existing MinIO helper

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("/")
async def list_documents():
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.post("/")
async def create_document():
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.get("/{document_id}")
async def get_document(document_id: int):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.put("/{document_id}")
async def update_document(document_id: int):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.delete("/{document_id}")
async def delete_document(document_id: int):
    return JSONResponse({"detail": "not implemented"}, status_code=501)


# ------------------------------------------------------------------ NV-007

@router.post(
    "/{document_id}/classify",
    response_model=ClassificationResponse,
    summary="Clasifică tipul unui document folosind LLM vision",
)
async def classify_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    """
    Descarcă prima pagină a documentului din MinIO, o trimite la
    OpenAI GPT-4o Vision și returnează { tip_document, confidence }.
    Actualizează câmpurile document_type și confidence în baza de date.
    """
    # 1. Fetch document from DB
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 2. Determine image path — use first page if available, else file_path
    image_minio_path: str
    if doc.pages:
        first_page = sorted(doc.pages, key=lambda p: p.page_number)[0]
        image_minio_path = first_page.image_path
    else:
        image_minio_path = doc.file_path

    # 3. Download from MinIO to a temp file
    storage = StorageService()
    with tempfile.NamedTemporaryFile(suffix=_get_extension(image_minio_path), delete=False) as tmp:
        tmp_path = tmp.name

    try:
        storage.download_file(image_minio_path, tmp_path)  # adjust to your StorageService API

        # 4. Classify
        svc = DocumentClassificationService()
        response = await svc.classify_async(tmp_path)

        if not response.success or not response.data:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=response.errors,
            )

        # 5. Persist result
        doc.document_type = response.data.tip_document
        doc.confidence = response.data.confidence
        doc.status = DocumentStatusEnum.CLASSIFIED
        db.commit()
        db.refresh(doc)

        return ClassificationResponse(
            success=True,
            data=response.data,
            document_id=document_id,
        )

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _get_extension(path: str) -> str:
    from pathlib import Path
    ext = Path(path).suffix
    return ext if ext else ".png"