# PostgreSQL Database Schema - Alt_F4_Bureaucracy

## Overview
This document describes the PostgreSQL database schema for the NexusVault v2 Document Management System.

## Tables

### 1. users
User accounts with role-based access control (RBAC).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | User ID |
| username | VARCHAR(255) | UNIQUE, NOT NULL | Login username |
| email | VARCHAR(255) | UNIQUE, NOT NULL | User email |
| full_name | VARCHAR(255) | | Full name |
| hashed_password | VARCHAR(255) | NOT NULL | Bcrypt hashed password |
| role | ENUM | NOT NULL | admin, archivist, inspector, viewer, system |
| is_active | BOOLEAN | DEFAULT=true | Account status |
| is_verified | BOOLEAN | DEFAULT=false | Email verification |
| created_at | TIMESTAMP | DEFAULT=NOW() | Creation time |
| updated_at | TIMESTAMP | DEFAULT=NOW() | Last update |

**Indexes:** username, email

---

### 2. documents
Core document entity with metadata and processing status.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Document ID |
| document_number | VARCHAR(255) | UNIQUE, NOT NULL | Unique document ID |
| document_type | ENUM | NOT NULL | invoice, contract, report, correspondence, decision, protocol, other |
| title | VARCHAR(511) | NOT NULL | Document title |
| description | TEXT | | Document description |
| amount | FLOAT | | Financial amount |
| currency | VARCHAR(3) | DEFAULT='RON' | Currency code |
| file_path | VARCHAR(511) | NOT NULL | MinIO storage path |
| file_size | INTEGER | | File size in bytes |
| mime_type | VARCHAR(100) | | File MIME type |
| page_count | INTEGER | | Number of pages |
| status | ENUM | NOT NULL | uploaded, processing, classified, extracted, validated, archived, rejected |
| fraud_score | FLOAT | DEFAULT=0.0 | Fraud confidence (0-1) |
| confidence | FLOAT | | Classification confidence (0-1) |
| dosar_id | INTEGER | FK | Parent archive folder |
| nomenclator_id | INTEGER | FK | Classification category |
| created_by_id | INTEGER | FK | Creator user |
| document_date | TIMESTAMP | | Document creation date |
| created_at | TIMESTAMP | DEFAULT=NOW() | Record creation |
| updated_at | TIMESTAMP | DEFAULT=NOW() | Last update |
| archived_at | TIMESTAMP | | Archive timestamp |

**Indexes:** document_number, status, dosar_id

**Foreign Keys:**
- `dosar_id` → dosare(id)
- `nomenclator_id` → nomenclator(id)
- `created_by_id` → users(id)

---

### 3. document_pages
Individual pages extracted from documents.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Page ID |
| document_id | INTEGER | FK, NOT NULL | Parent document |
| page_number | INTEGER | NOT NULL | Page sequence |
| image_path | VARCHAR(511) | NOT NULL | MinIO image path |
| text_content | TEXT | | OCR extracted text |
| created_at | TIMESTAMP | DEFAULT=NOW() | Creation time |

**Indexes:** document_id

**Foreign Keys:**
- `document_id` → documents(id) CASCADE DELETE

---

### 4. extracted_data
Data extracted by LLM from documents.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Entry ID |
| document_id | INTEGER | FK, NOT NULL | Source document |
| field_name | VARCHAR(255) | NOT NULL | Field identifier (e.g., invoice_number) |
| field_value | TEXT | NOT NULL | Extracted value |
| extraction_confidence | FLOAT | DEFAULT=1.0 | Confidence (0-1) |
| created_at | TIMESTAMP | DEFAULT=NOW() | Creation time |
| updated_at | TIMESTAMP | DEFAULT=NOW() | Last update |

**Indexes:** document_id

**Foreign Keys:**
- `document_id` → documents(id) CASCADE DELETE

---

### 5. nomenclator
Classification categories with hierarchical support.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Entry ID |
| code | VARCHAR(50) | UNIQUE, NOT NULL | Classification code |
| name | VARCHAR(255) | NOT NULL | Category name |
| description | TEXT | | Category description |
| parent_id | INTEGER | FK | Parent category (for hierarchy) |
| default_termen_pastrare | ENUM | NOT NULL | Default retention period |
| is_active | INTEGER | DEFAULT=1 | Soft delete flag |
| created_at | TIMESTAMP | DEFAULT=NOW() | Creation time |
| updated_at | TIMESTAMP | DEFAULT=NOW() | Last update |

**Indexes:** code, parent_id

**Foreign Keys:**
- `parent_id` → nomenclator(id)

---

### 6. dosare
Archive folders/cases containing documents.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Dosar ID |
| dosar_number | VARCHAR(255) | UNIQUE, NOT NULL | Folder number |
| title | VARCHAR(511) | NOT NULL | Folder title |
| description | TEXT | | Description |
| nomenclator_id | INTEGER | FK, NOT NULL | Classification |
| termen_pastrare | ENUM | NOT NULL | Retention period |
| is_active | INTEGER | DEFAULT=1 | Status flag |
| created_at | TIMESTAMP | DEFAULT=NOW() | Creation time |
| updated_at | TIMESTAMP | DEFAULT=NOW() | Last update |
| archived_at | TIMESTAMP | | Archive date |

**Indexes:** dosar_number

**Foreign Keys:**
- `nomenclator_id` → nomenclator(id)

---

### 7. audit_logs
Compliance audit trail.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Log entry ID |
| user_id | INTEGER | FK, NOT NULL | Acting user |
| action | ENUM | NOT NULL | create, read, update, delete, download, upload, classify, extract, archive, restore, login, logout, permission_change |
| resource_type | VARCHAR(100) | NOT NULL | Resource type (e.g., "document", "dosar") |
| resource_id | INTEGER | NOT NULL | Resource ID |
| description | TEXT | | Action description |
| ip_address | VARCHAR(45) | | IPv4/IPv6 address |
| changes | JSON | | Before/after changes |
| document_id | INTEGER | FK | Associated document |
| created_at | TIMESTAMP | DEFAULT=NOW() | Log timestamp |

**Indexes:** user_id, action, resource_type, resource_id, document_id, created_at

**Foreign Keys:**
- `user_id` → users(id)
- `document_id` → documents(id)

---

### 8. fraud_alerts
Fraud detection and anomaly alerts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PK, AUTO | Alert ID |
| document_id | INTEGER | FK, NOT NULL | Document with anomaly |
| anomaly_type | ENUM | NOT NULL | duplicate_document, forged_signature, tampered_data, invalid_amount, pattern_anomaly, missing_metadata, ocr_error, unknown |
| fraud_score | FLOAT | NOT NULL | Fraud confidence (0-1) |
| risk_level | VARCHAR(20) | NOT NULL | low, medium, high, critical |
| description | TEXT | NOT NULL | Alert description |
| is_resolved | INTEGER | DEFAULT=0 | Resolution status |
| resolution_notes | TEXT | | Resolution details |
| detected_at | TIMESTAMP | DEFAULT=NOW() | Detection time |
| resolved_at | TIMESTAMP | | Resolution time |

**Indexes:** document_id, detected_at

**Foreign Keys:**
- `document_id` → documents(id)

---

## Retention Periods (Enum)
```
- 6_months
- 1_year
- 3_years
- 5_years (default)
- 7_years
- 10_years
- permanent
```

## Document Status Flow
```
uploaded → processing → classified → extracted → validated → archived
                                                          ↓
                                                       rejected
```

## Retention Strategy
- Documents inherit retention period from their classification (nomenclator)
- Dosare have designated retention periods
- Automatic archival happens based on retention dates
- Soft deletion using `is_active` flag

## Data Relationships
```
User (1)
    ├── audit_logs (N)
    └── documents (N, created_by)

Document (1)
    ├── document_pages (N)
    ├── extracted_data (N)
    ├── audit_logs (N)
    ├── fraud_alerts (N)
    ├── dosar (1, parent)
    └── nomenclator (1, classification)

Dosar (1)
    ├── documents (N)
    └── nomenclator (1)

NomenclatorEntry (1)
    ├── documents (N)
    ├── dosare (N)
    └── children (N, hierarchical)
```

## Indexes Summary
For performance optimization:
- **users**: UNIQUE (username), UNIQUE (email)
- **documents**: UNIQUE (document_number), documents(status), documents(dosar_id)
- **document_pages**: documents(document_id)
- **extracted_data**: extracted_data(document_id)
- **nomenclator**: UNIQUE (code), nomenclator(parent_id)
- **dosare**: UNIQUE (dosar_number)
- **audit_logs**: audit_logs(user_id, action, resource_type, resource_id, document_id, created_at)
- **fraud_alerts**: fraud_alerts(document_id, detected_at)
