from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    content = Column(Text, nullable=False)
    type = Column(String(20), nullable=False)  # SINGLE_CHOICE | MULTI_CHOICE | FILL_BLANK
    difficulty = Column(String(10), nullable=False, default="MEDIUM")  # EASY | MEDIUM | HARD
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    image_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    subject = relationship("Subject", back_populates="questions")
    creator = relationship("User", back_populates="created_questions")
    options = relationship("QuestionOption", back_populates="question", cascade="all, delete-orphan")
    exam_questions = relationship("ExamQuestion", back_populates="question", cascade="all, delete-orphan")
    student_answers = relationship("StudentAnswer", back_populates="question")
