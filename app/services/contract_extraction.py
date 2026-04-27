"""Contract extraction service using LLM vision capabilities."""
import base64
import json
from pathlib import Path
from typing import Optional, Tuple
import logging

import httpx
from pydantic import ValidationError

from app.config import settings
from app.schemas_contract import ContractData, ContractExtractionResponse

logger = logging.getLogger(__name__)


class ContractExtractionService:
    """Service for extracting structured contract data from document images."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured in settings or provided as argument")

        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o"

    @staticmethod
    def _image_to_base64(image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.standard_b64encode(image_file.read()).decode("utf-8")

    @staticmethod
    def _get_image_media_type(image_path: str) -> str:
        ext = Path(image_path).suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return mime_types.get(ext, "image/png")

    @staticmethod
    def _create_extraction_prompt(language: str = "en") -> str:
        lang_hint = "Romanian" if language == "ro" else "English" if language == "en" else language
        return f"""You are an expert contract data extraction specialist. Analyze this contract image (likely in {lang_hint}) and extract key fields.

Return ONLY valid JSON in this exact format:
{{
  "contract_number": "string or null",
  "party_a": "string or null",
  "party_b": "string or null",
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null",
  "contract_value": 0.0,
  "currency": "RON",
  "scope_of_work": "string or null"
}}

Rules:
1. Extract exact values visible in document.
2. If missing, return null.
3. Numeric values must be plain numbers (no currency symbols).
4. Do not return markdown or explanations, only JSON."""

    def _call_openai_api(self, image_base64: str, media_type: str, prompt: str) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{image_base64}"},
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1400,
        }

        with httpx.Client() as client:
            response = client.post(self.base_url, json=payload, headers=headers, timeout=60.0)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _parse_openai_response(response: dict) -> Tuple[dict, float]:
        if "choices" not in response or not response["choices"]:
            raise ValueError("No choices in API response")
        text_content = response["choices"][0].get("message", {}).get("content", "")
        if not text_content:
            raise ValueError("No content in API response")

        if "```json" in text_content:
            start = text_content.find("```json") + 7
            end = text_content.find("```", start)
            text_content = text_content[start:end].strip()
        elif "```" in text_content:
            start = text_content.find("```") + 3
            end = text_content.find("```", start)
            text_content = text_content[start:end].strip()

        extracted_data = json.loads(text_content)
        return extracted_data, 0.9

    def extract_contract_data(
        self,
        image_path: str,
        language: str = "en",
    ) -> Tuple[Optional[ContractData], Optional[list], float]:
        try:
            image_base64 = self._image_to_base64(image_path)
            media_type = self._get_image_media_type(image_path)
            prompt = self._create_extraction_prompt(language)
            response = self._call_openai_api(image_base64, media_type, prompt)
            extracted_data, confidence = self._parse_openai_response(response)

            contract_data = ContractData(**extracted_data)
            return contract_data, None, confidence
        except ValidationError as exc:
            errors = [f"{error['loc'][0]}: {error['msg']}" for error in exc.errors()]
            return None, errors, 0.0
        except Exception as exc:
            logger.error("Error extracting contract data: %s", exc)
            return None, [f"Extraction error: {exc}"], 0.0

    async def extract_contract_async(
        self,
        image_path: str,
        language: str = "en",
    ) -> ContractExtractionResponse:
        contract_data, errors, confidence = self.extract_contract_data(image_path, language)
        if contract_data:
            return ContractExtractionResponse(success=True, data=contract_data, confidence=confidence)
        return ContractExtractionResponse(success=False, errors=errors or ["Unknown extraction error"], confidence=confidence)
