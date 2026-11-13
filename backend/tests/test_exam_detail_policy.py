"""Test cho bản vá ExamEditor (F4 + A7).

Bối cảnh lỗi:
  * F4: ExamEditor gọi `policyService.getExamPolicy()` (đã bóc `.data`) rồi lại
    đọc `.data` lần nữa -> nhận `undefined` -> policy rơi về mặc định.
  * A7: ExamEditor gọi `/admin/settings` để lấy cờ SEB hệ thống, nhưng endpoint
    đó yêu cầu role ADMIN nên TEACHER luôn nhận 403 -> `Promise.all` reject ->
    trang không bao giờ tải được.

Bản vá: đưa `require_safe_browser_global` (chỉ đọc) vào ExamDetailResponse để
ExamEditor không phải gọi endpoint admin nữa.

Chạy: cd backend && .venv/bin/python -m pytest tests/test_exam_detail_policy.py -v
"""

from app.models.role import Role
from app.models.user import User
from app.core.security import get_password_hash
from app.services.exam_service import ExamService
from app.services.settings_service import SettingsService


def test_exam_detail_exposes_global_flag(db, seeded):
    SettingsService.set_require_safe_browser_global(db, True)
    db.commit()

    detail = ExamService.get_exam_detail(db, seeded["exam"].id)
    assert detail.require_safe_browser_global is True


def test_exam_detail_global_flag_false_by_default(db, seeded):
    detail = ExamService.get_exam_detail(db, seeded["exam"].id)
    assert detail.require_safe_browser_global is False


def test_exam_detail_still_returns_resolved_policy(db, seeded):
    from app.schemas.settings_schema import ExamSecurityConfig
    from app.services.exam_security_service import ExamSecurityService

    ExamSecurityService.save_config(
        db, seeded["exam"].id, ExamSecurityConfig(max_tab_switch=7, max_fullscreen_exit=4)
    )
    detail = ExamService.get_exam_detail(db, seeded["exam"].id)
    assert detail.security_config is not None
    assert detail.security_config.max_tab_switch == 7
    assert detail.security_config.max_fullscreen_exit == 4


def test_teacher_can_read_exam_detail_without_admin_settings(db, seeded):
    """Giáo viên đọc detail đề phải nhận được cả policy lẫn cờ hệ thống."""
    role_teacher = Role(code="TEACHER", name="Giảng viên")
    db.add(role_teacher)
    db.flush()
    teacher = User(
        username="teacher1", password_hash=get_password_hash("teacher123"),
        full_name="Giảng Viên", email="t1@test.vn", role_id=role_teacher.id,
    )
    db.add(teacher)
    db.commit()

    SettingsService.set_require_safe_browser_global(db, True)
    db.commit()

    detail = ExamService.get_exam_detail(db, seeded["exam"].id)
    payload = detail.model_dump()
    assert "require_safe_browser_global" in payload
    assert "security_config" in payload
    assert payload["require_safe_browser_global"] is True
