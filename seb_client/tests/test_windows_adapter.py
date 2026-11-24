"""Test cho WindowsAdapter (#1) — chạy được trên Linux và trên Windows/Wine.

Bối cảnh lỗi trước bản vá:
  * `_load()` import `win32user`, module KHÔNG tồn tại trong pywin32. ImportError
    bị nuốt nên TOÀN BỘ tầng hệ điều hành Windows bị vô hiệu im lặng.
  * `SessionGuard._tick()` gọi `self._os.poll_window_switch()`, nhưng adapter
    chỉ có `pump_hotkeys` -> AttributeError mỗi giây (lộ ra ngay khi sửa xong
    import).

Chiến lược test:
  * Nhóm A (mọi nền tảng): dùng user32 giả lập để kiểm tra logic điều phối —
    đăng ký/huỷ hotkey, xử lý WM_HOTKEY, phát hiện PID lạ, nuốt lỗi callback,
    và hành vi "không hỗ trợ" trên non-Windows.
  * Nhóm B (`@pytest.mark.windows`): chạy trên Windows thật/Wine với user32
    thật — xác minh RegisterHotKey/PeekMessage/clipboard/taskbar hoạt động.

Chạy trên Linux:        cd seb_client && .venv/bin/python -m pytest tests -q
Chạy trên Wine:         wine "C:\\Program Files\\Python311\\python.exe" -m pytest tests -q -m windows
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from sebclient.osint.windows_adapter import (
    HOTKEY_ID_ALT_CTRL_TAB,
    HOTKEY_ID_ALT_TAB,
    WM_HOTKEY,
    WH_KEYBOARD_LL,
    WindowsAdapter,
)

IS_WINDOWS = sys.platform.startswith("win")

windows_only = pytest.mark.skipif(
    not IS_WINDOWS, reason="Cần Windows/Wine cho Win32 API thật"
)


# --- user32 giả lập, dùng được trên mọi nền tảng ---

class FakeUser32:
    """Bề mặt tối thiểu mà WindowsAdapter dùng, mô phỏng đủ để test logic."""

    def __init__(self, *, register_ok=True, messages=None, foreground_pid=None):
        self.register_ok = register_ok
        self.registered: list[int] = []
        self.unregistered: list[int] = []
        self._queue = list(messages or [])
        self.foreground_pid = foreground_pid
        self.foreground_hwnd = 4242 if foreground_pid is not None else None
        self.clipboard_open = True
        self.clipboard_cleared = False
        self.clipboard_closed = False
        self.taskbar_hidden = False

    def RegisterHotKey(self, hwnd, hotkey_id, modifiers, vk):
        if not self.register_ok:
            return 0
        self.registered.append(hotkey_id)
        return 1

    def UnregisterHotKey(self, hwnd, hotkey_id):
        self.unregistered.append(hotkey_id)
        return 1

    def PeekMessageW(self, msg_ref, hwnd, min_filter, max_filter, remove):
        if not self._queue:
            return 0
        message, wparam = self._queue.pop(0)
        msg_ref._obj.message = message
        msg_ref._obj.wParam = wparam
        return 1

    def GetForegroundWindow(self):
        return self.foreground_hwnd

    def GetWindowThreadProcessId(self, hwnd, ref):
        ref._obj.value = self.foreground_pid or 0
        return 1

    def OpenClipboard(self, hwnd):
        return 1 if self.clipboard_open else 0

    def EmptyClipboard(self):
        self.clipboard_cleared = True
        return 1

    def CloseClipboard(self):
        self.clipboard_closed = True
        return 1

    def FindWindowW(self, cls, name):
        return 777

    def ShowWindow(self, hwnd, cmd):
        self.taskbar_hidden = cmd == 0
        return 1


def _adapter_with(fake: FakeUser32, own_pid: int = 100) -> WindowsAdapter:
    """Tạo adapter đã 'nạp' sẵn user32 giả — bỏ qua kiểm tra sys.platform."""
    a = WindowsAdapter()
    a._user32 = fake
    a._own_pid = own_pid
    a._kernel32 = object()
    return a


# --- Nhóm A: logic, chạy mọi nền tảng ---

def test_non_windows_reports_unsupported_without_crashing():
    """Trên Linux, _load() phải trả False và KHÔNG ném ImportError."""
    if IS_WINDOWS:
        pytest.skip("chỉ có ý nghĩa trên nền tảng không phải Windows")
    a = WindowsAdapter()
    assert a._load() is False
    # Mọi thao tác phải "báo thiếu" thay vì nổ.
    assert a.enter_kiosk() is False
    assert a.clear_clipboard() is False
    assert a.start_monitor_switch_detection(lambda: None) is False
    a.poll_window_switch()  # không được ném
    a.stop_monitor_switch_detection()  # không được ném


def test_has_poll_window_switch_method():
    """SessionGuard gọi hàm này mỗi giây — thiếu là AttributeError."""
    assert callable(getattr(WindowsAdapter, "poll_window_switch", None))


def test_start_registers_both_hotkeys():
    fake = FakeUser32()
    a = _adapter_with(fake)
    assert a.start_monitor_switch_detection(lambda: None) is True
    assert fake.registered == [HOTKEY_ID_ALT_TAB, HOTKEY_ID_ALT_CTRL_TAB]
    assert a._monitoring is True


def test_start_returns_false_when_all_hotkeys_fail():
    fake = FakeUser32(register_ok=False)
    a = _adapter_with(fake)
    assert a.start_monitor_switch_detection(lambda: None) is False
    assert a._monitoring is False
    assert a._hotkeys_registered == []


def test_poll_fires_callback_on_wm_hotkey():
    fake = FakeUser32(messages=[(WM_HOTKEY, HOTKEY_ID_ALT_TAB)])
    a = _adapter_with(fake)
    a._callback = lambda: fired.append(1)
    fired: list[int] = []
    a._callback = lambda: fired.append(1)
    a._hotkeys_registered = [HOTKEY_ID_ALT_TAB]

    a.poll_window_switch()
    assert len(fired) == 1


def test_poll_ignores_wm_hotkey_of_other_id():
    fake = FakeUser32(messages=[(WM_HOTKEY, 0x9999)])
    a = _adapter_with(fake)
    fired: list[int] = []
    a._callback = lambda: fired.append(1)
    a._hotkeys_registered = [HOTKEY_ID_ALT_TAB]

    a.poll_window_switch()
    assert fired == []


def test_poll_fires_when_foreground_belongs_to_other_process():
    """Alt+Tab chỉ là một đường; click chuột sang app khác phải bị bắt."""
    fake = FakeUser32(foreground_pid=999)
    a = _adapter_with(fake, own_pid=100)
    fired: list[int] = []
    a._callback = lambda: fired.append(1)

    a.poll_window_switch()
    assert len(fired) == 1


def test_poll_does_not_fire_for_own_window():
    fake = FakeUser32(foreground_pid=100)
    a = _adapter_with(fake, own_pid=100)
    fired: list[int] = []
    a._callback = lambda: fired.append(1)

    a.poll_window_switch()
    assert fired == []


def test_poll_swallows_callback_exception():
    """Lỗi trong slot Qt không được làm chết vòng phát hiện."""
    fake = FakeUser32(foreground_pid=999)
    a = _adapter_with(fake, own_pid=100)

    def boom():
        raise RuntimeError("boom")

    a._callback = boom
    a.poll_window_switch()  # không được ném ra ngoài


def test_poll_is_noop_before_load():
    a = WindowsAdapter()
    a.poll_window_switch()  # _user32 None -> trả về, không ném


def test_stop_unregisters_everything():
    fake = FakeUser32()
    a = _adapter_with(fake)
    a.start_monitor_switch_detection(lambda: None)
    a.stop_monitor_switch_detection()

    assert fake.unregistered == [HOTKEY_ID_ALT_TAB, HOTKEY_ID_ALT_CTRL_TAB]
    assert a._hotkeys_registered == []
    assert a._monitoring is False


def test_clear_clipboard_does_not_raise_when_open_fails():
    """bản cũ gọi CloseClipboard trong finally vô điều kiện -> AttributeError."""
    fake = FakeUser32()
    fake.clipboard_open = False
    a = _adapter_with(fake)

    assert a.clear_clipboard() is False
    # Open thất bại thì KHÔNG được đóng.
    assert fake.clipboard_closed is False


def test_clear_clipboard_closes_after_success():
    fake = FakeUser32()
    a = _adapter_with(fake)
    assert a.clear_clipboard() is True
    assert fake.clipboard_cleared is True
    assert fake.clipboard_closed is True


@pytest.fixture
def kiosk_adapter(monkeypatch):
    fake = FakeUser32()
    a = _adapter_with(fake)
    monkeypatch.setattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, raising=False)
    fake.SetWindowsHookExW = Mock(return_value=123)
    fake.CallNextHookEx = Mock(return_value=42)
    fake.UnhookWindowsHookEx = Mock(return_value=True)
    a._kernel32 = SimpleNamespace(GetModuleHandleW=Mock(return_value=456))
    return a, fake


def test_enter_and_exit_kiosk_toggle_taskbar_and_hook(kiosk_adapter):
    a, fake = kiosk_adapter
    assert a.enter_kiosk() is True
    assert a.enter_kiosk() is True
    fake.SetWindowsHookExW.assert_called_once_with(WH_KEYBOARD_LL, a._win_key_proc, 456, 0)
    assert fake.taskbar_hidden is True
    a.exit_kiosk()
    a.exit_kiosk()
    fake.UnhookWindowsHookEx.assert_called_once_with(123)
    assert a._win_key_proc is None
    assert fake.taskbar_hidden is False


def test_keyboard_events_are_swallowed_only_in_kiosk(kiosk_adapter):
    a, fake = kiosk_adapter
    assert a.enter_kiosk()
    proc = a._win_key_proc
    for message in (0x0100, 0x0101, 0x0104, 0x0105):
        assert proc(0, message, 0) == 1
    fake.CallNextHookEx.assert_not_called()
    assert proc(-1, 0x0100, 0) == 42
    a.exit_kiosk()
    assert proc(0, 0x0100, 0) == 42


def test_kiosk_removes_hook_even_without_taskbar(kiosk_adapter):
    a, fake = kiosk_adapter
    fake.FindWindowW = Mock(return_value=None)
    assert a.enter_kiosk()
    a.exit_kiosk()
    fake.UnhookWindowsHookEx.assert_called_once_with(123)


def test_hook_install_failure_does_not_hide_taskbar(kiosk_adapter):
    a, fake = kiosk_adapter
    fake.SetWindowsHookExW.side_effect = OSError("hook failed")
    assert not a.enter_kiosk()
    assert not fake.taskbar_hidden
    assert a._win_key_proc is None


# --- Nhóm B: Win32 thật (Windows / Wine) ---

@windows_only
def test_real_load_and_capabilities():
    a = WindowsAdapter()
    assert a._load() is True
    assert "monitor_switch" in a.capabilities()


@windows_only
def test_real_register_and_unregister_hotkey():
    a = WindowsAdapter()
    assert a.start_monitor_switch_detection(lambda: None) is True
    assert len(a._hotkeys_registered) == 2
    a.stop_monitor_switch_detection()
    assert a._hotkeys_registered == []


@windows_only
def test_real_wm_hotkey_message_reaches_callback():
    a = WindowsAdapter()
    a._load()
    fired: list[int] = []
    assert a.start_monitor_switch_detection(lambda: fired.append(1)) is True

    user32 = ctypes.windll.user32
    user32.PostMessageW(None, WM_HOTKEY, HOTKEY_ID_ALT_TAB, 0)
    a.poll_window_switch()
    a.stop_monitor_switch_detection()

    assert len(fired) >= 1


@windows_only
def test_real_clipboard_cycle():
    a = WindowsAdapter()
    assert a._load() is True
    assert a.clear_clipboard() is True


@windows_only
def test_real_taskbar_hide_and_restore():
    a = WindowsAdapter()
    assert a._load() is True
    assert a.enter_kiosk() is True
    a.exit_kiosk()


@windows_only
def test_real_block_print_does_not_raise():
    a = WindowsAdapter()
    assert a._load() is True
    # Không quan trọng có printer hay không — chỉ cần không ném và trả bool.
    assert isinstance(a.block_print(), bool)
