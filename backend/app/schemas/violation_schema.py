from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class ViolationLogCreate(BaseModel):
    event_type: str = Field(..., description="TAB_SWITCH | FULLSCREEN_EXIT | DEVTOOLS_DETECTED | COPY_PASTE_ATTEMPT | RIGHT_CLICK_ATTEMPT | DUPLICATE_LOGIN | CONNECTION_LOST")
    severity: str = Field(default="MEDIUM", description="LOW | MEDIUM | HIGH")
    detail: Optional[Dict[str, Any]] = None
    client_timestamp: datetime

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
