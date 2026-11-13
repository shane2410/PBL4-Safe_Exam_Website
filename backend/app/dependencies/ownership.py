"""Kiểm tra quyền sở hữu tài nguyên cho TEACHER (A9).

Trước đây mọi endpoint chỉ kiểm tra ROLE (`require_role(["ADMIN","TEACHER"])`),
nên bất kỳ giảng viên nào cũng sửa/xoá được đề của người khác, đổi cấu hình
khoá an toàn của đề không phải mình phụ trách, và tải báo cáo kết quả của ca
thi bất kỳ.

Quy ước phân quyền:
  * ADMIN: toàn quyền.
  * TEACHER: chỉ thao tác trên đề mình tạo (`exams.created_by`) và ca thi mình
    phụ trách (`exam_schedules.supervised_by`), hoặc ca thi thuộc đề mình tạo.

Đọc danh sách/chi tiết đề vẫn mở cho mọi TEACHER (ngân hàng đề dùng chung),
chỉ các thao tác GHI và BÁO CÁO mới bị giới hạn theo chủ sở hữu.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.exam_schedule import ExamSchedule
from app.models.exam_session import ExamSession
from app.models.user import User


def _role_of(user: User) -> str:
    return user.role.code if user.role else "STUDENT"


def _is_admin(user: User) -> bool:
    return _role_of(user) == "ADMIN"


def _forbidden(what: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Bạn không có quyền thao tác trên {what} này",
    )


def ensure_exam_owner(db: Session, exam: Exam, user: User) -> None:
    """Chặn TEACHER sửa/xoá đề của người khác."""
    if _is_admin(user):
        return
    if exam.created_by is None or exam.created_by != user.id:
        raise _forbidden("đề thi")


def ensure_exam_owner_by_id(db: Session, exam_id: int, user: User) -> Exam:
    """Như trên nhưng nhận exam_id; trả về Exam để dùng tiếp."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")
    ensure_exam_owner(db, exam, user)
    return exam


def ensure_schedule_owner(
    db: Session, schedule: ExamSchedule, user: User, exam: Exam | None = None
) -> None:
    """Chặn TEACHER thao tác/báo cáo ca thi không thuộc phạm vi phụ trách."""
    if _is_admin(user):
        return
    if schedule.supervised_by is not None and schedule.supervised_by == user.id:
        return
    # Ca thi chưa gán người phụ trách: cho phép GV tạo đề tương ứng quản lý.
    owner_exam = exam
    if owner_exam is None and schedule.exam_id:
        owner_exam = db.query(Exam).filter(Exam.id == schedule.exam_id).first()
    if owner_exam is not None and owner_exam.created_by == user.id:
        return
    raise _forbidden("ca thi")


def ensure_schedule_owner_by_id(db: Session, schedule_id: int, user: User) -> ExamSchedule:
    schedule = db.query(ExamSchedule).filter(ExamSchedule.id == schedule_id).first()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca thi")
    ensure_schedule_owner(db, schedule, user)
    return schedule


def ensure_session_owner_by_id(db: Session, session_id: int, user: User) -> ExamSession:
    """Kiểm tra quyền xem dữ liệu của một phiên thi (dùng cho báo cáo vi phạm)."""
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên thi")
    if _is_admin(user):
        return session
    if session.student_id == user.id:
        return session
    if session.schedule is not None:
        ensure_schedule_owner(db, session.schedule, user)
        return session
    raise _forbidden("phiên thi")
