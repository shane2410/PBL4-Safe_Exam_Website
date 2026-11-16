"""Hằng số dùng chung cho SEB Client.

Giá trị `CLIENT_TYPE` và `CLIENT_VERSION` được gửi lên server trong quy trình
attestation — server dùng chúng để đối chiếu, nên KHÔNG được để trống.
"""

from __future__ import annotations

APP_NAME = "SEB Client"
APP_DISPLAY_NAME = "An toàn thi trực tuyến"

CLIENT_TYPE = "seb"
CLIENT_VERSION = "1.0.0-phase1"

# SHA-256 hash chuẩn của bản build phát hành (None nếu đang ở chế độ dev).
# Build script sẽ điền chuỗi hex 64 ký tự vào đây trước khi đóng gói / ký số.
BASE_HASH: str | None = None

# Header bắt buộc gửi kèm mọi request tới backend.
HEADER_CLIENT_TYPE = "X-Client-Type"
HEADER_CLIENT_VERSION = "X-Client-Version"
HEADER_CLIENT_HASH = "X-Client-Hash"
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

# Đường dẫn trang kết quả của web app. Client dùng để biết phiên đã nộp xong —
# `submit` là request do TRANG phát ra, client không có kênh nào khác.
RESULTS_PATH_SUFFIX = "/exam/results"

# Thời gian sống của attestation token phía server (phút). Xem
# backend/app/services/attestation_service.py:ATTESTATION_TOKEN_TTL_MINUTES.
# Client phải attest lại TRƯỚC mốc này, nếu không các request sau sẽ bị server
# coi là web thường giữa kỳ thi.
ATTESTATION_TTL_MINUTES = 5
# Attest lại sớm hơn TTL để không có khoảng trống nào token đã hết hạn.
ATTESTATION_REFRESH_SECONDS = 240

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