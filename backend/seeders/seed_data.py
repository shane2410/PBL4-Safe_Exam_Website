import sys
import os
from datetime import datetime, timedelta, timezone

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal, Base, engine
from app.core.security import get_password_hash
from app.models.role import Role
from app.models.user import User
from app.models.subject import Subject
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.models.exam import Exam
from app.models.exam_question import ExamQuestion
from app.models.exam_schedule import ExamSchedule

def seed():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        print("🌱 Seeding database...")

        # 1. Seed Roles
        roles_data = [
            {"code": "ADMIN", "name": "Quản trị viên"},
            {"code": "TEACHER", "name": "Giảng viên"},
            {"code": "STUDENT", "name": "Sinh viên"},
        ]
        roles_map = {}
        for r_data in roles_data:
            role = db.query(Role).filter_by(code=r_data["code"]).first()
            if not role:
                role = Role(code=r_data["code"], name=r_data["name"])
                db.add(role)
                db.flush()
            roles_map[r_data["code"]] = role
        print("✓ Seeded Roles")

        # 2. Seed Users
        users_data = [
            {
                "username": "admin",
                "password": "admin123",
                "full_name": "System Administrator",
                "email": "admin@safeexam.edu.vn",
                "role_id": roles_map["ADMIN"].id,
                "student_code": None,
            },
            {
                "username": "teacher1",
                "password": "teacher123",
                "full_name": "ThS. Nguyễn Văn A",
                "email": "teacher1@safeexam.edu.vn",
                "role_id": roles_map["TEACHER"].id,
                "student_code": None,
            },
            {
                "username": "student1",
                "password": "student123",
                "full_name": "Lê Văn An",
                "email": "student1@safeexam.edu.vn",
                "role_id": roles_map["STUDENT"].id,
                "student_code": "20T1020001",
            },
            {
                "username": "student2",
                "password": "student123",
                "full_name": "Trần Thị Bình",
                "email": "student2@safeexam.edu.vn",
                "role_id": roles_map["STUDENT"].id,
                "student_code": "20T1020002",
            },
        ]
        users_map = {}
        for u_data in users_data:
            user = db.query(User).filter_by(username=u_data["username"]).first()
            if not user:
                user = User(
                    username=u_data["username"],
                    password_hash=get_password_hash(u_data["password"]),
                    full_name=u_data["full_name"],
                    email=u_data["email"],
                    role_id=u_data["role_id"],
                    student_code=u_data["student_code"],
                    is_active=True
                )
                db.add(user)
                db.flush()
            users_map[u_data["username"]] = user
        print("✓ Seeded Users (admin/admin123, teacher1/teacher123, student1/student123)")

        # 3. Seed Subjects
        subjects_data = [
            {"code": "HDH101", "name": "Hệ điều hành"},
            {"code": "NET101", "name": "Mạng máy tính"},
            {"code": "PBL4", "name": "Đồ án Hệ điều hành & Mạng máy tính"},
        ]
        subjects_map = {}
        for s_data in subjects_data:
            subj = db.query(Subject).filter_by(code=s_data["code"]).first()
            if not subj:
                subj = Subject(code=s_data["code"], name=s_data["name"])
                db.add(subj)
                db.flush()
            subjects_map[s_data["code"]] = subj
        print("✓ Seeded Subjects")

        # 4. Seed Questions
        questions_data = [
            {
                "subject_id": subjects_map["HDH101"].id,
                "content": "Trong hệ điều hành, tiến trình (Process) ở trạng thái nào sau đây khi đang đợi một sự kiện I/O hoàn thành?",
                "type": "SINGLE_CHOICE",
                "difficulty": "EASY",
                "options": [
                    {"content": "Ready (Sẵn sàng)", "is_correct": False, "order_index": 1},
                    {"content": "Running (Đang chạy)", "is_correct": False, "order_index": 2},
                    {"content": "Waiting / Blocked (Chờ / Bị chặn)", "is_correct": True, "order_index": 3},
                    {"content": "Terminated (Kết thúc)", "is_correct": False, "order_index": 4},
                ]
            },
            {
                "subject_id": subjects_map["HDH101"].id,
                "content": "Thuật toán định thời CPU nào sau đây có thể dẫn đến hiện tượng 'đói tiến trình' (Starvation)?",
                "type": "SINGLE_CHOICE",
                "difficulty": "MEDIUM",
                "options": [
                    {"content": "Round Robin (RR)", "is_correct": False, "order_index": 1},
                    {"content": "Shortest Job First (SJF)", "is_correct": True, "order_index": 2},
                    {"content": "First-Come, First-Served (FCFS)", "is_correct": False, "order_index": 3},
                    {"content": "FIFO có hàng đợi tuần tự", "is_correct": False, "order_index": 4},
                ]
            },
            {
                "subject_id": subjects_map["HDH101"].id,
                "content": "Những điều kiện nào sau đây là BẮT BUỘC để xảy ra bế tắc (Deadlock) theo Coffman? (Chọn các câu đúng)",
                "type": "MULTI_CHOICE",
                "difficulty": "HARD",
                "options": [
                    {"content": "Mutual Exclusion (Loại trừ tương hỗ)", "is_correct": True, "order_index": 1},
                    {"content": "Hold and Wait (Giữ và chờ)", "is_correct": True, "order_index": 2},
                    {"content": "No Preemption (Không ưu tiên trưng dụng)", "is_correct": True, "order_index": 3},
                    {"content": "Circular Wait (Chờ đợi vòng tròn)", "is_correct": True, "order_index": 4},
                ]
            },
            {
                "subject_id": subjects_map["NET101"].id,
                "content": "Giao thức nào sau đây thuộc tầng Transport (Giao vận) trong mô hình OSI và cung cấp truyền dữ liệu tin cậy có kết nối?",
                "type": "SINGLE_CHOICE",
                "difficulty": "EASY",
                "options": [
                    {"content": "UDP", "is_correct": False, "order_index": 1},
                    {"content": "TCP", "is_correct": True, "order_index": 2},
                    {"content": "IP", "is_correct": False, "order_index": 3},
                    {"content": "HTTP", "is_correct": False, "order_index": 4},
                ]
            },
            {
                "subject_id": subjects_map["NET101"].id,
                "content": "Cơ chế bắt tay 3 bước (3-way handshake) của giao thức TCP sử dụng các cờ (flags) nào sau đây?",
                "type": "SINGLE_CHOICE",
                "difficulty": "MEDIUM",
                "options": [
                    {"content": "SYN, SYN-ACK, ACK", "is_correct": True, "order_index": 1},
                    {"content": "FIN, FIN-ACK, ACK", "is_correct": False, "order_index": 2},
                    {"content": "RST, SYN, ACK", "is_correct": False, "order_index": 3},
                    {"content": "PSH, URG, ACK", "is_correct": False, "order_index": 4},
                ]
            },
            {
                "subject_id": subjects_map["NET101"].id,
                "content": "Cổng mặc định (Default Port) của giao thức HTTPS là bao nhiêu?",
                "type": "SINGLE_CHOICE",
                "difficulty": "EASY",
                "options": [
                    {"content": "80", "is_correct": False, "order_index": 1},
                    {"content": "443", "is_correct": True, "order_index": 2},
                    {"content": "8080", "is_correct": False, "order_index": 3},
                    {"content": "22", "is_correct": False, "order_index": 4},
                ]
            },
            {
                "subject_id": subjects_map["PBL4"].id,
                "content": "Vì sao các trình duyệt web hiện đại KHÔNG cho phép JavaScript chặn hoàn toàn tổ hợp phím Alt+Tab?",
                "type": "SINGLE_CHOICE",
                "difficulty": "MEDIUM",
                "options": [
                    {"content": "Do JavaScript là ngôn ngữ đơn luồng", "is_correct": False, "order_index": 1},
                    {"content": "Do phím Alt+Tab được xử lý trực tiếp bởi Hệ điều hành trước khi gửi sự kiện tới Sandbox của trình duyệt", "is_correct": True, "order_index": 2},
                    {"content": "Do giao thức WebSocket không hỗ trợ truyền phím tắt", "is_correct": False, "order_index": 3},
                    {"content": "Do cơ chế CORS ngăn chặn sự kiện bàn phím", "is_correct": False, "order_index": 4},
                ]
            }
        ]

        created_questions = []
        for q_data in questions_data:
            existing_q = db.query(Question).filter_by(content=q_data["content"]).first()
            if not existing_q:
                q = Question(
                    subject_id=q_data["subject_id"],
                    content=q_data["content"],
                    type=q_data["type"],
                    difficulty=q_data["difficulty"],
                    created_by=users_map["teacher1"].id,
                )
                db.add(q)
                db.flush()
                for opt in q_data["options"]:
                    db.add(QuestionOption(
                        question_id=q.id,
                        content=opt["content"],
                        is_correct=opt["is_correct"],
                        order_index=opt["order_index"]
                    ))
                created_questions.append(q)
            else:
                created_questions.append(existing_q)
        print(f"✓ Seeded {len(created_questions)} Questions with Options")

        # 5. Seed Exam
        exam_title = "Kiểm tra Giữa kỳ - Hệ điều hành & Mạng máy tính"
        exam = db.query(Exam).filter_by(title=exam_title).first()
        if not exam:
            exam = Exam(
                title=exam_title,
                subject_id=subjects_map["PBL4"].id,
                duration_minutes=45,
                total_score=10.00,
                is_shuffled=True,
                max_violation_allowed=5,
                created_by=users_map["teacher1"].id
            )
            db.add(exam)
            db.flush()

            # Add questions to exam
            score_per_q = round(10.0 / len(created_questions), 2)
            for idx, q in enumerate(created_questions, start=1):
                db.add(ExamQuestion(
                    exam_id=exam.id,
                    question_id=q.id,
                    score=score_per_q,
                    order_index=idx
                ))
            db.flush()
        print("✓ Seeded Exam & Exam Questions")

        # 6. Seed Exam Schedule
        room_code = "PBL4-EXAM-01"
        schedule = db.query(ExamSchedule).filter_by(room_code=room_code).first()
        now = datetime.now(timezone.utc)
        if not schedule:
            schedule = ExamSchedule(
                exam_id=exam.id,
                room_code=room_code,
                start_time=now - timedelta(minutes=15),
                end_time=now + timedelta(hours=3),
                supervised_by=users_map["teacher1"].id,
                status="ONGOING"
            )
            db.add(schedule)
            db.flush()
        print(f"✓ Seeded Exam Schedule with Room Code: {room_code}")

        db.commit()
        print("🎉 Database seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()
