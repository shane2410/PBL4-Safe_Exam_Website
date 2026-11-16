#!/bin/bash
set -e

echo "=========================================="
echo "🚀 Secure Online Exam System - Backend Entrypoint"
echo "=========================================="

# 1. Chờ CSDL MySQL sẵn sàng chấp nhận kết nối
echo "⏳ Đang kiểm tra kết nối tới cơ sở dữ liệu..."
python - << 'EOF'
import os
import sys
import time
from urllib.parse import urlparse

db_url = os.environ.get("DATABASE_URL", "")
if not db_url:
    print("⚠️ CẢNH BÁO: Biến DATABASE_URL chưa được thiết lập!")
    sys.exit(0)

# Ẩn mật khẩu khi hiển thị log
try:
    parsed = urlparse(db_url)
    safe_host = parsed.hostname or "unknown"
    safe_port = parsed.port or 3306
    safe_db = parsed.path.lstrip('/')
    print(f"📡 Đang kết nối tới CSDL tại {safe_host}:{safe_port}/{safe_db}...")
except Exception:
    print("📡 Đang kết nối tới CSDL...")

from sqlalchemy import create_engine, text

max_retries = int(os.environ.get("DB_WAIT_RETRIES", "45"))
retry_interval = int(os.environ.get("DB_WAIT_INTERVAL", "2"))

for attempt in range(1, max_retries + 1):
    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 3}, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"✅ Kết nối CSDL thành công sau {attempt} lần thử.")
        sys.exit(0)
    except Exception as exc:
        if attempt % 5 == 0 or attempt == 1:
            print(f"⏳ ({attempt}/{max_retries}) Đang chờ CSDL sẵn sàng... ({type(exc).__name__})")
        time.sleep(retry_interval)

print("❌ LỖI: Quá thời gian chờ kết nối CSDL MySQL!")
sys.exit(1)
EOF

# 2. Tự động áp dụng Alembic Migrations
echo "📦 Đang thực thi migrations CSDL (alembic upgrade head)..."
alembic upgrade head
echo "✅ Migrations CSDL hoàn tất."

# 3. Nạp dữ liệu mẫu ban đầu (nếu cờ AUTO_SEED hoặc SEED_DATA được bật)
AUTO_SEED_VAL=$(echo "${AUTO_SEED:-${SEED_DATA:-false}}" | tr '[:upper:]' '[:lower:]')
if [ "$AUTO_SEED_VAL" = "true" ] || [ "$AUTO_SEED_VAL" = "1" ] || [ "$AUTO_SEED_VAL" = "yes" ]; then
    echo "🌱 Cờ AUTO_SEED được bật. Đang nạp/kiểm tra dữ liệu mẫu ban đầu..."
    python -m seeders.seed_data || echo "⚠️ Quá trình nạp dữ liệu mẫu kết thúc với cảnh báo."
else
    echo "ℹ️ Bỏ qua bước nạp dữ liệu mẫu (AUTO_SEED không bật)."
fi

# 4. Khởi động tiến trình chính
echo "=========================================="
if [ $# -gt 0 ]; then
    echo "▶️ Chạy lệnh tùy biến: $@"
    exec "$@"
else
    echo "▶️ Khởi động Uvicorn server: 0.0.0.0:8000 (--workers 1)"
    # LƯU Ý BẢO MẬT: Bắt buộc duy trì --workers 1 vì nonce challenge và active sockets lưu trong bộ nhớ
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
fi
