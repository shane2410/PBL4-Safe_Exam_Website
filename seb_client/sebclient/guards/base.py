"""BaseGuard — lớp nền cho mọi cơ chế chặn trong phòng thi.

Nguyên tắc thiết kế:

* Guard chỉ **phát hiện**, không trực tiếp quyết định hình phạt. Việc đếm điểm
  và tự nộp bài thuộc về ExamWindow + server. Nhờ vậy thêm guard mới không phải
  sửa lại logic đếm.
* Mỗi guard khai báo `violation_type` đúng với `ALLOWED_EVENT_TYPES` của
  backend, sai là bị validate reject.
* `report_violation` có chống trùng: cùng một loại trong `dedupe_ms` chỉ gửi
  một lần, tránh việc người dùng Alt+Tab liên tục làm đầy bảng vi phạm.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from PySide6.QtCore import QObject

logger = logging.getLogger(__name__)

ViolationReporter = Callable[[str, dict[str, Any]], None]


class BaseGuard(QObject):
    """Lớp cơ sở của mọi guard.

    Kế thừa `QObject` là bắt buộc, không phải tuỳ chọn: `installEventFilter` của
    Qt chỉ nhận đối tượng QObject, nên guard dùng event filter sẽ văng TypeError
    nếu đây là class Python thuần.

    Subclass cần thiết kế:
        - đặt `violation_type`
        - ghi đè `install()` để gắn listener vào Qt/JS
        - (tuỳ chọn) ghi đè `uninstall()` để gỡ listener
    """

    name: str = "base"
    violation_type: str = ""
    dedupe_ms: int = 1500

    def __init__(self, window, reporter: ViolationReporter | None = None, parent=None):
        super().__init__(parent)
        self._window = window
        self._reporter = reporter
        self._installed = False
        self._last_reported_at: dict[str, float] = {}

    @property
    def installed(self) -> bool:
        return self._installed

    def install(self) -> None:
        """Gắn listener. Gọi lần đầu khi cửa sổ thi đã sẵn sàng."""
        raise NotImplementedError

    def uninstall(self) -> None:
        """Gỡ listener. Phải chịu được việc gọi khi chưa install."""
        raise NotImplementedError

    def report(
        self,
        detail: dict[str, Any] | None = None,
        dedupe: bool = True,
        event_type: str | None = None,
    ) -> bool:
        """Báo một sự kiện vi phạm. Trả True nếu thực sự đã gửi đi.

        `event_type` cho phép một guard báo nhiều loại vi phạm khác nhau — ví dụ
        keyboard_guard vừa báo `DEVTOOLS_DETECTED` vừa báo `COPY_PASTE_ATTEMPT`.
        Không có tham số này, cả hai sẽ bị ghi nhầm thành `violation_type` của
        guard và làm sai số liệu trên dashboard giám sát.
        """
        resolved_type = event_type or self.violation_type
        if not resolved_type:
            raise ValueError(f"{type(self).__name__} chưa khai báo violation_type")

        now = time.monotonic()
        if dedupe:
            last = self._last_reported_at.get(resolved_type, 0.0)
            if (now - last) * 1000 < self.dedupe_ms:
                return False
        self._last_reported_at[resolved_type] = now

        payload = {"guard": self.name, **((detail or {}) if isinstance(detail, dict) else {"value": detail})}
        logger.info("VIOLATION %s: %s", resolved_type, payload)

        if self._reporter:
            self._reporter(resolved_type, payload)
        return True

    def clear_dedupe(self) -> None:
        """Xoá lịch sử chống trùng — dùng khi đổi phòng hoặc sau khi GV nhập mật khẩu."""
        self._last_reported_at.clear()