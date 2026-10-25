"""Bảng năng lực theo hệ điều hành.

Mục đích **không phải** để trông có vẻ đầy đủ, mà để làm rõ điều mà plan yêu cầu
(Quy tắc #5 — liêm chính học thuật): máy nào **không** hỗ trợ đủ cơ chế thì phải
báo, không được bật im lặng.

Client đọc `capabilities_for()` để biết guard nào được bật; phần không thuộc tập
sẽ được báo lên server với `detail.unsupported = [...]` để giảng viên nhìn thấy.
"""

from __future__ import annotations

import sys
from typing import Iterable

# Guard mà SEB Client có thể thực hiện.
ALL_CAPABILITIES: frozenset[str] = frozenset(
    {
        "kiosk",              # fullscreen + ẩn taskbar/dock
        "clipboard",          # khoá clipboard hệ thống
        "devtools",           # chặn DevTools
        "keyboard",           # chặn tổ hợp phím
        "monitor_switch",     # phát hiện chuyển sang ứng dụng khác
        "block_print",
        "block_download",
        "navigation",         # khoá điều hướng ra ngoài
        "heartbeat",
    }
)

_COMMON = {
    "kiosk",
    "clipboard",
    "devtools",
    "keyboard",
    "block_print",
    "block_download",
    "navigation",
    "heartbeat",
}

CAPABILITIES: dict[str, frozenset[str]] = {
    "windows": frozenset(_COMMON | {"monitor_switch"}),
    "macos": frozenset(_COMMON | {"monitor_switch"}),
    # X11: có thể theo dõi cửa sổ đang focus -> bắt được Alt+Tab toàn cục.
    "linux": frozenset(_COMMON | {"monitor_switch"}),
    # Wayland CỐ TÌNH thiếu monitor_switch. Giao diện đồ hoạ không cho đọc
    # cửa sổ đang focus của ứng dụng khác; nói dối là có sẽ tạo cảm giác an toàn
    # giả cho cả GV lẫn sinh viên.
    "linux:wayland": frozenset(_COMMON),
}

_UNSUPPORTED_REASON = {
    "monitor_switch": "Wayland không cho đọc cửa sổ đang focus của ứng dụng khác",
}


def detect_platform() -> str:
    """Nhận diện nền tảng, phân biệt Wayland/X11 trên Linux."""
    if sys.platform.startswith("linux"):
        session_type = ""
        try:
            import os

            for path in ("/run/wayland-0", "/run/user/0/wayland-0"):
                if os.path.exists(path):
                    session_type = "wayland"
                    break
            if not session_type:
                import os as _os

                if _os.environ.get("WAYLAND_DISPLAY"):
                    session_type = "wayland"
                elif _os.environ.get("DISPLAY"):
                    session_type = "x11"
        except Exception:  # noqa: BLE001
            session_type = ""
        if session_type != "wayland":
            try:
                import os

                if os.environ.get("XDG_SESSION_TYPE") == "wayland" or os.environ.get(
                    "WAYLAND_DISPLAY"
                ):
                    session_type = "wayland"
            except Exception:  # noqa: BLE001
                pass
        return f"linux:{session_type}" if session_type else "linux"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform in {"win32", "cygwin"}:
        return "windows"
    return "unknown"


def capabilities_for(platform_key: str | None = None) -> frozenset[str]:
    key = platform_key or detect_platform()
    return CAPABILITIES.get(key, frozenset())


def unsupported(
    platform_key: str | None = None, requested: Iterable[str] | None = None
) -> dict[str, str]:
    """Trả về {guard: lý do} cho những guard yêu cầu mà nền tảng không có."""
    key = platform_key or detect_platform()
    available = capabilities_for(key)
    wanted = set(requested) if requested else set(ALL_CAPABILITIES)
    return {
        name: _UNSUPPORTED_REASON.get(name, "Không hỗ trợ trên nền tảng này")
        for name in sorted(wanted - available)
    }


def describe(platform_key: str | None = None) -> str:
    key = platform_key or detect_platform()
    caps = sorted(capabilities_for(key))
    missing = unsupported(key)
    text = f"{key}: " + ", ".join(caps)
    if missing:
        text += "  | THIEU: " + ", ".join(missing)
    return text