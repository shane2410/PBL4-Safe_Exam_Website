"""Kịch bản kiểm thử tải (Load Testing) với Locust cho hệ thống thi trực tuyến.

Bao gồm 2 kịch bản chính:
1. StudentExamWorkflow (SequentialTaskSet / StudentUser):
   - Đăng nhập tài khoản thí sinh (POST /api/auth/login)
   - Vào phòng thi với mã phòng (POST /api/exam-sessions/join)
   - Lặp lưu từng câu trả lời (POST /api/exam-sessions/save-answer)
   - Nộp bài thi (POST /api/exam-sessions/submit)

2. TeacherMonitorWorkflow (TaskSet / TeacherMonitorUser):
   - Đăng nhập tài khoản giám thị / giáo viên (POST /api/auth/login)
   - Lấy thống kê ca thi (GET /api/reports/schedules/{id}/statistics)
   - Xem nhật ký vi phạm của thí sinh (GET /api/reports/sessions/{session_id}/violations)

Cách chạy:
    locust -f backend/tests/locustfile.py --host http://localhost:8000
"""

import os
import random
import logging
from locust import HttpUser, SequentialTaskSet, TaskSet, task, between

logger = logging.getLogger(__name__)

# Cấu hình mặc định (có thể ghi đè qua biến môi trường)
DEFAULT_ROOM_CODE = os.getenv("LOCUST_ROOM_CODE", "PBL4-EXAM-01")
DEFAULT_STUDENT_USER = os.getenv("LOCUST_STUDENT_USER", "student1")
DEFAULT_STUDENT_PASS = os.getenv("LOCUST_STUDENT_PASS", "student123")
DEFAULT_TEACHER_USER = os.getenv("LOCUST_TEACHER_USER", "teacher1")
DEFAULT_TEACHER_PASS = os.getenv("LOCUST_TEACHER_PASS", "teacher123")
DEFAULT_SCHEDULE_ID = int(os.getenv("LOCUST_SCHEDULE_ID", "1"))


class StudentExamSequence(SequentialTaskSet):
    """Vòng đời làm bài thi của thí sinh: Login -> Join -> Save Answer Loop -> Submit."""

    def on_start(self):
        self.access_token = None
        self.session_token = None
        self.session_id = None
        self.questions = []
        self.headers = {}
        # Hỗ trợ phân bổ nhiều user thí sinh nếu có danh sách
        self.username = getattr(self.user, "custom_username", DEFAULT_STUDENT_USER)
        self.password = getattr(self.user, "custom_password", DEFAULT_STUDENT_PASS)

    @task
    def login(self):
        """Bước 1: Đăng nhập nhận JWT access token."""
        payload = {"username": self.username, "password": self.password}
        with self.client.post(
            "/api/auth/login",
            json=payload,
            name="/api/auth/login (Student)",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                data = res.json()
                self.access_token = data.get("access_token")
                self.headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }
                res.success()
            else:
                res.failure(f"Student login failed: {res.status_code} - {res.text}")

    @task
    def join_exam(self):
        """Bước 2: Vào phòng thi với mã phòng."""
        if not self.access_token:
            return

        payload = {
            "room_code": DEFAULT_ROOM_CODE,
            "client_type": "web",
        }
        with self.client.post(
            "/api/exam-sessions/join",
            json=payload,
            headers=self.headers,
            name="/api/exam-sessions/join",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                data = res.json()
                self.session_token = data.get("session_token")
                self.session_id = data.get("session_id")
                self.questions = data.get("questions") or []
                res.success()
            else:
                res.failure(f"Join exam failed: {res.status_code} - {res.text}")

    @task
    def save_answers_loop(self):
        """Bước 3: Vòng lặp lưu câu trả lời cho các câu hỏi trong đề."""
        if not self.session_token or not self.questions:
            return

        for q in self.questions:
            q_id = q.get("id")
            options = q.get("options") or []
            selected_ids = []
            if options:
                # Chọn ngẫu nhiên 1 phương án
                selected_ids = [random.choice(options).get("id")]

            save_payload = {
                "session_token": self.session_token,
                "question_id": q_id,
                "selected_option_ids": selected_ids,
            }
            with self.client.post(
                "/api/exam-sessions/save-answer",
                json=save_payload,
                headers=self.headers,
                name="/api/exam-sessions/save-answer",
                catch_response=True,
            ) as res:
                if res.status_code in (200, 201):
                    res.success()
                else:
                    res.failure(f"Save answer failed for q_id={q_id}: {res.status_code}")

    @task
    def submit_exam(self):
        """Bước 4: Nộp bài thi hoàn thành phiên thi."""
        if not self.session_token:
            return

        submit_payload = {
            "session_token": self.session_token,
            "submit_type": "MANUAL",
        }
        with self.client.post(
            "/api/exam-sessions/submit",
            json=submit_payload,
            headers=self.headers,
            name="/api/exam-sessions/submit",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                res.success()
                # Dừng chu kỳ làm bài của user này để không submit lặp lại
                self.interrupt()
            else:
                res.failure(f"Submit exam failed: {res.status_code} - {res.text}")


class StudentUser(HttpUser):
    """Mô phỏng thí sinh tham gia thi."""

    tasks = [StudentExamSequence]
    wait_time = between(1, 3)


class TeacherMonitorTasks(TaskSet):
    """Nhiệm vụ của giám thị: kiểm tra thống kê ca thi và giám sát nhật ký vi phạm."""

    def on_start(self):
        self.access_token = None
        self.headers = {}
        self.login()

    def login(self):
        payload = {"username": DEFAULT_TEACHER_USER, "password": DEFAULT_TEACHER_PASS}
        with self.client.post(
            "/api/auth/login",
            json=payload,
            name="/api/auth/login (Teacher)",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                self.access_token = res.json().get("access_token")
                self.headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }
                res.success()
            else:
                res.failure(f"Teacher login failed: {res.status_code} - {res.text}")

    @task(3)
    def get_schedule_statistics(self):
        """Theo dõi dashboard thống kê ca thi."""
        if not self.access_token:
            return

        with self.client.get(
            f"/api/reports/schedules/{DEFAULT_SCHEDULE_ID}/statistics",
            headers=self.headers,
            name="/api/reports/schedules/[id]/statistics",
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                res.success()
            else:
                res.failure(f"Get statistics failed: {res.status_code}")

    @task(2)
    def get_session_violations(self):
        """Kiểm tra nhật ký vi phạm của phiên thi."""
        if not self.access_token:
            return

        session_id = random.randint(1, 10)
        with self.client.get(
            f"/api/reports/sessions/{session_id}/violations",
            headers=self.headers,
            name="/api/reports/sessions/[id]/violations",
            catch_response=True,
        ) as res:
            # 200 hoặc 404/403 nếu session_id ngẫu nhiên chưa tồn tại
            if res.status_code in (200, 404, 403):
                res.success()
            else:
                res.failure(f"Get violations failed: {res.status_code}")


class TeacherMonitorUser(HttpUser):
    """Mô phỏng giáo viên / giám thị theo dõi phòng thi."""

    tasks = [TeacherMonitorTasks]
    wait_time = between(2, 5)
