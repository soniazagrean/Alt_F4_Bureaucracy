from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.dependencies.security import RBACRole, require_roles
from app.db.database import get_db
from app.models.archive import Dosar, NomenclatorEntry
from app.schemas import DosarCreate

router = APIRouter(prefix="/archive", tags=["Archive"])

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

    payload = [
        {
            "id": dosar.id,
            "dosar_number": dosar.dosar_number,
            "title": dosar.title,
            "description": dosar.description,
            "nomenclator_id": dosar.nomenclator_id,
            "termen_pastrare": dosar.termen_pastrare.value if hasattr(dosar.termen_pastrare, "value") else str(dosar.termen_pastrare),
            "is_active": bool(dosar.is_active),
            "created_at": dosar.created_at.isoformat() if dosar.created_at else None,
            "updated_at": dosar.updated_at.isoformat() if dosar.updated_at else None,
            "archived_at": dosar.archived_at.isoformat() if dosar.archived_at else None,
            "documents_count": len(dosar.documents or []),
        }
        for dosar in dosare
    ]

    return JSONResponse({"items": payload, "total": len(payload)})

@router.post("/")
async def archive_document(
    payload: DosarCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
):
    existing = db.query(Dosar).filter(Dosar.dosar_number == payload.dosar_number).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dosar number already exists")

    nomenclator = db.query(NomenclatorEntry).filter(NomenclatorEntry.id == payload.nomenclator_id).first()
    if not nomenclator:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid nomenclator_id")

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

    return JSONResponse(
        {
            "id": dosar.id,
            "dosar_number": dosar.dosar_number,
            "title": dosar.title,
            "description": dosar.description,
            "nomenclator_id": dosar.nomenclator_id,
            "termen_pastrare": dosar.termen_pastrare.value if hasattr(dosar.termen_pastrare, "value") else str(dosar.termen_pastrare),
            "is_active": bool(dosar.is_active),
            "created_at": dosar.created_at.isoformat() if dosar.created_at else None,
            "updated_at": dosar.updated_at.isoformat() if dosar.updated_at else None,
            "archived_at": dosar.archived_at.isoformat() if dosar.archived_at else None,
        },
        status_code=status.HTTP_201_CREATED,
    )

@router.get("/{archive_id}")
async def get_archived(
    archive_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    dosar = db.query(Dosar).filter(Dosar.id == archive_id).first()
    if not dosar:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")

    return JSONResponse({
        "id": dosar.id,
        "dosar_number": dosar.dosar_number,
        "title": dosar.title,
        "description": dosar.description,
        "nomenclator_id": dosar.nomenclator_id,
        "termen_pastrare": dosar.termen_pastrare.value if hasattr(dosar.termen_pastrare, "value") else str(dosar.termen_pastrare),
        "is_active": bool(dosar.is_active),
        "created_at": dosar.created_at.isoformat() if dosar.created_at else None,
        "updated_at": dosar.updated_at.isoformat() if dosar.updated_at else None,
        "archived_at": dosar.archived_at.isoformat() if dosar.archived_at else None,
        "documents_count": len(dosar.documents or []),
    })

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