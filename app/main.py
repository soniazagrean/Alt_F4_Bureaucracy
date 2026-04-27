import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.db.database import init_db, engine
from app.models import *  # Import all models to register them
from app.services.storage import StorageService
from app.services.search import SearchService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize services
    try:
        storage_service = StorageService()
        storage_service.ensure_buckets_exist()
        print("Storage buckets initialized.")
    except Exception as e:
        print(f"Warning: Could not initialize storage buckets: {e}")

    try:
        search_service = SearchService()
        search_service.ensure_index_exists()
        print("Search index initialized.")
    except Exception as e:
        print(f"Warning: Could not initialize search index: {e}")

    try:
        from app.db.neo4j import init_driver, init_constraints

        init_driver()
        init_constraints()
        print("Neo4j driver initialized and constraints ensured.")
    except Exception as e:
        print(f"Warning: Could not initialize Neo4j: {e}")
    
    yield

    try:
        from app.db.neo4j import close_driver

        close_driver()
        print("Neo4j driver closed.")
    except Exception as e:
        print(f"Warning: Could not close Neo4j driver: {e}")

app = FastAPI(title="Alt_F4_Bureaucracy API", version="1.0.0", lifespan=lifespan)

@app.get("/")
async def root():
    return JSONResponse({
        "message": "Alt_F4_Bureaucracy API",
        "status": "running"
    })

@app.get("/health")
async def health():
    return JSONResponse({
        "status": "healthy",
        "version": "1.0.0"
    })

@app.get("/db/status")
async def db_status():
    """Check database connection status"""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({
            "status": "connected",
            "database": "PostgreSQL"
        })
    except Exception as e:
        return JSONResponse({
            "status": "disconnected",
            "error": str(e)
        }, status_code=503)

# Include invoice extraction routes
from app.routes.invoices import router as invoices_router
app.include_router(invoices_router)

# Include nomenclator suggestion routes
from app.routes.nomenclator import router as nomenclator_router
app.include_router(nomenclator_router)

# Include auth routes
from app.routes.routes_auth import router as auth_router
app.include_router(auth_router)

# Include document detail CRUD router
from app.routes.routes_documents import router as documents_detail_router
app.include_router(documents_detail_router)

# Include export router
from app.routes.routes_export import router as export_router
app.include_router(export_router)

# Include archive router
from app.routes.routes_archive import router as archive_router
app.include_router(archive_router)

# Include audit trail router
from app.routes.audit_trail import router as audit_trail_router
app.include_router(audit_trail_router)
