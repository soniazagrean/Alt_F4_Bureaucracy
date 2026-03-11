from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.db.database import Base

class PastrareEnum(str, enum.Enum):
    """Retention periods for archived documents"""
    SIX_MONTHS = "6_months"
    ONE_YEAR = "1_year"
    THREE_YEARS = "3_years"
    FIVE_YEARS = "5_years"
    SEVEN_YEARS = "7_years"
    TEN_YEARS = "10_years"
    PERMANENT = "permanent"

class Dosar(Base):
    """Archive folder/case (contained folder with multiple documents)"""
    __tablename__ = "dosare"

    id = Column(Integer, primary_key=True, index=True)

    # Identification
    dosar_number = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(511), nullable=False)
    description = Column(Text, nullable=True)

    # Classification
    nomenclator_id = Column(Integer, ForeignKey("nomenclator.id"), nullable=False)
    termen_pastrare = Column(Enum(PastrareEnum), default=PastrareEnum.FIVE_YEARS, nullable=False)

    # Status and dates
    is_active = Column(Integer, default=1)  # 1 = active, 0 = archived
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    archived_at = Column(DateTime, nullable=True)

    # Relationships
    nomenclator = relationship("NomenclatorEntry", back_populates="dosare")
    documents = relationship("Document", back_populates="dosar", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Dosar(id={self.id}, number={self.dosar_number})>"

class NomenclatorEntry(Base):
    """Classification categories for documents"""
    __tablename__ = "nomenclator"

    id = Column(Integer, primary_key=True, index=True)

    # Identification
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Hierarchy
    parent_id = Column(Integer, ForeignKey("nomenclator.id"), nullable=True, index=True)

    # Default retention
    default_termen_pastrare = Column(
        Enum(PastrareEnum),
        default=PastrareEnum.FIVE_YEARS,
        nullable=False
    )

    # Status
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    children = relationship(
        "NomenclatorEntry",
        remote_side=[id],
        backref="parent"
    )
    dosare = relationship("Dosar", back_populates="nomenclator")
    documents = relationship("Document", back_populates="nomenclator")

    def __repr__(self):
        return f"<NomenclatorEntry(code={self.code}, name={self.name})>"
