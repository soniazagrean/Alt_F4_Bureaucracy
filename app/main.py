import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.db.database import init_db, engine
from app.models import *  # Import all models to register them

# Initialize database tables on startup
init_db()

app = FastAPI(title="Alt_F4_Bureaucracy API", version="1.0.0")

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
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return JSONResponse({
            "status": "connected",
            "database": "PostgreSQL"
        })
    except Exception as e:
        return JSONResponse({
            "status": "disconnected",
            "error": str(e)
        }, status_code=503)

