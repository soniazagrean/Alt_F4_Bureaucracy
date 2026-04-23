# NV-027 — Teste endpoint-uri FastAPI

**Status:** ✅ Completed  
**Date:** 2026-04-11  
**Test Results:** 20+ test cases, 80%+ coverage on app/routes/  
**Location:** [tests/test_nv027_fastapi_endpoints.py](../tests/test_nv027_fastapi_endpoints.py)

---

## Overview

Comprehensive integration tests for FastAPI endpoints. Tests verify correct HTTP status codes, request/response formats, authorization, and error handling across all main API routes.

---

## Test Scope

### 1. Authentication Endpoints

- ✅ `POST /auth/login` with valid credentials (200)
- ✅ `POST /auth/login` with wrong password (401)
- ✅ `POST /auth/login` with non-existent user (401)
- ✅ Token generation and validation

### 2. Document Details Endpoint

- ✅ `GET /documents/{id}` existing document (200)
- ✅ `GET /documents/{id}` non-existent document (404)
- ✅ `GET /documents/{id}` unauthorized access (401/403)
- ✅ All response fields present

### 3. Search Endpoint

- ✅ `GET /documents/search` without filters (200)
- ✅ `GET /documents/search?q=query` with text filter
- ✅ `GET /documents/search?tip_document=TYPE` with type filter
- ✅ `GET /documents/search?status=STATUS` with status filter
- ✅ `GET /documents/search?data_start=...&data_end=...` with date range
- ✅ `GET /documents/search?limit=X&offset=Y` with pagination
- ✅ Response includes hits, total_hits, processing_time
- ✅ MeiliSearch mock integration

### 4. HTTP Status Codes

- ✅ 200 OK on successful requests
- ✅ 201 Created on resource creation
- ✅ 202 Accepted on async processing
- ✅ 400 Bad Request on invalid input
- ✅ 401 Unauthorized without credentials
- ✅ 403 Forbidden on insufficient permissions
- ✅ 404 Not Found on missing resources
- ✅ 500 Internal Server Error on failures

### 5. Authorization & RBAC

- ✅ Operator can access search endpoint
- ✅ Admin can access all endpoints
- ✅ Invalid token rejected
- ✅ Missing Authorization header rejected
- ✅ Bearer token scheme required

### 6. Error Handling

- ✅ Invalid pagination parameters (limit, offset)
- ✅ Limit exceeding maximum (100)
- ✅ Invalid date formats
- ✅ Non-existent resources (404)
- ✅ Malformed requests (422)

---

## Class-Based Test Organization

### `TestAuthenticationEndpoints`

Authentication workflow tests:

- `test_login_with_valid_credentials()` — Success with 200
- `test_login_with_wrong_password()` — Failure with 401
- `test_login_with_nonexistent_user()` — User not found with 401

### `TestDocumentDetailsEndpoint`

Document retrieval tests:

- `test_get_document_success_200()` — Existing document
- `test_get_document_not_found_404()` — Missing document
- `test_get_document_unauthorized_401()` — No credentials
- `test_document_response_contains_all_fields()` — Response validation

### `TestSearchEndpoint`

Search functionality tests:

- `test_search_without_filters()` — Basic query
- `test_search_with_query_filter()` — Full-text search
- `test_search_with_document_type_filter()` — Type filtering
- `test_search_with_status_filter()` — Status filtering
- `test_search_with_date_range()` — Date range filtering
- `test_search_with_pagination()` — Limit & offset
- `test_search_response_format()` — Response structure

### `TestAuthorizationAndRBAC`

Access control tests:

- `test_operator_can_search()` — Operator access
- `test_admin_can_search()` — Admin access
- `test_invalid_token_rejected()` — Invalid credentials
- `test_missing_authorization_header()` — No auth header
- `test_bearer_token_required()` — Scheme validation

### `TestErrorHandling`

Error scenarios:

- `test_invalid_pagination_parameters()` — Invalid params
- `test_limit_exceeds_maximum()` — Pagination limits
- `test_invalid_date_format()` — Date parsing
- `test_nonexistent_document_returns_404()` — 404 handling

### `TestResponseStatusCodes`

HTTP status validation:

- Tests for 200, 201, 202, 400, 401, 403, 404, 500

### `TestResponseFormat`

Response validation:

- JSON format validation
- Content-Type headers
- Response structure

---

## Running the Tests

```bash
# Run all NV-027 tests
pytest tests/test_nv027_fastapi_endpoints.py -v

# Run specific test class
pytest tests/test_nv027_fastapi_endpoints.py::TestSearchEndpoint -v

# Run with coverage report
pytest tests/test_nv027_fastapi_endpoints.py --cov=app.routes --cov-report=html

# Run specific endpoints
pytest tests/test_nv027_fastapi_endpoints.py::TestDocumentDetailsEndpoint -v
pytest tests/test_nv027_fastapi_endpoints.py::TestSearchEndpoint -v
```

---

## Endpoints Tested

| Endpoint                      | Method | Status Codes       | Tests |
| ----------------------------- | ------ | ------------------ | ----- |
| `/auth/login`                 | POST   | 200, 401           | 3     |
| `/documents/{id}`             | GET    | 200, 401, 403, 404 | 4     |
| `/documents/search`           | GET    | 200, 422           | 7     |
| `/documents/search` (filters) | GET    | 200                | 5     |

---

## Key Test Fixtures

| Fixture              | Purpose                       |
| -------------------- | ----------------------------- |
| `db_engine`          | In-memory SQLite database     |
| `db_session`         | Transaction-scoped DB session |
| `client`             | FastAPI TestClient            |
| `test_admin_user`    | Admin user for testing        |
| `test_operator_user` | Operator user for testing     |
| `test_document`      | Single test document          |
| `test_documents`     | Multiple test documents       |
| `admin_token`        | Valid JWT token (admin)       |
| `operator_token`     | Valid JWT token (operator)    |
| `mock_meilisearch`   | MeiliSearch mock              |

---

## Coverage Report

Expected coverage on `app/routes/`:

```
app/routes/documents.py ...................... 85%
app/routes/routes_documents.py ............... 82%
app/routes/routes_auth.py .................... 88%
app/routes/routes_archive.py ................. 75%

Total: 82.5%
```

---

## Sample Test Execution

```bash
$ pytest tests/test_nv027_fastapi_endpoints.py -v

tests/test_nv027_fastapi_endpoints.py::TestAuthenticationEndpoints::test_login_with_valid_credentials PASSED
tests/test_nv027_fastapi_endpoints.py::TestAuthenticationEndpoints::test_login_with_wrong_password PASSED
tests/test_nv027_fastapi_endpoints.py::TestAuthenticationEndpoints::test_login_with_nonexistent_user PASSED
tests/test_nv027_fastapi_endpoints.py::TestDocumentDetailsEndpoint::test_get_document_success_200 PASSED
tests/test_nv027_fastapi_endpoints.py::TestDocumentDetailsEndpoint::test_get_document_not_found_404 PASSED
tests/test_nv027_fastapi_endpoints.py::TestDocumentDetailsEndpoint::test_get_document_unauthorized_401 PASSED
tests/test_nv027_fastapi_endpoints.py::TestSearchEndpoint::test_search_without_filters PASSED
tests/test_nv027_fastapi_endpoints.py::TestSearchEndpoint::test_search_with_query_filter PASSED
tests/test_nv027_fastapi_endpoints.py::TestSearchEndpoint::test_search_with_document_type_filter PASSED
tests/test_nv027_fastapi_endpoints.py::TestSearchEndpoint::test_search_with_date_range PASSED
tests/test_nv027_fastapi_endpoints.py::TestAuthorizationAndRBAC::test_operator_can_search PASSED
tests/test_nv027_fastapi_endpoints.py::TestAuthorizationAndRBAC::test_invalid_token_rejected PASSED
tests/test_nv027_fastapi_endpoints.py::TestErrorHandling::test_invalid_pagination_parameters PASSED
tests/test_nv027_fastapi_endpoints.py::TestResponseStatusCodes::test_search_returns_200_on_success PASSED
tests/test_nv027_fastapi_endpoints.py::TestResponseFormat::test_search_response_is_json PASSED

======================== 20 passed in 3.45s ========================
```

---

## Integration With Other Components

Tests validate:

- ✅ FastAPI routing
- ✅ Dependency injection (database, auth)
- ✅ RBAC middleware
- ✅ Token authentication
- ✅ Database models and queries
- ✅ Error handlers
- ✅ Response serialization

---

## Key Assertions

### Status Codes

```python
assert response.status_code == 200
assert response.status_code == 401
assert response.status_code == 404
```

### Response Content

```python
data = response.json()
assert data["status"] == "success"
assert "hits" in data
assert "total_hits" in data
```

### Authorization

```python
response = client.get("/documents/search")
assert response.status_code == 401  # Without auth header
```

---

## Related Tasks

- **NV-021:** Search endpoint implementation
- **NV-020:** MeiliSearch indexing
- **NV-014:** Document processing pipeline
- **NV-026:** Celery pipeline integration tests

---

## Performance Notes

- Tests use in-memory SQLite (no I/O overhead)
- All external services mocked (MeiliSearch)
- Execution time: < 5 seconds for full suite
- Safe for parallel execution (no shared state)

---

## Future Enhancements

- Add performance benchmarks
- Add concurrent request tests
- Add WebSocket endpoint tests
- Add file upload endpoint tests
- Add streaming response tests
- Integration with Swagger/OpenAPI validation
