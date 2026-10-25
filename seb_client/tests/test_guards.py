"""Test các guard của SEB Client.

Các test này chính là bản lưu lại của những phép thử trước đây chỉ chạy tay —
mục tiêu là mọi sửa đổi sau này không thể phá guard mà không ai nhận ra.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from sebclient.constants import (  # noqa: E402
    VIOLATION_COPY_PASTE_ATTEMPT,
    VIOLATION_DEVTOOLS_DETECTED,
    VIOLATION_RIGHT_CLICK_ATTEMPT,
    VIOLATION_TAB_SWITCH,
)
from sebclient.guards.base import BaseGuard  # noqa: E402
from sebclient.guards.keyboard_guard import KeyboardGuard  # noqa: E402
from sebclient.guards.navigation_guard import NavigationGuard  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def reported():
    return []


class _DummyWindow:
    """Guard chỉ cần `web_view` khi install; phần lớn test gọi hàm trực tiếp."""

    def __init__(self, view=None):
        self.web_view = view

    def reload_exam(self):
        pass


# ---------------------------------------------------------------- navigation


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://localhost:5173/exam/room?room=A1", True),
        ("http://localhost:5173", True),
        ("http://LOCALHOST:5173/x", True),
        ("http://127.0.0.1:8000/docs", True),
        ("about:blank", True),
        # Những cái PHẢI bị chặn
        ("http://localhost:5173.evil.com/x", False),
        ("http://localhost:5174/x", False),
        ("https://localhost:5173/x", False),
        ("http://evil.com", False),
        ("http://169.254.169.254/latest/", False),
        ("file:///etc/passwd", False),
    ],
)
def test_navigation_guard_origin(url, expected):
    allowed = ["http://localhost:5173", "http://127.0.0.1:8000"]
    guard = NavigationGuard(_DummyWindow(), allowed)
    assert guard.is_allowed(QUrl(url)) is expected


def test_navigation_guard_reload_is_not_recursive(qapp, reported):
    """URL rỗng lúc khởi tạo không được kích hoạt reload.

    Hồi quy: `loadStarted` phát ra trước khi `view.url()` có giá trị; nếu coi
    URL rỗng là trái phép thì reload → load() → phát lại → treo tiến trình.
    """
    window = _DummyWindow()
    window.reload_exam = lambda: reported.append("reload")

    guard = NavigationGuard(window, ["http://localhost:5173"])
    guard._on_url_changed(QUrl(""))          # URL rỗng
    guard._on_url_changed(QUrl("about:blank"))
    assert reported == []

    guard._on_url_changed(QUrl("http://evil.com/"))
    assert reported == ["reload"]


# ------------------------------------------------------------------ keyboard


class _Key:
    def __init__(self, key, modifiers):
        self._key = key
        self._modifiers = modifiers

    def key(self):
        return self._key

    def modifiers(self):
        return self._modifiers

    def type(self):
        return 6  # QEvent.KeyPress


def test_keyboard_guard_blocks_and_reports(qapp, reported):
    """Phím bị chặn thì PHẢI báo đúng loại vi phạm, không gộp chung."""
    from PySide6.QtCore import Qt

    window = _DummyWindow()
    guard = KeyboardGuard(window, reporter=lambda t, d: reported.append(t))

    C, S, A = Qt.ControlModifier, Qt.ShiftModifier, Qt.AltModifier
    cases = [
        (Qt.Key_F12, Qt.NoModifier, True, VIOLATION_DEVTOOLS_DETECTED),
        (Qt.Key_I, C | S, True, VIOLATION_DEVTOOLS_DETECTED),
        (Qt.Key_C, C, True, VIOLATION_COPY_PASTE_ATTEMPT),
        (Qt.Key_V, C, True, VIOLATION_COPY_PASTE_ATTEMPT),
        (Qt.Key_P, C, True, VIOLATION_COPY_PASTE_ATTEMPT),
        (Qt.Key_S, C, True, VIOLATION_COPY_PASTE_ATTEMPT),
        # Alt+Tab là TAB_SWITCH — nếu để mặc định của guard sẽ bị ghi nhầm
        # thành COPY_PASTE và làm sai số liệu dashboard.
        (Qt.Key_Tab, A, True, VIOLATION_TAB_SWITCH),
        # Phím bình thường phải qua
        (Qt.Key_A, Qt.NoModifier, False, None),
        (Qt.Key_Escape, Qt.NoModifier, False, None),
        (Qt.Key_F5, Qt.NoModifier, False, None),
    ]

    for key, modifiers, expect_blocked, expect_type in cases:
        before = len(reported)
        blocked = guard.eventFilter(None, _Key(key, modifiers))
        assert blocked is expect_blocked, f"key={key} mods={modifiers}"
        if expect_blocked:
            assert len(reported) == before + 1
            assert reported[-1] == expect_type
        else:
            assert len(reported) == before


# ------------------------------------------------------------------ base


class _FakeGuard(BaseGuard):
    name = "fake"
    violation_type = VIOLATION_RIGHT_CLICK_ATTEMPT


def test_base_guard_dedupe_blocks_spam(qapp, reported):
    """Alt+Tab liên tục không được làm đầy bảng vi phạm."""
    guard = _FakeGuard(_DummyWindow(), reporter=lambda t, d: reported.append(t))

    assert guard.report() is True
    assert guard.report() is False          # trong dedupe_ms
    guard.clear_dedupe()
    assert guard.report() is True


def test_base_guard_event_type_override(qapp, reported):
    """Một guard được ghi đè loại sự kiện, nhưng dedupe tách theo từng loại."""
    guard = _FakeGuard(_DummyWindow(), reporter=lambda t, d: reported.append(t))

    guard.report(event_type=VIOLATION_DEVTOOLS_DETECTED)
    # Loại khác -> không bị dedupe của loại trước chặn
    guard.report(event_type=VIOLATION_COPY_PASTE_ATTEMPT)
    assert reported == [VIOLATION_DEVTOOLS_DETECTED, VIOLATION_COPY_PASTE_ATTEMPT]


def test_base_guard_requires_violation_type(qapp):
    class Broken(BaseGuard):
        name = "broken"

    guard = Broken(_DummyWindow(), reporter=lambda t, d: None)
    with pytest.raises(ValueError):
        guard.report()