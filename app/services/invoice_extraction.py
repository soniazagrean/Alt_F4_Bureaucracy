"""Invoice extraction service using LLM with vision capabilities."""
import json
import base64
from typing import Optional, Tuple
from pathlib import Path
import logging
from decimal import Decimal

import httpx
from PIL import Image
import io

from app.config import settings
from app.schemas_invoice import InvoiceData, InvoiceExtractionResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class InvoiceExtractionService:
    """Service for extracting structured data from invoice images using LLM vision."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the service with Gemini API key.
        
        Args:
            api_key: Google Gemini API key. If None, uses GEMINI_API_KEY from settings.
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured in settings or provided as argument")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        self.model = "gemini-1.5-flash"
    
    @staticmethod
    def _image_to_base64(image_path: str) -> str:
        """
        Convert image file to base64 string.
        
        Args:
            image_path: Path to the image file (PNG, JPG, etc.)
            
        Returns:
            Base64 encoded image string
        """
        with open(image_path, 'rb') as image_file:
            return base64.standard_b64encode(image_file.read()).decode('utf-8')
    
    @staticmethod
    def _get_image_media_type(image_path: str) -> str:
        """Get MIME type based on file extension."""
        ext = Path(image_path).suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return mime_types.get(ext, 'image/png')
    
    def extract_invoice_data(
        self,
        image_path: str,
        language: str = "en"
    ) -> Tuple[Optional[InvoiceData], Optional[list], float]:
        """
        Extract invoice data from an image using Gemini vision API.
        
        Args:
            image_path: Path to the invoice image
            language: Language of the invoice ("en" for English, "ro" for Romanian, etc.)
            
        Returns:
            Tuple of (InvoiceData, errors list, confidence score)
        """
        try:
            # Convert image to base64
            image_base64 = self._image_to_base64(image_path)
            media_type = self._get_image_media_type(image_path)
            
            # Create the prompt
            prompt = self._create_extraction_prompt(language)
            
            # Call Gemini API
            response = self._call_gemini_api(image_base64, media_type, prompt)
            
            # Parse the response
            extracted_data, confidence = self._parse_gemini_response(response)
            
            # Validate with Pydantic
            try:
                invoice_data = InvoiceData(**extracted_data)
                return invoice_data, None, confidence
            except ValidationError as e:
                errors = [f"{error['loc'][0]}: {error['msg']}" for error in e.errors()]
                return None, errors, confidence
                
        except Exception as e:
            logger.error(f"Error extracting invoice data: {str(e)}")
            return None, [f"Extraction error: {str(e)}"], 0.0
    
    @staticmethod
    def _create_extraction_prompt(language: str = "en") -> str:
        """
        Create a detailed prompt for invoice extraction.
        
        Args:
            language: Language hint for the invoice
            
        Returns:
            Formatted prompt string
        """
        if language == "ro":
            lang_hint = "Romanian"
        elif language == "en":
            lang_hint = "English"
        else:
            lang_hint = language
        
        prompt = f"""You are an expert invoice data extraction specialist. Analyze this invoice image (likely in {lang_hint}) and extract all relevant data.

IMPORTANT: You MUST respond with ONLY valid JSON in this exact format, nothing else:

{{
    "nr_factura": "invoice number",
    "data": "date in DD.MM.YYYY format",
    "furnizor": "supplier/vendor name",
    "CUI": "company tax ID (10 digits for Romania)",
    "IBAN": "bank account IBAN or null",
    "items": [
        {{
            "description": "item description",
            "quantity": 1.0,
            "unit": "unit of measurement (buc, kg, etc)",
            "unit_price": "price per unit as decimal",
            "total_price": "line item total as decimal"
        }}
    ],
    "total": "total amount including VAT as decimal",
    "TVA": "VAT/tax amount as decimal",
    "numar_ordine": "PO/order number or null",
    "termen_plata": "payment deadline in DD.MM.YYYY format or null",
    "observatii": "additional notes or null"
}}

EXTRACTION RULES:
1. Extract EXACTLY what you see - do not invent data
2. For dates: Use DD.MM.YYYY format (e.g., 15.03.2024)
3. For amounts: Use decimal format with dot (e.g., 250.50, not "250,50")
4. For CUI: Extract the 10-digit company tax ID
5. For items: List all line items from the invoice table
6. Calculate totals accurately from the items list
7. TVA is the tax amount (difference between total and subtotal, or explicitly stated)
8. If a field is not visible/available, use null (not empty string)
9. Ensure all numeric values are valid decimals
10. For IBAN: Clean spaces and format standardly or use null if not found

VALIDATION:
- Invoice number cannot be empty
- Supplier name cannot be empty
- CUI must be numeric and 8-10 digits
- Items list must have at least one item
- Each item must have positive quantity and unit_price
- Total must be >= TVA
- All amounts must be positive or zero

Output ONLY the JSON object, no markdown, no explanations."""
        
        return prompt
    
    def _call_gemini_api(self, image_base64: str, media_type: str, prompt: str) -> dict:
        """
        Call Google Gemini API with vision capabilities.
        
        Args:
            image_base64: Base64 encoded image
            media_type: MIME type of the image
            prompt: Extraction prompt
            
        Returns:
            API response as dictionary
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        },
                        {
                            "inline_data": {
                                "mime_type": media_type,
                                "data": image_base64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,  # Lower temperature for more consistent extraction
                "maxOutputTokens": 2048,
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                }
            ]
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}?key={self.api_key}",
                    json=payload,
                    headers=headers,
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            raise Exception(f"API request failed: {str(e)}")
    
    @staticmethod
    def _parse_gemini_response(response: dict) -> Tuple[dict, float]:
        """
        Parse Gemini API response and extract JSON.
        
        Args:
            response: API response dictionary
            
        Returns:
            Tuple of (extracted JSON dict, confidence score)
        """
        try:
            # Extract text from response
            if "candidates" not in response or not response["candidates"]:
                raise ValueError("No candidates in API response")
            
            candidate = response["candidates"][0]
            if "content" not in candidate or not candidate["content"]["parts"]:
                raise ValueError("No content in candidate")
            
            text_content = candidate["content"]["parts"][0].get("text", "")
            
            # Try to extract JSON from the response
            # Sometimes the API might wrap it in markdown code blocks
            if "```json" in text_content:
                start = text_content.find("```json") + 7
                end = text_content.find("```", start)
                text_content = text_content[start:end].strip()
            elif "```" in text_content:
                start = text_content.find("```") + 3
                end = text_content.find("```", start)
                text_content = text_content[start:end].strip()
            
            # Parse JSON
            extracted_data = json.loads(text_content)
            
            # Calculate confidence based on response metadata
            confidence = 0.85  # Default confidence
            if "safetyRatings" in candidate:
                # Adjust confidence based on safety ratings
                confidence = 0.9
            
            return extracted_data, confidence
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse API response as JSON: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to parse Gemini response: {str(e)}")
    
    async def extract_invoice_async(
        self,
        image_path: str,
        language: str = "en"
    ) -> InvoiceExtractionResponse:
        """
        Async wrapper for invoice extraction.
        
        Args:
            image_path: Path to the invoice image
            language: Language of the invoice
            
        Returns:
            InvoiceExtractionResponse with results
        """
        invoice_data, errors, confidence = self.extract_invoice_data(image_path, language)
        
        if invoice_data is not None:
            return InvoiceExtractionResponse(
                success=True,
                data=invoice_data,
                errors=None,
                confidence=confidence
            )
        else:
            return InvoiceExtractionResponse(
                success=False,
                data=None,
                errors=errors or ["Unknown extraction error"],
                confidence=confidence
            )
