"""Màn hình chặn: thông báo phiên thi đã bị khoá / bị buộc nộp bài.

Hiển thị ngay khi server bắt buộc nộp (`force_submit`) hoặc khi phiên hết giờ.
Màn hình native cũng dùng khi không vào được phòng, kể cả khi WebEngine lỗi.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

_STYLE = """
QWidget#blockedRoot { background: #450a0a; }
QLabel#title { color: #fecaca; font-size: 20px; font-weight: 700; }
QLabel#reason { color: #fca5a5; font-size: 14px; }
QLabel#hint { color: #f87171; font-size: 12px; }
"""


class BlockedOverlay(QWidget):
    exit_requested = Signal()

    def __init__(self, reason: str, parent: QWidget | None = None, *,
                 title: str = "Phiên thi đã kết thúc"):
        super().__init__(parent)
        self.setObjectName("blockedRoot")
        self.setWindowTitle(title)
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(14)

        title = QLabel(title)
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self._reason = QLabel(reason)
        self._reason.setTextFormat(Qt.PlainText)
        self._reason.setObjectName("reason")
        self._reason.setWordWrap(True)
        self._reason.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._reason)

        hint = QLabel("Vui lòng liên hệ giám thị nếu cần hỗ trợ.")
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        button = QPushButton("Thoát SEB")
        button.clicked.connect(self.exit_requested.emit)
        layout.addWidget(button, alignment=Qt.AlignCenter)

        layout.addStretch(1)

    def set_reason(self, reason: str) -> None:
        self._reason.setText(reason)
