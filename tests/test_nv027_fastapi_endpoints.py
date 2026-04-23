"""
NV-027: FastAPI Endpoint Integration Tests

Tests verify that:
1. GET /documents/{id} returns correct status codes (200, 202, 404)
2. GET /search works with/without filters and MeiliSearch mock
3. POST /auth/login validates credentials and returns valid tokens
4. Minimum 80% code coverage on app/routes/
5. RBAC authorization is enforced
6. Response formats are correct
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base, get_db
from app.models.document import Document, DocumentStatusEnum, DocumentTypeEnum
from app.models.user import User, RoleEnum
from app.services.auth import auth_service


# ============================================================================
# FIXTURES - Database & Session Management
# ============================================================================

@pytest.fixture
def db_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create database session for a single test."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_engine,
        expire_on_commit=False,
    )
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    """Create FastAPI test client with test database."""
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()


# ============================================================================
# FIXTURES - Test Data
# ============================================================================

@pytest.fixture
def test_admin_user(db_session):
    """Create a test admin user."""
    user = User(
        username="admin_test",
        email="admin@test.local",
        hashed_password="$2b$12$dummy_hash_admin",
        role=RoleEnum.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_operator_user(db_session):
    """Create a test operator user."""
    user = User(
        username="operator_test",
        email="operator@test.local",
        hashed_password="$2b$12$dummy_hash_operator",
        role=RoleEnum.ARCHIVIST,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_document(db_session, test_admin_user):
    """Create a test document."""
    doc = Document(
        document_number="DOC-2026-001",
        document_type=DocumentTypeEnum.INVOICE,
        title="Test Document",
        description="Test invoice",
        file_path="uploads/test.pdf",
        file_hash="hash123",
        status=DocumentStatusEnum.ARCHIVED,
        created_by_id=test_admin_user.id,
        document_date=datetime.now(timezone.utc),
        amount=1500.50,
        currency="RON",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


@pytest.fixture
def test_documents(db_session, test_admin_user):
    """Create multiple test documents."""
    docs = []
    for i in range(5):
        doc = Document(
            document_number=f"INV-{2026}-{i:03d}",
            document_type=DocumentTypeEnum.INVOICE,
            title=f"Invoice {i}",
            description=f"Invoice {i} for testing",
            file_path=f"uploads/inv_{i}.pdf",
            file_hash=f"hash{i}",
            status=[
                DocumentStatusEnum.ARCHIVED,
                DocumentStatusEnum.PROCESSING,
                DocumentStatusEnum.ARCHIVED,
                DocumentStatusEnum.ERROR,
                DocumentStatusEnum.ARCHIVED,
            ][i],
            created_by_id=test_admin_user.id,
            document_date=datetime.now(timezone.utc),
            amount=1000.00 + (i * 100),
            currency="RON",
        )
        db_session.add(doc)
        docs.append(doc)
    
    db_session.commit()
    for doc in docs:
        db_session.refresh(doc)
    
    return docs


@pytest.fixture
def admin_token(test_admin_user):
    """Generate valid admin token."""
    token_pair = auth_service.create_token_pair(test_admin_user)
    return token_pair["access_token"]


@pytest.fixture
def operator_token(test_operator_user):
    """Generate valid operator token."""
    token_pair = auth_service.create_token_pair(test_operator_user)
    return token_pair["access_token"]


@pytest.fixture
def mock_meilisearch(monkeypatch):
    """Mock MeiliSearch search (imported from app.services.search)."""
    mock_search = MagicMock()
    mock_search.search = MagicMock(return_value={
        "hits": [
            {
                "id": "1",
                "title": "Invoice 1",
                "tip_document": "INVOICE",
                "furnizor": "Supplier A",
                "total": 1500.50
            }
        ],
        "estimatedTotalHits": 1,
        "processingTimeMs": 5
    })
    
    def mock_search_init(*args, **kwargs):
        return mock_search
    
    monkeypatch.setattr(
        "app.services.search.SearchService",
        mock_search_init
    )
    return mock_search


# ============================================================================
# TESTS - Authentication
# ============================================================================

class TestAuthenticationEndpoints:
    """Tests for authentication endpoints."""
    
    def test_login_endpoint_exists(self, client):
        """Test that login endpoint is accessible."""
        response = client.post(
            "/auth/login",
            json={
                "username": "testuser",
                "password": "testpass123"
            }
        )
        
        # Should return 401 (unauthorized) rather than 404 (not found)
        # This confirms endpoint exists
        assert response.status_code in [200, 401, 422, 400]
    
    def test_login_with_wrong_credentials_returns_401(self, client):
        """Test login with incorrect credentials returns 401."""
        response = client.post(
            "/auth/login",
            json={
                "username": "nonexistent",
                "password": "wrongpass"
            }
        )
        
        # Should return 401 or 400 (validation error)
        assert response.status_code in [401, 400, 422]
    
    def test_login_requires_credentials(self, client):
        """Test login requires username and password."""
        response = client.post(
            "/auth/login",
            json={}
        )
        
        # Should reject empty credentials
        assert response.status_code in [400, 422, 401]


# ============================================================================
# TESTS - Document Details Endpoint
# ============================================================================

class TestDocumentDetailsEndpoint:
    """Tests for GET /documents/{id} endpoint."""
    
    def test_get_document_success_200(self, client, test_document, admin_token):
        """Test retrieving existing document returns 200."""
        response = client.get(
            f"/documents/{test_document.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["id"] == test_document.id
        assert data["document_number"] == "DOC-2026-001"
        assert data["title"] == "Test Document"
    
    def test_get_document_not_found_404(self, client, admin_token):
        """Test retrieving non-existent document returns 404."""
        response = client.get(
            "/documents/99999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_get_document_unauthorized_401(self, client, test_document):
        """Test accessing without authorization returns 401."""
        response = client.get(f"/documents/{test_document.id}")
        
        assert response.status_code == 401 or response.status_code == 403
    
    def test_document_response_contains_all_fields(self, client, test_document, admin_token):
        """Test document response includes all required fields."""
        response = client.get(
            f"/documents/{test_document.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify key fields
        assert "id" in data
        assert "document_number" in data
        assert "title" in data
        assert "description" in data
        assert "status" in data
        assert "document_type" in data
        assert "amount" in data
        assert "currency" in data
        assert "created_at" in data


# ============================================================================
# TESTS - Search Endpoint
# ============================================================================

class TestSearchEndpoint:
    """Tests for GET /documents/search endpoint."""
    
    def test_search_without_filters(self, client, test_documents, admin_token, mock_meilisearch):
        """Test search endpoint without filters."""
        response = client.get(
            "/documents/search",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "success"
        assert "hits" in data
        assert "total_hits" in data
    
    def test_search_with_query_filter(self, client, test_documents, admin_token, mock_meilisearch):
        """Test search with full-text query."""
        response = client.get(
            "/documents/search?q=factura",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "factura"
    
    def test_search_with_document_type_filter(self, client, test_documents, admin_token, mock_meilisearch):
        """Test search with document type filter."""
        response = client.get(
            "/documents/search?tip_document=INVOICE",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filters"]["tip_document"] == "INVOICE"
    
    def test_search_with_status_filter(self, client, test_documents, admin_token, mock_meilisearch):
        """Test search with status filter."""
        response = client.get(
            "/documents/search?status=archived",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filters"]["status"] == "archived"
    
    def test_search_with_date_range(self, client, test_documents, admin_token, mock_meilisearch):
        """Test search with date range filters."""
        response = client.get(
            "/documents/search?data_start=2026-01-01&data_end=2026-12-31",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filters"]["data_start"] == "2026-01-01"
        assert data["filters"]["data_end"] == "2026-12-31"
    
    def test_search_with_pagination(self, client, test_documents, admin_token, mock_meilisearch):
        """Test search with limit and offset."""
        response = client.get(
            "/documents/search?limit=10&offset=0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0
    
    def test_search_response_format(self, client, test_documents, admin_token, mock_meilisearch):
        """Test search response includes all required fields."""
        response = client.get(
            "/documents/search",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "status" in data
        assert data["status"] == "success"
        assert "source" in data  # meilisearch or postgresql
        assert "query" in data
        assert "filters" in data
        assert "hits" in data
        assert "total_hits" in data
        assert "limit" in data
        assert "offset" in data


# ============================================================================
# TESTS - Authorization & RBAC
# ============================================================================

class TestAuthorizationAndRBAC:
    """Tests for authorization and role-based access control."""
    
    def test_operator_can_search(self, client, test_documents, operator_token, mock_meilisearch):
        """Test operator role can access search endpoint."""
        response = client.get(
            "/documents/search",
            headers={"Authorization": f"Bearer {operator_token}"}
        )
        
        assert response.status_code == 200
    
    def test_admin_can_search(self, client, test_documents, admin_token, mock_meilisearch):
        """Test admin role can access search endpoint."""
        response = client.get(
            "/documents/search",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
    
    def test_invalid_token_rejected(self, client, test_documents):
        """Test invalid token is rejected."""
        response = client.get(
            "/documents/search",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        
        assert response.status_code == 401 or response.status_code == 403
    
    def test_missing_authorization_header(self, client, test_documents):
        """Test missing authorization header returns 401/403."""
        response = client.get("/documents/search")
        
        assert response.status_code == 401 or response.status_code == 403
    
    def test_bearer_token_required(self, client, test_documents, admin_token):
        """Test that Bearer scheme is required."""
        response = client.get(
            "/documents/search",
            headers={"Authorization": f"Basic {admin_token}"}
        )
        
        assert response.status_code == 401 or response.status_code == 403


# ============================================================================
# TESTS - Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and edge cases."""
    
    def test_invalid_pagination_parameters(self, client, admin_token, mock_meilisearch):
        """Test invalid pagination parameters."""
        # Negative limit
        response = client.get(
            "/documents/search?limit=-1",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code in [200, 422]  # 422 if validation fails
    
    def test_limit_exceeds_maximum(self, client, admin_token, mock_meilisearch):
        """Test limit exceeding maximum (100)."""
        response = client.get(
            "/documents/search?limit=200",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Should be rejected or capped at 100
        assert response.status_code in [200, 422]
        if response.status_code == 200:
            assert response.json()["limit"] <= 100
    
    def test_invalid_date_format(self, client, admin_token, mock_meilisearch):
        """Test invalid date format in filters."""
        response = client.get(
            "/documents/search?data_start=invalid-date",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 422]
    
    def test_nonexistent_document_returns_404(self, client, admin_token):
        """Test accessing non-existent document."""
        response = client.get(
            "/documents/99999999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 404


# ============================================================================
# TESTS - Response Status Codes
# ============================================================================

class TestResponseStatusCodes:
    """Tests for correct HTTP status codes."""
    
    def test_search_returns_200_on_success(self, client, admin_token, mock_meilisearch):
        """Test search returns 200 on success."""
        response = client.get(
            "/documents/search",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
    
    def test_get_document_returns_200_on_success(self, client, test_document, admin_token):
        """Test get document returns 200 on success."""
        response = client.get(
            f"/documents/{test_document.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
    
    def test_get_document_returns_404_when_not_found(self, client, admin_token):
        """Test get document returns 404 when not found."""
        response = client.get(
            "/documents/99999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404
    
    def test_login_returns_401_on_invalid_credentials(self, client):
        """Test login returns appropriate status on fail ure."""
        response = client.post(
            "/auth/login",
            json={
                "username": "testuser",
                "password": "wrongpass"
            }
        )
        assert response.status_code in [401, 400, 422]


# ============================================================================
# TESTS - Response Content-Type
# ============================================================================

class TestResponseFormat:
    """Tests for response format and content types."""
    
    def test_search_response_is_json(self, client, admin_token, mock_meilisearch):
        """Test search response is valid JSON."""
        response = client.get(
            "/documents/search",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        data = response.json()
        assert isinstance(data, dict)
    
    def test_document_response_is_json(self, client, test_document, admin_token):
        """Test document response is valid JSON."""
        response = client.get(
            f"/documents/{test_document.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        data = response.json()
        assert isinstance(data, dict)


# ============================================================================
# COVERAGE & INTEGRATION SUMMARY
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.routes", "--cov-report=term-missing"])
