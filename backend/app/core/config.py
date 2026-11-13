import os
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Giá trị mặc định của SECRET_KEY — CHỈ dùng cho môi trường phát triển.
# Nếu chạy với giá trị này ở production, bất kỳ ai đọc được source đều ký được
# JWT hợp lệ (và dẫn xuất được `device_secret` của mọi người dùng).
DEV_SECRET_KEY = "pbl4-secure-exam-system-secret-key-change-in-production"

# Mật khẩu rỗng của MySQL chỉ phù hợp máy dev (XAMPP mặc định).
DEV_DATABASE_URL = "mysql+pymysql://root:@127.0.0.1:3306/secure_exam_db?charset=utf8mb4"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Secure Online Exam System"
    API_V1_STR: str = "/api"

    # --- Biến môi trường ---
    # `ENV=production` bật các kiểm tra an toàn bên dưới. Mặc định "development"
    # để `pytest` và máy dev không phải cấu hình gì.
    ENV: str = "development"
    DEBUG: bool = True

    SECRET_KEY: str = DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours

    # MySQL connection string
    DATABASE_URL: str = DEV_DATABASE_URL

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
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.ENV.strip().lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _guard_production_secrets(self):
        """Chặn khởi động production với cấu hình dev.

        Kiểm tra ở đây (lúc tạo Settings) thay vì lúc dùng, để lỗi cấu hình làm
        app KHÔNG khởi động được — im lặng chạy với secret mặc định nguy hiểm
        hơn nhiều so với crash sớm và rõ ràng.
        """
        if not self.is_production:
            return self

        problems = []
        if not self.SECRET_KEY or self.SECRET_KEY == DEV_SECRET_KEY:
            problems.append(
                "SECRET_KEY đang dùng giá trị mặc định của source code. "
                "Đặt SECRET_KEY=<chuỗi ngẫu nhiên dài> trong biến môi trường/.env."
            )
        elif len(self.SECRET_KEY) < 32:
            problems.append("SECRET_KEY quá ngắn (cần tối thiểu 32 ký tự) khi chạy production.")

        if not self.DATABASE_URL or self.DATABASE_URL == DEV_DATABASE_URL:
            problems.append(
                "DATABASE_URL đang trỏ tới MySQL dev (root, mật khẩu rỗng). "
                "Đặt DATABASE_URL có mật khẩu khi chạy production."
            )

        if "*" in self.CORS_ORIGINS:
            problems.append("CORS_ORIGINS không được chứa '*' khi chạy production.")

        if problems:
            raise ValueError(
                "Cấu hình không an toàn cho production:\n  - " + "\n  - ".join(problems)
            )
        return self


settings = Settings()
