"""Fixture dùng SQLite in-memory cho test — không phụ thuộc MySQL/XAMPP hay file .env thật.

Cả unit test lẫn API test (`test_api.py`) đều chạy hoàn toàn trên SQLite in-memory
mà không cần MySQL thật đang chạy.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Thiết lập biến môi trường trước khi bất kỳ module app nào được nạp
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENV", "development")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, engine, get_db  # noqa: E402
import app.models  # noqa: F401,E402  (đăng ký toàn bộ model vào Base.metadata)
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.subject import Subject  # noqa: E402
from app.models.question import Question  # noqa: E402
from app.models.question_option import QuestionOption  # noqa: E402
from app.models.exam import Exam  # noqa: E402
from app.models.exam_question import ExamQuestion  # noqa: E402
from app.models.exam_schedule import ExamSchedule  # noqa: E402
from app.models.exam_session import ExamSession  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from seeders.seed_data import seed  # noqa: E402

# Khởi tạo bảng và seed dữ liệu mặc định cho engine chung (dùng bởi TestClient / test_api.py)
Base.metadata.create_all(bind=engine)
try:
    seed()
except Exception:
    pass


@pytest.fixture()
def db():
    """Session SQLite in-memory mới cho mỗi test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def seeded(db):
    """Dữ liệu tối thiểu: 1 admin, 1 thí sinh, 1 môn, 1 đề có 1 câu, 1 ca thi đang mở."""
    role_admin = Role(code="ADMIN", name="Quản trị viên")
    role_student = Role(code="STUDENT", name="Sinh viên")
    db.add_all([role_admin, role_student])
    db.flush()

    admin = User(
        username="admin", password_hash=get_password_hash("admin123"),
        full_name="Admin", email="admin@test.vn", role_id=role_admin.id,
    )
    student = User(
        username="student1", password_hash=get_password_hash("student123"),
        full_name="Thí Sinh", email="s1@test.vn", role_id=role_student.id,
        student_code="20T1020001",
    )
    db.add_all([admin, student])
    db.flush()

    subject = Subject(code="HDH101", name="Hệ điều hành")
    db.add(subject)
    db.flush()

    question = Question(
        content="Câu hỏi kiểm thử?", type="SINGLE_CHOICE",
        difficulty="EASY", subject_id=subject.id,
    )
    db.add(question)
    db.flush()

    db.add_all([
        QuestionOption(question_id=question.id, content="A", is_correct=True, order_index=1),
        QuestionOption(question_id=question.id, content="B", is_correct=False, order_index=2),
    ])

    exam = Exam(
        title="Đề thi kiểm thử", subject_id=subject.id,
        duration_minutes=60, total_score=10, is_shuffled=False,
        max_violation_allowed=5, require_safe_browser=False, created_by=admin.id,
    )
    db.add(exam)
    db.flush()

    db.add(ExamQuestion(exam_id=exam.id, question_id=question.id, score=10, order_index=0))

    schedule = ExamSchedule(
        exam_id=exam.id, room_code="TEST-01",
        start_time=_utcnow_naive() - timedelta(minutes=5),
        end_time=_utcnow_naive() + timedelta(hours=2),
        status="ONGOING",
    )
    db.add(schedule)
    db.commit()

    return {
        "admin": admin, "student": student, "subject": subject,
        "question": question, "exam": exam, "schedule": schedule,
    }
