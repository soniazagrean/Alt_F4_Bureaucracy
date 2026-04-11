# NV-020 — Automatic Document Indexing in MeiliSearch After Processing

**Status:** ✅ Completed  
**Date:** 2026-04-11  
**Test Results:** 11/11 passed ✅

---

## Overview

Implemented automatic indexing of processed documents in MeiliSearch at the end of the NV-014 document processing pipeline. This enables full-text search and filtering capabilities on documents after they have been classified, extracted, and validated.

---

## What Was Implemented

### 1. SearchService Enhancements (`app/services/search.py`)

#### Index Configuration

- **Filterable attributes** (for filtering/faceting):
  - `tip_document` — Document type (invoice, contract, report, etc.)
  - `status` — Processing status (pending, processing, archived, error, etc.)
  - `data` — Document date (ISO format)
  - `cod_nomenclator` — Nomenclator code

- **Sortable attributes**:
  - `created_at` — Creation timestamp
  - `updated_at` — Last update timestamp
  - `data` — Document date

- **Searchable attributes**:
  - `tip_document`, `furnizor`, `nr_factura`, `cod_nomenclator`
  - `title`, `description`

#### New Method: `prepare_document_for_indexing()`

Converts a Document ORM object + extracted data into MeiliSearch-ready format:

```python
{
    'id': str(document_id),
    'title': str,
    'description': str,
    'tip_document': str (enum value),
    'status': str (enum value),
    'furnizor': str (from extracted data),
    'nr_factura': str (from extracted data),
    'cod_nomenclator': str (from extracted data),
    'data': str (ISO datetime),
    'amount': float,
    'currency': str,
    'created_at': str (ISO datetime),
    'updated_at': str (ISO datetime),
}
```

### 2. Celery Indexing Task (`app/celery_app.py`)

#### New Task: `index_document_in_meilisearch_task()`

- **Trigger:** Called automatically after `process_document_task()` completes
- **Responsibility:**
  1. Fetch document and extracted data from database
  2. Prepare document data using SearchService
  3. Add/update document in MeiliSearch index
  4. Return success/error status
- **Retry behavior:** Failures are logged but don't block the main pipeline
- **Async:** Scheduled with Celery `apply_async()` for non-blocking execution

#### Integration Point

Added after graph population in `process_document_task()`:

```python
try:
    index_result = index_document_in_meilisearch_task.apply_async(
        args=[document_id],
        countdown=0
    )
    logger.info(f"Scheduled indexing task for document {document_id}: {index_result.id}")
except Exception as exc:
    logger.error(f"Indexing task scheduling failed for document {document_id}: {exc}")
```

---

## Testing

### Test File: `tests/test_nv020_indexing.py`

**Test Coverage:**

1. ✅ SearchService initialization and configuration
2. ✅ Index attribute configuration (filterable, sortable, searchable)
3. ✅ Document preparation with minimal data
4. ✅ Document preparation with extracted invoice data
5. ✅ Field defaults for missing data
6. ✅ ISO datetime format conversion
7. ✅ Database query and extracted data fetching
8. ✅ Handling of missing documents
9. ✅ Task integration with process_document_task

**Results:**

- **11 tests passed** ✅
- **1 test skipped** (requires running MeiliSearch instance)
- 0 failures

---

## Pipeline Flow

```
document_upload
    ↓
convert_pdf_to_images_task
    ↓
process_document_task (NV-014)
    ├── classify pages
    ├── extract invoice data
    ├── suggest nomenclator
    ├── populate graph
    └── SCHEDULE: index_document_in_meilisearch_task ← NV-020
                    ├── fetch document & extracted data
                    ├── prepare indexing payload
                    └── add to MeiliSearch

```

---

## Key Features

| Feature               | Details                                                                 |
| --------------------- | ----------------------------------------------------------------------- |
| **Searchable Fields** | tip_document, furnizor, nr_factura, cod_nomenclator, title, description |
| **Filterable Fields** | tip_document, status, data, cod_nomenclator                             |
| **Sortable Fields**   | created_at, updated_at, data                                            |
| **Extracted Data**    | Automatically included from ExtractedData table                         |
| **ISO Dates**         | All dates stored as ISO 8601 format for consistency                     |
| **Error Handling**    | Task failures logged but don't block main pipeline                      |
| **Async Execution**   | Non-blocking Celery task scheduling                                     |

---

## Schema Mapping

### From Document Model

- `document.id` → `id`
- `document.title` → `title`
- `document.description` → `description`
- `document.document_type.value` → `tip_document`
- `document.status.value` → `status`
- `document.document_number` → fallback for `nr_factura`
- `document.amount` → `amount`
- `document.currency` → `currency`
- `document.document_date` → `data`
- `document.created_at` → `created_at`
- `document.updated_at` → `updated_at`

### From ExtractedData Table

- `field_name='furnizor'` → `furnizor`
- `field_name='nr_factura'` → `nr_factura`
- `field_name='cod_nomenclator'` → `cod_nomenclator`

---

## Usage Example

Once a document is processed via NV-014, it will automatically be indexed and searchable. The search endpoint (NV-021) can then query these indexed documents:

```bash
# Example search query (implemented in NV-021)
GET /search?q=invoice&filter=status:archived&sort=data:desc
```

---

## Notes

- **Non-breaking:** Added as optional enhancement to existing pipeline
- **Graceful degradation:** If MeiliSearch is unavailable, main pipeline continues
- **Logging:** All operations logged at INFO/ERROR level for debugging
- **Database efficiency:** Uses single query for document + extracted data
- **Memory efficient:** Streams data through without large intermediate structures

---

## Files Modified

| File                           | Changes                                                                                 |
| ------------------------------ | --------------------------------------------------------------------------------------- |
| `app/services/search.py`       | Added index configuration, `prepare_document_for_indexing()` method                     |
| `app/celery_app.py`            | Added `index_document_in_meilisearch_task()`, integrated into `process_document_task()` |
| `tests/test_nv020_indexing.py` | New comprehensive test suite (12 tests)                                                 |

---

## Next Steps

→ **NV-021:** Implement `GET /search` endpoint to query indexed documents  
→ **NV-027:** Add unit tests for search endpoint  
→ **NV-024:** Build Streamlit upload interface (depends on working search)
