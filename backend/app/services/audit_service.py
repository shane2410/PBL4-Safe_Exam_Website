"""Ghi nhật ký thao tác quản trị (audit log).

Bảng `audit_logs` đã có sẵn trong CSDL từ migration đầu tiên nhưng trước đây
KHÔNG có nơi nào ghi vào — nghĩa là toàn bộ cột dữ liệu này luôn rỗng. Module này
đóng lại khoảng trống đó.

Phạm vi ghi: các thao tác quản trị có hậu quả (đổi cấu hình hệ thống, tạo/sửa/xoá
đề thi, quản lý người dùng). KHÔNG ghi các lỗi thường nhật để tránh làm nhiễu nhật ký.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

# Danh sách action chuẩn — dùng lại cho cả ghi log và lọc ở API.
ACTIONS = {
    "LOGIN": "Đăng nhập",
    "USER_CREATE": "Tạo người dùng",
    "USER_UPDATE": "Cập nhật người dùng",
    "USER_DELETE": "Xoá người dùng",
    "PASSWORD_RESET": "Đặt lại mật khẩu",
    "TOGGLE_REQUIRE_SAFE_BROWSER": "Đổi cờ yêu cầu Safe Exam Browser",
    "UPDATE_SECURITY_CONFIG": "Cập nhật cấu hình khoá an toàn",
    "UPDATE_SYSTEM_CONFIG": "Cập nhật cấu hình hệ thống",
    "EXAM_CREATE": "Tạo đề thi",
    "EXAM_UPDATE": "Cập nhật đề thi",
    "EXAM_DELETE": "Xoá đề thi",
    "SCHEDULE_CREATE": "Tạo ca thi",
    "SCHEDULE_UPDATE": "Cập nhật ca thi",
    "QUESTION_CREATE": "Tạo câu hỏi",
    "QUESTION_UPDATE": "Sửa câu hỏi",
    "QUESTION_DELETE": "Xoá câu hỏi",
    "FORCE_SUBMIT": "Giám thị thu bài",
    "DEVICE_REVOKE": "Thu hồi thiết bị",
    "DEVICE_UNREVOKE": "Mở khoá thiết bị",
}


class AuditService:
    @staticmethod
    def log(
        db: Session,
        action: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Ghi một dòng nhật ký. Không ném lỗi ra ngoài.

        Việc ghi log thất bại KHÔNG được làm hỏng thao tác nghiệp vụ đang thực hiện —
        nếu không, một sự cố kỹ thuật nhỏ sẽ chặn cả thao tác quản trị hợp lệ.
        """
        try:
            db.add(AuditLog(user_id=user_id, action=action, ip_address=ip_address))
            db.commit()
        except Exception:
            db.rollback()
            logger.error("Không ghi được audit log cho action=%s", action, exc_info=True)

    @staticmethod
    def list_logs(
        db: Session,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ):
        """Lấy nhật ký có phân trang, mới nhất trước."""
        from app.models.user import User

        query = db.query(AuditLog)
        if action:
            query = query.filter(AuditLog.action == action)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        total = query.count()
        rows = (
            query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        usernames = {
            u.id: u.username
            for u in db.query(User).filter(User.id.in_([r.user_id for r in rows if r.user_id])).all()
        }

        return rows, usernames, total
