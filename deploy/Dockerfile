# ==============================================================================
# Dockerfile cho Backend FastAPI - Hệ thống Thi trắc nghiệm trực tuyến An toàn
# Base Image: Python 3.11 slim để tối ưu kích thước và bảo mật
# ==============================================================================

FROM python:3.11-slim

# Thiết lập các biến môi trường chuẩn:
# - PYTHONDONTWRITEBYTECODE: không ghi file .pyc vào ổ đĩa container
# - PYTHONUNBUFFERED: flush stdout/stderr trực tiếp để theo dõi log thời gian thực
# - TZ=UTC: Bắt buộc chuẩn hóa múi giờ toàn hệ thống theo UTC
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

WORKDIR /app

# Cài đặt các gói phụ trợ hệ thống tối thiểu cần thiết để biên dịch các C-extension
# (như cryptography, bcrypt, pymysql) và công cụ kiểm tra sức khỏe
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt dependencies Python trước để tận dụng Docker layer caching
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn ứng dụng, cấu hình Alembic và script seeder
COPY backend/app /app/app
COPY backend/alembic /app/alembic
COPY backend/seeders /app/seeders
COPY backend/alembic.ini /app/alembic.ini
COPY deploy/entrypoint-backend.sh /app/entrypoint.sh

# Tạo người dùng không đặc quyền (non-root) tăng cường bảo mật
RUN useradd -m -u 1000 appuser && \
    chmod +x /app/entrypoint.sh && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Entrypoint tự động chờ database sẵn sàng, chạy migration và optional seed data
ENTRYPOINT ["/app/entrypoint.sh"]

# LƯU Ý BẢO MẬT BẮT BUỘC: --workers 1 do cơ chế lưu nonce in-memory của challenge-response
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
