"""Test cho A9: phân quyền sở hữu đề / ca thi / phiên thi.

Trước đây mọi endpoint chỉ kiểm tra ROLE, nên TEACHER bất kỳ sửa/xoá được đề
của người khác, đổi cấu hình khoá an toàn, và tải báo cáo ca thi không phải
mình phụ trách.

Chạy: cd backend && .venv/bin/python -m pytest tests/test_ownership.py -v
"""

from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.core.security import get_password_hash
from app.dependencies.ownership import (
    ensure_exam_owner,
    ensure_schedule_owner,
    ensure_session_owner_by_id,
)
from app.models.exam_schedule import ExamSchedule
from app.models.role import Role
from app.models.user import User


@pytest.fixture()
def teachers(db, seeded):
    role_teacher = Role(code="TEACHER", name="Giảng viên")
    db.add(role_teacher)
    db.flush()

    owner = User(
        username="teacher_owner", password_hash=get_password_hash("t123456"),
        full_name="GV Chủ", email="owner@test.vn", role_id=role_teacher.id,
    )
    other = User(
        username="teacher_other", password_hash=get_password_hash("t123456"),
        full_name="GV Khác", email="other@test.vn", role_id=role_teacher.id,
    )
    db.add_all([owner, other])
    db.commit()

    # Đề thuộc GV chủ
    seeded["exam"].created_by = owner.id
    db.commit()
    return {"owner": owner, "other": other, "admin": seeded["admin"]}


# --- Đề thi ---

def test_admin_can_touch_any_exam(db, seeded, teachers):
    ensure_exam_owner(db, seeded["exam"], teachers["admin"])  # không ném


def test_owner_can_touch_own_exam(db, seeded, teachers):
    ensure_exam_owner(db, seeded["exam"], teachers["owner"])


def test_other_teacher_cannot_touch_exam(db, seeded, teachers):
    with pytest.raises(HTTPException) as exc:
        ensure_exam_owner(db, seeded["exam"], teachers["other"])
    assert exc.value.status_code == 403


def test_exam_without_owner_is_protected(db, seeded, teachers):
    seeded["exam"].created_by = None
    db.commit()
    with pytest.raises(HTTPException) as exc:
        ensure_exam_owner(db, seeded["exam"], teachers["other"])
    assert exc.value.status_code == 403


# --- Ca thi ---

def test_schedule_supervisor_can_access(db, seeded, teachers):
    schedule = seeded["schedule"]
    schedule.supervised_by = teachers["other"].id
    db.commit()
    ensure_schedule_owner(db, schedule, teachers["other"])


def test_exam_creator_can_access_their_schedule(db, seeded, teachers):
    schedule = seeded["schedule"]
    schedule.supervised_by = teachers["other"].id
    db.commit()
    # GV tạo đề vẫn quản lý được ca thi của đề đó
    ensure_schedule_owner(db, schedule, teachers["owner"])


def test_unrelated_teacher_cannot_access_schedule(db, seeded, teachers):
    schedule = seeded["schedule"]
    schedule.supervised_by = teachers["admin"].id  # người khác phụ trách
    db.commit()
    with pytest.raises(HTTPException) as exc:
        ensure_schedule_owner(db, schedule, teachers["other"])
    assert exc.value.status_code == 403


def test_admin_can_access_any_schedule(db, seeded, teachers):
    ensure_schedule_owner(db, seeded["schedule"], teachers["admin"])


# --- Phiên thi ---

def test_student_can_view_own_session(db, seeded):
    from app.dependencies.client_identity import ClientIdentity
    from app.services.exam_session_service import ExamSessionService

    state = ExamSessionService.join_exam(
        db=db, room_code="TEST-01", student_id=seeded["student"].id,
        client_identity=ClientIdentity(client_type="web"),
    )
    session = ensure_session_owner_by_id(db, state.session_id, seeded["student"])
    assert session.id == state.session_id


def test_unrelated_teacher_cannot_view_session(db, seeded, teachers):
    from app.dependencies.client_identity import ClientIdentity
    from app.services.exam_session_service import ExamSessionService

    seeded["schedule"].supervised_by = teachers["admin"].id
    db.commit()

    state = ExamSessionService.join_exam(
        db=db, room_code="TEST-01", student_id=seeded["student"].id,
        client_identity=ClientIdentity(client_type="web"),
    )
    # GV không phụ trách ca, cũng không tạo đề -> 403
    seeded["exam"].created_by = teachers["owner"].id
    db.commit()
    with pytest.raises(HTTPException) as exc:
        ensure_session_owner_by_id(db, state.session_id, teachers["other"])
    assert exc.value.status_code == 403


def test_missing_session_returns_404(db, seeded):
    with pytest.raises(HTTPException) as exc:
        ensure_session_owner_by_id(db, 999999, seeded["admin"])
    assert exc.value.status_code == 404
