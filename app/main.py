import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

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
