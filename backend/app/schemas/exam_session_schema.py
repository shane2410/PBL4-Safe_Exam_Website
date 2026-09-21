from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.question_schema import QuestionPublic

class JoinExamRequest(BaseModel):
    room_code: str = Field(..., min_length=3, max_length=20)

class SavedAnswerItem(BaseModel):
    question_id: int
    selected_option_ids: Optional[List[int]] = None
    fill_blank_text: Optional[str] = None

class ExamTakingStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    session_token: str
    room_code: str
    exam_title: str
    duration_minutes: int
    started_at: datetime
    server_time: datetime
    remaining_seconds: int
    max_violation_allowed: int
    questions: List[QuestionPublic]
    saved_answers: Dict[str, Any] = {}

class SaveAnswerRequest(BaseModel):
    question_id: int
    selected_option_ids: Optional[List[int]] = None
    fill_blank_text: Optional[str] = None
    client_timestamp: Optional[datetime] = None

class SubmitExamRequest(BaseModel):
    submit_type: str = Field(default="MANUAL")  # MANUAL | SHUTDOWN_BUTTON | AUTO_TIMEOUT | AUTO_VIOLATION

class ExamResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    student_name: str
    student_code: Optional[str] = None
    exam_title: str
    final_score: Optional[float] = None
    total_score: float
    submit_type: str
    status: str
    started_at: datetime
    submitted_at: Optional[datetime] = None
    risk_score: int
    tab_switch_count: int
    fullscreen_exit_count: int
