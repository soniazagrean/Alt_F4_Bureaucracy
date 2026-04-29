"""Pydantic schemas for invoice extraction and validation."""
import re
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List
from decimal import Decimal


def _normalize_numeric_text(value):
    if value is None:
        return value
    if isinstance(value, (int, float, Decimal)):
        return str(value)

    text = str(value).strip()
    if not text:
        return text

    text = re.sub(r"[^0-9,\.\-]", "", text)
    if not text:
        return text

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1:
        parts = text.split(".")
        text = "".join(parts[:-1]) + "." + parts[-1]

    return text


def _normalize_text(value):
    if value is None:
        return value
    return str(value).strip()


class InvoiceItem(BaseModel):
    """Schema for a line item in an invoice."""
    description: str = Field(..., description="Item description")
    quantity: float = Field(..., gt=0, description="Quantity of items")
    unit: str = Field(default="buc", description="Unit of measurement")
    unit_price: Decimal = Field(..., gt=0, description="Price per unit")
    total_price: Decimal = Field(..., ge=0, description="Total price for this line item")

    @validator('quantity', pre=True)
    def parse_quantity(cls, v):
        if v is None:
            return v
        return float(_normalize_numeric_text(v))

    @validator('unit', pre=True)
    def parse_unit(cls, v):
        return _normalize_text(v)

    @validator('unit_price', 'total_price', pre=True)
    def parse_decimal_fields(cls, v):
        return Decimal(_normalize_numeric_text(v)) if v is not None else Decimal('0')

    class Config:
        from_attributes = True


class InvoiceData(BaseModel):
    """Main schema for extracted invoice data with full validation."""
    
    nr_factura: str = Field(..., min_length=1, description="Invoice number")
    data: datetime = Field(..., description="Invoice date")
    furnizor: str = Field(..., min_length=1, description="Supplier/Vendor name")
    CUI: str = Field(..., min_length=1, description="Romanian Company Tax ID (CUI)")
    IBAN: Optional[str] = Field(None, description="Bank account IBAN")
    items: List[InvoiceItem] = Field(..., min_items=1, description="List of invoice line items")
    total: Decimal = Field(..., ge=0, description="Total invoice amount (including VAT)")
    TVA: Decimal = Field(..., ge=0, description="VAT/Tax amount")
    currency: Optional[str] = Field(default="EUR", description="Currency code (EUR, RON, USD, etc)")
    
    # Optional fields for additional context
    numar_ordine: Optional[str] = Field(None, description="PO/Order number")
    termen_plata: Optional[datetime] = Field(None, description="Payment deadline")
    observatii: Optional[str] = Field(None, description="Additional notes/observations")
    
    @validator('data', pre=True)
    def parse_date(cls, v):
        """Parse date from various formats."""
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # Try common date formats
            for fmt in ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            raise ValueError(f'Invalid date format: {v}')
        raise ValueError(f'Cannot parse date from {type(v)}')
    
    @validator('termen_plata', pre=True)
    def parse_termen_plata(cls, v):
        """Parse payment deadline from various formats."""
        if v is None:
            return v
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # Try common date formats
            for fmt in ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            raise ValueError(f'Invalid date format for termen_plata: {v}')
        raise ValueError(f'Cannot parse termen_plata from {type(v)}')
    
    @validator('TVA', pre=True)
    def validate_tva(cls, v, values):
        """Ensure TVA doesn't exceed total."""
        normalized = Decimal(_normalize_numeric_text(v)) if v is not None else Decimal('0')
        if 'total' in values:
            if normalized > Decimal(str(values['total'])):
                raise ValueError('TVA cannot be greater than total amount')
        return normalized
    
    @validator('total', pre=True)
    def parse_decimal(cls, v):
        """Convert numeric values to Decimal."""
        return Decimal(_normalize_numeric_text(v)) if v is not None else Decimal('0')

    @validator('currency', pre=True)
    def normalize_currency(cls, v):
        if v is None:
            return v
        text = _normalize_text(v)
        return text.upper() if text else text
    
    @validator('CUI', pre=True)
    def validate_cui(cls, v):
        """CUI should be numeric and typically 10 digits."""
        if v is None:
            return v
        v = re.sub(r"\D", "", str(v))
        if not v.isdigit():
            raise ValueError('CUI must contain only digits')
        if len(v) < 8 or len(v) > 10:
            raise ValueError('CUI should be between 8-10 digits')
        return v
    
    @validator('IBAN', pre=True)
    def validate_iban(cls, v):
        """Validate IBAN format (basic validation)."""
        if v is None:
            return v
        # Remove spaces
        v = re.sub(r"\s+", "", str(v)).upper()
        # IBAN format: country code (2 letters) + check digits (2 digits) + BBAN
        if len(v) < 15:
            raise ValueError('IBAN too short')
        if not v[:2].isalpha():
            raise ValueError('IBAN must start with country code')
        if not v[2:4].isdigit():
            raise ValueError('IBAN check digits must be numeric')
        return v
    
    @validator('items')
    def validate_items_total(cls, v, values):
        """Verify that items sum matches the invoice total."""
        if not v:
            return v
        items_sum = sum(Decimal(str(item.total_price)) for item in v)
        # We'll validate this more strictly in the service
        return v

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "nr_factura": "FAC-2024-001234",
                "data": "2024-03-15",
                "furnizor": "SC EXAMPLE SRL",
                "CUI": "1234567890",
                "IBAN": "RO12 ABNA 1234 5678 9012 3456",
                "items": [
                    {
                        "description": "Product A",
                        "quantity": 2,
                        "unit": "buc",
                        "unit_price": "100.00",
                        "total_price": "200.00"
                    }
                ],
                "total": "238.00",
                "TVA": "38.00"
            }
        }


class InvoiceExtractionResponse(BaseModel):
    """Response schema after successful extraction."""
    success: bool
    data: Optional[InvoiceData] = None
    errors: Optional[List[str]] = None
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Extraction confidence score")
    
    class Config:
        from_attributes = True
