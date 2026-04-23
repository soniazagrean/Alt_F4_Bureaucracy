from minio import Minio
from app.config import settings
import io
import re

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

    def get_presigned_url(self, bucket_name: str, object_name: str, expires_minutes: int = 15):
        """
        Generate presigned URL that works from browser (replaces docker hostname with localhost)
        """
        from datetime import timedelta
        url = self.client.presigned_get_object(
            bucket_name,
            object_name,
            expires=timedelta(minutes=expires_minutes),
        )
        # Replace docker hostname with localhost for browser access
        # Handle both http://minio:9000 and minio:9000 formats
        url = url.replace("http://minio:9000", "http://localhost:9000")
        url = url.replace("minio:9000", "http://localhost:9000")
        return url

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

    def download_file(self, object_path: str, file_path: str) -> None:
        """Downloads a MinIO object (bucket/object) to a local path."""
        bucket_name, object_name = object_path.split("/", 1)
        response = self.client.get_object(bucket_name, object_name)
        try:
            with open(file_path, "wb") as handle:
                for chunk in response.stream(amt=1024 * 1024):
                    handle.write(chunk)
        finally:
            response.close()
            response.release_conn()

# Create a single instance to reuse
storage = StorageService()
