"""Test cho cơ chế phát hiện mất kết nối (heartbeat timeout) và đăng nhập trùng.

Vòng quét heartbeat là một trong những cơ chế "răn đe" của hệ thống: trước đây
HEARTBEAT_TIMEOUT_SECONDS có trong config nhưng không được dùng ở đâu, nên cắm máy
giữa kỳ thi không bị ghi nhận. Bộ test này khẳng định cơ chế đó hoạt động.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.models.exam_session import ExamSession
from app.models.violation_log import ViolationLog
from app.services.heartbeat_monitor import scan_stale_connections


def _iso_ago(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FakeSio:
    """Socket.IO giả — chỉ ghi lại các emit để kiểm chứng."""

    def __init__(self):
        self.emitted = []

    async def emit(self, event, payload, room=None, to=None):
        self.emitted.append({"event": event, "payload": payload, "room": room})


@pytest.fixture()
def active_session(db, seeded):
    """Tạo một phiên thi đang IN_PROGRESS."""
    from datetime import timezone as _tz

    row = ExamSession(
        schedule_id=seeded["schedule"].id,
        student_id=seeded["student"].id,
        session_token="sess_hb_test",
        started_at=datetime.now(_tz.utc),
        status="IN_PROGRESS",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_fresh_heartbeat_is_not_marked(db, active_session):
    """Kết nối vừa gửi heartbeat -> KHÔNG được đánh dấu mất kết nối."""
    sockets = {
        "sid-1": {
            "session_id": active_session.id,
            "room_code": "TEST-01",
            "student_id": active_session.student_id,
            "student_name": "Thí Sinh",
            "last_heartbeat": _iso_ago(3),
        }
    }
    sio = FakeSio()

    marked = asyncio.run(scan_stale_connections(sockets, sio, db_factory=lambda: db))

    db.refresh(active_session)
    assert marked == 0
    assert active_session.status == "IN_PROGRESS"
    assert sio.emitted == []


def test_stale_connection_is_marked_and_logged(db, active_session):
    """Im lặng quá ngưỡng -> đánh dấu DISCONNECTED + ghi log CONNECTION_LOST."""
    sockets = {
        "sid-1": {
            "session_id": active_session.id,
            "room_code": "TEST-01",
            "student_id": active_session.student_id,
            "student_name": "Thí Sinh",
            "last_heartbeat": _iso_ago(120),  # vượt xa ngưỡng 30s
        }
    }
    sio = FakeSio()

    marked = asyncio.run(scan_stale_connections(sockets, sio, db_factory=lambda: db))

    db.refresh(active_session)
    logs = (
        db.query(ViolationLog)
        .filter(ViolationLog.session_id == active_session.id)
        .all()
    )

    assert marked == 1
    assert active_session.status == "DISCONNECTED"
    assert len(logs) == 1
    assert logs[0].event_type == "CONNECTION_LOST"
    assert logs[0].detail["reason"]

    # Giám thị đang theo dõi phải nhận được thông báo
    assert len(sio.emitted) == 1
    assert sio.emitted[0]["event"] == "student_status_change"
    assert sio.emitted[0]["room"] == "monitor_TEST-01"


def test_stale_socket_is_removed_from_tracking(db, active_session):
    """Sau khi xử lý, socket không còn trong danh sách theo dõi."""
    sockets = {
        "sid-1": {
            "session_id": active_session.id,
            "room_code": "TEST-01",
            "student_id": active_session.student_id,
            "student_name": "Thí Sinh",
            "last_heartbeat": _iso_ago(120),
        }
    }
    asyncio.run(scan_stale_connections(sockets, FakeSio(), db_factory=lambda: db))
    assert sockets == {}


def test_submitted_session_is_not_touched(db, active_session):
    """Phiên đã nộp bài không được đánh dấu mất kết nối (sẽ gây nhiễu báo cáo)."""
    active_session.status = "SUBMITTED"
    db.commit()

    sockets = {
        "sid-1": {
            "session_id": active_session.id,
            "room_code": "TEST-01",
            "student_id": active_session.student_id,
            "student_name": "Thí Sinh",
            "last_heartbeat": _iso_ago(120),
        }
    }

    marked = asyncio.run(scan_stale_connections(sockets, FakeSio(), db_factory=lambda: db))

    db.refresh(active_session)
    assert marked == 0
    assert active_session.status == "SUBMITTED"


def test_multiple_stale_connections_all_handled(db, seeded):
    """Nhiều phiên cùng mất kết nối -> xử lý hết, không bỏ sót.

    Lưu ý: mỗi sinh viên chỉ có 1 phiên trong 1 ca (UniqueConstraint
    schedule_id + student_id), nên phải tạo nhiều sinh viên khác nhau.
    """
    from datetime import timezone as _tz

    from app.core.security import get_password_hash
    from app.models.role import Role
    from app.models.user import User

    student_role = db.query(Role).filter(Role.code == "STUDENT").first()
    ids = []
    for i in range(3):
        extra = User(
            username=f"sv{i}",
            password_hash=get_password_hash("student123"),
            full_name=f"Sinh Viên {i}",
            email=f"sv{i}@test.vn",
            role_id=student_role.id,
            student_code=f"20T000000{i}",
        )
        db.add(extra)
        db.flush()
        row = ExamSession(
            schedule_id=seeded["schedule"].id,
            student_id=extra.id,
            session_token=f"sess_multi_{i}",
            started_at=datetime.now(_tz.utc),
            status="IN_PROGRESS",
        )
        db.add(row)
        db.flush()
        ids.append(row.id)
    db.commit()

    sockets = {
        f"sid-{i}": {
            "session_id": sid,
            "room_code": "TEST-01",
            "student_id": sid,
            "student_name": f"SV {i}",
            "last_heartbeat": _iso_ago(120),
        }
        for i, sid in enumerate(ids)
    }

    marked = asyncio.run(scan_stale_connections(sockets, FakeSio(), db_factory=lambda: db))

    assert marked == 3
    assert sockets == {}
    for sid in ids:
        db.refresh(db.query(ExamSession).filter(ExamSession.id == sid).first())
    remaining = (
        db.query(ExamSession)
        .filter(ExamSession.id.in_(ids), ExamSession.status == "IN_PROGRESS")
        .count()
    )
    assert remaining == 0
