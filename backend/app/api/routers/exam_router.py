from typing import List, Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_role
from app.dependencies.ownership import (
    ensure_exam_owner_by_id,
    ensure_schedule_owner_by_id,
)
from app.models.user import User
from app.schemas.exam_schema import (
    ExamCreate, ExamUpdate, ExamResponse, ExamDetailResponse,
    ExamScheduleCreate, ExamScheduleUpdate, ExamScheduleResponse
)
from app.services.exam_service import ExamService
from app.services.audit_service import AuditService

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
    request: Request,
    data: ExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Create a new exam."""
    created = ExamService.create_exam(db, data, current_user.id)
    AuditService.log(db, "EXAM_CREATE", current_user.id, request.client.host if request.client else None)
    return created

@router.put("/{exam_id}", response_model=ExamDetailResponse)
def update_exam(
    request: Request,
    exam_id: int,
    data: ExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Update exam parameters and question list."""
    ensure_exam_owner_by_id(db, exam_id, current_user)
    updated = ExamService.update_exam(db, exam_id, data)
    AuditService.log(db, "EXAM_UPDATE", current_user.id, request.client.host if request.client else None)
    return updated

@router.delete("/{exam_id}")
def delete_exam(
    request: Request,
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Delete an exam."""
    ensure_exam_owner_by_id(db, exam_id, current_user)
    result = ExamService.delete_exam(db, exam_id)
    AuditService.log(db, "EXAM_DELETE", current_user.id, request.client.host if request.client else None)
    return result

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
    request: Request,
    data: ExamScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Create a new exam room schedule."""
    created = ExamService.create_schedule(db, data, current_user.id)
    AuditService.log(db, "SCHEDULE_CREATE", current_user.id, request.client.host if request.client else None)
    return created

@router.put("/schedules/{schedule_id}", response_model=ExamScheduleResponse)
def update_schedule(
    request: Request,
    schedule_id: int,
    data: ExamScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Update an exam schedule."""
    ensure_schedule_owner_by_id(db, schedule_id, current_user)
    updated = ExamService.update_schedule(db, schedule_id, data)
    AuditService.log(db, "SCHEDULE_UPDATE", current_user.id, request.client.host if request.client else None)
    return updated
