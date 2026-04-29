"""Service for nomenclator archive classification using LLM prompt engineering."""
import json
import time
import logging
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
import time as time_module

import httpx

from app.config import settings
from app.schemas_nomenclator import (
    NomenclatorSuggestionRequest,
    NomenclatorSuggestionResponse,
    NomenclatorSuggestion,
    ConfidentialityLevelEnum,
    PastrareEnum
)
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class NomenclatorSuggestionService:
    """Service for suggesting archival nomenclature using LLM with Romanian standard context."""
    
    # Romanian standard nomenclator categories (I-VII) + common extensions
    ROMANIAN_NOMENCLATOR_CONTEXT = """
    ROMANIAN STANDARD NOMENCLATOR (I-VII Classification System)
    ============================================================
    
    I. Administrative and Management Documents
       I.1 - Decisions, resolutions, internal regulations, annual reports
    
    II. Personnel Documents
        II.1 - Personnel files, job descriptions, staffing tables, individual employment contracts
    
    III. Financial and Accounting Documents
         III.1 - Execution accounts, balance sheets, accounting notes, invoices, payment orders, bank statements
    
    IV. Fixed Assets and Materials Documents
        IV.1 - Inventory lists, disposal reports, warehouse records
    
    V. Educational Activity Documents
       V.1 - Curriculum plans, timetables, catalogs, register books
    
    VI. Correspondence
        VI.1 - Current institutional correspondence
    
    VII. Other Documents
         VII.1 - Register books, special regime forms, other documents
    """
    
    PRESERVATION_GUIDE = """
    PRESERVATION TERMS (Termen de Pastrare) Guidelines:
    - 6_months: Temporary documents, drafts, working copies
    - 1_year: Short-term operational documents
    - 3_years: Regulatory compliance documents
    - 5_years: Standard retention (default for most business documents)
    - 7_years: Tax-related and financial records (Romanian tax law requirement)
    - 10_years: Legal documents, contracts, HR records
    - permanent: Strategic documents, policies, founding documents, legal records of significance
    """
    
    CONFIDENTIALITY_GUIDE = """
    CONFIDENTIALITY LEVELS:
    - public: Documents that can be freely shared (annual reports, general policies)
    - internal: For internal use only (internal memos, internal procedures)
    - confidential: Sensitive business information (financial details, client lists)
    - restricted: Highly sensitive (contracts with confidentiality clauses, proprietary information)
    - top_secret: Government classified or extremely sensitive data
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the nomenclator suggestion service.
        
        Args:
            api_key: OpenAI API key. If None, uses OPENAI_API_KEY from settings.
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured in settings or provided as argument")
        
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4"
        self.timeout = 60.0
    
    def suggest_nomenclator(
        self,
        request: NomenclatorSuggestionRequest,
        num_suggestions: int = 3
    ) -> NomenclatorSuggestionResponse:
        """
        Suggest nomenclator classification for a document.
        
        Args:
            request: NomenclatorSuggestionRequest with document metadata
            num_suggestions: Number of suggestions to return (default 3)
            
        Returns:
            NomenclatorSuggestionResponse with suggestions
        """
        start_time = time.time()
        
        try:
            # Create prompt with hardcoded nomenclator context
            prompt = self._create_suggestion_prompt(request, num_suggestions)
            
            # Call OpenAI API
            response_text = self._call_openai_api(prompt)
            
            # Parse the response
            suggestions, errors = self._parse_suggestions_response(response_text)
            
            processing_time = (time.time() - start_time) * 1000  # Convert to ms
            
            if not suggestions:
                return NomenclatorSuggestionResponse(
                    success=False,
                    message="Failed to generate nomenclator suggestions",
                    errors=errors or ["Unknown error during suggestion generation"],
                    processing_time_ms=processing_time
                )
            
            # Primary suggestion is the first one
            primary = suggestions[0]
            
            return NomenclatorSuggestionResponse(
                success=True,
                message="Nomenclator suggestions generated successfully",
                suggestions=suggestions,
                primary_suggestion=primary,
                confidence=primary.confidence,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"Error suggesting nomenclator: {str(e)}")
            processing_time = (time.time() - start_time) * 1000
            return NomenclatorSuggestionResponse(
                success=False,
                message=f"Error generating suggestions: {str(e)}",
                errors=[str(e)],
                processing_time_ms=processing_time
            )
    
    def _create_suggestion_prompt(
        self,
        request: NomenclatorSuggestionRequest,
        num_suggestions: int
    ) -> str:
        """
        Create a comprehensive prompt for nomenclator suggestion.
        
        Args:
            request: Document information for classification
            num_suggestions: Number of suggestions to generate
            
        Returns:
            Formatted prompt string
        """
        metadata_str = json.dumps(request.extracted_metadata, indent=2, default=str)
        
        prompt = f"""You are an expert archival specialist specializing in Romanian document classification and preservation.
Your task is to suggest the most appropriate nomenclator classification for a document based on the Romanian standard nomenclator (I-VII system).

{self.ROMANIAN_NOMENCLATOR_CONTEXT}

{self.PRESERVATION_GUIDE}

{self.CONFIDENTIALITY_GUIDE}

DOCUMENT TO CLASSIFY:
=====================
Document Type: {request.document_type}
Title: {request.title}
Description: {request.description or "Not provided"}

Extracted Metadata:
{metadata_str}

TASK:
=====
Based on the document information above, suggest {num_suggestions} nomenclator classifications.
For each suggestion, determine:
1. cod_nomenclator: The specific code from I-VII nomenclator (e.g., "II.1" for invoices)
2. dosar_propus: A clear, descriptive name for the archive case/folder this would belong to
3. termen_pastrare: How long to keep this document based on Romanian regulations and document type
4. nivel_confidentialitate: The appropriate confidentiality level

RESPONSE FORMAT:
================
Return a valid JSON response with this EXACT structure:
{{
    "suggestions": [
        {{
            "cod_nomenclator": "II.1",
            "dosar_propus": "Financial Documents 2024",
            "termen_pastrare": "7_years",
            "nivel_confidentialitate": "confidential",
            "confidence": 0.95,
            "rationale": "This is an invoice (document_type=invoice) with financial metadata. Category II.1 covers invoices and billing documents. Romanian tax law requires 7 years retention for financial records. Confidentiality is set to confidential as it contains financial and supplier information."
        }},
        {{
            "cod_nomenclator": "II.5",
            "dosar_propus": "Accounting Records 2024",
            "termen_pastrare": "7_years",
            "nivel_confidentialitate": "internal",
            "confidence": 0.75,
            "rationale": "Alternative classification focusing on accounting aspect."
        }},
        {{
            "cod_nomenclator": "I.2",
            "dosar_propus": "Internal Procedures and Operations",
            "termen_pastrare": "5_years",
            "nivel_confidentialitate": "internal",
            "confidence": 0.60,
            "rationale": "Less likely but possible if document has procedure nature."
        }}
    ]
}}

CRITICAL REQUIREMENTS:
======================
1. Return ONLY valid JSON, no explanation text before or after
2. cod_nomenclator must use I-VII Roman numeral format with decimal (e.g., "II.1", "V.3")
3. termen_pastrare must be one of: 6_months, 1_year, 3_years, 5_years, 7_years, 10_years, permanent
4. nivel_confidentialitate must be one of: public, internal, confidential, restricted, top_secret
5. confidence must be a float between 0.0 and 1.0
6. For Romanian documents, prefer 7_years for financial records (tax law requirement)
7. All suggestions should be realistic and based on the provided document type and metadata"""
        
        return prompt
    
    def _call_openai_api(self, prompt: str) -> str:
        """Call the OpenAI API with retry/backoff for transient failures."""
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        max_attempts = 3
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(self.base_url, json=payload, headers=headers)
                    response.raise_for_status()

                    result = response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        message = result["choices"][0].get("message", {})
                        content = message.get("content", "")
                        if content:
                            return content

                    raise ValueError("Unexpected API response format")
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code in {429, 500, 502, 503, 504} and attempt < max_attempts:
                    retry_after = exc.response.headers.get("Retry-After") if exc.response is not None else None
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * attempt
                    logger.warning(
                        "OpenAI nomenclator request failed with %s; retrying in %.1fs (%s/%s)",
                        status_code,
                        delay,
                        attempt,
                        max_attempts,
                    )
                    time_module.sleep(delay)
                    last_error = exc
                    continue
                logger.error("OpenAI API error: %s", exc)
                raise
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < max_attempts:
                    delay = 2.0 * attempt
                    logger.warning(
                        "OpenAI nomenclator transport error; retrying in %.1fs (%s/%s): %s",
                        delay,
                        attempt,
                        max_attempts,
                        exc,
                    )
                    time_module.sleep(delay)
                    continue
                logger.error("Error calling OpenAI API: %s", exc)
                raise

        raise RuntimeError(f"OpenAI API request failed after {max_attempts} attempts: {last_error}")
    
    def _parse_suggestions_response(
        self,
        response_text: str
    ) -> Tuple[list[NomenclatorSuggestion], Optional[list[str]]]:
        """
        Parse and validate the LLM response into suggestions.
        
        Args:
            response_text: The raw response from OpenAI API
            
        Returns:
            Tuple of (list of NomenclatorSuggestion, list of errors or None)
        """
        try:
            # Try to extract JSON from response
            json_text = response_text.strip()
            
            # Remove markdown code blocks if present
            if json_text.startswith("```json"):
                json_text = json_text[7:]
            if json_text.startswith("```"):
                json_text = json_text[3:]
            if json_text.endswith("```"):
                json_text = json_text[:-3]
            
            json_text = json_text.strip()
            
            # Parse JSON
            data = json.loads(json_text)
            
            suggestions_data = data.get("suggestions", [])
            suggestions = []
            errors = []
            
            for idx, suggestion_data in enumerate(suggestions_data):
                try:
                    # Map string values to enums
                    if isinstance(suggestion_data.get("termen_pastrare"), str):
                        suggestion_data["termen_pastrare"] = PastrareEnum(
                            suggestion_data["termen_pastrare"]
                        )
                    
                    if isinstance(suggestion_data.get("nivel_confidentialitate"), str):
                        suggestion_data["nivel_confidentialitate"] = ConfidentialityLevelEnum(
                            suggestion_data["nivel_confidentialitate"]
                        )
                    
                    # Ensure confidence is valid (not None, and within 0-1 range)
                    confidence = suggestion_data.get("confidence")
                    if confidence is None or (isinstance(confidence, (int, float)) and (confidence < 0 or confidence > 1)):
                        suggestion_data["confidence"] = 0.7  # Default confidence
                    
                    suggestion = NomenclatorSuggestion(**suggestion_data)
                    suggestions.append(suggestion)
                    
                except (ValidationError, ValueError) as e:
                    error_msg = f"Error parsing suggestion {idx + 1}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
            
            return suggestions, errors if errors else None
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON response: {str(e)}"
            logger.error(error_msg)
            return [], [error_msg]
        except Exception as e:
            error_msg = f"Error processing suggestions: {str(e)}"
            logger.error(error_msg)
            return [], [error_msg]
