import logging
import random
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from app.core.security import to_utc_naive
from app.dependencies.client_identity import ClientIdentity
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
from app.schemas.violation_schema import ViolationLogCreate, resolve_severity
from app.dependencies.exam_time import check_exam_schedule_active
from app.services.grading_service import GradingService
from app.services.exam_security_service import ExamSecurityService
from app.services.anticheat_service import AnticheatService

logger = logging.getLogger(__name__)

ALLOWED_SUBMIT_TYPES = {"MANUAL", "SHUTDOWN_BUTTON", "AUTO_TIMEOUT", "AUTO_VIOLATION"}


def _get_deadline(session: ExamSession, schedule: ExamSchedule) -> datetime:
    """Mốc chót nộp bài theo đồng hồ SERVER (skills.md Quy tắc #4.1).

    = min(thời điểm bắt đầu + thời lượng đề, thời điểm kết thúc ca thi)
    Trả về datetime UTC-naive để so sánh với `datetime.now(timezone.utc)` đã bỏ tz.
    """
    started_at = to_utc_naive(session.started_at)
    exam_duration = schedule.exam.duration_minutes if schedule.exam else 0
    end_by_duration = started_at + timedelta(minutes=exam_duration)
    schedule_end = to_utc_naive(schedule.end_time)
    return min(end_by_duration, schedule_end)


def _device_id_from_fingerprint(fingerprint: str | None) -> str | None:
    """device_id là 16 ký tự đầu của fingerprint (cùng sha256(public_key)).

    Suy ra từ fingerprint vì ClientIdentity chỉ mang fingerprint; tránh thêm
    một header nữa chỉ để truyền cùng một thông tin.
    """
    if not fingerprint or len(fingerprint) < 16:
        return None
    return fingerprint[:16]


class ExamSessionService:
    @staticmethod
    def join_exam(
        db: Session,
        room_code: str,
        student_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        client_identity: Optional[ClientIdentity] = None,
    ) -> ExamTakingStateResponse:
        identity = client_identity or ClientIdentity()
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

        # --- Phase 0: áp dụng chính sách khoá an toàn ---
        policy = ExamSecurityService.resolve_policy(db, exam.id)
        seb_required = ExamSecurityService.is_safe_browser_required(db, exam)

        # Client tự khai là SEB thì vẫn phải được xác thực bằng challenge-response.
        # Nếu chưa attest -> coi như web thường (không tin lời khai của client).
        #
        # KHÔNG dùng trạng thái phiên để suy ra điều này: một phiên đã VERIFIED
        # rồi thì ai có access token cũng mở được bằng trình duyệt thường, đúng
        # thứ cần chặn. Việc trang web nhúng trong SEB không bị coi là "web" là
        # trách nhiệm của client — nó phải gắn header định danh cho request do
        # webview phát ra (sebclient/ui/request_interceptor.py) và attest lại
        # trước khi token 5 phút hết hạn.
        claims_seb = identity.is_seb
        is_verified_seb = claims_seb and identity.attested
        restricted_mode = seb_required and not is_verified_seb

        if seb_required and not identity.attested and not policy.allow_web_fallback:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Kỳ thi yêu cầu sử dụng Safe Exam Browser và không cho phép làm bài qua trình duyệt web thông thường",
            )

        # Check existing session
        session = db.query(ExamSession).filter(
            ExamSession.schedule_id == schedule.id,
            ExamSession.student_id == student_id
        ).first()

        now = datetime.now(timezone.utc)
        if not session:
            token = f"sess_{uuid.uuid4().hex}"
            attestation_status = "VERIFIED" if is_verified_seb else "NOT_ATTESTED"
            if seb_required and not is_verified_seb:
                attestation_status = "REQUIRED_MISSING"

            session = ExamSession(
                schedule_id=schedule.id,
                student_id=student_id,
                session_token=token,
                started_at=now,
                status="IN_PROGRESS",
                ip_address=ip_address,
                user_agent=user_agent,
                client_type="seb" if is_verified_seb else "web",
                client_version=identity.client_version,
                device_fingerprint=identity.device_fingerprint,
                device_id=_device_id_from_fingerprint(identity.device_fingerprint),
                attestation_status=attestation_status,
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
            # Phiên từng bị heartbeat đánh dấu DISCONNECTED (rớt mạng > ngưỡng)
            # phải được đưa về IN_PROGRESS khi thí sinh vào lại. Nếu không,
            # `AnticheatService.record_violation` (yêu cầu status == IN_PROGRESS)
            # sẽ bỏ qua im lặng MỌI vi phạm còn lại và ngưỡng tự nộp không bao
            # giờ kích hoạt nữa.
            if session.status == "DISCONNECTED":
                session.status = "IN_PROGRESS"
                logger.info("Phiên %d vào lại sau khi mất kết nối -> IN_PROGRESS", session.id)
            # Update IP and user-agent on reconnect
            if ip_address or user_agent:
                if ip_address:
                    session.ip_address = ip_address
                if user_agent:
                    session.user_agent = user_agent
            # Reconnect bằng client khác -> cập nhật thông tin client, nếu đã xác thực
            # thì nâng trạng thái lại tương ứng (VD: GV mới bật cờ giữa kỳ thi).
            # CHỈ NÂNG, KHÔNG HẠ. Một yêu cầu join không kèm attestation token
            # (VD: chính trang web nhúng trong SEB Client gọi lại join_exam) KHÔNG
            # được xoá dấu vết client đã xác thực — nếu không, thí sinh chỉ cần
            # mở web app là mất hoàn toàn dấu vết SEB khỏi phiên.
            if is_verified_seb:
                session.client_type = "seb"
                session.attestation_status = "VERIFIED"
            session.client_version = identity.client_version or session.client_version
            if identity.device_fingerprint:
                session.device_fingerprint = identity.device_fingerprint
                session.device_id = _device_id_from_fingerprint(
                    identity.device_fingerprint
                ) or session.device_id
            elif seb_required and session.attestation_status != "VERIFIED":
                session.attestation_status = "REQUIRED_MISSING"
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning("Failed to update reconnect client info for session %d: %s", session.id, e)

        # Ghi vết client đã xác thực vào CHÍNH phiên thi này (áp dụng cho cả
        # lần tạo phiên mới lẫn reconnect — nếu chỉ ghi ở nhánh tạo mới thì
        # phiên đã tồn tại sẽ không có vết để phục tra).
        # Phase 1 dùng bản ghi này để xác minh heartbeat.
        if is_verified_seb and identity.device_fingerprint:
            from app.models.client_attestation import ClientAttestation
            already = db.query(ClientAttestation).filter(
                ClientAttestation.session_id == session.id,
                ClientAttestation.device_fingerprint == identity.device_fingerprint,
                ClientAttestation.verified.is_(True),
            ).count() > 0
            if not already:
                db.add(ClientAttestation(
                    session_id=session.id,
                    client_type="seb",
                    client_version=identity.client_version,
                    device_fingerprint=identity.device_fingerprint,
                device_id=_device_id_from_fingerprint(identity.device_fingerprint),
                    verified=True,
                    verification_detail="OK_ON_JOIN",
                    key_salt=secrets.token_hex(16),
                ))
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.warning("Không ghi được vết xác thực client cho session %d", session.id)

        # Ghi nhận việc thí sinh dùng web khi đề đang bắt buộc SEB (restricted mode).
        # Đây là BẰNG CHỨNG phục tra, không phải cơ chế ngăn chặn (skills.md Quy tắc #5).
        if restricted_mode:
            AnticheatService.record_violation(db, session.id, ViolationLogCreate(
                event_type="UNAUTHORIZED_CLIENT",
                detail={
                    "reason": "Exam requires Safe Exam Browser Client",
                    "claimed_client_type": identity.client_type,
                    "attested": False,
                },
                client_timestamp=datetime.now(timezone.utc),
            ))

        # Calculate time remaining (SERVER-authoritative)
        started_at = to_utc_naive(session.started_at)
        schedule_end = to_utc_naive(schedule.end_time)
        effective_end = min(started_at + timedelta(minutes=exam.duration_minutes), schedule_end)
        remaining_seconds = max(0, int((effective_end - to_utc_naive(now)).total_seconds()))

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
            max_violation_allowed=AnticheatService.resolve_max_violations_for_exam(db, exam),
            # Khôi phục bộ đếm đã tích luỹ (F5 / vào lại phòng) để UI hiển thị
            # đúng "x/y" thay vì luôn bắt đầu lại từ 0.
            tab_switch_count=session.tab_switch_count or 0,
            fullscreen_exit_count=session.fullscreen_exit_count or 0,
            questions=public_questions,
            saved_answers=saved_dict,
            security_policy=policy,
            require_safe_browser=seb_required,
            restricted_mode=restricted_mode,
        )

    @staticmethod
    def save_answer(
        db: Session,
        session_token: str,
        data: SaveAnswerRequest,
        current_user: User
    ) -> dict:
        session = db.query(ExamSession).options(
            joinedload(ExamSession.schedule).joinedload(ExamSchedule.exam)
        ).filter(ExamSession.session_token == session_token).first()
        if not session or session.status == "SUBMITTED":
            raise HTTPException(status_code=400, detail="Phiên thi không hợp lệ hoặc đã kết thúc")

        # Security check: Verify ownership
        user_role = current_user.role.code if current_user.role else "STUDENT"
        if user_role == "STUDENT" and session.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền thao tác trên phiên thi của thí sinh khác"
            )

        if not session.schedule or not session.schedule.exam:
            raise HTTPException(status_code=500, detail="Đề thi liên kết với ca thi không tồn tại")

        # Server-authoritative time: chặn lưu đáp án SAU khi hết giờ.
        # Trước đây chỉ kiểm tra thời gian lúc join, nên gọi API trực tiếp vẫn lưu được.
        now = datetime.now(timezone.utc)
        deadline = _get_deadline(session, session.schedule)
        if to_utc_naive(now) > deadline:
            logger.info(
                "Từ chối lưu đáp án ngoài giờ: session=%d, quá hạn %s giây",
                session.id, int((to_utc_naive(now) - deadline).total_seconds()),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Đã hết thời gian làm bài, không thể lưu đáp án",
            )

        # Chỉ cho lưu câu hỏi thực sự thuộc đề thi này — trước đây thiếu bước này,
        # thí sinh có thể gửi question_id bất kỳ để dựng bài giả.
        exam_question = db.query(ExamQuestion).filter(
            ExamQuestion.exam_id == session.schedule.exam_id,
            ExamQuestion.question_id == data.question_id,
        ).first()
        if not exam_question:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Câu hỏi không thuộc đề thi hiện tại",
            )

        # Các lựa chọn được chọn phải thuộc đúng câu hỏi đó.
        if data.selected_option_ids:
            option_count = db.query(QuestionOption).filter(
                QuestionOption.question_id == data.question_id,
                QuestionOption.id.in_(data.selected_option_ids),
            ).count()
            if option_count != len(set(data.selected_option_ids)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Danh sách lựa chọn không hợp lệ với câu hỏi này",
                )

        ans = db.query(StudentAnswer).filter(
            StudentAnswer.session_id == session.id,
            StudentAnswer.question_id == data.question_id
        ).first()

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

        # Validate submit_type — client có thể gửi bất kỳ chuỗi nào.
        if data.submit_type not in ALLOWED_SUBMIT_TYPES:
            logger.warning(
                "submit_type không hợp lệ '%s' cho session %d, chuyển thành MANUAL",
                data.submit_type, session.id,
            )
            data.submit_type = "MANUAL"

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
