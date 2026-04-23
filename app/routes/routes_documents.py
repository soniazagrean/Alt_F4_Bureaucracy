from datetime import timedelta, datetime
from typing import Any, Optional, List
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import os
import tempfile

from app.dependencies.security import RBACRole, require_roles
from app.db.database import get_db
from app.models.document import Document, DocumentStatusEnum, ExtractedData
from app.schemas_classification import ClassificationResponse
from app.schemas_related import RelatedDocumentsResponse, RelationType
from app.services.document_classification import DocumentClassificationService
from app.services import graph_service
from app.services.storage import StorageService, storage   # existing MinIO helper
from app.services.search import SearchService
from pydantic import BaseModel

router = APIRouter(prefix="/documents", tags=["Documents"])

logger = logging.getLogger(__name__)


@router.get("/")
async def list_documents(_=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR))):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.post("/")
async def create_document(_=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR))):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.get("/search")
async def search_documents(
    q: str = Query("", min_length=0, description="Full-text search query"),
    tip_document: Optional[str] = Query(None, description="Filter by document type (invoice, contract, report, etc.)"),
    data_start: Optional[str] = Query(None, description="Filter documents from date (ISO format: YYYY-MM-DD)"),
    data_end: Optional[str] = Query(None, description="Filter documents until date (ISO format: YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter by status (pending, archived, error, etc.)"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    """
    NV-021: Full-text search endpoint for indexed documents.
    
    Queries MeiliSearch with fallback to PostgreSQL if MeiliSearch is unavailable.
    
    Query Parameters:
    - q: Full-text search query
    - tip_document: Filter by document type
    - data_start / data_end: Date range filtering
    - status: Filter by processing status
    - limit: Results per page (max 100)
    - offset: Pagination offset
    
    Returns:
    - List of matching documents with relevance scores
    - Total hit count
    - MeiliSearch processing time
    """
    try:
        search_service = SearchService()
        
        # Build MeiliSearch filter
        filters = []
        
        if tip_document and tip_document != "All":
            filters.append(f'tip_document = "{tip_document.lower()}"')
        
        if status and status != "All":
            filters.append(f'status = "{status.lower()}"')
        
        # Date range filtering
        if data_start or data_end:
            date_filter = []
            if data_start:
                try:
                    start_dt = datetime.fromisoformat(data_start)
                    date_filter.append(f"data >= '{start_dt.isoformat()}'")
                except ValueError:
                    logger.warning(f"Invalid data_start format: {data_start}")
            if data_end:
                try:
                    end_dt = datetime.fromisoformat(data_end)
                    # End of day
                    end_dt = end_dt.replace(hour=23, minute=59, second=59)
                    date_filter.append(f"data <= '{end_dt.isoformat()}'")
                except ValueError:
                    logger.warning(f"Invalid data_end format: {data_end}")
            if date_filter:
                filters.append(" AND ".join(date_filter))
        
        # Prepare search parameters
        search_params = {
            "limit": limit,
            "offset": offset,
        }
        if filters:
            search_params["filter"] = filters
        
        # Execute MeiliSearch query
        logger.info(f"Searching MeiliSearch: q={q}, filters={filters}")
        result = search_service.search(q, search_params)
        
        # Format response with relevance scores
        hits = result.get("hits", [])
        total_hits = result.get("estimatedTotalHits", 0)
        processing_time_ms = result.get("processingTimeMs", 0)
        
        return JSONResponse({
            "status": "success",
            "source": "meilisearch",
            "query": q,
            "filters": {
                "tip_document": tip_document,
                "status": status,
                "data_start": data_start,
                "data_end": data_end,
            },
            "hits": hits,
            "total_hits": total_hits,
            "limit": limit,
            "offset": offset,
            "processing_time_ms": processing_time_ms,
        })
        
    except Exception as e:
        logger.warning(f"MeiliSearch search failed, falling back to PostgreSQL: {str(e)}")
        
        # Fallback to PostgreSQL full-text search
        try:
            query = db.query(Document)
            
            # Full-text search
            if q:
                search_term = f"%{q}%"
                query = query.filter(
                    or_(
                        Document.title.ilike(search_term),
                        Document.description.ilike(search_term),
                        Document.document_number.ilike(search_term),
                    )
                )
            
            # Type filter
            if tip_document and tip_document != "All":
                query = query.filter(Document.document_type.astext == tip_document.lower())
            
            # Status filter
            if status and status != "All":
                query = query.filter(Document.status.astext == status.lower())
            
            # Date range filter
            filters_date = []
            if data_start:
                try:
                    start_dt = datetime.fromisoformat(data_start)
                    filters_date.append(Document.document_date >= start_dt)
                except ValueError:
                    pass
            if data_end:
                try:
                    end_dt = datetime.fromisoformat(data_end)
                    end_dt = end_dt.replace(hour=23, minute=59, second=59)
                    filters_date.append(Document.document_date <= end_dt)
                except ValueError:
                    pass
            
            if filters_date:
                query = query.filter(and_(*filters_date))
            
            # Get total count before pagination
            total_hits = query.count()
            
            # Apply pagination
            documents = query.offset(offset).limit(limit).all()
            
            # Format response
            hits = []
            for doc in documents:
                hits.append({
                    "id": str(doc.id),
                    "title": doc.title,
                    "description": doc.description,
                    "tip_document": doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type),
                    "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
                    "document_number": doc.document_number,
                    "amount": doc.amount,
                    "currency": doc.currency,
                    "data": doc.document_date.isoformat() if doc.document_date else None,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                })
            
            return JSONResponse({
                "status": "success",
                "source": "postgresql",
                "query": q,
                "filters": {
                    "tip_document": tip_document,
                    "status": status,
                    "data_start": data_start,
                    "data_end": data_end,
                },
                "hits": hits,
                "total_hits": total_hits,
                "limit": limit,
                "offset": offset,
                "processing_time_ms": None,
            })
            
        except Exception as pg_error:
            logger.error(f"PostgreSQL fallback search also failed: {str(pg_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Search failed: {str(pg_error)}"
            )

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
        preview_url = storage_service.get_presigned_url(bucket_name, object_name, expires_minutes=15)
    except Exception:
        preview_url = None

    # Keep both list and map forms for backward compatibility.
    extracted_data_dict = {}
    extracted_data_list = []
    for item in doc.extracted_data:
        extracted_data_dict[item.field_name] = item.field_value
        extracted_data_list.append(
            {
                "id": item.id,
                "field_name": item.field_name,
                "field_value": item.field_value,
                "extraction_confidence": item.extraction_confidence,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
        )
    
    # Get nomenclator suggestion if available
    nomenclator_suggestion = None
    if doc.nomenclator_id:
        try:
            # Try to fetch nomenclator suggestion from database/service
            # For now, construct from nomenclator relationship if available
            if doc.nomenclator:
                nomenclator_suggestion = {
                    "cod": doc.nomenclator.code,
                    "descriere": doc.nomenclator.description or doc.nomenclator.name,
                    "incidenta": "0",  # TODO: add to DB if needed
                    "confidence": doc.confidence or 0.0,
                    "alternative": [],
                }
        except Exception:
            pass

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
        "nomenclator_confirmed": doc.nomenclator_confirmed if hasattr(doc, "nomenclator_confirmed") else False,
        "nomenclator_confirmed_at": doc.nomenclator_confirmed_at.isoformat() if hasattr(doc, "nomenclator_confirmed_at") and doc.nomenclator_confirmed_at else None,
        "preview_url": preview_url,
        "preview_url_expires_in_minutes": 15,
        "pages": pages,
        # Legacy list contract used by existing API tests/consumers.
        "extracted_data": extracted_data_list,
        # Map format for UI consumers that render key-value extraction panels.
        "extracted_data_map": extracted_data_dict,
        "nomenclator_suggestion": nomenclator_suggestion,
        "classification": {
            "document_type": doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type),
            "tip_document": doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type),
            "confidence": doc.confidence,
        },
        "nomenclator": None,
    }
    
    # Ensure classification confidence is never None (API contract)
    if payload.get("classification") and payload["classification"].get("confidence") is None:
        payload["classification"]["confidence"] = 0.0

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


@router.post("/reindex/meilisearch")
async def reindex_documents(
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN)),
):
    """Rebuild MeiliSearch index from database (admin only)"""
    try:
        # Get all documents from database
        documents = db.query(Document).all()
        
        if not documents:
            return JSONResponse({"message": "No documents to index", "count": 0})
        
        # Prepare documents for indexing
        indexed_docs = []
        search_svc = SearchService()
        
        for doc in documents:
            prepared = SearchService.prepare_document_for_indexing(doc)
            if prepared:
                indexed_docs.append(prepared)
        
        # Add to MeiliSearch
        search_svc.ensure_index_exists()
        search_svc.add_documents(indexed_docs)
        
        logger.info(f"Reindexed {len(indexed_docs)} documents in MeiliSearch")
        return JSONResponse({
            "message": "Reindexing completed",
            "count": len(indexed_docs),
            "documents": [{"id": d["id"], "title": d.get("title", "N/A")} for d in indexed_docs[:5]]
        })
    
    except Exception as e:
        logger.error(f"Reindexing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Reindexing failed: {str(e)}")


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    """Download document PDF file"""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        # Parse file path from MinIO
        bucket_name, object_name = doc.file_path.split("/", 1)
        
        # Download file from MinIO
        storage_service = storage
        response = storage_service.client.get_object(bucket_name, object_name)
        
        # Return as streaming response
        return StreamingResponse(
            iter(response.stream(amt=1024*1024)),
            media_type=doc.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename=\"{doc.title}\""
            }
        )
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download document: {str(e)}")


@router.get("/{document_id}/page-image/{page_number}")
async def get_page_image(
    document_id: int,
    page_number: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    """Get page image from document"""
    from app.models.document import DocumentPage
    
    try:
        # Find page
        page = db.query(DocumentPage).filter(
            and_(
                DocumentPage.document_id == document_id,
                DocumentPage.page_number == page_number
            )
        ).first()
        
        if not page or not page.image_path:
            raise HTTPException(status_code=404, detail="Page not found or image not available yet")
        
        # Get image from MinIO
        bucket_name, object_name = page.image_path.split("/", 1)
        response = storage.client.get_object(bucket_name, object_name)
        
        # Return as streaming response
        return StreamingResponse(
            iter(response.stream(amt=1024*1024)),
            media_type="image/png",
            headers={
                "Content-Disposition": f"inline; filename=\"page_{page_number}.png\""
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting page image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Could not retrieve page image: {str(e)}")


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


@router.post("/{document_id}/confirm-nomenclator")
async def confirm_nomenclator(
    document_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    """
    NV-025: Confirm nomenclator suggestion for a document.
    
    Marks the nomenclator suggestion as confirmed by the user.
    This is prepared for Sprint 3 integration with the nomenclator system.
    
    Parameters:
    - document_id: ID of the document
    - payload: {"confirmed": True}
    
    Returns:
    - Updated document with nomenclator confirmation
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if document is in ARCHIVED status (NV-025 requirement)
    if doc.status != DocumentStatusEnum.ARCHIVED:
        raise HTTPException(
            status_code=400,
            detail=f"Can only confirm nomenclator for ARCHIVED documents. Current status: {doc.status.value}"
        )
    
    # Mark nomenclator as confirmed (Sprint 3 will implement full logic)
    # Safely handle case where columns may not exist yet
    try:
        doc.nomenclator_confirmed = True
        doc.nomenclator_confirmed_at = datetime.utcnow()
        db.commit()
        db.refresh(doc)
        
        return JSONResponse({
            "status": "success",
            "document_id": document_id,
            "message": "Nomenclator confirmed successfully",
            "confirmed_at": doc.nomenclator_confirmed_at.isoformat() if hasattr(doc, 'nomenclator_confirmed_at') and doc.nomenclator_confirmed_at else None,
        })
    except Exception as e:
        # If columns don't exist yet, log confirmation to log instead
        logger.warning(f"Could not persist nomenclator confirmation (columns may not exist): {str(e)}")
        return JSONResponse({
            "status": "success",
            "document_id": document_id,
            "message": "Nomenclator confirmation recorded (Sprint 3 persistence pending)",
            "warning": "Database schema not yet migrated for this feature"
        })


def _get_extension(path: str) -> str:
    from pathlib import Path
    ext = Path(path).suffix
    return ext if ext else ".png"