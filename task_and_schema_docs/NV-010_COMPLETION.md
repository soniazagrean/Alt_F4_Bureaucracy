# NV-010 — FastAPI Entry Point + Route Structure
 
**Status:** ✅ Completed  
**Date:** 2026-03-22
 
---
 
## Objective
 
Set up the FastAPI entry point and create skeleton route files for the three core domain areas: authentication, documents, and archive. Swagger UI must be functional at `/docs`.
 
---
 
## What Was Done
 
### New Files Created
 
| File | Prefix | Tags |
|---|---|---|
| `app/routes/routes_auth.py` | `/auth` | Auth |
| `app/routes/routes_documents.py` | `/documents` | Documents |
| `app/routes/routes_archive.py` | `/archive` | Archive |
 
### Endpoints Registered (Skeletons)
 
**Auth** (`/auth`)
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET  /auth/me`
 
**Documents** (`/documents`)
- `GET    /documents/`
- `POST   /documents/`
- `GET    /documents/{document_id}`
- `PUT    /documents/{document_id}`
- `DELETE /documents/{document_id}`
 
**Archive** (`/archive`)
- `GET    /archive/`
- `POST   /archive/`
- `GET    /archive/{archive_id}`
- `DELETE /archive/{archive_id}`
 
All endpoints return `{"detail": "not implemented"}` with HTTP `501` pending business logic implementation.
 
### `app/main.py` Changes
 
Three `include_router()` calls added at the bottom of `main.py`, consistent with the existing pattern used for `invoices_router` and `nomenclator_router`:
 
```python
from app.routes.routes_auth import router as auth_router
app.include_router(auth_router)
 
from app.routes.routes_documents import router as documents_router
app.include_router(documents_router)
 
from app.routes.routes_archive import router as archive_router
app.include_router(archive_router)
```
 
---
 
## Swagger UI
 
Accessible at `http://localhost:8000/docs`.  
All 5 route groups are visible as separate tagged sections:
 
- ✅ Auth
- ✅ Documents
- ✅ Archive
- ✅ Invoices *(pre-existing)*
- ✅ Nomenclator *(pre-existing)*
 
---
 
## Notes
 
- No business logic implemented — all new endpoints are stubs intentionally.
- Existing routes (`/invoices`, `/nomenclator`), lifespan handlers, and health/db endpoints were not modified.
- A Pylance `reportMissingImports` warning appeared in VS Code before the files were saved to disk — resolved automatically after "Restart Language Server".
 
---
