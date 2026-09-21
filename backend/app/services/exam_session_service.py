import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from app.models.exam_schedule import ExamSchedule
from app.models.exam_session import ExamSession
from app.models.exam import Exam
from app.models.exam_question import ExamQuestion
from app.models.student_answer import StudentAnswer
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.models.user import User
from app.schemas.question_schema import QuestionPublic, QuestionOptionPublic
from app.schemas.exam_session_schema import (
    ExamTakingStateResponse, SaveAnswerRequest, SubmitExamRequest, ExamResultResponse
)
from app.dependencies.exam_time import check_exam_schedule_active
from app.services.grading_service import GradingService

logger = logging.getLogger(__name__)

class ExamSessionService:
    @staticmethod
    def join_exam(
        db: Session,
        room_code: str,
        student_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> ExamTakingStateResponse:
        schedule = db.query(ExamSchedule).options(
            joinedload(ExamSchedule.exam).joinedload(Exam.exam_questions).joinedload(ExamQuestion.question).joinedload(Question.options)
        ).filter(ExamSchedule.room_code == room_code.upper()).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Không tìm thấy phòng thi với mã đã nhập")
            
        # Check time window
        check_exam_schedule_active(schedule)
        exam = schedule.exam
        if not exam:
            logger.error("Schedule %s has no linked exam", schedule.id)
            raise HTTPException(status_code=500, detail="Đề thi liên kết với ca thi không tồn tại")

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
            try:
                db.add(session)
                db.commit()
                db.refresh(session)
            except IntegrityError:
                # Handle concurrent join race condition gracefully
                db.rollback()
                session = db.query(ExamSession).filter(
                    ExamSession.schedule_id == schedule.id,
                    ExamSession.student_id == student_id
                ).first()
                if not session:
                    logger.error("Failed to recover session for student %d in schedule %d", student_id, schedule.id)
                    raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi khởi tạo phiên thi")
        else:
            if session.status == "SUBMITTED":
                raise HTTPException(status_code=400, detail="Bạn đã nộp bài thi này rồi")
            # Update IP and user-agent on reconnect
            if ip_address or user_agent:
                if ip_address:
                    session.ip_address = ip_address
                if user_agent:
                    session.user_agent = user_agent
                try:
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.warning("Failed to update reconnect client info for session %d: %s", session.id, e)

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

        # If time is already over, trigger auto submit gracefully
        if remaining_seconds <= 0:
            try:
                ExamSessionService.submit_exam(
                    db, session.session_token,
                    SubmitExamRequest(submit_type="AUTO_TIMEOUT"),
                    current_user=None,
                    skip_auth_check=True
                )
            except Exception as e:
                logger.warning("Auto-submit on timeout failed for session %d: %s", session.id, e, exc_info=True)
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
    def save_answer(
        db: Session,
        session_token: str,
        data: SaveAnswerRequest,
        current_user: User
    ) -> dict:
        session = db.query(ExamSession).filter(ExamSession.session_token == session_token).first()
        if not session or session.status == "SUBMITTED":
            raise HTTPException(status_code=400, detail="Phiên thi không hợp lệ hoặc đã kết thúc")

        # Security check: Verify ownership
        user_role = current_user.role.code if current_user.role else "STUDENT"
        if user_role == "STUDENT" and session.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền thao tác trên phiên thi của thí sinh khác"
            )

        ans = db.query(StudentAnswer).filter(
            StudentAnswer.session_id == session.id,
            StudentAnswer.question_id == data.question_id
        ).first()

        now = datetime.now(timezone.utc)
        try:
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
        except Exception as e:
            db.rollback()
            logger.error("Error saving answer for session %d, question %d: %s", session.id, data.question_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi lưu đáp án")

    @staticmethod
    def submit_exam(
        db: Session,
        session_token: str,
        data: SubmitExamRequest,
        current_user: Optional[User] = None,
        skip_auth_check: bool = False
    ) -> ExamResultResponse:
        session = db.query(ExamSession).options(
            joinedload(ExamSession.student),
            joinedload(ExamSession.schedule).joinedload(ExamSchedule.exam)
        ).filter(ExamSession.session_token == session_token).first()

        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên thi")

        # Security check: Verify ownership unless system trigger or admin/teacher
        if not skip_auth_check and current_user:
            user_role = current_user.role.code if current_user.role else "STUDENT"
            if user_role == "STUDENT" and session.student_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền nộp bài cho phiên thi của thí sinh khác"
                )

        try:
            if session.status != "SUBMITTED":
                session.submitted_at = datetime.now(timezone.utc)
                session.submit_type = data.submit_type
                session.status = "SUBMITTED"
                db.commit()
                
                # Grade immediately
                GradingService.grade_session(db, session.id)
                db.refresh(session)
        except Exception as e:
            db.rollback()
            logger.error("Error submitting exam for session %d: %s", session.id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi nộp bài thi")

        exam = session.schedule.exam if session.schedule else None
        student_name = session.student.full_name if session.student else "Thí sinh (Đã xoá)"
        student_code = session.student.student_code if session.student else "N/A"
        exam_title = exam.title if exam else "Đề thi"
        total_score_val = float(exam.total_score) if exam else 10.0

        return ExamResultResponse(
            session_id=session.id,
            student_name=student_name,
            student_code=student_code,
            exam_title=exam_title,
            final_score=float(session.final_score) if session.final_score is not None else 0.0,
            total_score=total_score_val,
            submit_type=session.submit_type or "MANUAL",
            status=session.status,
            started_at=session.started_at,
            submitted_at=session.submitted_at,
            risk_score=session.risk_score,
            tab_switch_count=session.tab_switch_count,
            fullscreen_exit_count=session.fullscreen_exit_count
        )
