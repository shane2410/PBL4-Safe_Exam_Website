#!/usr/bin/env python3
"""Điểm khởi chạy SEB Client.

Chạy được từ bất kỳ thư mục nào:
    python seb_client/main.py
    cd seb_client && python -m sebclient

`sys.path` được chỉnh trước khi import để không phụ thuộc thư mục làm việc.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if __name__ == "__main__":
    # Frozen Windows extensions can depend on DLLs in sibling directories.
    # Register only directories inside the bundle before qasync imports Qt.
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        runtime_dir = Path(sys._MEIPASS)
        dll_handles = [
            os.add_dll_directory(str(path))
            for path in (runtime_dir, runtime_dir / "PySide6", runtime_dir / "shiboken6")
            if path.is_dir()
        ]

    from sebclient.app import main

    if sys.argv[1:] == ["--check-runtime"]:
        # The application imports WebEngine lazily when opening an exam.
        # Validate the native extension too, without starting a GUI.
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

        sys.exit(0)
    sys.exit(main())
