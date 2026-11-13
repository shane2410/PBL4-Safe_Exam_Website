"""Test cho vòng quét phiên quá hạn + hành vi ngưỡng vi phạm + reconnect.

Bao phủ các lỗi đã vá:
  - A1: phiên DISCONNECTED vào lại phải trở về IN_PROGRESS, nếu không
        record_violation bỏ qua mọi vi phạm sau đó.
  - A2: ngưỡng chỉ đếm TAB_SWITCH + FULLSCREEN_EXIT, không tính
        DEVTOOLS/COPY_PASTE/CONNECTION_LOST...
  - A4: exams.max_violation_allowed được dùng khi đề chưa có security config.
  - Sweeper: phiên quá deadline được tự nộp AUTO_TIMEOUT; phiên còn trong
    thời gian (hoặc đang trong khoảng grace) thì không bị đụng.

Chạy: cd backend && .venv/bin/python -m pytest tests/test_deadline_and_threshold.py -v
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.dependencies.client_identity import ClientIdentity
from app.models.exam_session import ExamSession
from app.models.violation_log import ViolationLog
from app.schemas.violation_schema import ViolationLogCreate
from app.services.anticheat_service import AnticheatService
from app.services.deadline_sweeper import sweep_expired_sessions
from app.services.exam_session_service import ExamSessionService


def _utcnow():
    return datetime.now(timezone.utc)


def _utcnow_naive():
    return _utcnow().replace(tzinfo=None)


def _join(db, seeded, student=None):
    return ExamSessionService.join_exam(
        db=db,
        room_code="TEST-01",
        student_id=(student or seeded["student"]).id,
        client_identity=ClientIdentity(client_type="web"),
    )


def _violation(event_type: str) -> ViolationLogCreate:
    return ViolationLogCreate(event_type=event_type, client_timestamp=_utcnow())


# --- A1: reconnect sau DISCONNECTED ---

def test_reconnect_restores_in_progress(db, seeded):
    state = _join(db, seeded)
    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()

    session.status = "DISCONNECTED"
    db.commit()

    _join(db, seeded)
    db.refresh(session)
    assert session.status == "IN_PROGRESS"


def test_violations_counted_again_after_reconnect(db, seeded):
    state = _join(db, seeded)
    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()

    session.status = "DISCONNECTED"
    db.commit()

    # Rớt mạng xong vào lại
    _join(db, seeded)

    log, _ = AnticheatService.record_violation(db, session.id, _violation("TAB_SWITCH"))
    assert log is not None, "Vi phạm phải được ghi lại sau khi reconnect"
    db.refresh(session)
    assert session.tab_switch_count == 1


# --- A2: ngưỡng chỉ đếm tab switch + fullscreen exit ---

def test_non_counted_violations_do_not_trigger_threshold(db, seeded):
    """7 lần DevTools + copy/paste không được tự nộp (ngưỡng mặc định 5+3=8)."""
    state = _join(db, seeded)

    for _ in range(5):
        AnticheatService.record_violation(db, state.session_id, _violation("DEVTOOLS_DETECTED"))
    for _ in range(4):
        _, exceeded = AnticheatService.record_violation(
            db, state.session_id, _violation("COPY_PASTE_ATTEMPT")
        )
        assert exceeded is False

    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()
    db.refresh(session)
    # risk score vẫn tăng (metric hiển thị), nhưng không tính vào ngưỡng nộp bài
    assert session.risk_score > 0
    assert session.tab_switch_count == 0
    assert session.fullscreen_exit_count == 0


def test_counted_violations_trigger_threshold(db, seeded):
    state = _join(db, seeded)
    exceeded = False
    for _ in range(5):
        _, exceeded = AnticheatService.record_violation(
            db, state.session_id, _violation("TAB_SWITCH")
        )
    for _ in range(3):
        _, exceeded = AnticheatService.record_violation(
            db, state.session_id, _violation("FULLSCREEN_EXIT")
        )
    assert exceeded is True

    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()
    db.refresh(session)
    assert session.tab_switch_count + session.fullscreen_exit_count == 8


# --- A4: exams.max_violation_allowed được tôn trọng ---

def test_exam_max_violation_allowed_is_used(db, seeded):
    exam = seeded["exam"]
    exam.max_violation_allowed = 3
    db.commit()

    state = _join(db, seeded)
    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()
    assert AnticheatService.resolve_max_violations(db, session) == 3


def test_exam_security_config_overrides_exam_column(db, seeded):
    from app.schemas.settings_schema import ExamSecurityConfig
    from app.services.exam_security_service import ExamSecurityService

    exam = seeded["exam"]
    exam.max_violation_allowed = 3
    db.commit()

    ExamSecurityService.save_config(
        db, exam.id, ExamSecurityConfig(max_tab_switch=4, max_fullscreen_exit=2)
    )
    state = _join(db, seeded)
    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()
    assert AnticheatService.resolve_max_violations(db, session) == 6


# --- Sweeper ---

@pytest.fixture()
def sweeper_db(sqlite_engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)
    db = Session()
    try:
        yield db, Session
    finally:
        db.close()


@pytest.fixture()
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


def test_sweeper_submits_expired_session(db, seeded):
    state = _join(db, seeded)
    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()

    # Đẩy phiên lùi về quá khứ xa hơn cả thời lượng đề lẫn giờ kết thúc ca.
    schedule = seeded["schedule"]
    schedule.start_time = _utcnow_naive() - timedelta(hours=3)
    schedule.end_time = _utcnow_naive() - timedelta(hours=1)
    session.started_at = _utcnow_naive() - timedelta(hours=3)
    db.commit()

    submitted = sweep_expired_sessions(db_factory=lambda: db, grace_seconds=0)
    assert submitted == 1

    db.refresh(session)
    assert session.status == "SUBMITTED"
    assert session.submit_type == "AUTO_TIMEOUT"


def test_sweeper_skips_session_still_running(db, seeded):
    state = _join(db, seeded)
    submitted = sweep_expired_sessions(db_factory=lambda: db, grace_seconds=0)
    assert submitted == 0

    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()
    db.refresh(session)
    assert session.status == "IN_PROGRESS"


def test_sweeper_respects_grace_window(db, seeded):
    state = _join(db, seeded)
    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()

    # Vừa hết giờ đúng 5 giây trước: chưa vượt grace 15s -> chưa nộp.
    schedule = seeded["schedule"]
    schedule.start_time = _utcnow_naive() - timedelta(minutes=60, seconds=5)
    schedule.end_time = _utcnow_naive() + timedelta(hours=1)
    session.started_at = _utcnow_naive() - timedelta(minutes=60, seconds=5)
    db.commit()

    submitted = sweep_expired_sessions(db_factory=lambda: db, grace_seconds=15)
    assert submitted == 0

    db.refresh(session)
    assert session.status == "IN_PROGRESS"


def test_sweeper_is_idempotent(db, seeded):
    state = _join(db, seeded)
    session = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()
    schedule = seeded["schedule"]
    schedule.start_time = _utcnow_naive() - timedelta(hours=3)
    schedule.end_time = _utcnow_naive() - timedelta(hours=1)
    session.started_at = _utcnow_naive() - timedelta(hours=3)
    db.commit()

    assert sweep_expired_sessions(db_factory=lambda: db, grace_seconds=0) == 1
    # Quét lại không được nộp lần nữa (đã SUBMITTED).
    assert sweep_expired_sessions(db_factory=lambda: db, grace_seconds=0) == 0

    db.refresh(session)
    assert session.status == "SUBMITTED"
