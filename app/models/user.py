from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from passlib.context import CryptContext
from app.db.database import Base

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class RoleEnum(str, enum.Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    ARCHIVIST = "archivist"
    INSPECTOR = "inspector"
    VIEWER = "viewer"
    SYSTEM = "system"

class User(Base):
    """User model with role-based access control"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum, create_type=False), default=RoleEnum.VIEWER, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    # Brute-force lockout
    failed_login_attempts = Column(Integer, default=0, nullable=False, server_default="0")
    locked_until = Column(DateTime, nullable=True)
    # TOTP 2FA
    totp_secret = Column(String(64), nullable=True)
    totp_enabled = Column(Boolean, default=False, nullable=False, server_default="false")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user")
    documents = relationship("Document", back_populates="created_by_user")

    def set_password(self, password: str):
        """Hash and set password"""
        self.hashed_password = pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(password, self.hashed_password)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"
