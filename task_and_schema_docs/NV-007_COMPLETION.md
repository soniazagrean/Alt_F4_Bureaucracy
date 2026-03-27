# NV-007 — Prompt engineering: clasificare tip document

## Status: COMPLETED

## What was implemented

### New files
- `app/services/document_classification.py` — `DocumentClassificationService` class
- `app/schemas_classification.py` — `ClassificationResult`, `ClassificationResponse` schemas
- `tests/test_document_classification.py` — unit + integration tests

### Modified files
| File | Change |
|---|---|
| `app/schemas.py` | Added `ADRESA`, `CERERE`, `HCL`, `DEVIZ` to `DocumentTypeEnum` |
| `app/models/document.py` | Same enum extension (keep in sync with schemas.py) |
| `app/routes/routes_documents.py` | Added `POST /documents/{id}/classify` endpoint |
| `alembic/versions/<hash>_add_document_type_enum_values_nv007.py` | New migration: ALTER TYPE adds 4 values |

## Supported document types
| Enum value | Tip document |
|---|---|
| `invoice` | Factură |
| `contract` | Contract |
| `report` | Raport |
| `correspondence` | Corespondență generală |
| `decision` | Decizie administrativă |
| `protocol` | Proces-verbal (PV) |
| `adresa` | Adresă oficială |
| `cerere` | Cerere / Petiție |
| `hcl` | Hotărâre Consiliu Local |
| `deviz` | Deviz de lucrări |

## API contract
```
POST /documents/{document_id}/classify
→ 200 { success: true, data: { tip_document, confidence, reasoning }, document_id }
→ 404 if document not found
→ 422 if classification fails
```

## Prompt design decisions
- Prompt in Romanian — improves accuracy for Romanian administrative documents
- `temperature=0.0` — deterministic output for classification
- `detail: "low"` vision mode — ~80% token savings; sufficient for document type recognition
- Reasoning field included for debugging / audit trail (stored in response, not DB)

## Database changes
- `documents.document_type` updated after classification
- `documents.confidence` updated after classification
- `documents.status` set to `CLASSIFIED`

## Running the migration
```bash
alembic upgrade head
```

## Running the tests
```bash
pytest tests/test_document_classification.py -v
```