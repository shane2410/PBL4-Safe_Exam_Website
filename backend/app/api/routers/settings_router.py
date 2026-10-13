from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_role
from app.models.user import User
from app.schemas.settings_schema import (
    ExamSecurityConfig, RequireSafeBrowserSetting, SebClientConfig, SettingsOverviewResponse
)
from app.services.settings_service import SettingsService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin/settings", tags=["System Settings (Admin)"])


@router.get("", response_model=SettingsOverviewResponse)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """Trả toàn bộ cấu hình liên quan cơ chế khoá an toàn cho trang Admin."""
    return {
        "require_safe_browser_global": SettingsService.get_require_safe_browser_global(db),
        "seb_client_config": SettingsService.get_seb_client_config(db),
        "default_security_config": SettingsService.get_default_security_config(db),
    }


@router.get("/require-safe-browser", response_model=RequireSafeBrowserSetting)
def get_require_safe_browser(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """Toggle cấp hệ thống: chỉ cho phép thi qua Safe Exam Browser Client."""
    return {"value": SettingsService.get_require_safe_browser_global(db)}


@router.put("/require-safe-browser", response_model=RequireSafeBrowserSetting)
def set_require_safe_browser(
    payload: RequireSafeBrowserSetting,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """Bật/tắt yêu cầu bắt buộc dùng Safe Exam Browser Client cho toàn hệ thống.

    Lưu ý: đề thi có `require_safe_browser = false` vẫn thi được bằng web,
    kể cả khi cờ này đang bật — xem ExamSecurityService.is_safe_browser_required.
    """
    try:
        value = SettingsService.set_require_safe_browser_global(db, payload.value, current_user.id)
        db.commit()
        db.refresh(current_user)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi cập nhật cấu hình")

    AuditService.log(
        db, "TOGGLE_REQUIRE_SAFE_BROWSER", current_user.id,
        request.client.host if request.client else None,
    )
    return {"value": value}


@router.put("/seb-client-config", response_model=SebClientConfig)
def set_seb_client_config(
    payload: SebClientConfig,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """Cập nhật cấu hình áp dụng cho Safe Exam Browser Client (Lớp B)."""
    SettingsService.set_raw(
        db, "seb_client_config", payload.model_dump(), current_user.id
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi cập nhật cấu hình SEB Client")
    AuditService.log(db, "UPDATE_SYSTEM_CONFIG", current_user.id,
                     request.client.host if request.client else None)
    return payload


@router.put("/default-security-config", response_model=ExamSecurityConfig)
def set_default_security_config(
    payload: ExamSecurityConfig,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    """Cập nhật bộ cấu hình khoá an toàn MẶC ĐỊNH áp dụng cho đề chưa cấu hình riêng."""
    SettingsService.set_raw(
        db, "default_security_config", payload.model_dump(), current_user.id
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi cập nhật cấu hình mặc định")
    AuditService.log(db, "UPDATE_SECURITY_CONFIG", current_user.id,
                     request.client.host if request.client else None)
    return payload
