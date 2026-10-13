from typing import List, Optional
from pydantic import BaseModel, Field


class ImportOptionOut(BaseModel):
    content: str
    is_correct: bool


class ImportQuestionOut(BaseModel):
    content: str
    type: str
    difficulty: str
    options: List[ImportOptionOut]
    source_row: Optional[int] = None


class ImportErrorOut(BaseModel):
    row: Optional[int]
    reason: str
    snippet: str = ""


class ImportPreviewResponse(BaseModel):
    """Kết quả đọc thử file — CHƯA ghi gì vào CSDL."""
    preview_token: str
    format_used: str
    format_label: str
    subject_id: int
    total_rows: int
    parsed_count: int
    error_count: int
    duplicate_count: int
    new_count: int
    questions: List[ImportQuestionOut]
    errors: List[ImportErrorOut]
    message: str = ""


class ImportCommitRequest(BaseModel):
    preview_token: str = Field(..., min_length=10, max_length=128)
    subject_id: int


class ImportCommitResponse(BaseModel):
    imported_count: int
    skipped_duplicate_count: int
    message: str
