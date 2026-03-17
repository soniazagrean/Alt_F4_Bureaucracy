from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
from app.config import settings

# Create engine used settings
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,  # Disable connection pooling for Docker
    echo=False,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_db():
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database - create all tables"""
    from app.models import user, document, audit  # Import models to register them with Base
    # Base.metadata.create_all(bind=engine) # removed: Alembic manages schema
