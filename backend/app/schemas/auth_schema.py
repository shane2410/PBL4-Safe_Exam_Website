from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4)

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    # KHÔNG có `role_code`: đây là endpoint đăng ký CÔNG KHAI, luôn tạo STUDENT.
    # Tạo ADMIN/TEACHER phải qua POST /api/admin/users (yêu cầu quyền ADMIN).
    student_code: Optional[str] = None

class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    email: str
    role: RoleResponse
    student_code: Optional[str] = None
    is_active: bool
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
