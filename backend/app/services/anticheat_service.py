import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from app.models.exam_session import ExamSession
from app.models.exam_schedule import ExamSchedule
from app.models.violation_log import ViolationLog
from app.schemas.violation_schema import ViolationLogCreate

logger = logging.getLogger(__name__)

# Risk score weights per violation event type
RISK_WEIGHTS = {
    "TAB_SWITCH": 10,
    "FULLSCREEN_EXIT": 15,
    "DEVTOOLS_DETECTED": 30,
    "COPY_PASTE_ATTEMPT": 5,
    "RIGHT_CLICK_ATTEMPT": 5,
    "DUPLICATE_LOGIN": 25,
    "CONNECTION_LOST": 5,
}

MAX_RISK_SCORE = 1000

class AnticheatService:
    @staticmethod
    def record_violation(
        db: Session,
        session_id: int,
        v_data: ViolationLogCreate
    ) -> Tuple[Optional[ViolationLog], bool]:
        """
        Records a security violation event, increments counters, updates risk score,
        and determines if the violation threshold has been reached.
        Returns: (ViolationLog object or None, is_threshold_exceeded: bool)
        """
        session = db.query(ExamSession).options(
            joinedload(ExamSession.schedule).joinedload(ExamSchedule.exam)
        ).filter(ExamSession.id == session_id).first()
        
        if not session or session.status != "IN_PROGRESS":
            return None, False

        try:
            # Create violation log
            v_log = ViolationLog(
                session_id=session_id,
                event_type=v_data.event_type,
                severity=v_data.severity,
                detail=v_data.detail,
                client_timestamp=v_data.client_timestamp,
                server_timestamp=datetime.now(timezone.utc)
            )
            db.add(v_log)
            db.flush()  # Flush so count() reflects the added record in the current transaction

            # Update specific counters
            if v_data.event_type == "TAB_SWITCH":
                session.tab_switch_count += 1
            elif v_data.event_type == "FULLSCREEN_EXIT":
                session.fullscreen_exit_count += 1

            # Add risk score with upper bound
            weight = RISK_WEIGHTS.get(v_data.event_type, 10)
            session.risk_score = min(session.risk_score + weight, MAX_RISK_SCORE)

            # Count total violations for this session
            total_violations = db.query(ViolationLog).filter(ViolationLog.session_id == session_id).count()
            
            # Check against exam threshold
            max_allowed = 5
            if session.schedule and session.schedule.exam:
                max_allowed = session.schedule.exam.max_violation_allowed
                
            threshold_exceeded = (total_violations >= max_allowed) and (session.status == "IN_PROGRESS")

            db.commit()
            db.refresh(v_log)
            return v_log, threshold_exceeded
        except Exception as e:
            db.rollback()
            logger.error("Error recording violation for session %d: %s", session_id, e, exc_info=True)
            return None, False
