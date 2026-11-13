import logging
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User
from app.models.role import Role
from app.schemas.auth_schema import LoginRequest, RegisterRequest, TokenResponse, UserResponse

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    def authenticate_user(db: Session, login_data: LoginRequest) -> TokenResponse:
        user = db.query(User).filter(User.username == login_data.username).first()
        if not user or not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tên đăng nhập hoặc mật khẩu không chính xác",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản này đã bị khoá"
            )
            
        role_code = user.role.code if user.role else "STUDENT"
        access_token = create_access_token(
            subject=user.id,
            role=role_code,
            extra_claims={"username": user.username, "full_name": user.full_name}
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user)
        )

    @staticmethod
    def register_user(db: Session, reg_data: RegisterRequest) -> UserResponse:
        # Check duplicate username
        if db.query(User).filter(User.username == reg_data.username).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên đăng nhập đã tồn tại"
            )
        # Check duplicate email
        if db.query(User).filter(User.email == reg_data.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email này đã được sử dụng"
            )
        
        # Tự đăng ký CÔNG KHAI luôn tạo tài khoản STUDENT.
        # KHÔNG đọc `role_code` từ request: trước đây client gửi "ADMIN"/"TEACHER"
        # là tự tạo được tài khoản quản trị (leo thang đặc quyền). Việc tạo
        # ADMIN/TEACHER chỉ được phép qua POST /api/admin/users (có require_role).
        role = db.query(Role).filter(Role.code == "STUDENT").first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cấu hình vai trò người dùng trong hệ thống chưa được khởi tạo"
            )
            
        user = User(
            username=reg_data.username,
            password_hash=get_password_hash(reg_data.password),
            full_name=reg_data.full_name,
            email=reg_data.email,
            role_id=role.id,
            student_code=reg_data.student_code,
            is_active=True
        )
        try:
            db.add(user)
            db.commit()
            db.refresh(user)
            return UserResponse.model_validate(user)
        except Exception as e:
            db.rollback()
            logger.error("Error registering user %s: %s", reg_data.username, e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Lỗi máy chủ nội bộ khi lưu thông tin người dùng"
            )
