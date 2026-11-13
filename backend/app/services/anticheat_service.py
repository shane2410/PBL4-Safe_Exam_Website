import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from app.core.config import settings
from app.models.exam_session import ExamSession
from app.models.exam_schedule import ExamSchedule
from app.models.violation_log import ViolationLog
from app.schemas.violation_schema import ViolationLogCreate, resolve_severity
from app.services.exam_security_service import ExamSecurityService

logger = logging.getLogger(__name__)

# Trọng số risk score theo từng loại vi phạm.
# LƯU Ý: đây chỉ là metric hiển thị cho GV/QTV — KHÔNG phải điều kiện quyết định
# tự động nộp bài. Quyết định nộp bài dựa trên NGƯỠNG SỐ LẦN vi phạm lấy từ
# exam_security_service (skills.md Quy tắc #4.3).
RISK_WEIGHTS = {
    "TAB_SWITCH": 10,
    "FULLSCREEN_EXIT": 15,
    "DEVTOOLS_DETECTED": 30,
    "COPY_PASTE_ATTEMPT": 5,
    "RIGHT_CLICK_ATTEMPT": 5,
    "DUPLICATE_LOGIN": 25,
    "CONNECTION_LOST": 5,
    "UNAUTHORIZED_CLIENT": 20,
}

MAX_RISK_SCORE = 1000


class AnticheatService:
    @staticmethod
    def resolve_max_violations_for_exam(db: Session, exam) -> int:
        """Ngưỡng vi phạm cho một đề thi, theo đúng thứ tự ưu tiên đã tài liệu hoá.

        1. `exam_security_configs` (GV cấu hình riêng cho đề)
        2. `exams.max_violation_allowed` (cột có sẵn trên đề)
        3. `DEFAULT_MAX_VIOLATION_ALLOWED` trong config

        Mọi nơi hiển thị/áp ngưỡng (join response, monitor, auto-submit) phải
        dùng CÙNG hàm này, nếu không UI và server lại lệch nhau.
        """
        if exam is None:
            return settings.DEFAULT_MAX_VIOLATION_ALLOWED

        exam_config = ExamSecurityService.get_stored_config(db, exam.id)
        if exam_config is not None:
            return exam_config.max_tab_switch + exam_config.max_fullscreen_exit

        if exam.max_violation_allowed:
            return int(exam.max_violation_allowed)

        return settings.DEFAULT_MAX_VIOLATION_ALLOWED

    @staticmethod
    def resolve_max_violations(db: Session, session: ExamSession) -> int:
        """Ngưỡng số lần vi phạm của phiên thi hiện tại."""
        exam = session.schedule.exam if session.schedule else None
        return AnticheatService.resolve_max_violations_for_exam(db, exam)

    @staticmethod
    def record_violation(
        db: Session,
        session_id: int,
        v_data: ViolationLogCreate
    ) -> Tuple[Optional[ViolationLog], bool]:
        """
        Ghi nhận sự kiện vi phạm, tăng bộ đếm, cập nhật risk score và đánh giá
        ngưỡng vi phạm.
        Trả về: (ViolationLog hoặc None, is_threshold_exceeded: bool)
        """
        session = db.query(ExamSession).options(
            joinedload(ExamSession.schedule).joinedload(ExamSchedule.exam)
        ).filter(ExamSession.id == session_id).first()

        if not session or session.status != "IN_PROGRESS":
            return None, False

        try:
            # Mức nghiêm trọng do SERVER quyết định, không tin giá trị client gửi lên.
            v_log = ViolationLog(
                session_id=session_id,
                event_type=v_data.event_type,
                severity=resolve_severity(v_data.event_type),
                detail=v_data.detail,
                client_timestamp=v_data.client_timestamp,
                server_timestamp=datetime.now(timezone.utc)
            )
            db.add(v_log)
            db.flush()  # Flush so count() thấy bản ghi vừa thêm trong transaction hiện tại

            # Cập nhật bộ đếm riêng cho từng cơ chế
            if v_data.event_type == "TAB_SWITCH":
                session.tab_switch_count += 1
            elif v_data.event_type == "FULLSCREEN_EXIT":
                session.fullscreen_exit_count += 1

            # Cộng risk score, chặn trên trần
            weight = RISK_WEIGHTS.get(v_data.event_type, 10)
            session.risk_score = min(session.risk_score + weight, MAX_RISK_SCORE)

            # Đếm số vi phạm THUỘC DIỆN TÍNH NGƯỠNG (tab switch + fullscreen exit).
            # Trước đây đếm TẤT CẢ ViolationLog, nên DEVTOOLS_DETECTED,
            # COPY_PASTE_ATTEMPT, RIGHT_CLICK_ATTEMPT, CONNECTION_LOST,
            # DUPLICATE_LOGIN... cũng ăn vào quota chuyển tab -> tự nộp sớm hơn
            # cấu hình, lệch với bộ đếm hiển thị cho thí sinh.
            counted_violations = session.tab_switch_count + session.fullscreen_exit_count

            max_allowed = AnticheatService.resolve_max_violations(db, session)
            threshold_exceeded = (counted_violations >= max_allowed) and (session.status == "IN_PROGRESS")

            db.commit()
            db.refresh(v_log)
            return v_log, threshold_exceeded
        except Exception as e:
            db.rollback()
            logger.error("Error recording violation for session %d: %s", session_id, e, exc_info=True)
            return None, False
