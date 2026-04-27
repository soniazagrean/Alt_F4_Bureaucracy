from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.dependencies.security import RBACRole, require_roles
from app.db.database import get_db
from app.models.audit import AuditActionEnum
from app.models.archive import Dosar, NomenclatorEntry
from app.models.document import Document
from app.models.user import User
from app.schemas import DosarCreate
from app.services.audit_service import get_request_ip, log_audit_event, serialize_audit_value

router = APIRouter(prefix="/archive", tags=["Archive"])


class ArchiveCreateRequest(DosarCreate):
    document_ids: list[int] = Field(default_factory=list)


def _serialize_document(doc: Document) -> dict[str, Any]:
    return {
        "id": doc.id,
        "document_number": doc.document_number,
        "title": doc.title,
        "description": doc.description,
        "document_type": doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type),
        "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "archived_at": doc.archived_at.isoformat() if doc.archived_at else None,
    }


def _serialize_dosar_summary(dosar: Dosar) -> dict[str, Any]:
    return {
        "id": dosar.id,
        "dosar_number": dosar.dosar_number,
        "title": dosar.title,
        "description": dosar.description,
        "nomenclator_id": dosar.nomenclator_id,
        "nomenclator_code": dosar.nomenclator.code if dosar.nomenclator else None,
        "nomenclator_name": dosar.nomenclator.name if dosar.nomenclator else None,
        "termen_pastrare": dosar.termen_pastrare.value if hasattr(dosar.termen_pastrare, "value") else str(dosar.termen_pastrare),
        "status": "active" if dosar.is_active == 1 else "archived", 
        "created_at": dosar.created_at.isoformat() if dosar.created_at else None,
        "updated_at": dosar.updated_at.isoformat() if dosar.updated_at else None,
        "archived_at": dosar.archived_at.isoformat() if dosar.archived_at else None,
        "documents_count": len(dosar.documents or []),
    }

@router.get("/")
async def list_archived(
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    dosare = (
        db.query(Dosar)
        .order_by(Dosar.created_at.desc())
        .all()
    )

    payload = [_serialize_dosar_summary(dosar) for dosar in dosare]

    return JSONResponse({"items": payload, "total": len(payload)})

@router.post("/")
async def archive_document(
    payload: ArchiveCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    existing = db.query(Dosar).filter(Dosar.dosar_number == payload.dosar_number).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dosar number already exists")

    nomenclator = db.query(NomenclatorEntry).filter(NomenclatorEntry.id == payload.nomenclator_id).first()
    if not nomenclator:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid nomenclator_id")

    unique_document_ids = sorted(set(payload.document_ids)) if payload.document_ids else []
    documents: list[Document] = []
    if unique_document_ids:
        documents = (
            db.query(Document)
            .filter(Document.id.in_(unique_document_ids))
            .all()
        )
        found_ids = {doc.id for doc in documents}
        missing_ids = [doc_id for doc_id in unique_document_ids if doc_id not in found_ids]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document ids: {missing_ids}",
            )

    dosar = Dosar(
        dosar_number=payload.dosar_number,
        title=payload.title,
        description=payload.description,
        nomenclator_id=payload.nomenclator_id,
        termen_pastrare=payload.termen_pastrare,
    )
    db.add(dosar)
    db.commit()
    db.refresh(dosar)

    linked_document_ids: list[int] = []
    previous_dosar_ids: dict[int, int | None] = {}
    if documents:
        previous_dosar_ids = {document.id: document.dosar_id for document in documents}
        for document in documents:
            document.dosar_id = dosar.id
            linked_document_ids.append(document.id)
        db.commit()
        db.refresh(dosar)

        for document in documents:
            log_audit_event(
                db=db,
                user=current_user,
                action=AuditActionEnum.ARCHIVE,
                resource_type="document",
                resource_id=document.id,
                document_id=document.id,
                description="Document linked to archive dosar",
                changes={
                    "dosar_id": {
                        "from": serialize_audit_value(previous_dosar_ids.get(document.id)),
                        "to": serialize_audit_value(dosar.id),
                    }
                },
                ip_address=get_request_ip(request),
            )

    return JSONResponse(
        {
            **_serialize_dosar_summary(dosar),
            "linked_document_ids": linked_document_ids,
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/tree")
async def get_archive_tree(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    nomenclator_entries = db.query(NomenclatorEntry).all()

    dosare_query = db.query(Dosar)
    if not include_inactive:
        dosare_query = dosare_query.filter(Dosar.is_active == 1)
    dosare = dosare_query.all()

    entries_by_parent: dict[Optional[int], list[NomenclatorEntry]] = {}
    for entry in nomenclator_entries:
        entries_by_parent.setdefault(entry.parent_id, []).append(entry)

    dosare_by_nomenclator: dict[int, list[dict[str, Any]]] = {}
    for dosar in dosare:
        dosare_by_nomenclator.setdefault(dosar.nomenclator_id, []).append(_serialize_dosar_summary(dosar))

    for grouped_dosare in dosare_by_nomenclator.values():
        grouped_dosare.sort(key=lambda item: item.get("dosar_number") or "")

    def build_node(entry: NomenclatorEntry) -> dict[str, Any]:
        children = [build_node(child) for child in sorted(entries_by_parent.get(entry.id, []), key=lambda x: x.code)]
        return {
            "id": entry.id,
            "code": entry.code,
            "name": entry.name,
            "description": entry.description,
            "is_active": bool(entry.is_active),
            "children": children,
            "dosare": dosare_by_nomenclator.get(entry.id, []),
        }

    roots = [build_node(root_entry) for root_entry in sorted(entries_by_parent.get(None, []), key=lambda x: x.code)]

    return JSONResponse(
        {
            "roots": roots,
            "total_categories": len(nomenclator_entries),
            "total_dosare": len(dosare),
        }
    )


@router.get("/dosar/{dosar_id}")
async def get_dosar_details(
    dosar_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    dosar = db.query(Dosar).filter(Dosar.id == dosar_id).first()
    if not dosar:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")

    return JSONResponse(
        {
            **_serialize_dosar_summary(dosar),
            "documents": [_serialize_document(doc) for doc in sorted(dosar.documents or [], key=lambda d: d.id)],
        }
    )


@router.get("/search")
async def search_archive(
    q: str = Query("", min_length=0),
    nomenclator_id: Optional[int] = Query(None),
    include_inactive: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    query = db.query(Dosar).join(NomenclatorEntry, Dosar.nomenclator_id == NomenclatorEntry.id)

    if not include_inactive:
        query = query.filter(Dosar.is_active == 1)

    if nomenclator_id is not None:
        query = query.filter(Dosar.nomenclator_id == nomenclator_id)

    search_text = q.strip()
    if search_text:
        search_pattern = f"%{search_text}%"
        query = query.filter(
            or_(
                Dosar.dosar_number.ilike(search_pattern),
                Dosar.title.ilike(search_pattern),
                Dosar.description.ilike(search_pattern),
                NomenclatorEntry.code.ilike(search_pattern),
                NomenclatorEntry.name.ilike(search_pattern),
            )
        )

    total = query.count()
    items = (
        query.order_by(Dosar.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return JSONResponse(
        {
            "query": search_text,
            "nomenclator_id": nomenclator_id,
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [_serialize_dosar_summary(dosar) for dosar in items],
        }
    )

@router.get("/{archive_id}")
async def get_archived(
    archive_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    # Backward-compatible alias for legacy clients.
    return await get_dosar_details(archive_id, db)

@router.delete("/{archive_id}")
async def delete_archived(
    archive_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN)),
):
    dosar = db.query(Dosar).filter(Dosar.id == archive_id).first()
    if not dosar:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")

    dosar.is_active = 0
    dosar.archived_at = datetime.now(timezone.utc)
    db.commit()

    return JSONResponse({
        "status": "success",
        "message": "Archive entry deactivated",
        "archive_id": archive_id,
    })