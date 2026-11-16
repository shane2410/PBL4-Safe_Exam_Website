# Hướng dẫn Kiểm thử tải (Load Testing) với Locust

Tài liệu này hướng dẫn cách chạy kịch bản kiểm thử hiệu năng và tải đồng thời cho hệ thống backend FastAPI.

## 1. Cài đặt Locust

Locust đã được thêm vào `backend/requirements.txt`. Cài đặt qua pip nếu chưa có:

```bash
pip install locust
```

## 2. Kịch bản kiểm thử (`locustfile.py`)

File `locustfile.py` định nghĩa 2 đối tượng người dùng mô phỏng thực tế:

1. **StudentUser (Thí sinh):**
   - Đăng nhập tài khoản thí sinh (`POST /api/auth/login`)
   - Tham gia phòng thi với mã phòng (`POST /api/exam-sessions/join`)
   - Vòng lặp lưu đáp án từng câu hỏi (`POST /api/exam-sessions/save-answer`)
   - Nộp bài thi (`POST /api/exam-sessions/submit`)

2. **TeacherMonitorUser (Giám thị / Giáo viên):**
   - Đăng nhập tài khoản giảng viên (`POST /api/auth/login`)
   - Giám sát tiến độ và thống kê ca thi (`GET /api/reports/schedules/{id}/statistics`)
   - Truy vấn nhật ký vi phạm an toàn theo thời gian thực (`GET /api/reports/sessions/{session_id}/violations`)

## 3. Khởi chạy Load Test

Khởi động backend server trước (ví dụ: `uvicorn app.main:fastapi_app --reload --port 8000`).

Sau đó, đứng tại thư mục `backend/tests/` và chạy lệnh:

```bash
locust -f locustfile.py --host http://localhost:8000
```

Hoặc đứng tại thư mục gốc của repository:

```bash
locust -f backend/tests/locustfile.py --host http://localhost:8000
```

## 4. Giao diện Web UI & Chạy Headless

### Giao diện Web UI (Mặc định)
- Mở trình duyệt tại: `http://localhost:8089`
- Nhập số lượng người dùng mô phỏng (`Number of users`) và tốc độ tăng tải (`Spawn rate`).
- Bấm **Start swarming** để bắt đầu theo dõi RPS, thời gian phản hồi (Response time) và tỷ lệ lỗi.

### Chạy trực tiếp trên Terminal (Headless / CI mode)
```bash
locust -f backend/tests/locustfile.py --host http://localhost:8000 \
    --headless -u 50 -r 5 --run-time 1m --csv=load_test_results
```

## 5. Tuỳ chỉnh tham số môi trường

Bạn có thể truyền các biến môi trường để tuỳ biến phòng thi và tài khoản kiểm thử:

- `LOCUST_ROOM_CODE`: Mã phòng thi (mặc định: `PBL4-EXAM-01`)
- `LOCUST_STUDENT_USER`: Tài khoản thí sinh (mặc định: `student1`)
- `LOCUST_STUDENT_PASS`: Mật khẩu thí sinh (mặc định: `student123`)
- `LOCUST_TEACHER_USER`: Tài khoản giáo viên (mặc định: `teacher1`)
- `LOCUST_TEACHER_PASS`: Mật khẩu giáo viên (mặc định: `teacher123`)
- `LOCUST_SCHEDULE_ID`: ID ca thi cần giám sát (mặc định: `1`)
