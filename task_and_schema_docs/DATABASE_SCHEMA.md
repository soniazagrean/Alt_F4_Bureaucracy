# NexusVault v2 - Database Schema Documentation

## Overview

This document describes the PostgreSQL database schema for the NexusVault v2 document management and processing system.

## Tables

### 1. **users** - User Accounts & Access Control
- **Purpose**: Store user credentials and role information
- **Key Columns**:
  - `id` (PK): Unique user identifier
  - `username` (UNIQUE): Login username
  - `email` (UNIQUE): User email address
  - `hashed_password`: Bcrypt-hashed password
  - `role` (ENUM): User role (ADMIN, ARCHIVIST, INSPECTOR, VIEWER, SYSTEM)
  - `is_active`: Boolean flag for account status
  - `is_verified`: Boolean flag for email verification
  - `created_at`, `updated_at`: Timestamps

**Indexes**: username, email, id

**Relationships**:
- One-to-Many with `documents` (created_by_id)
- One-to-Many with `audit_logs` (user_id)
- One-to-Many with `fraud_alerts` (reviewed_by_id)

---

### 2. **nomenclator** - Document Classification Categories
- **Purpose**: Hierarchical classification system for document types
- **Key Columns**:
  - `id` (PK): Category ID
  - `code` (UNIQUE): Short code (e.g., "FIN-INV")
  - `name`: Category name
  - `description`: Long description
  - `parent_id` (FK): Parent category for hierarchy
  - `default_termen_pastrare` (ENUM): Default retention period
  - `is_active`: Active/inactive flag
  - `created_at`, `updated_at`: Timestamps

**Indexes**: code, parent_id, id

**Retention Periods**: 6_months, 1_year, 3_years, 5_years (default), 7_years, 10_years, permanent

**Relationships**:
- Self-referencing (parent_id)
- One-to-Many with `dosare`
- One-to-Many with `documents`

---

### 3. **dosare** - Archive Folders/Cases
- **Purpose**: Group related documents into logical folders
- **Key Columns**:
  - `id` (PK): Folder ID
  - `dosar_number` (UNIQUE): Reference number (e.g., "DOS-2026-001")
  - `title`: Folder title
  - `description`: Folder description
  - `nomenclator_id` (FK): Classification category
  - `termen_pastrare` (ENUM): Retention period
  - `is_active`: Status flag (1 = active, 0 = archived)
  - `created_at`, `updated_at`, `archived_at`: Timestamps

**Indexes**: dosar_number, id

**Relationships**:
- Many-to-One with `nomenclator`
- One-to-Many with `documents`

---

### 4. **documents** - Main Document Table
- **Purpose**: Store document metadata and processing status
- **Key Columns**:
  - `id` (PK): Document ID
  - `document_number` (UNIQUE): Unique document reference
  - `document_type` (ENUM): Type of document
  - `title`: Document title
  - `description`: Long description
  - `amount`: Monetary value (for financial docs)
  - `currency`: Currency code (default: RON)
  - `file_path`: MinIO storage path
  - `file_size`: Size in bytes
  - `mime_type`: MIME type (e.g., application/pdf)
  - `page_count`: Number of pages
  - `status` (ENUM): Processing status
  - `fraud_score`: 0-1 fraud detection score
  - `confidence`: 0-1 classification confidence
  - `dosar_id` (FK): Parent folder
  - `nomenclator_id` (FK): Classification category
  - `created_by_id` (FK): User who uploaded
  - `document_date`: When document was created
  - `created_at`, `updated_at`, `archived_at`: Timestamps

**Document Types**: invoice, contract, report, correspondence, decision, protocol, other

**Processing Status**: uploaded, processing, classified, extracted, validated, archived, rejected

**Indexes**: document_number, status, dosar_id, id

**Relationships**:
- Many-to-One with `users` (created_by_id)
- Many-to-One with `dosare`
- Many-to-One with `nomenclator`
- One-to-Many with `document_pages`
- One-to-Many with `extracted_data`
- One-to-Many with `audit_logs`
- One-to-Many with `fraud_alerts`

---

### 5. **document_pages** - Individual Document Pages
- **Purpose**: Store page-level information with OCR content
- **Key Columns**:
  - `id` (PK): Page ID
  - `document_id` (FK): Parent document
  - `page_number`: Page sequence number
  - `image_path`: MinIO path to page image
  - `text_content`: OCR extracted text
  - `created_at`: Timestamp

**Indexes**: document_id, id

**Relationships**:
- Many-to-One with `documents`

---

### 6. **extracted_data** - LLM-Extracted Information
- **Purpose**: Store structured data extracted from documents by LLM
- **Key Columns**:
  - `id` (PK): Extraction record ID
  - `document_id` (FK): Source document
  - `field_name`: Field identifier (e.g., "invoice_number")
  - `field_value`: Extracted value
  - `extraction_confidence`: 0-1 confidence score
  - `created_at`, `updated_at`: Timestamps

**Indexes**: document_id, id

**Relationships**:
- Many-to-One with `documents`

---

### 7. **audit_logs** - Compliance & Security Tracking
- **Purpose**: Immutable audit trail for all operations
- **Key Columns**:
  - `id` (PK): Log entry ID
  - `user_id` (FK): User performing action
  - `action` (ENUM): Type of action
  - `resource_type`: Object type (e.g., "document")
  - `resource_id`: Object ID
  - `description`: Human-readable description
  - `ip_address`: Client IP address
  - `changes` (JSON): Before/after data
  - `document_id` (FK): Related document (if any)
  - `created_at`: Timestamp (indexed for time-range queries)

**Actions Tracked**:
- create, read, update, delete
- download, upload
- classify, extract
- archive, restore
- login, logout
- permission_change

**Indexes**: user_id, action, resource_id, created_at, id

**Relationships**:
- Many-to-One with `users`
- Many-to-One with `documents`

---

### 8. **fraud_alerts** - Anomaly Detection Results
- **Purpose**: Store fraud/anomaly detection results
- **Key Columns**:
  - `id` (PK): Alert ID
  - `document_id` (FK): Flagged document
  - `anomaly_type` (ENUM): Type of anomaly (fraud, anomaly)
  - `severity`: Severity level (low, medium, high, critical)
  - `score`: 0-1 anomaly score
  - `description`: Alert description
  - `is_reviewed`: Status flag
  - `reviewed_by_id` (FK): User who reviewed
  - `reviewed_at`: Review timestamp
  - `created_at`: Detection timestamp

**Indexes**: document_id, id

**Relationships**:
- Many-to-One with `documents`
- Many-to-One with `users` (reviewed_by_id)

---

## Data Types & Constraints

### ENUM Types
```sql
-- User roles
CREATE TYPE RoleEnum AS ENUM ('ADMIN', 'ARCHIVIST', 'INSPECTOR', 'VIEWER', 'SYSTEM');

-- Retention periods
CREATE TYPE PastrareEnum AS ENUM ('6_months', '1_year', '3_years', '5_years', '7_years', '10_years', 'permanent');

-- Document status
CREATE TYPE DocumentStatusEnum AS ENUM ('uploaded', 'processing', 'classified', 'extracted', 'validated', 'archived', 'rejected');

-- Document types
CREATE TYPE DocumentTypeEnum AS ENUM ('invoice', 'contract', 'report', 'correspondence', 'decision', 'protocol', 'other');

-- Audit actions
CREATE TYPE AuditActionEnum AS ENUM ('create', 'read', 'update', 'delete', 'download', 'upload', 'classify', 'extract', 'archive', 'restore', 'login', 'logout', 'permission_change');

-- Anomaly types
CREATE TYPE AnomalyTypeEnum AS ENUM ('fraud', 'anomaly');
```

---

## Key Features

### 1. **Role-Based Access Control (RBAC)**
- 5 roles: ADMIN, ARCHIVIST, INSPECTOR, VIEWER, SYSTEM
- User role determines database operation permissions

### 2. **Hierarchical Classification**
- Nomenclator support for tree-like category structure
- Default retention periods per category
- Multiple inheritance paths through Dosar

### 3. **Document Lifecycle Management**
- Status tracking from upload to archival
- Automatic timestamp tracking
- Soft delete support via archived_at flag

### 4. **Comprehensive Audit Trail**
- All operations logged with user, timestamp, IP
- JSON storage for complex change tracking
- Time-indexed for efficient queries

### 5. **Fraud Detection Integration**
- Continuous anomaly detection scoring
- Alert severity classification
- Review workflow tracking

### 6. **OCR & Data Extraction**
- Per-page OCR text storage
- Field-level extracted data with confidence
- Ready for MeiliSearch full-text indexing

---

## Initialization & Seeding

Run the initialization script to create tables and seed default data:

```bash
python app/db/init_db.py
```

This creates:
- Admin user (username: admin, password: admin123)
- Root nomenclator entry
- Default category hierarchy (Financial, HR, Legal)

---

## Alembic Migrations

Create schema changes using Alembic:

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## Performance Considerations

### Indexes
- All FK relationships indexed
- Status columns indexed for filtering
- Created_at indexed on audit_logs for range queries
- Code/number fields indexed for lookups

### Query Optimization
- Consider pagination for large result sets
- Use status index for document filtering
- Use nomenclator parent_id for category traversal
- Limit audit_logs queries by date range

### Future Partitioning
Consider partitioning strategies:
- `documents` by created_at (monthly)
- `audit_logs` by created_at (monthly)
- `fraud_alerts` by created_at (quarterly)

---

## Security Notes

- Passwords stored as bcrypt hashes
- IP addresses logged for audit trail
- No sensitive data in extracteddata (only field values)
- Audit logs are immutable (no delete operations)
- All user actions trackable

