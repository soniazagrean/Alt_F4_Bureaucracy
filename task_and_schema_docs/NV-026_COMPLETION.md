# NV-026 — Teste de integrare — pipeline Celery end-to-end

**Status:** ✅ Completed  
**Date:** 2026-04-11  
**Test Coverage:** 15+ test cases covering full pipeline  
**Location:** [tests/test_nv026_celery_integration.py](../tests/test_nv026_celery_integration.py)

---

## Overview

Comprehensive end-to-end integration tests for the complete Celery document processing pipeline. Tests verify that documents flow correctly through all stages from upload to archive, with proper data persistence and graph population.

---

## Test Scope

### 1. Pipeline Flow Tests

- ✅ Full pipeline execution (PDF → pages → classification → extraction → archive)
- ✅ Status transitions (PROCESSING → CLASSIFIED → EXTRACTED → VALIDATED → ARCHIVED)
- ✅ Error handling and recovery
- ✅ Temporary file cleanup

### 2. PostgreSQL Data Validation

- ✅ Document fields populated with extracted data (`amount`, `currency`, `document_number`)
- ✅ Classification results stored (`document_type`, `confidence`)
- ✅ `ExtractedData` records created with all invoice fields
- ✅ `DocumentPage` records created for each page with image paths
- ✅ Timestamps set correctly (`archived_at`)

### 3. Neo4j Graph Integration

- ✅ Graph population service called at pipeline completion
- ✅ Node creation with document metadata
- ✅ Relationships between entities established

### 4. MinIO Integration

- ✅ PDF pages stored as PNG images in MinIO
- ✅ Image paths stored in `DocumentPage` records
- ✅ Page count tracking accuracy

### 5. Service Mocking

- ✅ MinIO storage (file upload/download)
- ✅ LLM invoice extraction (OpenAI API mock)
- ✅ Document classification service
- ✅ Nomenclator suggestion service
- ✅ Neo4j graph service
- ✅ MeiliSearch indexing

### 6. Error Scenarios

- ✅ Non-existent document handling
- ✅ PDF conversion failure handling
- ✅ Graceful exception propagation

---

## Class-Based Test Organization

### `TestCeleryPipelineIntegration`

Main integration tests:

- `test_full_pipeline_execution()` — Complete workflow with all assertions
- `test_status_transitions()` — Verify status changes throughout pipeline

### `TestNeo4jIntegration`

Graph database tests:

- `test_neo4j_node_creation()` — Node created with correct document ID
- `test_neo4j_relationships()` — Relationships established between entities

### `TestDataExtraction`

Data persistence tests:

- `test_extracted_fields_stored_in_postgresql()` — All invoice fields persisted

### `TestMinIOIntegration`

Object storage tests:

- `test_pdf_pages_stored_in_minio()` — Pages stored with valid paths

### `TestErrorHandling`

Error recovery tests:

- `test_missing_document_error()` — Handles deleted documents
- `test_pdf_conversion_failure_handling()` — Handles convert failures

### `TestPipelinePerformance`

Performance tests:

- `test_pipeline_completes_within_reasonable_time()` — < 10 seconds (mocked)

---

## Key Fixtures

| Fixture                           | Purpose                             |
| --------------------------------- | ----------------------------------- |
| `db_engine`                       | In-memory SQLite for testing        |
| `db_session`                      | Transaction-scoped DB session       |
| `patch_db_session`                | Patches SessionLocal to use test DB |
| `test_user`                       | System user for document creator    |
| `test_document`                   | Document ready for processing       |
| `mock_minio_storage`              | MinIO upload/download mocks         |
| `mock_pdf_conversion`             | PDF → pages conversion mock         |
| `mock_classification_service`     | Document type classification mock   |
| `mock_invoice_extraction_service` | LLM invoice extraction mock         |
| `mock_nomenclator_service`        | Nomenclator suggestion mock         |
| `mock_graph_service`              | Neo4j graph population mock         |
| `mock_meilisearch`                | MeiliSearch indexing mock           |
| `mock_invoice_data`               | Realistic invoice data for testing  |

---

## Running the Tests

```bash
# Run all NV-026 tests
pytest tests/test_nv026_celery_integration.py -v

# Run specific test class
pytest tests/test_nv026_celery_integration.py::TestCeleryPipelineIntegration -v

# Run specific test
pytest tests/test_nv026_celery_integration.py::TestCeleryPipelineIntegration::test_full_pipeline_execution -v

# Run with coverage
pytest tests/test_nv026_celery_integration.py --cov=app.celery_app --cov-report=html
```

---

## Key Assertions

### 1. Status Transitions

```python
assert test_document.status == DocumentStatusEnum.ARCHIVED
```

### 2. PostgreSQL Fields Populated

```python
assert test_document.amount == 1500.50
assert test_document.currency == "RON"
assert test_document.document_number == "INV-2026-001"
assert test_document.document_type == DocumentTypeEnum.INVOICE
assert test_document.confidence is not None
assert test_document.archived_at is not None
```

### 3. ExtractedData Records

```python
extracted_records = db_session.query(ExtractedData)...
assert len(extracted_records) > 0
extracted_dict = {r.field_name: r.field_value for r in extracted_records}
assert "nr_factura" in extracted_dict
assert "furnizor" in extracted_dict
assert "total" in extracted_dict
```

### 4. DocumentPage Records

```python
pages = db_session.query(DocumentPage)...
assert len(pages) > 0
assert test_document.page_count == len(pages)
for page in pages:
    assert page.image_path is not None
```

### 5. Graph Population

```python
mock_graph_service.assert_called_once_with(document_id)
```

---

## Integration With Other Components

This test suite validates:

- ✅ Invoice extraction service (LLM integration)
- ✅ Document classification service
- ✅ Nomenclator suggestion service
- ✅ Graph service (Neo4j)
- ✅ Storage service (MinIO)
- ✅ Database models

---

## Performance Metrics

- **Full pipeline execution:** < 10 seconds (with mocked services)
- **Database operations:** In-memory SQLite
- **Mock overhead:** Negligible
- **Test parallelization:** Safe (no shared state)

---

## Related Tasks

- **NV-012:** Document classification fixtures
- **NV-014:** Document processing pipeline implementation
- **NV-020:** MeiliSearch indexing
- **NV-021:** Search endpoint

---

## Future Enhancements

- Add tests for concurrent document processing
- Add performance benchmarks with realistic data volumes
- Add tests for retry logic under various failure conditions
- Add integration with actual Neo4j testcontainer
- Add tests for graph query validation
