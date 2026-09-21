from typing import List
from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_role
from app.models.user import User
from app.models.violation_log import ViolationLog
from app.schemas.report_schema import ExamScheduleStatistics
from app.schemas.violation_schema import ViolationLogResponse
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])

@router.get("/schedules/{schedule_id}/statistics", response_model=ExamScheduleStatistics)
def get_schedule_statistics(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Get candidate results, summary metrics and violation stats for an exam schedule."""
    return ReportService.get_schedule_statistics(db, schedule_id)

@router.get("/schedules/{schedule_id}/export-excel")
def export_schedule_excel(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Export exam results to Excel (.xlsx) using openpyxl."""
    excel_stream = ReportService.export_excel(db, schedule_id)
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=KetQuaThi_Ca_{schedule_id}.xlsx"}
    )

@router.get("/schedules/{schedule_id}/export-pdf")
def export_schedule_pdf(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Export exam results to PDF using reportlab."""
    pdf_stream = ReportService.export_pdf(db, schedule_id)
    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=KetQuaThi_Ca_{schedule_id}.pdf"}
    )

@router.get("/sessions/{session_id}/violations", response_model=List[ViolationLogResponse])
def get_session_violations(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """View full chronological violation audit logs for a single candidate session."""
    logs = db.query(ViolationLog).filter(
        ViolationLog.session_id == session_id
    ).order_by(ViolationLog.client_timestamp.asc()).all()
    return [ViolationLogResponse.model_validate(l) for l in logs]
