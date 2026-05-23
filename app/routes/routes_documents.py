from datetime import timedelta, datetime
import json
from typing import Any, Optional, List
import logging

from fastapi import APIRouter, UploadFile, Depends, File, HTTPException, Query, Request, status, Form
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import os
import tempfile

from app.dependencies.security import RBACRole, require_roles
from app.db.database import get_db
from app.models.audit import AuditActionEnum
from app.models.archive import Dosar, NomenclatorEntry, PastrareEnum
from app.models.document import Document, DocumentStatusEnum, ExtractedData, DocumentTypeEnum
from app.models.user import User
from app.schemas import (
    DocumentUpdateRequest,
    DocumentCorrectionRequest,
    NomenclatorConfirmationRequest,
)
from app.schemas_classification import ClassificationResponse
from app.schemas_related import RelatedDocumentsResponse, RelationType
from app.services.audit_service import get_request_ip, log_audit_event, serialize_audit_value
from app.services.document_classification import DocumentClassificationService
from app.services import graph_service
from app.services.storage import StorageService, storage   # existing MinIO helper
from app.services.search import SearchService
from app.models.audit import AuditLog
from app.db.neo4j import get_neo4j_session
from app.models.document import DocumentPage
from pydantic import BaseModel


def _extract_data_map(doc: Document) -> dict[str, str]:
    return {
        item.field_name: item.field_value
        for item in getattr(doc, "extracted_data", [])
        if item.field_name
    }


def _parse_termen_pastrare(value: Optional[str]) -> PastrareEnum:
    if not value:
        return PastrareEnum.FIVE_YEARS
    try:
        return PastrareEnum(value)
    except ValueError:
        return PastrareEnum.FIVE_YEARS


def _generate_dosar_number_from_code(db: Session, code: str) -> str:
    prefix = code.replace(".", "").upper()
    count = db.query(Dosar).filter(Dosar.dosar_number.ilike(f"{prefix}-%")).count()
    return f"{prefix}-{count + 1:04d}"


def _create_dosar_from_suggestion(
    db: Session,
    code: str,
    title: str,
    termen_pastrare: Optional[str] = None,
) -> Dosar:
    nomenclator = db.query(NomenclatorEntry).filter(NomenclatorEntry.code == code).first()
    if not nomenclator:
        raise HTTPException(status_code=400, detail=f"Invalid suggested nomenclator code: {code}")

    existing = db.query(Dosar).filter(
        Dosar.nomenclator_id == nomenclator.id,
        Dosar.title == title,
    ).first()
    if existing:
        return existing

    dosar_number = _generate_dosar_number_from_code(db, code)
    new_dosar = Dosar(
        dosar_number=dosar_number,
        title=title,
        description=f"Auto-created from suggestion {code}",
        nomenclator_id=nomenclator.id,
        termen_pastrare=_parse_termen_pastrare(termen_pastrare),
    )
    db.add(new_dosar)
    db.commit()
    db.refresh(new_dosar)
    return new_dosar

import hashlib
import uuid
from app.schemas import DocumentUploadResponse
from app.models.alert import FraudAlert

router = APIRouter(prefix="/documents", tags=["Documents"])

logger = logging.getLogger(__name__)


@router.get("/", include_in_schema=False)
async def list_documents(_=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR))):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.post("/", include_in_schema=False)
async def create_document(_=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR))):
    return JSONResponse({"detail": "not implemented"}, status_code=501)


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    auto_archive: bool = Form(False),
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
            task = process_document_task.delay(document_id, auto_archive=auto_archive)
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
    auto_archive: bool = Form(False),
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

        process_task = process_document_task.delay(document_id, auto_archive=auto_archive)

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
    
@router.get("/search")
async def search_documents(
    q: str = Query("", min_length=0, description="Full-text search query"),
    tip_document: Optional[str] = Query(None, description="Filter by document type (invoice, contract, report, etc.)"),
    data_start: Optional[str] = Query(None, description="Filter documents from date (ISO format: YYYY-MM-DD)"),
    data_end: Optional[str] = Query(None, description="Filter documents until date (ISO format: YYYY-MM-DD)"),
    furnizor: Optional[str] = Query(None, description="Filter by supplier/vendor name"),
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
    - furnizor: Filter by supplier/vendor
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

        if furnizor:
            safe_furnizor = furnizor.replace('"', '\\"')
            filters.append(f'furnizor = "{safe_furnizor}"')
        
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

        # If MeiliSearch is empty and the query is unfiltered, fallback to PostgreSQL
        if not hits and not q and not filters and offset == 0:
            raise RuntimeError("MeiliSearch returned empty for unfiltered query")

        return JSONResponse({
            "status": "success",
            "source": "meilisearch",
            "query": q,
            "filters": {
                "tip_document": tip_document,
                "status": status,
                "data_start": data_start,
                "data_end": data_end,
                "furnizor": furnizor,
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

            join_extracted = bool(q or furnizor)
            if join_extracted:
                query = query.outerjoin(
                    ExtractedData,
                    and_(
                        ExtractedData.document_id == Document.id,
                        ExtractedData.field_name.ilike("furnizor"),
                    ),
                )
            
            # Full-text search
            if q:
                search_term = f"%{q}%"
                text_filters = [
                    Document.title.ilike(search_term),
                    Document.description.ilike(search_term),
                    Document.document_number.ilike(search_term),
                    Document.invoice_number.ilike(search_term),
                ]
                if join_extracted:
                    text_filters.append(ExtractedData.field_value.ilike(search_term))
                query = query.filter(or_(*text_filters))

            if furnizor:
                supplier_term = f"%{furnizor}%"
                query = query.filter(
                    or_(
                        ExtractedData.field_value.ilike(supplier_term),
                        Document.title.ilike(supplier_term),
                        Document.description.ilike(supplier_term),
                    )
                )
            
            # Type filter
            if tip_document and tip_document != "All":
                query = query.filter(Document.document_type == tip_document.lower())
            
            # Status filter
            if status and status != "All":
                query = query.filter(Document.status == status.lower())
            
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
            
            if join_extracted:
                query = query.distinct()

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
                    "invoice_number": doc.invoice_number,
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
                    "furnizor": furnizor,
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    log_audit_event(
        db=db,
        user=current_user,
        action=AuditActionEnum.INSPECT,
        resource_type="document",
        resource_id=doc.id,
        document_id=doc.id,
        description="Document inspected",
        ip_address=get_request_ip(request),
    )

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
    
    # ANAF supplier validation (best-effort — never raises to the caller)
    anaf_validation = None
    try:
        from app.services.anaf_service import validate_cui
        # Schema stores field as "CUI" (uppercase); normalise before lookup
        _cui = (extracted_data_dict.get("CUI") or extracted_data_dict.get("cui")
                or extracted_data_dict.get("COD_FISCAL") or extracted_data_dict.get("cod_fiscal"))
        if _cui:
            anaf_validation = validate_cui(_cui)
    except Exception:
        anaf_validation = {"found": False, "error": "ANAF service unavailable"}

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
    elif extracted_data_dict.get("cod_nomenclator"):
        alternatives = []
        raw_alternatives = extracted_data_dict.get("nomenclator_alternative")
        if raw_alternatives:
            try:
                alternatives = json.loads(raw_alternatives)
            except Exception:
                alternatives = []

        confidence_value = extracted_data_dict.get("nomenclator_confidence")
        try:
            confidence_value = float(confidence_value) if confidence_value is not None else 0.0
        except (TypeError, ValueError):
            confidence_value = 0.0

        nomenclator_suggestion = {
            "cod": extracted_data_dict.get("cod_nomenclator"),
            "descriere": extracted_data_dict.get("nomenclator_rationale") or "AI nomenclator suggestion",
            "incidenta": "0",
            "confidence": confidence_value,
            "dosar_propus": extracted_data_dict.get("dosar_propus"),
            "termen_pastrare": extracted_data_dict.get("termen_pastrare"),
            "nivel_confidentialitate": extracted_data_dict.get("nivel_confidentialitate"),
            "alternative": alternatives,
        }

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
        "invoice_number": doc.invoice_number,
        "document_type": doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type),
        "title": doc.title,
        "description": doc.description,
        "amount": doc.amount,
        "currency": doc.currency,
        "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        "fraud_score": doc.fraud_score,
        "anaf_validation": anaf_validation,
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

@router.get("/{document_id}/alerts")
async def get_document_alerts(
    document_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    alerts = db.query(FraudAlert).filter(
        FraudAlert.document_id == document_id,
        FraudAlert.is_resolved == 0
    ).all()
    
    return [{
        "id": a.id,
        "type": a.anomaly_type,
        "score": a.fraud_score,
        "risk": a.risk_level,
        "description": a.description,
        "detected_at": a.detected_at.isoformat()
    } for a in alerts]

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
async def update_document(
    document_id: int,
    payload: DocumentUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if payload.document_number and payload.document_number != doc.document_number:
        existing = (
            db.query(Document)
            .filter(Document.document_number == payload.document_number, Document.id != document_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Document number already exists")

    changes: dict[str, dict[str, object]] = {}

    def apply_change(field_name: str, new_value: object) -> None:
        if new_value is None:
            return
        current_value = getattr(doc, field_name)
        if new_value != current_value:
            changes[field_name] = {
                "from": serialize_audit_value(current_value),
                "to": serialize_audit_value(new_value),
            }
            setattr(doc, field_name, new_value)

    apply_change("document_number", payload.document_number)
    apply_change("title", payload.title)
    apply_change("description", payload.description)
    apply_change("amount", payload.amount)
    apply_change("currency", payload.currency.upper() if payload.currency else payload.currency)
    apply_change("document_date", payload.document_date)
    apply_change("document_type", payload.document_type)

    if changes and doc.status == DocumentStatusEnum.RETURNED:
        changes["status"] = {
            "from": serialize_audit_value(doc.status),
            "to": serialize_audit_value(DocumentStatusEnum.REVIEW),
        }
        doc.status = DocumentStatusEnum.REVIEW

    if not changes:
        return JSONResponse({
            "status": "no_changes",
            "document_id": document_id,
        })

    db.commit()
    db.refresh(doc)

    log_audit_event(
        db=db,
        user=current_user,
        action=AuditActionEnum.MANUAL_EDIT,
        resource_type="document",
        resource_id=doc.id,
        document_id=doc.id,
        description="Document updated manually",
        changes=changes,
        ip_address=get_request_ip(request),
    )

    return JSONResponse({
        "status": "success",
        "document_id": doc.id,
        "updated_fields": sorted(changes.keys()),
    })

@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN)),
):
    """Delete a document and related resources (MinIO objects, MeiliSearch index, Neo4j node, alerts, audit refs)."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Collect storage object paths to remove
    storage_paths: list[str] = []
    if getattr(doc, "file_path", None):
        storage_paths.append(doc.file_path)

    for page in getattr(doc, "pages", []) or []:
        if getattr(page, "image_path", None):
            storage_paths.append(page.image_path)

    # 1) Remove from MeiliSearch (best-effort)
    try:
        search_svc = SearchService()
        try:
            search_svc.delete_document(str(document_id))
        except Exception as e:
            logger.warning("Failed to remove document from MeiliSearch: %s", e)
    except Exception:
        logger.debug("SearchService unavailable or misconfigured")

    # 2) Remove Neo4j node (best-effort)
    try:
        with get_neo4j_session() as session:
            session.execute_write(lambda tx: tx.run("MATCH (d:Document {id: $id}) DETACH DELETE d", id=str(document_id)))
    except Exception as e:
        logger.warning("Failed to remove Neo4j node for document %s: %s", document_id, e)

    # 3) Delete FraudAlert rows referencing the document (to avoid FK violations)
    try:
        db.query(FraudAlert).filter(FraudAlert.document_id == document_id).delete(synchronize_session=False)
    except Exception as e:
        logger.warning("Failed to delete FraudAlert rows for document %s: %s", document_id, e)

    # 4) Nullify AuditLog.document_id to preserve audit entries without FK constraints
    try:
        db.query(AuditLog).filter(AuditLog.document_id == document_id).update({AuditLog.document_id: None}, synchronize_session=False)
    except Exception as e:
        logger.warning("Failed to nullify AuditLog.document_id for document %s: %s", document_id, e)

    # 5) Delete storage objects from MinIO (best-effort)
    for path in storage_paths:
        try:
            if not path:
                continue
            bucket_name, object_name = path.split("/", 1)
            storage.client.remove_object(bucket_name, object_name)
            logger.info("Deleted storage object: %s", path)
        except Exception as e:
            logger.warning("Failed to delete storage object %s: %s", path, e)

    # 6) Finally delete the DB document (cascade should remove pages and extracted_data)
    try:
        db.delete(doc)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Failed to delete Document %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

    # Log audit event for deletion
    try:
        log_audit_event(
            db=db,
            user=current_user,
            action=AuditActionEnum.DELETE,
            resource_type="document",
            resource_id=document_id,
            document_id=document_id,
            description="Document deleted by user",
            changes=None,
            ip_address=get_request_ip(request),
        )
    except Exception:
        logger.debug("Failed to log audit event for document deletion %s", document_id)

    return JSONResponse({"status": "deleted", "document_id": document_id})


# ------------------------------------------------------------------ NV-007

@router.post(
    "/{document_id}/classify",
    response_model=ClassificationResponse,
    summary="Clasifică tipul unui document folosind LLM vision",
)
async def classify_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
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
        previous_type = doc.document_type
        previous_confidence = doc.confidence
        doc.document_type = response.data.tip_document
        doc.confidence = response.data.confidence
        doc.status = DocumentStatusEnum.CLASSIFIED
        db.commit()
        db.refresh(doc)

        changes = {
            "document_type": {
                "from": serialize_audit_value(previous_type),
                "to": serialize_audit_value(doc.document_type),
            },
            "confidence": {
                "from": serialize_audit_value(previous_confidence),
                "to": serialize_audit_value(doc.confidence),
            },
        }

        log_audit_event(
            db=db,
            user=current_user,
            action=AuditActionEnum.CLASSIFY,
            resource_type="document",
            resource_id=doc.id,
            document_id=doc.id,
            description="Document classified",
            changes=changes,
            ip_address=get_request_ip(request),
        )

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
    payload: NomenclatorConfirmationRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    """Confirm nomenclator/dosar suggestion for a document in review."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != DocumentStatusEnum.REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"Can only confirm nomenclator during REVIEW. Current status: {doc.status.value}",
        )

    changes: dict[str, dict[str, object]] = {}

    extracted_map = _extract_data_map(doc)

    if payload.create_dosar_from_suggestion:
        if payload.dosar_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Cannot create a suggested dosar when dosar_id is provided",
            )

        suggested_code = payload.suggested_nomenclator_code or extracted_map.get("cod_nomenclator")
        suggested_title = payload.suggested_dosar_title or extracted_map.get("dosar_propus")
        if not suggested_code or not suggested_title:
            raise HTTPException(
                status_code=400,
                detail="Missing suggested code or title for auto-creating dosar",
            )

        created_dosar = _create_dosar_from_suggestion(
            db,
            suggested_code,
            suggested_title,
            extracted_map.get("termen_pastrare"),
        )
        payload.dosar_id = created_dosar.id
        payload.nomenclator_id = created_dosar.nomenclator_id

    if payload.nomenclator_id is not None:
        nomenclator = db.query(NomenclatorEntry).filter(NomenclatorEntry.id == payload.nomenclator_id).first()
        if not nomenclator:
            raise HTTPException(status_code=400, detail="Invalid nomenclator_id")
        if payload.nomenclator_id != doc.nomenclator_id:
            changes["nomenclator_id"] = {
                "from": serialize_audit_value(doc.nomenclator_id),
                "to": serialize_audit_value(payload.nomenclator_id),
            }
            doc.nomenclator_id = payload.nomenclator_id

    if payload.dosar_id is not None:
        dosar = db.query(Dosar).filter(Dosar.id == payload.dosar_id).first()
        if not dosar:
            raise HTTPException(status_code=400, detail="Invalid dosar_id")
        if payload.dosar_id != doc.dosar_id:
            changes["dosar_id"] = {
                "from": serialize_audit_value(doc.dosar_id),
                "to": serialize_audit_value(payload.dosar_id),
            }
            doc.dosar_id = payload.dosar_id

    if payload.confirmed:
        if not doc.nomenclator_confirmed:
            changes["nomenclator_confirmed"] = {
                "from": serialize_audit_value(doc.nomenclator_confirmed),
                "to": True,
            }
            doc.nomenclator_confirmed = True
            doc.nomenclator_confirmed_at = datetime.utcnow()
            changes["nomenclator_confirmed_at"] = {
                "from": None,
                "to": serialize_audit_value(doc.nomenclator_confirmed_at),
            }
    else:
        if doc.nomenclator_confirmed:
            previous_confirmed_at = doc.nomenclator_confirmed_at
            changes["nomenclator_confirmed"] = {
                "from": True,
                "to": False,
            }
            doc.nomenclator_confirmed = False
            doc.nomenclator_confirmed_at = None
            changes["nomenclator_confirmed_at"] = {
                "from": serialize_audit_value(previous_confirmed_at),
                "to": None,
            }

    if not changes:
        return JSONResponse({
            "status": "no_changes",
            "document_id": document_id,
        })

    db.commit()
    db.refresh(doc)

    log_audit_event(
        db=db,
        user=current_user,
        action=AuditActionEnum.APPROVE,
        resource_type="document",
        resource_id=doc.id,
        document_id=doc.id,
        description="Nomenclator/dosar confirmation",
        changes=changes,
        ip_address=get_request_ip(request),
    )

    return JSONResponse({
        "status": "success",
        "document_id": document_id,
        "nomenclator_id": doc.nomenclator_id,
        "dosar_id": doc.dosar_id,
        "confirmed": doc.nomenclator_confirmed,
        "confirmed_at": doc.nomenclator_confirmed_at.isoformat() if doc.nomenclator_confirmed_at else None,
    })


@router.post("/{document_id}/request-manual-correction")
async def request_manual_correction(
    document_id: int,
    payload: DocumentCorrectionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    """Request manual correction during review."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != DocumentStatusEnum.REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"Can only request correction during REVIEW. Current status: {doc.status.value}",
        )

    previous_status = doc.status
    doc.status = DocumentStatusEnum.RETURNED
    db.commit()
    db.refresh(doc)

    changes = {
        "status": {
            "from": serialize_audit_value(previous_status),
            "to": serialize_audit_value(doc.status),
        }
    }
    if payload.reason:
        changes["reason"] = {"from": None, "to": payload.reason}

    log_audit_event(
        db=db,
        user=current_user,
        action=AuditActionEnum.UPDATE,
        resource_type="document",
        resource_id=doc.id,
        document_id=doc.id,
        description="Manual correction requested",
        changes=changes,
        ip_address=get_request_ip(request),
    )

    return JSONResponse({
        "status": "success",
        "document_id": doc.id,
        "new_status": doc.status.value,
        "reason": payload.reason,
    })


@router.post("/{document_id}/approve")
async def approve_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    """Approve a reviewed document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != DocumentStatusEnum.REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"Can only approve during REVIEW. Current status: {doc.status.value}",
        )

    if not doc.nomenclator_confirmed:
        raise HTTPException(
            status_code=400,
            detail="Nomenclator must be confirmed before approval",
        )

    if not doc.nomenclator_id or not doc.dosar_id:
        raise HTTPException(
            status_code=400,
            detail="Nomenclator and dosar must be set before approval",
        )

    previous_status = doc.status
    doc.status = DocumentStatusEnum.APPROVED
    db.commit()
    db.refresh(doc)

    try:
        search_svc = SearchService()
        prepared_doc = search_svc.prepare_document_for_indexing(doc)
        search_svc.add_documents([prepared_doc])
        logger.info(f"✓ MeiliSearch updated for doc {doc.id}")
    except Exception as e:
        logger.warning(f"Failed to update MeiliSearch: {str(e)}")

    changes = {
        "status": {
            "from": serialize_audit_value(previous_status),
            "to": serialize_audit_value(doc.status),
        }
    }

    log_audit_event(
        db=db,
        user=current_user,
        action=AuditActionEnum.APPROVE,
        resource_type="document",
        resource_id=doc.id,
        document_id=doc.id,
        description="Document approved",
        changes=changes,
        ip_address=get_request_ip(request),
    )

    return JSONResponse({
        "status": "success",
        "document_id": doc.id,
        "new_status": doc.status.value,
        "approved_at": doc.updated_at.isoformat() if doc.updated_at else None,
    })


@router.post("/{document_id}/return")
async def return_document(
    document_id: int,
    payload: DocumentCorrectionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    """Return a reviewed document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != DocumentStatusEnum.REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"Can only return during REVIEW. Current status: {doc.status.value}",
        )

    previous_status = doc.status
    doc.status = DocumentStatusEnum.RETURNED
    db.commit()
    db.refresh(doc)

    changes = {
        "status": {
            "from": serialize_audit_value(previous_status),
            "to": serialize_audit_value(doc.status),
        }
    }
    if payload.reason:
        changes["reason"] = {"from": None, "to": payload.reason}

    log_audit_event(
        db=db,
        user=current_user,
        action=AuditActionEnum.UPDATE,
        resource_type="document",
        resource_id=doc.id,
        document_id=doc.id,
        description="Document returned",
        changes=changes,
        ip_address=get_request_ip(request),
    )

    return JSONResponse({
        "status": "success",
        "document_id": doc.id,
        "new_status": doc.status.value,
        "reason": payload.reason,
    })


@router.post("/{document_id}/archive")
async def archive_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    """Archive an approved document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != DocumentStatusEnum.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Can only archive during APPROVED. Current status: {doc.status.value}",
        )

    previous_status = doc.status
    previous_archived_at = doc.archived_at
    doc.status = DocumentStatusEnum.ARCHIVED
    if not doc.archived_at:
        doc.archived_at = datetime.utcnow()
    db.commit()
    db.refresh(doc)

    try:
        search_svc = SearchService()
        prepared_doc = search_svc.prepare_document_for_indexing(doc)
        search_svc.add_documents([prepared_doc])
        logger.info("✓ MeiliSearch updated for doc %s", doc.id)
    except Exception as e:
        logger.warning("Failed to update MeiliSearch: %s", str(e))

    changes = {
        "status": {
            "from": serialize_audit_value(previous_status),
            "to": serialize_audit_value(doc.status),
        }
    }
    if previous_archived_at != doc.archived_at:
        changes["archived_at"] = {
            "from": serialize_audit_value(previous_archived_at),
            "to": serialize_audit_value(doc.archived_at),
        }

    log_audit_event(
        db=db,
        user=current_user,
        action=AuditActionEnum.ARCHIVE,
        resource_type="document",
        resource_id=doc.id,
        document_id=doc.id,
        description="Document archived",
        changes=changes,
        ip_address=get_request_ip(request),
    )

    return JSONResponse({
        "status": "success",
        "document_id": doc.id,
        "new_status": doc.status.value,
        "archived_at": doc.archived_at.isoformat() if doc.archived_at else None,
    })


def _get_extension(path: str) -> str:
    from pathlib import Path
    ext = Path(path).suffix
    return ext if ext else ".png"