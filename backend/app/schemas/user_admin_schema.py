from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, EmailStr


class UserUpdate(BaseModel):
    """Cập nhật người dùng. Không cho sửa username/email tùy ý — chỉ Admin mới gọi được."""
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    role_code: Optional[str] = None  # ADMIN | TEACHER | STUDENT
    student_code: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = None


class UserCreateByAdmin(UserUpdate):
    """Tạo người dùng mới từ trang quản trị (khác về hình thức với đăng ký công khai)."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    role_code: str = Field(default="STUDENT")


class PasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=6)


class UserListItem(BaseModel):
    """Danh sách người dùng cho bảng quản trị — có thêm thống kê hoạt động."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    email: str
    student_code: Optional[str] = None
    is_active: bool
    created_at: datetime
    role: "RoleSummary"


class RoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class UserStats(BaseModel):
    """Thống kê tổng quan cho trang Người dùng."""
    total: int
    active: int
    admins: int
    teachers: int
    students: int


class AuditLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: List[AuditLogItem]
    total: int
    page: int
    page_size: int
