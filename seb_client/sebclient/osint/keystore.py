"""Sinh và lưu cặp khoá Ed25519 của thiết bị.

Private key KHÔNG BAO GIỜ rời máy. Thứ tự ưu tiên kho hệ thống:

1. **Windows** — DPAPI qua `CryptProtectData` (pywin32)
2. **macOS**   — Keychain
3. **Linux**   — Secret Service (`secretstorage`)

Khi không có kho hệ thống (Linux/Wayland hay container), KHÔNG được lưu khoá
rõ. Client báo `KEYSTORE_UNAVAILABLE` và mới đến chế độ yếu hơn do giảng viên
quyết định — xem `docs/PLAN.md` mục 1.5.2.1.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

logger = logging.getLogger(__name__)

KEY_FILENAME = "device_ed25519.json"


@dataclass
class DeviceKey:
    private_key: Ed25519PrivateKey
    public_key_b64: str
    weak_storage: bool

    @property
    def device_id(self) -> str:
        import hashlib

        raw = base64.b64decode(self.public_key_b64)
        return hashlib.sha256(raw).hexdigest()[:16]

    @property
    def fingerprint(self) -> str:
        import hashlib

        raw = base64.b64decode(self.public_key_b64)
        return hashlib.sha256(raw).hexdigest()

    def sign(self, message: bytes) -> str:
        return base64.b64encode(self.private_key.sign(message)).decode("utf-8")


def load_or_create(key_dir: Path) -> DeviceKey:
    """Lấy khoá đã có, hoặc sinh cặp khoá mới và lưu lại nếu bảo vệ được."""
    key_dir.mkdir(parents=True, exist_ok=True)
    key_path = key_dir / KEY_FILENAME

    if key_path.exists():
        try:
            data = json.loads(key_path.read_text(encoding="utf-8"))
            private_key = _unprotect(key_dir, data)
            if private_key is not None:
                logger.info("Dung khoa thiet bi da co (%s)", data.get("label", "?"))
                return DeviceKey(
                    private_key=private_key,
                    public_key_b64=data["public_key"],
                    weak_storage=bool(data.get("weak_storage")),
                )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Khoa thiet bi khong doc duoc (%s) — sinh lai", exc)

    return _generate(key_dir)


def _generate(key_dir: Path) -> DeviceKey:
    private_key = Ed25519PrivateKey.generate()
    public_b64 = base64.b64encode(
        private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode("utf-8")

    weak, reason = _save_protected(key_dir, private_key)
    if weak:
        logger.warning(
            "KHONG bao ve duoc private key tren %s (%s). Khoa chi song trong RAM, "
            "moi lan mo client se la mot thiet bi moi. Gianh vien se thay "
            "DEVICE_KEY_WEAK tren dashboard.",
            sys.platform, reason,
        )

    return DeviceKey(private_key=private_key, public_key_b64=public_b64, weak_storage=weak)


def _save_protected(key_dir: Path, private_key: Ed25519PrivateKey) -> tuple[bool, str]:
    """Bảo vệ rồi mới lưu private key. Trả (weak?, lý do).

    **Không bao giờ** ghi private key dạng rõ xuống đĩa. Nền tảng chưa có
    tích hợp kho hệ thống thì KHÔNG lưu gì cả — khoá chỉ sống trong RAM cho tới
    khi client đóng. Lạm dụng `weak_storage=True` để lách bước này là lỗi bảo
    mật, không phải lựa chọn kỹ thuật.
    """
    raw = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    key_path = key_dir / KEY_FILENAME

    if sys.platform == "win32":
        try:
            import win32crypt

            blob = win32crypt.CryptProtectData(
                raw, "SEB Client device key", None, None, None, 0
            )[1]
            key_path.write_text(
                json.dumps(
                    {
                        "protected": base64.b64encode(blob).decode("utf-8"),
                        "protection": "dpapi",
                        "public_key": base64.b64encode(
                            private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
                        ).decode("utf-8"),
                        "label": os.environ.get("COMPUTERNAME", "windows"),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return False, "dpapi"
        except Exception as exc:  # noqa: BLE001 - phụ thuộc môi trường Windows
            logger.error("DPAPI thất bại: %s", exc)
            return True, f"dpapi_error:{exc}"

    if sys.platform == "darwin":
        return True, "keychain_chua_duoc_tich_hop"
    return True, "secret_service_chua_duoc_tich_hop"


def _unprotect(key_dir: Path, data: dict) -> Ed25519PrivateKey | None:
    """Giải mã private key từ blob đã bảo vệ. Không đọc được -> None."""
    protection = data.get("protection")
    if protection != "dpapi":
        # Bản ghi cũ từng ghi khoá rõ (đã xoá khỏi đĩa) — từ chối dùng lại.
        return None

    try:
        import win32crypt

        blob = base64.b64decode(data["protected"])
        raw = win32crypt.CryptUnprotectData(blob, None, None, None, 0)[1]
        return Ed25519PrivateKey.from_private_bytes(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Khong giai ma duoc khoa DPAPI: %s", exc)
        return None