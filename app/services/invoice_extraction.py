"""Invoice extraction service using LLM with vision capabilities."""
import json
import base64
from typing import Optional, Tuple
from pathlib import Path
import logging
import time
from decimal import Decimal
from copy import deepcopy
import re

import httpx

from app.config import settings
from app.schemas_invoice import InvoiceData, InvoiceExtractionResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class InvoiceExtractionService:
    """Service for extracting structured data from invoice images using LLM vision."""

    @staticmethod
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

    @staticmethod
    def _normalize_extracted_data(extracted_data: dict) -> dict:
        """Normalize common alias keys and value formats before validation."""
        data = deepcopy(extracted_data)

        aliases = {
            "nr_factura": ["invoice_number", "invoice_no", "factura", "number"],
            "data": ["date", "invoice_date", "issue_date"],
            "furnizor": ["supplier", "vendor", "company_name"],
            "CUI": ["cui", "tax_id", "company_tax_id", "vat_number", "cif"],
            "IBAN": ["iban", "account_iban", "bank_account"],
            "currency": ["cur", "moneda", "monedă"],
            "total": ["amount_total", "total_amount", "grand_total", "sum_total"],
            "TVA": ["vat", "tax", "vat_amount", "tax_amount"],
            "numar_ordine": ["po_number", "order_number", "purchase_order"],
            "termen_plata": ["due_date", "payment_due", "deadline"],
            "observatii": ["notes", "remarks"],
            "items": ["line_items", "produse", "articole"],
        }

        for canonical_key, alias_keys in aliases.items():
            if data.get(canonical_key) in (None, "", []):
                for alias_key in alias_keys:
                    if alias_key in data and data[alias_key] not in (None, "", []):
                        data[canonical_key] = data[alias_key]
                        break

        if isinstance(data.get("items"), list):
            normalized_items = []
            for item in data["items"]:
                if not isinstance(item, dict):
                    normalized_items.append(item)
                    continue

                normalized_item = dict(item)
                item_aliases = {
                    "quantity": ["qty", "cantitate"],
                    "unit": ["uom", "unit_of_measurement"],
                    "unit_price": ["price", "unitprice", "pret_unitar"],
                    "total_price": ["amount", "line_total", "total", "value"],
                }
                for canonical_key, alias_keys in item_aliases.items():
                    if normalized_item.get(canonical_key) in (None, ""):
                        for alias_key in alias_keys:
                            if alias_key in normalized_item and normalized_item[alias_key] not in (None, ""):
                                normalized_item[canonical_key] = normalized_item[alias_key]
                                break
                normalized_items.append(normalized_item)
            data["items"] = normalized_items

        return data
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the service with OpenAI API key.
        
        Args:
            api_key: OpenAI API key. If None, uses OPENAI_API_KEY from settings.
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured in settings or provided as argument")
        
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o"
    
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
            
            # Call OpenAI API
            response = self._call_openai_api(image_base64, media_type, prompt)
            
            # Parse the response
            extracted_data, confidence = self._parse_openai_response(response)
            extracted_data = self._normalize_extracted_data(extracted_data)
            
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
    "CUI": "company tax ID (8-10 digits)",
    "IBAN": "bank account IBAN or null",
    "currency": "currency code (EUR, RON, USD, GBP, etc) or null",
    "items": [
        {{
            "description": "item description",
            "quantity": 1.0,
            "unit": "unit of measurement (buc, kg, etc)",
            "unit_price": 100.00,
            "total_price": 200.00
        }}
    ],
    "total": 238.00,
    "TVA": 38.00,
    "numar_ordine": "PO/order number or null",
    "termen_plata": "payment deadline in DD.MM.YYYY format or null",
    "observatii": "additional notes or null"
}}

EXTRACTION RULES:
1. Extract EXACTLY what you see - do not invent data.
2. Use the keys exactly as shown above.
3. For dates: use DD.MM.YYYY format (e.g., 15.03.2024).
4. For amounts: return plain numbers only, without currency symbols or text.
5. For CUI: return only digits, 8-10 digits if available.
6. For items: list all visible line items.
7. If a field is not visible/available, use null (not empty string).
8. Ensure all numeric values are valid JSON numbers.
9. For IBAN: clean spaces and uppercase it, or use null if not found.

Output ONLY the JSON object, no markdown, no explanations."""
        
        return prompt
    
    def _call_openai_api(self, image_base64: str, media_type: str, prompt: str) -> dict:
        """
        Call OpenAI API with vision capabilities (GPT-4 Vision).
        
        Args:
            image_base64: Base64 encoded image
            media_type: MIME type of the image
            prompt: Extraction prompt
            
        Returns:
            API response as dictionary
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.0,
            "max_tokens": 2048
        }
        
        max_attempts = 3
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client() as client:
                    response = client.post(
                        self.base_url,
                        json=payload,
                        headers=headers,
                        timeout=60.0
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code in {429, 500, 502, 503, 504} and attempt < max_attempts:
                    retry_after = exc.response.headers.get("Retry-After") if exc.response is not None else None
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * attempt
                    logger.warning(
                        "OpenAI invoice extraction request failed with %s; retrying in %.1fs (%s/%s)",
                        status_code,
                        delay,
                        attempt,
                        max_attempts,
                    )
                    time.sleep(delay)
                    last_error = exc
                    continue
                raise Exception(f"OpenAI API request failed: {str(exc)}")
            except httpx.RequestError as e:
                last_error = e
                if attempt < max_attempts:
                    delay = 2.0 * attempt
                    logger.warning(
                        "OpenAI invoice extraction transport error; retrying in %.1fs (%s/%s): %s",
                        delay,
                        attempt,
                        max_attempts,
                        e,
                    )
                    time.sleep(delay)
                    continue
                raise Exception(f"OpenAI API request failed: {str(e)}")

        raise Exception(f"OpenAI API request failed after {max_attempts} attempts: {last_error}")
    
    @staticmethod
    def _parse_openai_response(response: dict) -> Tuple[dict, float]:
        """
        Parse OpenAI API response and extract JSON.
        
        Args:
            response: API response dictionary
            
        Returns:
            Tuple of (extracted JSON dict, confidence score)
        """
        try:
            if "choices" not in response or not response["choices"]:
                raise ValueError("No choices in API response")

            choice = response["choices"][0]
            if "message" not in choice or "content" not in choice["message"]:
                raise ValueError("No content in message")

            text_content = choice["message"]["content"]

            if isinstance(text_content, dict):
                extracted_data = text_content
                return extracted_data, 0.95

            if "```json" in text_content:
                start = text_content.find("```json") + 7
                end = text_content.find("```", start)
                text_content = text_content[start:end].strip()
            elif "```" in text_content:
                start = text_content.find("```") + 3
                end = text_content.find("```", start)
                text_content = text_content[start:end].strip()

            extracted_data = json.loads(text_content)
            return extracted_data, 0.95

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse API response as JSON: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to parse OpenAI response: {str(e)}")
    
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
