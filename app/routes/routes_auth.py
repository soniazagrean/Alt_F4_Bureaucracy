from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register")
async def register():
    return JSONResponse({"detail" : "not implemented"}, status_code=501)

@router.post("/login")
async def login():
    return JSONResponse({"detail" : "not implemented"}, status_code=501)

@router.post("/logout")
async def login():
    return JSONResponse({"detail" : "not implemented"}, status_code=501)

@router.post("/me")
async def login():
    return JSONResponse({"detail" : "not implemented"}, status_code=501)