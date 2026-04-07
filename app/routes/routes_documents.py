# app/routes/routes_documents.py
from datetime import timedelta
from typing import Any, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import tempfile

from app.dependencies.security import RBACRole, require_roles
from app.db.database import get_db
from app.models.document import Document, DocumentStatusEnum
from app.schemas_classification import ClassificationResponse
from app.schemas_related import RelatedDocumentsResponse, RelationType
from app.services.document_classification import DocumentClassificationService
from app.services import graph_service
from app.services.storage import StorageService, storage   # existing MinIO helper

router = APIRouter(prefix="/documents", tags=["Documents"])

logger = logging.getLogger(__name__)


@router.get("/")
async def list_documents(_=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR))):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.post("/")
async def create_document(_=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR))):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.get("/{document_id}")
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    storage_service = storage
    preview_url = None
    try:
        bucket_name, object_name = doc.file_path.split("/", 1)
        preview_url = storage_service.client.presigned_get_object(
            bucket_name,
            object_name,
            expires=timedelta(minutes=15),
        )
    except Exception:
        preview_url = None

    extracted_data = [
        {
            "id": item.id,
            "field_name": item.field_name,
            "field_value": item.field_value,
            "extraction_confidence": item.extraction_confidence,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
        for item in doc.extracted_data
    ]

    pages = [
        {
            "id": page.id,
            "page_number": page.page_number,
            "image_path": page.image_path,
            "text_content": page.text_content,
            "created_at": page.created_at.isoformat() if page.created_at else None,
        }
        for page in sorted(doc.pages, key=lambda item: item.page_number)
    ]

    payload: dict[str, Any] = {
        "id": doc.id,
        "document_number": doc.document_number,
        "document_type": doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type),
        "title": doc.title,
        "description": doc.description,
        "amount": doc.amount,
        "currency": doc.currency,
        "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        "fraud_score": doc.fraud_score,
        "confidence": doc.confidence,
        "file_path": doc.file_path,
        "file_size": doc.file_size,
        "mime_type": doc.mime_type,
        "page_count": doc.page_count,
        "file_hash": doc.file_hash,
        "document_date": doc.document_date.isoformat() if doc.document_date else None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        "archived_at": doc.archived_at.isoformat() if doc.archived_at else None,
        "created_by_id": doc.created_by_id,
        "dosar_id": doc.dosar_id,
        "nomenclator_id": doc.nomenclator_id,
        "preview_url": preview_url,
        "preview_url_expires_in_minutes": 15,
        "pages": pages,
        "extracted_data": extracted_data,
        "classification": {
            "document_type": doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type),
            "confidence": doc.confidence,
        },
        "nomenclator": None,
    }

    if doc.nomenclator:
        payload["nomenclator"] = {
            "id": doc.nomenclator.id,
            "code": doc.nomenclator.code,
            "name": doc.nomenclator.name,
            "description": doc.nomenclator.description,
        }

    if doc.status in {DocumentStatusEnum.PENDING, DocumentStatusEnum.UPLOADED, DocumentStatusEnum.PROCESSING}:
        return JSONResponse(payload, status_code=202)

    return JSONResponse(payload)


@router.get("/{document_id}/related", response_model=RelatedDocumentsResponse)
async def get_related_documents(
    document_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=20),
    relation_type: Optional[RelationType] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        if graph_service.get_document_node(str(document_id)) is None:
            return RelatedDocumentsResponse(
                document_id=str(document_id),
                related=[],
                page=page,
                page_size=page_size,
                total_count=0,
                total_pages=0,
            )

        skip = (page - 1) * page_size
        if relation_type == RelationType.SAME_DOSAR:
            related, total_count = graph_service.get_related_by_dosar(
                str(document_id),
                skip,
                page_size,
            )
        elif relation_type == RelationType.SAME_FURNIZOR:
            related, total_count = graph_service.get_related_by_furnizor(
                str(document_id),
                skip,
                page_size,
            )
        else:
            related, total_count = graph_service.get_all_related(
                str(document_id),
                skip,
                page_size,
            )
    except Exception as exc:
        try:
            from neo4j.exceptions import ServiceUnavailable, Neo4jError
        except ImportError:
            ServiceUnavailable = Neo4jError = Exception

        if isinstance(exc, (ServiceUnavailable, Neo4jError)):
            logger.error("Neo4j unavailable while fetching related documents: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Neo4j service unavailable",
            )
        raise

    total_pages = (total_count + page_size - 1) // page_size if total_count else 0
    return RelatedDocumentsResponse(
        document_id=str(document_id),
        related=related,
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
    )

@router.put("/{document_id}")
async def update_document(document_id: int, _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR))):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.delete("/{document_id}")
async def delete_document(document_id: int, _=Depends(require_roles(RBACRole.ADMIN))):
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
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
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