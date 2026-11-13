from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ClientDeviceRevokeRequest(BaseModel):
    """Thu hồi / mở khoá một thiết bị của thí sinh.

    `revoke=True` -> đánh dấu `revoked_at`, thiết bị không attest được nữa.
    `revoke=False` -> mở khoá thủ công (chỉ ADMIN), để thí sinh có thể dùng
    lại thiết bị (VD: GV thu hồi nhầm, hoặc đã xác minh máy sạch).
    """

    revoke: bool = Field(default=True)
    reason: Optional[str] = Field(default=None, max_length=255)


class ClientDeviceAdminResponse(BaseModel):
    device_id: str
    user_id: int
    username: Optional[str] = None
    label: Optional[str] = None
    client_version: Optional[str] = None
    weak_key_storage: bool = False
    capabilities: Optional[str] = None
    unsupported: Optional[str] = None
    created_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class ClientDeviceListResponse(BaseModel):
    devices: list[ClientDeviceAdminResponse]
    total: int
