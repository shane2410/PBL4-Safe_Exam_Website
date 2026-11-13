"""Xác thực danh tính cho kết nối Socket.IO.

Trước đây handler `connect()` để trống, nên BẤT KỲ ai mở được socket đều gọi
được `teacher_force_submit` và `join_monitor_room`:

  * `teacher_force_submit` nhận `session_id` là khoá chính dạng số tự tăng nên
    liệt kê được -> thu bài (và chấm điểm) phiên thi của bất kỳ thí sinh nào.
  * `join_monitor_room` trả về toàn bộ danh sách thí sinh của một phòng.

Module này buộc mọi kết nối phải mang access token JWT hợp lệ và lưu
`sid -> {user_id, role}` để các handler kiểm tra quyền.

Token được đọc theo thứ tự: `auth` dict của Socket.IO (cả hai client đều gửi),
rồi query string `?token=` (dự phòng cho lần reconnect), rồi header
`Authorization: Bearer ...`.
"""

import logging
from typing import Any, Dict, Optional
from urllib.parse import unquote

from app.core.security import decode_access_token

logger = logging.getLogger(__name__)

MONITOR_ROLES = ("ADMIN", "TEACHER")

_identities: Dict[str, Dict[str, Any]] = {}


def _extract_token(auth: Any, environ: Optional[dict]) -> Optional[str]:
    if isinstance(auth, dict):
        token = auth.get("token")
        if isinstance(token, str) and token.strip():
            return token.strip()

    if environ:
        query = environ.get("QUERY_STRING") or ""
        for part in query.split("&"):
            key, _, value = part.partition("=")
            if key == "token" and value:
                return unquote(value)
        header = environ.get("HTTP_AUTHORIZATION") or ""
        if header.lower().startswith("bearer "):
            return header[7:].strip()
    return None


def authenticate_socket(sid: str, auth: Any = None, environ: Optional[dict] = None):
    """Xác thực token của kết nối. Trả identity hoặc None nếu không hợp lệ."""
    token = _extract_token(auth, environ)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload or payload.get("typ"):
        # `typ` có nghĩa là attestation token ngắn hạn, KHÔNG phải access token
        # đăng nhập -> không được dùng để mở socket.
        return None

    try:
        user_id = int(payload.get("sub", -1))
    except (TypeError, ValueError):
        return None
    if user_id < 0:
        return None

    identity = {"user_id": user_id, "role": payload.get("role") or "STUDENT"}
    _identities[sid] = identity
    return identity


def identity_of(sid: str) -> Optional[Dict[str, Any]]:
    return _identities.get(sid)


def drop_identity(sid: str) -> None:
    _identities.pop(sid, None)


def is_monitor(sid: str) -> bool:
    identity = _identities.get(sid)
    return bool(identity and identity.get("role") in MONITOR_ROLES)
