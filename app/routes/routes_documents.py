from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.get("/")
async def list_documents():
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.post("/")
async def create_document():
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.get("/{document_id}")
async def get_document(document_id: int):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.put("/{document_id}")
async def update_document(document_id: int):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.delete("/{document_id}")
async def delete_document(document_id: int):
    return JSONResponse({"detail": "not implemented"}, status_code=501)