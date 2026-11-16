"""Phát hiện trình gỡ lỗi (Anti-debugger) theo hệ điều hành (Phase 2).

Chống phân tích động bằng OllyDbg, x64dbg, IDA Pro, GDB, LLDB, strace:
- Windows: IsDebuggerPresent + CheckRemoteDebuggerPresent (kernel32).
- macOS: sysctl KERN_PROC_PID kiểm tra cờ P_TRACED.
- Linux: đọc /proc/self/status tìm TracerPid > 0.

Lưu ý trung thực (docs/PLAN.md mục 2.2 - C5):
Đây là rào chắn ở cấp người dùng (user-mode). Trình gỡ lỗi cấp nhân (kernel debugger)
hoặc kỹ thuật hook API có thể lách qua. Biện pháp này nhằm tăng chi phí và ngăn các
công cụ phân tích phổ thông.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys

logger = logging.getLogger(__name__)


def check_linux_debugger() -> bool:
    """Kiểm tra debugger trên Linux bằng cách đọc /proc/self/status.

    Khi có tiến trình khác gắn vào gỡ lỗi (gdb, lldb, strace), trường TracerPid
    sẽ mang giá trị PID của trình gỡ lỗi (khác 0).
    """
    status_path = "/proc/self/status"
    if not os.path.exists(status_path):
        return False

    try:
        with open(status_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("TracerPid:"):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        tracer_pid = int(parts[1].strip())
                        if tracer_pid != 0:
                            logger.warning("Linux debugger phát hiện qua TracerPid=%d", tracer_pid)
                            return True
                    break
    except Exception as exc:  # noqa: BLE001
        logger.debug("Không thể đọc /proc/self/status: %s", exc)
    return False


def check_windows_debugger() -> bool:
    """Kiểm tra debugger trên Windows qua Win32 API."""
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        # 1. IsDebuggerPresent()
        if bool(kernel32.IsDebuggerPresent()):
            logger.warning("Windows debugger phát hiện qua IsDebuggerPresent")
            return True

        # 2. CheckRemoteDebuggerPresent()
        is_remote_present = ctypes.c_bool(False)
        current_process = kernel32.GetCurrentProcess()
        if kernel32.CheckRemoteDebuggerPresent(current_process, ctypes.byref(is_remote_present)):
            if is_remote_present.value:
                logger.warning("Windows debugger phát hiện qua CheckRemoteDebuggerPresent")
                return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Lỗi khi kiểm tra Windows debugger: %s", exc)
    return False


def check_macos_debugger() -> bool:
    """Kiểm tra debugger trên macOS qua sysctl (P_TRACED flag).

    Cờ P_TRACED (0x00000800) được kernel bật trong struct kinfo_proc khi tiến trình
    đang bị theo dõi bởi ptrace/lldb/gdb.
    """
    try:
        libc = ctypes.CDLL("libc.dylib")

        # CTL_KERN = 1, KERN_PROC = 14, KERN_PROC_PID = 1
        CTL_KERN = 1
        KERN_PROC = 14
        KERN_PROC_PID = 1
        P_TRACED = 0x00000800

        mib = (ctypes.c_int * 4)(CTL_KERN, KERN_PROC, KERN_PROC_PID, os.getpid())
        size = ctypes.c_size_t(0)

        # Lấy kích thước buffer kinfo_proc
        if libc.sysctl(mib, 4, None, ctypes.byref(size), None, 0) != 0:
            return False

        buf = ctypes.create_string_buffer(size.value)
        if libc.sysctl(mib, 4, buf, ctypes.byref(size), None, 0) != 0:
            return False

        # Trong cấu trúc kinfo_proc trên macOS 64-bit:
        # struct extern_proc (kp_proc) nằm ở đầu, p_flag là trường int ở offset 32
        if size.value >= 36:
            p_flag = ctypes.c_int.from_buffer_copy(buf.raw[32:36]).value
            if (p_flag & P_TRACED) != 0:
                logger.warning("macOS debugger phát hiện qua sysctl P_TRACED")
                return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Lỗi khi kiểm tra macOS debugger: %s", exc)
    return False


def is_debugger_present() -> bool:
    """Kiểm tra xem tiến trình hiện tại có đang bị gỡ lỗi không theo từng OS."""
    platform = sys.platform
    if platform.startswith("linux"):
        return check_linux_debugger()
    if platform == "win32":
        return check_windows_debugger()
    if platform == "darwin":
        return check_macos_debugger()
    return False


def enforce_anti_debug() -> None:
    """Kiểm tra và thoát tiến trình ngay lập tức nếu phát hiện debugger.

    Được gọi ngay tại thời điểm khởi động ứng dụng (startup) trước khi load UI/mạng.
    """
    if is_debugger_present():
        msg = "Phát hiện trình gỡ lỗi (debugger/tracer) đang gắn vào tiến trình SEB Client!"
        logger.critical(msg)
        raise SystemExit(f"CRITICAL: {msg}")
