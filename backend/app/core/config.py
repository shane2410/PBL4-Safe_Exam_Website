from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Secure Online Exam System"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "pbl4-secure-exam-system-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours

    # MySQL connection string
    DATABASE_URL: str = "mysql+pymysql://root:@127.0.0.1:3306/secure_exam_db?charset=utf8mb4"

    # CORS origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Anti-cheat configs
    DEFAULT_MAX_VIOLATION_ALLOWED: int = 5
    HEARTBEAT_INTERVAL_SECONDS: int = 10
    HEARTBEAT_TIMEOUT_SECONDS: int = 30

    # Phase 0 — Safe Exam Browser Client attestation
    # Thời gian sống của nonce challenge (giây). Nonce dùng 1 lần rồi bị xoá.
    CLIENT_NONCE_TTL_SECONDS: int = 30

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
