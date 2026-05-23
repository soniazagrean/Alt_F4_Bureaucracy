from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.security import get_current_user_context
from app.db.database import get_db
from app.schemas_auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
    TwoFADisableRequest,
    TwoFAEnableRequest,
    TwoFASetupResponse,
    TwoFAVerifyRequest,
    UserMeResponse,
)
from app.services.auth import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


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


@router.post("/login")
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Step-1 login.  Returns either:
    - ``{"requires_2fa": false, access_token, refresh_token, …}``  – normal login
    - ``{"requires_2fa": true, "partial_token": "…"}``             – needs TOTP verification
    """
    user = auth_service.authenticate_user(db, payload.username, payload.password)
    if user.totp_enabled:
        partial = auth_service.create_partial_token(user)
        return {"requires_2fa": True, "partial_token": partial}
    tokens = auth_service.create_token_pair(user)
    return {"requires_2fa": False, **tokens}


@router.post("/2fa/verify", response_model=TokenPairResponse)
async def verify_2fa(payload: TwoFAVerifyRequest, db: Session = Depends(get_db)):
    """Step-2 login: exchange a partial token + 6-digit TOTP code for a full token pair."""
    user = auth_service.verify_partial_token(db, payload.partial_token)
    if not auth_service.verify_totp(user, payload.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired TOTP code.",
        )
    return auth_service.create_token_pair(user)


@router.get("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(context=Depends(get_current_user_context)):
    """
    Generate a fresh TOTP secret + QR code for the authenticated user.
    Call this to display the setup screen; then call /2fa/enable once the
    user has scanned and confirmed with a code.
    """
    return auth_service.generate_2fa_setup(context.user)


@router.post("/2fa/enable")
async def enable_2fa(
    payload: TwoFAEnableRequest,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Enable 2FA: provide the secret (from /2fa/setup) + the first valid code."""
    auth_service.enable_2fa(context.user, db, payload.secret, payload.code)
    return {"detail": "2FA enabled successfully."}


@router.post("/2fa/disable")
async def disable_2fa(
    payload: TwoFADisableRequest,
    context=Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Disable 2FA: verify current code before removing."""
    auth_service.disable_2fa(context.user, db, payload.code)
    return {"detail": "2FA disabled successfully."}


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return auth_service.rotate_refresh_token(db, payload.refresh_token)


@router.post("/logout")
async def logout(payload: LogoutRequest):
    auth_service.revoke_refresh_token(payload.refresh_token)
    return {"detail": "Refresh token revoked"}


@router.get("/me", response_model=UserMeResponse)
async def me(
    context=Depends(get_current_user_context),
):
    user = context.user
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "rbac_role": context.rbac_role.value,
        "is_active": user.is_active,
        "totp_enabled": bool(user.totp_enabled),
        "created_at": user.created_at,
    }