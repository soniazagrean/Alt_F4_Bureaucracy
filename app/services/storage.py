from minio import Minio
from app.config import settings
import io

class StorageService:
    def __init__(self):
        self.client = Minio(
            endpoint = settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        
        # Define buckets
        self.buckets = {
            "uploads": "uploads",
            "processed": "processed",
            "quarantine": "quarantine"
        }

    def ensure_buckets_exist(self):
        """Creates all required buckets if they don't exist yet."""
        for key, bucket_name in self.buckets.items():
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                print(f"Storage: Bucket '{bucket_name}' created.")
            else:
                print(f"Storage: Bucket '{bucket_name}' already exists.")

    def upload_file(self, file_data: bytes, file_name: str, bucket_key: str = "uploads", content_type: str = "application/octet-stream"):
        """
        Uploads bytes data to the specified bucket.
        bucket_key options: 'uploads', 'processed', 'quarantine'
        """
        if bucket_key not in self.buckets:
            raise ValueError(f"Invalid bucket key. expanding: {list(self.buckets.keys())}")
            
        bucket_name = self.buckets[bucket_key]
        
        # Ensure bucket exists
        if not self.client.bucket_exists(bucket_name):
            self.client.make_bucket(bucket_name)

        # MinIO expects a stream
        data_stream = io.BytesIO(file_data)
        length = len(file_data)
        
        self.client.put_object(
            bucket_name=bucket_name,
            object_name=file_name,
            data=data_stream,
            length=length,
            content_type=content_type
        )
        return f"{bucket_name}/{file_name}"

    def upload_from_path(self, file_path: str, object_name: str, bucket_key: str = "uploads"):
        """Uploads a file from disk to the specified bucket."""
        if bucket_key not in self.buckets:
             raise ValueError(f"Invalid bucket key. Options: {list(self.buckets.keys())}")
             
        bucket_name = self.buckets[bucket_key]
        if not self.client.bucket_exists(bucket_name):
            self.client.make_bucket(bucket_name)
            
        self.client.fput_object(
            bucket_name=bucket_name,
            object_name=object_name,
            file_path=file_path
        )
        return f"{bucket_name}/{object_name}"

# Create a single instance to reuse
storage = StorageService()
