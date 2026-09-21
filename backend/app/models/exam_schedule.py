from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class ExamSchedule(Base):
    __tablename__ = "exam_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    room_code = Column(String(20), unique=True, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    supervised_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), default="SCHEDULED", nullable=False)  # SCHEDULED | ONGOING | FINISHED | CANCELLED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    exam = relationship("Exam", back_populates="schedules")
    supervisor = relationship("User", back_populates="supervised_schedules")
    sessions = relationship("ExamSession", back_populates="schedule", cascade="all, delete-orphan")
