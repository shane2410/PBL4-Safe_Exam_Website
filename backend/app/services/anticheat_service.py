from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.exam_session import ExamSession
from app.models.violation_log import ViolationLog
from app.schemas.violation_schema import ViolationLogCreate

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

class AnticheatService:
    @staticmethod
    def record_violation(
        db: Session,
        session_id: int,
        v_data: ViolationLogCreate
    ) -> Tuple[ViolationLog, bool]:
        """
        Records a security violation event, increments counters, updates risk score,
        and determines if the violation threshold has been reached.
        Returns: (ViolationLog object, is_threshold_exceeded: bool)
        """
        session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
        if not session or session.status == "SUBMITTED":
            return None, False

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

        # Update specific counters
        if v_data.event_type == "TAB_SWITCH":
            session.tab_switch_count += 1
        elif v_data.event_type == "FULLSCREEN_EXIT":
            session.fullscreen_exit_count += 1

        # Add risk score
        weight = RISK_WEIGHTS.get(v_data.event_type, 10)
        session.risk_score += weight

        # Count total violations for this session
        total_violations = db.query(ViolationLog).filter(ViolationLog.session_id == session_id).count() + 1
        
        # Check against exam threshold
        max_allowed = session.schedule.exam.max_violation_allowed if session.schedule and session.schedule.exam else 5
        threshold_exceeded = total_violations >= max_allowed

        db.commit()
        db.refresh(v_log)
        return v_log, threshold_exceeded
