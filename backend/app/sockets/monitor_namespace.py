from app.sockets.socket_server import sio
from app.sockets.exam_namespace import active_sockets
from app.core.database import SessionLocal
from app.models.exam_session import ExamSession
from app.services.exam_session_service import ExamSessionService
from app.schemas.exam_session_schema import SubmitExamRequest

def register_monitor_socket_handlers():
    @sio.event
    async def join_monitor_room(sid, data):
        """Teacher joins live monitor room for a given exam schedule."""
        room_code = data.get("room_code")
        if not room_code:
            return {"status": "error", "message": "Missing room_code"}

        monitor_room = f"monitor_{room_code.upper()}"
        await sio.enter_room(sid, monitor_room)
        
        # Return currently active students in this room
        active_list = [
            v for v in active_sockets.values() if v.get("room_code") == room_code.upper()
        ]
        return {
            "status": "success",
            "monitor_room": monitor_room,
            "active_students": active_list
        }

    @sio.event
    async def teacher_force_submit(sid, data):
        """Teacher manually forces submit for a cheating student."""
        session_id = data.get("session_id")
        reason = data.get("reason", "Giám thị cưỡng chế thu bài do phát hiện gian lận")
        
        if not session_id:
            return {"status": "error", "message": "Missing session_id"}

        db = SessionLocal()
        try:
            session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
            if not session or session.status == "SUBMITTED":
                return {"status": "error", "message": "Session already submitted or not found"}

            ExamSessionService.submit_exam(
                db, session.session_token,
                SubmitExamRequest(submit_type="AUTO_VIOLATION")
            )

            # Find student sid if connected and emit force_submit
            for student_sid, info in active_sockets.items():
                if info.get("session_id") == session_id:
                    await sio.emit("force_submit", {"reason": reason}, to=student_sid)
                    break

            # Broadcast to monitor room
            room_code = session.schedule.room_code
            await sio.emit("student_force_submitted", {
                "session_id": session_id,
                "student_name": session.student.full_name,
                "reason": reason
            }, room=f"monitor_{room_code}")

            return {"status": "success"}
        finally:
            db.close()
