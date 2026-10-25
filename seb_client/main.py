#!/usr/bin/env python3
"""Điểm khởi chạy SEB Client.

Chạy được từ bất kỳ thư mục nào:
    python seb_client/main.py
    cd seb_client && python -m sebclient

`sys.path` được chỉnh trước khi import để không phụ thuộc thư mục làm việc.
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sebclient.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())