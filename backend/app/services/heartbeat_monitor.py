"""Giám sát heartbeat: phát hiện thí sinh mất kết nối.

Trước đây `HEARTBEAT_TIMEOUT_SECONDS` có trong config nhưng KHÔNG nơi nào dùng —
nghĩa là cắm máy hoặc tắt mạng trong kỳ thi sẽ không bị ghi nhận. Module này
đóng lại khoảng trống đó.

Cơ chế: mỗi kết nối đang thi giữ `last_heartbeat`. Vòng lặc nền quét mọi kết nối,
kết nối nào im lặng quá ngưỡng sẽ bị:
  1. đánh dấu phiên thi `DISCONNECTED`
  2. ghi log vi phạm `CONNECTION_LOST`
  3. thông báo cho phòng giám sát của GV/QTV

Lưu ý thẳng thắn: đây là **ghi nhận bằng chứng**, không phải ngăn chặn. Thí sinh
có thể tắt mạng rồi bật lại; hệ thống không khoá phiên, chỉ đánh dấu để GV biết
(không có heartbeat nào trong khoảng thời gian đó).

Lý do chạy nền trong tiến trình: đồ án chạy 1 tiến trình uvicorn nên vòng quét
đặt trong luồng sự kiện là đủ. Khi chạy multi-worker phải chuyển sang task
dùng chung (Redis/Celery), nếu không mỗi worker chỉ thấy socket của riêng mình.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.exam_session import ExamSession
from app.schemas.violation_schema import ViolationLogCreate
from app.services.anticheat_service import AnticheatService

logger = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = 10


def _parse_iso(value: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


async def scan_stale_connections(active_sockets: dict, sio, db_factory=None) -> int:
    """Quét các kết nối im lặng quá ngưỡng. Trả về số phiên bị đánh dấu mất kết nối.

    Được thiết kế nhận `active_sockets` và `sio` từ ngoài vào để không tạo phụ thuộc
    vòng import với `exam_namespace` (module này được import từ đó).

    `db_factory` cho phép truyền session factory khác (dùng trong test với SQLite).
    Mặc định lấy SessionLocal của ứng dụng.
    """
    now = datetime.now(timezone.utc)
    timeout = timedelta(seconds=settings.HEARTBEAT_TIMEOUT_SECONDS)
    stale_sids = []

    for sid, info in list(active_sockets.items()):
        last = _parse_iso(info.get("last_heartbeat", ""))
        if last is None or (now - last) <= timeout:
            continue
        stale_sids.append(sid)

    if not stale_sids:
        return 0

    factory = db_factory or SessionLocal
    owns_session = db_factory is None
    marked = 0
    db = factory()
    try:
        for sid in stale_sids:
            info = active_sockets.pop(sid, None)
            if not info:
                continue

            session_id = info.get("session_id")
            room_code = (info.get("room_code") or "").upper()

            session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
            if not session or session.status != "IN_PROGRESS":
                continue

            # 1. Ghi log vi phạm TRƯỚC, rồi mới đổi trạng thái.
            #    Thứ tự này quan trọng: `record_violation` chỉ ghi nhận cho phiên
            #    đang IN_PROGRESS, nếu đổi sang DISCONNECTED trước thì sự kiện
            #    mất kết nối sẽ bị bỏ qua và KHÔNG còn bằng chứng phục tra.
            AnticheatService.record_violation(
                db,
                session_id,
                ViolationLogCreate(
                    event_type="CONNECTION_LOST",
                    detail={
                        "reason": "Không nhận được heartbeat trong thời gian quy định",
                        "timeout_seconds": settings.HEARTBEAT_TIMEOUT_SECONDS,
                        "detected_by": "server_background_scan",
                    },
                    client_timestamp=now,
                ),
            )

            # 2. Đánh dấu mất kết nối
            session.status = "DISCONNECTED"
            db.commit()
            marked += 1

            # 3. Báo cho GV/QTV đang theo dõi phòng
            if sio is not None and room_code:
                await sio.emit(
                    "student_status_change",
                    {
                        "session_id": session_id,
                        "student_id": info.get("student_id"),
                        "student_name": info.get("student_name"),
                        "status": "DISCONNECTED",
                        "reason": "Mất kết nối — không nhận được tín hiệu heartbeat",
                        "timestamp": now.isoformat(),
                    },
                    room=f"monitor_{room_code}",
                )
    except Exception:
        db.rollback()
        logger.error("Lỗi khi quét heartbeat", exc_info=True)
    finally:
        # Chỉ đóng session do hàm này TỰ TẠO. Session được inject từ bên ngoài
        # (dùng trong test) thuộc quyền sở hữu của bên gọi — đóng ở đây sẽ phá
        # vỡ session của họ.
        if owns_session:
            db.close()

    if marked:
        logger.info("Đánh dấu %d phiên mất kết nối do thiếu heartbeat", marked)
    return marked


def start_heartbeat_monitor(active_sockets: dict, sio) -> "asyncio.Task":
    """Khởi động vòng quét heartbeat nền. Trả về Task để huỷ khi cần."""

    async def _loop():
        while True:
            try:
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
                await scan_stale_connections(active_sockets, sio)
            except asyncio.CancelledError:
                logger.info("Đã dừng vòng quét heartbeat")
                raise
            except Exception:
                logger.error("Vòng quét heartbeat gặp lỗi", exc_info=True)

    return asyncio.create_task(_loop())
