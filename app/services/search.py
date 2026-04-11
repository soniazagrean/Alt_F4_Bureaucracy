from meilisearch import Client
from app.config import settings

class SearchService:
    def __init__(self):
        self.client = Client(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
        self.index_name = "documents"

    def ensure_index_exists(self):
        """Creates the index if it doesn't exist and configures settings."""
        try:
            # Check if index exists
            try:
                self.client.get_index(self.index_name)
                print(f"Search: Index '{self.index_name}' already exists.")
            except Exception:
                # Create index if not found
                self.client.create_index(self.index_name, {'primaryKey': 'id'})
                print(f"Search: Index '{self.index_name}' created.")

            # Configure index settings (filterable attributes, sortable attributes, etc.)
            index = self.client.index(self.index_name)
            
            # Define filterable attributes for faceting and filtering (NV-020)
            # Based on task requirements: tip_document, status, data
            index.update_filterable_attributes([
                'tip_document',
                'status',
                'data',
                'cod_nomenclator'
            ])
            
            # Define sortable attributes
            index.update_sortable_attributes([
                'created_at',
                'updated_at',
                'data'
            ])
            
            # Define searchable attributes
            index.update_searchable_attributes([
                'tip_document',
                'furnizor',
                'nr_factura',
                'cod_nomenclator',
                'title',
                'description'
            ])

            print(f"Search: Index '{self.index_name}' configured.")
            
        except Exception as e:
            print(f"Search Error: {e}")

    def add_documents(self, documents: list):
        """Adds or updates documents in the index."""
        try:
            index = self.client.index(self.index_name)
            task = index.add_documents(documents)
            return task
        except Exception as e:
            print(f"Search Add Error: {e}")
            raise e

    def search(self, query: str, params: dict = None):
        """Searches for documents."""
        try:
            index = self.client.index(self.index_name)
            return index.search(query, params)
        except Exception as e:
            print(f"Search Query Error: {e}")
            raise e

    def delete_document(self, document_id: str):
        """Deletes a document from the index."""
        try:
            index = self.client.index(self.index_name)
            return index.delete_document(document_id)
        except Exception as e:
            print(f"Search Delete Error: {e}")
            raise e

    def health_check(self):
        """Checks connection to Meilisearch."""
        try:
            return self.client.health()
        except Exception as e:
            print(f"Search Health Check Failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    @staticmethod
    def prepare_document_for_indexing(document_obj, extracted_data_dict: dict = None):
        """
        Prepare a Document object for indexing in MeiliSearch.
        
        Args:
            document_obj: SQLAlchemy Document instance
            extracted_data_dict: Dict of extracted fields {field_name: field_value}
            
        Returns:
            Dict formatted for MeiliSearch indexing with fields:
            - id, title, description
            - tip_document, status
            - furnizor, nr_factura (from extracted data)
            - cod_nomenclator
            - data (document_date as ISO string)
            - amount, currency
            - created_at, updated_at
        """
        extracted = extracted_data_dict or {}
        
        return {
            'id': str(document_obj.id),
            'title': document_obj.title or '',
            'description': document_obj.description or '',
            'tip_document': document_obj.document_type.value if document_obj.document_type else 'other',
            'status': document_obj.status.value if document_obj.status else 'pending',
            'furnizor': extracted.get('furnizor', ''),
            'nr_factura': extracted.get('nr_factura', '') or document_obj.document_number or '',
            'cod_nomenclator': extracted.get('cod_nomenclator', ''),
            'data': document_obj.document_date.isoformat() if document_obj.document_date else document_obj.created_at.isoformat(),
            'amount': float(document_obj.amount) if document_obj.amount else 0.0,
            'currency': document_obj.currency or 'RON',
            'created_at': document_obj.created_at.isoformat() if document_obj.created_at else '',
            'updated_at': document_obj.updated_at.isoformat() if document_obj.updated_at else '',
        }

# Create a single instance to reuse
search_service = SearchService()
