from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    title = Column(String(200), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False, default=60)
    total_score = Column(Numeric(5, 2), nullable=False, default=10.00)
    is_shuffled = Column(Boolean, default=True, nullable=False)
    max_violation_allowed = Column(Integer, default=5, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    subject = relationship("Subject", back_populates="exams")
    creator = relationship("User", back_populates="created_exams")
    exam_questions = relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan", order_by="ExamQuestion.order_index")
    schedules = relationship("ExamSchedule", back_populates="exam", cascade="all, delete-orphan")
