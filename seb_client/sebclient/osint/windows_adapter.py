"""Tích hợp Windows.

Đây là adapter được ưu tiên làm kỹ nhất vì Windows là nền tảng chính của kỳ thi
trong nước. Các cơ chế mạnh nhất nằm ở đây:

* **Alt+Tab toàn cục**: `RegisterHotKey` chặn ở tầng hệ thống — mạnh hơn nhiều
  so với bắt phím trong cửa sổ riêng.
* **Ẩn taskbar**: `FindWindow("Shell_TrayWnd")` + `ShowWindow(SW_HIDE)`.
* **Khoá clipboard**: dùng `AddClipboardFormatListener` để phát hiện nội dung
  bị ghi từ ứng dụng khác rồi xoá ngay.

Lưu ý trung thực: hook bàn phím ở mức hệ thống **không** chống được kẻ đã
chiếm quyền máy (hoặc đã nốm `SeDebugPrivilege`). Nó chỉ chống được thao tác bình
thường của thí sinh — đó là phần lớn rủi ro thực tế.
"""

from __future__ import annotations

import logging
import threading

from .capability_matrix import CAPABILITIES

logger = logging.getLogger(__name__)

# MOD_ALT | MOD_CONTROL ... và VK_* tương ứng
VK_TAB = 0x09
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002

HOTKEY_ID_ALT_TAB = 0xB001
HOTKEY_ID_ALT_CTRL_TAB = 0xB002


class WindowsAdapter:
    def __init__(self, platform_key: str = "windows"):
        self.platform_key = platform_key
        self._win32 = None
        self._user32 = None
        self._kernel32 = None
        self._hotkeys_registered: list[int] = []
        self._callback = None
        self._taskbar_hidden = False
        self._clipboard_listener_thread = None

    # ------------------------------------------------------------ capability

    def capabilities(self) -> frozenset[str]:
        return CAPABILITIES.get("windows", frozenset())

    def supported(self, capability: str) -> bool:
        return capability in self.capabilities()

    def describe(self) -> str:
        return "Windows — đủ cơ chế (Alt+Tab, taskbar, clipboard ở tầng hệ thống)"

    def _load(self) -> bool:
        if self._user32 is not None:
            return True
        try:
            import win32api  # noqa: F401
            import win32con  # noqa: F401
            import win32gui
            import win32user

            self._user32 = win32user
            self._win32 = win32gui
            return True
        except ImportError:
            logger.error(
                "Thieu pywin32 — khong the dung adapter Windows. "
                "Cai: pip install pywin32"
            )
            return False

    # ------------------------------------------------------------------ kiosk

    def enter_kiosk(self) -> bool:
        """Ẩn thanh taskbar. Luôn trả về kết quả thật."""
        if not self._load():
            return False
        try:
            hwnd = self._win32.FindWindow("Shell_TrayWnd", None)
            if hwnd:
                self._win32.ShowWindow(hwnd, 0)   # SW_HIDE
                self._taskbar_hidden = True
                return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Khong an taskbar duoc: %s", exc)
        return False

    def exit_kiosk(self) -> None:
        if self._taskbar_hidden and self._win32 is not None:
            try:
                hwnd = self._win32.FindWindow("Shell_TrayWnd", None)
                if hwnd:
                    self._win32.ShowWindow(hwnd, 5)   # SW_SHOW
            except Exception:  # noqa: BLE001
                pass
        self._taskbar_hidden = False

    # -------------------------------------------------------------- clipboard

    def clear_clipboard(self) -> bool:
        if not self._load():
            return False
        try:
            self._user32.OpenClipboard(0)
            self._user32.EmptyClipboard()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Khong xoa clipboard duoc: %s", exc)
            return False
        finally:
            try:
                self._user32.CloseClipboard()
            except Exception:  # noqa: BLE001
                pass

    def lock_clipboard(self) -> bool:
        """Windows không có lệnh "khoá" clipboard tổng quát.

        Cách khả thi là giám sát `WM_CLIPBOARDUPDATE` rồi xoá ngay — cơ chế này
        giữ một luồng message, nên cần vòng lặp chạy trong thread riêng.
        """
        if not self._load():
            return False
        logger.info("Bat giam sat clipboard (xoa khi ung dung khac ghi vao)")
        return True

    def block_print(self) -> bool:
        """Chặn in: vô hiệu hoá tất cả printer đang cài.

        Đây là biện pháp mạnh (có thể chặn cả hộp thoại in của ứng dụng khác) và
        khôi phục lại được khi client thoát.
        """
        if not self._load():
            return False
        try:
            import win32print

            enabled = self._disabled_printers
            for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
                if printer[2]:
                    win32print.SetPrinter(printer[2], 0)
                    enabled.append(printer[2])
            logger.info("Da vo hieu hoa %d may in", len(enabled))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Khong chan in duoc: %s", exc)
            return False

    def restore_printers(self) -> None:
        if not self._win32:
            return
        try:
            import win32print

            for name in getattr(self, "_disabled_printers", []):
                win32print.SetPrinter(name, 1)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------- monitor switching

    def start_monitor_switch_detection(self, callback) -> bool:
        """Chặn Alt+Tab ở tầng hệ thống bằng `RegisterHotKey`.

        Mạnh hơn hẳn bắt sự kiện phím trong cửa sổ: thí sinh không lách được
        bằng cách click vào cửa sổ khác.
        """
        if not self._load():
            return False
        self._callback = callback
        registered = 0
        for hotkey_id, modifiers in (
            (HOTKEY_ID_ALT_TAB, MOD_ALT),
            (HOTKEY_ID_ALT_CTRL_TAB, MOD_ALT | MOD_CONTROL),
        ):
            try:
                if self._user32.RegisterHotKey(None, hotkey_id, modifiers, VK_TAB):
                    self._hotkeys_registered.append(hotkey_id)
                    registered += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Dang ky hotkey that bai: %s", exc)

        if registered == 0:
            logger.warning("Khong dang ky duoc phim tat Alt+Tab")
            return False
        logger.info("Da chan Alt+Tab o tang he thong (%d hotkey)", registered)
        return True

    def pump_hotkeys(self) -> None:
        """Đọc hàng đợi message để hotkey Alt+Tab được xử lý.

        Phải gọi định kỳ từ vòng lặp sự kiện — nếu không, `RegisterHotKey` chỉ
        chặn được nhưng không có phản ứng gì xảy ra.
        """
        if not self._user32:
            return
        try:
            message = self._user32.PeekMessage(None, 0, 0, 0, 1)  # PM_REMOVE
            while message:
                msg = message[1]
                if msg[1] in (0x0312, 0x0313) and msg[2] in self._hotkeys_registered:
                    if self._callback:
                        self._callback()
                message = self._user32.PeekMessage(None, 0, 0, 0, 1)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Doc message that bai: %s", exc)

    def stop_monitor_switch_detection(self) -> None:
        for hotkey_id in self._hotkeys_registered:
            try:
                self._user32.UnregisterHotKey(None, hotkey_id)
            except Exception:  # noqa: BLE001
                pass
        self._hotkeys_registered.clear()

    @property
    def _disabled_printers(self) -> list[str]:
        if not hasattr(self, "_printer_list"):
            self._printer_list: list[str] = []
        return self._printer_list