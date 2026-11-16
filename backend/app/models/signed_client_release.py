from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.database import Base


class SignedClientRelease(Base):
    """Mã băm SHA-256 của các bản SEB Client chính thức đã được ký số / phê duyệt.

    Phục vụ kiểm tra tính toàn vẹn client ở Phase 2 (C6 & 2.3.4):
    Khi thí sinh tham gia ca thi, SEB Client gửi hash qua header X-Client-Hash.
    Backend sẽ kiểm tra xem hash này có nằm trong allowlist các bản release đang hoạt động không.
    """

    __tablename__ = "signed_client_releases"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    version = Column(String(50), nullable=False, index=True)
    hash = Column(String(64), nullable=False, index=True)
    os = Column(String(20), default="all", nullable=False)  # windows | macos | linux | all
    released_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(String(255), nullable=True)
