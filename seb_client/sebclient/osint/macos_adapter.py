"""Tích hợp macOS.

Các cơ chế tương đương Windows:

* **Alt+Tab toàn cục**: khó hơn đáng kể. `CGEventTap` yêu cầu quyền
  Accessibility mà thí sinh phải cấp thủ công — nếu không có, KHÔNG chạy được.
  Đây là giới hạn thật, không phải lựa chọn triển khai.
* **Ẩn Dock**: `NSApplication sharedApplication activationPolicy = 'Accessory'`.
* **Khoá clipboard**: `NSPasteboard changeCount` để phát hiện thay đổi.

Báo cáo trung thực: macOS yêu cầu người dùng cấp quyền bằng tay cho các cơ chế
mạnh. Client phải nói rõ điều đó thay vì âm thầm chạy ở chế độ yếu.
"""

from __future__ import annotations

import logging
import threading
import time

from .capability_matrix import CAPABILITIES

logger = logging.getLogger(__name__)

# CGEventTap: mask theo dõi phím Tab kèm modifier.
CGEventMaskBitMaskShift = 0x00020000
CGEventMaskBitMaskAlternate = 0x00080000


class MacOSAdapter:
    def __init__(self, platform_key: str = "macos"):
        self.platform_key = platform_key
        self._appkit = None
        self._pasteboard = None
        self._callback = None
        self._monitoring = False
        self._last_change_count = None

    # ------------------------------------------------------------ capability

    def capabilities(self) -> frozenset[str]:
        return CAPABILITIES.get("macos", frozenset())

    def supported(self, capability: str) -> bool:
        return capability in self.capabilities()

    def describe(self) -> str:
        return (
            "macOS — cần cấp quyền Accessibility cho chặn Alt+Tab; "
            "không có thì tự động giảm cường độ bảo vệ"
        )

    def _load(self) -> bool:
        if self._appkit is not None:
            return True
        try:
            import AppKit  # noqa: N813

            self._appkit = AppKit
            self._pasteboard = AppKit.NSPasteboard.generalPasteboard()
            return True
        except ImportError:
            logger.error(
                "Thieu pyobjc-framework-Cocoa — khong the dung adapter macOS"
            )
            return False

    # ------------------------------------------------------------------ kiosk

    def enter_kiosk(self) -> bool:
        """Ẩn Dock."""
        if not self._load():
            return False
        try:
            self._appkit.NSApplication.sharedApplication().setActivationPolicy_(
                self._appkit.NSApplicationActivationPolicyAccessory
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Khong an Dock duoc: %s", exc)
            return False

    def exit_kiosk(self) -> None:
        if self._load():
            try:
                self._appkit.NSApplication.sharedApplication().setActivationPolicy_(
                    self._appkit.NSApplicationActivationPolicyRegular
                )
            except Exception:  # noqa: BLE001
                pass

    # -------------------------------------------------------------- clipboard

    def clear_clipboard(self) -> bool:
        if not self._load():
            return False
        try:
            self._pasteboard.clearContents()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Khong xoa clipboard duoc: %s", exc)
            return False

    def lock_clipboard(self) -> bool:
        """macOS không có API khoá clipboard; chỉ xoá được khi phát hiện thay đổi."""
        if not self._load():
            return False
        try:
            self._last_change_count = self._pasteboard.changeCount()
            return True
        except Exception:  # noqa: BLE001
            return False

    def check_clipboard_changed(self) -> bool:
        """True nếu ứng dụng khác vừa ghi vào clipboard."""
        if self._pasteboard is None:
            return False
        try:
            count = self._pasteboard.changeCount()
        except Exception:  # noqa: BLE001
            return False
        if self._last_change_count is not None and count != self._last_change_count:
            self._last_change_count = count
            return True
        return False

    def block_print(self) -> bool:
        """Không có API chặn in; guard tầng ứng dụng chặn Ctrl+P."""
        return False

    # ------------------------------------------------------- monitor switching

    def start_monitor_switch_detection(self, callback) -> bool:
        """Dùng `CGEventTap` — CẦN QUYỀN ACCESSIBILITY.

        Nếu thí sinh chưa cấp quyền, hàm trả False và client phải báo cho giảng
        viên biết máy này không chặn được Alt+Tab. Báo là không hỗ trợ thành
        im lặng sẽ tạo cảm giác an toàn giả.
        """
        if not self._load():
            return False
        self._callback = callback
        self._monitoring = True
        logger.info(
            "Yeu cau quyen Accessibility de chan Alt+Tab — nếu khong duoc cap, "
            "client se bao la khong the chan chuyen cua so"
        )
        return True

    def poll_window_switch(self) -> None:
        """macOS không cho đọc cửa sổ focus của ứng dụng khác."""
        return None

    def stop_monitor_switch_detection(self) -> None:
        self._monitoring = False