from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.models.exam import Exam
from app.models.exam_question import ExamQuestion
from app.models.exam_schedule import ExamSchedule
from app.models.subject import Subject
from app.schemas.exam_schema import (
    ExamCreate, ExamUpdate, ExamResponse, ExamDetailResponse,
    ExamScheduleCreate, ExamScheduleUpdate, ExamScheduleResponse
)

class ExamService:
    @staticmethod
    def get_exams(db: Session, subject_id: Optional[int] = None) -> List[ExamResponse]:
        query = db.query(Exam)
        if subject_id:
            query = query.filter(Exam.subject_id == subject_id)
        exams = query.order_by(Exam.id.desc()).all()
        
        result = []
        for e in exams:
            item = ExamResponse.model_validate(e)
            item.question_count = len(e.exam_questions)
            result.append(item)
        return result

    @staticmethod
    def get_exam_detail(db: Session, exam_id: int) -> ExamDetailResponse:
        exam = db.query(Exam).options(
            joinedload(Exam.exam_questions).joinedload(ExamQuestion.question)
        ).filter(Exam.id == exam_id).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")
        
        res = ExamDetailResponse.model_validate(exam)
        res.question_count = len(exam.exam_questions)
        return res

    @staticmethod
    def create_exam(db: Session, data: ExamCreate, user_id: int) -> ExamDetailResponse:
        # Check subject
        subject = db.query(Subject).filter(Subject.id == data.subject_id).first()
        if not subject:
            raise HTTPException(status_code=404, detail="Môn học không tồn tại")
            
        exam = Exam(
            title=data.title,
            subject_id=data.subject_id,
            duration_minutes=data.duration_minutes,
            total_score=data.total_score,
            is_shuffled=data.is_shuffled,
            max_violation_allowed=data.max_violation_allowed,
            created_by=user_id
        )
        db.add(exam)
        db.flush()

        for q_item in data.questions:
            db.add(ExamQuestion(
                exam_id=exam.id,
                question_id=q_item.question_id,
                score=q_item.score,
                order_index=q_item.order_index
            ))
            
        db.commit()
        db.refresh(exam)
        return ExamService.get_exam_detail(db, exam.id)

    @staticmethod
    def update_exam(db: Session, exam_id: int, data: ExamUpdate) -> ExamDetailResponse:
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")
            
        if data.title is not None:
            exam.title = data.title
        if data.duration_minutes is not None:
            exam.duration_minutes = data.duration_minutes
        if data.total_score is not None:
            exam.total_score = data.total_score
        if data.is_shuffled is not None:
            exam.is_shuffled = data.is_shuffled
        if data.max_violation_allowed is not None:
            exam.max_violation_allowed = data.max_violation_allowed

        if data.questions is not None:
            db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam.id).delete()
            for q_item in data.questions:
                db.add(ExamQuestion(
                    exam_id=exam.id,
                    question_id=q_item.question_id,
                    score=q_item.score,
                    order_index=q_item.order_index
                ))
                
        db.commit()
        db.refresh(exam)
        return ExamService.get_exam_detail(db, exam.id)

    @staticmethod
    def delete_exam(db: Session, exam_id: int) -> dict:
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")
        db.delete(exam)
        db.commit()
        return {"message": "Đã xoá đề thi thành công"}

    # --- Schedules ---
    @staticmethod
    def get_schedules(db: Session, status_filter: Optional[str] = None) -> List[ExamScheduleResponse]:
        query = db.query(ExamSchedule).options(
            joinedload(ExamSchedule.exam).joinedload(Exam.subject),
            joinedload(ExamSchedule.supervisor)
        )
        if status_filter:
            query = query.filter(ExamSchedule.status == status_filter)
        schedules = query.order_by(ExamSchedule.start_time.desc()).all()
        return [ExamScheduleResponse.model_validate(s) for s in schedules]

    @staticmethod
    def create_schedule(db: Session, data: ExamScheduleCreate, user_id: int) -> ExamScheduleResponse:
        # Check exam
        exam = db.query(Exam).filter(Exam.id == data.exam_id).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Đề thi không tồn tại")
        # Check duplicate room code
        existing = db.query(ExamSchedule).filter(ExamSchedule.room_code == data.room_code.upper()).first()
        if existing:
            raise HTTPException(status_code=400, detail="Mã phòng thi đã tồn tại")
            
        schedule = ExamSchedule(
            exam_id=data.exam_id,
            room_code=data.room_code.upper(),
            start_time=data.start_time,
            end_time=data.end_time,
            supervised_by=user_id,
            status=data.status
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return ExamScheduleResponse.model_validate(schedule)

    @staticmethod
    def update_schedule(db: Session, schedule_id: int, data: ExamScheduleUpdate) -> ExamScheduleResponse:
        schedule = db.query(ExamSchedule).filter(ExamSchedule.id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Không tìm thấy ca thi")
        if data.room_code is not None:
            schedule.room_code = data.room_code.upper()
        if data.start_time is not None:
            schedule.start_time = data.start_time
        if data.end_time is not None:
            schedule.end_time = data.end_time
        if data.status is not None:
            schedule.status = data.status
        db.commit()
        db.refresh(schedule)
        return ExamScheduleResponse.model_validate(schedule)
