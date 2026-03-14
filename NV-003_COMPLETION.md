# [NV-003] Configure MinIO (Object Storage)

## ✅ Completion Summary

MinIO object storage has been successfully configured and integrated into the application infrastructure.

## Components Configured

### 1. **Docker Service** (`docker-compose.yml`)

- **Image**: `minio/minio:latest`
- **Ports**:
  - API: `9000`
  - Console: `9001`
- **Persistence**: `minio_data` volume
- **Credentials**: Managed via `.env` files

### 2. **Configuration** (`app/config.py`)

- Pydantic settings for secure connection management
- Automatic credential fallback logic (root user/pass as default)
- Environment-aware endpoint configuration (localhost vs docker service name)

### 3. **Service Layer** (`app/services/storage.py`)

**StorageService Class**:

- **Bucket Management**: Automatic creation of required buckets on startup
- **Upload Logic**:
  - `upload_file`: Stream-based upload
  - `upload_from_path`: File-path based upload
- **Security**: Endpoint sanitization (stripping protocol prefixes)

## Validated Resources

The following buckets are automatically created and ready for use:

- `uploads`: Raw document ingestion
- `processed`: Cleaned/OCR'd documents
- `quarantine`: Potentially malicious files

## Verification

- Connection test via `test_all_services.py`: **PASSED**
- Service startup check in `app/main.py`: **PASSED**
