"""Thiết lập logging: ra console và file, không bao giờ vào `print()`.

File log đặt tên theo ngày và nằm trong `logs/`. Log phải ghi được đủ để GV tra
cứu sau, nhưng KHÔNG được ghi mật khẩu, token hay `session_token`.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_dir: Path, level: str = "INFO") -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"seb_client_{_today()}.log"

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Bản đóng gói không có console: `sys.stderr` là None, tạo StreamHandler
    # với nó sẽ ném lỗi ngay khi ghi log đầu tiên. Chỉ gắn console khi thật sự
    # có luồng lỗi — bản chạy phòng thi vẫn còn file log để tra cứu.
    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        root.addHandler(console)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when="midnight", backupCount=14, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Thư viện socketio/httpx nói quá nhiều ở mức DEBUG.
    for noisy in ("httpx", "httpcore", "socketio", "engineio", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return log_file


def _today() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d")