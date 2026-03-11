# Import all models to ensure they are registered with SQLAlchemy
from app.models.user import User, RoleEnum
from app.models.document import Document, DocumentPage, ExtractedData, DocumentStatusEnum, DocumentTypeEnum
from app.models.archive import Dosar, NomenclatorEntry, PastrareEnum
from app.models.audit import AuditLog, AuditActionEnum
from app.models.alert import FraudAlert, AnomalyTypeEnum

__all__ = [
    # User models
    "User",
    "RoleEnum",
    # Document models
    "Document",
    "DocumentPage",
    "ExtractedData",
    "DocumentStatusEnum",
    "DocumentTypeEnum",
    # Archive models
    "Dosar",
    "NomenclatorEntry",
    "PastrareEnum",
    # Audit models
    "AuditLog",
    "AuditActionEnum",
    # Alert models
    "FraudAlert",
    "AnomalyTypeEnum",
]
