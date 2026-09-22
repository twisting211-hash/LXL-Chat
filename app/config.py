import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """
    Application Settings loaded from environment variables or .env file.
    Follows Pydantic v2 BaseSettings specifications.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server settings
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    SERVER_PUBLIC_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/messenger"

    # Security & JWT
    JWT_SECRET: str = "default_insecure_secret_key_change_me_in_production_32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    # Owner notification settings (Render Cold Start / Server Status)
    OWNER_USERNAME: str = ""

    # CORS
    CORS_ORIGINS: str = "*"

    # WebRTC STUN & TURN
    STUN_SERVER: str = "stun:stun.l.google.com:19302"
    STUN_SERVER_SECONDARY: str = "stun:stun1.l.google.com:19302"
    TURN_SERVER: str = ""
    TURN_USERNAME: str = ""
    TURN_PASSWORD: str = ""

    # Storage settings
    STORAGE_PROVIDER: str = "local"  # "local" or "s3"
    LOCAL_UPLOAD_DIR: str = "uploads"
    STORAGE_BUCKET: str = ""
    STORAGE_REGION: str = "auto"
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""
    STORAGE_ENDPOINT_URL: str = ""
    STORAGE_PUBLIC_URL_PREFIX: str = ""
    MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB

    # Push notifications (Firebase Cloud Messaging)
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""
    FIREBASE_PRIVATE_KEY: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS or self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def async_database_url(self) -> str:
        """
        Ensures asyncpg driver prefix for async SQLAlchemy.
        Render provides 'postgres://' or 'postgresql://'.
        """
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """
        Synchronous URL for Alembic migrations.
        """
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url


settings = Settings()
