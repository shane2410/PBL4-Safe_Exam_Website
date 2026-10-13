# Hệ thống Thi trắc nghiệm trực tuyến An toàn (Secure Online Exam System)

Đồ án PBL — nền tảng thi trắc nghiệm trực tuyến có cơ chế khoá an toàn và giám sát
thời gian thực, tham khảo mô hình nghiệp vụ của Safe Exam Browser (SEB).

> **Đọc trước khi trình bày:** [`docs/BAOCAO_LIMITATION.md`](docs/BAOCAO_LIMITATION.md) —
> mục giới hạn kỹ thuật. Đây là tài liệu **bắt buộc** theo đề cương.

---

## 1. Tính năng chính

### Cho thí sinh
- Vào phòng thi bằng mã phòng, làm bài trên trình duyệt, tự lưu đáp án, nộp bài.
- **7 cơ chế khoá an toàn** ở tầng trình duyệt: toàn màn hình, chặn copy/paste,
  chặn DevTools, phát hiện DevTools, giám sát chuyển tab, khoá điều hướng, chặn in.
- Cảnh báo đếm ngược khi rời khỏi phòng thi, yêu cầu quay lại trong thời gian quy định.
- Tự động lưu và khôi phục đáp án khi kết nối lại.

### Cho giảng viên
- Ngân hàng câu hỏi: thêm/sửa/xoá từng câu, **hoặc nhập hàng loạt từ file .docx**
  (hỗ trợ cả bảng Word lẫn văn bản phân tách).
- Tạo đề thi, gắn câu hỏi và đặt điểm từng câu.
- Tạo ca thi, sinh mã phòng.
- **Dashboard giám sát thời gian thực**: theo dõi thí sinh, cảnh báo vi phạm,
  cưỡng chế thu bài.
- Báo cáo kết quả, xuất Excel/PDF, tra cứu nhật ký vi phạm từng thí sinh.

### Cho quản trị viên
- Bật/tắt **"Chỉ cho phép Safe Exam Browser"** ở cấp hệ thống và cấp từng đề.
- Cấu hình bộ cơ chế khoá an toàn mặc định và cấu hình SEB Client.
- Quản lý người dùng (thêm/sửa/xoá, khoá tài khoản, đặt lại mật khẩu).
- Nhật ký thao tác quản trị.

---

## 2. Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Backend | Python 3.11+ · FastAPI · SQLAlchemy 2.0 · Alembic |
| CSDL | MySQL Community (XAMPP) |
| Realtime | python-socketio (Socket.IO) |
| Xác thực | JWT (PyJWT) + bcrypt |
| Frontend | React 18 + Vite + TailwindCSS + Zustand + React Router |
| Báo cáo | openpyxl (Excel) · reportlab (PDF) |
| Nhập câu hỏi | python-docx |
| Test | pytest (backend) |

Tất cả thư viện đều **miễn phí / mã nguồn mở**.

---

## 3. Yêu cầu môi trường

- Python 3.11 trở lên
- Node.js 18 trở lên
- MySQL Community — khuyến nghị dùng XAMPP

---

## 4. Cài đặt & chạy

### 4.1. Khởi tạo CSDL

```bash
# Tạo database (nếu chưa có)
mysql -uroot -e "CREATE DATABASE secure_exam_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

> **Lưu ý múi giờ:** backend lưu mọi mốc thời gian theo **UTC**. Nên đặt MySQL dùng UTC
> để khớp, tránh lệch khi xem trực tiếp trong database:
> Thêm vào `my.ini` → `[mysqld]`:
> ```ini
> default-time-zone = '+00:00'
> ```

### 4.2. Backend

```bash
cd backend

# Tạo môi trường ảo và cài thư viện
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Sao chép cấu hình mẫu rồi chỉnh lại
cp .env.example .env
#   → BẮT BUỘC đổi SECRET_KEY thành chuỗi ngẫu nhiên trước khi dùng thật

# Tạo bảng + dữ liệu mẫu
alembic upgrade head
python -m seeders.seed_data

# Chạy server
uvicorn app.main:app --reload --port 8000
```

- API docs (Swagger): <http://localhost:8000/docs>
- **Chỉ chạy 1 tiến trình** (`--workers 1`): cơ chế nonce của challenge-response đang
  lưu trong bộ nhớ, nhiều worker sẽ làm xác thực thất bại.

### 4.3. Nhập câu hỏi từ file Word

Trong **Ngân hàng câu hỏi** → nút **Nhập từ Word** → **Tải file .docx mẫu** về điền.

Hệ thống đọc theo **2 định dạng**, tự nhận diện:

**Dạng 1 — Bảng Word** (khuyến nghị). Dòng tiêu đề bắt buộc: `Câu hỏi` và `Đáp án`.

| Câu hỏi | A | B | C | D | Đáp án |
|---|---|---|---|---|---|
| Tiến trình nào chờ I/O? | Ready | Running | Waiting | Terminated | C |
| Chọn các điều kiện gây bế tắc | Loại trừ | Giữ và chờ | Không cướp | Chờ vòng | A,B,C,D |

Cột `Độ khó` và `Loại` là tuỳ chọn. Không có dòng tiêu đề thì hệ thống coi
cột đầu là câu hỏi, các cột giữa là lựa chọn, cột cuối là đáp án.

**Dạng 2 — Văn bản phân tách**

```
Câu 1: Tiến trình nào chờ I/O?
A. Ready
B. Running
C. Waiting
Đáp án: C
```

**Cách viết đáp án** — chấp nhận nhiều kiểu: `C` · `A,C` · `AC` · `A C` · `1,3` · `a) c)`

**Loại câu hỏi được tự suy ra**: 1 đáp án đúng → chọn một; từ 2 đáp án đúng → chọn nhiều.

**Quy trình luôn gồm 2 bước** (xem trước → xác nhận) để tránh tạo ra hàng loạt câu
hỏi sai định dạng. Câu lỗi được bỏ qua kèm số dòng, không làm hỏng phần còn lại.
Câu trùng nội dung với ngân hàng sẽ tự động bỏ qua.

### 4.4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Mở <http://localhost:5173>. Dev server đã cấu hình proxy `/api` và `/socket.io`
về backend ở port 8000.

---

## 5. Tài khoản mẫu

| Vai trò | Tài khoản | Mật khẩu |
|---|---|---|
| Quản trị | `admin` | `admin123` |
| Giảng viên | `teacher1` | `teacher123` |
| Thí sinh | `student1` | `student123` |
| Thí sinh | `student2` | `student123` |

Mã phòng thi mẫu: **`PBL4-EXAM-01`**

---

## 6. Chạy thử nhanh

1. Đăng nhập `admin/admin123` → **Cấu hình hệ thống** → bật *"Yêu cầu Safe Exam Browser"*.
2. Đăng nhập `teacher1/teacher123` → **Đề thi** → chọn đề → bật cờ *"Yêu cầu Safe Exam
   Browser Client"*.
3. Đăng nhập `student1/student123` → **Vào phòng thi** → nhập `PBL4-EXAM-01`.
   → Hệ thống hiện màn hình yêu cầu dùng SEB Client. Chọn *"Thi bằng trình duyệt với
   chế độ hạn chế"* để vào phòng và quan sát chế độ hạn chế có ghi log phục tra.
4. Mở tab khác với `teacher1` → **Lịch thi** → nút *Giám sát* để xem dashboard
   thời gian thực, chuyển tab trong tab thí sinh để thấy sự kiện hiện lên.

> **Chạy lại seed sau vài ngày:** script sẽ tự lùi khung giờ ca thi về hiện tại nếu
> ca đã hết hạn.

---

## 7. Cấu trúc thư mục

```
├── backend/
│   ├── app/
│   │   ├── api/routers/     # FastAPI routers (chỉ điều phối request)
│   │   ├── core/            # Config, security, database
│   │   ├── dependencies/    # get_current_user, require_role, client_identity
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic DTO
│   │   ├── services/        # TOÀN BỘ business logic
│   │   ├── sockets/         # Socket.IO handlers
│   │   └── main.py
│   ├── alembic/versions/    # Database migrations
│   ├── seeders/             # Script tạo dữ liệu mẫu
│   ├── tests/               # pytest
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── common/      # Button, Card, Input, Toggle, Modal, Alert, Badge, Icon, ErrorBoundary
│       │   └── layout/      # Layout (sidebar), ProtectedRoute
│       ├── pages/
│       │   ├── admin/       # Tổng quan, Người dùng, Cấu hình, Nhật ký
│       │   ├── teacher/     # Tổng quan, Câu hỏi, Đề thi, Lịch thi, Báo cáo
│       │   ├── exam/        # Phòng thi + PolicyGate + 8 hook khoá an toàn
│       │   └── monitor/     # Dashboard giám sát thời gian thực
│       ├── services/        # apiClient, socketClient, policyService, teacherService
│       └── store/           # Zustand
└── docs/
    ├── PLAN.md              # Kế hoạch triển khai chi tiết
    ├── BAOCAO_LIMITATION.md # Mục giới hạn kỹ thuật (BẮT BUỘC trình bày)
    └── SRS_He_thong_thi_truc_tuyen_v2.docx
```

---

## 8. Kiểm thử

```bash
# Backend — 75 test, không cần MySQL (dùng SQLite in-memory)
cd backend && .venv/bin/python -m pytest tests/ --ignore=tests/test_api.py -v

# Frontend — lint và build
cd frontend && npm run lint && npm run build
```

---

## 9. Tài liệu tham khảo

| Tài liệu | Nội dung |
|---|---|
| [`docs/BAOCAO_LIMITATION.md`](docs/BAOCAO_LIMITATION.md) | **Giới hạn kỹ thuật — bắt buộc trình bày** |
| [`docs/PLAN.md`](docs/PLAN.md) | Kế hoạch triển khai, kiến trúc, mô hình đe doạ |
| `skills.md` | Quy tắc bắt buộc cho dự án (kiến trúc, đặc tên, UI) |
| `design.md` | Design system tham khảo lịch sử (giao diện hiện tại dùng token trong `tailwind.config.js`) |
| `SRS_He_thong_thi_truc_tuyen_v2.docx` | Đặc tả yêu cầu (phiên bản 2) |

---

## 10. Cơ chế bảo mật chính

### Đồng hồ chuẩn do server giữ
Mọi tính toán thời gian dùng thời gian UTC phía server. Sửa đồng hồ máy thí sinh
không có tác dụng — server từ chối lưu đáp án sau khi hết giờ, kể cả khi gọi API
trực tiếp bằng `curl`.

### Đáp án đúng không bao giờ tới máy thí sinh
Schema `QuestionPublic` không chứa trường `is_correct`. Chấm điểm hoàn toàn ở server.

### Xác thực client (challenge-response HMAC)
Client được server cấp nonce 1-lần, ký HMAC-SHA256, nhận token xác thực ngắn hạn.
Dùng để phân biệt SEB Client thật với trình duyệt thường — **ghi nhận bằng chứng,
không phải ngăn chặn** (xem `docs/BAOCAO_LIMITATION.md` mục 3).

### Ba mức xử lý vi phạm
| Mức | Khi nào | Hệ thống làm gì |
|---|---|---|
| 1 — Nhẹ | Lỡ tay chuyển tab ngắn | Chỉ ghi log |
| 2 — Trung bình | Lặp lại nhiều lần | Cảnh báo đếm ngược, yêu cầu quay lại |
| 3 — Nghiêm trọng | Vượt ngưỡng cấu hình | Tự động nộp bài, lưu log đầy đủ |

Mọi quyết định mức 3 đều do **server** xác nhận dựa trên log đã ghi, không phải do
client tự quyết định.
