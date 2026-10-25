"""Tích hợp Linux: X11 và Wayland.

Khác biệt quan trọng nhất giữa hai loại:

* **X11** — đọc được `_NET_ACTIVE_WINDOW`, nên phát hiện được người dùng
  chuyển sang ứng dụng khác (Alt+Tab). Đây là cơ chế mạnh nhất ngoài Windows.
* **Wayland** — **không** cho đọc cửa sổ đang focus của ứng dụng khác. Không có
  API tương đương nào mà không cần cơ chế bên thứ ba (portal chưa đủ).

Vì vậy trên Wayland `monitor_switch` **không** nằm trong capability, và client
phải báo cho giảng viên biết máy đó không được bảo vệ đầy đủ — thay vì bật một
cơ chế chỉ mang lại cảm giác an toàn giả.
"""

from __future__ import annotations

import logging
import os
import subprocess

from .capability_matrix import CAPABILITIES, detect_platform

logger = logging.getLogger(__name__)


class LinuxAdapter:
    """Adapter Linux. Dùng được ở cả X11 lẫn Wayland, nhưng khả năng khác nhau."""

    def __init__(self, platform_key: str | None = None):
        self.platform_key = platform_key or detect_platform()
        self._xlib = None
        self._display = None
        self._root = None
        self._monitoring = False
        self._callback = None

    # ------------------------------------------------------------ capability

    def capabilities(self) -> frozenset[str]:
        return CAPABILITIES.get(self.platform_key, frozenset())

    def supported(self, capability: str) -> bool:
        return capability in self.capabilities()

    def describe(self) -> str:
        base = f"Linux ({self.platform_key})"
        if self.platform_key == "linux:wayland":
            return base + " — THIẾU phát hiện chuyển cửa sổ (giới hạn của Wayland)"
        return base + " — X11, đủ cơ chế"

    # ------------------------------------------------------------------ kiosk

    def enter_kiosk(self) -> bool:
        """Ẩn taskbar/dock.

        Trên X11 có thể dùng `wmctrl` để ẩn panel; trên Wayland thì tuỳ trình
        quản lý cửa sổ và thường không làm được. Trả False nếu không bật được —
        guard sẽ ghi nhận để giảng viên biết.
        """
        if self.platform_key == "linux:wayland":
            logger.warning("Wayland: khong an duoc taskbar bang API chung")
            return False
        try:
            subprocess.run(
                ["wmctrl", "-b", "add,hidden"],
                check=True, capture_output=True, timeout=3,
            )
            return True
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            logger.warning("Khong an taskbar duoc (%s)", exc)
            return False

    def exit_kiosk(self) -> None:
        if self.platform_key == "linux:wayland":
            return
        try:
            subprocess.run(
                ["wmctrl", "-b", "remove,hidden"],
                check=False, capture_output=True, timeout=3,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

    # -------------------------------------------------------------- clipboard

    def clear_clipboard(self) -> bool:
        """Xoá clipboard qua `xclip`/`wl-copy`.

        Lưu ý: trên Wayland `wl-copy -c` chỉ xoá được clipboard của chính
        compositor session, không chặn được ứng dụng khác ghi vào. Vì vậy đây
        vẫn là biện pháp hỗ trợ, không phải khoá thật.
        """
        if self.platform_key == "linux:wayland":
            return self._run_quiet(["wl-copy", "-c"])
        return self._run_quiet(["xclip", "-selection", "clipboard", "-i", "/dev/null"])

    def lock_clipboard(self) -> bool:
        """Linux không có cơ chế khoá clipboard tổng quát cho mọi ứng dụng."""
        return False

    def block_print(self) -> bool:
        """Không có API chặn in tổng quát. Guard tầng ứng dụng vẫn chặn Ctrl+P."""
        return False

    # ------------------------------------------------------- monitor switching

    def start_monitor_switch_detection(self, callback) -> bool:
        """Chỉ X11 làm được, bằng cách theo `_NET_ACTIVE_WINDOW`."""
        if not self.supported("monitor_switch"):
            logger.warning(
                "Bo qua phat hien chuyen cua so: khong ho tro tren %s", self.platform_key
            )
            return False

        try:
            from Xlib import display as xdisplay  # noqa: N811
            from Xlib import X  # noqa: N402
        except ImportError:
            logger.warning(
                "Thieu python-xlib — khong the phat hien chuyen cua so tren X11"
            )
            return False

        try:
            self._display = xdisplay.Display()
            self._root = self._display.screen().root
            self._window_id = int(self._root.get_id())
            self._xlib = X
        except Exception as exc:  # noqa: BLE001
            logger.warning("Khong ket noi duoc X server: %s", exc)
            return False

        self._callback = callback
        self._monitoring = True
        logger.info("Bat dau theo doi chuyen cua so qua _NET_ACTIVE_WINDOW")
        return True

    def poll_window_switch(self) -> None:
        """Gọi callback nếu cửa sổ focus đã đổi khỏi cửa sổ thi.

        Được `session_guard` gọi định kỳ. Dùng polling thay vì event vì
        `_NET_ACTIVE_WINDOW` không có thông báo thay đổi qua XCB đơn giản.
        """
        if not self._monitoring or self._display is None:
            return
        try:
            active = self._root.get_full_property(
                self._xlib.Xatom.IN_NET_ACTIVE_WINDOW, self._xlib.XA_WINDOW
            )
            if active and active.value:
                current = int(active.value[0])
                if current != self._window_id and self._callback:
                    self._callback()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Doc trang thai focus that bai: %s", exc)

    def stop_monitor_switch_detection(self) -> None:
        self._monitoring = False
        if self._display is not None:
            try:
                self._display.close()
            except Exception:  # noqa: BLE001
                pass
            self._display = None

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _run_quiet(command: list[str]) -> bool:
        if not os.path.exists(command[0]) and not _in_path(command[0]):
            logger.debug("Khong tim thay %s", command[0])
            return False
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=3)
            return True
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            logger.debug("Lenh %s that bai: %s", command[0], exc)
            return False


def _in_path(name: str) -> bool:
    from shutil import which

    return which(name) is not None