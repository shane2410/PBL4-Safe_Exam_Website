from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.core.security import to_utc_naive

# Whitelist event_type theo SRS mục 8.2 (skills.md Quy tắc #3).
# Client KHÔNG được gửi event_type tự do — nếu không, kẻ xấu có thể gán
# risk weight bất kỳ hoặc làm nhiễu báo cáo vi phạm.
ALLOWED_EVENT_TYPES = {
    "TAB_SWITCH",
    "FULLSCREEN_EXIT",
    "DEVTOOLS_DETECTED",
    "COPY_PASTE_ATTEMPT",
    "RIGHT_CLICK_ATTEMPT",
    "DUPLICATE_LOGIN",
    "CONNECTION_LOST",
    # Phase 0: thí sinh dùng web trong khi đề đang bắt buộc Safe Exam Browser Client.
    # Đây là BẰNG CHỨNG ghi nhận, không phải cơ chế ngăn chặn (skills.md Quy tắc #5).
    "UNAUTHORIZED_CLIENT",
    # Phase 2: Mã băm SHA-256 của SEB Client không khớp với danh sách bản phát hành đã ký.
    "CLIENT_HASH_INVALID",
}

ALLOWED_SEVERITIES = {"LOW", "MEDIUM", "HIGH"}

# Severity do SERVER quyết định từ event_type, không tin giá trị client gửi lên.
EVENT_TYPE_SEVERITY = {
    "TAB_SWITCH": "LOW",
    "FULLSCREEN_EXIT": "MEDIUM",
    "DEVTOOLS_DETECTED": "HIGH",
    "COPY_PASTE_ATTEMPT": "MEDIUM",
    "RIGHT_CLICK_ATTEMPT": "MEDIUM",
    "DUPLICATE_LOGIN": "HIGH",
    "CONNECTION_LOST": "MEDIUM",
    "UNAUTHORIZED_CLIENT": "HIGH",
    "CLIENT_HASH_INVALID": "HIGH",
}


def resolve_severity(event_type: str) -> str:
    """Server-side authority cho mức nghiêm trọng của vi phạm (skills.md Quy tắc #4)."""
    return EVENT_TYPE_SEVERITY.get(event_type, "MEDIUM")


class ViolationLogCreate(BaseModel):
    event_type: str = Field(..., description="TAB_SWITCH | FULLSCREEN_EXIT | DEVTOOLS_DETECTED | COPY_PASTE_ATTEMPT | RIGHT_CLICK_ATTEMPT | DUPLICATE_LOGIN | CONNECTION_LOST")
    detail: Optional[Dict[str, Any]] = None
    client_timestamp: datetime

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, v: str) -> str:
        if v not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"event_type không hợp lệ: {v}")
        return v

    @field_validator("client_timestamp")
    @classmethod
    def _validate_client_timestamp(cls, v: datetime) -> datetime:
        return to_utc_naive(v)


class ViolationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    event_type: str
    severity: str
    detail: Optional[Dict[str, Any]] = None
    client_timestamp: datetime
    server_timestamp: datetime
    reviewed_by: Optional[int] = None


class ForceSubmitRequest(BaseModel):
    session_id: int
    reason: str = Field(..., min_length=3)
