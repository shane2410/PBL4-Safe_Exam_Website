from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.question_schema import QuestionPublic
from app.schemas.settings_schema import ExamSecurityConfig

class JoinExamRequest(BaseModel):
    room_code: str = Field(..., min_length=3, max_length=20)
    # Client tự khai loại của mình; server KHÔNG tin tuyệt đối, chỉ dùng cờ này
    # để chọn nhánh xử lý. Việc xác thực thật do attestation_service quyết định.
    client_type: str = Field(default="web")  # web | seb

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
    # --- Phase 0: cấu hình khoá an toàn đã resolve, client dùng để bật/tắt guard ---
    security_policy: Optional[ExamSecurityConfig] = None
    require_safe_browser: bool = False
    restricted_mode: bool = False
    # Bộ đếm vi phạm ĐÃ tích luỹ của phiên. Client dùng để khôi phục thanh
    # "Lần vi phạm x/y" khi thí sinh F5 hoặc vào lại phòng. Trước đây client
    # luôn khởi tạo 0 nên sau khi reload, UI hiện "1/8" trong khi server đã
    # ở 7/8 và có thể tự nộp ngay lần vi phạm kế tiếp.
    tab_switch_count: int = 0
    fullscreen_exit_count: int = 0

class SaveAnswerRequest(BaseModel):
    question_id: int
    selected_option_ids: Optional[List[int]] = None
    fill_blank_text: Optional[str] = None
    client_timestamp: Optional[datetime] = None
    # Token phiên thi. Thuộc về payload của request chứ không phải tham số
    # định tuyến — trước đây khai báo là query param trong khi client gửi trong
    # body, khiến mọi lần tự lưu đều trả 422.
    session_token: str = Field(..., min_length=1, max_length=255)


class SubmitExamRequest(BaseModel):
    submit_type: str = Field(default="MANUAL")  # MANUAL | SHUTDOWN_BUTTON | AUTO_TIMEOUT | AUTO_VIOLATION
    # Bắt buộc khi gọi từ client; để trống ở các lần gọi nội bộ từ server
    # (timeout, ngưỡng vi phạm) vì server đã nắm session_token sẵn.
    session_token: Optional[str] = Field(default=None, max_length=255)

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
