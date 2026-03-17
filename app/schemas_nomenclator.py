"""Schemas for nomenclator archive classification and suggestion."""
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class ConfidentialityLevelEnum(str, Enum):
    """Confidentiality/classification levels for documents"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class PastrareEnum(str, Enum):
    """Retention periods for archived documents (preservation terms)"""
    SIX_MONTHS = "6_months"
    ONE_YEAR = "1_year"
    THREE_YEARS = "3_years"
    FIVE_YEARS = "5_years"
    SEVEN_YEARS = "7_years"
    TEN_YEARS = "10_years"
    PERMANENT = "permanent"


class NomenclatorSuggestionRequest(BaseModel):
    """Request for nomenclator archive suggestion"""
    document_type: str = Field(
        ..., 
        description="Type of document (e.g., invoice, contract, report, correspondence, decision, protocol)"
    )
    title: str = Field(..., description="Document title/subject")
    description: Optional[str] = Field(None, description="Document description")
    extracted_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted metadata from document (e.g., amount, date, supplier, etc.)"
    )
    language: str = Field(default="ro", description="Document language (ro for Romanian, en for English)")


class NomenclatorSuggestion(BaseModel):
    """Single nomenclator suggestion with all required fields"""
    cod_nomenclator: str = Field(
        ...,
        description="Nomenclator code from Romanian standard (I-VII structure)"
    )
    dosar_propus: str = Field(
        ...,
        description="Proposed archive case/folder name"
    )
    termen_pastrare: PastrareEnum = Field(
        default=PastrareEnum.FIVE_YEARS,
        description="Retention/preservation term for the document"
    )
    nivel_confidentialitate: ConfidentialityLevelEnum = Field(
        default=ConfidentialityLevelEnum.INTERNAL,
        description="Confidentiality level of the document"
    )
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1) of the suggestion"
    )
    rationale: str = Field(
        default="",
        description="Explanation for the suggestion"
    )


class NomenclatorSuggestionResponse(BaseModel):
    """Response with nomenclator suggestions"""
    success: bool = Field(..., description="Whether suggestion was successful")
    message: Optional[str] = Field(None, description="Status message")
    suggestions: list[NomenclatorSuggestion] = Field(
        default_factory=list,
        description="List of nomenclator suggestions (primary is first)"
    )
    primary_suggestion: Optional[NomenclatorSuggestion] = Field(
        None,
        description="Primary/recommended nomenclator suggestion"
    )
    errors: Optional[list[str]] = Field(None, description="Any validation or processing errors")
    confidence: Optional[float] = Field(None, description="Overall confidence of primary suggestion")
    processing_time_ms: float = Field(default=0.0, description="Processing time in milliseconds")


class NomenclatorMetadata(BaseModel):
    """Complete metadata for a document after nomenclator classification"""
    document_id: int
    cod_nomenclator: str
    dosar_propus: str
    termen_pastrare: PastrareEnum
    nivel_confidentialitate: ConfidentialityLevelEnum
    confidence: float
    classified_at: datetime
    
    class Config:
        from_attributes = True
