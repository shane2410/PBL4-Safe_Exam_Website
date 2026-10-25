"""Khoá clipboard hệ thống trong suốt thời gian thi.

Cách làm: xoá clipboard định kỳ. Không thể "khoá" clipboard trên Windows — không
có API khoá thật, chỉ có thể xoá. Vì vậy:

* xoá mỗi `interval_ms` để thí sinh không kịp dán ra ứng dụng khác
* kết hợp với `keyboard_guard` chặn Ctrl+C/Ctrl+V ở tầng Qt

Clipboard là dữ liệu của chính máy thí sinh, xoá nó không làm mất dữ liệu thi
(ví dụ đã trả lời nằm trong backend, không nằm trong clipboard).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

from ..constants import VIOLATION_COPY_PASTE_ATTEMPT
from .base import BaseGuard

logger = logging.getLogger(__name__)


class ClipboardGuard(BaseGuard):
    name = "clipboard"
    violation_type = VIOLATION_COPY_PASTE_ATTEMPT

    def __init__(self, window, reporter=None, interval_ms: int = 2000, os_adapter=None):
        super().__init__(window, reporter)
        self._interval_ms = interval_ms
        self._os = os_adapter
        self._cleared_count = 0
        self._os_locked = False

    @property
    def cleared_count(self) -> int:
        return self._cleared_count

    def install(self) -> None:
        self._timer = QTimer(self._window)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._clear_clipboard)
        self._timer.start()
        if self._os is not None and self._os.lock_clipboard():
            self._os_locked = True
            logger.info("clipboard_guard: da bat co che clipboard he thong")
        self._installed = True
        logger.info("clipboard_guard: xoa clipboard moi %d ms", self._interval_ms)

    def uninstall(self) -> None:
        if getattr(self, "_timer", None) is not None:
            self._timer.stop()
            self._timer = None
        self._installed = False

    def _clear_clipboard(self) -> None:
        # Ưu tiên xoá ở tầng hệ thống — chặn được cả việc ứng dụng khác ghi vào.
        if self._os is not None:
            self._os.clear_clipboard()

        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return

        has_text = bool(clipboard.text().strip())
        has_image = not clipboard.image().isNull()
        if not has_text and not has_image:
            return

        self._cleared_count += 1
        clipboard.clear()

        # Có nội dung bị xoá khi thí sinh đang thi => đáng ghi nhận.
        self.report({"detected": "clipboard_had_content", "count": self._cleared_count})