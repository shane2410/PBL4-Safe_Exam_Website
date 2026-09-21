from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth_schema import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """User login endpoint to receive JWT access token."""
    return AuthService.authenticate_user(db, login_data)

@router.post("/login-form", response_model=TokenResponse)
def login_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """OAuth2 compatible login endpoint for Swagger UI."""
    login_data = LoginRequest(username=form_data.username, password=form_data.password)
    return AuthService.authenticate_user(db, login_data)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(reg_data: RegisterRequest, db: Session = Depends(get_db)):
    """User registration endpoint."""
    return AuthService.register_user(db, reg_data)

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get profile of current logged-in user."""
    return UserResponse.model_validate(current_user)
