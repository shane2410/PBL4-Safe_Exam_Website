import io
import logging
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_option import QuestionOption
from app.services.import_service import (
    ParseError,
    ParsedQuestion,
    content_fingerprint,
    parse_docx,
)

logger = logging.getLogger(__name__)

PREVIEW_TTL_MINUTES = 30
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Kho chứa kết quả đọc thử: token -> (thời điểm hết hạn, subject_id, câu hỏi, số trùng).
# Lưu trong bộ nhớ: đây là dữ liệu tạm, không cần bền vững, và tự biến mất khi
# khởi động lại server — người dùng chỉ cần đọc thử lại.
_preview_store: Dict[str, dict] = {}

FORMAT_LABELS = {
    "table": "Bảng Word",
    "text": "Văn bản phân tách",
    "unknown": "Không nhận diện được",
}


def _purge_expired_previews() -> None:
    now = datetime.now(timezone.utc)
    expired = [k for k, v in _preview_store.items() if v["expires_at"] < now]
    for k in expired:
        _preview_store.pop(k, None)


def _new_token() -> str:
    return "imp_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=32))


def find_existing_fingerprints(
    db: Session, questions: List[ParsedQuestion], subject_id: int
) -> set:
    """Trả về tập fingerprint đã tồn tại TRONG CÙNG MÔN với câu sắp import.

    Phải lọc theo `subject_id`: trước đây hàm quét toàn bộ ngân hàng câu hỏi,
    nên một câu cơ bản (VD "TCP là giao thức tầng nào?") đã có ở môn Mạng máy
    tính sẽ bị coi là trùng khi giảng viên môn An toàn thông tin muốn thêm nó
    vào môn của mình — họ không import được dù câu hỏi hoàn toàn hợp lệ với môn.

    Vẫn quét ở tầng ứng dụng (không thêm unique index) vì phạm vi đã thu hẹp
    còn một môn, đủ nhanh với quy mô ngân hàng của một trường.
    """
    existing = {
        content_fingerprint(c)
        for (c,) in db.query(Question.content).filter(
            Question.subject_id == subject_id
        ).all()
    }
    return {content_fingerprint(q.content) for q in questions} & existing


def preview_import(
    db: Session,
    file_bytes: bytes,
    filename: str,
    subject_id: int,
) -> Tuple[str, List[ParsedQuestion], List[ParseError], int, int, int, str, int]:
    """Đọc thử file, KHÔNG ghi CSDL.

    Trả về: (token, câu hỏi hợp lệ, lỗi, số trùng, số tổng dòng, số câu mới,
             định dạng, số dòng)
    """
    if not filename.lower().endswith(".docx"):
        raise ValueError("Chỉ hỗ trợ file .docx. Hãy lưu file dưới định dạng .docx.")

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File quá lớn ({len(file_bytes) / 1024 / 1024:.1f} MB). "
            f"Tối đa {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f} MB."
        )

    result = parse_docx(file_bytes)

    duplicates = find_existing_fingerprints(db, result.questions, subject_id)
    # Lọc bỏ câu trùng khỏi danh sách sẽ import
    unique_questions = [q for q in result.questions if content_fingerprint(q.content) not in duplicates]

    _purge_expired_previews()
    token = _new_token()
    _preview_store[token] = {
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=PREVIEW_TTL_MINUTES),
        "subject_id": subject_id,
        "questions": unique_questions,
        "duplicate_count": len(duplicates),
        "filename": filename,
    }

    return (
        token,
        unique_questions,
        result.errors,
        len(duplicates),
        result.total_rows,
        len(unique_questions),
        result.format_used,
        len(result.questions),
    )


def get_preview(token: str) -> Optional[dict]:
    _purge_expired_previews()
    return _preview_store.get(token)


def commit_import(db: Session, token: str, subject_id: int) -> Tuple[int, int]:
    """Ghi các câu hỏi đã đọc thử vào CSDL.

    Kiểm tra lại trùng lặp ngay lúc ghi vì có thể đã có câu mới được thêm từ
    lúc đọc thử (ví dụ GV mở 2 cửa sổ).
    """
    payload = get_preview(token)
    if payload is None:
        raise ValueError("Phiên đọc thử đã hết hạn hoặc không tồn tại. Hãy tải lại file.")

    questions: List[ParsedQuestion] = payload["questions"]
    # Kiểm tra trùng trong CÙNG MÔN đích (xem find_existing_fingerprints).
    # Dùng subject_id của tham số (môn GV chọn lúc bấm Import) chứ không phải
    # của preview, vì GV có thể đổi môn giữa bước đọc thử và bước ghi.
    existing = {
        content_fingerprint(c)
        for (c,) in db.query(Question.content).filter(
            Question.subject_id == subject_id
        ).all()
    }

    imported = 0
    # Số câu đã bị loại ở bước đọc thử + số câu mới bị trùng phát sinh giữa
    # lúc đọc thử và lúc ghi (ví dụ GV mở 2 cửa sổ cùng lúc).
    skipped = payload["duplicate_count"]

    try:
        for q in questions:
            if content_fingerprint(q.content) in existing:
                skipped += 1
                continue

            question = Question(
                content=q.content,
                type=q.type,
                difficulty=q.difficulty,
                subject_id=subject_id,
            )
            db.add(question)
            db.flush()

            for i, opt in enumerate(q.options):
                db.add(
                    QuestionOption(
                        question_id=question.id,
                        content=opt.content,
                        is_correct=opt.is_correct,
                        order_index=i,
                    )
                )
            existing.add(content_fingerprint(q.content))
            imported += 1

        db.commit()
    except Exception:
        db.rollback()
        logger.error("Lỗi khi ghi câu hỏi từ file", exc_info=True)
        raise

    # Xoá phiên đọc thử để không import nhầm hai lần
    _preview_store.pop(token, None)

    return imported, skipped


def build_template_docx() -> bytes:
    """Sinh file .docx mẫu để giảng viên tải về và điền theo đúng định dạng."""
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("MẪU IMPORT CÂU HỎI — HỆ THỐNG THI TRẮC NGHIỆM")
    run.bold = True
    run.font.size = Pt(14)

    note = doc.add_paragraph()
    note_run = note.add_run(
        "Điền câu hỏi vào BẢNG bên dưới. Cột bắt buộc: Câu hỏi và Đáp án. "
        "Xoá các dòng hướng dẫn trước khi tải lên hệ thống."
    )
    note_run.italic = True
    note_run.font.size = Pt(9)

    table = doc.add_table(rows=3, cols=6)
    table.style = "Table Grid"

    headers = ["Câu hỏi", "A", "B", "C", "D", "Đáp án"]
    for i, text in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = text
        for paragraph in cell.paragraphs:
            for r in paragraph.runs:
                r.bold = True

    # Cột "Độ khó" và "Loại" là tuỳ chọn — thêm vào như gợi ý ở dạng văn bản.
    sample = [
        "Tiến trình nào đang chờ một sự kiện I/O hoàn thành?",
        "Ready (Sẵn sàng)", "Running (Đang chạy)",
        "Waiting (Chờ)", "Terminated (Kết thúc)", "C",
    ]
    for i, text in enumerate(sample):
        table.rows[1].cells[i].text = text

    hint = [
        "(Câu nhập đáp án tự do — để trống A, B, C, D)", "Đúng", "Sai", "Sai", "Sai", "A",
    ]
    for i, text in enumerate(hint):
        table.rows[2].cells[i].text = text

    doc.add_paragraph()
    p2 = doc.add_paragraph()
    r2 = p2.add_run("CÁCH ĐỌC ĐÁP ÁN (dùng được nhiều cách viết):")
    r2.bold = True
    for example in [
        "Một đáp án:        C",
        "Nhiều đáp án:      A,C     hoặc     AC     hoặc     A C",
        "Theo số thứ tự:   1,3",
    ]:
        doc.add_paragraph(f"  {example}")

    p3 = doc.add_paragraph()
    r3 = p3.add_run(
        "Hệ thống tự suy ra loại câu hỏi: 1 đáp án đúng = chọn một, "
        "từ 2 đáp án đúng trở lên = chọn nhiều."
    )
    r3.font.size = Pt(9)

    p4 = doc.add_paragraph()
    r4 = p4.add_run(
        "Ngoài ra bạn cũng có thể dùng định dạng văn bản phân tách nếu không muốn làm bảng:"
    )
    r4.font.size = Pt(9)
    for line in [
        "Câu 1: Tiến trình nào đang chờ một sự kiện I/O hoàn thành?",
        "A. Ready (Sẵn sàng)",
        "B. Running (Đang chạy)",
        "C. Waiting (Chờ)",
        "Đáp án: C",
    ]:
        para = doc.add_paragraph(line)
        for r in para.runs:
            r.font.size = Pt(9)
            r.font.name = "Consolas"

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
