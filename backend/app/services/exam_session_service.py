import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.models.exam_schedule import ExamSchedule
from app.models.exam_session import ExamSession
from app.models.exam import Exam
from app.models.exam_question import ExamQuestion
from app.models.student_answer import StudentAnswer
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.schemas.question_schema import QuestionPublic, QuestionOptionPublic
from app.schemas.exam_session_schema import (
    ExamTakingStateResponse, SaveAnswerRequest, SubmitExamRequest, ExamResultResponse
)
from app.dependencies.exam_time import check_exam_schedule_active
from app.services.grading_service import GradingService

class ExamSessionService:
    @staticmethod
    def join_exam(
        db: Session,
        room_code: str,
        student_id: int,
        ip_address: str = None,
        user_agent: str = None
    ) -> ExamTakingStateResponse:
        schedule = db.query(ExamSchedule).options(
            joinedload(ExamSchedule.exam).joinedload(Exam.exam_questions).joinedload(ExamQuestion.question).joinedload(Question.options)
        ).filter(ExamSchedule.room_code == room_code.upper()).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Không tìm thấy phòng thi với mã đã nhập")
            
        # Check time window
        check_exam_schedule_active(schedule)
        exam = schedule.exam

        # Check existing session
        session = db.query(ExamSession).filter(
            ExamSession.schedule_id == schedule.id,
            ExamSession.student_id == student_id
        ).first()

        now = datetime.now(timezone.utc)
        if not session:
            token = f"sess_{uuid.uuid4().hex}"
            session = ExamSession(
                schedule_id=schedule.id,
                student_id=student_id,
                session_token=token,
                started_at=now,
                status="IN_PROGRESS",
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        elif session.status == "SUBMITTED":
            raise HTTPException(status_code=400, detail="Bạn đã nộp bài thi này rồi")

        # Calculate time remaining
        started_at = session.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
            
        end_time_by_duration = started_at + timedelta(minutes=exam.duration_minutes)
        schedule_end = schedule.end_time
        if schedule_end.tzinfo is None:
            schedule_end = schedule_end.replace(tzinfo=timezone.utc)
            
        effective_end = min(end_time_by_duration, schedule_end)
        remaining_seconds = max(0, int((effective_end - now).total_seconds()))

        # If time is already over, trigger auto submit
        if remaining_seconds <= 0:
            ExamSessionService.submit_exam(db, session.session_token, SubmitExamRequest(submit_type="AUTO_TIMEOUT"))
            raise HTTPException(status_code=400, detail="Thời gian làm bài đã kết thúc")

        # Prepare Questions (Public schema - STRICTLY NO is_correct)
        exam_questions = exam.exam_questions
        if exam.is_shuffled:
            # Seed shuffle using session_token to ensure consistent question order per student session
            rng = random.Random(session.session_token)
            shuffled_eqs = list(exam_questions)
            rng.shuffle(shuffled_eqs)
        else:
            shuffled_eqs = sorted(exam_questions, key=lambda x: x.order_index)

        public_questions: List[QuestionPublic] = []
        for eq in shuffled_eqs:
            q = eq.question
            options = list(q.options)
            if exam.is_shuffled:
                rng = random.Random(f"{session.session_token}_{q.id}")
                rng.shuffle(options)
            else:
                options = sorted(options, key=lambda opt: opt.order_index)

            public_opts = [
                QuestionOptionPublic(id=opt.id, content=opt.content)
                for opt in options
            ]
            public_questions.append(QuestionPublic(
                id=q.id,
                content=q.content,
                type=q.type,
                difficulty=q.difficulty,
                subject_id=q.subject_id,
                image_url=q.image_url,
                score=float(eq.score),
                options=public_opts
            ))

        # Load saved answers
        saved_answers_records = db.query(StudentAnswer).filter(StudentAnswer.session_id == session.id).all()
        saved_dict: Dict[str, Any] = {}
        for ans in saved_answers_records:
            saved_dict[str(ans.question_id)] = {
                "selected_option_ids": ans.selected_option_ids or [],
                "fill_blank_text": ans.fill_blank_text or ""
            }

        return ExamTakingStateResponse(
            session_id=session.id,
            session_token=session.session_token,
            room_code=schedule.room_code,
            exam_title=exam.title,
            duration_minutes=exam.duration_minutes,
            started_at=session.started_at,
            server_time=now,
            remaining_seconds=remaining_seconds,
            max_violation_allowed=exam.max_violation_allowed,
            questions=public_questions,
            saved_answers=saved_dict
        )

    @staticmethod
    def save_answer(db: Session, session_token: str, data: SaveAnswerRequest) -> dict:
        session = db.query(ExamSession).filter(ExamSession.session_token == session_token).first()
        if not session or session.status == "SUBMITTED":
            raise HTTPException(status_code=400, detail="Phiên thi không hợp lệ hoặc đã kết thúc")

        ans = db.query(StudentAnswer).filter(
            StudentAnswer.session_id == session.id,
            StudentAnswer.question_id == data.question_id
        ).first()

        now = datetime.now(timezone.utc)
        if not ans:
            ans = StudentAnswer(
                session_id=session.id,
                question_id=data.question_id,
                selected_option_ids=data.selected_option_ids,
                fill_blank_text=data.fill_blank_text,
                updated_at=now
            )
            db.add(ans)
        else:
            ans.selected_option_ids = data.selected_option_ids
            ans.fill_blank_text = data.fill_blank_text
            ans.updated_at = now

        db.commit()
        return {"status": "saved", "question_id": data.question_id, "server_timestamp": now.isoformat()}

    @staticmethod
    def submit_exam(db: Session, session_token: str, data: SubmitExamRequest) -> ExamResultResponse:
        session = db.query(ExamSession).options(
            joinedload(ExamSession.student),
            joinedload(ExamSession.schedule).joinedload(ExamSchedule.exam)
        ).filter(ExamSession.session_token == session_token).first()

        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên thi")
            
        if session.status != "SUBMITTED":
            session.submitted_at = datetime.now(timezone.utc)
            session.submit_type = data.submit_type
            session.status = "SUBMITTED"
            db.commit()
            
            # Grade immediately
            GradingService.grade_session(db, session.id)
            db.refresh(session)

        exam = session.schedule.exam
        return ExamResultResponse(
            session_id=session.id,
            student_name=session.student.full_name,
            student_code=session.student.student_code,
            exam_title=exam.title,
            final_score=float(session.final_score) if session.final_score is not None else 0.0,
            total_score=float(exam.total_score),
            submit_type=session.submit_type or "MANUAL",
            status=session.status,
            started_at=session.started_at,
            submitted_at=session.submitted_at,
            risk_score=session.risk_score,
            tab_switch_count=session.tab_switch_count,
            fullscreen_exit_count=session.fullscreen_exit_count
        )
