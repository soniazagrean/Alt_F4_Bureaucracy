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
            
            # Define filterable attributes for faceting and filtering
            index.update_filterable_attributes([
                'status',
                'type',
                'created_at',
                'tags'
            ])
            
            # Define sortable attributes
            index.update_sortable_attributes([
                'created_at',
                'updated_at'
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

# Create a single instance to reuse
search_service = SearchService()
