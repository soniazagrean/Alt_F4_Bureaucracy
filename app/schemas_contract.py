"""Pydantic schemas for contract extraction."""
from typing import Optional, List
from pydantic import BaseModel, Field


class ContractData(BaseModel):
    """Schema for extracted contract data."""

    contract_number: str = Field(..., min_length=1, description="Contract identifier")
    party_a: str = Field(..., min_length=1, description="First legal party")
    party_b: str = Field(..., min_length=1, description="Second legal party")
    start_date: Optional[str] = Field(None, description="Contract start date")
    end_date: Optional[str] = Field(None, description="Contract end date")
    contract_value: Optional[float] = Field(None, ge=0, description="Contract value")
    currency: Optional[str] = Field(default="RON", description="Currency code")
    scope_of_work: Optional[str] = Field(None, description="Scope/subject of contract")

    class Config:
        from_attributes = True


class ContractExtractionResponse(BaseModel):
    """Response schema after contract extraction."""

    success: bool
    data: Optional[ContractData] = None
    errors: Optional[List[str]] = None
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Extraction confidence score")

    class Config:
        from_attributes = True
