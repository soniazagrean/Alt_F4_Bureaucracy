from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    APP_NAME: str = "Alt_F4_Bureaucracy"
    APP_ENV: str = "development"

    # Database (PostgreSQL)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "alt_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Database (Neo4j)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Cache (Redis)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # Storage (MinIO)
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin"
    MINIO_PORT: int = 9000
    
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: Optional[str] = None
    MINIO_SECRET_KEY: Optional[str] = None
    
    MINIO_BUCKET_UPLOADS: str = "uploads"
    MINIO_BUCKET_PROCESSED: str = "processed"
    MINIO_BUCKET_QUARANTINE: str = "quarantine"
    MINIO_SECURE: bool = False

    # Search Engine (Meilisearch)
    MEILI_HOST: str = "localhost"
    MEILISEARCH_PORT: int = 7700
    MEILI_MASTER_KEY: str = "super_secret_key"
    
    @property
    def MEILI_URL(self) -> str:
        return f"http://{self.MEILI_HOST}:{self.MEILISEARCH_PORT}"

    # AI Services (OpenAI)
    OPENAI_API_KEY: Optional[str] = None

    # Auth (JWT)
    JWT_SECRET_KEY: str = Field(default="change_me_in_production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def model_post_init(self, __context):
        if self.MINIO_ACCESS_KEY is None:
            self.MINIO_ACCESS_KEY = self.MINIO_ROOT_USER
        if self.MINIO_SECRET_KEY is None:
            self.MINIO_SECRET_KEY = self.MINIO_ROOT_PASSWORD

settings = Settings()