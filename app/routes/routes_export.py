import csv
import io
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.dependencies.security import RBACRole, require_roles
from app.db.database import get_db
from app.models.audit import AuditActionEnum
from app.models.document import Document
from app.models.user import User
from app.services.audit_service import get_request_ip, log_audit_event
from app.services.pdfa_utils import PDFAConversionError, convert_pdf_to_pdfa
from app.services.storage import storage

router = APIRouter(prefix="/export", tags=["Export"])

logger = logging.getLogger(__name__)

SAFE_FILENAME = re.compile(r"[^A-Za-z0-9_.-]+")


def _sanitize_filename(value: str, fallback: str) -> str:
    cleaned = Path(value).name
    cleaned = SAFE_FILENAME.sub("_", cleaned).strip("._")
    if not cleaned:
        cleaned = fallback
    return cleaned


def _document_filenames(doc: Document) -> tuple[str, str]:
    base_name = _sanitize_filename(
        doc.title or doc.document_number or f"document_{doc.id}.pdf",
        f"document_{doc.id}.pdf",
    )
    if not base_name.lower().endswith(".pdf"):
        base_name = f"{base_name}.pdf"
    stem = Path(base_name).stem
    return base_name, f"{stem}_pdfa.pdf"


def _iter_file(path: str, chunk_size: int = 1024 * 1024):
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            yield chunk
    os.unlink(path)


def _registry_headers() -> list[str]:
    return [
        "id",
        "document_number",
        "title",
        "document_type",
        "status",
        "document_date",
        "created_at",
        "archived_at",
        "dosar_id",
        "nomenclator_id",
        "nomenclator_confirmed",
        "file_hash",
        "file_size",
        "mime_type",
        "file_path",
    ]


def _registry_row(doc: Document) -> list[str]:
    def enum_value(value):
        return value.value if hasattr(value, "value") else str(value)

    return [
        str(doc.id),
        doc.document_number or "",
        doc.title or "",
        enum_value(doc.document_type) if doc.document_type is not None else "",
        enum_value(doc.status) if doc.status is not None else "",
        doc.document_date.isoformat() if doc.document_date else "",
        doc.created_at.isoformat() if doc.created_at else "",
        doc.archived_at.isoformat() if doc.archived_at else "",
        str(doc.dosar_id) if doc.dosar_id is not None else "",
        str(doc.nomenclator_id) if doc.nomenclator_id is not None else "",
        "true" if doc.nomenclator_confirmed else "false",
        doc.file_hash or "",
        str(doc.file_size) if doc.file_size is not None else "",
        doc.mime_type or "",
        doc.file_path or "",
    ]


def _iter_registry_csv(documents: list[Document]):
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(_registry_headers())
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)

    for doc in documents:
        writer.writerow(_registry_row(doc))
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)


@router.get("/registry")
async def export_registry(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    documents = db.query(Document).order_by(Document.id.asc()).all()

    log_audit_event(
        db=db,
        user=current_user,
        action=AuditActionEnum.DOWNLOAD,
        resource_type="registry",
        resource_id=0,
        description="Registry exported",
        changes={"total_documents": len(documents)},
        ip_address=get_request_ip(request),
    )

    filename = f"registry_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        _iter_registry_csv(documents),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get("/document/{document_id}")
async def export_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.mime_type and doc.mime_type.lower() not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=400, detail="Only PDF documents can be exported as PDF/A")

    try:
        bucket_name, object_name = doc.file_path.split("/", 1)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Invalid document file path") from exc

    base_name, pdfa_name = _document_filenames(doc)

    input_path = None
    output_path = None
    streaming_ready = False
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(object_name).suffix or ".pdf") as tmp:
            input_path = tmp.name
        storage.download_file(f"{bucket_name}/{object_name}", input_path)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            output_path = tmp.name

        convert_pdf_to_pdfa(input_path, output_path)

        archive_object_name = f"document_{doc.id}/{pdfa_name}"
        archive_path = storage.upload_from_path(
            output_path,
            archive_object_name,
            bucket_key="processed",
        )

        log_audit_event(
            db=db,
            user=current_user,
            action=AuditActionEnum.DOWNLOAD,
            resource_type="document",
            resource_id=doc.id,
            document_id=doc.id,
            description="PDF/A export generated",
            changes={"archive_path": archive_path},
            ip_address=get_request_ip(request),
        )
        streaming_ready = True
        return StreamingResponse(
            _iter_file(output_path),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=\"{pdfa_name}\""},
        )

    except PDFAConversionError as exc:
        quarantine_path = None
        if input_path and os.path.exists(input_path):
            quarantine_object_name = f"document_{doc.id}/{base_name}"
            try:
                quarantine_path = storage.upload_from_path(
                    input_path,
                    quarantine_object_name,
                    bucket_key="quarantine",
                )
            except Exception as storage_exc:
                logger.error("Failed to store quarantine copy: %s", storage_exc)

        log_audit_event(
            db=db,
            user=current_user,
            action=AuditActionEnum.DOWNLOAD,
            resource_type="document",
            resource_id=doc.id,
            document_id=doc.id,
            description="PDF/A export failed",
            changes={
                "error": str(exc),
                "quarantine_path": quarantine_path,
            },
            ip_address=get_request_ip(request),
        )

        raise HTTPException(
            status_code=500,
            detail=f"PDF/A conversion failed. Stored in quarantine: {quarantine_path or 'unavailable'}",
        )
    finally:
        if input_path and os.path.exists(input_path):
            os.unlink(input_path)
        if output_path and os.path.exists(output_path) and not streaming_ready:
            os.unlink(output_path)
