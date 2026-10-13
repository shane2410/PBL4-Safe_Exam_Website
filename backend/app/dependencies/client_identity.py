from typing import Optional
from fastapi import Depends, Header
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.client_attestation_schema import CLIENT_TYPES

# Header do client tự khai. Giá trị này KHÔNG đáng tin — nó chỉ được dùng để
# chọn nhánh xử lý. Việc quyết định client có phải SEB thật hay không
# do AttestationService (challenge-response HMAC) quyết định — xem Quy tắc #4.
HEADER_CLIENT_TYPE = "X-Client-Type"
HEADER_CLIENT_VERSION = "X-Client-Version"
HEADER_DEVICE_FINGERPRINT = "X-Device-Fingerprint"
HEADER_ATTESTATION_TOKEN = "X-Attestation-Token"

# Kí hiệu claim để phân biệt token xác thực client với access token đăng nhập.
ATTESTATION_TOKEN_TYPE = "seb_attestation"


def verify_attestation_token(token: str, user_id: int, fingerprint: Optional[str]) -> bool:
    """Kiểm tra token xác thực do AttestationService cấp sau khi challenge-response thành công.

    Token ngắn hạn (5 phút), ký bằng SECRET_KEY, ràng buộc với user và fingerprint.
    """
    if not token:
        return False

    payload = decode_access_token(token)
    if not payload:
        return False
    if payload.get("typ") != ATTESTATION_TOKEN_TYPE:
        return False

    try:
        if int(payload.get("sub", -1)) != user_id:
            return False
    except (TypeError, ValueError):
        return False

    # Token phải khớp fingerprint client khai ở header, chặn việc chuyển token
    # sang máy khác trong thời gian còn hiệu lực.
    token_fp = payload.get("fp")
    if fingerprint and token_fp != fingerprint:
        return False

    return True


class ClientIdentity:
    """Định danh client cho request hiện tại."""

    __slots__ = ("client_type", "client_version", "device_fingerprint", "attested")

    def __init__(
        self,
        client_type: str = "web",
        client_version: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
        attested: bool = False,
    ) -> None:
        self.client_type = client_type
        self.client_version = client_version
        self.device_fingerprint = device_fingerprint
        self.attested = attested

    @property
    def is_seb(self) -> bool:
        return self.client_type == "seb"


def get_client_identity(
    current_user: User = Depends(get_current_user),
    x_client_type: Optional[str] = Header(default=None, alias=HEADER_CLIENT_TYPE),
    x_client_version: Optional[str] = Header(default=None, alias=HEADER_CLIENT_VERSION),
    x_device_fingerprint: Optional[str] = Header(default=None, alias=HEADER_DEVICE_FINGERPRINT),
    x_attestation_token: Optional[str] = Header(default=None, alias=HEADER_ATTESTATION_TOKEN),
) -> ClientIdentity:
    """Đọc định danh client từ header. Giá trị rác -> mặc định an toàn về 'web'."""
    client_type = (x_client_type or "web").strip().lower()
    if client_type not in CLIENT_TYPES:
        client_type = "web"

    version = (x_client_version or "").strip()[:20] or None
    fingerprint = (x_device_fingerprint or "").strip()[:128] or None

    # Chỉ coi là SEB Client đã xác thực khi token hợp lệ — không dựa vào header.
    attested = False
    if client_type == "seb" and x_attestation_token:
        attested = verify_attestation_token(x_attestation_token, current_user.id, fingerprint)

    return ClientIdentity(
        client_type=client_type,
        client_version=version,
        device_fingerprint=fingerprint,
        attested=attested,
    )
