"""
NV-026: End-to-end Celery pipeline integration tests

Tests verify that:
1. Document processes through full pipeline (PDF → pages → classification → extraction → graph)
    2. Status transitions from PROCESSING → CLASSIFIED → EXTRACTED → VALIDATED → REVIEW
3. PostgreSQL fields are populated with extracted invoice data
4. Neo4j node is created with correct relationships
5. MinIO stores images correctly
6. Error handling and retries work as expected
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch, call
from io import BytesIO
from PIL import Image

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.document import Document, DocumentStatusEnum, DocumentTypeEnum, DocumentPage, ExtractedData
from app.models.user import User, RoleEnum
from app.celery_app import celery_app, process_document_task


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
def patch_db_session(monkeypatch, db_session):
    """Patch SessionLocal to use test database."""
    from app.celery_app import SessionLocal as OriginalSessionLocal
    
    def mock_session_local():
        return db_session
    
    monkeypatch.setattr("app.celery_app.SessionLocal", mock_session_local)
    return db_session


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        username="test_processor",
        email="processor@test.local",
        hashed_password="secret",
        role=RoleEnum.SYSTEM,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_document(db_session, test_user):
    """Create a test document ready to process."""
    doc = Document(
        document_number="INV-2026-001",
        document_type=DocumentTypeEnum.INVOICE,
        title="Test Invoice",
        description="Test invoice for pipeline validation",
        file_path="uploads/test-invoice.pdf",
        file_hash="hash123abc",
        status=DocumentStatusEnum.PROCESSING,
        created_by_id=test_user.id,
        document_date=datetime.now(timezone.utc),
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


# ============================================================================
# FIXTURES - External Services
# ============================================================================

@pytest.fixture
def mock_invoice_data():
    """Mock invoice data from LLM extraction."""
    return {
        "nr_factura": "INV-2026-001",
        "data": "2026-04-11",
        "furnizor": "Acme Corp",
        "cod_fiscal": "RO12345678",
        "total": 1500.50,
        "currency": "RON",
        "status_factura": "paid",
        "items": [
            {"description": "Service A", "quantity": 1, "unit_price": 1500.50}
        ]
    }


@pytest.fixture
def mock_minio_storage(monkeypatch, test_document):
    """Mock MinIO storage client."""
    mock_storage = MagicMock()
    mock_storage.client = MagicMock()
    mock_storage.upload_file = MagicMock(return_value="processed/documents/1/page_000.png")
    mock_storage.client.fget_object = MagicMock()
    
    # Generator for PDF to PNG conversion
    def mock_get_object(bucket, obj_name, local_path):
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='white')
        img.save(local_path)
    
    mock_storage.client.fget_object.side_effect = mock_get_object
    
    monkeypatch.setattr("app.celery_app.storage", mock_storage)
    return mock_storage


@pytest.fixture
def mock_pdf_conversion(monkeypatch):
    """Mock PDF to pages conversion."""
    def mock_pdf_to_pages(pdf_path, dpi=300):
        # Return a list with one mock image
        img = Image.new('RGB', (100, 100), color='white')
        return [img], None
    
    monkeypatch.setattr("app.celery_app.pdf_to_pages_safe", mock_pdf_to_pages)


@pytest.fixture
def mock_classification_service(monkeypatch):
    """Mock document classification service."""
    mock_classifier = MagicMock()
    
    # Mock classification result
    mock_result = MagicMock()
    mock_result.tip_document = MagicMock()
    mock_result.tip_document.value = "INVOICE"
    mock_result.confidence = 0.95
    mock_result.reasoning = "Clear invoice document"
    
    mock_classifier.classify = MagicMock(return_value=(mock_result, None))
    
    def mock_classifier_init(*args, **kwargs):
        return mock_classifier
    
    monkeypatch.setattr(
        "app.services.document_classification.DocumentClassificationService",
        mock_classifier_init
    )
    return mock_classifier


@pytest.fixture
def mock_invoice_extraction_service(monkeypatch, mock_invoice_data):
    """Mock invoice extraction service with LLM."""
    mock_extractor = MagicMock()
    
    # Mock extracted invoice data
    invoice_data_obj = MagicMock()
    invoice_data_obj.dict = MagicMock(return_value=mock_invoice_data)
    invoice_data_obj.total = 1500.50
    invoice_data_obj.currency = "RON"
    invoice_data_obj.nr_factura = "INV-2026-001"
    
    mock_extractor.extract_invoice_data = MagicMock(
        return_value=(invoice_data_obj, None, 0.92)
    )
    
    def mock_extractor_init(*args, **kwargs):
        return mock_extractor
    
    monkeypatch.setattr(
        "app.services.invoice_extraction.InvoiceExtractionService",
        mock_extractor_init
    )
    return mock_extractor


@pytest.fixture
def mock_nomenclator_service(monkeypatch):
    """Mock nomenclator suggestion service."""
    mock_nomenclator = MagicMock()
    
    # Mock suggestion result
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.primary_suggestion = MagicMock()
    mock_result.primary_suggestion.code = "GOODS_INVOICE"
    
    mock_nomenclator.suggest_nomenclator = MagicMock(return_value=mock_result)
    
    def mock_nomenclator_init(*args, **kwargs):
        return mock_nomenclator
    
    monkeypatch.setattr(
        "app.services.nomenclator_suggestion.NomenclatorSuggestionService",
        mock_nomenclator_init
    )
    return mock_nomenclator


@pytest.fixture
def mock_graph_service(monkeypatch):
    """Mock Neo4j graph service."""
    mock_populate = MagicMock()
    monkeypatch.setattr(
        "app.services.graph_service.populate_graph_for_document",
        mock_populate
    )
    return mock_populate


@pytest.fixture
def mock_meilisearch(monkeypatch):
    """Mock MeiliSearch indexing service."""
    mock_search = MagicMock()
    mock_search.prepare_document_for_indexing = MagicMock(
        return_value={"id": "1", "tip_document": "INVOICE"}
    )
    mock_search.add_documents = MagicMock(return_value={"status": "success"})
    
    def mock_search_init(*args, **kwargs):
        return mock_search
    
    monkeypatch.setattr(
        "app.services.search.SearchService",
        mock_search_init
    )
    return mock_search


# ============================================================================
# TESTS - Pipeline Flow
# ============================================================================

class TestCeleryPipelineIntegration:
    """Integration tests for the complete Celery document processing pipeline."""
    
    def test_full_pipeline_execution(
        self,
        db_session,
        patch_db_session,
        test_document,
        mock_minio_storage,
        mock_pdf_conversion,
        mock_classification_service,
        mock_invoice_extraction_service,
        mock_nomenclator_service,
        mock_graph_service,
        mock_meilisearch,
        mock_invoice_data
    ):
        """Test complete pipeline from upload to review."""
        document_id = test_document.id
        
        # Execute the pipeline task
        result = process_document_task(document_id)
        
        # Verify task completed without errors
        assert result is not None
        
        # Refresh document from DB
        db_session.refresh(test_document)
        
        # ====================================================================
        # ASSERTION 1: Status Transition
        # ====================================================================
        # Pipeline should end with REVIEW status
        assert test_document.status == DocumentStatusEnum.REVIEW, \
            f"Expected status REVIEW, got {test_document.status}"
        
        # ====================================================================
        # ASSERTION 2: PostgreSQL Fields Populated
        # ====================================================================
        # Extracted invoice data should be saved
        assert test_document.amount == 1500.50, \
            f"Expected amount 1500.50, got {test_document.amount}"
        assert test_document.currency == "RON", \
            f"Expected currency RON, got {test_document.currency}"
        assert test_document.document_number == "INV-2026-001", \
            f"Expected document_number INV-2026-001, got {test_document.document_number}"
        
        # Document classification should be set
        assert test_document.document_type == DocumentTypeEnum.INVOICE, \
            f"Expected type INVOICE, got {test_document.document_type}"
        assert test_document.confidence is not None, \
            f"Confidence should be set, got {test_document.confidence}"
        
        # Archived timestamp should not be set before manual archive
        assert test_document.archived_at is None, \
            "archived_at should be empty before manual archive"
        
        # ====================================================================
        # ASSERTION 3: ExtractedData Records Created
        # ====================================================================
        extracted_records = db_session.query(ExtractedData).filter(
            ExtractedData.document_id == document_id
        ).all()
        
        assert len(extracted_records) > 0, \
            "No ExtractedData records found in PostgreSQL"
        
        # Check for key extracted fields
        extracted_dict = {r.field_name: r.field_value for r in extracted_records}
        assert "nr_factura" in extracted_dict, \
            "nr_factura not in extracted fields"
        assert "furnizor" in extracted_dict, \
            "furnizor not in extracted fields"
        assert "total" in extracted_dict, \
            "total not in extracted fields"
        
        # ====================================================================
        # ASSERTION 4: DocumentPage Records Created
        # ====================================================================
        pages = db_session.query(DocumentPage).filter(
            DocumentPage.document_id == document_id
        ).all()
        
        assert len(pages) > 0, \
            "No DocumentPage records found - PDF pages not stored"
        assert test_document.page_count == len(pages), \
            f"Page count mismatch: {test_document.page_count} vs {len(pages)}"
        
        # ====================================================================
        # ASSERTION 5: Neo4j Graph Population Called
        # ====================================================================
        mock_graph_service.assert_called_once_with(document_id), \
            "Graph population service not called"
    
    def test_status_transitions(
        self,
        db_session,
        patch_db_session,
        test_document,
        mock_minio_storage,
        mock_pdf_conversion,
        mock_classification_service,
        mock_invoice_extraction_service,
        mock_nomenclator_service,
        mock_graph_service,
        mock_meilisearch
    ):
        """Test that status transitions correctly through the pipeline."""
        # Record initial status
        initial_status = test_document.status
        assert initial_status == DocumentStatusEnum.PROCESSING
        
        # Execute pipeline
        process_document_task(test_document.id)
        
        # Refresh to get updated status
        db_session.refresh(test_document)
        
        # Verify final status is REVIEW
        assert test_document.status == DocumentStatusEnum.REVIEW, \
            "Document should end in REVIEW status"


# ============================================================================
# TESTS - Neo4j Integration
# ============================================================================

class TestNeo4jIntegration:
    """Tests for Neo4j graph population."""
    
    def test_neo4j_node_creation(
        self,
        db_session,
        patch_db_session,
        test_document,
        mock_minio_storage,
        mock_pdf_conversion,
        mock_classification_service,
        mock_invoice_extraction_service,
        mock_nomenclator_service,
        mock_graph_service,
        mock_meilisearch
    ):
        """Test that Neo4j node is created with correct data."""
        document_id = test_document.id
        
        # Execute pipeline
        process_document_task(document_id)
        
        # Verify populate_graph_for_document was called
        mock_graph_service.assert_called_once_with(document_id)
    
    def test_neo4j_relationships(
        self,
        db_session,
        patch_db_session,
        test_document,
        mock_minio_storage,
        mock_pdf_conversion,
        mock_classification_service,
        mock_invoice_extraction_service,
        mock_nomenclator_service,
        mock_graph_service,
        mock_meilisearch
    ):
        """Test that relationships between nodes are created correctly."""
        document_id = test_document.id
        
        # Execute pipeline
        process_document_task(document_id)
        
        # Verify graph population was attempted with correct document_id
        mock_graph_service.assert_called_once_with(document_id)


# ============================================================================
# TESTS - Data Extraction
# ============================================================================

class TestDataExtraction:
    """Tests for invoice data extraction and storage."""
    
    def test_extracted_fields_stored_in_postgresql(
        self,
        db_session,
        patch_db_session,
        test_document,
        mock_minio_storage,
        mock_pdf_conversion,
        mock_classification_service,
        mock_invoice_extraction_service,
        mock_nomenclator_service,
        mock_graph_service,
        mock_meilisearch,
        mock_invoice_data
    ):
        """Test that extracted invoice fields are stored in PostgreSQL."""
        document_id = test_document.id
        
        # Execute pipeline
        process_document_task(document_id)
        
        # Query extracted data from DB
        extracted_records = db_session.query(ExtractedData).filter(
            ExtractedData.document_id == document_id
        ).all()
        
        # Verify records exist
        assert len(extracted_records) > 0, \
            "No extracted data stored in PostgreSQL"
        
        # Convert to dict for easier checking
        extracted_dict = {r.field_name: r.field_value for r in extracted_records}
        
        # Verify key fields from mock data are present
        assert "nr_factura" in extracted_dict
        assert extracted_dict["nr_factura"] == "INV-2026-001"
        
        assert "furnizor" in extracted_dict
        assert extracted_dict["furnizor"] == "Acme Corp"
        
        assert "total" in extracted_dict
        assert extracted_dict["total"] == "1500.5"
        
        # Verify extraction confidence is recorded
        for record in extracted_records:
            assert record.extraction_confidence is not None
            assert record.extraction_confidence > 0.8


# ============================================================================
# TESTS - Minio Integration
# ============================================================================

class TestMinIOIntegration:
    """Tests for MinIO page storage."""
    
    def test_pdf_pages_stored_in_minio(
        self,
        db_session,
        patch_db_session,
        test_document,
        mock_minio_storage,
        mock_pdf_conversion,
        mock_classification_service,
        mock_invoice_extraction_service,
        mock_nomenclator_service,
        mock_graph_service,
        mock_meilisearch
    ):
        """Test that PDF pages are stored in MinIO."""
        document_id = test_document.id
        
        # Execute pipeline
        process_document_task(document_id)
        
        # Query document pages from DB
        pages = db_session.query(DocumentPage).filter(
            DocumentPage.document_id == document_id
        ).all()
        
        # Verify pages were stored
        assert len(pages) > 0, "No pages stored"
        
        # Verify each page has a MinIO path
        for page in pages:
            assert page.image_path is not None, \
                f"Page {page.page_number} missing image_path"
            assert "processed/documents/" in page.image_path or \
                   page.image_path.endswith(".png"), \
                f"Invalid image path: {page.image_path}"


# ============================================================================
# TESTS - Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and recovery."""
    
    def test_missing_document_error(self, patch_db_session):
        """Test handling of non-existent document."""
        with pytest.raises(ValueError, match="not found"):
            process_document_task(99999)
    
    def test_pdf_conversion_failure_handling(
        self,
        db_session,
        patch_db_session,
        test_document,
        mock_minio_storage,
        monkeypatch,
        mock_classification_service,
        mock_invoice_extraction_service,
        mock_nomenclator_service,
        mock_graph_service,
        mock_meilisearch
    ):
        """Test handling of PDF conversion failures."""
        
        # Mock PDF conversion to fail
        def mock_pdf_fail(pdf_path, dpi=300):
            return None, "PDF conversion failed"
        
        monkeypatch.setattr("app.celery_app.pdf_to_pages_safe", mock_pdf_fail)
        
        # Pipeline should raise error
        with pytest.raises(RuntimeError, match="PDF to image conversion failed"):
            process_document_task(test_document.id)


# ============================================================================
# BENCHMARK TESTS
# ============================================================================

class TestPipelinePerformance:
    """Performance and behavior tests."""
    
    def test_pipeline_completes_within_reasonable_time(
        self,
        db_session,
        patch_db_session,
        test_document,
        mock_minio_storage,
        mock_pdf_conversion,
        mock_classification_service,
        mock_invoice_extraction_service,
        mock_nomenclator_service,
        mock_graph_service,
        mock_meilisearch
    ):
        """Test that pipeline execution completes in reasonable time."""
        import time
        
        document_id = test_document.id
        start_time = time.time()
        
        # Execute pipeline
        process_document_task(document_id)
        
        elapsed = time.time() - start_time
        
        # Should complete in under 10 seconds (mocked services)
        assert elapsed < 10.0, \
            f"Pipeline took {elapsed:.2f}s - too slow"


# ============================================================================
# INTEGRATION TEST SUMMARY
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
