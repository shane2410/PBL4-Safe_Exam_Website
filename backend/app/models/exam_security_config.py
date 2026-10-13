from datetime import datetime, timezone
from sqlalchemy import Column, Integer, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class ExamSecurityConfigRow(Base):
    """Bộ cấu hình khoá an toàn chi tiết của một đề thi (1 đề = 1 bản ghi).

    `config` là JSON đã được validate bằng schema Pydantic `ExamSecurityConfig`
    trước khi ghi xuống. Xem docs/PLAN.md mục 0.2.
    """
    __tablename__ = "exam_security_configs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    config = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    exam = relationship("Exam", back_populates="security_config")
