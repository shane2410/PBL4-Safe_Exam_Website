"""Chế độ kiosk: fullscreen, chặn chuột phải, chặn đóng cửa sổ.

Phần "ẩn taskbar/dock" phụ thuộc hệ điều hành và được giao cho `osint/adapter`
(xem S4) — guard này chỉ làm những gì Qt làm được và làm tốt:

* bắt buộc fullscreen, ghi nhận lỗi khi thí sinh thoát fullscreen
* chặn menu chuột phải (chặn cả "Xem mã nguồn" của trình duyệt)
* chặn đóng cửa sổ khi thi (trừ khi giám thị cho phép)
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, Qt

from ..constants import VIOLATION_FULLSCREEN_EXIT, VIOLATION_RIGHT_CLICK_ATTEMPT
from .base import BaseGuard

logger = logging.getLogger(__name__)


class KioskGuard(BaseGuard):
    name = "kiosk"
    violation_type = VIOLATION_RIGHT_CLICK_ATTEMPT

    def __init__(self, window, reporter=None, allow_close: bool = False, os_adapter=None):
        super().__init__(window, reporter)
        self._allow_close = allow_close
        self._os = os_adapter
        self._ever_fullscreen = False
        self._os_kiosk_active = False

    @property
    def ever_fullscreen(self) -> bool:
        return self._ever_fullscreen

    def install(self) -> None:
        window = self._window
        window.setContextMenuPolicy(Qt.NoContextMenu)
        window.installEventFilter(self)
        self._enter_fullscreen()
        self._enter_os_kiosk()
        self._installed = True
        logger.info("kiosk_guard: vao fullscreen, chan context menu")

    def _enter_os_kiosk(self) -> None:
        """Ẩn taskbar/dock ở tầng hệ điều hành.

        Qt chỉ fullscreen được cửa sổ; thanh taskbar và dock là của trình quản
        lý cửa sổ, nằm ngoài tầm với của Qt.
        """
        if self._os is None:
            return
        if self._os.enter_kiosk():
            self._os_kiosk_active = True
            logger.info("Đa ẩn taskbar/dock qua %s", self._os.describe())
        else:
            # Không ẩn được là giới hạn thật — phải để lại dấu vết để GV biết.
            logger.warning("Khong an taskbar/dock duoc tren nen tang nay")

    def uninstall(self) -> None:
        window = self._window
        if not self._installed:
            return
        try:
            window.removeEventFilter(self)
            window.setContextMenuPolicy(Qt.DefaultContextMenu)
        except (RuntimeError, TypeError):
            pass
        if self._os_kiosk_active and self._os is not None:
            self._os.exit_kiosk()
            self._os_kiosk_active = False
        self._installed = False

    def _enter_fullscreen(self) -> None:
        self._window.showFullScreen()
        self._ever_fullscreen = True

    def eventFilter(self, obj, event):  # noqa: N802
        if event.type() == QEvent.WindowStateChange:
            was = bool(event.oldState() & Qt.WindowState.WindowFullScreen)
            now = bool(self._window.windowState() & Qt.WindowState.WindowFullScreen)
            if was and not now:
                self.report(
                    {"detected": "left_fullscreen"},
                    event_type=VIOLATION_FULLSCREEN_EXIT,
                )
            elif now:
                self._ever_fullscreen = True

        elif event.type() == QEvent.ContextMenu:
            self.report({"detected": "context_menu"}, dedupe=False)
            return True

        elif event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.RightButton:
                self.report({"detected": "right_click"}, dedupe=False)
                return True

        elif event.type() == QEvent.Close and not self._allow_close:
            logger.warning("Thuong cho dong cua so thi")
            event.ignore()
            self.report({"detected": "close_attempt"})
            return True

        return False