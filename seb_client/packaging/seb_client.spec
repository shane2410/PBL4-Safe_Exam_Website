# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller cho SEB Client.

Dùng chung cho cả Windows và Linux: các import đặc thù nền tảng được khai báo
trong `hiddenimports` và chỉ có hiệu lực khi module tồn tại ở môi trường build.

Vì sao `onedir` chứ không `onefile`: QtWebEngine kéo theo hàng trăm MB DLL/thư
viện và một tiến trình con (QtWebEngineProcess). Chế độ `onefile` phải giải nén
toàn bộ mỗi lần khởi động, làm chậm đáng kể và dễ hỏng khi thư mục tạm bị chặn
chính sách — không phù hợp phòng thi. `onedir` khởi động nhanh và giữ nguyên
`QtWebEngineProcess` cạnh file chạy.
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

hiddenimports = [
    # qasync là cầu nối asyncio <-> Qt, PyInstaller không thấy import động
    # bên trong nó. Nó chọn backend theo nền tảng (_unix / _windows).
    "qasync",
    "qasync._unix",
    "qasync._windows",
    # python-socketio chọn driver async lúc chạy, không phải lúc import tĩnh.
    "engineio.async_drivers.asyncio",
    "engineio.async_drivers._websocket_ws",
    "engineio.async_drivers.threading",
    "socketio.async_client",
    "socketio.async_manager",
    "socketio.client",
    # PySide6 & shiboken6: đầy đủ module Qt được SEB Client sử dụng
    "shiboken6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtNetwork",
    "PySide6.QtPrintSupport",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSvg",
    # Thư viện hỗ trợ
    "packaging",
    "packaging.version",
]

if sys.platform == "win32":
    hiddenimports += ["win32crypt", "win32print", "win32api", "win32con"]
elif sys.platform.startswith("linux"):
    hiddenimports += ["secretstorage", "jeepney"]
elif sys.platform == "darwin":
    hiddenimports += ["objc", "Foundation", "AppKit", "Quartz"]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "pytest", "unittest", "pydoc", "doctest", "tests",
        # PyInstaller từ chối build khi thấy >1 Qt binding. Máy build (đặc biệt
        # là Python trong Wine) có thể đã cài sẵn PyQt6 cho việc khác — loại
        # tường minh để build không phụ thuộc tình trạng máy.
        "PyQt6", "PyQt5", "PySide2",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SEB-Client",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SEB-Client",
)
