"""Đăng ký và quản lý khoá công khai Ed25519 của thiết bị.

Thay thế mô hình khoá đối xứng (`device_secret`) — xem `docs/PLAN.md` mục 1.5.2.

Điểm khác biệt bản chất: server chỉ giữ PUBLIC key, nên **không thể** tự tạo
chữ ký hợp lệ. Với HMAC, server giữ khoá dùng chung nên về lý thuyết ký thay
client được; ở đây điều đó bị loại bỏ bằng toán học, không phải bằng thủ thuật.
"""

import base64
import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.client_device import ClientDevice
from app.models.user import User
from app.schemas.client_device_schema import (
    ClientDeviceRegisterRequest,
    ClientDeviceResponse,
)

logger = logging.getLogger(__name__)

ED25519_PUBLIC_KEY_BYTES = 32
DEVICE_ID_LENGTH = 16


class DeviceKeyError(Exception):
    """Thiết bị không hợp lệ: chưa đăng ký, bị thu hồi, hoặc khoá sai."""


def device_id_from_public_key(public_key_b64: str) -> str:
    """device_id = sha256(public_key)[:16].

    Ổn định theo khoá nên đổi tên máy hay đổi IP không làm đổi định danh. MAC
    và hostname thì người dùng sửa được, nên không dùng.
    """
    raw = base64.b64decode(public_key_b64)
    return hashlib.sha256(raw).hexdigest()[:DEVICE_ID_LENGTH]


def fingerprint_from_public_key(public_key_b64: str) -> str:
    raw = base64.b64decode(public_key_b64)
    return hashlib.sha256(raw).hexdigest()


def _parse_unsupported(raw: str | None) -> dict[str, str] | None:
    """Đọc lại chuỗi "khoa:ly do;khoa:ly do" thành dict."""
    if not raw:
        return None
    result = {}
    for part in raw.split(";"):
        if ":" in part:
            name, reason = part.split(":", 1)
            result[name] = reason
    return result or None


class ClientDeviceService:
    @staticmethod
    def register(
        db: Session,
        user: User,
        payload: ClientDeviceRegisterRequest,
    ) -> ClientDeviceResponse:
        device_id = device_id_from_public_key(payload.public_key)
        fingerprint = fingerprint_from_public_key(payload.public_key)

        existing = db.query(ClientDevice).filter(
            ClientDevice.user_id == user.id,
            ClientDevice.device_id == device_id,
        ).first()

        if existing is not None:
            # Gọi lại cùng khoá: cập nhật thông tin, không tạo bản ghi mới.
            existing.last_seen_at = datetime.now(timezone.utc)
            existing.label = payload.label or existing.label
            existing.client_version = payload.client_version or existing.client_version
            existing.weak_key_storage = payload.weak_key_storage or existing.weak_key_storage
            if payload.capabilities is not None:
                existing.capabilities = ",".join(payload.capabilities)[:255]
            if payload.unsupported is not None:
                # Lưu dạng "khoa:ly do;khoa:ly do" — đủ để GV đọc trên
                # dashboard mà không cần bảng phụ.
                existing.unsupported = ";".join(
                    f"{k}:{v}" for k, v in payload.unsupported.items()
                )[:255]
            if existing.revoked_at is not None:
                # Khoá bị thu hồi mà giờ client quay lại dùng: cho phép đăng ký
                # lại, nhưng ghi lại sự kiện vì đáng ngờ.
                logger.warning(
                    "Thiết bị %s của user=%s đã bị thu hồi, đăng ký lại",
                    device_id, user.username,
                )
                existing.revoked_at = None
            db.commit()
            db.refresh(existing)
            logger.info("Thiết bị %s đã tồn tại (user=%s)", device_id, user.username)
            return ClientDeviceResponse(
                device_id=existing.device_id,
                fingerprint=existing.fingerprint,
                already_registered=True,
                weak_key_storage=existing.weak_key_storage,
                unsupported=_parse_unsupported(existing.unsupported),
            )

        device = ClientDevice(
            user_id=user.id,
            device_id=device_id,
            public_key=payload.public_key,
            fingerprint=fingerprint,
            label=payload.label,
            client_version=payload.client_version,
            weak_key_storage=payload.weak_key_storage,
            capabilities=",".join(payload.capabilities or [])[:255],
            unsupported=";".join(
                f"{k}:{v}" for k, v in (payload.unsupported or {}).items()
            )[:255],
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(device)
        try:
            db.commit()
            db.refresh(device)
        except Exception:
            db.rollback()
            logger.error("Không lưu được thiết bị cho user=%s", user.username, exc_info=True)
            raise

        logger.info(
            "Đăng ký thiết bị mới %s (user=%s, weak_key_storage=%s)",
            device_id, user.username, payload.weak_key_storage,
        )
        return ClientDeviceResponse(
            device_id=device.device_id,
            fingerprint=device.fingerprint,
            already_registered=False,
            weak_key_storage=device.weak_key_storage,
            unsupported=_parse_unsupported(device.unsupported),
        )

    @staticmethod
    def get_active(db: Session, user_id: int, device_id: str) -> ClientDevice:
        """Lấy thiết bị đang hoạt động. Ném `DeviceKeyError` nếu không dùng được."""
        device = db.query(ClientDevice).filter(
            ClientDevice.user_id == user_id,
            ClientDevice.device_id == device_id,
        ).first()
        if device is None:
            raise DeviceKeyError("DEVICE_NOT_REGISTERED")
        if device.revoked_at is not None:
            raise DeviceKeyError("DEVICE_REVOKED")
        return device

    @staticmethod
    def verify_signature(device: ClientDevice, message: bytes, signature_b64: str) -> bool:
        """Xác minh chữ ký Ed25519. Sai chữ ký -> False, không ném lỗi ra ngoài."""
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        try:
            signature = base64.b64decode(signature_b64, validate=True)
        except Exception:
            return False
        if len(signature) != 64:
            return False

        try:
            public_key_bytes = base64.b64decode(device.public_key, validate=True)
            if len(public_key_bytes) != ED25519_PUBLIC_KEY_BYTES:
                return False
            Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature, message)
        except (InvalidSignature, ValueError, TypeError):
            return False
        return True

    @staticmethod
    def touch(db: Session, device: ClientDevice) -> None:
        device.last_seen_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception:
            db.rollback()