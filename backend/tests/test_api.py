import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import fastapi_app
from app.core.database import SessionLocal
from app.models.exam_session import ExamSession
from app.models.exam_schedule import ExamSchedule
from app.models.exam import Exam
from app.models.question import Question
from app.models.user import User

client = TestClient(fastapi_app)

@pytest.fixture(autouse=True)
def clean_test_sessions():
    """Clean up exam sessions before each test to ensure test isolation."""
    db = SessionLocal()
    try:
        student_users = db.query(User).filter(User.username.in_(["student1", "student2"])).all()
        student_ids = [u.id for u in student_users]
        if student_ids:
            db.query(ExamSession).filter(ExamSession.student_id.in_(student_ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_auth_login_teacher():
    response = client.post("/api/auth/login", json={
        "username": "teacher1",
        "password": "teacher123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["role"]["code"] == "TEACHER"

def test_auth_login_student():
    response = client.post("/api/auth/login", json={
        "username": "student1",
        "password": "student123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["role"]["code"] == "STUDENT"

def test_auth_login_invalid():
    response = client.post("/api/auth/login", json={
        "username": "student1",
        "password": "wrongpassword"
    })
    assert response.status_code == 401

def test_student_join_exam_and_verify_no_answers_leaked():
    login_res = client.post("/api/auth/login", json={
        "username": "student1",
        "password": "student123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    join_res = client.post("/api/exam-sessions/join", json={
        "room_code": "PBL4-EXAM-01"
    }, headers=headers)
    assert join_res.status_code == 200
    data = join_res.json()
    assert "session_token" in data
    assert len(data["questions"]) > 0

    # STRICT SECURITY VERIFICATION: Ensure NO question or option contains 'is_correct'
    for q in data["questions"]:
        assert "is_correct" not in q
        for opt in q["options"]:
            assert "is_correct" not in opt, "SECURITY BREACH: is_correct leaked in student response schema!"

def test_student_save_answer_and_submit():
    login_res = client.post("/api/auth/login", json={
        "username": "student2",
        "password": "student123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    join_res = client.post("/api/exam-sessions/join", json={
        "room_code": "PBL4-EXAM-01"
    }, headers=headers)
    assert join_res.status_code == 200
    session_token = join_res.json()["session_token"]
    questions = join_res.json()["questions"]

    first_q = questions[0]
    first_opt = first_q["options"][0]
    save_res = client.post(
        f"/api/exam-sessions/save-answer?session_token={session_token}",
        json={
            "question_id": first_q["id"],
            "selected_option_ids": [first_opt["id"]]
        },
        headers=headers
    )
    assert save_res.status_code == 200

    submit_res = client.post(
        f"/api/exam-sessions/submit?session_token={session_token}",
        json={"submit_type": "MANUAL"},
        headers=headers
    )
    assert submit_res.status_code == 200
    submit_data = submit_res.json()
    assert submit_data["status"] == "SUBMITTED"
    assert submit_data["final_score"] is not None

def test_session_ownership_verification():
    # 1. Student 1 joins
    res1 = client.post("/api/auth/login", json={"username": "student1", "password": "student123"})
    token1 = res1.json()["access_token"]
    join1 = client.post("/api/exam-sessions/join", json={"room_code": "PBL4-EXAM-01"}, headers={"Authorization": f"Bearer {token1}"})
    token_sess1 = join1.json()["session_token"]
    q1_id = join1.json()["questions"][0]["id"]

    # 2. Student 2 tries to save answer or submit for Student 1's session -> must be 403 Forbidden!
    res2 = client.post("/api/auth/login", json={"username": "student2", "password": "student123"})
    token2 = res2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    save_attack = client.post(
        f"/api/exam-sessions/save-answer?session_token={token_sess1}",
        json={"question_id": q1_id, "selected_option_ids": [1]},
        headers=headers2
    )
    assert save_attack.status_code == 403, "Vulnerability: Student 2 was able to modify Student 1's answers!"

    submit_attack = client.post(
        f"/api/exam-sessions/submit?session_token={token_sess1}",
        json={"submit_type": "MANUAL"},
        headers=headers2
    )
    assert submit_attack.status_code == 403, "Vulnerability: Student 2 was able to submit Student 1's exam!"

def test_create_schedule_invalid_time():
    login_res = client.post("/api/auth/login", json={"username": "teacher1", "password": "teacher123"})
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # End time before start time -> 400 Bad Request
    now = datetime.now(timezone.utc)
    res = client.post("/api/exams/schedules", json={
        "exam_id": 1,
        "room_code": "INVALID-TIME-ROOM",
        "start_time": now.isoformat(),
        "end_time": (now - timedelta(hours=1)).isoformat(),
        "status": "SCHEDULED"
    }, headers=headers)
    assert res.status_code == 400

def test_delete_in_use_exam_and_question():
    login_res = client.post("/api/auth/login", json={"username": "teacher1", "password": "teacher123"})
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 1. Try deleting Exam 1 which has active schedule -> 400
    del_exam_res = client.delete("/api/exams/1", headers=headers)
    assert del_exam_res.status_code == 400

    # 2. Try deleting Question 1 which is in Exam 1 -> 400
    del_q_res = client.delete("/api/questions/1", headers=headers)
    assert del_q_res.status_code == 400
