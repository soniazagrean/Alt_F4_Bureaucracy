"""FastAPI endpoints for invoice extraction."""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import tempfile
import logging
from pathlib import Path
from typing import Optional

from app.services.invoice_extraction import InvoiceExtractionService
from app.schemas_invoice import InvoiceExtractionResponse, InvoiceData
from app.db.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])


@router.post("/extract", response_model=InvoiceExtractionResponse)
async def extract_invoice(
    file: UploadFile = File(..., description="Invoice image file (PNG, JPG)"),
    language: str = Query("en", description="Invoice language (en, ro, etc.)"),
):
    """
    Extract invoice data from an image file.
    
    Accepts PNG or JPG images and extracts structured data including:
    - Invoice number
    - Date
    - Supplier info and CUI
    - Line items
    - Totals and VAT
    
    Validation is performed using Pydantic schemas.
    """
    # Validate file type
    allowed_types = {"image/png", "image/jpeg", "image/jpg"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: PNG, JPG. Got: {file.content_type}"
        )
    
    # Validate file size (max 10MB)
    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
    
    try:
        # Save file to temporary location
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=Path(file.filename).suffix,
            dir="/tmp"
        ) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name
        
        try:
            # Initialize extraction service
            service = InvoiceExtractionService()
            
            # Extract invoice data
            response = await service.extract_invoice_async(tmp_path, language=language)
            
            return response
            
        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)
            
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return InvoiceExtractionResponse(
            success=False,
            errors=[str(e)],
            confidence=0.0
        )
    except Exception as e:
        logger.error(f"Unexpected error during extraction: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing invoice: {str(e)}"
        )


@router.post("/extract-url")
async def extract_invoice_from_url(
    image_url: str = Query(..., description="URL of the invoice image"),
    language: str = Query("en", description="Invoice language (en, ro, etc.")
) -> InvoiceExtractionResponse:
    """
    Extract invoice data from a URL.
    
    Useful for processing invoices from external sources without uploading files.
    """
    import httpx
    
    try:
        # Download image from URL
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url, timeout=30.0)
            response.raise_for_status()
            
            # Validate content type
            content_type = response.headers.get("content-type", "").lower()
            if "image" not in content_type:
                raise HTTPException(status_code=400, detail="URL does not point to an image")
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".png",
            dir="/tmp"
        ) as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name
        
        try:
            # Extract invoice data
            service = InvoiceExtractionService()
            result = await service.extract_invoice_async(tmp_path, language=language)
            return result
            
        finally:
            # Clean up
            Path(tmp_path).unlink(missing_ok=True)
            
    except httpx.RequestError as e:
        logger.error(f"Failed to download image: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to download image: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing invoice from URL: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate")
async def validate_invoice_data(
    nr_factura: str = Query(...),
    data: str = Query(...),
    furnizor: str = Query(...),
    CUI: str = Query(...),
    total: float = Query(...),
    TVA: float = Query(...),
):
    """
    Validate invoice data using Pydantic schemas (GET query parameters).
    
    Useful for testing validation rules without extraction.
    """
    try:
        # Minimal validation test
        invoice_data = InvoiceData(
            nr_factura=nr_factura,
            data=data,
            furnizor=furnizor,
            CUI=CUI,
            total=total,
            TVA=TVA,
            items=[]  # Empty items for validation test
        )
        
        return {
            "success": True,
            "message": "Invoice data is valid",
            "data": invoice_data.model_dump()
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "data": None
        }


@router.post("/validate-full")
async def validate_invoice_full(
    invoice_data: InvoiceData
):
    """
    Validate complete invoice data with items (POST with JSON body).
    
    Useful for comprehensive validation testing with line items.
    """
    try:
        # Data is already validated by Pydantic at this point
        return {
            "success": True,
            "message": "Invoice data is valid",
            "data": invoice_data.model_dump()
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "data": None
        }


@router.post("/batch-extract")
async def batch_extract_invoices(
    files: list[UploadFile] = File(..., description="Multiple invoice image files"),
    language: str = Query("en", description="Invoice language")
):
    """
    Extract data from multiple invoices in one request.
    
    Returns a list of extraction results.
    """
    results = []
    
    for file in files:
        try:
            # Reuse single extraction logic
            file_content = await file.read()
            
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=Path(file.filename).suffix
            ) as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            try:
                service = InvoiceExtractionService()
                response = await service.extract_invoice_async(tmp_path, language=language)
                results.append({
                    "filename": file.filename,
                    "result": response.model_dump()
                })
            finally:
                Path(tmp_path).unlink(missing_ok=True)
                
        except Exception as e:
            results.append({
                "filename": file.filename,
                "error": str(e),
                "result": None
            })
    
    return {
        "total": len(files),
        "successful": sum(1 for r in results if "result" in r),
        "results": results
    }
