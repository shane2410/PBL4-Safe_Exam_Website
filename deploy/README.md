# HƯỚNG DẪN TRIỂN KHAI HỆ THỐNG THI TRẮC NGHIỆM TRỰC TUYẾN AN TOÀN
## (Secure Online Exam System - Production Deployment Guide)

Tài liệu này hướng dẫn chi tiết quy trình triển khai trọn bộ hệ thống thi trực tuyến bằng **Docker**, **Nginx** và **Docker Compose**, hỗ trợ đầy đủ các tính năng bảo mật, thời gian thực qua **Socket.IO** và tích hợp ứng dụng desktop **Safe Exam Browser (SEB Client)**.

---

## 1. Kiến trúc Triển khai (Deployment Architecture)

Hệ thống được đóng gói thành mô hình 3-tier container hóa trong mạng bridge nội bộ (`exam_network`):

```
                                [ Thí sinh / Giảng viên / SEB Client ]
                                                  │
                                            HTTP (80) / HTTPS (443)
                                                  ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ MÁY CHỦ TRIỂN KHAI (DOCKER HOST)                                                        │
│                                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Container: exam_web (Nginx:Alpine + React 18 SPA)                                 │  │
│  │  - Cổng mở ngoài: 80, 443                                                        │  │
│  │  - Phục vụ Static Files cho SPA (/usr/share/nginx/html)                          │  │
│  │  - SPA Fallback routing (try_files -> /index.html)                               │  │
│  │  - Reverse Proxy /api/ -> http://backend:8000                                    │  │
│  │  - WebSocket Proxy /socket.io/ (Upgrade, Keep-alive 120s, no-buffer)             │  │
│  └───────────────────────────┬──────────────────────────────────────────────────────┘  │
│                              │ Mạng nội bộ (exam_network)                              │
│                              ▼                                                         │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Container: exam_backend (Python 3.11-slim FastAPI ASGI)                           │  │
│  │  - Non-root user: appuser                                                        │  │
│  │  - Entrypoint tự động: Chờ MySQL -> alembic upgrade head -> Auto seed data       │  │
│  │  - Uvicorn Server: 0.0.0.0:8000 với BẮT BUỘC --workers 1                         │  │
│  │  - Múi giờ hệ thống: TZ=UTC                                                      │  │
│  └───────────────────────────┬──────────────────────────────────────────────────────┘  │
│                              │                                                         │
│                              ▼                                                         │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Container: exam_db (MySQL 8.0)                                                    │  │
│  │  - Healthcheck: mysqladmin ping                                                  │  │
│  │  - Chuẩn UTF-8: utf8mb4_unicode_ci                                               │  │
│  │  - Múi giờ đồng bộ: --default-time-zone=+00:00 (UTC)                              │  │
│  │  - Persistent Volume: mysql_data                                                 │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Yêu cầu Hệ thống & Chuẩn bị Máy chủ

### 2.1. Cấu hình phần cứng tối thiểu
- **Hệ điều hành:** Linux (Ubuntu 20.04/22.04 LTS, Debian 11/12, CentOS Stream/Rocky Linux 9).
- **CPU:** Tối thiểu 2 Cores (Khuyến nghị 4 Cores cho ca thi > 200 thí sinh).
- **RAM:** Tối thiểu 2 GB RAM (Khuyến nghị 4 GB trở lên).
- **Ổ đĩa:** Trống tối thiểu 10 GB SSD.
- **Mạng:** Kết nối Internet ổn định, có IP tĩnh công khai (Static Public IP) hoặc Tên miền (Domain FQDN).

### 2.2. Mở cổng Firewall (Tường lửa)
Đảm bảo máy chủ đã mở các cổng mạng sau:
- `22/TCP`: SSH quản trị máy chủ.
- `80/TCP`: HTTP Web & Xác thực Let's Encrypt Certbot.
- `443/TCP`: HTTPS Web an toàn.

Trên Ubuntu/Debian (UFW):
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2.3. Cài đặt Docker & Docker Compose
Nếu máy chủ chưa có Docker:
```bash
# Cài đặt Docker Engine (Ubuntu)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Cấp quyền cho user hiện tại (tránh dùng root)
sudo usermod -aG docker $USER
newgrp docker

# Kiểm tra phiên bản
docker --version
docker compose version
```

---

## 3. Quy trình Triển khai Nhanh (Một Lệnh)

### Bước 1: Di chuyển vào thư mục deploy
```bash
cd /path/to/PBL4-Safe_Exam_Website/deploy
```

### Bước 2: Thiết lập cấu hình môi trường (.env)
Nếu chưa có file `.env`, bạn có thể sao chép từ file mẫu:
```bash
cp .env.example .env
```

Mở file `.env` và kiểm tra các thông số quan trọng:
```bash
nano .env
```
Các thông số bắt buộc lưu ý:
1. **`SECRET_KEY`**: Tạo chuỗi ngẫu nhiên dài (tối thiểu 32 - 64 ký tự).
   *Mẹo sinh khóa an toàn:* `openssl rand -hex 32`
2. **`MYSQL_ROOT_PASSWORD`**: Mật khẩu quản trị CSDL MySQL an toàn.
3. **`CORS_ORIGINS`**: Khai báo chính xác domain hoặc IP truy cập hệ thống.
   Ví dụ: `'["http://exam.truong.edu.vn", "https://exam.truong.edu.vn"]'`
4. **`AUTO_SEED=true`**: Trong lần chạy đầu tiên để tạo sẵn tài khoản quản trị, giảng viên và phòng thi mẫu.

> **Ghi chú tiện ích:** Nếu bạn bỏ qua bước này, script `deploy.sh` sẽ tự động phát hiện, copy `.env.example` và tự tạo `SECRET_KEY` cùng mật khẩu ngẫu nhiên cho bạn!

### Bước 3: Khởi chạy triển khai bằng `deploy.sh`
Cấp quyền thực thi và chạy script:
```bash
chmod +x deploy.sh
./deploy.sh up
```

Script sẽ tự động:
1. Kiểm tra môi trường Docker và Docker Compose.
2. Thiết lập file `.env` nếu chưa có.
3. Build container Backend và Web Frontend React (Nginx).
4. Khởi động MySQL 8.0 và chờ healthcheck đạt trạng thái `healthy`.
5. Tự động áp dụng database migrations (`alembic upgrade head`).
6. Nạp dữ liệu mẫu ban đầu (`seed_data.py`).
7. Bật reverse proxy Nginx sẵn sàng đón nhận truy cập.

---

## 4. Quản trị & Vận hành Hệ thống

Script `deploy.sh` tích hợp sẵn các lệnh vận hành phổ biến:

| Lệnh | Ý nghĩa |
|---|---|
| `./deploy.sh up` | Build và khởi động toàn bộ hệ thống |
| `./deploy.sh down` | Dừng an toàn hệ thống (không xóa dữ liệu database) |
| `./deploy.sh restart` | Khởi động lại tất cả container |
| `./deploy.sh status` | Xem trạng thái các container (Up, Healthy, Exited) |
| `./deploy.sh logs` | Xem nhật ký hoạt động thời gian thực của toàn bộ hệ thống |
| `./deploy.sh logs backend` | Xem log chi tiết của dịch vụ Backend FastAPI |
| `./deploy.sh logs web` | Xem access & error log của Nginx Reverse Proxy |
| `./deploy.sh seed` | Chạy lại seeder nạp dữ liệu mẫu |
| `./deploy.sh migrate` | Chạy thủ công cập nhật database migration |
| `./deploy.sh backup` | Sao lưu CSDL nén (.sql.gz) vào thư mục `deploy/backups/` |

---

## 5. Dữ liệu Mẫu & Tài khoản Khởi tạo Ban đầu

Sau khi chạy với `AUTO_SEED=true`, hệ thống đã có sẵn dữ liệu để kiểm thử ngay lập tức:

| Vai trò | Tên đăng nhập | Mật khẩu | Mục đích sử dụng |
|---|---|---|---|
| Quản trị viên (Admin) | `admin` | `admin123` | Quản lý người dùng, cấu hình bảo mật toàn cục |
| Giảng viên (Teacher) | `teacher1` | `teacher123` | Quản lý ngân hàng câu hỏi, tạo đề thi, phòng thi, giám sát |
| Sinh viên (Student) | `student1` | `student123` | Vào thi, làm bài, nộp bài |
| Sinh viên dự bị | `student2` | `student123` | Thí sinh thứ hai cùng phòng thi |

- **Mã phòng thi mẫu:** `PBL4-EXAM-01` (Thời lượng 45 phút, 7 câu trắc nghiệm thuộc môn Hệ điều hành & Mạng máy tính).

---

## 6. Kiểm tra Hoạt động (Healthcheck Checklist)

Trước khi tổ chức kỳ thi thật, quản trị viên cần thực hiện kiểm tra nhanh:

### 6.1. Kiểm tra REST API
Truy cập tài liệu OpenAPI trên trình duyệt hoặc qua curl:
```bash
curl -I http://localhost/api/docs
# Kết quả mong đợi: HTTP/1.1 200 OK
```

### 6.2. Kiểm tra WebSocket Upgrade
Mở Developer Tools (F12) trên trình duyệt, tab **Network** -> lọc **WS**.
Đăng nhập tài khoản và vào phòng thi:
- Phải thấy request kết nối tới `/socket.io/?...&transport=websocket`.
- Trạng thái trả về: `101 Switching Protocols`.

### 6.3. Kiểm tra SPA Routing
Trên trình duyệt, truy cập trực tiếp đường dẫn:
`http://localhost/exam/room?room=PBL4-EXAM-01`
Bấm F5 (Reload trang): Trang web phải nạp lại bình thường, **không** được xuất hiện trang lỗi 404 Not Found của Nginx.

### 6.4. Kiểm tra số lượng Worker Backend
Xác nhận backend chỉ chạy đúng 1 tiến trình:
```bash
docker exec exam_backend ps aux | grep uvicorn
```
*(Bắt buộc đúng 1 worker do cơ chế lưu nonce xác thực challenge-response in-memory).*

---

## 7. Sao lưu & Phục hồi Cơ sở dữ liệu (Backup & Restore)

### 7.1. Tự động sao lưu bằng script
Chạy lệnh:
```bash
./deploy.sh backup
```
File sao lưu sẽ được xuất vào thư mục `deploy/backups/exam_db_YYYYMMDD_HHMMSS.sql.gz`.

### 7.2. Lên lịch tự động sao lưu hàng ngày (Cronjob)
Chạy `crontab -e` và thêm dòng sau (sao lưu lúc 02:00 sáng mỗi ngày):
```cron
0 2 * * * cd /path/to/PBL4-Safe_Exam_Website/deploy && ./deploy.sh backup > /dev/null 2>&1
```

### 7.3. Phục hồi dữ liệu (Restore)
Để khôi phục database từ file backup:
```bash
# 1. Đọc mật khẩu CSDL từ .env
source .env

# 2. Giải nén và nạp vào MySQL container
gunzip < backups/exam_db_20261116_120000.sql.gz | docker exec -i exam_db mysql -u root -p"${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}"
```

---

## 8. Cấu hình HTTPS / SSL với Let's Encrypt Certbot

Khi triển khai trên môi trường Internet thực tế (Domain FQDN, ví dụ `exam.truong.edu.vn`), bắt buộc phải sử dụng SSL/TLS để:
- Mã hóa toàn bộ dữ liệu bài thi và mật khẩu.
- Cho phép SEB Client kết nối an toàn (SEB từ chối HTTP không an toàn trên internet).

### Bước 1: Trỏ DNS Domain về IP máy chủ
Đảm bảo bản ghi `A` của domain `exam.truong.edu.vn` trỏ về IP Public của VPS.

### Bước 2: Cài đặt Certbot trên máy chủ
```bash
sudo apt update
sudo apt install -y certbot
```

### Bước 3: Cấp phát chứng chỉ SSL (Chế độ Standalone)
Tạm dừng container `web` để giải phóng cổng 80:
```bash
docker stop exam_web
sudo certbot certonly --standalone -d exam.truong.edu.vn --agree-tos -m admin@truong.edu.vn
docker start exam_web
```
Chứng chỉ được tạo tại:
- Certificate: `/etc/letsencrypt/live/exam.truong.edu.vn/fullchain.pem`
- Private Key: `/etc/letsencrypt/live/exam.truong.edu.vn/privkey.pem`

### Bước 4: Mount chứng chỉ vào container Nginx
Mở file `deploy/docker-compose.yml`, cập nhật phần `volumes` của service `web`:
```yaml
  web:
    # ...
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
```

### Bước 5: Kích hoạt SSL trong `deploy/nginx.conf`
Chuyển hướng toàn bộ HTTP sang HTTPS và thêm block lắng nghe cổng 443:
```nginx
server {
    listen 80;
    server_name exam.truong.edu.vn;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name exam.truong.edu.vn;

    ssl_certificate /etc/letsencrypt/live/exam.truong.edu.vn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/exam.truong.edu.vn/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # [Toàn bộ cấu hình SPA, location /api/ và location /socket.io/ giữ nguyên]
    # ...
}
```

Khởi động lại dịch vụ web:
```bash
./deploy.sh restart
```

---

## 9. Tích hợp với Safe Exam Browser (SEB Client)

Khi phát hành file chạy cho thí sinh thi bằng SEB Client trên máy tính Windows/Linux, đảm bảo các biến cấu hình trong `seb_client/.env` khớp với máy chủ:

```ini
# seb_client/.env
SEB_BACKEND_URL=https://exam.truong.edu.vn
SEB_EXAM_URL_TEMPLATE=https://exam.truong.edu.vn/exam/room?room={room_code}&embedded=1
SEB_EXAM_ORIGIN=https://exam.truong.edu.vn
SEB_ALLOWED_ORIGINS=https://exam.truong.edu.vn
```

> **LƯU Ý QUAN TRỌNG:**
> - Tham số `embedded=1` là **BẮT BUỘC** trên URL phòng thi của SEB. Thiếu tham số này, web frontend sẽ mở thêm một WebSocket kết nối thứ hai, gây xung đột và kích hoạt cơ chế `DUPLICATE_LOGIN` buộc sinh viên nộp bài.
> - Chi tiết tham khảo tại tài liệu [`docs/deploy/TRIEN_KHAI_WEB_VA_SEB.md`](../docs/deploy/TRIEN_KHAI_WEB_VA_SEB.md).

---

## 10. Bảng Xử lý Sự cố Thường gặp (Troubleshooting)

| Triệu chứng | Nguyên nhân | Cách khắc phục |
|---|---|---|
| Backend báo lỗi `Cấu hình không an toàn cho production` và dừng lại | `ENV=production` nhưng `SECRET_KEY` đang dùng mặc định hoặc ngắn < 32 ký tự, hoặc `DATABASE_URL` dùng mật khẩu rỗng | Mở `deploy/.env` đổi `SECRET_KEY` sang chuỗi 64 ký tự và đặt mật khẩu MySQL |
| Web báo lỗi CORS khi gọi API | `CORS_ORIGINS` trong `.env` chưa có origin truy cập của trình duyệt | Thêm URL/domain vào mảng `CORS_ORIGINS` trong `.env` rồi restart backend |
| Giám thị không nhận được cảnh báo vi phạm của thí sinh | Nginx thiếu cấu hình WebSocket upgrade cho `/socket.io/` | Kiểm tra `deploy/nginx.conf` đã có proxy headers cho `Upgrade` và `Connection` |
| Thí sinh xin nonce attestation bị báo lỗi `NONCE_INVALID_OR_EXPIRED` | Backend chạy nhiều hơn 1 worker (`--workers > 1`) | Giữ nguyên `--workers 1` trong Dockerfile và compose |
| Ca thi bị báo lỗi "quá thời gian" hoặc "chưa tới giờ" | Lệch múi giờ giữa MySQL và Backend | Đảm bảo MySQL có `--default-time-zone=+00:00` và Backend có `TZ=UTC` |
