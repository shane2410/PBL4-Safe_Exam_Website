"""Interface chung cho các lớp tích hợp hệ điều hành.

Mỗi OS có cách chặn khác nhau hoàn toàn. Guard chỉ làm việc ở tầng ứng dụng,
nên những cơ chế mạnh (khoá clipboard hệ thống, phát hiện Alt+Tab toàn cục,
ẩn taskbar) buộc phải gọi xuống tầng hệ điều hành — đó là vai trò của adapter.

Nguyên tắc: **thiếu thì báo thiếu, không giả vờ có**. Mỗi phương thức trả về giá
trị và báo cảnh báo nếu không thực hiện được, để lớp trên quyết định có báo cho
giảng viên hay không.
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class BaseOSAdapter(Protocol):
    """Interface chung. Xem `windows_adapter` / `macos_adapter` / `linux_adapter`."""

    platform_key: str

    def capabilities(self) -> frozenset[str]:
        """Tập cơ chế thực sự thực hiện được trên máy này."""

    def supported(self, capability: str) -> bool:
        """Cơ chế này có khả dụng không."""

    def enter_kiosk(self) -> bool:
        """Ẩn taskbar/dock, khóa task switcher."""

    def exit_kiosk(self) -> None:
        """Hoàn nguyên (dùng khi thoát client, không phải khi đóng bài)."""

    def lock_clipboard(self) -> bool:
        """Khoá clipboard hệ thống nếu OS cho phép."""

    def clear_clipboard(self) -> bool:
        """Xoá nội dung clipboard."""

    def start_monitor_switch_detection(self, callback) -> bool:
        """Gọi `callback()` khi người dùng rời cửa sổ thi sang ứng dụng khác."""

    def stop_monitor_switch_detection(self) -> None:
        ...

    def block_print(self) -> bool:
        """Chặn thao tác in của hệ thống."""

    def describe(self) -> str:
        """Mô tả ngắn để log/ghi vào báo cáo hỗ trợ."""