"""Test đọc file cấu hình `.seb` và policy suy ra từ nó.

Điểm cần khoá lại: một file cấu hình do SEB Config Tool xuất ra phải mở được,
và mỗi khoá bảo mật phải ánh xạ đúng — sai một khoá nghĩa là thí sinh in được
đề hoặc mở DevTools trong khi giảng viên tưởng đã chặn.
"""

import plistlib

import pytest

from sebclient.config_file import (
    BrowserPolicy,
    ConfigFileError,
    build_config_bytes,
    is_config_file,
    load_config_file,
    parse_config,
)


def _write_seb(tmp_path, data: dict, name: str = "exam.seb"):
    path = tmp_path / name
    path.write_bytes(plistlib.dumps(data))
    return path


@pytest.fixture
def minimal_seb(tmp_path):
    return _write_seb(
        tmp_path,
        {
            "startURL": "http://localhost:5173/exam/room?room=A1",
            "allowPrint": False,
            "clipboardPolicy": 1,
            "enableRightMouse": False,
            "allowDeveloperConsole": False,
            "browserWindowAllowAddressBar": False,
            "enableAltTab": False,
            "enableEsc": False,
            "enableCtrlEsc": False,
            "enablePrintScreen": False,
            "blockPopUpWindows": True,
            "allowQuit": True,
            "hashedQuitPassword": "",
        },
    )


# ------------------------------------------------------------------ detection

@pytest.mark.parametrize(
    "name,expected",
    [
        ("a.seb", True),
        ("a.SEB", True),
        ("a.seb2", True),
        ("a.json", False),
        ("aseb", False),
        ("a.seb.txt", False),
    ],
)
def test_is_config_file(name, expected):
    assert is_config_file(name) is expected


# ------------------------------------------------------------------- parsing

def test_parse_minimal_maps_all_keys(minimal_seb):
    policy = load_config_file(minimal_seb)

    assert policy.start_url == "http://localhost:5173/exam/room?room=A1"
    assert policy.allow_print is False
    assert policy.allow_copy_paste is False
    assert policy.allow_right_mouse is False
    assert policy.allow_devtools is False
    assert policy.allow_address_bar is False
    assert policy.block_alt_tab is True
    assert policy.block_esc is True
    assert policy.block_ctrl_esc is True
    assert policy.block_print_screen is True
    assert policy.allow_quit is True
    assert policy.source_path == minimal_seb.resolve()


def test_parse_permissive_config():
    policy = parse_config(
        {
            "startURL": "http://example.edu/exam",
            "allowPrint": True,
            "clipboardPolicy": 0,
            "enableRightMouse": True,
            "allowDeveloperConsole": True,
            "enableAltTab": True,
            "enableEsc": True,
            "enableCtrlEsc": True,
            "enablePrintScreen": True,
            "blockPopUpWindows": False,
        }
    )

    assert policy.allow_print is True
    assert policy.allow_copy_paste is True
    assert policy.allow_right_mouse is True
    assert policy.allow_devtools is True
    assert policy.block_alt_tab is False
    assert policy.block_esc is False
    assert policy.block_ctrl_esc is False
    assert policy.block_print_screen is False
    assert policy.block_popups is False


@pytest.mark.parametrize("policy_value,expected", [(0, True), (1, False), (2, True)])
def test_clipboard_policy_values(policy_value, expected):
    policy = parse_config({"startURL": "http://a.b/", "clipboardPolicy": policy_value})
    assert policy.allow_copy_paste is expected


def test_unknown_clipboard_policy_is_restrictive():
    """Giá trị lạ phải coi như chặn — thiên về an toàn thay vì mở."""
    policy = parse_config({"startURL": "http://a.b/", "clipboardPolicy": 99})
    assert policy.allow_copy_paste is False


def test_int_bools_are_accepted():
    """SEB đôi khi lưu 0/1 thay vì true/false."""
    policy = parse_config(
        {"startURL": "http://a.b/", "allowPrint": 0, "enableRightMouse": 1}
    )
    assert policy.allow_print is False
    assert policy.allow_right_mouse is True


def test_missing_start_url_raises():
    with pytest.raises(ConfigFileError, match="startURL"):
        parse_config({"allowPrint": True})


def test_non_http_start_url_raises():
    with pytest.raises(ConfigFileError, match="http/https"):
        parse_config({"startURL": "file:///etc/passwd"})


def test_start_url_key_variant_is_accepted():
    """SEB có bản ghi `startUrl` (chữ l thường) — phải chấp nhận cả hai."""
    policy = parse_config({"startUrl": "http://example.edu/x"})
    assert policy.start_url == "http://example.edu/x"


# ------------------------------------------------------------------- origins

def test_origin_from_start_url_only():
    policy = parse_config({"startURL": "http://localhost:5173/exam/room"})
    assert policy.allowed_origins == ("http://localhost:5173",)


def test_origin_default_port_applied():
    policy = parse_config({"startURL": "https://exam.edu.vn/room"})
    assert policy.allowed_origins == ("https://exam.edu.vn:443",)


def test_origin_from_whitelist_filter():
    policy = parse_config(
        {
            "startURL": "http://localhost:5173/exam",
            "whitelistURLFilter": "http://127.0.0.1:8000\nhttps://api.exam.edu.vn",
        }
    )
    assert "http://127.0.0.1:8000" in policy.allowed_origins
    assert "https://api.exam.edu.vn:443" in policy.allowed_origins


def test_origin_from_url_filter_rules():
    policy = parse_config(
        {
            "startURL": "http://localhost:5173/exam",
            "URLFilterRules": [
                {"expression": "https://cdn.exam.edu.vn", "active": True},
                {"expression": "https://ignored.exam.edu.vn", "active": False},
                {"expression": ".*\\.regex\\.edu", "active": True},
            ],
        }
    )
    assert "https://cdn.exam.edu.vn:443" in policy.allowed_origins
    assert not any("ignored" in origin for origin in policy.allowed_origins)
    # Rule dạng regex thuần không được đoán thành origin.
    assert not any("regex" in origin for origin in policy.allowed_origins)


# ------------------------------------------------------------------ unsupported

def test_unsupported_lists_real_gaps_only():
    policy = parse_config(
        {
            "startURL": "http://a.b/",
            "enableURLFilter": True,
            "killExplorerShell": True,
            "browserExamKey": "abc",
        }
    )
    assert "enableURLFilter" in policy.unsupported
    assert "killExplorerShell" in policy.unsupported
    assert "browserExamKey" in policy.unsupported
    assert "createNewDesktop" not in policy.unsupported


def test_unsupported_empty_for_simple_config():
    policy = parse_config({"startURL": "http://a.b/"})
    assert policy.unsupported == {}


# ------------------------------------------------------------ quit password

def test_quit_password_blocks_quit():
    policy = parse_config(
        {
            "startURL": "http://a.b/",
            "allowQuit": False,
            "hashedQuitPassword": "deadbeef",
        }
    )
    assert policy.requires_quit_password is True


def test_quit_allowed_without_password_is_not_blocking():
    policy = parse_config({"startURL": "http://a.b/", "allowQuit": True})
    assert policy.requires_quit_password is False


# ---------------------------------------------------------------- file errors

def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigFileError, match="Không tìm thấy"):
        load_config_file(tmp_path / "nope.seb")


def test_wrong_extension_raises(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}")
    with pytest.raises(ConfigFileError, match="Không phải file cấu hình"):
        load_config_file(path)


def test_invalid_plist_raises(tmp_path):
    path = tmp_path / "broken.seb"
    path.write_text("<not plist")
    with pytest.raises(ConfigFileError, match="plist"):
        load_config_file(path)


def test_plist_that_is_not_dict_raises(tmp_path):
    path = tmp_path / "list.seb"
    path.write_bytes(plistlib.dumps(["a", "b"]))
    with pytest.raises(ConfigFileError, match="dictionary"):
        load_config_file(path)


def test_oversized_file_raises(tmp_path):
    path = tmp_path / "big.seb"
    path.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    with pytest.raises(ConfigFileError, match="quá lớn"):
        load_config_file(path)


# --------------------------------------------------------------- round trip

def test_build_config_bytes_round_trips():
    original = BrowserPolicy(
        start_url="http://localhost:5173/exam/room?room=Z9",
        allow_print=True,
        allow_copy_paste=False,
        allow_right_mouse=True,
        allow_devtools=False,
        allow_address_bar=False,
        allow_reload=False,
        block_alt_tab=True,
        block_esc=True,
        block_ctrl_esc=True,
        block_print_screen=True,
        allow_quit=False,
        hashed_quit_password="cafebabe",
    )
    restored = parse_config(plistlib.loads(build_config_bytes(original)))

    assert restored.start_url == original.start_url
    assert restored.allow_print == original.allow_print
    assert restored.allow_copy_paste == original.allow_copy_paste
    assert restored.allow_right_mouse == original.allow_right_mouse
    assert restored.allow_devtools == original.allow_devtools
    assert restored.allow_address_bar == original.allow_address_bar
    assert restored.allow_reload == original.allow_reload
    assert restored.block_alt_tab == original.block_alt_tab
    assert restored.allow_quit == original.allow_quit
    assert restored.hashed_quit_password == original.hashed_quit_password


def test_real_seb_file_shape_is_supported():
    """Cấu trúc tối thiểu đúng như file .seb do SEB thật sinh ra."""
    data = {
        "originatorVersion": "SEB_Win_2.1.1",
        "startURL": "http://wandertour.ddns.net/",
        "sebConfigPurpose": 0,
        "sebMode": 0,
        "enableJavaScript": True,
        "enableRightMouse": True,
        "clipboardPolicy": 2,
        "allowPrint": False,
        "enableAltTab": True,
        "enableEsc": True,
        "allowQuit": True,
        "hashedQuitPassword": "",
        "browserWindowAllowAddressBar": False,
        "showTaskBar": True,
        "URLFilterRules": [],
    }
    policy = parse_config(data)

    assert policy.start_url == "http://wandertour.ddns.net/"
    assert policy.allow_print is False
    assert policy.allow_copy_paste is True
    assert policy.allow_right_mouse is True
    assert policy.block_alt_tab is False
    assert "http://wandertour.ddns.net:80" in policy.allowed_origins
