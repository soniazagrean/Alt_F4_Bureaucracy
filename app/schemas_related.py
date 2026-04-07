from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class RelationType(str, Enum):
    SAME_DOSAR = "same_dosar"
    SAME_FURNIZOR = "same_furnizor"


class RelatedDocumentItem(BaseModel):
    id: str
    nr_factura: Optional[str] = None
    tip_document: Optional[str] = None
    data: Optional[str] = None
    total: Optional[float] = None
    status: Optional[str] = None
    furnizor: Optional[str] = None
    dosar: Optional[str] = None
    relation_types: List[RelationType] = Field(default_factory=list)


class RelatedDocumentsResponse(BaseModel):
    document_id: str
    related: List[RelatedDocumentItem]
    page: int
    page_size: int
    total_count: int
    total_pages: int
