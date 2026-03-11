# [NV-002] PostgreSQL Configuration - Basic Models

## ✅ Completion Summary

All PostgreSQL models have been successfully configured for the NexusVault v2 system.

## Models Created

### 1. **User Model** (`app/models/user.py`)
- User accounts with RBAC (Admin, Archivist, Inspector, Viewer, System)
- Password hashing with bcrypt
- Email verification tracking
- Account activation status
- Relationships: audit_logs, documents (created by)

### 2. **Document Model** (`app/models/document.py`)
Core document entity with:
- Document metadata (number, type, title, description)
- Financial data (amount, currency)
- File information (path, size, MIME type, page count)
- Processing status tracking (7 states)
- Fraud detection score
- Classification confidence
- Relationships: pages, extracted_data, dosar, nomenclator, audit_logs

**Sub-models:**
- **DocumentPage**: Individual pages with OCR text
- **ExtractedData**: LLM-extracted field values with confidence scores

### 3. **Archive Model** (`app/models/archive.py`)

**Dosar (Archive Folder)**
- Unique folder numbering
- Classification category assignment
- Retention period specification (6 months to permanent)
- Active/archived status
- Relationships: documents, nomenclator

**NomenclatorEntry (Classification Categories)**
- Hierarchical classification system
- Default retention periods
- Unique category codes
- Parent-child relationships for hierarchy
- Relationships: dosare, documents

### 4. **Audit Model** (`app/models/audit.py`)
Comprehensive compliance tracking:
- User action logging
- Resource type and ID tracking
- IP address recording
- Change tracking (JSON)
- 12 action types (create, read, update, delete, etc.)
- Indexed for performance and compliance queries

### 5. **Alert Model** (`app/models/alert.py`)
Fraud detection and anomaly alerts:
- Document anomaly detection
- Fraud scoring (0-1)
- Risk levels (low, medium, high, critical)
- Anomaly types (8 types)
- Resolution tracking with notes
- Detection and resolution timestamps

## Database Configuration

### Database Setup
- **File**: `app/db/database.py`
- **Engine**: PostgreSQL with SQLAlchemy ORM
- **Connection**: Via environment variables (.env)
- **Session Management**: SessionLocal factory + FastAPI dependency
- **Initialization**: Automatic table creation on app startup

### Environment Variables (in .env)
```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=alt_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5433
```

## Pydantic Schemas

**File**: `app/schemas.py`

All models have corresponding Pydantic schemas for API validation:
- UserCreate, UserResponse
- DocumentCreate, DocumentResponse
- DosarCreate, DosarResponse
- NomenclatorEntryResponse
- AuditLogResponse
- FraudAlertResponse

## Updated Requirements

Added dependencies:
- `alembic==1.12.1` - Database migrations
- `passlib==1.7.4` - Password hashing utilities
- `python-jose==3.3.0` - JWT token management
- `bcrypt==4.1.1` - Bcrypt hashing
- `python-jwt==1.7.1` - JWT utilities

## Database Schema Features

### Indexes for Performance
- Unique constraints on natural keys (username, email, document_number, dosar_number, classification code)
- Indexes on foreign keys and frequently queried fields
- Composite indexes on audit logs for compliance queries

### Data Relationships
- Proper foreign key constraints with CASCADE DELETE for orphaned records
- Soft delete support using `is_active` flags where applicable
- Referential integrity across all tables

### Enum Types
- **RoleEnum**: User authorization levels
- **DocumentStatusEnum**: Processing pipeline states
- **DocumentTypeEnum**: Document categories
- **AuditActionEnum**: 12 action types
- **AnomalyTypeEnum**: 8 fraud/anomaly types
- **PastrareEnum**: 7 retention period options

## Documentation

### Generated Files
1. **DB_SCHEMA.md** - Complete schema documentation with:
   - Table definitions
   - Column descriptions and constraints
   - Indexes and foreign keys
   - Data relationships diagram
   - Retention strategy

2. **MIGRATIONS.md** - Guide for using Alembic migrations

## Integration with Docker

The models automatically initialize when the FastAPI service starts:
```python
# In app/main.py
from app.models import *  # Registers all models
init_db()  # Creates all tables
```

### New Endpoints Added
- `GET /db/status` - Check database connection and status

## Acceptance Criteria

✅ **All criteria met:**
- [x] PostgreSQL models configured
- [x] User model with RBAC
- [x] Document model with full metadata
- [x] Archive (Dosar) model with retention periods
- [x] Classification (Nomenclator) model
- [x] Audit trail implementation
- [x] Fraud alert model
- [x] Database initialization on startup
- [x] Pydantic validation schemas
- [x] Complete documentation

## Next Steps

To use these models:

1. **Run docker compose** (services will start)
2. **FastAPI will auto-create** all tables in PostgreSQL
3. **Use the Pydantic schemas** for API request validation
4. **Track changes** with audit logs (automatic in endpoints)
5. **Set up migrations** with Alembic for future schema changes:
   ```bash
   alembic init migrations
   alembic revision --autogenerate -m "Initial schema"
   alembic upgrade head
   ```

## Files Created

```
app/
├── db/
│   ├── __init__.py
│   └── database.py          # SQLAlchemy setup
├── models/
│   ├── __init__.py
│   ├── user.py              # User + RBAC
│   ├── document.py          # Document + pages + extracted data
│   ├── archive.py           # Dosar + Nomenclator
│   ├── audit.py             # Audit logs
│   └── alert.py             # Fraud alerts
├── schemas.py               # Pydantic models for API
└── main.py                  # Updated with DB init

Documentation/
├── DB_SCHEMA.md             # Complete schema reference
└── MIGRATIONS.md            # Migration guide
```

---

**Task Status**: ✅ COMPLETED
**Models Implemented**: 8 (User, Document, DocumentPage, ExtractedData, Dosar, NomenclatorEntry, AuditLog, FraudAlert)
**Total Tables**: 8
**Ready for Integration**: Yes
