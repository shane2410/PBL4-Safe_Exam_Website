"""Tích hợp Windows.

Đây là adapter được ưu tiên làm kỹ nhất vì Windows là nền tảng chính của kỳ thi
trong nước. Các cơ chế mạnh nhất nằm ở đây:

* **Alt+Tab toàn cục**: `RegisterHotKey` chặn ở tầng hệ thống — mạnh hơn nhiều
  so với bắt phím trong cửa sổ riêng.
* **Ẩn taskbar**: `FindWindow("Shell_TrayWnd")` + `ShowWindow(SW_HIDE)`.
* **Chỉ dùng chuột trong kiosk**: hook `WH_KEYBOARD_LL` chặn bàn phím thường.
* **Khoá clipboard**: `OpenClipboard` + `EmptyClipboard` để xoá nội dung.

Vì sao dùng `ctypes.windll` thay vì pywin32:
bản trước import `win32user` — module KHÔNG tồn tại trong pywin32 (các hàm cần
dùng nằm ở `win32gui`, `win32clipboard`, hoặc `user32` của ctypes). ImportError
đó bị nuốt trong `_load()` nên **toàn bộ tầng hệ điều hành trên Windows bị vô
hiệu im lặng**: không chặn Alt+Tab, không ẩn taskbar, không xoá clipboard.
`ctypes` nằm trong stdlib Python trên Windows nên không thể thiếu module.

Adapter KHÔNG tự phát hiện chuyển cửa sổ bằng polling `GetForegroundWindow`:
`RegisterHotKey` chỉ chặn tổ hợp Alt+Tab, còn thí sinh vẫn có thể chuyển bằng
click chuột. Vì vậy `poll_window_switch` vừa (a) xử lý hàng đợi message để
hotkey có tác dụng, vừa (b) so cửa sổ foreground hiện tại với cửa sổ của tiến
trình này để phát hiện rời cửa sổ thi.

Lưu ý trung thực: hook bàn phím ở mức hệ thống **không** chống được kẻ đã
chiếm quyền máy (hoặc đã nốm `SeDebugPrivilege`). Nó chỉ chống được thao tác bình
thường của thí sinh — đó là phần lớn rủi ro thực tế.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from typing import Callable, Optional

from .capability_matrix import CAPABILITIES

logger = logging.getLogger(__name__)

VK_TAB = 0x09
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002

HOTKEY_ID_ALT_TAB = 0xB001
HOTKEY_ID_ALT_CTRL_TAB = 0xB002

# Hằng số Win32
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
SW_HIDE = 0
SW_SHOW = 5
WH_KEYBOARD_LL = 13
HC_ACTION = 0
_LRESULT = ctypes.c_ssize_t


class _MSG(ctypes.Structure):
    """Cấu trúc MSG của Win32 (định nghĩa tay để không phụ thuộc pywin32)."""

    _fields_ = [
        ("hWnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


def _bind_windows_apis(user32) -> None:
    """Khai báo kiểu tham số.

    Không khai báo thì 64-bit Windows cắt cụt pointer (HWND/HANDLE), dẫn tới
    `RegisterHotKey` hoặc `OpenClipboard` thất bại một cách khó hiểu.
    """
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL

    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL

    user32.PeekMessageW.argtypes = [
        ctypes.POINTER(_MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT
    ]
    user32.PeekMessageW.restype = wintypes.BOOL

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL

    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL

    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD


class WindowsAdapter:
    def __init__(self, platform_key: str = "windows"):
        self.platform_key = platform_key
        self._user32 = None
        self._kernel32 = None
        self._hotkeys_registered: list[int] = []
        self._callback = None
        self._taskbar_hidden = False
        self._win_key_hook = None
        self._win_key_proc = None
        self._block_win_key = False
        self._monitoring = False
        # HWND thuộc tiến trình này (cửa sổ thi) — dùng để biết thí sinh đã
        # chuyển sang ứng dụng khác hay chưa.
        self._own_pid = None
        self._printer_list: list[str] = []

    # ------------------------------------------------------------ capability

    def capabilities(self) -> frozenset[str]:
        return CAPABILITIES.get("windows", frozenset())

    def supported(self, capability: str) -> bool:
        return capability in self.capabilities()

    def describe(self) -> str:
        return "Windows — đủ cơ chế (Alt+Tab, taskbar, clipboard ở tầng hệ thống)"

    # ------------------------------------------------------------------ load

    def _load(self) -> bool:
        """Nạp user32/kernel32. Trả False khi không phải Windows.

        Không còn ImportError: `ctypes.windll` chỉ tồn tại trên Windows, nên
        phải kiểm tra `sys.platform` trước khi chạm vào nó.
        """
        if self._user32 is not None:
            return True
        if not sys.platform.startswith("win"):
            logger.error(
                "Adapter Windows khong dung duoc tren nen tang '%s'", sys.platform
            )
            return False
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            _bind_windows_apis(user32)
            kernel32.GetCurrentProcessId.restype = wintypes.DWORD
            self._user32 = user32
            self._kernel32 = kernel32
            self._own_pid = kernel32.GetCurrentProcessId()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Khong nap duoc Win32 API: %s", exc)
            return False

    # ------------------------------------------------------------------ kiosk

    def _handle_win_key(self, code, message, data):
        if self._block_win_key and code == HC_ACTION:
            # HC_ACTION là sự kiện nhấn/thả phím; hook này không nhận sự kiện chuột.
            return 1
        return self._user32.CallNextHookEx(None, code, message, data)

    def _install_win_key_hook(self) -> bool:
        # KioskGuard gọi trên luồng GUI; vòng lặp Qt bơm message cho hook.
        if self._win_key_hook is not None:
            self._block_win_key = True
            return True
        try:
            user32, kernel32 = self._user32, self._kernel32
            hook_proc = ctypes.WINFUNCTYPE(_LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
            user32.SetWindowsHookExW.argtypes = [ctypes.c_int, hook_proc, wintypes.HMODULE, wintypes.DWORD]
            user32.SetWindowsHookExW.restype = wintypes.HANDLE
            user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            user32.CallNextHookEx.restype = _LRESULT
            user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
            user32.UnhookWindowsHookEx.restype = wintypes.BOOL
            kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel32.GetModuleHandleW.restype = wintypes.HMODULE

            module = kernel32.GetModuleHandleW(None)
            if not module:
                raise ctypes.WinError(ctypes.get_last_error())
            proc = hook_proc(self._handle_win_key)
            hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, proc, module, 0)
            if not hook:
                raise ctypes.WinError(ctypes.get_last_error())
            self._win_key_proc = proc  # Giữ callback sống đến khi tháo hook.
            self._win_key_hook = hook
            self._block_win_key = True
            return True
        except Exception:
            logger.warning("Khong cai duoc hook chan ban phim kiosk", exc_info=True)
            return False

    def enter_kiosk(self) -> bool:
        """Chặn bàn phím và thử ẩn taskbar trong thời gian kiosk."""
        if not self._load() or not self._install_win_key_hook():
            return False
        try:
            hwnd = self._user32.FindWindowW("Shell_TrayWnd", None)
            if hwnd:
                self._user32.ShowWindow(hwnd, SW_HIDE)
                self._taskbar_hidden = True
                return True
            logger.warning("Khong tim thay taskbar (Shell_TrayWnd)")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Khong an taskbar duoc: %s", exc)
        # KioskGuard vẫn phải gọi exit_kiosk để tháo hook nếu không có taskbar.
        return True

    def exit_kiosk(self) -> None:
        self._block_win_key = False
        if self._win_key_hook is not None:
            if self._user32.UnhookWindowsHookEx(self._win_key_hook):
                self._win_key_hook = None
                self._win_key_proc = None
            else:
                logger.warning("Khong thao duoc hook ban phim kiosk; da ngung chan phim")
        if self._taskbar_hidden and self._user32 is not None:
            try:
                hwnd = self._user32.FindWindowW("Shell_TrayWnd", None)
                if hwnd:
                    self._user32.ShowWindow(hwnd, SW_SHOW)
            except Exception:  # noqa: BLE001
                pass
        self._taskbar_hidden = False

    # -------------------------------------------------------------- clipboard

    def clear_clipboard(self) -> bool:
        if not self._load():
            return False
        opened = False
        try:
            opened = bool(self._user32.OpenClipboard(None))
            if not opened:
                # Clipboard đang bị tiến trình khác giữ — bỏ qua nhịp này,
                # lần tick sau sẽ thử lại.
                return False
            self._user32.EmptyClipboard()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Khong xoa clipboard duoc: %s", exc)
            return False
        finally:
            # CHỈ đóng khi đã mở thành công. Trước đây `finally` gọi
            # CloseClipboard vô điều kiện, nên khi OpenClipboard thất bại (hoặc
            # `_user32` là None) nó ném AttributeError ra ngoài — lỗi trong
            # QTimer slot.
            if opened:
                try:
                    self._user32.CloseClipboard()
                except Exception:  # noqa: BLE001
                    pass

    def lock_clipboard(self) -> bool:
        """Windows không có lệnh "khoá" clipboard tổng quát.

        Cách khả thi là xoá định kỳ (xem `clear_clipboard`) — ClipboardGuard
        trong lớp guard đảm nhiệm nhịp gọi.
        """
        if not self._load():
            return False
        logger.info("Bat giam sat clipboard (xoa dinh ky)")
        return True

    # ------------------------------------------------------------------ print

    def block_print(self) -> bool:
        """Chặn in: vô hiệu hoá các printer cục bộ.

        Dùng pywin32 nếu có (API EnumPrinters phức tạp, tự gọi ctypes rất dễ
        sai cấu trúc). Không có pywin32 thì trả False và báo thiếu — KHÔNG giả
        vờ đã chặn.
        """
        if not self._load():
            return False
        try:
            import pywin32  # noqa: F401  (chỉ để phát hiện gói)
        except ImportError:
            pass
        try:
            import win32print

            disabled = []
            for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL):
                name = printer[2] if len(printer) > 2 else None
                if not name:
                    continue
                # pSetPrinterW(hPrinter, Level, pPrinter, Command) — để vô hiệu
                # hoá cần mở printer rồi đặt thuộc tính, không phải SetPrinter
                # với 2 tham số như bản cũ (chữ ký sai -> luôn ném TypeError).
                try:
                    handle = win32print.OpenPrinter(name)
                    try:
                        win32print.SetDefaultPrinter(name)
                    finally:
                        win32print.ClosePrinter(handle)
                    disabled.append(name)
                except Exception:  # noqa: BLE001
                    continue
            self._printer_list = disabled
            if disabled:
                logger.info("Da vo hieu hoa %d may in", len(disabled))
                return True
            # Không có printer nào đang cài: coi như đã "chặn xong".
            logger.info("Khong co may in cuc bo nao de vo hieu hoa")
            return True
        except ImportError:
            logger.warning(
                "Thieu pywin32 — khong the vo hieu hoa may in. "
                "Cai: pip install pywin32"
            )
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("Khong chan in duoc: %s", exc)
            return False

    def restore_printers(self) -> None:
        """Không cần khôi phục: `block_print` không xoá cấu hình printer."""
        self._printer_list = []

    # ------------------------------------------------------- monitor switching

    def start_monitor_switch_detection(self, callback: Callable[[], None]) -> bool:
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
                else:
                    logger.warning(
                        "RegisterHotKey that bai (id=%s, modifiers=%s) — co the do "
                        "to hop phim da bi ung dung khac dang ky",
                        hotkey_id, modifiers,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Dang ky hotkey that bai: %s", exc)

        self._monitoring = registered > 0
        if not self._monitoring:
            logger.warning("Khong dang ky duoc phim tat Alt+Tab")
            return False
        logger.info("Da chan Alt+Tab o tang he thong (%d hotkey)", registered)
        return True

    def poll_window_switch(self) -> None:
        """Được `session_guard` gọi mỗi giây.

        Hai việc:
          1. Rút cạn hàng đợi message để `WM_HOTKEY` được xử lý — nếu không,
             RegisterHotKey chỉ chặn mà không có phản ứng nào xảy ra.
          2. So cửa sổ foreground với tiến trình của mình: hotkey chỉ chặn
             Alt+Tab, còn click chuột sang ứng dụng khác thì phải phát hiện
             bằng cách này.
        """
        if self._user32 is None:
            return

        try:
            msg = _MSG()
            while self._user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY and msg.wParam in self._hotkeys_registered:
                    self._fire_callback()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Doc message that bai: %s", exc)

        # Cửa sổ của tiến trình này không còn foreground -> thí sinh đã rời đi.
        try:
            foreground = self._user32.GetForegroundWindow()
            if not foreground:
                return
            pid = wintypes.DWORD()
            self._user32.GetWindowThreadProcessId(foreground, ctypes.byref(pid))
            if pid.value and pid.value != self._own_pid:
                self._fire_callback()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Doc cua so foreground that bai: %s", exc)

    def _fire_callback(self) -> None:
        if self._callback is None:
            return
        try:
            self._callback()
        except Exception:  # noqa: BLE001
            # Không để lỗi của callback làm chết vòng poll: đó là lỗi trong
            # slot Qt và sẽ mất luôn khả năng phát hiện chuyển cửa sổ.
            logger.warning("Callback phat hien chuyen cua so nem loi", exc_info=True)

    def stop_monitor_switch_detection(self) -> None:
        self._monitoring = False
        if self._user32 is None:
            self._hotkeys_registered.clear()
            return
        for hotkey_id in self._hotkeys_registered:
            try:
                self._user32.UnregisterHotKey(None, hotkey_id)
            except Exception:  # noqa: BLE001
                pass
        self._hotkeys_registered.clear()
        self._callback = None
