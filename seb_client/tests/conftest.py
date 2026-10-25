"""Thiết lập chung cho test SEB Client.

Bắt buộc chạy với `QT_QPA_PLATFORM=offscreen` khi không có màn hình. WebEngine
cần display thật để *render*, nhưng test ở đây chỉ kiểm tra logic nên offscreen
là đủ và giúp test chạy được trên CI.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Không cho client đọc .env thật khi test — tránh test bị ảnh hưởng bởi cấu hình
# của máy đang chạy.
os.environ["SEB_HEADLESS"] = "true"

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))