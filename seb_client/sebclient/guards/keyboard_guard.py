"""Chặn tổ hợp phím tắt dùng để lách phòng thi.

Cài bằng hai lớp vì mỗi lớp có lỗ hổng riêng:

1. `QShortcut` với `Qt.ApplicationShortcut` — bắt các tổ hợp cố định (F12,
   Ctrl+Shift+I…). Đơn giản nhưng chỉ bắt đúng tổ hợp đã liệt kê.
2. `eventFilter` trên **chính `web_view`** — chặn mọi phím theo *mẫu* (Ctrl+C, Ctrl+P…),
   nên các biến thể Shift/CapsLock cũng bị chặn. Không gắn filter này lên
   `QApplication`: làm vậy sẽ làm sập QWebEngineView (đã kiểm chứng, xem `install()`).

Chặn ở tầng Qt, không phụ thuộc JavaScript trong trang.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from ..constants import (
    VIOLATION_COPY_PASTE_ATTEMPT,
    VIOLATION_DEVTOOLS_DETECTED,
    VIOLATION_TAB_SWITCH,
)
from .base import BaseGuard

logger = logging.getLogger(__name__)


class KeyboardGuard(BaseGuard):
    name = "keyboard"
    violation_type = VIOLATION_COPY_PASTE_ATTEMPT

    # Tổ hợp bị chặn cứng, báo vi phạm DEVTOOLS.
    DEVTOOLS_SEQUENCES = [
        "F12",
        "Ctrl+Shift+I",
        "Ctrl+Shift+J",
        "Ctrl+Shift+C",
        "Shift+F5",
    ]

    # Tổ hợp chặn clipboard / in / lưu trang, báo vi phạm COPY_PASTE.
    CONTENT_SEQUENCES = [
        "Ctrl+C", "Ctrl+V", "Ctrl+X", "Ctrl+A",
        "Ctrl+P", "Ctrl+S", "Ctrl+U",
        "Ctrl+Shift+Delete", "Shift+Delete",
    ]

    def __init__(self, window, reporter=None, policy=None):
        super().__init__(window, reporter)
        self._shortcuts: list[QShortcut] = []
        self._view = None
        self._policy = policy

    def _devtools_sequences(self) -> list[str]:
        if self._policy is not None and self._policy.allow_devtools:
            return []
        return self.DEVTOOLS_SEQUENCES

    def _content_sequences(self) -> list[str]:
        """Tổ hợp chặn nội dung, lọc theo policy của file `.seb` nếu có."""
        if self._policy is None:
            return self.CONTENT_SEQUENCES
        sequences = []
        for sequence in self.CONTENT_SEQUENCES:
            if sequence == "Ctrl+P":
                # In là một khoá riêng trong SEB, không nằm trong clipboard.
                if not self._policy.allow_print:
                    sequences.append(sequence)
                continue
            if self._policy.allow_copy_paste:
                continue
            sequences.append(sequence)
        return sequences

    def install(self) -> None:
        for sequence in self._devtools_sequences():
            shortcut = QShortcut(QKeySequence(sequence), self._window)
            shortcut.setContext(Qt.ApplicationShortcut)
            shortcut.activated.connect(
                lambda seq=sequence: self.report(
                    {"sequence": seq, "category": "devtools"},
                    dedupe=False,
                    event_type=VIOLATION_DEVTOOLS_DETECTED,
                )
            )
            self._shortcuts.append(shortcut)

        for sequence in self._content_sequences():
            shortcut = QShortcut(QKeySequence(sequence), self._window)
            shortcut.setContext(Qt.ApplicationShortcut)
            shortcut.activated.connect(
                lambda seq=sequence: self.report(
                    {"sequence": seq, "category": "clipboard"}, dedupe=False
                )
            )
            self._shortcuts.append(shortcut)

        # Gắn event filter vào CHÍNH web_view, KHÔNG gắn vào QApplication.
        # Đã kiểm chứng thực nghiệm: `QApplication.installEventFilter()` làm
        # segfault QWebEngineView ngay khi trang bắt đầu render. Gắn vào view
        # thì chạy ổn, và phạm vi thu hẹp hơn — chỉ cần chặn phím khi con trỏ
        # đang trong vùng thi.
        self._view = self._window.web_view
        self._view.installEventFilter(self)
        self._installed = True
        logger.info("keyboard_guard: da chan %d to hop phim", len(self._shortcuts))

    def uninstall(self) -> None:
        for shortcut in self._shortcuts:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self._shortcuts.clear()
        if getattr(self, "_view", None) is not None:
            try:
                self._view.removeEventFilter(self)
            except (RuntimeError, TypeError):
                pass
            self._view = None
        self._installed = False

    def eventFilter(self, obj, event):  # noqa: N802 - chữ ký bắt buộc của Qt
        from PySide6.QtCore import QEvent

        if event.type() != QEvent.KeyPress:
            return False

        key = event.key()
        modifiers = event.modifiers()

        ctrl = bool(modifiers & Qt.ControlModifier)
        alt = bool(modifiers & Qt.AltModifier)
        shift = bool(modifiers & Qt.ShiftModifier)
        meta = bool(modifiers & Qt.MetaModifier)

        is_devtools = key == Qt.Key_F12 or (ctrl and shift and key in (Qt.Key_I, Qt.Key_J, Qt.Key_C))
        is_content = ctrl and key in (
            Qt.Key_C, Qt.Key_V, Qt.Key_X, Qt.Key_A,
            Qt.Key_P, Qt.Key_S, Qt.Key_U,
        )
        is_content = is_content or (shift and key == Qt.Key_Delete)
        is_switch = alt and key == Qt.Key_Tab
        is_meta_leak = meta and key in (Qt.Key_H, Qt.Key_I, Qt.Key_J, Qt.Key_C)

        # Policy từ file `.seb` có thể NỚI LỎNG từng nhóm. Kiểm tra ở đây chứ
        # không chỉ ở `install()` vì eventFilter chặn theo mẫu phím, độc lập
        # với các QShortcut đã đăng ký.
        if self._policy is not None:
            if self._policy.allow_devtools:
                is_devtools = False
            if self._policy.allow_print and key == Qt.Key_P and ctrl and not shift:
                is_content = False
            if self._policy.allow_copy_paste and key in (
                Qt.Key_C, Qt.Key_V, Qt.Key_X, Qt.Key_A,
            ):
                is_content = False
            if not self._policy.block_alt_tab:
                is_switch = False

        if is_devtools:
            self.report(
                {"category": "devtools", "key": _key_name(key)},
                dedupe=False,
                event_type=VIOLATION_DEVTOOLS_DETECTED,
            )
            return True
        if is_content:
            self.report({"category": "clipboard", "key": _key_name(key)}, dedupe=False)
            return True
        if is_switch:
            # Alt+Tab phai la TAB_SWITCH: do la loai vi pham ma GV theo doi
            # tren dashboard va co so dem rieng. Neu de mac dinh
            # COPY_PASTE_ATTEMPT thi thoi gian chuyen cua so se bi ghi sai
            # vao thong keo clipboard.
            self.report(
                {"category": "window_switch", "key": "Alt+Tab"},
                dedupe=False,
                event_type=VIOLATION_TAB_SWITCH,
            )
            return True
        if is_meta_leak:
            self.report({"category": "clipboard", "key": _key_name(key)}, dedupe=False)
            return True

        return False


def _key_name(key: int) -> str:
    from PySide6.QtCore import Qt

    name = Qt.Key(key).name
    return name.removeprefix("Key_")