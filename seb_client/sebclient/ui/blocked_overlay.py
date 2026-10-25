"""Màn hình chặn: thông báo phiên thi đã bị khoá / bị buộc nộp bài.

Hiển thị ngay khi server bắt buộc nộp (`force_submit`) hoặc khi phiên hết giờ.
Không cho thí sinh đóng cửa sổ — đóng ở đây sẽ khiến họ tưởng mình còn đang thi.

Cố ý không có nút "Thử lại": mọi việc sau đó là của giám thị.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_STYLE = """
QWidget#blockedRoot { background: #450a0a; }
QLabel#title { color: #fecaca; font-size: 20px; font-weight: 700; }
QLabel#reason { color: #fca5a5; font-size: 14px; }
QLabel#hint { color: #f87171; font-size: 12px; }
"""


class BlockedOverlay(QWidget):
    def __init__(self, reason: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("blockedRoot")
        self.setWindowTitle("Phiên thi đã kết thúc")
        self.setStyleSheet(_STYLE)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(14)

        title = QLabel("Phiên thi đã kết thúc")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self._reason = QLabel(reason)
        self._reason.setObjectName("reason")
        self._reason.setWordWrap(True)
        self._reason.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._reason)

        hint = QLabel("Vui lòng liên hệ giám thị nếu cần hỗ trợ.")
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        layout.addStretch(1)

    def set_reason(self, reason: str) -> None:
        self._reason.setText(reason)

    def closeEvent(self, event):  # noqa: N802
        """Không cho đóng — giám thị mới là người quyết định."""
        event.ignore()