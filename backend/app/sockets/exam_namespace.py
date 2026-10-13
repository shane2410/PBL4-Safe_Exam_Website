import logging
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy.orm import joinedload
from app.sockets.socket_server import sio
from app.core.database import SessionLocal
from app.models.exam_session import ExamSession
from app.models.exam_schedule import ExamSchedule
from app.schemas.violation_schema import (
    ALLOWED_EVENT_TYPES, ViolationLogCreate, resolve_severity
)
from app.services.anticheat_service import AnticheatService
from app.services.exam_security_service import ExamSecurityService
from app.services.exam_session_service import ExamSessionService
from app.schemas.exam_session_schema import SubmitExamRequest

logger = logging.getLogger(__name__)

# In-memory mapping of sid -> session info {session_token, session_id, room_code, student_id, student_name}
active_sockets: Dict[str, Dict[str, Any]] = {}

def register_exam_socket_handlers():
    @sio.event
    async def connect(sid, environ, auth):
        pass

    @sio.event
    async def join_exam_room(sid, data):
        """Thí sinh vào phòng thi qua socket."""
        room_code = data.get("room_code")
        session_token = data.get("session_token")

        if not room_code or not session_token:
            return {"status": "error", "message": "Missing room_code or session_token"}

        db = SessionLocal()
        try:
            session = db.query(ExamSession).filter(ExamSession.session_token == session_token).first()
            if not session or session.status == "SUBMITTED":
                return {"status": "error", "message": "Invalid or finished session"}

            # --- Phát hiện đăng nhập trùng ---
            # Cùng một phiên thi mà có 2 socket đang mở là dấu hiệu thí sinh
            # mở nhiều tab / thi từ nhiều máy. Ghi log rồi KICK socket cũ đi,
            # để phiên chỉ có một kết nối duy nhất.
            duplicate_sids = [
                other_sid
                for other_sid, info in active_sockets.items()
                if other_sid != sid and info.get("session_id") == session.id
            ]
            if duplicate_sids:
                for other_sid in duplicate_sids:
                    other_info = active_sockets.pop(other_sid, None)
                    AnticheatService.record_violation(db, session.id, ViolationLogCreate(
                        event_type="DUPLICATE_LOGIN",
                        detail={
                            "reason": "Cùng phiên thi mở nhiều kết nối cùng lúc",
                            "kicked_sid_count": len(duplicate_sids),
                            "detected_by": "server",
                        },
                        client_timestamp=datetime.now(timezone.utc),
                    ))
                    await sio.emit(
                        "force_submit",
                        {
                            "reason": "Phiên thi của bạn vừa bị phát hiện mở nhiều nơi cùng lúc. "
                                      "Vui lòng liên hệ giám thị.",
                        },
                        to=other_sid,
                    )
                    if other_info:
                        await sio.emit(
                            "student_status_change",
                            {
                                "session_id": session.id,
                                "student_id": other_info.get("student_id"),
                                "student_name": other_info.get("student_name"),
                                "status": "DISCONNECTED",
                                "reason": "Đăng nhập trùng — phiên thi bị buộc ngắt kết nối",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                            room=f"monitor_{room_code.upper()}",
                        )
                    logger.warning(
                        "Phát hiện đăng nhập trùng: session=%d, kick %d socket cũ",
                        session.id, len(duplicate_sids),
                    )

            room_name = f"room_{room_code.upper()}"
            await sio.enter_room(sid, room_name)

            student_name = session.student.full_name if session.student else "Thí sinh"
            student_code = session.student.student_code if session.student else "N/A"

            active_sockets[sid] = {
                "session_token": session_token,
                "session_id": session.id,
                "room_code": room_code.upper(),
                "student_id": session.student_id,
                "student_name": student_name,
                "student_code": student_code,
                "last_heartbeat": datetime.now(timezone.utc).isoformat()
            }

            # Notify monitor room (Teachers)
            monitor_room = f"monitor_{room_code.upper()}"
            await sio.emit("student_status_change", {
                "session_id": session.id,
                "student_id": session.student_id,
                "student_name": student_name,
                "student_code": student_code,
                "status": "ONLINE",
                "risk_score": session.risk_score,
                "tab_switch_count": session.tab_switch_count,
                "fullscreen_exit_count": session.fullscreen_exit_count,
            }, room=monitor_room)

            return {"status": "success", "room": room_name}
        finally:
            db.close()

    @sio.event
    async def heartbeat(sid, data):
        """Heartbeat ping from student exam client."""
        if sid in active_sockets:
            active_sockets[sid]["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
            
            # Send ack back
            return {
                "status": "alive",
                "server_time": datetime.now(timezone.utc).isoformat()
            }

    @sio.event
    async def violation(sid, data):
        """Thí sinh báo cáo sự kiện vi phạm an toàn.

        Server KHÔNG tin `severity` do client gửi lên — mức nghiêm trọng được
        quyết định từ event_type (skills.md Quy tắc #4).
        """
        if sid not in active_sockets:
            return {"status": "error", "message": "Socket not registered"}

        sock_info = active_sockets[sid]
        session_id = sock_info["session_id"]
        room_code = sock_info["room_code"]

        event_type = data.get("type", "TAB_SWITCH")
        detail = data.get("detail", {}) or {}
        client_ts_str = data.get("clientTimestamp")

        # Chỉ chấp nhận event_type có trong whitelist — client tự do gửi
        # sẽ làm sai lệch thống kê vi phạm và risk score.
        if event_type not in ALLOWED_EVENT_TYPES:
            logger.warning("Từ chối event_type không hợp lệ '%s' từ session %d", event_type, session_id)
            return {"status": "error", "message": "Loại sự kiện không hợp lệ"}

        try:
            client_ts = datetime.fromisoformat(client_ts_str) if client_ts_str else datetime.now(timezone.utc)
        except Exception:
            client_ts = datetime.now(timezone.utc)

        v_create = ViolationLogCreate(
            event_type=event_type,
            detail=detail,
            client_timestamp=client_ts,
        )
        severity = resolve_severity(event_type)

        db = SessionLocal()
        try:
            v_log, exceeded = AnticheatService.record_violation(db, session_id, v_create)
            if v_log:
                session = db.query(ExamSession).options(
                    joinedload(ExamSession.schedule).joinedload(ExamSchedule.exam)
                ).filter(ExamSession.id == session_id).first()
                if session:
                    # Broadcast violation alert to teacher monitor room
                    monitor_room = f"monitor_{room_code}"
                    await sio.emit("violation_alert", {
                        "session_id": session_id,
                        "student_name": sock_info["student_name"],
                        "student_code": sock_info["student_code"],
                        "event_type": event_type,
                        "severity": severity,
                        "detail": detail,
                        "risk_score": session.risk_score,
                        "tab_switch_count": session.tab_switch_count,
                        "fullscreen_exit_count": session.fullscreen_exit_count,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }, room=monitor_room)

                    # If threshold exceeded, force submit exam
                    if exceeded and session.status == "IN_PROGRESS":
                        policy_auto_submit = True
                        if session.schedule and session.schedule.exam:
                            policy = ExamSecurityService.resolve_policy(db, session.schedule.exam_id)
                            policy_auto_submit = policy.auto_submit_on_threshold

                        if policy_auto_submit:
                            ExamSessionService.submit_exam(
                                db, session.session_token,
                                SubmitExamRequest(submit_type="AUTO_VIOLATION"),
                                skip_auth_check=True
                            )
                            max_limit = AnticheatService.resolve_max_violations(db, session)
                            # Notify student client to lock and submit
                            await sio.emit("force_submit", {
                                "reason": f"Vượt quá số lần vi phạm an toàn cho phép ({max_limit} lần). Bài thi đã tự động nộp."
                            }, to=sid)

            return {"status": "ok", "threshold_exceeded": exceeded}
        finally:
            db.close()

    @sio.event
    async def disconnect(sid):
        """Handle student socket disconnect."""
        if sid in active_sockets:
            sock_info = active_sockets.pop(sid)
            session_id = sock_info["session_id"]
            room_code = sock_info["room_code"]

            monitor_room = f"monitor_{room_code}"
            await sio.emit("student_status_change", {
                "session_id": session_id,
                "student_id": sock_info["student_id"],
                "student_name": sock_info["student_name"],
                "status": "DISCONNECTED",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, room=monitor_room)
