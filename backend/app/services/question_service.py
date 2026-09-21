import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.models.subject import Subject
from app.models.exam_question import ExamQuestion
from app.schemas.question_schema import QuestionCreate, QuestionUpdate, QuestionAdmin, SubjectCreate, SubjectResponse

logger = logging.getLogger(__name__)

def escape_like(s: str) -> str:
    """Escapes SQL LIKE wildcards (% and _) and backslashes."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

class QuestionService:
    @staticmethod
    def get_subjects(db: Session) -> List[SubjectResponse]:
        subjects = db.query(Subject).all()
        return [SubjectResponse.model_validate(s) for s in subjects]

    @staticmethod
    def create_subject(db: Session, data: SubjectCreate) -> SubjectResponse:
        existing = db.query(Subject).filter(Subject.code == data.code).first()
        if existing:
            raise HTTPException(status_code=400, detail="Mã môn học đã tồn tại")
        subj = Subject(code=data.code, name=data.name)
        try:
            db.add(subj)
            db.commit()
            db.refresh(subj)
            return SubjectResponse.model_validate(subj)
        except Exception as e:
            db.rollback()
            logger.error("Error creating subject: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi tạo môn học")

    @staticmethod
    def get_questions(
        db: Session,
        subject_id: Optional[int] = None,
        difficulty: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[QuestionAdmin]:
        query = db.query(Question)
        if subject_id:
            query = query.filter(Question.subject_id == subject_id)
        if difficulty:
            query = query.filter(Question.difficulty == difficulty)
        if search:
            safe_search = escape_like(search.strip())
            query = query.filter(Question.content.ilike(f"%{safe_search}%"))
            
        questions = query.order_by(Question.id.desc()).all()
        return [QuestionAdmin.model_validate(q) for q in questions]

    @staticmethod
    def get_question_by_id(db: Session, question_id: int) -> QuestionAdmin:
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q:
            raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi")
        return QuestionAdmin.model_validate(q)

    @staticmethod
    def create_question(db: Session, data: QuestionCreate, user_id: int) -> QuestionAdmin:
        # Check subject
        subject = db.query(Subject).filter(Subject.id == data.subject_id).first()
        if not subject:
            raise HTTPException(status_code=404, detail="Môn học không tồn tại")
            
        q = Question(
            subject_id=data.subject_id,
            content=data.content,
            type=data.type,
            difficulty=data.difficulty,
            image_url=data.image_url,
            created_by=user_id
        )
        try:
            db.add(q)
            db.flush()

            for opt in data.options:
                db.add(QuestionOption(
                    question_id=q.id,
                    content=opt.content,
                    is_correct=opt.is_correct,
                    order_index=opt.order_index
                ))
                
            db.commit()
            db.refresh(q)
            return QuestionAdmin.model_validate(q)
        except Exception as e:
            db.rollback()
            logger.error("Error creating question: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi lưu câu hỏi")

    @staticmethod
    def update_question(db: Session, question_id: int, data: QuestionUpdate) -> QuestionAdmin:
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q:
            raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi")
            
        try:
            if data.content is not None:
                q.content = data.content
            if data.type is not None:
                q.type = data.type
            if data.difficulty is not None:
                q.difficulty = data.difficulty
            if data.image_url is not None:
                q.image_url = data.image_url

            if data.options is not None:
                # Remove old options
                db.query(QuestionOption).filter(QuestionOption.question_id == q.id).delete()
                for opt in data.options:
                    db.add(QuestionOption(
                        question_id=q.id,
                        content=opt.content,
                        is_correct=opt.is_correct,
                        order_index=opt.order_index
                    ))
                    
            db.commit()
            db.refresh(q)
            return QuestionAdmin.model_validate(q)
        except Exception as e:
            db.rollback()
            logger.error("Error updating question %d: %s", question_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi cập nhật câu hỏi")

    @staticmethod
    def delete_question(db: Session, question_id: int) -> dict:
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q:
            raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi")

        # Check if question is used in any exam
        in_use = db.query(ExamQuestion).filter(ExamQuestion.question_id == question_id).first()
        if in_use:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể xoá câu hỏi vì đang được sử dụng trong một hoặc nhiều đề thi"
            )

        try:
            db.delete(q)
            db.commit()
            return {"message": "Đã xoá câu hỏi thành công"}
        except Exception as e:
            db.rollback()
            logger.error("Error deleting question %d: %s", question_id, e, exc_info=True)
            raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi xoá câu hỏi")
