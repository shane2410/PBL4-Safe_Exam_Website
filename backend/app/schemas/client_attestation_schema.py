from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

# Loại client: web (Lớp A) hoặc seb (Safe Exam Browser Client - Lớp B)
CLIENT_TYPES = ["web", "seb"]


class ClientNonceResponse(BaseModel):
    """Server cấp nonce 1-lần cho client dùng để ký HMAC."""
    nonce: str
    expires_in: int


class ClientAttestRequest(BaseModel):
    """Client gửi lại chữ ký HMAC để chứng minh mình là SEB Client thật.

    message = nonce + "|" + client_version + "|" + device_fingerprint
    signature = base64(HMAC-SHA256(message, session_secret))
    """
    nonce: str = Field(..., min_length=16, max_length=128)
    client_version: str = Field(..., max_length=20)
    device_fingerprint: str = Field(..., max_length=128)
    signature: str = Field(..., min_length=16, max_length=256)
    # Có `device_id` -> xác minh Ed25519 bằng public key đã đăng ký.
    # Rỗng -> rơi về HMAC cũ (chỉ để tương thích ngược, sẽ gỡ).
    device_id: Optional[str] = Field(default=None, max_length=32)


class ClientAttestResponse(BaseModel):
    """Kết quả xác thực client.

    `attestation_key` chỉ được trả về ĐÚNG MỘT LẦN, dùng để ký các heartbeat sau.
    """
    attested: bool
    client_type: str
    client_version: Optional[str] = None
    device_fingerprint: Optional[str] = None
    device_id: Optional[str] = None
    attestation_key: Optional[str] = None
    # Token ngắn hạn (5 phút) cần gửi kèm ở header `X-Attestation-Token` khi
    # gọi join_exam. Không có nó, server coi client là chưa xác thực.
    attestation_token: Optional[str] = None
    server_time: datetime
    # Chỉ có mặt khi xác thực thất bại — mô tả ngắn gọn lý do cho client hiển thị.
    verification_reason: Optional[str] = None


class ClientIdentityResponse(BaseModel):
    """Thông tin định danh client mà server đã ghi nhận cho phiên thi."""
    client_type: str
    client_version: Optional[str] = None
    client_hash: Optional[str] = None
    device_fingerprint: Optional[str] = None
    attestation_status: str
