"""Test capability matrix và adapter đa OS.

Điểm quan trọng nhất: trên nền tảng thiếu cơ chế, adapter phải **báo thiếu** chứ
không được bật im lặng — nếu không, GV và thí sinh đều tin là máy đang được bảo vệ
trong khi thực tế thì không.
"""

import pytest

from sebclient.osint.capability_matrix import (
    ALL_CAPABILITIES,
    CAPABILITIES,
    capabilities_for,
    describe,
    unsupported,
)
from sebclient.osint.platform import UnsupportedAdapter, create_adapter


@pytest.mark.parametrize("platform_key", ["windows", "macos", "linux"])
def test_main_platforms_have_full_capabilities(platform_key):
    caps = capabilities_for(platform_key)
    assert caps == ALL_CAPABILITIES, f"{platform_key} thiếu: {ALL_CAPABILITIES - caps}"
    assert unsupported(platform_key) == {}


def test_wayland_reports_missing_monitor_switch():
    """Wayland KHÔNG được giả vờ có phát hiện chuyển cửa sổ."""
    caps = capabilities_for("linux:wayland")
    missing = unsupported("linux:wayland")

    assert "monitor_switch" not in caps
    assert "monitor_switch" in missing
    # Và phải nêu lý do, không chỉ tên
    assert "Wayland" in missing["monitor_switch"]


def test_unsupported_reports_everything_for_unknown_platform():
    missing = unsupported("unknown-os")
    assert set(missing) == set(ALL_CAPABILITIES)
    assert all(reason for reason in missing.values())


def test_describe_mentions_missing():
    text = describe("linux:wayland")
    assert "THIEU" in text
    assert "monitor_switch" in text


@pytest.mark.parametrize(
    "platform_key,expected_class",
    [
        ("windows", "WindowsAdapter"),
        ("macos", "MacOSAdapter"),
        ("linux", "LinuxAdapter"),
        ("linux:wayland", "LinuxAdapter"),
        ("solaris", "UnsupportedAdapter"),
    ],
)
def test_create_adapter_dispatch(platform_key, expected_class):
    adapter = create_adapter(platform_key)
    assert type(adapter).__name__ == expected_class


def test_unknown_platform_adapter_never_claims_capability():
    adapter = UnsupportedAdapter("solaris")
    assert adapter.capabilities() == frozenset()
    for capability in ALL_CAPABILITIES:
        assert adapter.supported(capability) is False


def test_adapter_agrees_with_capability_matrix():
    """Adapter và bảng năng lực phải KHỚP nhau.

    Lệch nhau sẽ dẫn tới tình huống: báo cho GV là thiếu trong khi client lại
    bật, hoặc ngược lại.
    """
    for key in CAPABILITIES:
        adapter = create_adapter(key)
        assert adapter.capabilities() == capabilities_for(key), key


def test_missing_capability_is_actually_disabled():
    """Nếu bảng năng lực nói thiếu thì adapter không được báo là thực hiện được."""
    adapter = create_adapter("linux:wayland")
    assert adapter.supported("monitor_switch") is False
    assert adapter.start_monitor_switch_detection(lambda: None) is False
    assert adapter.enter_kiosk() is False   # Wayland không ẩn taskbar bằng API chung