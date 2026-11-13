"""Cửa sổ trình duyệt khoá theo file cấu hình `.seb`.

Khác `ExamWindow` ở ba điểm cốt lõi:

* **Không cần backend.** Không login, không join phòng, không socket, không
  attestation. Mở file cấu hình là mở trang.
* **Nguồn sự thật là file `.seb`.** Khoá nào bật/tắt đều đọc từ
  `BrowserPolicy`, không có mặc định ngầm.
* **Không có khái niệm "vi phạm".** Không có server để đếm, nên chỉ ghi log.
  Đây là điều phải nói rõ với giảng viên: chế độ này khoá được máy nhưng
  **không giám sát được**.

Dùng khi nào: giảng viên phát hành file cấu hình cho một kỳ thi không nối
backend, hoặc để thử cơ chế khoá trước khi tích hợp.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow

from ..config_file import BrowserPolicy
from ..guards.clipboard_guard import ClipboardGuard
from ..guards.devtools_guard import DevToolsGuard
from ..guards.download_guard import DownloadGuard
from ..guards.keyboard_guard import KeyboardGuard
from ..guards.kiosk_guard import KioskGuard
from ..guards.navigation_guard import NavigationGuard
from ..osint.platform import create_adapter
from .web_page import GuardedWebEnginePage

logger = logging.getLogger(__name__)


class PolicyBrowserWindow(QMainWindow):
    """Cửa sổ duy nhất nạp `policy.start_url`, khoá theo `policy`."""

    def __init__(self, policy: BrowserPolicy, parent=None):
        super().__init__(parent)
        self._policy = policy
        self._guards = []
        self._blocked = False

        self.setWindowTitle(self._window_title())
        self._os = create_adapter()

        self._build_view()
        self._build_guards()

    def _window_title(self) -> str:
        label = "SEB Client"
        if self._policy.source_path is not None:
            label += f" — {self._policy.source_path.name}"
        return label

    def _build_view(self) -> None:
        # Profile off-the-record: không ghi cookie/cache/token xuống đĩa.
        self._profile = QWebEngineProfile()
        self._profile.setHttpCacheType(QWebEngineProfile.NoCache)

        page = GuardedWebEnginePage(
            self._profile, self, reporter=self._log_violation, policy=self._policy
        )
        self._page = page

        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.ShowScrollBars, False)
        settings.setAttribute(
            QWebEngineSettings.JavascriptCanOpenWindows, not self._policy.block_popups
        )
        settings.setAttribute(
            QWebEngineSettings.JavascriptCanAccessClipboard, self._policy.allow_copy_paste
        )
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, False)
        settings.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls, False
        )

        # Trang web có thể tự gọi `requestFullscreen()`. Không nối signal này thì
        # promise phía JS không bao giờ settle và nút bấm trên trang treo.
        page.fullScreenRequested.connect(self._on_fullscreen_requested)

        self.web_view = QWebEngineView(page)
        self.setCentralWidget(self.web_view)

    def _on_fullscreen_requested(self, request) -> None:
        """Chấp nhận fullscreen từ trang và áp lên cửa sổ Qt."""
        request.accept()
        if request.toggleOn():
            self.showFullScreen()
            logger.info("Trang yeu cau fullscreen -> da bat")
            return
        # Guard được tạo SAU view, nên phải tra bằng getattr: một request
        # fullscreen đến trước khi guard tồn tại không được làm sập chương trình.
        kiosk = getattr(self, "_kiosk_guard", None)
        if kiosk is not None and not kiosk._allow_close:
            logger.info("Bi qua yeu cau thoat fullscreen khi dang thi")
            return
        self.showNormal()

    def _build_guards(self) -> None:
        policy = self._policy
        self._navigation_guard = NavigationGuard(
            self, list(policy.allowed_origins), reporter=self._log_violation
        )
        self._keyboard_guard = KeyboardGuard(
            self, reporter=self._log_violation, policy=policy
        )
        self._devtools_guard = DevToolsGuard(self, reporter=self._log_violation)
        self._clipboard_guard = ClipboardGuard(
            self, reporter=self._log_violation, os_adapter=self._os
        )
        self._download_guard = DownloadGuard(self, reporter=self._log_violation)
        self._kiosk_guard = KioskGuard(
            self, reporter=self._log_violation, os_adapter=self._os, policy=policy
        )

        self._guards = [
            self._navigation_guard,
            self._keyboard_guard,
            self._devtools_guard,
            self._clipboard_guard,
            self._download_guard,
            self._kiosk_guard,
        ]

        # Guard không đọc policy: tắt hẳn những cơ chế mà cấu hình cho phép,
        # thay vì để chúng chạy rồi bỏ qua kết quả — tránh log gây hiểu nhầm.
        if policy.allow_devtools:
            self._guards.remove(self._devtools_guard)
        if policy.allow_copy_paste:
            self._guards.remove(self._clipboard_guard)

        if not policy.allow_print:
            logger.info("In bi chan theo cau hinh")

    def start(self) -> None:
        for guard in self._guards:
            guard.install()
        self.load_start_url()
        logger.info("Mo trinh duyet theo cau hinh: %s", self._policy.start_url)
        if self._policy.unsupported:
            for key, reason in self._policy.unsupported.items():
                logger.warning("Cau hinh %s chua ho tro — %s", key, reason)

    def load_start_url(self) -> None:
        self.web_view.load(QUrl(self._policy.start_url))

    def reload_exam(self) -> None:
        """NavigationGuard gọi khi bị điều hướng ra ngoài danh sách cho phép."""
        if not self._policy.allow_reload:
            logger.warning("Chan reload: cau hinh browserWindowAllowReload=false")
            return
        logger.info("Nap lai trang chu theo cau hinh")
        self.load_start_url()

    def _log_violation(self, event_type: str, detail: dict) -> None:
        # Không có server => không gửi đi đâu được. Ghi log để phục tra.
        logger.warning("SU KIEN %s: %s", event_type, detail)

    def closeEvent(self, event):  # noqa: N802
        logger.info("Dong trinh duyet theo cau hinh")
        for guard in self._guards:
            try:
                guard.uninstall()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Loi go guard %s: %s", type(guard).__name__, exc)
        self._kiosk_guard._allow_close = True
        self._release_webengine()
        super().closeEvent(event)

    def _release_webengine(self) -> None:
        """Huỷ view/page/profile trước khi QApplication bị phá huỷ (tránh segfault)."""
        import shiboken6

        for obj in (self.web_view, self._page):
            if obj is not None and shiboken6.isValid(obj):
                shiboken6.delete(obj)
        self.web_view = None
        self._page = None


def open_config_file(path: str | Path) -> PolicyBrowserWindow:
    """Đọc file `.seb` rồi tạo cửa sổ. Ném `ConfigFileError` nếu file hỏng."""
    from ..config_file import load_config_file

    policy = load_config_file(path)
    window = PolicyBrowserWindow(policy)
    window.start()
    return window
