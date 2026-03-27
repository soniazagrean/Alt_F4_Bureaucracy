# app/schemas_classification.py
from pydantic import BaseModel, Field
from typing import Optional
from app.schemas import DocumentTypeEnum


class ClassificationResult(BaseModel):
    tip_document: DocumentTypeEnum
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: Optional[str] = None  # short explanation from the LLM (debug aid)


class ClassificationResponse(BaseModel):
    success: bool
    data: Optional[ClassificationResult] = None
    errors: Optional[list[str]] = None
    document_id: Optional[int] = None
