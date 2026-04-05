from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field
from pathlib import Path

class Settings(BaseSettings):
    PROJECT_NAME: str = "Violence Detection System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Chỉ dùng 1 biến duy nhất cho kết nối Database
    DATABASE_URL: str
    
    # Khai báo thêm biến AI_SERVER_URL vì bạn đang dùng nó trong .env
    AI_SERVER_URL: str 

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    UPLOAD_DIR: str = "uploads"
    MEDIA_URL_PREFIX: str = "/media"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        # SQLAlchemy yêu cầu bắt đầu bằng postgresql://
        # Render đôi khi trả về postgres:// nên ta cần xử lý thay thế nếu có
        if self.DATABASE_URL.startswith("postgres://"):
            return self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return self.DATABASE_URL

    @computed_field
    @property
    def UPLOAD_DIR_PATH(self) -> Path:
        return Path(self.UPLOAD_DIR).resolve()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()