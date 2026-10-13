from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    student_code = Column(String(20), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    # Salt dùng để dẫn xuất device_secret cho challenge-response (Phase 0).
    # Chỉ lưu salt — khoá thật được dẫn xuất lúc chạy từ SECRET_KEY, không lưu rõ.
    device_secret_salt = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    role = relationship("Role", back_populates="users")
    created_questions = relationship("Question", back_populates="creator")
    created_exams = relationship("Exam", back_populates="creator")
    supervised_schedules = relationship("ExamSchedule", back_populates="supervisor")
    exam_sessions = relationship("ExamSession", back_populates="student")
    audit_logs = relationship("AuditLog", back_populates="user")
