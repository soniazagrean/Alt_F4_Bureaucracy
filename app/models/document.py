from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.db.database import Base

class DocumentStatusEnum(str, enum.Enum):
    """Document processing status"""
    PENDING = "pending"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    ARCHIVED = "archived"
    REJECTED = "rejected"

class DocumentTypeEnum(str, enum.Enum):
    """Document types according to nomenclator"""
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

class Document(Base):
    """Document model with metadata and processing status"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    # Document identification
    document_number = Column(String(255), unique=True, nullable=False, index=True)
    document_type = Column(Enum(DocumentTypeEnum, create_type=False), nullable=False)
    title = Column(String(511), nullable=False)
    description = Column(Text, nullable=True)

    # Financial metadata
    amount = Column(Float, nullable=True)  # Document amount (e.g., invoice total)
    currency = Column(String(3), default="RON", nullable=True)

    # Document content and metadata
    file_path = Column(String(511), nullable=False)  # MinIO path
    file_size = Column(Integer, nullable=True)  # in bytes
    mime_type = Column(String(100), nullable=True)
    page_count = Column(Integer, nullable=True)
    file_hash = Column(String(64), unique=True, index=True, nullable=True) # Added for deduplication

    # Classification and processing
    status = Column(Enum(DocumentStatusEnum, create_type=False), default=DocumentStatusEnum.PENDING, nullable=False, index=True)
    fraud_score = Column(Float, default=0.0)  # 0-1 score for fraud detection
    confidence = Column(Float, nullable=True)  # 0-1 confidence in classification

    # Relationships
    dosar_id = Column(Integer, ForeignKey("dosare.id"), nullable=True, index=True)
    nomenclator_id = Column(Integer, ForeignKey("nomenclator.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Timestamps
    document_date = Column(DateTime, nullable=True)  # When the document was created
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    archived_at = Column(DateTime, nullable=True)

    # Relationships
    dosar = relationship("Dosar", back_populates="documents")
    nomenclator = relationship("NomenclatorEntry", back_populates="documents")
    created_by_user = relationship("User", back_populates="documents")
    extracted_data = relationship("ExtractedData", back_populates="document", cascade="all, delete-orphan")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="document")
    
    #

    def __repr__(self):
        return f"<Document(id={self.id}, number={self.document_number}, status={self.status})>"

class DocumentPage(Base):
    """Individual pages of a document"""
    __tablename__ = "document_pages"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    image_path = Column(String(511), nullable=False)  # MinIO path
    text_content = Column(Text, nullable=True)  # OCR text
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    document = relationship("Document", back_populates="pages")

    __table_args__ = (
        # Unique constraint: one document can only have one page per page number
    )

    def __repr__(self):
        return f"<DocumentPage(doc_id={self.document_id}, page={self.page_number})>"

class ExtractedData(Base):
    """Data extracted by LLM from documents"""
    __tablename__ = "extracted_data"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)

    # Extracted information
    field_name = Column(String(255), nullable=False)  # e.g., "invoice_number", "total_amount"
    field_value = Column(Text, nullable=False)
    extraction_confidence = Column(Float, default=1.0)  # 0-1 confidence in extraction

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    document = relationship("Document", back_populates="extracted_data")

    def __repr__(self):
        return f"<ExtractedData(doc_id={self.document_id}, field={self.field_name})>"
