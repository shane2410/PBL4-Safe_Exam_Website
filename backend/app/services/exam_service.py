import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models.exam import Exam
from app.models.exam_question import ExamQuestion
from app.models.exam_schedule import ExamSchedule
from app.models.subject import Subject
from app.schemas.exam_schema import (
    ExamCreate, ExamUpdate, ExamResponse, ExamDetailResponse,
    ExamQuestionResponse, ExamScheduleCreate, ExamScheduleUpdate, ExamScheduleResponse
)
from app.services.exam_security_service import ExamSecurityService
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

class ExamService:
    @staticmethod
    def get_exams(db: Session, subject_id: Optional[int] = None) -> List[ExamResponse]:
        # joinedload cả 2 quan hệ mà ExamResponse chạm tới:
        #   * exam_questions -> dùng cho `question_count`
        #   * subject        -> ExamResponse.subject
        # Trước đây không có joinedload nên với N đề, SQLAlchemy bắn thêm 2N
        # câu SELECT (N cho số câu hỏi + N cho môn học) — trang danh sách đề
        # chậm dần rõ rệt khi ngân hàng đề lớn lên.
        # Dùng selectinload cho exam_questions để tránh nhân bản dòng khi
        # joinedload kết hợp với collection (mỗi đề N câu sẽ lặp N lần).
        query = db.query(Exam).options(
            selectinload(Exam.exam_questions),
            joinedload(Exam.subject),
        )
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
            joinedload(Exam.exam_questions).joinedload(ExamQuestion.question),
            joinedload(Exam.security_config)
        ).filter(Exam.id == exam_id).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")

        # `Exam.security_config` là ORM row (cột `config` dạng JSON), không phải
        # schema Pydantic. Validate thẳng ORM object vào ExamDetailResponse sẽ
        # ném ValidationError ngay khi đề ĐÃ có cấu hình riêng — tức là giáo
        # viên càng chỉnh cấu hình thì trang sửa đề càng chắc chắn hỏng.
        # Vì vậy dựng response từ ExamResponse (không có field này) rồi gán
        # policy ĐÃ RESOLVE vào.
        base = ExamResponse.model_validate(exam)
        res = ExamDetailResponse(
            **base.model_dump(),
            exam_questions=[
                ExamQuestionResponse.model_validate(eq) for eq in exam.exam_questions
            ],
            security_config=ExamSecurityService.resolve_policy(db, exam_id),
            require_safe_browser_global=SettingsService.get_require_safe_browser_global(db),
        )
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
            require_safe_browser=data.require_safe_browser,
            created_by=user_id
        )
        try:
            db.add(exam)
            db.flush()

            for q_item in data.questions:
                db.add(ExamQuestion(
                    exam_id=exam.id,
                    question_id=q_item.question_id,
                    score=q_item.score,
                    order_index=q_item.order_index
                ))

            # Lưu cấu hình khoá an toàn riêng cho đề nếu GV có gửi kèm
            if data.security_config:
                ExamSecurityService.save_config(db, exam.id, data.security_config)

            db.commit()
            db.refresh(exam)
            return ExamService.get_exam_detail(db, exam.id)
        except Exception as e:
            db.rollback()
            logger.error("Error creating exam: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi tạo đề thi")

    @staticmethod
    def update_exam(db: Session, exam_id: int, data: ExamUpdate) -> ExamDetailResponse:
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")

        try:
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
            if data.require_safe_browser is not None:
                exam.require_safe_browser = data.require_safe_browser

            if data.security_config is not None:
                ExamSecurityService.save_config(db, exam.id, data.security_config)

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
        except Exception as e:
            db.rollback()
            logger.error("Error updating exam %d: %s", exam_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi cập nhật đề thi")

    @staticmethod
    def delete_exam(db: Session, exam_id: int) -> dict:
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        if not exam:
            raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")
            
        # Check if exam has existing schedules
        active_schedules = db.query(ExamSchedule).filter(ExamSchedule.exam_id == exam_id).all()
        if active_schedules:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể xoá đề thi đang được gắn vào ca thi. Vui lòng xoá hoặc huỷ các ca thi liên quan trước."
            )

        try:
            db.delete(exam)
            db.commit()
            return {"message": "Đã xoá đề thi thành công"}
        except Exception as e:
            db.rollback()
            logger.error("Error deleting exam %d: %s", exam_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi xoá đề thi")

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
        # Validate end_time > start_time
        if data.end_time <= data.start_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thời gian kết thúc (end_time) phải sau thời gian bắt đầu (start_time)"
            )

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
        try:
            db.add(schedule)
            db.commit()
            db.refresh(schedule)
            return ExamScheduleResponse.model_validate(schedule)
        except Exception as e:
            db.rollback()
            logger.error("Error creating exam schedule: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi tạo ca thi")

    @staticmethod
    def update_schedule(db: Session, schedule_id: int, data: ExamScheduleUpdate) -> ExamScheduleResponse:
        schedule = db.query(ExamSchedule).filter(ExamSchedule.id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Không tìm thấy ca thi")
            
        new_start = data.start_time if data.start_time is not None else schedule.start_time
        new_end = data.end_time if data.end_time is not None else schedule.end_time
        if new_end <= new_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thời gian kết thúc (end_time) phải sau thời gian bắt đầu (start_time)"
            )

        try:
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
        except Exception as e:
            db.rollback()
            logger.error("Error updating exam schedule %d: %s", schedule_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi cập nhật ca thi")
