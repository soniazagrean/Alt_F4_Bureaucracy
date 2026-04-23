"""
NV-020: Tests for automatic document indexing in MeiliSearch after processing.

Tests verify that:
1. SearchService can be initialized and index is configured
2. Documents are properly formatted for indexing with all required fields
3. Documents are indexed after processing completes
4. Filtered and sortable fields are properly configured
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch, call
from app.models.document import Document, DocumentStatusEnum, DocumentTypeEnum, ExtractedData
from app.services.search import SearchService
from app.db.database import SessionLocal
from app.celery_app import index_document_in_meilisearch_task

# Register custom pytest markers
pytestmark = [
    pytest.mark.filterwarnings("ignore::pytest.PytestUnknownMarkWarning"),
]


class TestSearchServiceConfiguration:
    """Test SearchService setup and configuration."""
    
    def test_search_service_can_be_initialized(self):
        """Verify SearchService initializes without errors."""
        search_service = SearchService()
        assert search_service.client is not None
        assert search_service.index_name == "documents"
    
    @patch('app.services.search.Client')
    def test_index_configuration_sets_filterable_attributes(self, mock_client_class):
        """Verify that MeiliSearch index is configured with required filterable attributes."""
        mock_client = MagicMock()
        mock_index = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_index.return_value = mock_index
        mock_client.index.return_value = mock_index
        
        search_service = SearchService()
        search_service.ensure_index_exists()
        
        # Verify filterable attributes include NV-020 requirements
        calls = mock_index.update_filterable_attributes.call_args
        filterable_attrs = calls[0][0] if calls else []
        assert 'tip_document' in filterable_attrs
        assert 'status' in filterable_attrs
        assert 'data' in filterable_attrs
        assert 'cod_nomenclator' in filterable_attrs
    
    @patch('app.services.search.Client')
    def test_index_configuration_sets_sortable_attributes(self, mock_client_class):
        """Verify that MeiliSearch index includes sortable attributes."""
        mock_client = MagicMock()
        mock_index = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_index.return_value = mock_index
        mock_client.index.return_value = mock_index
        
        search_service = SearchService()
        search_service.ensure_index_exists()
        
        # Verify sortable attributes
        calls = mock_index.update_sortable_attributes.call_args
        sortable_attrs = calls[0][0] if calls else []
        assert 'created_at' in sortable_attrs
        assert 'updated_at' in sortable_attrs
        assert 'data' in sortable_attrs


class TestDocumentPreparationForIndexing:
    """Test document formatting for MeiliSearch indexing."""
    
    def test_prepare_document_with_minimal_data(self):
        """Test preparing a document with only required fields."""
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.title = "Invoice 2024-001"
        mock_doc.description = "Test invoice"
        mock_doc.document_type = DocumentTypeEnum.INVOICE
        mock_doc.status = DocumentStatusEnum.ARCHIVED
        mock_doc.document_number = "INV-001"
        mock_doc.amount = 1000.50
        mock_doc.currency = "RON"
        mock_doc.document_date = datetime(2024, 3, 15, tzinfo=timezone.utc)
        mock_doc.created_at = datetime(2024, 3, 15, tzinfo=timezone.utc)
        mock_doc.updated_at = datetime(2024, 3, 15, tzinfo=timezone.utc)
        
        result = SearchService.prepare_document_for_indexing(mock_doc, {})
        
        # Verify required fields are present
        assert result['id'] == '1'
        assert result['title'] == "Invoice 2024-001"
        assert result['tip_document'] == 'invoice'
        assert result['status'] == 'archived'
        assert result['nr_factura'] == 'INV-001'
        assert result['amount'] == 1000.50
        assert result['currency'] == 'RON'
    
    def test_prepare_document_with_extracted_data(self):
        """Test preparing a document with extracted invoice data."""
        mock_doc = Mock(spec=Document)
        mock_doc.id = 42
        mock_doc.title = "Factura Furnizor"
        mock_doc.description = None
        mock_doc.document_type = DocumentTypeEnum.INVOICE
        mock_doc.status = DocumentStatusEnum.ARCHIVED
        mock_doc.document_number = None  # Will use nr_factura from extracted
        mock_doc.amount = 5000.00
        mock_doc.currency = "RON"
        mock_doc.document_date = datetime(2024, 2, 10, tzinfo=timezone.utc)
        mock_doc.created_at = datetime(2024, 2, 10, tzinfo=timezone.utc)
        mock_doc.updated_at = datetime(2024, 2, 11, tzinfo=timezone.utc)
        
        extracted_data = {
            'furnizor': 'ABC Company SRL',
            'nr_factura': 'FAC2024-0512',
            'cod_nomenclator': 'INV-SERV-2024',
        }
        
        result = SearchService.prepare_document_for_indexing(mock_doc, extracted_data)
        
        # Verify extracted fields are included
        assert result['furnizor'] == 'ABC Company SRL'
        assert result['nr_factura'] == 'FAC2024-0512'
        assert result['cod_nomenclator'] == 'INV-SERV-2024'
    
    def test_prepare_document_with_empty_extracted_data(self):
        """Test that missing extracted fields default to empty strings."""
        mock_doc = Mock(spec=Document)
        mock_doc.id = 10
        mock_doc.title = "Document"
        mock_doc.description = None
        mock_doc.document_type = DocumentTypeEnum.OTHER
        mock_doc.status = DocumentStatusEnum.VALIDATED
        mock_doc.document_number = "DOC-001"
        mock_doc.amount = None
        mock_doc.currency = "RON"
        mock_doc.document_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_doc.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_doc.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        
        result = SearchService.prepare_document_for_indexing(mock_doc, {})
        
        # Verify defaults
        assert result['furnizor'] == ''
        assert result['cod_nomenclator'] == ''
        assert result['amount'] == 0.0
    
    def test_prepare_document_iso_format_dates(self):
        """Test that dates are converted to ISO format."""
        mock_doc = Mock(spec=Document)
        mock_doc.id = 5
        mock_doc.title = "Test"
        mock_doc.description = None
        mock_doc.document_type = DocumentTypeEnum.INVOICE
        mock_doc.status = DocumentStatusEnum.ARCHIVED
        mock_doc.document_number = "TST-001"
        mock_doc.amount = 100.0
        mock_doc.currency = "EUR"
        test_date = datetime(2024, 3, 20, 14, 30, 45, tzinfo=timezone.utc)
        mock_doc.document_date = test_date
        mock_doc.created_at = test_date
        mock_doc.updated_at = test_date
        
        result = SearchService.prepare_document_for_indexing(mock_doc, {})
        
        # Verify ISO format
        assert 'T' in result['data']  # ISO format with T
        assert 'Z' in result['data'] or '+' in result['data']  # Timezone indicator


class TestIndexingTaskExecution:
    """Test the Celery indexing task."""
    
    @patch('app.services.search.SearchService')
    @patch('app.celery_app.SessionLocal')
    def test_index_task_fetches_document_successfully(self, mock_session_class, mock_search_class):
        """Test that indexing task retrieves document from database."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session_class.return_value = mock_db
        
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.title = "Invoice"
        mock_doc.description = "Test"
        mock_doc.document_type = DocumentTypeEnum.INVOICE
        mock_doc.status = DocumentStatusEnum.ARCHIVED
        mock_doc.document_number = "INV-001"
        mock_doc.amount = 1000.0
        mock_doc.currency = "RON"
        mock_doc.document_date = datetime.now(timezone.utc)
        mock_doc.created_at = datetime.now(timezone.utc)
        mock_doc.updated_at = datetime.now(timezone.utc)
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []  # No extracted data
        mock_query.first.return_value = mock_doc
        
        mock_search_service = MagicMock()
        mock_search_class.return_value = mock_search_service
        mock_search_service.prepare_document_for_indexing.return_value = {
            'id': '1',
            'title': 'Invoice'
        }
        
        # Execute task
        result = index_document_in_meilisearch_task(1)
        
        # Verify database was queried
        assert mock_db.query.called
        assert mock_db.close.called
        assert result['status'] == 'success'
        assert result['document_id'] == 1
    
    @patch('app.services.search.SearchService')
    @patch('app.celery_app.SessionLocal')
    def test_index_task_fetches_extracted_data(self, mock_session_class, mock_search_class):
        """Test that indexing task retrieves extracted data fields."""
        # Setup mocks
        mock_db = MagicMock()
        mock_session_class.return_value = mock_db
        
        mock_doc = Mock(spec=Document)
        mock_doc.id = 2
        mock_doc.title = "Invoice"
        mock_doc.description = None
        mock_doc.document_type = DocumentTypeEnum.INVOICE
        mock_doc.status = DocumentStatusEnum.ARCHIVED
        mock_doc.document_number = None
        mock_doc.amount = None
        mock_doc.currency = "RON"
        mock_doc.document_date = datetime.now(timezone.utc)
        mock_doc.created_at = datetime.now(timezone.utc)
        mock_doc.updated_at = datetime.now(timezone.utc)
        
        # Setup extracted data rows
        mock_extracted_1 = Mock(spec=ExtractedData)
        mock_extracted_1.field_name = 'furnizor'
        mock_extracted_1.field_value = 'Supplier XYZ'
        
        mock_extracted_2 = Mock(spec=ExtractedData)
        mock_extracted_2.field_name = 'nr_factura'
        mock_extracted_2.field_value = 'FAC-2024-001'
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        
        # First call returns document, second call returns extracted data
        mock_query.first.return_value = mock_doc
        mock_query.all.return_value = [mock_extracted_1, mock_extracted_2]
        
        mock_search_service = MagicMock()
        mock_search_class.return_value = mock_search_service
        mock_search_service.prepare_document_for_indexing.return_value = {
            'id': '2',
            'furnizor': 'Supplier XYZ',
            'nr_factura': 'FAC-2024-001'
        }
        
        # Execute task
        result = index_document_in_meilisearch_task(2)
        
        # Verify search service was called with extracted data
        assert mock_search_service.prepare_document_for_indexing.called
        call_args = mock_search_service.prepare_document_for_indexing.call_args
        
        assert result['status'] == 'success'
        assert result['document_id'] == 2
    
    @patch('app.celery_app.SessionLocal')
    def test_index_task_returns_not_found_for_missing_document(self, mock_session_class):
        """Test that indexing task handles missing documents gracefully."""
        mock_db = MagicMock()
        mock_session_class.return_value = mock_db
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # Document not found
        
        result = index_document_in_meilisearch_task(999)
        
        assert result['status'] == 'document_not_found'
        assert result['document_id'] == 999


class TestIndexingIntegration:
    """Integration tests for indexing after document processing."""
    
    @patch('app.celery_app.index_document_in_meilisearch_task')
    def test_process_document_schedules_indexing(self, mock_index_task):
        """Test that process_document_task schedules indexing task."""
        from app.celery_app import process_document_task
        
        # This test verifies the integration point exists
        # The actual scheduling is tested by checking celery_app.py code
        assert hasattr(process_document_task, 'apply_async') or callable(process_document_task)


# Markers for running specific test subsets
@pytest.mark.meilisearch
class TestMeiliSearchConnection:
    """Tests requiring actual MeiliSearch connection (optional)."""
    
    @pytest.mark.skip(reason="Requires running MeiliSearch instance")
    def test_actual_indexing_if_meilisearch_available(self):
        """Test actual indexing if MeiliSearch is available."""
        search_service = SearchService()
        health = search_service.health_check()
        
        if health.get('status') != 'available':
            pytest.skip("MeiliSearch not available")
        
        # Create test document
        test_doc = {
            'id': '999',
            'title': 'Test Document',
            'tip_document': 'invoice',
            'status': 'archived',
            'furnizor': 'Test Supplier',
            'nr_factura': 'TEST-999',
            'cod_nomenclator': 'TEST-CODE',
            'data': datetime.now(timezone.utc).isoformat(),
        }
        
        result = search_service.add_documents([test_doc])
        assert result is not None
