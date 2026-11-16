"""Cửa sổ đăng nhập: nhập tài khoản thí sinh + mã phòng thi.

Không có nút thoát ẩn, không có menu. Sau khi đăng nhập thành công, cửa sổ này
đóng lại và phát tín hiệu `login_succeeded` để app mở ExamWindow.
"""

from __future__ import annotations

import asyncio
import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..api.client import ApiClient, ApiError
from ..constants import APP_DISPLAY_NAME, APP_NAME

logger = logging.getLogger(__name__)


class LoginWindow(QWidget):
    login_succeeded = Signal(dict, str)
    login_failed = Signal(str)

    def __init__(self, api: ApiClient, parent: QWidget | None = None):
        super().__init__(parent)
        self._api = api
        self._room_code = ""
        self.setWindowTitle(APP_NAME)
        self.setObjectName("loginRoot")
        self.setFixedSize(460, 380)
        self.setStyleSheet(_STYLE)

        self._build_ui()
        self._username.setFocus()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        title = QLabel(APP_DISPLAY_NAME)
        title.setFont(QFont("Segoe UI", 17, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)

        subtitle = QLabel("Đăng nhập để vào phòng thi")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("subtitle")
        outer.addWidget(subtitle)

        outer.addSpacing(6)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._username = QLineEdit()
        self._username.setPlaceholderText("Tên đăng nhập")
        self._username.setMaxLength(50)
        self._username.textChanged.connect(self._on_field_changed)

        self._password = QLineEdit()
        self._password.setPlaceholderText("Mật khẩu")
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setMaxLength(128)
        self._password.textChanged.connect(self._on_field_changed)

        self._room_code = QLineEdit()
        self._room_code.setPlaceholderText("Mã phòng thi, ví dụ: ABC123")
        self._room_code.setMaxLength(12)
        self._room_code.textChanged.connect(self._on_room_code_changed)

        form.addRow("Tài khoản:", self._username)
        form.addRow("Mật khẩu:", self._password)
        form.addRow("Mã phòng:", self._room_code)
        outer.addLayout(form)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setObjectName("status")
        self._status.setMinimumHeight(38)
        outer.addWidget(self._status)

        self._submit = QPushButton("Vào phòng thi")
        self._submit.setObjectName("submit")
        self._submit.setMinimumHeight(44)
        self._submit.setEnabled(False)
        self._submit.clicked.connect(self._on_submit)
        outer.addWidget(self._submit)

        outer.addStretch(1)

        footer = QLabel("Mọi hành vi trong phòng thi đều được ghi nhận phục vụ đối chiếu.")
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignCenter)
        footer.setWordWrap(True)
        outer.addWidget(footer)

        self._room_code.returnPressed.connect(self._on_submit)

    def _on_field_changed(self) -> None:
        self._refresh_submit()

    def _on_room_code_changed(self, text: str) -> None:
        # Chuẩn hoá mã phòng về chữ hoa ngay khi gõ. Backend cũng tự upper() khi
        # join socket, nhưng hiển thị mã khác nhau giữa client và GV rất dễ gây
        # hiểu nhầm lúc thực tế.
        upper = text.upper()
        if upper != text:
            cursor = self._room_code.cursorPosition()
            self._room_code.blockSignals(True)
            self._room_code.setText(upper)
            self._room_code.blockSignals(False)
            self._room_code.setCursorPosition(cursor)
        self._refresh_submit()

    def _refresh_submit(self) -> None:
        self._submit.setEnabled(
            len(self._username.text().strip()) >= 3
            and len(self._password.text()) >= 4
            and len(self._room_code.text().strip()) >= 4
        )

    def _set_status(self, message: str, level: str = "info") -> None:
        self._status.setProperty("level", level)
        self._status.setText(message)
        # Đổi property động cần style lại mới áp dụng.
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)

    def _on_submit(self, *_args) -> None:
        """Slot đồng bộ của Qt — lên lịch coroutine xử lý đăng nhập vào event loop."""
        asyncio.ensure_future(self._handle_submit())

    async def _handle_submit(self) -> None:
        self._submit.setEnabled(False)
        self._submit.setText("Đang kiểm tra...")
        self._set_status("Đang liên hệ máy chủ...")

        try:
            user = await self._api.login(self._username.text(), self._password.text())
        except ApiError as exc:
            logger.warning("Dang nhap that bai: %s", exc.message)
            self._set_status(exc.message, "error")
            self.login_failed.emit(exc.message)
            self._submit.setText("Vào phòng thi")
            self._refresh_submit()
            self._password.selectAll()
            self._password.setFocus()
            return
        except Exception as exc:  # noqa: BLE001
            logger.error("Loi he thong khi dang nhap: %s", exc)
            msg = f"Lỗi kết nối máy chủ: {exc}"
            self._set_status(msg, "error")
            self.login_failed.emit(msg)
            self._submit.setText("Vào phòng thi")
            self._refresh_submit()
            return

        role_code = ((user.get("role") or {}).get("code") or "").strip().upper()
        if role_code != "STUDENT":
            # Fail-closed: không xác định được vai trò thì cũng từ chối. Nếu để
            # qua khi role rỗng, một thay đổi tên trường ở backend là giáo viên
            # đăng nhập được vào client thí sinh.
            message = (
                "Tài khoản này không phải tài khoản thí sinh."
                if role_code
                else "Không xác định được vai trò tài khoản — đã từ chối cho an toàn."
            )
            self._set_status(message, "error")
            self.login_failed.emit(message)
            self._submit.setText("Vào phòng thi")
            self._refresh_submit()
            return

        if user.get("is_active") is False:
            message = "Tài khoản đã bị khoá. Vui lòng liên hệ giám thị."
            self._set_status(message, "error")
            self.login_failed.emit(message)
            self._submit.setText("Vào phòng thi")
            self._refresh_submit()
            return

        room_code = self._room_code.text().strip().upper()
        self._set_status("Đăng nhập thành công.")
        self.login_succeeded.emit(user, room_code)
        self.close()

    def show_error(self, message: str) -> None:
        self._set_status(message, "error")
        self._submit.setText("Vào phòng thi")
        self._refresh_submit()


_STYLE = """
QWidget#loginRoot { background: #0f172a; }
QLabel { color: #e2e8f0; }
QLabel#subtitle { color: #94a3b8; font-size: 12px; }
QLabel#footer { color: #64748b; font-size: 11px; }
QLabel#status { color: #94a3b8; font-size: 12px; padding: 2px 0; }
QLabel#status[level="error"] { color: #f87171; }
QLineEdit {
    background: #1e293b; color: #e2e8f0;
    border: 1px solid #334155; border-radius: 6px; padding: 9px 10px;
}
QLineEdit:focus { border: 1px solid #3b82f6; }
QPushButton#submit {
    background: #2563eb; color: #ffffff; border: none;
    border-radius: 6px; font-weight: 600;
}
QPushButton#submit:hover { background: #1d4ed8; }
QPushButton#submit:disabled { background: #1e293b; color: #475569; }
"""