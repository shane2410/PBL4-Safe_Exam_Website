from fastapi import APIRouter, Depends, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.client_identity import get_client_identity, ClientIdentity
from app.models.user import User
from app.schemas.auth_schema import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.schemas.client_device_schema import (
    ClientDeviceRegisterRequest,
    ClientDeviceResponse,
)
from app.schemas.client_attestation_schema import (
    ClientAttestRequest, ClientAttestResponse, ClientNonceResponse
)
from app.services.auth_service import AuthService
from app.services.attestation_service import AttestationService
from app.services.client_device_service import ClientDeviceService

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


@router.post("/client-devices", response_model=ClientDeviceResponse)
def register_client_device(
    payload: ClientDeviceRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Đăng ký khoá công khai Ed25519 của thiết bị (mục 1.5.2 PLAN.md).

    Endpoint này KHÔNG làm cho thiết bị trở thành SEB hợp lệ — nó chỉ lưu public
    key để `client-attest` xác minh được chữ ký sau đó. Giá trị thật nằm ở chỗ
    server KHÔNG THỂ tự sinh chữ ký hợp lệ.

    Gọi lại với cùng public key trả `already_registered=true` để client khôi
    phục sau khi thí sinh cài lại máy mà không tạo bản ghi rác.
    """
    return ClientDeviceService.register(db, current_user, payload)


# --- Client attestation (Phase 0 — xác thực Safe Exam Browser Client) ---
# Xem docs/PLAN.md mục 0.3. Web client KHÔNG cần gọi 2 endpoint này.

@router.post("/client-nonce", response_model=ClientNonceResponse)
def request_client_nonce(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bước 1/2 của challenge-response: server cấp nonce dùng 1 lần, hạn 30 giây.

    Endpoint này KHÔNG tiết lộ gì bí mật — nó chỉ chứng minh web client cần policy.
    Chỉ khi bước 2 thành công thì mới xác lập được `attestation_key`.
    """
    nonce, ttl = AttestationService.issue_nonce(db, current_user)
    return {"nonce": nonce, "expires_in": ttl}


@router.post("/client-attest", response_model=ClientAttestResponse)
def attest_client(
    payload: ClientAttestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bước 2/2: client gửi chữ ký HMAC-SHA256 để chứng minh là SEB Client thật.

    message   = "nonce|client_version|device_fingerprint"
    signature = base64(HMAC-SHA256(message, device_secret))

    Server trả `attestation_key` khi chữ ký hợp lệ — khoá này chỉ được trả
    đúng một lần và dùng để ký các heartbeat sau (Phase 1).
    """
    return AttestationService.verify_attestation(db, current_user, payload)
