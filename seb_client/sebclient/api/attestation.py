"""Quy trình xác thực client bằng Ed25519 (mục 1.5.2 PLAN.md).

    1. POST /auth/client-devices  (public key)      -> device_id
    2. POST /auth/client-nonce                      -> nonce
    3. ký bằng private key trên máy                 -> signature
    4. POST /auth/client-attest                     -> attestation_token

Khác HMAC cũ ở chỗ: server KHÔNG sinh ra được bất kỳ khoá nào để gửi cho
client. Nó chỉ có public key — không thể tự tạo chữ ký hợp lệ.
"""

from __future__ import annotations

import logging

from ..api.client import ApiClient, ApiError
from ..constants import CLIENT_VERSION
from ..osint.keystore import DeviceKey

logger = logging.getLogger(__name__)

# Phải khớp đúng hàm build_attest_message ở backend
# (app/services/attestation_service.py). Sai một ký tự là chữ ký hỏng.
MESSAGE_TEMPLATE = "{nonce}|{client_version}|{device_fingerprint}|{device_id}"


def build_attest_message(
    nonce: str, client_version: str, device_fingerprint: str, device_id: str
) -> bytes:
    return MESSAGE_TEMPLATE.format(
        nonce=nonce,
        client_version=client_version,
        device_fingerprint=device_fingerprint,
        device_id=device_id,
    ).encode("utf-8")


class AttestationResult:
    def __init__(self, attested: bool, reason: str = "", token: str | None = None,
                 device_id: str | None = None, fingerprint: str | None = None):
        self.attested = attested
        self.reason = reason
        self.token = token
        self.device_id = device_id
        self.fingerprint = fingerprint


class ClientAttestor:
    def __init__(self, api: ApiClient, device_key: DeviceKey, client_version: str = CLIENT_VERSION):
        self._api = api
        self._key = device_key
        self._version = client_version

    async def attest(self) -> AttestationResult:
        """Chạy trọn 4 bước. Trả về kết quả, không ném lỗi ra ngoài."""
        from ..osint.platform import report as capability_report

        caps = capability_report()
        try:
            registered = await self._api.register_device(
                public_key=self._key.public_key_b64,
                label=None,
                client_version=self._version,
                weak_key_storage=self._key.weak_storage,
                capabilities=caps["capabilities"],
                unsupported=caps["unsupported"] or None,
            )
        except ApiError as exc:
            logger.error("Đăng ký thiết bị thất bại: %s", exc.message)
            return AttestationResult(False, f"DEVICE_REGISTER_FAILED: {exc.message}")

        device_id = registered["device_id"]
        if caps["unsupported"]:
            # Ghi log để GV tra log khi cần; server đã lưu để hiển thị.
            logger.warning(
                "May nay KHONG ho tro day du: %s", ", ".join(caps["unsupported"])
            )

        try:
            nonce_payload = await self._api.client_nonce()
        except ApiError as exc:
            return AttestationResult(False, f"NONCE_FAILED: {exc.message}")

        nonce = nonce_payload["nonce"]
        fingerprint = self._key.fingerprint
        message = build_attest_message(nonce, self._version, fingerprint, device_id)
        signature = self._key.sign(message)

        try:
            result = await self._api.client_attest(
                nonce=nonce,
                client_version=self._version,
                device_fingerprint=fingerprint,
                signature=signature,
                device_id=device_id,
            )
        except ApiError as exc:
            return AttestationResult(False, f"ATTEST_FAILED: {exc.message}")

        if not result.get("attested"):
            reason = result.get("verification_reason") or "UNKNOWN"
            logger.warning("Xác thực thất bại: %s", reason)
            return AttestationResult(False, reason, device_id=device_id)

        logger.info("Xác thực thành công, device_id=%s", device_id)
        self._api.set_attestation(result.get("attestation_token"), fingerprint)
        return AttestationResult(
            True,
            token=result.get("attestation_token"),
            device_id=device_id,
            fingerprint=fingerprint,
        )