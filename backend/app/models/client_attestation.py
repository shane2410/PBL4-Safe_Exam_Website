from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base

class ClientAttestation(Base):
    """Bản ghi xác thực client (Safe Exam Browser Client) cho từng phiên thi.

    Lưu vết kết quả challenge-response để hỗ trợ phúc tra về sau (Phase 2).
    KHÔNG lưu `session_secret` hay `attestation_key` ở dạng rõ — chỉ lưu hash.
    """
    __tablename__ = "client_attestations"
    __table_args__ = (
        Index("idx_attestation_session", "session_id", "verified"),
        Index("idx_attestation_device", "device_id", "verified"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    client_type = Column(String(20), nullable=False)  # web | seb
    client_version = Column(String(20), nullable=True)
    device_fingerprint = Column(String(128), nullable=True)
    # Thiết bị Ed25519 đã xác thực (NULL với client dùng HMAC cũ).
    device_id = Column(String(32), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)
    verification_detail = Column(String(255), nullable=True)
    # Salt để dẫn xuất lại attestation_key khi xác minh heartbeat, không lưu khoá rõ.
    key_salt = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("ExamSession", back_populates="attestations")
