from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_role
from app.models.user import User
from app.schemas.question_schema import (
    QuestionAdmin, QuestionCreate, QuestionUpdate, SubjectCreate, SubjectResponse
)
from app.services.question_service import QuestionService

router = APIRouter(prefix="/questions", tags=["Questions & Question Bank"])

# --- Subjects ---
@router.get("/subjects", response_model=List[SubjectResponse])
def get_subjects(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """List all subjects."""
    return QuestionService.get_subjects(db)

@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
def create_subject(
    data: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Create a new subject."""
    return QuestionService.create_subject(db, data)

# --- Questions ---
@router.get("", response_model=List[QuestionAdmin])
def list_questions(
    subject_id: Optional[int] = None,
    difficulty: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """List questions in question bank with optional filtering."""
    return QuestionService.get_questions(db, subject_id, difficulty, search)

@router.get("/{question_id}", response_model=QuestionAdmin)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Get single question detail by ID."""
    return QuestionService.get_question_by_id(db, question_id)

@router.post("", response_model=QuestionAdmin, status_code=status.HTTP_201_CREATED)
def create_question(
    data: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Create a new question with options."""
    return QuestionService.create_question(db, data, current_user.id)

@router.put("/{question_id}", response_model=QuestionAdmin)
def update_question(
    question_id: int,
    data: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Update question and its options."""
    return QuestionService.update_question(db, question_id, data)

@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Delete question by ID."""
    return QuestionService.delete_question(db, question_id)
