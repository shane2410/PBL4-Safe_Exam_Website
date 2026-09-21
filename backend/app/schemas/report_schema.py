from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class StudentResultItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    student_id: int
    student_name: str
    student_code: Optional[str] = None
    email: str
    started_at: datetime
    submitted_at: Optional[datetime] = None
    submit_type: Optional[str] = None
    status: str
    final_score: Optional[float] = None
    total_score: float
    risk_score: int
    tab_switch_count: int
    fullscreen_exit_count: int
    violation_count: int

class ExamScheduleStatistics(BaseModel):
    schedule_id: int
    room_code: str
    exam_title: str
    total_candidates: int
    submitted_count: int
    in_progress_count: int
    average_score: float
    highest_score: float
    lowest_score: float
    candidates: List[StudentResultItem] = []
