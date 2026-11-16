# HƯỚNG DẪN ĐÓNG GÓI BACKEND BẰNG DOCKER
## Hệ thống Thi trắc nghiệm trực tuyến An toàn (Secure Online Exam System)

> **Lưu ý quan trọng:** Tài liệu này cung cấp hướng dẫn văn bản và mã mẫu (template). **Không tạo trực tiếp file `Dockerfile` hay `docker-compose.yml` vào kho lưu trữ (repository)** để đảm bảo tuân thủ cấu hình phát triển cục bộ của dự án. Khi triển khai trên máy chủ thật, quản trị viên có thể tạo các file này trực tiếp tại thư mục triển khai của server.

---

## 1. Giới thiệu

Backend của hệ thống được xây dựng trên nền tảng **FastAPI**, sử dụng cơ sở dữ liệu **MySQL**, giao tiếp thời gian thực qua **Socket.IO** và yêu cầu thời gian chuẩn xác theo chuẩn **UTC**.

Việc đóng gói backend thành Docker image mang lại nhiều lợi ích:
- Đồng nhất môi trường thực thi (Python 3.11+, các thư viện C-extension như `cryptography`, `bcrypt`).
- Dễ dàng triển khai cùng CSDL MySQL trên các máy chủ đám mây hoặc VPS.
- Độc lập với môi trường hệ điều hành máy chủ chủ quản.

---

## 2. File `Dockerfile` mẫu cho Backend

Tạo file có tên `Dockerfile` trong thư mục `backend/` trên máy chủ triển khai:

```dockerfile
# Sử dụng Python 3.11 bản rút gọn (slim) để tối ưu kích thước image
FROM python:3.11-slim

# Thiết lập các biến môi trường chuẩn cho Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Cài đặt các gói phụ trợ hệ thống cần thiết để biên dịch thư viện C (cryptography, pymysql)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Sao chép và cài đặt các thư viện Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn ứng dụng, cấu hình Alembic và script seeder
COPY app /app/app
COPY alembic /app/alembic
COPY seeders /app/seeders
COPY alembic.ini /app/

# Tạo người dùng không đặc quyền (non-root) để tăng cường bảo mật
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Mở cổng 8000
EXPOSE 8000

# Khởi chạy ứng dụng bằng Uvicorn
# LƯU Ý BẢO MẬT: Bắt buộc giữ --workers 1 do cơ chế lưu nonce in-memory của challenge-response
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

---

## 3. File `docker-compose.yml` mẫu

Để chạy cả Backend và MySQL trong một mạng nội bộ cô lập, tạo file `docker-compose.yml` tại thư mục gốc triển khai:

```yaml
version: '3.8'

services:
  # CSDL MySQL
  db:
    image: mysql:8.0
    container_name: exam_db
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: secure_db_password_123
      MYSQL_DATABASE: secure_exam_db
      MYSQL_CHARSET: utf8mb4
      MYSQL_COLLATION: utf8mb4_unicode_ci
      TZ: UTC
    command: >
      --default-time-zone=+00:00
      --character-set-server=utf8mb4
      --collation-server=utf8mb4_unicode_ci
    ports:
      - "127.0.0.1:3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - exam_network
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Backend FastAPI
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: exam_backend
    restart: always
    depends_on:
      db:
        condition: service_healthy
    environment:
      # Chuỗi kết nối trỏ tới service 'db' trong mạng Docker
      DATABASE_URL: mysql+pymysql://root:secure_db_password_123@db:3306/secure_exam_db?charset=utf8mb4
      SECRET_KEY: thay_bang_chuoi_ngau_nhien_dai_it_nhat_64_ky_tu_truoc_khi_chay_that
      ACCESS_TOKEN_EXPIRE_MINUTES: 120
      CORS_ORIGINS: '["https://exam.truong.edu.vn", "http://localhost:5173"]'
    ports:
      - "8000:8000"
    networks:
      - exam_network

volumes:
  mysql_data:
    driver: local

networks:
  exam_network:
    driver: bridge
```

---

## 4. Các bước xây dựng và vận hành (Build & Run)

### 4.1. Khởi động các container

```bash
# Khởi động dịch vụ ở chế độ chạy ngầm (detached mode)
docker compose up -d --build

# Kiểm tra trạng thái các container
docker compose ps
```

### 4.2. Chạy Migration tạo bảng CSDL

Sau khi CSDL đã sẵn sàng, thực thi Alembic migration trực tiếp bên trong container `backend`:

```bash
docker compose exec backend alembic upgrade head
```

### 4.3. Nạp dữ liệu mẫu ban đầu (Seeding Data)

```bash
docker compose exec backend python -m seeders.seed_data
```

Lệnh này sẽ tạo các tài khoản mẫu (`admin`, `teacher1`, `student1`) và ca thi mẫu `PBL4-EXAM-01`.

### 4.4. Theo dõi nhật ký hoạt động (Logs)

```bash
# Xem log thời gian thực của backend
docker compose logs -f backend

# Xem log của MySQL
docker compose logs -f db
```

### 4.5. Dừng và gỡ bỏ hệ thống

```bash
# Dừng container (dữ liệu MySQL vẫn lưu trong volume mysql_data)
docker compose down

# Dừng và xóa cả volume dữ liệu (CẨN TRỌNG: Mất toàn bộ dữ liệu CSDL)
docker compose down -v
```

---

## 5. Những lưu ý kỹ thuật bắt buộc khi triển khai Docker

1. **Ràng buộc tiến trình đơn (`--workers 1`):**
   - Cơ chế phát sinh nonce một lần (TTL 30s) trong xác thực challenge-response (`attestation_service.py`) được lưu trong RAM của tiến trình FastAPI.
   - Nếu chạy nhiều worker (`--workers > 1`), thí sinh gửi yêu cầu xin nonce tới worker A nhưng gửi yêu cầu xác thực (`/api/auth/client-attest`) tới worker B thì quá trình xác thực sẽ báo lỗi `NONCE_INVALID_OR_EXPIRED`.
   - Nếu muốn scale nhiều worker trong tương lai, cần cấu hình tầng lưu trữ nonce phân tán bằng Redis.

2. **Đồng bộ múi giờ UTC:**
   - MySQL bắt buộc phải khởi động với cờ `--default-time-zone=+00:00` và container backend phải có `TZ=UTC`.
   - Mọi tính toán thời gian bắt đầu, kết thúc ca thi và kiểm tra hạn chót nộp bài (`deadline_sweeper`) đều căn cứ theo UTC.

3. **Cấu hình Reverse Proxy & WebSocket:**
   - Khi đứng sau Nginx hoặc Traefik, bắt buộc phải cấu hình chuyển tiếp header `Upgrade` và `Connection` cho đường dẫn `/socket.io/`.
   - Xem chi tiết cấu hình Nginx mẫu tại [`docs/deploy/TRIEN_KHAI_WEB_VA_SEB.md`](TRIEN_KHAI_WEB_VA_SEB.md).

4. **Bảo mật khóa bí mật (`SECRET_KEY`):**
   - Tuyệt đối không lưu giá trị mặc định của `SECRET_KEY` trong file cấu hình công khai.
   - Sử dụng Docker Secrets hoặc file `.env` được bảo vệ bằng quyền truy cập tệp (`chmod 600 .env`) trên server.
