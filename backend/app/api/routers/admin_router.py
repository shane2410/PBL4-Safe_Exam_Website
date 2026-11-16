import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import get_password_hash
from app.dependencies.auth import require_role
from app.models.role import Role
from app.models.user import User
from app.schemas.user_admin_schema import (
    AuditLogListResponse,
    PasswordResetRequest,
    UserCreateByAdmin,
    UserListItem,
    UserStats,
    UserUpdate,
)
from app.models.client_device import ClientDevice
from app.models.signed_client_release import SignedClientRelease
from app.schemas.client_device_admin_schema import (
    ClientDeviceAdminResponse,
    ClientDeviceListResponse,
    ClientDeviceRevokeRequest,
)
from app.schemas.client_release_schema import (
    ClientReleaseCreate,
    ClientReleaseResponse,
)
from app.services.audit_service import ACTIONS, AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["User & Audit Management (Admin)"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _get_role(db: Session, code: str) -> Role:
    role = db.query(Role).filter(Role.code == code).first()
    if not role:
        raise HTTPException(status_code=400, detail=f"Vai trò '{code}' không tồn tại")
    return role


# --- Người dùng ---

@router.get("/users", response_model=List[UserListItem])
def list_users(
    role_code: Optional[str] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Danh sách người dùng, hỗ trợ lọc theo vai trò / tìm kiếm / trạng thái."""
    query = db.query(User).options(joinedload(User.role))

    if role_code:
        role = db.query(Role).filter(Role.code == role_code).first()
        if not role:
            return []
        query = query.filter(User.role_id == role.id)

    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(User.full_name.ilike(keyword) | User.username.ilike(keyword))

    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))

    return query.order_by(User.id.desc()).all()


@router.get("/users/stats", response_model=UserStats)
def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Thống kê nhanh số lượng người dùng theo vai trò."""
    role_counts = {
        r.code: r.id
        for r in db.query(Role).all()
    }
    total = db.query(User).count()
    active = db.query(User).filter(User.is_active.is_(True)).count()

    def count_for(code: str) -> int:
        rid = role_counts.get(code)
        return db.query(User).filter(User.role_id == rid).count() if rid else 0

    return UserStats(
        total=total,
        active=active,
        admins=count_for("ADMIN"),
        teachers=count_for("TEACHER"),
        students=count_for("STUDENT"),
    )


@router.post("/users", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateByAdmin,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Admin tạo tài khoản trực tiếp (không qua form đăng ký công khai)."""
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email đã được sử dụng")

    # Mã sinh viên phải là duy nhất
    if payload.student_code:
        exists = db.query(User).filter(User.student_code == payload.student_code).first()
        if exists:
            raise HTTPException(status_code=400, detail="Mã sinh viên đã tồn tại")

    role = _get_role(db, payload.role_code)
    user = User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        full_name=payload.full_name or payload.username,
        email=payload.email,
        role_id=role.id,
        student_code=payload.student_code or None,
        is_active=True,
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi tạo người dùng")

    AuditService.log(db, "USER_CREATE", current_user.id, _client_ip(request))
    return user


@router.put("/users/{user_id}", response_model=UserListItem)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Cập nhật thông tin người dùng."""
    user = db.query(User).options(joinedload(User.role)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    # Không cho Admin tự khoá chính mình — tránh mất quyền truy cập hệ thống
    if user.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Không thể tự khoá tài khoản của chính mình")

    # Không cho xoá quyền Admin cuối cùng của hệ thống
    if (
        user.role.code == "ADMIN"
        and payload.role_code
        and payload.role_code != "ADMIN"
    ):
        remaining = (
            db.query(User)
            .filter(User.role_id == user.role_id, User.is_active.is_(True), User.id != user.id)
            .count()
        )
        if remaining == 0:
            raise HTTPException(
                status_code=400,
                detail="Phải còn ít nhất một quản trị viên khác đang hoạt động",
            )

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.email is not None:
        if db.query(User).filter(User.email == payload.email, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="Email đã được sử dụng")
        user.email = payload.email
    if payload.student_code is not None:
        if db.query(User).filter(User.student_code == payload.student_code, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="Mã sinh viên đã tồn tại")
        user.student_code = payload.student_code or None
    if payload.role_code is not None:
        user.role_id = _get_role(db, payload.role_code).id
    if payload.is_active is not None:
        user.is_active = payload.is_active

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi cập nhật người dùng")

    AuditService.log(db, "USER_UPDATE", current_user.id, _client_ip(request))
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Xoá người dùng.

    Lưu ý: đề xoá cứng sẽ kéo theo xoá luôn phiên thi, đáp án và log vi phạm
    (FK ON DELETE CASCADE) — dữ liệu phục tra sẽ mất. Vì vậy chỉ cho phép xoá
    tài khoản chưa từng thi; tài khoản đã thi phải khoá (is_active=false).
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Không thể xoá chính tài khoản của mình")

    user = db.query(User).options(joinedload(User.role)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    from app.models.exam_session import ExamSession
    session_count = db.query(ExamSession).filter(ExamSession.student_id == user_id).count()
    if session_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tài khoản này đã có {session_count} phiên thi. "
                   "Xoá cứng sẽ mất dữ liệu phục tra — hãy khoá tài khoản thay vì xoá.",
        )

    try:
        db.delete(user)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi xoá người dùng")

    AuditService.log(db, "USER_DELETE", current_user.id, _client_ip(request))
    return {"message": "Đã xoá người dùng thành công"}


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Admin đặt lại mật khẩu cho người dùng."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    user.password_hash = get_password_hash(payload.new_password)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi đặt lại mật khẩu")

    AuditService.log(db, "PASSWORD_RESET", current_user.id, _client_ip(request))
    return {"message": "Đã đặt lại mật khẩu thành công"}


# --- Nhật ký thao tác ---

@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Xem nhật ký thao tác quản trị, mới nhất trước."""
    rows, usernames, total = AuditService.list_logs(
        db, action=action, user_id=user_id, page=page, page_size=page_size
    )
    return AuditLogListResponse(
        items=[
            {
                "id": r.id,
                "user_id": r.user_id,
                "username": usernames.get(r.user_id),
                "action": r.action,
                "ip_address": r.ip_address,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/audit-logs/actions")
def list_audit_actions(
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Danh sách loại thao tác để lọc trên giao diện."""
    return [{"code": code, "label": label} for code, label in ACTIONS.items()]


# --- Thiết bị của thí sinh (Ed25519) ---
#
# Trước bản vá này KHÔNG có API quản trị nào cho `client_devices`: bảng được
# ghi tự động khi client đăng ký, nhưng ADMIN không có cách thu hồi thiết bị
# gian lận, cũng không có cách mở khoá khi thu hồi nhầm.

@router.get("/devices", response_model=ClientDeviceListResponse)
def list_client_devices(
    user_id: Optional[int] = None,
    revoked: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Danh sách thiết bị đã đăng ký, lọc theo thí sinh / trạng thái thu hồi."""
    query = db.query(ClientDevice).options(joinedload(ClientDevice.user))
    if user_id is not None:
        query = query.filter(ClientDevice.user_id == user_id)
    if revoked is True:
        query = query.filter(ClientDevice.revoked_at.isnot(None))
    elif revoked is False:
        query = query.filter(ClientDevice.revoked_at.is_(None))

    rows = query.order_by(ClientDevice.created_at.desc()).all()
    return ClientDeviceListResponse(
        devices=[
            ClientDeviceAdminResponse(
                device_id=d.device_id,
                user_id=d.user_id,
                username=d.user.username if d.user else None,
                label=d.label,
                client_version=d.client_version,
                weak_key_storage=bool(d.weak_key_storage),
                capabilities=d.capabilities,
                unsupported=d.unsupported,
                created_at=d.created_at,
                last_seen_at=d.last_seen_at,
                revoked_at=d.revoked_at,
            )
            for d in rows
        ],
        total=len(rows),
    )


@router.post("/devices/{device_id}/revoke", response_model=ClientDeviceAdminResponse)
def revoke_client_device(
    device_id: str,
    payload: ClientDeviceRevokeRequest,
    request: Request,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Thu hồi (`revoke=true`) hoặc mở khoá (`revoke=false`) một thiết bị.

    Đây là ĐƯỜNG DUY NHẤT mở khoá được: endpoint đăng ký của client sẽ từ chối
    (403) mọi thiết bị đang bị thu hồi, nên thí sinh không thể tự mở khoá bằng
    cách chạy lại client.
    """
    query = db.query(ClientDevice).filter(ClientDevice.device_id == device_id)
    if user_id is not None:
        query = query.filter(ClientDevice.user_id == user_id)
    device = query.first()
    if device is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thiết bị")

    if payload.revoke:
        if device.revoked_at is None:
            device.revoked_at = datetime.now(timezone.utc)
    else:
        device.revoked_at = None

    db.commit()
    db.refresh(device)

    AuditService.log(
        db,
        "DEVICE_REVOKE" if payload.revoke else "DEVICE_UNREVOKE",
        current_user.id,
        _client_ip(request),
    )
    logger.info(
        "%s thiết bị %s (user=%s) bởi admin=%s. Lý do: %s",
        "Thu hồi" if payload.revoke else "Mở khoá",
        device.device_id, device.user_id, current_user.username, payload.reason,
    )

    return ClientDeviceAdminResponse(
        device_id=device.device_id,
        user_id=device.user_id,
        username=device.user.username if device.user else None,
        label=device.label,
        client_version=device.client_version,
        weak_key_storage=bool(device.weak_key_storage),
        capabilities=device.capabilities,
        unsupported=device.unsupported,
        created_at=device.created_at,
        last_seen_at=device.last_seen_at,
        revoked_at=device.revoked_at,
    )


# --- Quản lý bản phát hành SEB Client đã ký (Phase 2) ---

@router.get("/client-releases", response_model=List[ClientReleaseResponse])
def list_client_releases(
    is_active: Optional[bool] = None,
    os_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Lấy danh sách các bản phát hành SEB Client đã được phê duyệt / ký số."""
    query = db.query(SignedClientRelease)
    if is_active is not None:
        query = query.filter(SignedClientRelease.is_active.is_(is_active))
    if os_name:
        query = query.filter(
            (SignedClientRelease.os == os_name.strip().lower())
            | (SignedClientRelease.os == "all")
        )
    return query.order_by(SignedClientRelease.id.desc()).all()


@router.post("/client-releases", response_model=ClientReleaseResponse, status_code=status.HTTP_201_CREATED)
def create_client_release(
    payload: ClientReleaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"])),
):
    """Đăng ký mã băm của một bản phát hành SEB Client mới."""
    # Kiểm tra trùng lặp hash
    existing = db.query(SignedClientRelease).filter(
        SignedClientRelease.hash == payload.hash,
        SignedClientRelease.os == payload.os,
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Bản phát hành với hash này đã tồn tại (version: {existing.version})",
        )

    now = datetime.now(timezone.utc)
    release = SignedClientRelease(
        version=payload.version.strip(),
        hash=payload.hash,
        os=payload.os,
        released_at=now,
        is_active=payload.is_active if payload.is_active is not None else True,
        notes=payload.notes,
    )
    db.add(release)
    db.commit()
    db.refresh(release)

    AuditService.log(
        db,
        "CLIENT_RELEASE_CREATE",
        current_user.id,
        _client_ip(request),
    )
    logger.info(
        "Admin %s đăng ký bản phát hành SEB Client v%s (%s, hash=%s)",
        current_user.username,
        release.version,
        release.os,
        release.hash[:16],
    )
    return release

