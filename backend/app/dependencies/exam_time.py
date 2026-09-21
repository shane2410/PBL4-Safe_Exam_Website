from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.exam_schedule import ExamSchedule

def check_exam_schedule_active(schedule: ExamSchedule) -> None:
    """Verifies if the exam schedule is active according to server time."""
    now = datetime.now(timezone.utc)
    
    if schedule.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ca thi này đã bị huỷ"
        )
    if schedule.status == "FINISHED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ca thi này đã kết thúc"
        )
        
    start_time = schedule.start_time
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
        
    end_time = schedule.end_time
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    if now < start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chưa đến giờ bắt đầu ca thi"
        )
    if now > end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ca thi đã quá thời gian kết thúc"
        )
