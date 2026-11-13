# Hướng dẫn triển khai web + SEB Client

Tài liệu này là phần còn thiếu của `docs/KIEN_TRUC_VA_NGHIEP_VU.md`: kiến trúc
đã mô tả *hệ thống chạy thế nào*, ở đây mô tả *triển khai thế nào để web tương
thích đúng với SEB Client*.

> Đọc mục 1 trước khi triển khai bất kỳ môi trường nào. Ba biến cấu hình ở đó
> phải khớp nhau, nếu lệch thì hoặc trình duyệt không gọi được API, hoặc SEB
> Client từ chối nạp trang.

---

## 1. Ba danh sách origin phải khớp nhau

Đây là lỗi cấu hình phổ biến nhất và triệu chứng rất khó đoán.

| Biến | Thuộc | Kiểm soát cái gì | Nếu thiếu |
|---|---|---|---|
| `CORS_ORIGINS` | backend `.env` | Trình duyệt có được gọi API không | Lỗi CORS/preflight ở **cả** web lẫn webview |
| `SEB_ALLOWED_ORIGINS` | client `.env` | `NavigationGuard` cho webview nạp URL nào | Client reload vô hạn rồi hiện trang trắng |
| `SEB_EXAM_URL_TEMPLATE` | client `.env` | Trang client mở đầu tiên | Không mở được phòng |

Ví dụ production (một domain duy nhất, khuyến nghị):

```ini
# backend/.env
CORS_ORIGINS=["https://exam.truong.edu.vn"]

# seb_client/.env (cạnh file chạy)
SEB_BACKEND_URL=https://exam.truong.edu.vn
SEB_EXAM_URL_TEMPLATE=https://exam.truong.edu.vn/exam/room?room={room_code}&embedded=1
SEB_EXAM_ORIGIN=https://exam.truong.edu.vn
SEB_ALLOWED_ORIGINS=https://exam.truong.edu.vn
```

Ví dụ tách API và web (hai domain):

```ini
# backend/.env
CORS_ORIGINS=["https://exam.truong.edu.vn", "https://api.truong.edu.vn"]

# seb_client/.env
SEB_BACKEND_URL=https://api.truong.edu.vn
SEB_EXAM_URL_TEMPLATE=https://exam.truong.edu.vn/exam/room?room={room_code}&embedded=1
SEB_ALLOWED_ORIGINS=https://exam.truong.edu.vn,https://api.truong.edu.vn
```

Kiểm tra nhanh trước khi phát hành:

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Origin: https://exam.truong.edu.vn" \
  -H "Access-Control-Request-Method: POST" \
  -X OPTIONS https://api.truong.edu.vn/api/auth/login
# phải là 200, không phải 400
```

---

## 2. Vì sao `embedded=1` là bắt buộc

Trang thi chạy **hai nơi**: trực tiếp trên trình duyệt (Lớp A) và bên trong
`QWebEngineView` của SEB Client (Lớp B). Cả hai đều nạp cùng một bundle React.

Khi `embedded=1`:

| Thành phần | Hành vi |
|---|---|
| `useSecurityPolicy` | Không tự mở Socket.IO — client đã giữ socket (`useSecurityPolicy.js:47`) |
| `logViolation` | Bỏ qua — client chặn ở tầng OS nên báo từ DOM sẽ đếm trùng |

Thiếu `embedded=1`, trang web mở socket thứ hai cho cùng phiên → server ghi
`DUPLICATE_LOGIN` và đá socket cũ → **buộc nộp bài**.

Nếu bạn đổi template sang hệ thống khác, giữ nguyên tham số:

```ini
SEB_EXAM_URL_TEMPLATE=https://exam.truong.edu.vn/room/{room_code}?embedded=1
```

---

## 3. Reverse proxy (nginx)

Bắt buộc phải proxy `/socket.io` với WebSocket upgrade. Thiếu hai header
`Upgrade`/`Connection` thì Socket.IO rơi về polling, chậm và dễ timeout.

```nginx
upstream exam_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name exam.truong.edu.vn;

    ssl_certificate     /etc/ssl/certs/exam.crt;
    ssl_certificate_key /etc/ssl/private/exam.key;

    # --- Frontend (Spa build tĩnh) ---
    root /var/www/exam/dist;
    index index.html;

    location / {
        # SPA: mọi route không phải file đều trả index.html.
        # Thiếu dòng này thì F5 ở /exam/room?room=X trả 404 — đúng lúc thí
        # sinh đang thi.
        try_files $uri $uri/ /index.html;
    }

    # --- API ---
    location /api/ {
        proxy_pass http://exam_backend;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # --- Socket.IO ---
    location /socket.io/ {
        proxy_pass http://exam_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host       $host;
        proxy_set_header X-Real-IP  $remote_addr;

        # Heartbeat là 10s, server timeout 30s. Proxy cắt sớm hơn 30s sẽ làm
        # phiên bị đánh dấu DISCONNECTED dù mạng tốt.
        proxy_read_timeout  120s;
        proxy_send_timeout  120s;
        proxy_buffering     off;
    }

    # File .docx khi nhập câu hỏi có thể tới 5 MB
    client_max_body_size 10m;
}
```

### Ba điều bắt buộc ở tầng backend

1. **Chạy đúng 1 worker.** Nonce attestation và `active_sockets` lưu trong RAM
   (`attestation_service.py:50`, `exam_namespace.py`). Nhiều worker → nonce không
   tìm thấy, socket của thí sinh nằm ở worker khác với giám thị.
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
   ```
2. **`ENV=production`.** Bật kiểm tra `SECRET_KEY` mặc định, `DATABASE_URL`
   root không mật khẩu, `CORS_ORIGINS` chứa `*` (`core/config.py:model_validator`).
   Sai là app **từ chối khởi động** — đúng ý đồ.
3. **UTC ở cả hai phía.** MySQL `default-time-zone='+00:00'`, container/host
   `TZ=UTC`. Lệch múi giờ làm `check_exam_schedule_active` chặn ca thi hợp lệ.

---

## 4. Thứ tự triển khai

```bash
# 1. Backend
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env      # sửa SECRET_KEY, DATABASE_URL, CORS_ORIGINS, ENV=production
.venv/bin/alembic upgrade head
.venv/bin/python -m seeders.seed_data     # chỉ lần đầu
.venv/bin/uvicorn app.main:app --workers 1 --port 8000

# 2. Frontend
cd frontend
npm ci
npm run build             # → dist/ ; nginx trỏ root vào đây

# 3. Kiểm tra trước khi phát hành (xem mục 5)
```

---

## 5. Checklist trước khi cho thí sinh thi

### Hạ tầng

- [ ] `curl -X OPTIONS` với `Origin` thật trả 200, không phải 400
- [ ] `wss://<domain>/socket.io/` kết nối được (DevTools → Network → WS)
- [ ] `F5` tại `/exam/room?room=X` không ra 404 (SPA fallback)
- [ ] Chạy `--workers 1`; log khởi động không có cảnh báo production
- [ ] `ENV=production` và `SECRET_KEY` đã đổi khỏi giá trị mặc định

### Web ↔ SEB Client

- [ ] `SEB_ALLOWED_ORIGINS` chứa **cả** origin web **và** origin API
- [ ] `SEB_EXAM_URL_TEMPLATE` có `{room_code}` và `embedded=1`
- [ ] Mở SEB Client → vào phòng → **không** thấy màn hình "Đề thi này yêu cầu
      Safe Exam Browser" (nếu thấy: header định danh chưa tới server)
- [ ] Bấm "Bắt đầu thi" → cửa sổ vào fullscreen (nếu treo: `fullScreenRequested`
      chưa được xử lý — kiểm tra phiên bản client)
- [ ] Nộp bài → thấy màn hình "Bạn đã nộp bài. Có thể đóng cửa sổ này."
- [ ] Rời tab 1 lần → dashboard giám sát nhận **đúng 1** sự kiện, không phải 2
- [ ] F5 giữa giờ thi → bộ đếm vi phạm khôi phục đúng "x/8", không về 0
- [ ] Để thi quá 6 phút → vẫn làm bài bình thường (attestation đã tự làm mới)

### Bảo mật

- [ ] TLS hợp lệ — client từ chối `http://` ngoài localhost khi phát hành thật
- [ ] `CORS_ORIGINS` không chứa `*`
- [ ] File `.seb` (nếu dùng chế độ cấu hình) không chứa mật khẩu dạng thô

---

## 6. Những điểm đã biết còn lệch (chưa vá)

Ghi lại để không ai tưởng hệ thống đã hoàn hảo:

| # | Vấn đề | Ảnh hưởng |
|---|---|---|
| 1 | Client **bỏ qua** `security_policy` server trả về, luôn bật đủ 7 guard | GV tắt `block_copy_paste` cho đề → web tôn trọng, SEB vẫn chặn |
| 2 | Guard của web vẫn chạy khi `embedded=1` (chỉ socket và `logViolation` được bỏ) | Chặn trùng ở tầng DOM; `strikes` cục bộ có thể lệch server |
| 3 | Heuristic phát hiện DevTools vô dụng trong webview (`outerWidth < innerWidth`) | Luôn trả "không mở" — nhưng client đã có `DevToolsGuard` thật |
| 4 | `X-Client-Required` được `expose_headers` nhưng không nơi nào set | Hợp đồng chết, không ảnh hưởng |
| 5 | `SebClientConfig.attestation_required` không được enforce | Bật cờ này không có tác dụng |
| 6 | `hashedQuitPassword` trong file `.seb` chỉ được đọc, chưa có hộp thoại nhập | Không dùng được mật khẩu giám thị để mở khoá thoát |

---

## 7. Chẩn đoán nhanh

| Triệu chứng | Nguyên nhân thường gặp | Kiểm tra |
|---|---|---|
| Web báo lỗi CORS | `CORS_ORIGINS` thiếu origin thật | `curl -X OPTIONS` |
| Client hiện trang trắng, log có `Chuyen trang ra ngoai danh sach` | `SEB_ALLOWED_ORIGINS` thiếu origin | log client |
| Thí sinh dùng SEB vẫn thấy PolicyGate | Request của webview thiếu header (`request_interceptor`) hoặc attestation hết hạn | server log `restricted_mode`; client log `Attest lai` |
| Bấm "Bắt đầu thi" không có gì xảy ra | `fullScreenRequested` không được accept | log client `Trang yeu cau fullscreen` |
| Dashboard không nhận vi phạm | Socket không kết nối (proxy thiếu Upgrade) | DevTools → WS |
| Nộp bài xong không thoát được | Không phát hiện `/exam/results` | log client `Web app da nop bai` |
| Phiên `DISCONNECTED` dù mạng tốt | Proxy cắt socket < 30s | `proxy_read_timeout` |
| Nhiều worker | Nonce/socket mất | đếm process uvicorn |
| Ca thi bị chặn "quá thời gian" | Lệch múi giờ | so `NOW()` MySQL với `date -u` |
