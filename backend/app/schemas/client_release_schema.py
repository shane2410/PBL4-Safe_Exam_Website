from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClientReleaseCreate(BaseModel):
    version: str = Field(..., min_length=1, max_length=50, description="Phiên bản SEB Client (vd: 1.0.0)")
    hash: str = Field(..., min_length=64, max_length=64, description="Mã băm SHA-256 (64 ký tự hex)")
    os: Optional[str] = Field("all", max_length=20, description="Hệ điều hành: windows | macos | linux | all")
    is_active: Optional[bool] = Field(True, description="Trạng thái kích hoạt của bản release")
    notes: Optional[str] = Field(None, max_length=255, description="Ghi chú về bản phát hành")

    @field_validator("hash")
    @classmethod
    def _validate_hash(cls, v: str) -> str:
        clean = v.strip().lower()
        if len(clean) != 64 or not all(c in "0123456789abcdef" for c in clean):
            raise ValueError("Mã băm client phải là chuỗi SHA-256 gồm 64 ký tự hex hợp lệ")
        return clean

    @field_validator("os")
    @classmethod
    def _validate_os(cls, v: Optional[str]) -> str:
        val = (v or "all").strip().lower()
        allowed = {"windows", "macos", "linux", "all"}
        if val not in allowed:
            raise ValueError(f"Hệ điều hành không hợp lệ: {val}. Cho phép: {', '.join(allowed)}")
        return val


class ClientReleaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    hash: str
    os: str
    released_at: datetime
    is_active: bool
    notes: Optional[str] = None
