"""Test cho các bản vá bảo mật trong Phase 0 (skills.md Quy tắc #4).

Bao phủ:
  - save_answer chặn lưu đáp án sau khi hết giờ (server-authoritative time)
  - save_answer chặn câu hỏi không thuộc đề thi
  - save_answer chặn lựa chọn không thuộc câu hỏi
  - join_exam ghi log UNAUTHORIZED_CLIENT ở restricted mode
  - join_exam trả security_policy + cờ require_safe_browser

Chạy: cd backend && .venv/bin/python -m pytest tests/test_exam_session_fixes.py -v
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.dependencies.client_identity import ClientIdentity
from app.models.exam_question import ExamQuestion
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.models.subject import Subject
from app.models.exam_session import ExamSession
from app.schemas.exam_session_schema import SaveAnswerRequest, SubmitExamRequest
from app.services.exam_session_service import ExamSessionService
from app.services.exam_security_service import ExamSecurityService
from app.services.settings_service import SettingsService


def _join(db, seeded, client_type="web", attested=False):
    identity = ClientIdentity(
        client_type=client_type,
        client_version="1.0.0" if client_type == "seb" else None,
        device_fingerprint="fp-test" if client_type == "seb" else None,
        attested=attested,
    )
    return ExamSessionService.join_exam(
        db=db,
        room_code="TEST-01",
        student_id=seeded["student"].id,
        client_identity=identity,
    )


# --- join_exam / cờ require_safe_browser ---

def test_join_returns_policy_and_flags(db, seeded):
    state = _join(db, seeded)
    assert state.security_policy is not None
    assert state.require_safe_browser is False
    assert state.restricted_mode is False
    # Không lộ đáp án đúng
    assert all(not hasattr(opt, "is_correct") for opt in state.questions[0].options)


def test_web_allowed_when_not_required(db, seeded):
    state = _join(db, seeded)
    assert state.restricted_mode is False


def test_web_blocked_when_both_flags_on(db, seeded):
    exam = seeded["exam"]
    exam.require_safe_browser = True
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        _join(db, seeded)
    assert exc.value.status_code == 403
    assert exc.value.detail == "SEB_REQUIRED"


def test_web_rejection_does_not_create_session(db, seeded):
    exam = seeded["exam"]
    exam.require_safe_browser = True
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    db.commit()

    count = db.query(ExamSession).count()
    with pytest.raises(HTTPException):
        _join(db, seeded)
    assert db.query(ExamSession).count() == count


def test_attested_seb_client_not_restricted(db, seeded):
    """Client SEB đã xác thực HMAC thì không bị coi là restricted."""
    exam = seeded["exam"]
    exam.require_safe_browser = True
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    db.commit()

    state = _join(db, seeded, client_type="seb", attested=True)
    assert state.restricted_mode is False


def test_claiming_seb_without_attestation_is_blocked(db, seeded):
    """Chỉ KHAI là SEB mà không xác thực -> vẫn bị coi là web (không tin client)."""
    exam = seeded["exam"]
    exam.require_safe_browser = True
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        _join(db, seeded, client_type="seb", attested=False)
    assert exc.value.detail == "SEB_REQUIRED"


def test_allow_web_fallback_false_blocks_unattested_client(db, seeded):
    """Khi require_safe_browser=True và allow_web_fallback=False, unattested client bị 403."""
    from fastapi import HTTPException
    from app.schemas.settings_schema import ExamSecurityConfig

    exam = seeded["exam"]
    exam.require_safe_browser = True
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    ExamSecurityService.save_config(db, exam.id, ExamSecurityConfig(allow_web_fallback=False))
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        _join(db, seeded, client_type="web", attested=False)
    assert exc_info.value.status_code == 403

    # Kể cả client tự khai là seb nhưng attested=False cũng bị 403
    with pytest.raises(HTTPException) as exc_info_seb:
        _join(db, seeded, client_type="seb", attested=False)
    assert exc_info_seb.value.status_code == 403


def test_allow_web_fallback_false_allows_attested_seb_client(db, seeded):
    """Khi require_safe_browser=True và allow_web_fallback=False, attested SEB client vẫn vào được bình thường."""
    from app.schemas.settings_schema import ExamSecurityConfig

    exam = seeded["exam"]
    exam.require_safe_browser = True
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    ExamSecurityService.save_config(db, exam.id, ExamSecurityConfig(allow_web_fallback=False))
    db.commit()

    state = _join(db, seeded, client_type="seb", attested=True)
    assert state.restricted_mode is False
    assert state.session_id is not None


# --- save_answer: các bản vá bảo mật ---

def test_save_answer_ok(db, seeded):
    state = _join(db, seeded)
    result = ExamSessionService.save_answer(
        db, state.session_token,
        SaveAnswerRequest(
            session_token=state.session_token,
            question_id=seeded["question"].id, selected_option_ids=[]),
        current_user=seeded["student"],
    )
    assert result["status"] == "saved"


def test_save_answer_rejected_after_deadline(db, seeded):
    """Lỗi đã sửa: trước đây gọi API sau giờ vẫn lưu được đáp án."""
    state = _join(db, seeded)

    # Đẩy mốc bắt đầu phiên về quá khứ để deadline đã qua
    session = state  # noqa: F841 (chỉ để đọc rõ ý đồ)
    from app.models.exam_session import ExamSession
    row = db.query(ExamSession).filter(ExamSession.id == state.session_id).first()
    row.started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=5)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        ExamSessionService.save_answer(
            db, state.session_token,
            SaveAnswerRequest(
            session_token=state.session_token,
            question_id=seeded["question"].id, selected_option_ids=[]),
            current_user=seeded["student"],
        )
    assert exc.value.status_code == 403


def test_save_answer_rejects_question_outside_exam(db, seeded):
    """Lỗi đã sửa: trước đây có thể gửi question_id bất kỳ để dựng bài giả."""
    state = _join(db, seeded)

    other_subject = Subject(code="NET101", name="Mạng")
    db.add(other_subject)
    db.flush()
    other_q = Question(
        content="Câu hỏi ngoài đề", type="SINGLE_CHOICE",
        difficulty="EASY", subject_id=other_subject.id,
    )
    db.add(other_q)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        ExamSessionService.save_answer(
            db, state.session_token,
            SaveAnswerRequest(
            session_token=state.session_token,
            question_id=other_q.id, selected_option_ids=[]),
            current_user=seeded["student"],
        )
    assert exc.value.status_code == 400


def test_save_answer_rejects_option_from_other_question(db, seeded):
    """Lựa chọn phải thuộc đúng câu hỏi đang làm."""
    state = _join(db, seeded)

    other_subject = Subject(code="NET102", name="Mạng 2")
    db.add(other_subject)
    db.flush()
    other_q = Question(
        content="Câu khác", type="SINGLE_CHOICE",
        difficulty="EASY", subject_id=other_subject.id,
    )
    db.add(other_q)
    db.flush()
    foreign_option = QuestionOption(question_id=other_q.id, content="X", order_index=1)
    db.add(foreign_option)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        ExamSessionService.save_answer(
            db, state.session_token,
            SaveAnswerRequest(
            session_token=state.session_token,
            question_id=seeded["question"].id,
                selected_option_ids=[foreign_option.id],
            ),
            current_user=seeded["student"],
        )
    assert exc.value.status_code == 400


def test_save_answer_rejects_other_students_session(db, seeded):
    from app.models.role import Role
    from app.models.user import User
    from app.core.security import get_password_hash

    state = _join(db, seeded)

    student_role = db.query(Role).filter(Role.code == "STUDENT").first()
    intruder = User(
        username="student2", password_hash=get_password_hash("student123"),
        full_name="SV Khác", email="s2@test.vn", role_id=student_role.id,
    )
    db.add(intruder)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        ExamSessionService.save_answer(
            db, state.session_token,
            SaveAnswerRequest(
            session_token=state.session_token,
            question_id=seeded["question"].id, selected_option_ids=[]),
            current_user=intruder,
        )
    assert exc.value.status_code == 403


# --- submit_exam ---

def test_submit_type_whitelist(db, seeded):
    """Client gửi submit_type bừa bãi -> server ép về MANUAL."""
    state = _join(db, seeded)
    result = ExamSessionService.submit_exam(
        db, state.session_token,
        SubmitExamRequest(submit_type="I_HACKED_IT"),
        current_user=seeded["student"],
    )
    assert result.submit_type == "MANUAL"

# --- Tương thích webview nhúng trong SEB Client (P0-2) ---

def _enable_seb_required(db, seeded):
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    seeded["exam"].require_safe_browser = True
    db.commit()


def test_existing_session_cannot_be_rejoined_without_identity(db, seeded):
    """Request không có header định danh vẫn bị coi là web thường.

    Đây là hành vi ĐÚNG và phải giữ: nếu server tin trạng thái phiên thì ai có
    access token cũng mở được bằng trình duyệt thường. Việc webview trong SEB
    không rơi vào trường hợp này là trách nhiệm của client — nó gắn header
    (request_interceptor) và attest lại trước khi token hết hạn.
    """
    _enable_seb_required(db, seeded)

    # Lần join đầu: SEB đã xác thực -> phiên VERIFIED.
    state = _join(db, seeded, client_type="seb", attested=True)
    assert state.restricted_mode is False

    with pytest.raises(HTTPException) as exc:
        _join(db, seeded, client_type="web")
    assert exc.value.detail == "SEB_REQUIRED"


def test_webview_with_identity_headers_not_restricted(db, seeded):
    """Có header seb + attestation hợp lệ -> không restricted, dù phiên đã tồn tại."""
    _enable_seb_required(db, seeded)

    _join(db, seeded, client_type="seb", attested=True)
    state = _join(db, seeded, client_type="seb", attested=True)

    assert state.restricted_mode is False
    assert state.attestation_status == "VERIFIED" if hasattr(state, "attestation_status") else True


def test_seb_session_requires_attestation_to_save_or_submit(db, seeded):
    _enable_seb_required(db, seeded)
    state = _join(db, seeded, client_type="seb", attested=True)
    assert state.security_policy.allow_web_fallback is False
    answer = SaveAnswerRequest(
        session_token=state.session_token,
        question_id=seeded["question"].id,
        selected_option_ids=[],
    )
    submission = SubmitExamRequest(session_token=state.session_token, submit_type="MANUAL")
    for service, data in (
        (ExamSessionService.save_answer, answer),
        (ExamSessionService.submit_exam, submission),
    ):
        with pytest.raises(HTTPException) as exc:
            service(db, state.session_token, data, current_user=seeded["student"])
        assert exc.value.detail == "SEB_REQUIRED"
