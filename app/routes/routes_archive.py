from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.dependencies.security import RBACRole, require_roles

router = APIRouter(prefix="/archive", tags=["Archive"])

@router.get("/")
async def list_archived(_=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR))):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.post("/")
async def archive_document(_=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR))):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.get("/{archive_id}")
async def get_archived(
    archive_id: int,
    _=Depends(require_roles(RBACRole.ADMIN, RBACRole.OPERATOR, RBACRole.AUDITOR)),
):
    return JSONResponse({"detail": "not implemented"}, status_code=501)

@router.delete("/{archive_id}")
async def delete_archived(archive_id: int, _=Depends(require_roles(RBACRole.ADMIN))):
    return JSONResponse({"detail": "not implemented"}, status_code=501)