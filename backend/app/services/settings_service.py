import logging
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models.system_setting import SystemSetting
from app.schemas.settings_schema import ExamSecurityConfig, SebClientConfig

logger = logging.getLogger(__name__)

# Whitelist các key được phép đọc/ghi từ bảng system_settings.
# Ngăn user gõ bất kỳ key nào cũng được lưu — tránh phát sinh rác trong DB.
SETTING_KEY_REQUIRE_SAFE_BROWSER = "require_safe_browser_global"
SETTING_KEY_SEB_CLIENT = "seb_client_config"
SETTING_KEY_DEFAULT_SECURITY = "default_security_config"

ALLOWED_SETTING_KEYS = {
    SETTING_KEY_REQUIRE_SAFE_BROWSER,
    SETTING_KEY_SEB_CLIENT,
    SETTING_KEY_DEFAULT_SECURITY,
}

# Ghi đè cứng: nếu DB chưa seed hoặc JSON hỏng, vẫn phải trả về giá trị hợp lệ.
FALLBACK_VALUES = {
    SETTING_KEY_REQUIRE_SAFE_BROWSER: False,
    SETTING_KEY_SEB_CLIENT: {
        "min_version": "1.0.0",
        "heartbeat_interval": 10,
        "heartbeat_timeout": 30,
        "attestation_required": False,
    },
    SETTING_KEY_DEFAULT_SECURITY: ExamSecurityConfig().model_dump(),
}


class SettingsService:
    """Đọc/ghi cấu hình toàn cục của hệ thống.

    Không dùng cache trong bộ nhớ: lượt đọc rất ít (vài lần mỗi phiên thi),
    cache ở đây chỉ thêm rủi ro đọc giá trị cũ khi GV vừa đổi toggle.
    """

    @staticmethod
    def get_raw(db: Session, key: str) -> Any:
        """Đọc giá trị thô của một setting, có fallback nếu thiếu/hỏng."""
        if key not in ALLOWED_SETTING_KEYS:
            raise ValueError(f"Setting key không hợp lệ: {key}")

        row = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        if row is None:
            logger.info("System setting '%s' chưa tồn tại, dùng giá trị mặc định", key)
            return FALLBACK_VALUES[key]
        return row.setting_value

    @staticmethod
    def set_raw(db: Session, key: str, value: Any, user_id: Optional[int] = None) -> SystemSetting:
        if key not in ALLOWED_SETTING_KEYS:
            raise ValueError(f"Setting key không hợp lệ: {key}")

        row = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        if row is None:
            row = SystemSetting(setting_key=key, setting_value=value, updated_by=user_id)
            db.add(row)
        else:
            row.setting_value = value
            row.updated_by = user_id
        return row

    # --- Typed accessors ---
    @staticmethod
    def get_require_safe_browser_global(db: Session) -> bool:
        """Cờ cấp HỆ THỐNG: bật thì mọi đề có cờ riêng sẽ bắt buộc dùng SEB Client."""
        raw = SettingsService.get_raw(db, SETTING_KEY_REQUIRE_SAFE_BROWSER)
        return bool(raw) if isinstance(raw, (bool, int)) else bool(FALLBACK_VALUES[SETTING_KEY_REQUIRE_SAFE_BROWSER])

    @staticmethod
    def set_require_safe_browser_global(db: Session, value: bool, user_id: Optional[int] = None) -> bool:
        SettingsService.set_raw(db, SETTING_KEY_REQUIRE_SAFE_BROWSER, bool(value), user_id)
        return bool(value)

    @staticmethod
    def get_seb_client_config(db: Session) -> SebClientConfig:
        raw = SettingsService.get_raw(db, SETTING_KEY_SEB_CLIENT)
        try:
            return SebClientConfig.model_validate(raw)
        except Exception:
            logger.warning("seb_client_config trong DB không hợp lệ, dùng mặc định", exc_info=True)
            return SebClientConfig()

    @staticmethod
    def get_default_security_config(db: Session) -> ExamSecurityConfig:
        raw = SettingsService.get_raw(db, SETTING_KEY_DEFAULT_SECURITY)
        try:
            return ExamSecurityConfig.model_validate(raw)
        except Exception:
            logger.warning("default_security_config trong DB không hợp lệ, dùng mặc định", exc_info=True)
            return ExamSecurityConfig()
