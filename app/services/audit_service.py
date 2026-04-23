from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4
import enum

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditActionEnum, AuditLog
from app.models.user import RoleEnum, User


def get_request_ip(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client:
        return request.client.host

    return None


def serialize_audit_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    return value


def get_or_create_system_user(db: Session) -> User:
    user = db.query(User).filter(User.username == "system").first()
    if user:
        return user

    user = User(
        username="system",
        email="system@nexusvault.local",
        full_name="System",
        role=RoleEnum.SYSTEM,
        is_active=True,
        is_verified=True,
    )
    user.set_password(str(uuid4()))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def log_audit_event(
    db: Session,
    user: User,
    action: AuditActionEnum,
    resource_type: str,
    resource_id: int,
    *,
    document_id: Optional[int] = None,
    description: Optional[str] = None,
    changes: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    commit: bool = True,
) -> AuditLog:
    audit = AuditLog(
        user_id=user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        description=description,
        ip_address=ip_address,
        changes=changes,
        document_id=document_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)

    if commit:
        db.commit()
        db.refresh(audit)

    return audit
