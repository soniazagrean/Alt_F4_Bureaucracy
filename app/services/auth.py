from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import uuid4

import jwt
import redis
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import RoleEnum, User


class AuthService:
    def __init__(self):
        self._redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        # Fallback store used when Redis is unavailable.
        self._fallback_store: Dict[str, str] = {}

    def register_user(
        self,
        db: Session,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str],
        role,
    ) -> User:
        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already in use")

        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

        role_value = role.value if hasattr(role, "value") else str(role)
        try:
            db_role = RoleEnum(role_value)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

        # Keep PK sequence aligned with table state (common after manual inserts/seeds).
        self._resync_user_id_sequence(db)

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            role=db_role,
            is_active=True,
            is_verified=True,
        )
        user.set_password(password)

        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            detail = str(exc.orig)

            if "users_username_key" in detail:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already in use")
            if "users_email_key" in detail:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

            # If sequence drift still happened under concurrency, retry once.
            if "users_pkey" in detail:
                self._resync_user_id_sequence(db)
                db.add(user)
                db.commit()
            else:
                raise

        db.refresh(user)
        return user

    # Lockout policy constants
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15

    def authenticate_user(self, db: Session, username: str, password: str) -> User:
        now = datetime.now(timezone.utc)

        user = db.query(User).filter(User.username == username).first()

        # ── Lockout check ──────────────────────────────────────────────────────
        if user and user.locked_until is not None:
            lu = user.locked_until
            if lu.tzinfo is None:
                lu = lu.replace(tzinfo=timezone.utc)
            if lu > now:
                remaining = int((lu - now).total_seconds())
                mins, secs = divmod(remaining, 60)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Account locked. Try again in {mins}m {secs}s.",
                )
            # Expired — clear
            user.failed_login_attempts = 0
            user.locked_until = None
            db.commit()

        # ── Credential check ───────────────────────────────────────────────────
        if not user or not user.verify_password(password):
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                    user.locked_until = now + timedelta(minutes=self.LOCKOUT_MINUTES)
                    db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Too many failed attempts. Account locked for {self.LOCKOUT_MINUTES} minutes.",
                    )
                db.commit()
                left = self.MAX_FAILED_ATTEMPTS - user.failed_login_attempts
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid credentials. {left} attempt(s) left before lockout.",
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

        # ── Success: reset counter ─────────────────────────────────────────────
        if user.failed_login_attempts:
            user.failed_login_attempts = 0
            user.locked_until = None
            db.commit()

        return user

    def create_token_pair(self, user: User) -> Dict[str, object]:
        now = datetime.now(timezone.utc)

        access_exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "typ": "access",
            "jti": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int(access_exp.timestamp()),
        }
        access_token = jwt.encode(access_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        refresh_jti = str(uuid4())
        refresh_exp = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_payload = {
            "sub": str(user.id),
            "typ": "refresh",
            "jti": refresh_jti,
            "iat": int(now.timestamp()),
            "exp": int(refresh_exp.timestamp()),
        }
        refresh_token = jwt.encode(refresh_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        ttl_seconds = int((refresh_exp - now).total_seconds())
        self._set_token_key(self._refresh_key(refresh_jti), ttl_seconds, str(user.id))

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    def rotate_refresh_token(self, db: Session, refresh_token: str) -> Dict[str, object]:
        payload = self._decode_token(refresh_token, expected_type="refresh")
        jti = payload.get("jti")
        user_id = payload.get("sub")
        exp = payload.get("exp")

        if not jti or not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        key = self._refresh_key(jti)
        if self._token_is_blacklisted(jti):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or expired")

        if not self._exists_token_key(key):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or expired")

        self._delete_token_key(key)
        self._blacklist_refresh_token_jti(jti, exp)

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

        return self.create_token_pair(user)

    def revoke_refresh_token(self, refresh_token: str) -> None:
        payload = self._decode_token(refresh_token, expected_type="refresh")
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti:
            self._delete_token_key(self._refresh_key(jti))
            self._blacklist_refresh_token_jti(jti, exp)

    def get_current_user_from_access_token(self, db: Session, token: str) -> User:
        payload = self._decode_token(token, expected_type="access")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

        return user

    def _decode_token(self, token: str, expected_type: str) -> Dict[str, object]:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        except jwt.PyJWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        token_type = payload.get("typ")
        if token_type != expected_type:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        return payload

    def _set_token_key(self, key: str, ttl_seconds: int, value: str) -> None:
        ttl = max(int(ttl_seconds), 1)
        try:
            self._redis.setex(key, ttl, value)
        except Exception:
            self._fallback_store[key] = value

    def _exists_token_key(self, key: str) -> bool:
        try:
            return bool(self._redis.exists(key))
        except Exception:
            return key in self._fallback_store

    def _delete_token_key(self, key: str) -> None:
        try:
            self._redis.delete(key)
        except Exception:
            pass
        self._fallback_store.pop(key, None)

    def _blacklist_refresh_token_jti(self, jti: str, exp_epoch: Optional[int]) -> None:
        ttl_seconds = self._ttl_from_exp(exp_epoch)
        self._set_token_key(self._refresh_blacklist_key(jti), ttl_seconds, "1")

    def _token_is_blacklisted(self, jti: str) -> bool:
        return self._exists_token_key(self._refresh_blacklist_key(jti))

    @staticmethod
    def _ttl_from_exp(exp_epoch: Optional[int]) -> int:
        if not exp_epoch:
            return 60

        now_epoch = int(datetime.now(timezone.utc).timestamp())
        return max(exp_epoch - now_epoch, 1)

    @staticmethod
    def _refresh_key(jti: str) -> str:
        return f"auth:refresh:{jti}"

    @staticmethod
    def _refresh_blacklist_key(jti: str) -> str:
        return f"auth:refresh:blacklist:{jti}"

    @staticmethod
    def _resync_user_id_sequence(db: Session) -> None:
        try:
            db.execute(
                text(
                    """
                    SELECT setval(
                        pg_get_serial_sequence('users', 'id'),
                        COALESCE((SELECT MAX(id) FROM users), 1),
                        true
                    )
                    """
                )
            )
        except Exception:
            # Non-PostgreSQL databases or missing sequence metadata can ignore this.
            pass


auth_service = AuthService()
