from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import require_role
from app.models.user import User
from app.models.subject import Subject
from app.schemas.question_schema import (
    QuestionAdmin, QuestionCreate, QuestionUpdate, SubjectCreate, SubjectResponse
)
from app.schemas.import_schema import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportErrorOut,
    ImportOptionOut,
    ImportPreviewResponse,
    ImportQuestionOut,
)
from app.services.question_service import QuestionService
from app.services.question_import_service import (
    FORMAT_LABELS,
    build_template_docx,
    commit_import,
    preview_import,
)

router = APIRouter(prefix="/questions", tags=["Questions & Question Bank"])

# --- Subjects ---
@router.get("/subjects", response_model=List[SubjectResponse])
def get_subjects(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """List all subjects."""
    return QuestionService.get_subjects(db)

@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
def create_subject(
    data: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Create a new subject."""
    return QuestionService.create_subject(db, data)

# --- Questions ---
@router.get("", response_model=List[QuestionAdmin])
def list_questions(
    subject_id: Optional[int] = None,
    difficulty: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """List questions in question bank with optional filtering."""
    return QuestionService.get_questions(db, subject_id, difficulty, search)

@router.get("/{question_id}", response_model=QuestionAdmin)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Get single question detail by ID."""
    return QuestionService.get_question_by_id(db, question_id)

@router.post("", response_model=QuestionAdmin, status_code=status.HTTP_201_CREATED)
def create_question(
    data: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Create a new question with options."""
    return QuestionService.create_question(db, data, current_user.id)

@router.put("/{question_id}", response_model=QuestionAdmin)
def update_question(
    question_id: int,
    data: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Update question and its options."""
    return QuestionService.update_question(db, question_id, data)

@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Delete question by ID."""
    return QuestionService.delete_question(db, question_id)


# --- Nhập câu hỏi hàng loạt từ file .docx ---

@router.get("/import/template")
def download_import_template(
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"]))
):
    """Tải file .docx mẫu để giảng viên điền theo đúng định dạng hệ thống nhận."""
    content = build_template_docx()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=Mau_Import_Cau_Hoi.docx"},
    )


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def preview_question_import(
    file: UploadFile = File(...),
    subject_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"])),
):
    """Bước 1/2: đọc thử file .docx và báo kết quả — KHÔNG ghi gì vào CSDL.

    GV xem kết quả rồi mới quyết định có import hay không, tránh tạo ra hàng loạt
    câu hỏi sai định dạng rồi mới phát hiện.
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Môn học không tồn tại")

    file_bytes = await file.read()
    try:
        (token, questions, errors, duplicate_count,
         total_rows, new_count, format_used, parsed_count) = preview_import(
            db, file_bytes, file.filename or "", subject_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    format_label = FORMAT_LABELS.get(format_used, format_used)
    # Ghép các thông tin lại theo đúng thứ tự ưu tiên. Phải nêu BẰNG CẢ hai loại
    # (lỗi và trùng) trong cùng một câu thông điệp, nếu không GV sẽ tưởng chỉ có
    # một loại và hiểu sai số câu thực sự sẽ được nhập.
    if parsed_count == 0 and not errors:
        message = "Không tìm thấy câu hỏi nào trong file."
    else:
        parts = [f"Đọc được {parsed_count} câu."]
        if duplicate_count:
            parts.append(
                f"{duplicate_count} câu đã tồn tại trong ngân hàng nên sẽ bỏ qua."
            )
        if errors:
            parts.append(
                f"{len(errors)} dòng bị lỗi và cũng sẽ bỏ qua — "
                "lỗi ở một dòng không ảnh hưởng các dòng còn lại."
            )
        parts.append(f"Sẽ nhập {new_count} câu.")
        message = " ".join(parts)

    return ImportPreviewResponse(
        preview_token=token,
        format_used=format_used,
        format_label=format_label,
        subject_id=subject_id,
        total_rows=total_rows,
        parsed_count=parsed_count,
        error_count=len(errors),
        duplicate_count=duplicate_count,
        new_count=new_count,
        questions=[
            ImportQuestionOut(
                content=q.content,
                type=q.type,
                difficulty=q.difficulty,
                options=[
                    ImportOptionOut(content=o.content, is_correct=o.is_correct)
                    for o in q.options
                ],
                source_row=q.source_row,
            )
            for q in questions
        ],
        errors=[
            ImportErrorOut(row=e.row, reason=e.reason, snippet=e.snippet) for e in errors
        ],
        message=message,
    )


@router.post("/import/commit", response_model=ImportCommitResponse)
def commit_question_import(
    payload: ImportCommitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "TEACHER"])),
):
    """Bước 2/2: ghi các câu hỏi đã đọc thử vào ngân hàng câu hỏi.

    Toàn bộ nằm trong một transaction: nếu có lỗi giữa chừng thì rollback sạch,
    không để lại dữ liệu dở dang.
    """
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Môn học không tồn tại")

    try:
        imported, skipped = commit_import(db, payload.preview_token, payload.subject_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nội bộ khi nhập câu hỏi")

    parts = [f"Đã nhập {imported} câu hỏi vào môn {subject.code}."]
    if skipped:
        parts.append(f"Bỏ qua {skipped} câu trùng với câu hỏi đã có.")
    return ImportCommitResponse(imported_count=imported, skipped_duplicate_count=skipped, message=" ".join(parts))
