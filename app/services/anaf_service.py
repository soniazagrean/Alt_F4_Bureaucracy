"""
ANAF (Romanian Tax Authority) supplier validation service.

Free public API: POST https://webservicesp.anaf.ro/PlatitorTvaRest/api/v8/ws/tva
Body: [{"cui": <int>, "data": "YYYY-MM-DD"}]

Used to validate supplier CUI codes extracted from invoices and detect:
  - Inactive companies (statusInactivi)
  - Name mismatches between document and official ANAF registry
"""

import difflib
import logging
from datetime import date
from typing import Optional

import requests

logger = logging.getLogger(__name__)

ANAF_URL = "https://webservicesp.anaf.ro/PlatitorTvaRest/api/v8/ws/tva"
TIMEOUT_SECONDS = 5

# Simple in-process cache: {"{cui}:{date}": result_dict}
# Avoids repeated network calls for the same CUI within a Celery worker process.
_cache: dict[str, dict] = {}


def validate_cui(cui: str, lookup_date: Optional[str] = None) -> dict:
    """
    Query the Romanian ANAF API for a CUI (company fiscal code).

    Returns:
        {
          "cui": str,
          "found": bool,
          "is_active": bool,         # False when statusInactivi is True
          "company_name": str,       # Official name from ANAF (denumire)
          "address": str,
          "registration_date": str,
          "raw": dict | None,
          "error": str | None,       # populated on network/parse errors
        }
    """
    if not cui:
        return {"cui": cui, "found": False, "is_active": False,
                "company_name": "", "address": "", "registration_date": "",
                "raw": None, "error": "empty CUI"}

    # Normalise: strip non-digits
    cui_clean = "".join(c for c in str(cui) if c.isdigit())
    if not cui_clean:
        return {"cui": cui, "found": False, "is_active": False,
                "company_name": "", "address": "", "registration_date": "",
                "raw": None, "error": "invalid CUI (no digits)"}

    lookup_date = lookup_date or date.today().strftime("%Y-%m-%d")
    cache_key = f"{cui_clean}:{lookup_date}"

    if cache_key in _cache:
        return _cache[cache_key]

    try:
        resp = requests.post(
            ANAF_URL,
            json=[{"cui": int(cui_clean), "data": lookup_date}],
            timeout=TIMEOUT_SECONDS,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        result = {"cui": cui_clean, "found": False, "is_active": False,
                  "company_name": "", "address": "", "registration_date": "",
                  "raw": None, "error": "ANAF API timeout"}
        _cache[cache_key] = result
        return result
    except Exception as exc:
        logger.warning("ANAF lookup failed for CUI %s: %s", cui_clean, exc)
        result = {"cui": cui_clean, "found": False, "is_active": False,
                  "company_name": "", "address": "", "registration_date": "",
                  "raw": None, "error": str(exc)}
        _cache[cache_key] = result
        return result

    found_list = data.get("found") or []
    if not found_list:
        result = {"cui": cui_clean, "found": False, "is_active": False,
                  "company_name": "", "address": "", "registration_date": "",
                  "raw": data, "error": None}
        _cache[cache_key] = result
        return result

    entry = found_list[0]
    # statusInactivi: true → company is inactive
    is_active = not bool(entry.get("statusInactivi", False))
    result = {
        "cui": cui_clean,
        "found": True,
        "is_active": is_active,
        "company_name": (entry.get("denumire") or "").strip(),
        "address": (entry.get("adresa") or "").strip(),
        "registration_date": entry.get("dataStartScpTva") or "",
        "raw": entry,
        "error": None,
    }
    _cache[cache_key] = result
    return result


def name_similarity(a: str, b: str) -> float:
    """Return 0.0–1.0 similarity between two company name strings (case-insensitive)."""
    def _norm(s: str) -> str:
        return " ".join(s.upper().split())

    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()