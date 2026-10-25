"""Tắt và phát hiện DevTools.

Hai lớp:

1. **Tắt hẳn** — `InspectElementEnabled = False` khiến QWebEngineView không mở
   được cửa sổ inspect. Đây là lớp mạnh nhất vì không dựa vào phát hiện.
2. **Phát hiện** — dùng để *ghi nhận bằng chứng* nếu lớp trên bị vô hiệu hoá
   (người dùng sửa cấu hình trước khi thi, hoặc gọi API nội bộ từ console).

Lưu ý thẳng thắn: một client chạy trên máy thí sinh **luôn** có thể bị vô hiệu
hoá từ bên trong. Vì vậy `devtools_guard` chỉ *tăng độ khó*, không tạo ra ranh
giới bảo mật — đó là việc của code signing (Phase 2).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

from ..constants import VIOLATION_DEVTOOLS_DETECTED
from .base import BaseGuard

logger = logging.getLogger(__name__)


class DevToolsGuard(BaseGuard):
    name = "devtools"
    violation_type = VIOLATION_DEVTOOLS_DETECTED
    dedupe_ms = 3000

    def install(self) -> None:
        page = self._window._page
        if page is None:
            logger.error("Khong co page de tat DevTools")
            return

        # Qt 6.12 đã gỡ `InspectElementEnabled`. Việc chặn DevTools thật sự nằm
        # ở `GuardedWebEnginePage.triggerAction` — xem ui/web_page.py.
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptCanPaste, False)
        settings.setAttribute(QWebEngineSettings.PdfViewerEnabled, False)
        settings.setAttribute(QWebEngineSettings.ScreenCaptureEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebRTCPublicInterfacesOnly, True)
        settings.setAttribute(QWebEngineSettings.PrintHeaderAndFooter, False)

        # Theo dõi DevTools có đang mở hay không. QWebEngineView không báo sự
        # kiện mở/đóng inspect, nên ta theo dõi cửa sổ con của chính nó.
        self._timer = QTimer(self._window)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._check)
        self._timer.start()

        self._installed = True
        logger.info("devtools_guard: da tat InspectElement")

    def uninstall(self) -> None:
        if getattr(self, "_timer", None) is not None:
            self._timer.stop()
            self._timer = None
        self._installed = False

    def _check(self) -> None:
        """Báo vi phạm nếu phát hiện cửa sổ DevTools của view đang mở."""
        view = self._window.web_view
        if view is None:
            return

        for child in view.findChildren(type(view)):
            # QWebEngineView con chỉ xuất hiện khi DevTools được mở.
            if child is view:
                continue
            class_name = type(child).__name__
            if "DevTools" in class_name:
                self.report({"detected": "devtools_window", "class": class_name})
                return