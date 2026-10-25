from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class ClientDevice(Base):
    """Khoá công khai Ed25519 của một thiết bị đã đăng ký (mục 1.5.2 PLAN.md).

    Private key KHÔNG BAO GIỜ lên server — nó nằm trong kho hệ thống của máy
    (DPAPI / Keychain / Secret Service). Server chỉ giữ public key, nên:

    * Server KHÔNG THỂ tự tạo chữ ký hợp lệ (đây là điểm mạnh so với HMAC, nơi
      server giữ khoá dùng chung).
    * Lộ `SECRET_KEY` không còn đủ để giả danh SEB Client.

    `device_id = sha256(public_key)[:16]` — định danh ổn định, không dùng
    MAC/hostname vì hai giá trị đó người dùng sửa được.
    """

    __tablename__ = "client_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_client_device_user_device"),
        Index("idx_client_device_fingerprint", "fingerprint"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    device_id = Column(String(32), nullable=False, index=True)
    # Public key Ed25525 dạng base64 raw 32 bytes.
    public_key = Column(String(128), nullable=False)
    fingerprint = Column(String(64), nullable=False)

    label = Column(String(100), nullable=True)
    client_version = Column(String(20), nullable=True)

    # Máy không có kho hệ thống thì private key được lưu yếu hơn — cờ này để
    # GV nhìn thấy trên dashboard thay vì phải đào vào log.
    weak_key_storage = Column(Boolean, nullable=False, default=False)

    # Cơ chế client thực sự hỗ trợ, và phần thiếu kèm lý do. GV cần nhìn thấy
    # để biết máy nào không được bảo vệ đầy đủ (VD: Wayland thiếu monitor_switch).
    capabilities = Column(String(255), nullable=True)
    unsupported = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="client_devices")