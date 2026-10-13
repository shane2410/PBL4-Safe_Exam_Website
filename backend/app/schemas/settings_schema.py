from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# --- Security policy schema (dùng chung cho cấu hình lưu DB và response) ---
class ExamSecurityConfig(BaseModel):
    """Bộ cấu hình khoá an toàn của một đề thi.

    Đây là schema chuẩn: mọi giá trị ghi xuống DB đều đã được validate qua đây,
    và cùng schema này được trả về cho client (Lớp A web và Lớp B SEB Client).
    """
    require_fullscreen: bool = True
    block_copy_paste: bool = True
    block_devtools: bool = True
    detect_devtools: bool = True
    monitor_tab_switch: bool = True
    lock_navigation: bool = True
    disable_print: bool = True

    # Khi đề bắt buộc SEB nhưng thí sinh dùng web: nếu GV bật cờ này thì vẫn cho
    # thi bằng web ở chế độ hạn chế (bị ghi log + nhân đôi risk score) thay vì chặn.
    allow_web_fallback: bool = True

    max_tab_switch: int = Field(default=5, ge=1, le=100)
    max_fullscreen_exit: int = Field(default=3, ge=1, le=100)
    auto_submit_on_threshold: bool = True
    warn_countdown_seconds: int = Field(default=10, ge=1, le=120)


class SebClientConfig(BaseModel):
    """Cấu hình áp dụng cho Safe Exam Browser Client."""
    min_version: str = "1.0.0"
    heartbeat_interval: int = Field(default=10, ge=1, le=120)
    heartbeat_timeout: int = Field(default=30, ge=5, le=600)
    attestation_required: bool = False


class RequireSafeBrowserSetting(BaseModel):
    value: bool = False


# --- System settings ---
class SystemSettingUpdate(BaseModel):
    """Cập nhật một setting toàn cục. `key` phải nằm trong whitelist."""
    value: bool


class SystemSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    setting_key: str
    setting_value: object
    updated_at: datetime
    updated_by: Optional[int] = None


class SettingsOverviewResponse(BaseModel):
    """Trả về toàn bộ cấu hình liên quan tới cơ chế khoá an toàn cho trang Admin."""
    require_safe_browser_global: bool
    seb_client_config: SebClientConfig
    default_security_config: ExamSecurityConfig
