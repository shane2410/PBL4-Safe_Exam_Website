import logging
from typing import Optional
from sqlalchemy.orm import Session
from pydantic import ValidationError
from app.models.exam import Exam
from app.models.exam_security_config import ExamSecurityConfigRow
from app.schemas.settings_schema import ExamSecurityConfig
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class ExamSecurityService:
    """Nguồn sự thật duy nhất cho cấu hình khoá an toàn.

    Cả Lớp A (web) và Lớp B (SEB Client) đều đọc chính hàm `resolve_policy` này,
    nên không thể xảy ra tình trạng client bật/tắt guard lệch với điều GV cấu hình.
    """

    @staticmethod
    def get_stored_config(db: Session, exam_id: int) -> Optional[ExamSecurityConfig]:
        """Đọc cấu hình riêng của đề thi, trả None nếu chưa cấu hình."""
        row = db.query(ExamSecurityConfigRow).filter(
            ExamSecurityConfigRow.exam_id == exam_id
        ).first()
        if row is None:
            return None

        try:
            return ExamSecurityConfig.model_validate(row.config)
        except ValidationError:
            # Cấu hình trong DB hỏng (VD: GV nhập tay) -> log và fallback về mặc định
            # thay vì làm sập cả luồng vào phòng thi.
            logger.warning("Cấu hình khoá an toàn của đề %d không hợp lệ, dùng mặc định", exam_id, exc_info=True)
            return None

    @staticmethod
    def save_config(db: Session, exam_id: int, config: ExamSecurityConfig) -> ExamSecurityConfig:
        """Upsert cấu hình khoá an toàn cho đề thi (đã validate qua schema)."""
        row = db.query(ExamSecurityConfigRow).filter(
            ExamSecurityConfigRow.exam_id == exam_id
        ).first()

        payload = config.model_dump()
        if row is None:
            row = ExamSecurityConfigRow(exam_id=exam_id, config=payload)
            db.add(row)
        else:
            row.config = payload

        db.commit()
        db.refresh(row)
        return config

    @staticmethod
    def resolve_policy(db: Session, exam_id: int) -> ExamSecurityConfig:
        """Cấu hình có hiệu lực cho đề: cấu hình riêng của đề, nếu không có thì lấy mặc định hệ thống."""
        exam_config = ExamSecurityService.get_stored_config(db, exam_id)
        if exam_config is not None:
            return exam_config
        return SettingsService.get_default_security_config(db)

    @staticmethod
    def is_safe_browser_required(db: Session, exam: Exam) -> bool:
        """Quyết định cuối cùng cho cờ 'only through safe exam browser'.

        = (cờ của đề) AND (cờ của hệ thống)

        GV có thể tắt yêu cầu cho từng đề ngay cả khi cả hệ thống đang bật.
        """
        if not exam.require_safe_browser:
            return False
        return SettingsService.get_require_safe_browser_global(db)
