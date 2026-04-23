from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.db.database import Base

class AuditActionEnum(str, enum.Enum):
    """Actions tracked in audit log"""
    CREATE = "create"
    READ = "read"
    INSPECT = "inspect"
    UPDATE = "update"
    DELETE = "delete"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    CLASSIFY = "classify"
    EXTRACT = "extract"
    ARCHIVE = "archive"
    RESTORE = "restore"
    APPROVE = "approve"
    MANUAL_EDIT = "manual_edit"
    LOGIN = "login"
    LOGOUT = "logout"
    PERMISSION_CHANGE = "permission_change"

class AuditLog(Base):
    """Audit trail for compliance and security tracking"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Actor
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Action
    action = Column(Enum(AuditActionEnum, create_type=False), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False)  # e.g., "document", "dosar"
    resource_id = Column(Integer, nullable=False, index=True)

    # Details
    description = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    changes = Column(JSON, nullable=True)  # Before/after changes in JSON format

    # Associated document (if applicable)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)

    # Timestamp
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")
    document = relationship("Document", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(user_id={self.user_id}, action={self.action}, resource={self.resource_type}#{self.resource_id})>"
