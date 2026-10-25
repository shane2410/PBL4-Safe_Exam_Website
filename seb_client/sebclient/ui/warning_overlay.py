"""Màn hình cảnh báo khi thí sinh sắp vượt ngưỡng vi phạm.

Cơ chế: khi còn `threshold` lần vi phạm nữa là tự nộp bài, hiện đếm ngược
`threshold x seconds_per_violation`. Học sinh thấy hậu quả trước khi xảy ra —
đây là điều phân biệt hệ thống có cảnh báo với hệ thống chỉ phạt.

Vị trí hiển thị: băng dọc giữa màn hình, không chặn tầm nhìn vào đề.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_STYLE = """
QWidget#warnRoot {
    background: rgba(180, 83, 9, 0.92);
    border: 2px solid #fbbf24;
    border-radius: 12px;
}
QLabel#title { color: #fffbeb; font-weight: 700; font-size: 16px; }
QLabel#body  { color: #fef3c7; font-size: 14px; }
QLabel#count { color: #ffffff; font-weight: 700; font-size: 30px; }
"""


def format_countdown(total_seconds: int) -> str:
    """Định dạng mm:ss, không âm."""
    safe = max(0, int(total_seconds))
    minutes, seconds = divmod(safe, 60)
    return f"{minutes:02d}:{seconds:02d}"


class WarningOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("warnRoot")
        self.setStyleSheet(_STYLE)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(6)

        title = QLabel("Cảnh báo an toàn")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self._body = QLabel("")
        self._body.setObjectName("body")
        self._body.setWordWrap(True)
        self._body.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._body)

        self._count = QLabel("")
        self._count.setObjectName("count")
        self._count.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._count)

        self._remaining = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.hide()

    @property
    def is_counting(self) -> bool:
        return self._timer.isActive()

    def show_warning(self, threshold: int, seconds_per_violation: int = 5) -> None:
        """Bật cảnh báo trong `threshold x seconds_per_violation` giây."""
        self._remaining = max(1, threshold * seconds_per_violation)
        self._body.setText(
            f"Còn {threshold} lần vi phạm nữa là hệ thống sẽ tự thu bài."
        )
        self._tick()
        self._timer.start(1000)
        self._reposition()
        self.show()
        self.raise_()

    def hide_warning(self) -> None:
        self._timer.stop()
        self._remaining = 0
        self.hide()

    def _tick(self) -> None:
        self._count.setText(format_countdown(self._remaining))
        self._remaining -= 1
        if self._remaining < 0:
            self.hide_warning()

    def _reposition(self) -> None:
        """Canh giữa theo cửa sổ cha."""
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        x = (parent.width() - self.width()) // 2
        y = (parent.height() - self.height()) // 2
        self.move(max(0, x), max(0, y))

    def closeEvent(self, event):  # noqa: N802
        event.ignore()