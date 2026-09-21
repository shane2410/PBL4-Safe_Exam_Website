from typing import Optional
from sqlalchemy.orm import Session, joinedload
from app.models.exam_session import ExamSession
from app.models.exam_question import ExamQuestion
from app.models.student_answer import StudentAnswer
from app.models.question import Question
from app.models.question_option import QuestionOption

class GradingService:
    @staticmethod
    def grade_session(db: Session, session_id: int) -> float:
        """Automatically grades all answers for a given exam session and calculates final_score."""
        session = db.query(ExamSession).options(
            joinedload(ExamSession.schedule),
            joinedload(ExamSession.answers).joinedload(StudentAnswer.question).joinedload(Question.options)
        ).filter(ExamSession.id == session_id).first()
        
        if not session:
            return 0.0

        # Build map of question_id -> score in exam
        exam_questions = db.query(ExamQuestion).filter(ExamQuestion.exam_id == session.schedule.exam_id).all()
        q_score_map = {eq.question_id: float(eq.score) for eq in exam_questions}

        total_earned = 0.0

        for ans in session.answers:
            question = ans.question
            if not question:
                continue
                
            max_q_score = q_score_map.get(question.id, 1.0)
            earned_q_score = 0.0

            # Correct option IDs
            correct_option_ids = [opt.id for opt in question.options if opt.is_correct]
            selected_ids = ans.selected_option_ids or []

            if question.type == "SINGLE_CHOICE":
                if len(selected_ids) == 1 and selected_ids[0] in correct_option_ids:
                    earned_q_score = max_q_score
            elif question.type == "MULTI_CHOICE":
                # Check exact set match
                if set(selected_ids) == set(correct_option_ids):
                    earned_q_score = max_q_score
            elif question.type == "FILL_BLANK":
                user_text = (ans.fill_blank_text or "").strip().lower()
                correct_texts = [opt.content.strip().lower() for opt in question.options if opt.is_correct]
                if user_text in correct_texts:
                    earned_q_score = max_q_score

            ans.auto_score = round(earned_q_score, 2)
            total_earned += earned_q_score

        final_score = round(total_earned, 2)
        session.final_score = final_score
        db.commit()
        return final_score
