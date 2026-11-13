"""Đọc file cấu hình `.seb` (plist XML) và chuyển thành `BrowserPolicy`.

Đây là mô hình của Safe Exam Browser thật: giảng viên phát hành **một file cấu
hình**, thí sinh mở file đó (double-click / "Open with"), và client khởi động
thành trình duyệt bị khoá đúng theo cấu hình ấy. Không cần đăng nhập, không cần
biết trước địa chỉ trang thi.

Vì sao dùng plist thay vì JSON riêng: file `.seb` do SEB chính thức tạo ra là
plist XML. Đọc được định dạng đó nghĩa là cấu hình do SEB Config Tool xuất ra
dùng được ngay, không phải chuyển đổi tay.

Nguyên tắc: **khoá nào không hiểu thì báo ra, không im lặng bỏ qua**. Một file
cấu hình có `enableURLFilter` mà client lờ đi sẽ tạo cảm giác an toàn giả.
"""

from __future__ import annotations

import logging
import plistlib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

SEB_EXTENSIONS = {".seb", ".seb2"}

# `clipboardPolicy` của SEB: 0 = cho phép, 1 = chỉ trong ứng dụng, 2 = cho phép
# hoàn toàn. Giá trị lạ được coi là "chặn" — thiên về an toàn.
_CLIPBOARD_ALLOWED_VALUES = {0, 2}


class ConfigFileError(Exception):
    """File cấu hình không đọc được hoặc thiếu khoá bắt buộc."""


@dataclass(frozen=True)
class BrowserPolicy:
    """Tập cơ chế khoá suy ra từ file `.seb`.

    Chỉ chứa những gì client thực hiện được. Khoá của SEB mà client chưa làm
    được nằm trong `unsupported` để hiện cho giảng viên biết.
    """

    start_url: str

    # Khoá an toàn
    allow_print: bool = False
    allow_copy_paste: bool = False
    allow_right_mouse: bool = False
    allow_devtools: bool = False
    allow_address_bar: bool = False
    allow_reload: bool = True
    block_alt_tab: bool = True
    block_esc: bool = True
    block_ctrl_esc: bool = True
    block_print_screen: bool = True
    block_popups: bool = True

    # Thoát chương trình
    allow_quit: bool = True
    hashed_quit_password: str = ""
    quit_url: str = ""

    # Lọc điều hướng: chỉ cho phép các origin này
    allowed_origins: tuple[str, ...] = ()
    blocked_url_regex: str = ""

    source_path: Path | None = None
    unsupported: dict[str, str] = field(default_factory=dict)

    @property
    def requires_quit_password(self) -> bool:
        return bool(self.hashed_quit_password) and not self.allow_quit


def is_config_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SEB_EXTENSIONS


def _norm_origin(url: str) -> str | None:
    """Chuẩn hoá URL thành `scheme://host:port`, None nếu không dùng được."""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"{parsed.scheme}://{parsed.hostname.lower()}:{port}"


def _allowed_origins_from(data: dict, start_url: str) -> tuple[str, ...]:
    """Suy ra danh sách origin được phép nạp.

    Chỉ `startURL` là không đủ: trang thi thật thường gọi API ở origin khác
    (backend). SEB giải quyết bằng `URLFilterRules` / whitelist; ta đọc cùng các
    khoá đó, và luôn thêm origin của chính `startURL`.
    """
    origins: list[str] = []

    def add(value: str | None) -> None:
        if not value:
            return
        origin = _norm_origin(value if "://" in value else f"http://{value}")
        if origin and origin not in origins:
            origins.append(origin)

    add(start_url)

    whitelist = data.get("whitelistURLFilter") or ""
    if isinstance(whitelist, str):
        for entry in whitelist.replace(";", "\n").splitlines():
            add(entry.strip())

    for rule in data.get("URLFilterRules") or []:
        if not isinstance(rule, dict):
            continue
        if rule.get("active") is False:
            continue
        expression = rule.get("expression") or ""
        # Rule dạng `.*\.truong\.edu\.vn` hoặc URL đầy đủ. Chỉ nhận khi trông
        # như URL đầy đủ — suy origin từ regex là đoán mò.
        if "://" in expression:
            add(expression)

    return tuple(origins)


def _collect_unsupported(data: dict) -> dict[str, str]:
    """Khoá bảo mật của SEB mà client chưa thực hiện được.

    Không liệt kê mọi khoá (file .seb có hơn 200 khoá), chỉ những khoá mà việc
    bỏ qua sẽ làm giảng viên hiểu sai về mức độ bảo vệ.
    """
    out: dict[str, str] = {}

    checks = {
        "enableURLFilter": "lọc URL theo regex chưa hỗ trợ; chỉ chặn theo origin",
        "URLFilterEnable": "lọc URL theo regex chưa hỗ trợ; chỉ chặn theo origin",
        "blacklistURLFilter": "danh sách đen URL chưa hỗ trợ",
        "enableChromeNotifications": "chặn thông báo hệ thống của Chromium chưa hỗ trợ",
        "killExplorerShell": "kết thúc Explorer (Windows) chưa hỗ trợ",
        "createNewDesktop": "tạo desktop riêng (Windows) chưa hỗ trợ",
        "monitorProcesses": "giám sát tiến trình đang chạy chưa hỗ trợ",
        "permittedProcesses": "danh sách tiến trình được phép chưa hỗ trợ",
        "prohibitedProcesses": "danh sách tiến trình bị cấm chưa hỗ trợ",
        "enableVirtualMachine": "phát hiện máy ảo chưa hỗ trợ",
        "enableScreenSharing": "chặn chia sẻ màn hình chưa hỗ trợ",
        "browserExamKey": "khoá Browser Exam Key (chữ ký phiên) chưa hỗ trợ",
        "sebServerURL": "chế độ SEB Server chưa hỗ trợ",
        "embeddedCertificates": "chứng chỉ nhúng chưa hỗ trợ",
        "proxySettingsPolicy": "áp proxy bắt buộc chưa hỗ trợ",
    }
    for key, reason in checks.items():
        value = data.get(key)
        if value in (None, "", False, [], {}):
            continue
        out[key] = reason
    return out


def _require_bool(data: dict, key: str, default: bool) -> bool:
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    # SEB đôi khi lưu 0/1 thay vì true/false.
    if isinstance(value, int):
        return bool(value)
    logger.warning("Khoa %s co kieu la %s, dung mac dinh %s", key, type(value).__name__, default)
    return default


def parse_config(data: dict, source_path: Path | None = None) -> BrowserPolicy:
    """Chuyển dict plist thành `BrowserPolicy`. Tách riêng để test được."""
    start_url = data.get("startURL") or data.get("startUrl") or ""
    if not isinstance(start_url, str) or not start_url.strip():
        raise ConfigFileError(
            "File cấu hình thiếu 'startURL' — không biết phải mở trang nào."
        )
    start_url = start_url.strip()

    origins = _allowed_origins_from(data, start_url)
    if not origins:
        raise ConfigFileError(
            f"'startURL' không phải URL http/https hợp lệ: {start_url!r}"
        )

    clipboard_policy = data.get("clipboardPolicy", 2)
    clipboard_allowed = (
        clipboard_policy in _CLIPBOARD_ALLOWED_VALUES
        if isinstance(clipboard_policy, int)
        else False
    )

    policy = BrowserPolicy(
        start_url=start_url,
        allow_print=_require_bool(data, "allowPrint", False),
        allow_copy_paste=clipboard_allowed,
        allow_right_mouse=_require_bool(data, "enableRightMouse", False),
        allow_devtools=_require_bool(data, "allowDeveloperConsole", False),
        allow_address_bar=_require_bool(data, "browserWindowAllowAddressBar", False),
        allow_reload=_require_bool(data, "browserWindowAllowReload", True),
        block_alt_tab=not _require_bool(data, "enableAltTab", False),
        block_esc=not _require_bool(data, "enableEsc", False),
        block_ctrl_esc=not _require_bool(data, "enableCtrlEsc", False),
        block_print_screen=not _require_bool(data, "enablePrintScreen", False),
        block_popups=_require_bool(data, "blockPopUpWindows", True),
        allow_quit=_require_bool(data, "allowQuit", True),
        hashed_quit_password=str(data.get("hashedQuitPassword") or ""),
        quit_url=str(data.get("quitURL") or ""),
        allowed_origins=origins,
        blocked_url_regex=str(data.get("blacklistURLFilter") or ""),
        source_path=source_path,
        unsupported=_collect_unsupported(data),
    )

    # `allowQuit=False` mà không có mật khẩu giám thị là cấu hình chết: thí sinh
    # không thoát được bằng bất kỳ cách nào, kể cả khi máy lỗi. Cảnh báo rõ.
    if not policy.allow_quit and not policy.hashed_quit_password:
        logger.warning(
            "Cau hinh cam thoat (allowQuit=false) nhung khong co hashedQuitPassword "
            "— nguoi dung se khong thoat duoc. Client van cho dong cua so de tranh ket."
        )

    return policy


def load_config_file(path: str | Path) -> BrowserPolicy:
    """Đọc file `.seb` từ đĩa."""
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigFileError(f"Không tìm thấy file cấu hình: {config_path}")
    if config_path.suffix.lower() not in SEB_EXTENSIONS:
        raise ConfigFileError(
            f"Không phải file cấu hình SEB ({', '.join(sorted(SEB_EXTENSIONS))}): {config_path.name}"
        )
    if config_path.stat().st_size > 2 * 1024 * 1024:
        raise ConfigFileError("File cấu hình quá lớn (>2 MB) — không phải file .seb hợp lệ.")

    try:
        with config_path.open("rb") as handle:
            data = plistlib.load(handle)
    except plistlib.InvalidFileException as exc:
        raise ConfigFileError(
            f"File cấu hình không phải plist XML hợp lệ: {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - lỗi đọc đĩa/quyền
        raise ConfigFileError(f"Không đọc được file cấu hình: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigFileError("Nội dung file cấu hình không phải một dictionary plist.")

    logger.info("Doc cau hinh: %s (%d khoa)", config_path.name, len(data))
    return parse_config(data, source_path=config_path)


def build_config_bytes(policy: BrowserPolicy) -> bytes:
    """Xuất lại một file `.seb` tối thiểu từ policy — dùng cho test và công cụ.

    Chỉ ghi những khoá client thực sự đọc, kèm `originatorVersion` để file mở
    được bằng SEB thật ở mức cơ bản.
    """
    data: dict = {
        "startURL": policy.start_url,
        "allowPrint": policy.allow_print,
        "clipboardPolicy": 2 if policy.allow_copy_paste else 1,
        "enableRightMouse": policy.allow_right_mouse,
        "allowDeveloperConsole": policy.allow_devtools,
        "browserWindowAllowAddressBar": policy.allow_address_bar,
        "browserWindowAllowReload": policy.allow_reload,
        "enableAltTab": not policy.block_alt_tab,
        "enableEsc": not policy.block_esc,
        "enableCtrlEsc": not policy.block_ctrl_esc,
        "enablePrintScreen": not policy.block_print_screen,
        "blockPopUpWindows": policy.block_popups,
        "allowQuit": policy.allow_quit,
        "hashedQuitPassword": policy.hashed_quit_password,
        "quitURL": policy.quit_url,
        "originatorVersion": "SEB_Client_1.0.0",
    }
    return plistlib.dumps(data)
