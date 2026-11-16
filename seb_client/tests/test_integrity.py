"""Tests cho module integrity (Self-check, Anti-debug, License-check) - Phase 2."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch
import pytest

from sebclient.integrity.anti_debug import (
    check_linux_debugger,
    check_macos_debugger,
    check_windows_debugger,
    enforce_anti_debug,
    is_debugger_present,
)
from sebclient.integrity.license_check import (
    enforce_min_version,
    is_version_supported,
    parse_version_safe,
)
from sebclient.integrity.self_check import (
    compute_file_hash,
    compute_hash,
    get_critical_files,
    verify_self_integrity,
)


# ============================================================================
# 1. Self-Check Tests
# ============================================================================

def test_compute_file_hash(tmp_path: Path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("safe_exam_integrity_test_content", encoding="utf-8")

    import hashlib
    expected = hashlib.sha256(b"safe_exam_integrity_test_content").hexdigest()

    result = compute_file_hash(test_file)
    assert result == expected
    assert len(result) == 64


def test_compute_file_hash_not_found(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.bin"
    with pytest.raises(FileNotFoundError):
        compute_file_hash(non_existent)


def test_compute_hash_deterministic():
    hash1 = compute_hash()
    hash2 = compute_hash()
    assert hash1 == hash2
    assert len(hash1) == 64
    assert all(c in "0123456789abcdef" for c in hash1)


def test_get_critical_files():
    files = get_critical_files()
    assert len(files) > 0
    # Đảm bảo các file trả về thực sự tồn tại
    for f in files:
        assert f.is_file()


def test_verify_self_integrity_dev_mode():
    # Khi expected_hash=None (dev mode), không bao giờ văng SystemExit
    current_hash = verify_self_integrity(expected_hash=None)
    assert len(current_hash) == 64


def test_verify_self_integrity_matching_hash():
    current_hash = compute_hash()
    verified_hash = verify_self_integrity(expected_hash=current_hash)
    assert verified_hash == current_hash


def test_verify_self_integrity_tampered_hash():
    fake_hash = "0" * 64
    with pytest.raises(SystemExit) as exc_info:
        verify_self_integrity(expected_hash=fake_hash)
    assert "CRITICAL" in str(exc_info.value)


# ============================================================================
# 2. Anti-Debug Tests
# ============================================================================

def test_check_linux_debugger_no_tracer():
    proc_status = "Name:\tseb_client\nState:\tS (sleeping)\nTracerPid:\t0\nUid:\t1000\n"
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=proc_status)):
        assert check_linux_debugger() is False


def test_check_linux_debugger_with_tracer():
    proc_status = "Name:\tseb_client\nState:\tt (tracing stop)\nTracerPid:\t4242\nUid:\t1000\n"
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=proc_status)):
        assert check_linux_debugger() is True


def test_check_windows_debugger_is_debugger_present():
    mock_kernel32 = MagicMock()
    mock_kernel32.IsDebuggerPresent.return_value = 1
    mock_windll = MagicMock(kernel32=mock_kernel32)

    with patch.object(ctypes, "windll", mock_windll, create=True):
        assert check_windows_debugger() is True


def test_check_windows_debugger_remote_debugger():
    mock_kernel32 = MagicMock()
    mock_kernel32.IsDebuggerPresent.return_value = 0

    def mock_check_remote(handle, pb_debugger):
        # Giả lập ghi True vào con trỏ bool
        pb_debugger._obj.value = True
        return 1

    mock_kernel32.CheckRemoteDebuggerPresent.side_effect = mock_check_remote
    mock_windll = MagicMock(kernel32=mock_kernel32)

    with patch.object(ctypes, "windll", mock_windll, create=True):
        assert check_windows_debugger() is True


def test_check_windows_debugger_clean():
    mock_kernel32 = MagicMock()
    mock_kernel32.IsDebuggerPresent.return_value = 0

    def mock_check_remote(handle, pb_debugger):
        pb_debugger._obj.value = False
        return 1

    mock_kernel32.CheckRemoteDebuggerPresent.side_effect = mock_check_remote
    mock_windll = MagicMock(kernel32=mock_kernel32)

    with patch.object(ctypes, "windll", mock_windll, create=True):
        assert check_windows_debugger() is False


def test_check_macos_debugger_traced():
    mock_libc = MagicMock()

    # sysctl lần 1: lấy size
    # sysctl lần 2: ghi buffer có cờ P_TRACED (0x00000800) tại offset 32
    def mock_sysctl(mib, mib_len, buf, size_ptr, new_val, new_val_len):
        if buf is None:
            size_ptr._obj.value = 64
            return 0
        raw_bytes = bytearray(64)
        # Ghi P_TRACED = 0x00000800 vào byte 32..35 (little endian)
        raw_bytes[32:36] = (0x00000800).to_bytes(4, byteorder="little")
        buf.raw = bytes(raw_bytes)
        return 0

    mock_libc.sysctl.side_effect = mock_sysctl

    with patch.object(ctypes, "CDLL", return_value=mock_libc):
        assert check_macos_debugger() is True


def test_check_macos_debugger_clean():
    mock_libc = MagicMock()

    def mock_sysctl(mib, mib_len, buf, size_ptr, new_val, new_val_len):
        if buf is None:
            size_ptr._obj.value = 64
            return 0
        raw_bytes = bytearray(64)
        raw_bytes[32:36] = (0).to_bytes(4, byteorder="little")
        buf.raw = bytes(raw_bytes)
        return 0

    mock_libc.sysctl.side_effect = mock_sysctl

    with patch.object(ctypes, "CDLL", return_value=mock_libc):
        assert check_macos_debugger() is False


def test_enforce_anti_debug_passes_when_clean():
    with patch("sebclient.integrity.anti_debug.is_debugger_present", return_value=False):
        # Không có lỗi nào xảy ra
        enforce_anti_debug()


def test_enforce_anti_debug_exits_when_debugged():
    with patch("sebclient.integrity.anti_debug.is_debugger_present", return_value=True):
        with pytest.raises(SystemExit) as exc_info:
            enforce_anti_debug()
        assert "CRITICAL" in str(exc_info.value)


# ============================================================================
# 3. License-Check Tests
# ============================================================================

def test_parse_version_safe():
    v1 = parse_version_safe("1.0.0")
    v2 = parse_version_safe("1.0.0-phase1")
    v3 = parse_version_safe("2.5.1+build102")
    assert v1.base_version == "1.0.0"
    assert v2.base_version == "1.0.0"
    assert v3.base_version == "2.5.1"


def test_is_version_supported():
    assert is_version_supported("1.0.0", "1.0.0") is True
    assert is_version_supported("1.0.0", "1.0.0-phase1") is True
    assert is_version_supported("1.0.0", "1.1.0") is True
    assert is_version_supported("1.0.0", "2.0.0") is True
    assert is_version_supported("1.2.0", "1.1.9") is False
    assert is_version_supported("2.0.0", "1.9.9") is False
    # Trường hợp rỗng
    assert is_version_supported("", "1.0.0") is True
    assert is_version_supported(None, "1.0.0") is True


def test_enforce_min_version_valid():
    # Đáp ứng -> không raise
    enforce_min_version("1.0.0", current_version="1.0.0", show_dialog=False)
    enforce_min_version("0.9.0", current_version="1.0.0", show_dialog=False)


def test_enforce_min_version_outdated():
    # Client cũ hơn min_version -> raise SystemExit
    with pytest.raises(SystemExit) as exc_info:
        enforce_min_version("2.0.0", current_version="1.0.0", show_dialog=False)
    assert "CRITICAL" in str(exc_info.value)
