from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL from environment
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "alt_db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Create engine
engine = create_engine(
    DATABASE_URL,
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
    Base.metadata.create_all(bind=engine)
