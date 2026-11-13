"""Test cho bản vá F6: join response phải trả bộ đếm vi phạm đã tích luỹ.

Bối cảnh: ExamRoom khởi tạo `strikes = {0,0}` cứng. Thí sinh đã vi phạm 7/8,
F5 rồi vào lại thì UI hiện 0/8, nhưng server vẫn ở 7/8 và tự nộp ngay lần vi
phạm kế tiếp. Bản vá trả `tab_switch_count` / `fullscreen_exit_count` trong
`ExamTakingStateResponse` để client khôi phục đúng trạng thái.

Chạy: cd backend && .venv/bin/python -m pytest tests/test_join_violation_counters.py -v
"""

from datetime import datetime, timezone

from app.dependencies.client_identity import ClientIdentity
from app.models.exam_session import ExamSession
from app.schemas.violation_schema import ViolationLogCreate
from app.services.anticheat_service import AnticheatService
from app.services.exam_session_service import ExamSessionService


def _join(db, seeded):
    return ExamSessionService.join_exam(
        db=db,
        room_code="TEST-01",
        student_id=seeded["student"].id,
        client_identity=ClientIdentity(client_type="web"),
    )


def _violation(event_type: str) -> ViolationLogCreate:
    return ViolationLogCreate(
        event_type=event_type,
        client_timestamp=datetime.now(timezone.utc),
    )


def test_join_returns_zero_counters_for_new_session(db, seeded):
    state = _join(db, seeded)
    assert state.tab_switch_count == 0
    assert state.fullscreen_exit_count == 0


def test_join_returns_accumulated_counters_on_reconnect(db, seeded):
    state = _join(db, seeded)
    session_id = state.session_id

    for _ in range(3):
        AnticheatService.record_violation(db, session_id, _violation("TAB_SWITCH"))
    for _ in range(2):
        AnticheatService.record_violation(db, session_id, _violation("FULLSCREEN_EXIT"))

    again = _join(db, seeded)
    assert again.session_id == session_id
    assert again.tab_switch_count == 3
    assert again.fullscreen_exit_count == 2


def test_join_counters_survive_disconnect_and_rejoin(db, seeded):
    state = _join(db, seeded)
    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()

    AnticheatService.record_violation(db, session.id, _violation("TAB_SWITCH"))

    # Mô phỏng bị heartbeat đánh dấu mất kết nối rồi vào lại.
    session.status = "DISCONNECTED"
    db.commit()

    again = _join(db, seeded)
    db.refresh(session)
    assert session.status == "IN_PROGRESS"
    assert again.tab_switch_count == 1


def test_join_counters_do_not_include_non_counted_violations(db, seeded):
    state = _join(db, seeded)
    for _ in range(4):
        AnticheatService.record_violation(
            db, state.session_id, _violation("DEVTOOLS_DETECTED")
        )

    again = _join(db, seeded)
    # risk score có tăng, nhưng bộ đếm hiển thị (theo cơ chế) phải là 0.
    assert again.tab_switch_count == 0
    assert again.fullscreen_exit_count == 0

    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()
    db.refresh(session)
    assert session.risk_score > 0
