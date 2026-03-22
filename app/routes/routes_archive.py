from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/archive", tags=["Archive"])

@router.get("/")
async def list_archived():
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.post("/")
async def archive_document():
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.get("/{archive_id}")
async def get_archived(archive_id: int):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.delete("/{archive_id}")
async def delete_archived(archive_id: int):
    return JSONResponse({"detail": "not implemented"}, status_code=501)