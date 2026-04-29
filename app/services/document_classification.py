# app/services/document_classification.py
"""Document type classification service using LLM with vision capabilities."""

import json
import base64
import time
from pathlib import Path
from typing import Optional, Tuple
import logging

import httpx

from app.config import settings
from app.schemas_classification import ClassificationResult, ClassificationResponse
from app.schemas import DocumentTypeEnum

logger = logging.getLogger(__name__)

# Human-readable Romanian labels for each enum value — used in the prompt
DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "invoice": "Factură (invoice fiscal)",
    "contract": "Contract (contract de servicii, furnizare, etc.)",
    "report": "Raport (raport de activitate, raport tehnic)",
    "correspondence": "Corespondență generală (notă internă, etc.)",
    "decision": "Decizie administrativă (decizie, ordin)",
    "protocol": "Proces-verbal / PV (ședință, recepție, constatare)",
    "other": "Alt tip de document (necunoscut)",
    "adresa": "Adresă oficială (adresă instituțională, înaintare)",
    "cerere": "Cerere / Petiție (cerere de aprobare, petiție)",
    "hcl": "HCL — Hotărâre a Consiliului Local",
    "deviz": "Deviz (deviz estimativ, deviz de lucrări)",
}


class DocumentClassificationService:
    """Classify a document image into one of the supported Romanian document types."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.model = (
            "gpt-4o"  # gpt-4o has best vision; cheaper than gpt-4-vision-preview
        )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _image_to_base64(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    @staticmethod
    def _get_media_type(image_path: str) -> str:
        ext = Path(image_path).suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(ext, "image/png")

    # ------------------------------------------------------------------ prompt

    @staticmethod
    def _create_classification_prompt() -> str:
        type_list = "\n".join(
            f'  "{k}": "{v}"' for k, v in DOCUMENT_TYPE_LABELS.items()
        )
        return f"""Ești un expert în clasificarea documentelor administrative și financiare românești.

Analizează imaginea documentului și determină tipul acestuia dintre variantele de mai jos.

TIPURI ACCEPTATE (folosește EXACT cheia din stânga):
{type_list}

RĂSPUNDE DOAR cu un obiect JSON valid, fără text suplimentar, în formatul:
{{
    "tip_document": "<cheie din lista de mai sus>",
    "confidence": <număr între 0.0 și 1.0>,
    "reasoning": "<maxim 1 propoziție explicând decizia>"
}}

REGULI:
1. "tip_document" trebuie să fie EXACT una din cheile de mai sus.
2. "confidence" = 1.0 dacă documentul este clar; 0.5–0.7 dacă există ambiguitate.
3. Dacă documentul nu se încadrează în nicio categorie, folosește "other".
4. Nu inventa informații. Clasifică doar ce vezi.
5. Răspunde DOAR cu JSON — fără markdown, fără explicații în afara câmpului "reasoning".
"""

    # ------------------------------------------------------------------ API call

    def _call_api(self, image_base64: str, media_type: str, prompt: str) -> dict:
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
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_base64}",
                                "detail": "low",  # "low" saves tokens; enough for classification
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.0,  # deterministic — classification should not vary
            "max_tokens": 256,  # classification response is tiny
        }
        max_attempts = 3
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client() as client:
                    resp = client.post(
                        self.base_url, json=payload, headers=headers, timeout=30.0
                    )
                    resp.raise_for_status()
                    return resp.json()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code in {429, 500, 502, 503, 504} and attempt < max_attempts:
                    retry_after = exc.response.headers.get("Retry-After") if exc.response is not None else None
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * attempt
                    logger.warning(
                        "OpenAI classification request failed with %s; retrying in %.1fs (%s/%s)",
                        status_code,
                        delay,
                        attempt,
                        max_attempts,
                    )
                    time.sleep(delay)
                    last_error = exc
                    continue
                raise
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < max_attempts:
                    delay = 2.0 * attempt
                    logger.warning(
                        "OpenAI classification transport error; retrying in %.1fs (%s/%s): %s",
                        delay,
                        attempt,
                        max_attempts,
                        exc,
                    )
                    time.sleep(delay)
                    continue
                raise

        raise RuntimeError(f"OpenAI classification request failed after {max_attempts} attempts: {last_error}")

    # ------------------------------------------------------------------ parser

    @staticmethod
    def _parse_response(response: dict) -> ClassificationResult:
        choices = response.get("choices", [])
        if not choices:
            raise ValueError("No choices in API response")

        content = choices[0].get("message", {}).get("content", "")

        # Strip optional markdown fences
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)

        # Validate tip_document is a known enum value
        tip_raw = data.get("tip_document", "other")
        try:
            tip = DocumentTypeEnum(tip_raw)
        except ValueError:
            logger.warning(
                f"LLM returned unknown type '{tip_raw}', defaulting to 'other'"
            )
            tip = DocumentTypeEnum.OTHER

        return ClassificationResult(
            tip_document=tip,
            confidence=float(data.get("confidence", 0.5)),
            reasoning=data.get("reasoning"),
        )

    # ------------------------------------------------------------------ public API

    def classify(
        self, image_path: str
    ) -> Tuple[Optional[ClassificationResult], Optional[list[str]]]:
        """
        Classify a document image.

        Returns:
            (ClassificationResult, None) on success
            (None, [error strings]) on failure
        """
        try:
            image_b64 = self._image_to_base64(image_path)
            media_type = self._get_media_type(image_path)
            prompt = self._create_classification_prompt()
            raw = self._call_api(image_b64, media_type, prompt)
            result = self._parse_response(raw)
            return result, None
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return None, [str(e)]

    async def classify_async(self, image_path: str) -> ClassificationResponse:
        """Async-friendly wrapper (runs sync call — swap for httpx.AsyncClient if needed)."""
        result, errors = self.classify(image_path)
        if result:
            return ClassificationResponse(success=True, data=result)
        return ClassificationResponse(success=False, errors=errors or ["Unknown error"])
