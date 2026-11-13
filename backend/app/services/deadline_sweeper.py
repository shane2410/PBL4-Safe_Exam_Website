"""Vòng quét phiên thi quá hạn và tự nộp bài (AUTO_TIMEOUT).

Vì sao cần: trước đây việc tự nộp khi hết giờ chỉ xảy ra nếu client chủ động
gọi. Nếu thí sinh đóng tab, mất mạng, hoặc SEB Client bị tắt đúng lúc hết giờ,
phiên sẽ kẹt `IN_PROGRESS` vĩnh viễn và KHÔNG BAO GIỜ được chấm điểm — kể cả
khi bài đã làm xong. Server có `_get_deadline()` nhưng chỉ dùng để chặn
`save_answer`; không có nơi nào thực sự nộp.

Cơ chế:
  * mỗi `SCAN_INTERVAL_SECONDS` quét các phiên chưa nộp còn sống,
  * tính deadline theo đồng hồ SERVER (min(thời lượng đề, giờ kết thúc ca)),
  * trễ thêm `GRACE_SECONDS` để nhường client tự nộp trước (tránh đua),
  * gọi `ExamSessionService.submit_exam(..., AUTO_TIMEOUT)` — idempotent, nên
    quét lại sau khi đã nộp không gây hại.

Giới hạn trung thực: vòng quét chạy trong tiến trình, giống heartbeat monitor.
Chạy multi-worker thì phải chuyển sang task dùng chung (Redis/Celery), nếu
không mỗi worker chỉ thấy một phần phiên.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import joinedload

from app.core.database import SessionLocal
from app.models.exam_session import ExamSession
from app.models.exam_schedule import ExamSchedule
from app.schemas.exam_session_schema import SubmitExamRequest
from app.services.exam_session_service import ExamSessionService, _get_deadline

logger = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = 30
# Nhường client (React / SEB Client) tự nộp trước khi server cưỡng chế.
GRACE_SECONDS = 15
# Chỉ quét các phiên còn "sống".
OPEN_STATUSES = ("IN_PROGRESS", "DISCONNECTED")


def sweep_expired_sessions(
    db_factory=None,
    now: datetime | None = None,
    grace_seconds: int = GRACE_SECONDS,
) -> int:
    """Nộp các phiên đã quá hạn. Trả về số phiên đã nộp thành công.

    `db_factory`/`now`/`grace_seconds` cho phép test với SQLite và mốc thời gian
    giả lập.
    """
    current = now or datetime.now(timezone.utc)
    cutoff_buffer = timedelta(seconds=grace_seconds)
    factory = db_factory or SessionLocal
    owns_session = db_factory is None

    db = factory()
    submitted = 0
    try:
        sessions = (
            db.query(ExamSession)
            .options(joinedload(ExamSession.schedule).joinedload(ExamSchedule.exam))
            .filter(
                ExamSession.status.in_(OPEN_STATUSES),
                ExamSession.submitted_at.is_(None),
            )
            .all()
        )

        for session in sessions:
            schedule = session.schedule
            if schedule is None or schedule.exam is None:
                continue
            try:
                deadline = _get_deadline(session, schedule)
            except Exception:
                logger.warning(
                    "Không tính được deadline cho phiên %d — bỏ qua", session.id, exc_info=True
                )
                continue

            if current.replace(tzinfo=None) <= deadline + cutoff_buffer:
                continue

            try:
                ExamSessionService.submit_exam(
                    db,
                    session.session_token,
                    SubmitExamRequest(submit_type="AUTO_TIMEOUT"),
                    current_user=None,
                    skip_auth_check=True,
                )
                submitted += 1
                logger.info(
                    "Tự nộp phiên %d do quá hạn %s",
                    session.id,
                    deadline.isoformat(),
                )
            except Exception:
                # Một phiên lỗi không được làm dừng cả vòng quét.
                db.rollback()
                logger.error("Tự nộp phiên %d thất bại", session.id, exc_info=True)
    except Exception:
        db.rollback()
        logger.error("Vòng quét phiên quá hạn gặp lỗi", exc_info=True)
    finally:
        if owns_session:
            db.close()

    return submitted


def start_deadline_sweeper() -> "asyncio.Task":
    """Khởi động vòng quét nền. Trả về Task để huỷ khi shutdown."""

    async def _loop():
        while True:
            try:
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
                submitted = await asyncio.to_thread(sweep_expired_sessions)
                if submitted:
                    logger.info("Đã tự nộp %d phiên quá hạn", submitted)
            except asyncio.CancelledError:
                logger.info("Đã dừng vòng quét phiên quá hạn")
                raise
            except Exception:
                logger.error("Vòng quét phiên quá hạn gặp lỗi", exc_info=True)

    return asyncio.create_task(_loop())
