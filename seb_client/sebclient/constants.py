"""Hằng số dùng chung cho SEB Client.

Giá trị `CLIENT_TYPE` và `CLIENT_VERSION` được gửi lên server trong quy trình
attestation — server dùng chúng để đối chiếu, nên KHÔNG được để trống.
"""

from __future__ import annotations

APP_NAME = "SEB Client"
APP_DISPLAY_NAME = "An toàn thi trực tuyến"

CLIENT_TYPE = "seb"
CLIENT_VERSION = "1.0.0-phase1"

# Header bắt buộc gửi kèm mọi request tới backend.
HEADER_CLIENT_TYPE = "X-Client-Type"
HEADER_CLIENT_VERSION = "X-Client-Version"
HEADER_ATTESTATION = "X-Attestation-Token"
HEADER_DEVICE_FINGERPRINT = "X-Device-Fingerprint"

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_EXAM_ORIGIN = "http://localhost:5173"

# Nhịp heartbeat: server đặt timeout 30s, ta gửi mỗi 10s (khớp
# settings.HEARTBEAT_INTERVAL_SECONDS của backend).
HEARTBEAT_INTERVAL_SECONDS = 10

# Khoảng thời gian client chịu chờ socket reconnect trước khi báo mất kết nối.
SOCKET_RECONNECT_DELAY_SECONDS = 2
SOCKET_MAX_RECONNECT_ATTEMPTS = 0

# Sự kiện socket của backend (namespace mặc định, không prefix).
EVENT_JOIN_ROOM = "join_exam_room"
EVENT_HEARTBEAT = "heartbeat"
EVENT_VIOLATION = "violation"
EVENT_FORCE_SUBMIT = "force_submit"
EVENT_STATUS_CHANGE = "student_status_change"

# Sự kiện client -> OS. Mỗi guard bắt một sự kiện riêng để BaseGuard
# chỉ cần biết "loại vi phạm nào" mà không phải if/elif dài.
EVENT_VIOLATION_REPORTED = "seb_violation_reported"

# Loại vi phạm — PHẢI khớp ALLOWED_EVENT_TYPES trong backend
# (backend/app/schemas/violation_schema.py). Gửi loại lạ sẽ bị validate reject.
VIOLATION_TAB_SWITCH = "TAB_SWITCH"
VIOLATION_FULLSCREEN_EXIT = "FULLSCREEN_EXIT"
VIOLATION_DEVTOOLS_DETECTED = "DEVTOOLS_DETECTED"
VIOLATION_COPY_PASTE_ATTEMPT = "COPY_PASTE_ATTEMPT"
VIOLATION_RIGHT_CLICK_ATTEMPT = "RIGHT_CLICK_ATTEMPT"