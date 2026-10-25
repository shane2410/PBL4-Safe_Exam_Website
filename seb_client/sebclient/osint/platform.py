"""Chọn adapter đúng theo hệ điều hành đang chạy.

Điểm quan trọng: khi hệ điều hành **không** có trong danh sách, phải trả về
`UnsupportedAdapter` — một adapter nói thẳng là không làm được gì, thay vì
trả `None` rồi để lớp trên gọi nhầm và crash.
"""

from __future__ import annotations

import logging
import sys

from .base import BaseOSAdapter
from .capability_matrix import detect_platform, describe, unsupported

logger = logging.getLogger(__name__)


class UnsupportedAdapter:
    """Adapter giả cho nền tảng lạ — mọi cơ chế đều trả False, không nổ."""

    def __init__(self, platform_key: str = "unknown"):
        self.platform_key = platform_key

    def capabilities(self) -> frozenset[str]:
        return frozenset()

    def supported(self, capability: str) -> bool:
        return False

    def enter_kiosk(self) -> bool:
        return False

    def exit_kiosk(self) -> None:
        return None

    def lock_clipboard(self) -> bool:
        return False

    def clear_clipboard(self) -> bool:
        return False

    def start_monitor_switch_detection(self, callback) -> bool:
        return False

    def stop_monitor_switch_detection(self) -> None:
        return None

    def block_print(self) -> bool:
        return False

    def poll_window_switch(self) -> None:
        return None

    def describe(self) -> str:
        return f"{self.platform_key} — KHÔNG được hỗ trợ"


def create_adapter(platform_key: str | None = None) -> BaseOSAdapter | UnsupportedAdapter:
    """Trả adapter tương ứng với nền tảng."""
    key = platform_key or detect_platform()
    base = key.split(":")[0]

    try:
        if base == "windows":
            from .windows_adapter import WindowsAdapter

            return WindowsAdapter(key)
        if base in {"darwin", "macos"}:
            from .macos_adapter import MacOSAdapter

            return MacOSAdapter(key)
        if base == "linux":
            from .linux_adapter import LinuxAdapter

            return LinuxAdapter(key)
    except ImportError as exc:
        logger.error("Khong nap duoc adapter cho %s: %s", key, exc)
        return UnsupportedAdapter(key)

    logger.error("Nen tang khong ho tro: %s", key)
    return UnsupportedAdapter(key)


def report(platform_key: str | None = None) -> dict:
    """Thông tin năng lực để log và đưa vào báo cáo hỗ trợ."""
    key = platform_key or detect_platform()
    return {
        "platform": key,
        "capabilities": sorted(create_adapter(key).capabilities()),
        "unsupported": unsupported(key),
        "summary": describe(key),
    }