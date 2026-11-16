"""Kiểm tra toàn vẹn và chống can thiệp cho SEB Client (Phase 2).

Bao gồm:
- Self-check: Tính SHA-256 các module cốt lõi, so sánh với BASE_HASH đã nhúng.
- Anti-debug: Phát hiện trình gỡ lỗi (Windows, macOS, Linux).
- License-check: Kiểm tra phiên bản tối thiểu min_version từ cấu hình server.
"""

from .anti_debug import (
    check_linux_debugger,
    check_macos_debugger,
    check_windows_debugger,
    enforce_anti_debug,
    is_debugger_present,
)
from .license_check import (
    enforce_min_version,
    is_version_supported,
    parse_version_safe,
    show_update_dialog,
)
from .self_check import (
    compute_file_hash,
    compute_hash,
    get_critical_files,
    verify_self_integrity,
)

__all__ = [
    "compute_file_hash",
    "compute_hash",
    "get_critical_files",
    "verify_self_integrity",
    "check_linux_debugger",
    "check_windows_debugger",
    "check_macos_debugger",
    "is_debugger_present",
    "enforce_anti_debug",
    "parse_version_safe",
    "is_version_supported",
    "show_update_dialog",
    "enforce_min_version",
]
