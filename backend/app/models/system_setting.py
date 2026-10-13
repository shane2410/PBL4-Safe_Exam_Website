from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class SystemSetting(Base):
    """Cấu hình toàn cục của hệ thống, lưu dạng key-value.

    Giá trị nằm trong `setting_value` (JSON). Tách riêng khỏi bảng `exams` để tránh
    kéo theo lỗi N+1 ở các endpoint liệt kê đề thi (xem docs/PLAN.md mục 0.2).
    """
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True)
    setting_value = Column(JSON, nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    editor = relationship("User", foreign_keys=[updated_by])
