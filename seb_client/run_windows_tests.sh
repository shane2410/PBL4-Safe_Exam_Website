#!/usr/bin/env bash
# Chạy test WindowsAdapter bằng Win32 THẬT dưới Wine.
#
# Vì sao cần: các cơ chế mạnh nhất (RegisterHotKey, clipboard, taskbar) chỉ
# tồn tại trên Windows. Test bằng stub chỉ chứng minh logic điều phối; script
# này chứng minh lời gọi Win32 thật sự chạy được.
#
# Yêu cầu: wine + Python cho Windows đã cài trong prefix.
# Mặc định: "C:\Program Files\Python311\python.exe" (đổi qua WIN_PYTHON nếu khác).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIN_PYTHON="${WIN_PYTHON:-C:\\Program Files\\Python311\\python.exe}"

# Đổi đường dẫn POSIX -> đường dẫn Wine (Z:\...).
win_path() { winepath -w "$1"; }

PROJECT_WIN="$(win_path "$HERE")"
TEST_FILE="${PROJECT_WIN}\\tests\\test_windows_adapter.py"

if wine "$WIN_PYTHON" -c "import pytest" >/dev/null 2>&1; then
  echo "== WindowsAdapter: Win32 thật qua Wine =="
  wine "$WIN_PYTHON" -c "
import sys
sys.path.insert(0, r'$PROJECT_WIN')
import pytest
sys.exit(pytest.main([r'$TEST_FILE', '-q', '-p', 'no:cacheprovider']))
"
else
  echo "Python Windows trong Wine chưa có pytest. Chạy:"
  echo "  wine \"$WIN_PYTHON\" -m pip install pytest"
  exit 1
fi
