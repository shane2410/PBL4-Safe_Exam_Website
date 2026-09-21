from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, JSON, DateTime, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class StudentAnswer(Base):
    __tablename__ = "student_answers"
    __table_args__ = (
        UniqueConstraint("session_id", "question_id", name="uq_session_question"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    selected_option_ids = Column(JSON, nullable=True)  # List of integer option IDs, e.g. [1, 3]
    fill_blank_text = Column(Text, nullable=True)
    auto_score = Column(Numeric(5, 2), nullable=True)
    manual_score = Column(Numeric(5, 2), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("ExamSession", back_populates="answers")
    question = relationship("Question", back_populates="student_answers")
