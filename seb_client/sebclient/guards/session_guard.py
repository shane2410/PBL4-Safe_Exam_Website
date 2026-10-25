"""Theo dõi vòng đời phiên thi: hết giờ, mất kết nối, trạng thái bị khoá.

Guard này KHÔNG gửi vi phạm — nó chỉ quan sát và điều khiển hiển thị. Những
gì đếm được (số lần vi phạm, ngưỡng) đã có việc của `BaseGuard.report`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import QTimer

from .base import BaseGuard

logger = logging.getLogger(__name__)


class SessionGuard(BaseGuard):
    """Đếm ngược thời gian và phát tín hiệu khi phiên kết thúc."""

    name = "session"

    def __init__(
        self,
        window,
        reporter=None,
        on_timeout=None,
        on_expired=None,
        os_adapter=None,
        on_window_switch=None,
    ):
        super().__init__(window, reporter)
        self._on_timeout = on_timeout
        self._on_expired = on_expired
        self._on_window_switch = on_window_switch
        self._os = os_adapter
        self._deadline: datetime | None = None
        self._expired_fired = False
        self._switch_monitoring = False

    def set_deadline(self, remaining_seconds: int | None) -> None:
        """Đặt mốc hết giờ.

        Ưu tiên `remaining_seconds` của server thay vì tự cộng `server_time`:
        đồng hồ của thí sinh có thể sai, còn deadline là mốc do GV quyết định.
        """
        if remaining_seconds is None:
            self._deadline = None
            return
        self._deadline = datetime.now(timezone.utc) + timedelta(seconds=remaining_seconds)
        self._expired_fired = False
        logger.info("Hết giờ sau %s giây", remaining_seconds)

    def remaining_seconds(self) -> int | None:
        if self._deadline is None:
            return None
        delta = (self._deadline - datetime.now(timezone.utc)).total_seconds()
        return max(0, int(delta))

    def install(self) -> None:
        self._timer = QTimer(self._window)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        if self._os is not None and self._on_window_switch is not None:
            self._switch_monitoring = self._os.start_monitor_switch_detection(
                self._on_window_switch
            )
            if not self._switch_monitoring:
                logger.warning(
                    "Khong the phat hien chuyen sang ung dung khac tren nen tang nay — "
                    "se ghi nhan thieu co che nay cho giang vien"
                )

        self._installed = True
        logger.info("session_guard: bat dau dem nguoc")

    def uninstall(self) -> None:
        if getattr(self, "_timer", None) is not None:
            self._timer.stop()
            self._timer = None
        if self._switch_monitoring and self._os is not None:
            self._os.stop_monitor_switch_detection()
            self._switch_monitoring = False
        self._installed = False

    def _tick(self) -> None:
        # Chuyển cửa sổ phải kiểm tra MỖI giây, kể cả khi chưa đặt deadline.
        if self._switch_monitoring and self._os is not None:
            self._os.poll_window_switch()

        if self._deadline is None or self._expired_fired:
            return
        remaining = self.remaining_seconds()
        if remaining is None:
            return
        if remaining <= 0:
            self._expired_fired = True
            logger.warning("Hết giờ làm bài")
            if self._on_expired:
                self._on_expired()