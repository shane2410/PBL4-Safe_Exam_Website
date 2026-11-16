from typing import List
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.dependencies.client_identity import ClientIdentity, get_client_identity
from app.models.user import User
from app.models.exam_session import ExamSession
from app.models.exam_schedule import ExamSchedule
from app.schemas.exam_session_schema import (
    JoinExamRequest, ExamTakingStateResponse, SaveAnswerRequest, SubmitExamRequest, ExamResultResponse
)
from app.schemas.client_attestation_schema import ClientIdentityResponse
from app.services.exam_session_service import ExamSessionService
from app.services.attestation_service import AttestationService

router = APIRouter(prefix="/exam-sessions", tags=["Exam Taking & Sessions"])

@router.post("/join", response_model=ExamTakingStateResponse)
def join_exam(
    data: JoinExamRequest,
    request: Request,
    db: Session = Depends(get_db),
    identity: ClientIdentity = Depends(get_client_identity),
    current_user: User = Depends(require_role(["STUDENT", "ADMIN", "TEACHER"]))
):
    """
    Thí sinh vào phòng thi bằng mã phòng.
    Trả về đề thi với QuestionPublic (KHÔNG có is_correct) + security_policy đã resolve.

    Lưu ý Phase 0: nếu đề bật cờ bắt buộc Safe Exam Browser nhưng client không
    được xác thực thành công, phiên vẫn được tạo ở `restricted_mode=true` và
    ghi log UNAUTHORIZED_CLIENT làm bằng chứng phục tra.
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return ExamSessionService.join_exam(
        db=db,
        room_code=data.room_code,
        student_id=current_user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        client_identity=identity,
    )


@router.get("/{session_token}/identity", response_model=ClientIdentityResponse)
def get_session_identity(
    session_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Thông tin định danh client mà server đã ghi nhận cho phiên thi."""
    session = db.query(ExamSession).filter(ExamSession.session_token == session_token).first()
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên thi")

    user_role = current_user.role.code if current_user.role else "STUDENT"
    if user_role == "STUDENT" and session.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền xem thông tin phiên thi này")

    return ClientIdentityResponse(
        client_type=session.client_type,
        client_version=session.client_version,
        client_hash=session.client_hash,
        device_fingerprint=session.device_fingerprint,
        attestation_status=session.attestation_status,
    )

@router.post("/save-answer")
def save_answer(
    data: SaveAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Auto-save an individual answer for the active session (verifies user ownership).

    `session_token` nằm trong body (`SaveAnswerRequest.session_token`), không phải
    query param — khai báo sai kiểu sẽ khiến mọi lần tự lưu trả 422.
    """
    return ExamSessionService.save_answer(db, data.session_token, data, current_user=current_user)

@router.post("/submit", response_model=ExamResultResponse)
def submit_exam(
    data: SubmitExamRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit exam, finalize session, and trigger automatic grading (verifies user ownership)."""
    if not data.session_token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Thiếu session_token",
        )
    return ExamSessionService.submit_exam(db, data.session_token, data, current_user=current_user)

@router.get("/my-results", response_model=List[ExamResultResponse])
def get_my_results(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List exam results for current logged-in student."""
    sessions = db.query(ExamSession).options(
        joinedload(ExamSession.student),
        joinedload(ExamSession.schedule).joinedload(ExamSchedule.exam)
    ).filter(
        ExamSession.student_id == current_user.id,
        ExamSession.status == "SUBMITTED"
    ).order_by(ExamSession.submitted_at.desc()).all()

    results = []
    for s in sessions:
        exam = s.schedule.exam if s.schedule else None
        student_name = s.student.full_name if s.student else "Thí sinh"
        student_code = s.student.student_code if s.student else "N/A"
        exam_title = exam.title if exam else "Đề thi"
        total_score_val = float(exam.total_score) if exam else 10.0

        results.append(ExamResultResponse(
            session_id=s.id,
            student_name=student_name,
            student_code=student_code,
            exam_title=exam_title,
            final_score=float(s.final_score) if s.final_score is not None else 0.0,
            total_score=total_score_val,
            submit_type=s.submit_type or "MANUAL",
            status=s.status,
            started_at=s.started_at,
            submitted_at=s.submitted_at,
            risk_score=s.risk_score,
            tab_switch_count=s.tab_switch_count,
            fullscreen_exit_count=s.fullscreen_exit_count
        ))
    return results
