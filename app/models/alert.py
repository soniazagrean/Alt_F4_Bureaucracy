from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.db.database import Base

class AnomalyTypeEnum(str, enum.Enum):
    """Types of anomalies/fraud detected"""
    DUPLICATE_DOCUMENT = "duplicate_document"
    FORGED_SIGNATURE = "forged_signature"
    TAMPERED_DATA = "tampered_data"
    INVALID_AMOUNT = "invalid_amount"
    PATTERN_ANOMALY = "pattern_anomaly"
    MISSING_METADATA = "missing_metadata"
    OCR_ERROR = "ocr_error"
    UNKNOWN = "unknown"

class FraudAlert(Base):
    """Fraud detection and anomaly alerts"""
    __tablename__ = "fraud_alerts"

    id = Column(Integer, primary_key=True, index=True)

    # Document reference
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)

    # Alert details
    anomaly_type = Column(Enum(AnomalyTypeEnum), nullable=False)
    fraud_score = Column(Float, nullable=False)  # 0-1 confidence in fraud
    risk_level = Column(String(20), nullable=False)  # low, medium, high, critical
    description = Column(Text, nullable=False)

    # Status
    is_resolved = Column(Integer, default=0)  # 0 = active, 1 = resolved
    resolution_notes = Column(Text, nullable=True)

    # Timestamps
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    document = relationship("Document")

    def __repr__(self):
        return f"<FraudAlert(doc_id={self.document_id}, type={self.anomaly_type}, score={self.fraud_score:.2f})>"
