from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_role
from app.models.user import User
from app.models.exam_session import ExamSession
from app.models.exam_schedule import ExamSchedule
from app.schemas.exam_session_schema import (
    JoinExamRequest, ExamTakingStateResponse, SaveAnswerRequest, SubmitExamRequest, ExamResultResponse
)
from app.services.exam_session_service import ExamSessionService

router = APIRouter(prefix="/exam-sessions", tags=["Exam Taking & Sessions"])

@router.post("/join", response_model=ExamTakingStateResponse)
def join_exam(
    data: JoinExamRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["STUDENT", "ADMIN", "TEACHER"]))
):
    """
    Student joins an active exam room by room_code.
    Returns exam details with QuestionPublic schema (NO is_correct).
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    return ExamSessionService.join_exam(
        db=db,
        room_code=data.room_code,
        student_id=current_user.id,
        ip_address=client_ip,
        user_agent=user_agent
    )

@router.post("/save-answer")
def save_answer(
    data: SaveAnswerRequest,
    session_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Auto-save an individual answer for the active session."""
    return ExamSessionService.save_answer(db, session_token, data)

@router.post("/submit", response_model=ExamResultResponse)
def submit_exam(
    data: SubmitExamRequest,
    session_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit exam, finalize session, and trigger automatic grading."""
    return ExamSessionService.submit_exam(db, session_token, data)

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
        exam = s.schedule.exam
        results.append(ExamResultResponse(
            session_id=s.id,
            student_name=s.student.full_name,
            student_code=s.student.student_code,
            exam_title=exam.title,
            final_score=float(s.final_score) if s.final_score is not None else 0.0,
            total_score=float(exam.total_score),
            submit_type=s.submit_type or "MANUAL",
            status=s.status,
            started_at=s.started_at,
            submitted_at=s.submitted_at,
            risk_score=s.risk_score,
            tab_switch_count=s.tab_switch_count,
            fullscreen_exit_count=s.fullscreen_exit_count
        ))
    return results
