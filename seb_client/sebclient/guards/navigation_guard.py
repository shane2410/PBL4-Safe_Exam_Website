"""Chặn điều hướng ra ngoài phòng thi và chặn cửa sổ con.

Đây là guard **quan trọng nhất** vì nó chặn ở tầng Qt, không phụ thuộc JavaScript
bên trong trang — thí sinh không vô hiệu hoá được bằng cách tắt JS trong
DevTools (vốn đã bị chặn).

Không có guard nào ở tài liệu hướng dẫn chính thức của SEB làm tốt hơn ở điểm
này.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from PySide6.QtCore import QUrl

from .base import BaseGuard

logger = logging.getLogger(__name__)

# Scheme không có cổng mặc định, không thuộc origin nào được phép.
_WELL_KNOWN_PORTS = {"http": 80, "https": 443}


def _origin_key(scheme: str | None, host: str | None, port: int | None) -> str | None:
    """Chuẩn hoá (scheme, host, port) thành một khoá so sánh duy nhất.

    QUrl.port() trả -1 khi URL không có cổng, nên phải chuẩn hoá một lần ở đây
    thay vì ghép chuỗi rồi parse lại — cách đó vỡ với URL không có cổng.
    """
    scheme = (scheme or "").lower()
    host = (host or "").lower()
    if not scheme or not host:
        return None
    if not port or port <= 0:
        port = _WELL_KNOWN_PORTS.get(scheme, 0)
    if port <= 0:
        return None
    return f"{scheme}://{host}:{port}"


class NavigationGuard(BaseGuard):
    name = "navigation"
    violation_type = "UNAUTHORIZED_CLIENT"

    def __init__(self, window, allowed_origins: list[str], reporter=None):
        super().__init__(window, reporter)
        self._reloading = False
        self._allowed = set()
        for origin in allowed_origins:
            parsed = urlparse(origin.strip())
            key = _origin_key(parsed.scheme, parsed.hostname, parsed.port)
            if key:
                self._allowed.add(key)

    def install(self) -> None:
        view = self._window.web_view
        view.urlChanged.connect(self._on_url_changed)
        self._installed = True
        logger.info("navigation_guard: cho phep %s", ", ".join(sorted(self._allowed)))

    def uninstall(self) -> None:
        if not self._installed:
            return
        view = self._window.web_view
        try:
            view.urlChanged.disconnect(self._on_url_changed)
        except (RuntimeError, TypeError):
            pass
        self._installed = False

    def is_allowed(self, url: QUrl) -> bool:
        """Origin có nằm trong danh sách cho phép không.

        So khớp theo scheme + host + port, không so chuỗi URL — tránh việc
        `http://localhost:5173.evil.com` lọt.
        """
        if url.scheme() in {"about", "qrc", "data"}:
            return True
        return _origin_key(url.scheme(), url.host(), url.port()) in self._allowed

    def _on_url_changed(self, url: QUrl) -> None:
        # URL rỗng xảy ra ở lúc khởi tạo view, chưa có ý nghĩa gì về bảo mật.
        # Quan trọng: cấm điều này còn vì `load()` sẽ phát `urlChanged` lần nữa,
        # dẫn tới reload vô hạn và treo tiến trình.
        if not url.isValid() or url.isEmpty():
            return
        if self.is_allowed(url):
            return

        logger.warning("Chuyen trang ra ngoai danh sach: %s", url.toString())

        # Chống đệ quy: `reload_exam()` lại gọi `load()` phát `urlChanged`.
        if self._reloading:
            return
        self._reloading = True
        try:
            self._window.reload_exam()
        finally:
            self._reloading = False