from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.dependencies.security import RBACRole, require_roles
from app.models.audit import AuditLog
from app.models.document import Document
from app.schemas import AuditActorResponse, AuditTrailEntryResponse, AuditTrailResponse

router = APIRouter(prefix="/audit-trail", tags=["Audit Trail"])


@router.get("/{document_id}", response_model=AuditTrailResponse)
async def get_audit_trail(
    document_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    logs = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.user))
        .filter(AuditLog.document_id == document_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )

    items: list[AuditTrailEntryResponse] = []
    for log in logs:
        user = log.user
        role_value = user.role.value if hasattr(user.role, "value") else str(user.role)

        actor = AuditActorResponse(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            role=role_value,
        )
        items.append(
            AuditTrailEntryResponse(
                id=log.id,
                actor=actor,
                action=log.action.value if hasattr(log.action, "value") else str(log.action),
                timestamp=log.created_at,
                details=log.description,
                changes=log.changes,
                ip_address=log.ip_address,
            )
        )

    return AuditTrailResponse(
        document_id=document_id,
        items=items,
        total=len(items),
    )
