from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List, Any, Dict
from enum import Enum

# User Schemas
class RoleEnum(str, Enum):
    ADMIN = "admin"
    ARCHIVIST = "archivist"
    INSPECTOR = "inspector"
    VIEWER = "viewer"
    SYSTEM = "system"

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: RoleEnum = RoleEnum.VIEWER

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: RoleEnum
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Document Schemas
class DocumentTypeEnum(str, Enum):
    INVOICE = "invoice"
    CONTRACT = "contract"
    REPORT = "report"
    CORRESPONDENCE = "correspondence"
    DECISION = "decision"
    PROTOCOL = "protocol"
    OTHER = "other"
    
    ADRESA         = "adresa"    # adresă oficială
    CERERE         = "cerere"    # cerere / petiție
    HCL            = "hcl"       # Hotărâre Consiliu Local
    DEVIZ          = "deviz"     # deviz de lucrări

class DocumentStatusEnum(str, Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    REVIEW = "review"
    APPROVED = "approved"
    RETURNED = "returned"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    ARCHIVED = "archived"
    REJECTED = "rejected"
    ERROR = "error"

class DocumentCreate(BaseModel):
    document_number: str
    document_type: DocumentTypeEnum
    title: str
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "RON"
    file_path: str
    dosar_id: Optional[int] = None
    nomenclator_id: Optional[int] = None


class DocumentUpdateRequest(BaseModel):
    document_number: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = Field(None, min_length=1, max_length=3)
    document_date: Optional[datetime] = None
    document_type: Optional[DocumentTypeEnum] = None


class NomenclatorConfirmationRequest(BaseModel):
    confirmed: bool = True
    nomenclator_id: Optional[int] = None
    dosar_id: Optional[int] = None


class DocumentCorrectionRequest(BaseModel):
    reason: Optional[str] = None

class DocumentResponse(BaseModel):
    id: int
    document_number: str
    document_type: DocumentTypeEnum
    title: str
    status: DocumentStatusEnum
    fraud_score: float
    created_at: datetime
    created_by_id: int

    class Config:
        from_attributes = True
        
class DocumentUploadResponse(BaseModel):
    id: int
    filename: str
    status: str
    message: str
    is_duplicate: bool = False

    class Config:
        from_attributes = True

# Archive Schemas
class PastrareEnum(str, Enum):
    SIX_MONTHS = "6_months"
    ONE_YEAR = "1_year"
    THREE_YEARS = "3_years"
    FIVE_YEARS = "5_years"
    SEVEN_YEARS = "7_years"
    TEN_YEARS = "10_years"
    PERMANENT = "permanent"

class NomenclatorEntryResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str]
    default_termen_pastrare: PastrareEnum

    class Config:
        from_attributes = True

class DosarCreate(BaseModel):
    dosar_number: str
    title: str
    description: Optional[str] = None
    nomenclator_id: int
    termen_pastrare: PastrareEnum = PastrareEnum.FIVE_YEARS

class DosarResponse(BaseModel):
    id: int
    dosar_number: str
    title: str
    termen_pastrare: PastrareEnum
    created_at: datetime
    nomenclator_id: int

    class Config:
        from_attributes = True

# Audit Schemas
class AuditActionEnum(str, Enum):
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

class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    action: AuditActionEnum
    resource_type: str
    resource_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class AuditActorResponse(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    role: RoleEnum

    class Config:
        from_attributes = True


class AuditTrailEntryResponse(BaseModel):
    id: int
    actor: AuditActorResponse
    action: AuditActionEnum
    timestamp: datetime
    details: Optional[str] = None
    changes: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None


class AuditTrailResponse(BaseModel):
    document_id: int
    items: List[AuditTrailEntryResponse]
    total: int

# Alert Schemas
class AnomalyTypeEnum(str, Enum):
    DUPLICATE_DOCUMENT = "duplicate_document"
    FORGED_SIGNATURE = "forged_signature"
    TAMPERED_DATA = "tampered_data"
    INVALID_AMOUNT = "invalid_amount"
    PATTERN_ANOMALY = "pattern_anomaly"
    MISSING_METADATA = "missing_metadata"
    OCR_ERROR = "ocr_error"
    UNKNOWN = "unknown"

class FraudAlertResponse(BaseModel):
    id: int
    document_id: int
    anomaly_type: AnomalyTypeEnum
    fraud_score: float
    risk_level: str
    description: str
    detected_at: datetime

    class Config:
        from_attributes = True
