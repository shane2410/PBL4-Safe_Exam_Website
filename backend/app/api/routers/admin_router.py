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
from app.services.audit_service import ACTIONS, AuditService

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
