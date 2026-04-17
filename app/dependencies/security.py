from enum import Enum
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.services.auth import auth_service


class RBACRole(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    AUDITOR = "AUDITOR"


security = HTTPBearer(auto_error=True)


@dataclass
class AuthenticatedUserContext:
    user: User
    rbac_role: RBACRole


def map_user_to_rbac_role(user: User) -> RBACRole:
    role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
    role_value = role_value.lower()

    if role_value in {"admin", "system"}:
        return RBACRole.ADMIN
    if role_value in {"operator", "archivist", "inspector"}:
        return RBACRole.OPERATOR
    if role_value in {"auditor", "viewer"}:
        return RBACRole.AUDITOR

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown user role")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    return auth_service.get_current_user_from_access_token(db, credentials.credentials)


def get_current_user_context(
    current_user: User = Depends(get_current_user),
) -> AuthenticatedUserContext:
    return AuthenticatedUserContext(
        user=current_user,
        rbac_role=map_user_to_rbac_role(current_user),
    )


def require_roles(*allowed: RBACRole) -> Callable[[User], User]:
    def checker(context: AuthenticatedUserContext = Depends(get_current_user_context)) -> User:
        if context.rbac_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return context.user

    return checker
