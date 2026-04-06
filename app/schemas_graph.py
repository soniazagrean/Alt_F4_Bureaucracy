from typing import Optional
from pydantic import BaseModel


class DocumentNode(BaseModel):
    id: str
    nr_factura: Optional[str] = None
    tip_document: Optional[str] = None
    data: Optional[str] = None
    total: Optional[float] = None
    status: Optional[str] = None
    fraud_score: Optional[float] = None


class DosarNode(BaseModel):
    id: str
    name: str
    nomenclator_code: str
    year: int


class FurnizorNode(BaseModel):
    CUI: str
    name: str
    iban: Optional[str] = None


class NomenclatorEntryNode(BaseModel):
    code: str
    name: str
    retention_years: int
    category: str
