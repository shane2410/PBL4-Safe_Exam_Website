"""Xác thực client (Lớp B - Safe Exam Browser Client) bằng challenge-response HMAC.

Mục tiêu: kẻ tấn công dùng curl/Postman giả header `X-Client-Type: seb` KHÔNG
được vào phòng thi khi đề bật cờ bắt buộc SEB.

Cơ chế (xem docs/PLAN.md mục 0.3):
  1. Client xin nonce  -> server sinh nonce ngẫu nhiên gắn user_id + hạn 30s.
  2. Client ký HMAC-SHA256(message, device_secret) với
     message = "nonce|client_version|device_fingerprint".
  3. Server dẫn xuất lại device_secret từ `users.device_secret_salt` + SECRET_KEY,
     dùng `hmac.compare_digest` để so khớp.

Vì sao mạnh hơn header thuần:
  - Nonce dùng 1 lần rồi xoá -> không replay được request đã bắt.
  - `device_secret` KHÔNG lưu rõ trong DB, chỉ lưu salt -> dump DB cũng không dựng lại được.
  - Không có `device_secret` thì không tạo được chữ ký hợp lệ dù biết mọi thứ khác.

LƯU Ý THẬT TRUNG THỰC: đây là cơ chế chống giả mạo ở mức đồ án, KHÔNG phải DRM
thương mại. Kẻ tấn công có source client vẫn có thể chạy client thật một lần để lấy
`device_secret`. Biện pháp mạnh hơn nằm ở Phase 2 (code signing — xem PLAN mục 2.2, hàng C6).
"""

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.client_attestation import ClientAttestation
from app.models.user import User
from app.schemas.client_attestation_schema import (
    ClientAttestRequest,
    ClientAttestResponse,
)

logger = logging.getLogger(__name__)

NONCE_TTL_SECONDS = settings.CLIENT_NONCE_TTL_SECONDS

# Token xác thực ngắn hạn client mang theo khi vào phòng thi.
ATTESTATION_TOKEN_TTL_MINUTES = 5
ATTESTATION_TOKEN_TYPE = "seb_attestation"

# Nonce đang chờ xác minh: nonce -> {user_id, expires_at}
# Ghi chú kiến trúc: đây là store in-memory phục vụ đồ án chạy 1 tiến trình.
# Khi chạy multi-worker phải đổi sang Redis/DB để các worker chia sẻ nonce.
_pending_nonces: Dict[str, Dict] = {}


def _purge_expired_nonces() -> None:
    """Dọn nonce hết hạn để store không phình vô hạn theo thời gian."""
    now = datetime.now(timezone.utc)
    expired = [k for k, v in _pending_nonces.items() if v["expires_at"] < now]
    for k in expired:
        _pending_nonces.pop(k, None)


def build_attest_message(
    nonce: str,
    client_version: str,
    device_fingerprint: str,
    device_id: str = "",
) -> bytes:
    """Chuẩn hoá message trước khi ký — client và server PHẢI dùng cùng công thức.

    `device_id` rỗng là đường HMAC cũ; có giá trị là đường Ed25519 mới. Rỗng
    phải nằm CUỐI chuỗi để hai nhánh không còn chung tiền tố chữ ký.
    """
    return f"{nonce}|{client_version}|{device_fingerprint}|{device_id}".encode("utf-8")


_FAIL_MESSAGES = {
    "NONCE_INVALID_OR_EXPIRED": "Nonce không hợp lệ hoặc đã hết hạn",
    "NONCE_EXPIRED": "Nonce đã hết hạn",
    "NONCE_USER_MISMATCH": "Nonce không thuộc về tài khoản hiện tại",
    "SIGNATURE_MISMATCH": "Chữ ký không hợp lệ",
    "DEVICE_NOT_REGISTERED": "Thiết bị chưa đăng ký khoá công khai",
    "DEVICE_REVOKED": "Thiết bị đã bị thu hồi",
}


def _derive_device_secret(user: User) -> bytes:
    """Dẫn xuất device_secret từ salt + SECRET_KEY (khoá thật không lưu rõ trong DB)."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"device_secret|{user.id}|{user.device_secret_salt or ''}".encode("utf-8"),
        hashlib.sha256,
    ).digest()


def _derive_attestation_key(session_id: Optional[int], key_salt: str) -> bytes:
    """Dẫn xuất khoá ký heartbeat của phiên thi, tương tự device_secret."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"attest_key|{session_id}|{key_salt}".encode("utf-8"),
        hashlib.sha256,
    ).digest()


def _failed(now: datetime, reason: str) -> ClientAttestResponse:
    return ClientAttestResponse(
        attested=False,
        client_type="seb",
        server_time=now,
        verification_reason=reason,
    )


class AttestationService:
    @staticmethod
    def issue_nonce(db: Session, user: User) -> Tuple[str, int]:
        """Sinh nonce 1-lần cho user hiện tại. Trả về (nonce, ttl_seconds)."""
        _purge_expired_nonces()

        nonce = secrets.token_urlsafe(32)
        _pending_nonces[nonce] = {
            "user_id": user.id,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=NONCE_TTL_SECONDS),
        }

        # Đảm bảo user có salt để server dẫn xuất được device_secret
        if not user.device_secret_salt:
            user.device_secret_salt = secrets.token_hex(16)
            db.commit()
            db.refresh(user)

        return nonce, NONCE_TTL_SECONDS

    @staticmethod
    def verify_attestation(
        db: Session,
        user: User,
        data: ClientAttestRequest,
        session_id: Optional[int] = None,
    ) -> ClientAttestResponse:
        """Xác minh chữ ký HMAC. Nếu hợp lệ -> trả attestation_key (chỉ một lần duy nhất)."""
        now = datetime.now(timezone.utc)

        # 1. Nonce phải tồn tại và chưa hết hạn
        pending = _pending_nonces.get(data.nonce)
        if pending is None:
            AttestationService._record_failure(db, session_id, user, "NONCE_INVALID_OR_EXPIRED", data)
            return _failed(now, "Nonce không hợp lệ hoặc đã hết hạn")

        # Nonce dùng đúng 1 lần -> xoá ngay để chặn replay
        _pending_nonces.pop(data.nonce, None)

        if pending["expires_at"] < now:
            AttestationService._record_failure(db, session_id, user, "NONCE_EXPIRED", data)
            return _failed(now, "Nonce đã hết hạn")

        # 2. Nonce phải được cấp cho đúng tài khoản đang xác thực
        if pending["user_id"] != user.id:
            AttestationService._record_failure(db, session_id, user, "NONCE_USER_MISMATCH", data)
            return _failed(now, "Nonce không thuộc về tài khoản hiện tại")

        # 3. Xác minh chữ ký.
        #
        # Ưu tiên Ed25519: nếu client gửi `device_id`, server xác minh bằng
        # public key đã đăng ký. Đây là đường mới (mục 1.5.2 PLAN.md) — server
        # KHÔNG THỂ tự sinh chữ ký hợp lệ vì không giữ private key.
        #
        # HMAC bên dưới là đường CŨ, giữ lại để client đã cài trước không bị
        # đột ngột không vào được phòng thi. Sẽ gỡ khi đủ client dùng Ed25519.
        if data.device_id:
            verified, reason = AttestationService._verify_ed25519(
                db, user, data
            )
            if not verified:
                AttestationService._record_failure(db, session_id, user, reason, data)
                return _failed(now, _FAIL_MESSAGES.get(reason, "Xác thực thất bại"))
        else:
            verified, reason = AttestationService._verify_legacy_hmac(user, data)
            if not verified:
                AttestationService._record_failure(db, session_id, user, reason, data)
                return _failed(now, _FAIL_MESSAGES.get(reason, "Xác thực thất bại"))
            logger.warning(
                "Client %s của user=%s vẫn dùng HMAC cũ — nên chuyển sang Ed25519",
                data.client_version, user.username,
            )

        # 4. Hợp lệ -> sinh attestation_key cho heartbeat, lưu salt để xác minh về sau
        key_salt = secrets.token_hex(16)
        attestation_key = _derive_attestation_key(session_id, key_salt)

        if session_id is not None:
            AttestationService._record(db, session_id, data, verified=True, detail="OK", key_salt=key_salt)

        # Cấp token ngắn hạn để client mang theo khi gọi join_exam.
        # Không có bước này thì kết quả attest chỉ nằm trong response và
        # join_exam không có cách nào biết client đã xác thực hay chưa.
        attestation_token = create_access_token(
            subject=user.id,
            role="SEB_CLIENT",
            expires_delta=timedelta(minutes=ATTESTATION_TOKEN_TTL_MINUTES),
            extra_claims={
                "typ": ATTESTATION_TOKEN_TYPE,
                "ver": data.client_version,
                "fp": data.device_fingerprint,
            },
        )

        return ClientAttestResponse(
            attested=True,
            client_type="seb",
            client_version=data.client_version,
            device_fingerprint=data.device_fingerprint,
            device_id=data.device_id,
            attestation_key=base64.b64encode(attestation_key).decode("utf-8"),
            attestation_token=attestation_token,
            server_time=now,
        )

    @staticmethod
    def _verify_ed25519(db: Session, user: User, data: ClientAttestRequest):
        """Xác minh chữ ký Ed25519 bằng public key của thiết bị. Trả (ok, reason)."""
        from app.services.client_device_service import ClientDeviceService, DeviceKeyError

        try:
            device = ClientDeviceService.get_active(db, user.id, data.device_id)
        except DeviceKeyError as exc:
            return False, str(exc)

        message = build_attest_message(
            data.nonce, data.client_version, data.device_fingerprint, data.device_id
        )
        if not ClientDeviceService.verify_signature(device, message, data.signature):
            return False, "SIGNATURE_MISMATCH"

        ClientDeviceService.touch(db, device)
        return True, "OK"

    @staticmethod
    def _verify_legacy_hmac(user: User, data: ClientAttestRequest):
        """Đường cũ: HMAC với `device_secret`. Giữ để tương thích ngược."""
        device_secret = _derive_device_secret(user)
        message = build_attest_message(
            data.nonce, data.client_version, data.device_fingerprint, ""
        )
        expected_sig = hmac.new(device_secret, message, hashlib.sha256).digest()
        try:
            provided_sig = base64.b64decode(data.signature, validate=True)
        except Exception:
            provided_sig = b""
        if not hmac.compare_digest(expected_sig, provided_sig):
            return False, "SIGNATURE_MISMATCH"
        return True, "OK"

    @staticmethod
    def _record(
        db: Session,
        session_id: int,
        data: ClientAttestRequest,
        verified: bool,
        detail: str,
        key_salt: Optional[str] = None,
    ) -> None:
        db.add(ClientAttestation(
            session_id=session_id,
            client_type="seb",
            client_version=data.client_version,
            device_fingerprint=data.device_fingerprint,
            verified=verified,
            verification_detail=detail,
            key_salt=key_salt,
        ))
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.error("Không ghi được client_attestation cho session %d", session_id, exc_info=True)

    @staticmethod
    def _record_failure(
        db: Session,
        session_id: Optional[int],
        user: User,
        reason: str,
        data: ClientAttestRequest,
    ) -> None:
        """Ghi vết xác thực thất bại phục vụ phúc tra; không ném lỗi ra ngoài."""
        logger.warning(
            "Xác thực client thất bại: user=%s reason=%s version=%s",
            user.username, reason, data.client_version,
        )
        if session_id is None:
            return
        AttestationService._record(db, session_id, data, verified=False, detail=reason)

    @staticmethod
    def is_session_attested(db: Session, session_id: int) -> bool:
        """Phiên thi đã có ít nhất một lần xác thực client thành công hay chưa."""
        return db.query(ClientAttestation).filter(
            ClientAttestation.session_id == session_id,
            ClientAttestation.verified.is_(True),
        ).count() > 0
