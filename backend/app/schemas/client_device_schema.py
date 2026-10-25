from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ClientDeviceRegisterRequest(BaseModel):
    """Đăng ký khoá công khai Ed25519 của thiết bị.

    Chỉ public key được gửi lên server. Private key sinh và lưu trên máy thí
    sinh (DPAPI / Keychain / Secret Service) — server không bao giờ có nó.
    """

    public_key: str = Field(
        ...,
        min_length=40,
        max_length=128,
        description="Ed25519 public key dạng base64 raw 32 bytes",
    )
    label: Optional[str] = Field(default=None, max_length=100)
    client_version: Optional[str] = Field(default=None, max_length=20)
    weak_key_storage: bool = Field(
        default=False,
        description="Máy không có kho hệ thống, private key lưu ở dạng yếu hơn",
    )
    capabilities: Optional[list[str]] = Field(
        default=None,
        description="Cơ chế client thực sự hỗ trợ trên máy này",
    )
    unsupported: Optional[dict[str, str]] = Field(
        default=None,
        description="Cơ chế không hỗ trợ kèm lý do, để GV biết mức bảo vệ thật",
    )

    @field_validator("public_key")
    @classmethod
    def _validate_base64(cls, value: str) -> str:
        import base64

        try:
            raw = base64.b64decode(value, validate=True)
        except Exception as exc:
            raise ValueError("public_key phải là base64 hợp lệ") from exc
        if len(raw) != 32:
            raise ValueError(f"public_key phải dài đúng 32 byte, nhận được {len(raw)}")
        return value


class ClientDeviceResponse(BaseModel):
    device_id: str
    fingerprint: str
    already_registered: bool
    weak_key_storage: bool = False
    unsupported: Optional[dict[str, str]] = None