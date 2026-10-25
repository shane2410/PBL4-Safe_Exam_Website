"""Cấu hình runtime của SEB Client, đọc từ biến môi trường / file `.env`.

Cố ý KHÔNG dùng `QSettings`: nó ghi plaintext xuống đĩa. Mọi giá trị ở đây chỉ
là cấu hình kết nối, không chứa bí mật — bí mật (token) chỉ nằm trong RAM,
xem `api/client.py`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .constants import DEFAULT_BACKEND_URL, DEFAULT_EXAM_ORIGIN

BASE_DIR = Path(__file__).resolve().parent.parent

# Chỉ override khi chưa có biến thật — không đè giá trị người dùng đã export.
load_dotenv(BASE_DIR / ".env", override=False)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class ClientConfig:
    """Cấu hình của một lần chạy SEB Client."""

    backend_url: str = os.getenv("SEB_BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")
    exam_origin: str = os.getenv("SEB_EXAM_ORIGIN", DEFAULT_EXAM_ORIGIN).rstrip("/")

    # URL trang thi, có thể cấu hình. Mặc định khớp web app hiện tại.
    # Dùng `{room_code}` làm chỗ thay thế — tự động được quote an toàn.
    # Muốn trỏ sang bản web khác (bản demo, bản deploy thật, IP của GV) thì chỉ
    # cần sửa biến này, không phải sửa code.
    exam_url_template: str = os.getenv(
        "SEB_EXAM_URL_TEMPLATE", DEFAULT_EXAM_ORIGIN + "/exam/room?room={room_code}&embedded=1"
    )

    # Origin nào được phép nạp trong QWebEngineView. Mọi URL ngoài danh sách này
    # sẽ bị navigation_guard chặn — không được để trống, nếu không client mở
    # được bất kỳ trang nào.
    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip().rstrip("/")
            for origin in os.getenv(
                "SEB_ALLOWED_ORIGINS",
                DEFAULT_EXAM_ORIGIN + "," + DEFAULT_BACKEND_URL,
            ).split(",")
            if origin.strip()
        )
    )

    log_level: str = os.getenv("SEB_LOG_LEVEL", "INFO").upper()
    log_dir: Path = Path(os.getenv("SEB_LOG_DIR", str(BASE_DIR / "logs")))

    # Nơi lưu khoá công khai + blob khoá đã mã hoá của thiết bị.
    key_dir: Path = Path(os.getenv("SEB_KEY_DIR", str(BASE_DIR / "device_keys")))

    heartbeat_interval: int = _env_int("SEB_HEARTBEAT_INTERVAL", 10)

    # Chạy không có màn hình thật (CI, test tự động). Bật thì log rõ ra để không
    # ai tưởng client đã hoạt động thật.
    headless: bool = _env_bool("SEB_HEADLESS", False)

    @property
    def api_root(self) -> str:
        return f"{self.backend_url}/api"

    def validate(self) -> list[str]:
        """Trả về danh sách cấu hình sai, rỗng nghĩa là hợp lệ."""
        problems: list[str] = []
        if not self.allowed_origins:
            problems.append(
                "SEB_ALLOWED_ORIGINS rỗng — client sẽ không nạp được trang nào."
            )
        if self.heartbeat_interval < 1:
            problems.append("SEB_HEARTBEAT_INTERVAL phải >= 1.")

        if "{room_code}" not in self.exam_url_template:
            problems.append(
                "SEB_EXAM_URL_TEMPLATE phải chứa {room_code}, nếu không client "
                "sẽ mở trang thi không kèm mã phòng."
            )
        if not self.exam_url_template.startswith(("http://", "https://")):
            problems.append("SEB_EXAM_URL_TEMPLATE phải bắt đầu bằng http:// hoặc https://.")
        return problems

    def build_exam_url(self, room_code: str) -> str:
        """Dựng URL trang thi từ template trong cấu hình."""
        return self.exam_url_template.format(room_code=room_code)


def load_config() -> ClientConfig:
    return ClientConfig()