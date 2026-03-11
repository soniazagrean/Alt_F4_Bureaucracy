from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.db.database import Base

class RoleModel(Base):
    """Role model for RBAC"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(Text, nullable=True)  # JSON string of permissions
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"
