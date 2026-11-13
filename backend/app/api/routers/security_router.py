from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.dependencies.ownership import ensure_exam_owner
from app.models.exam import Exam
from app.models.user import User
from app.schemas.settings_schema import ExamSecurityConfig
from app.services.exam_security_service import ExamSecurityService

router = APIRouter(prefix="/exams", tags=["Exam Security Policy"])


@router.get("/{exam_id}/security-policy", response_model=ExamSecurityConfig)
def get_security_policy(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Cấu hình khoá an toàn có hiệu lực của đề (GV xem trước khi thi)."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")

    return ExamSecurityService.resolve_policy(db, exam_id)


@router.put("/{exam_id}/security-policy", response_model=ExamSecurityConfig)
def update_security_policy(
    exam_id: int,
    payload: ExamSecurityConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """GV cấu hình các cơ chế khoá an toàn cho đề này (bật/tắt từng guard, đặt ngưỡng)."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")

    # Chỉ chủ sở hữu đề (hoặc ADMIN) mới được đổi cấu hình khoá an toàn: đây là
    # bề mặt ảnh hưởng trực tiếp tới kỳ thi của thí sinh.
    ensure_exam_owner(db, exam, current_user)

    try:
        return ExamSecurityService.save_config(db, exam_id, payload)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi lưu cấu hình khoá an toàn")
