from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base

class ViolationLog(Base):
    __tablename__ = "violation_logs"
    __table_args__ = (
        Index("idx_session_client_time", "session_id", "client_timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(30), nullable=False)  # TAB_SWITCH | FULLSCREEN_EXIT | DEVTOOLS_DETECTED | COPY_PASTE_ATTEMPT | RIGHT_CLICK_ATTEMPT | DUPLICATE_LOGIN | CONNECTION_LOST
    severity = Column(String(10), nullable=False, default="MEDIUM")  # LOW | MEDIUM | HIGH
    detail = Column(JSON, nullable=True)
    client_timestamp = Column(DateTime, nullable=False)
    server_timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    session = relationship("ExamSession", back_populates="violation_logs")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
