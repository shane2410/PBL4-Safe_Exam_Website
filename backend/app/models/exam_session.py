from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class ExamSession(Base):
    __tablename__ = "exam_sessions"
    __table_args__ = (
        UniqueConstraint("schedule_id", "student_id", name="uq_schedule_student"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    schedule_id = Column(Integer, ForeignKey("exam_schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token = Column(String(255), nullable=False, unique=True, index=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    submit_type = Column(String(20), nullable=True)  # MANUAL | SHUTDOWN_BUTTON | AUTO_TIMEOUT | AUTO_VIOLATION
    status = Column(String(20), default="IN_PROGRESS", nullable=False)  # IN_PROGRESS | SUBMITTED | DISCONNECTED
    risk_score = Column(Integer, default=0, nullable=False)
    tab_switch_count = Column(Integer, default=0, nullable=False)
    fullscreen_exit_count = Column(Integer, default=0, nullable=False)
    final_score = Column(Numeric(5, 2), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    # --- Thông tin client (Phase 0/1) ---
    client_type = Column(String(20), default="web", nullable=False)  # web | seb
    client_version = Column(String(20), nullable=True)
    # Thiết bị Ed25519 đã xác thực cho phiên này (NULL nếu client chưa attest).
    device_id = Column(String(32), nullable=True, index=True)
    device_fingerprint = Column(String(128), nullable=True)
    attestation_status = Column(String(20), default="NOT_ATTESTED", nullable=False)  # NOT_ATTESTED | VERIFIED | FAILED | REQUIRED_MISSING

    schedule = relationship("ExamSchedule", back_populates="sessions")
    student = relationship("User", back_populates="exam_sessions")
    answers = relationship("StudentAnswer", back_populates="session", cascade="all, delete-orphan")
    violation_logs = relationship("ViolationLog", back_populates="session", cascade="all, delete-orphan")
    attestations = relationship("ClientAttestation", back_populates="session", cascade="all, delete-orphan")
