from datetime import datetime, timezone
from typing import Dict, Any
from app.sockets.socket_server import sio
from app.core.database import SessionLocal
from app.models.exam_session import ExamSession
from app.schemas.violation_schema import ViolationLogCreate
from app.services.anticheat_service import AnticheatService
from app.services.exam_session_service import ExamSessionService
from app.schemas.exam_session_schema import SubmitExamRequest

# In-memory mapping of sid -> session info {session_token, session_id, room_code, student_id, student_name}
active_sockets: Dict[str, Dict[str, Any]] = {}

def register_exam_socket_handlers():
    @sio.event
    async def connect(sid, environ, auth):
        pass

    @sio.event
    async def join_exam_room(sid, data):
        """Student joins exam room socket."""
        room_code = data.get("room_code")
        session_token = data.get("session_token")
        
        if not room_code or not session_token:
            return {"status": "error", "message": "Missing room_code or session_token"}

        db = SessionLocal()
        try:
            session = db.query(ExamSession).filter(ExamSession.session_token == session_token).first()
            if not session or session.status == "SUBMITTED":
                return {"status": "error", "message": "Invalid or finished session"}

            room_name = f"room_{room_code.upper()}"
            await sio.enter_room(sid, room_name)

            active_sockets[sid] = {
                "session_token": session_token,
                "session_id": session.id,
                "room_code": room_code.upper(),
                "student_id": session.student_id,
                "student_name": session.student.full_name,
                "student_code": session.student.student_code,
                "last_heartbeat": datetime.now(timezone.utc).isoformat()
            }

            # Notify monitor room (Teachers)
            monitor_room = f"monitor_{room_code.upper()}"
            await sio.emit("student_status_change", {
                "session_id": session.id,
                "student_id": session.student_id,
                "student_name": session.student.full_name,
                "student_code": session.student.student_code,
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
        """Student exam client reports a security violation event."""
        if sid not in active_sockets:
            return {"status": "error", "message": "Socket not registered"}

        sock_info = active_sockets[sid]
        session_id = sock_info["session_id"]
        room_code = sock_info["room_code"]

        event_type = data.get("type", "TAB_SWITCH")
        severity = data.get("severity", "MEDIUM")
        detail = data.get("detail", {})
        client_ts_str = data.get("clientTimestamp")
        
        try:
            client_ts = datetime.fromisoformat(client_ts_str) if client_ts_str else datetime.now(timezone.utc)
        except Exception:
            client_ts = datetime.now(timezone.utc)

        v_create = ViolationLogCreate(
            event_type=event_type,
            severity=severity,
            detail=detail,
            client_timestamp=client_ts
        )

        db = SessionLocal()
        try:
            v_log, exceeded = AnticheatService.record_violation(db, session_id, v_create)
            if v_log:
                session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
                
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
                if exceeded:
                    ExamSessionService.submit_exam(
                        db, session.session_token,
                        SubmitExamRequest(submit_type="AUTO_VIOLATION")
                    )
                    # Notify student client to lock and submit
                    await sio.emit("force_submit", {
                        "reason": f"Vượt quá số lần vi phạm an toàn cho phép ({session.schedule.exam.max_violation_allowed} lần). Bài thi đã tự động nộp."
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
