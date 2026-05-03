from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field, Field
from pathlib import Path

class Settings(BaseSettings):
    PROJECT_NAME: str = "Violence Detection System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    # =========================
    # DATABASE & AI SERVER
    # =========================
    DATABASE_URL: str = Field(..., min_length=1)
    AI_SERVER_URL: str = Field(..., min_length=1)

    # =========================
    # SECURITY
    # =========================
    SECRET_KEY: str = Field(..., min_length=8)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # =========================
    # S3 (RUNPOD)
    # =========================
    S3_ENDPOINT_URL: str = Field(..., min_length=1)
    S3_REGION_NAME: str = "eu-ro-1"
    S3_ACCESS_KEY_ID: str = Field(..., min_length=1)
    S3_SECRET_ACCESS_KEY: str = Field(..., min_length=1)
    S3_BUCKET_NAME: str = Field(..., min_length=1)
    S3_UPLOAD_PREFIX: str = "uploads/"

    # =========================
    # COMPUTED PROPERTIES
    # =========================
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL.startswith("postgres://"):
            return self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return self.DATABASE_URL


    @computed_field
    @property
    def S3_BASE_URL(self) -> str:
        return f"{self.S3_ENDPOINT_URL}/{self.S3_BUCKET_NAME}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()