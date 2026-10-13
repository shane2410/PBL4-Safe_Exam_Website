from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.question_schema import QuestionAdmin, SubjectResponse
from app.schemas.auth_schema import UserResponse
from app.schemas.settings_schema import ExamSecurityConfig

class ExamQuestionItem(BaseModel):
    question_id: int
    score: float = 1.0
    order_index: int = 0

class ExamQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    question_id: int
    score: float
    order_index: int
    question: Optional[QuestionAdmin] = None

class ExamCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    subject_id: int
    duration_minutes: int = Field(default=60, ge=5, le=300)
    total_score: float = Field(default=10.0, ge=1.0)
    is_shuffled: bool = True
    max_violation_allowed: int = Field(default=5, ge=1, le=50)
    require_safe_browser: bool = False
    security_config: Optional[ExamSecurityConfig] = None
    questions: List[ExamQuestionItem] = []

class ExamUpdate(BaseModel):
    title: Optional[str] = None
    duration_minutes: Optional[int] = None
    total_score: Optional[float] = None
    is_shuffled: Optional[bool] = None
    max_violation_allowed: Optional[int] = None
    require_safe_browser: Optional[bool] = None
    security_config: Optional[ExamSecurityConfig] = None
    questions: Optional[List[ExamQuestionItem]] = None

class ExamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    subject_id: int
    subject: Optional[SubjectResponse] = None
    duration_minutes: int
    total_score: float
    is_shuffled: bool
    max_violation_allowed: int
    require_safe_browser: bool = False
    created_by: Optional[int] = None
    created_at: datetime
    question_count: Optional[int] = 0

class ExamDetailResponse(ExamResponse):
    exam_questions: List[ExamQuestionResponse] = []
    security_config: Optional[ExamSecurityConfig] = None

# --- Exam Schedule Schemas ---
class ExamScheduleCreate(BaseModel):
    exam_id: int
    room_code: str = Field(..., min_length=3, max_length=20)
    start_time: datetime
    end_time: datetime
    status: str = "SCHEDULED"  # SCHEDULED | ONGOING | FINISHED | CANCELLED

class ExamScheduleUpdate(BaseModel):
    room_code: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None

class ExamScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    exam: Optional[ExamResponse] = None
    room_code: str
    start_time: datetime
    end_time: datetime
    supervised_by: Optional[int] = None
    supervisor: Optional[UserResponse] = None
    status: str
    created_at: datetime
