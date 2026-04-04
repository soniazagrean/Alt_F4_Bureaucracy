"""API routes for nomenclator archive classification and suggestion."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any
import logging

from app.dependencies.security import RBACRole, require_roles
from app.schemas_nomenclator import (
    NomenclatorSuggestionRequest,
    NomenclatorSuggestionResponse
)
from app.services.nomenclator_suggestion import NomenclatorSuggestionService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/nomenclator",
    tags=["nomenclator"],
    responses={404: {"description": "Not found"}}
)


@router.post(
    "/suggest",
    response_model=NomenclatorSuggestionResponse,
    summary="Suggest nomenclator classification for a document",
    description="""
    Use LLM prompt engineering to suggest appropriate nomenclator archive classification
    for a document based on its type and extracted metadata.
    
    Returns multiple suggestions with:
    - cod_nomenclator: Classification code from Romanian standard (I-VII)
    - dosar_propus: Suggested archive case/folder name
    - termen_pastrare: Recommended preservation/retention term
    - nivel_confidentialitate: Confidentiality level
    - confidence: Confidence score (0-1)
    - rationale: Explanation for the suggestion
    """
)
async def suggest_nomenclator(
    request: NomenclatorSuggestionRequest,
    num_suggestions: int = Query(
        default=3,
        ge=1,
        le=5,
        description="Number of suggestions to return (1-5, default 3)"
    ),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
) -> NomenclatorSuggestionResponse:
    """
    Suggest nomenclator classifications for a document.
    
    This endpoint uses LLM with Romanian standard nomenclator (I-VII) as context
    to suggest the most appropriate archive classification, preservation term,
    and confidentiality level for the document.
    
    Args:
        request: Document metadata for classification
        num_suggestions: Number of suggestions to return (1-5)
        
    Returns:
        Response with nomenclator suggestions and confidence scores
        
    Example:
        ```json
        {
            "document_type": "invoice",
            "title": "Invoice from Supplier ABC",
            "description": "Monthly invoice for services",
            "extracted_metadata": {
                "amount": 5000,
                "currency": "RON",
                "supplier": "ABC Company",
                "date": "2024-01-15"
            }
        }
        ```
    """
    try:
        service = NomenclatorSuggestionService()
        response = service.suggest_nomenclator(request, num_suggestions=num_suggestions)
        
        if not response.success:
            logger.error(f"Nomenclator suggestion failed: {response.message}")
            raise HTTPException(
                status_code=500,
                detail=response.message or "Failed to generate nomenclator suggestions"
            )
        
        return response
        
    except ValueError as e:
        logger.error(f"Invalid input for nomenclator suggestion: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid input: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in nomenclator suggestion: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error generating nomenclator suggestions"
        )


@router.post(
    "/suggest-batch",
    response_model=list[NomenclatorSuggestionResponse],
    summary="Suggest nomenclator classifications for multiple documents",
    description="Batch process multiple documents for nomenclator classification."
)
async def suggest_nomenclator_batch(
    requests: list[NomenclatorSuggestionRequest],
    num_suggestions: int = Query(
        default=3,
        ge=1,
        le=5,
        description="Number of suggestions per document"
    ),
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR)),
) -> list[NomenclatorSuggestionResponse]:
    """
    Suggest nomenclator classifications for multiple documents in batch.
    
    Args:
        requests: List of document metadata for classification
        num_suggestions: Number of suggestions per document (1-5)
        
    Returns:
        List of responses with nomenclator suggestions for each document
    """
    try:
        if len(requests) > 50:
            raise HTTPException(
                status_code=400,
                detail="Batch size limited to 50 documents"
            )
        
        service = NomenclatorSuggestionService()
        responses = [
            service.suggest_nomenclator(request, num_suggestions=num_suggestions)
            for request in requests
        ]
        
        return responses
        
    except Exception as e:
        logger.error(f"Error in batch nomenclator suggestion: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error processing batch nomenclator suggestions"
        )


@router.get(
    "/standards",
    summary="Get Romanian nomenclator standards reference",
    description="Return the hardcoded Romanian standard nomenclator (I-VII) context used for classification."
)
async def get_nomenclator_standards(
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
) -> Dict[str, Any]:
    """
    Get the Romanian nomenclator standards reference used in suggestions.
    
    Returns:
        Dictionary containing the nomenclator categories, preservation terms guide,
        and confidentiality levels used by the suggestion engine.
    """
    service = NomenclatorSuggestionService()
    
    return {
        "romanian_nomenclator": service.ROMANIAN_NOMENCLATOR_CONTEXT,
        "preservation_terms": service.PRESERVATION_GUIDE,
        "confidentiality_levels": service.CONFIDENTIALITY_GUIDE,
        "version": "1.0",
        "standard": "Romanian Classification System (I-VII)"
    }
