from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas_auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
    UserMeResponse,
)
from app.services.auth import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])
security = HTTPBearer(auto_error=True)

@router.post("/register")
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register_user(
        db=db,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role=payload.role,
    )
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
    }

@router.post("/login", response_model=TokenPairResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, payload.username, payload.password)
    return auth_service.create_token_pair(user)

@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return auth_service.rotate_refresh_token(db, payload.refresh_token)

@router.post("/logout")
async def logout(payload: LogoutRequest):
    auth_service.revoke_refresh_token(payload.refresh_token)
    return {"detail": "Refresh token revoked"}


@router.get("/me", response_model=UserMeResponse)
async def me(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = auth_service.get_current_user_from_access_token(db, credentials.credentials)
    return user