from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_role
from app.models.user import User
from app.schemas.exam_schema import (
    ExamCreate, ExamUpdate, ExamResponse, ExamDetailResponse,
    ExamScheduleCreate, ExamScheduleUpdate, ExamScheduleResponse
)
from app.services.exam_service import ExamService

router = APIRouter(prefix="/exams", tags=["Exams & Schedules"])

# --- Exams ---
@router.get("", response_model=List[ExamResponse])
def list_exams(
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """List all created exams."""
    return ExamService.get_exams(db, subject_id)

@router.get("/{exam_id}", response_model=ExamDetailResponse)
def get_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Get exam details with its question list."""
    return ExamService.get_exam_detail(db, exam_id)

@router.post("", response_model=ExamDetailResponse, status_code=status.HTTP_201_CREATED)
def create_exam(
    data: ExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Create a new exam."""
    return ExamService.create_exam(db, data, current_user.id)

@router.put("/{exam_id}", response_model=ExamDetailResponse)
def update_exam(
    exam_id: int,
    data: ExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Update exam parameters and question list."""
    return ExamService.update_exam(db, exam_id, data)

@router.delete("/{exam_id}")
def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Delete an exam."""
    return ExamService.delete_exam(db, exam_id)

# --- Exam Schedules ---
@router.get("/schedules/list", response_model=List[ExamScheduleResponse])
def list_schedules(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER", "STUDENT"]))
):
    """List exam schedules/rooms."""
    return ExamService.get_schedules(db, status_filter)

@router.post("/schedules", response_model=ExamScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    data: ExamScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Create a new exam room schedule."""
    return ExamService.create_schedule(db, data, current_user.id)

@router.put("/schedules/{schedule_id}", response_model=ExamScheduleResponse)
def update_schedule(
    schedule_id: int,
    data: ExamScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Update an exam schedule."""
    return ExamService.update_schedule(db, schedule_id, data)
