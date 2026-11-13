"""Test cho bản vá #4: dedupe import theo môn + N+1 ở danh sách đề.

Bối cảnh:
  * Trước đây `find_existing_fingerprints` / `commit_import` quét TOÀN BỘ ngân
    hàng câu hỏi, không lọc `subject_id`. Một câu cơ bản đã có ở môn A bị coi
    là trùng khi giảng viên môn B muốn thêm → không import được.
  * `ExamService.get_exams` không `joinedload`, nên N đề sinh thêm 2N query
    (số câu hỏi + môn học).

Chạy: cd backend && .venv/bin/python -m pytest tests/test_import_dedupe_and_n1.py -v
"""

import io

import pytest
from docx import Document
from sqlalchemy import event

from app.models.question import Question
from app.models.subject import Subject
from app.services.exam_service import ExamService
from app.services.import_service import content_fingerprint
from app.services.question_import_service import (
    commit_import,
    find_existing_fingerprints,
    preview_import,
)
from app.services.import_service import ParsedQuestion, ParsedOption


def _skip_attr():
    pass


def _docx_single(content: str) -> bytes:
    """File .docx đúng định dạng bảng Word: cột câu hỏi + cột lựa chọn + cột đáp án."""
    rows = [
        ["Nội dung", "A", "B", "Đáp án", "Độ khó"],
        [content, "TCP/IP", "UDP", "A", "Dễ"],
    ]
    doc = Document()
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.rows[r].cells[c].text = value
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _parsed(content: str) -> ParsedQuestion:
    return ParsedQuestion(
        content=content,
        type="SINGLE_CHOICE",
        difficulty="EASY",
        options=[ParsedOption(content="A", is_correct=True)],
    )


# --- dedupe theo môn ---

def test_fingerprint_lookup_is_scoped_to_subject(db, seeded):
    other = Subject(code="ATTT01", name="An toàn thông tin")
    db.add(other)
    db.commit()

    content = "TCP là giao thức tầng nào?"
    db.add(Question(
        content=content, type="SINGLE_CHOICE", difficulty="EASY",
        subject_id=other.id,
    ))
    db.commit()

    target = seeded["subject"]
    dupes = find_existing_fingerprints(db, [_parsed(content)], target.id)
    assert dupes == set(), "Câu ở môn khác KHÔNG được coi là trùng"

    dupes_same = find_existing_fingerprints(db, [_parsed(content)], other.id)
    assert content_fingerprint(content) in dupes_same


def test_preview_import_does_not_flag_question_from_other_subject(db, seeded):
    other = Subject(code="ATTT01", name="An toàn thông tin")
    db.add(other)
    db.commit()

    content = "TCP là giao thức tầng nào?"
    db.add(Question(
        content=content, type="SINGLE_CHOICE", difficulty="EASY",
        subject_id=other.id,
    ))
    db.commit()

    token, unique, errors, dup_count, _total, new_count, _fmt, _rows = preview_import(
        db, _docx_single(content),
        "q.docx", seeded["subject"].id,
    )
    assert dup_count == 0
    assert new_count == 1
    assert len(unique) == 1


def test_preview_import_still_detects_same_subject_duplicate(db, seeded):
    content = "TCP là giao thức tầng nào?"
    db.add(Question(
        content=content, type="SINGLE_CHOICE", difficulty="EASY",
        subject_id=seeded["subject"].id,
    ))
    db.commit()

    token, unique, errors, dup_count, _total, new_count, _fmt, _rows = preview_import(
        db, _docx_single(content),
        "q.docx", seeded["subject"].id,
    )
    assert dup_count == 1
    assert new_count == 0
    assert unique == []


def test_commit_import_allows_same_content_in_another_subject(db, seeded):
    other = Subject(code="ATTT01", name="An toàn thông tin")
    db.add(other)
    db.commit()

    content = "TCP là giao thức tầng nào?"
    db.add(Question(
        content=content, type="SINGLE_CHOICE", difficulty="EASY",
        subject_id=other.id,
    ))
    db.commit()

    token, _u, _e, _d, _t, _n, _f, _r = preview_import(
        db, _docx_single(content),
        "q.docx", seeded["subject"].id,
    )
    imported, skipped = commit_import(db, token, seeded["subject"].id)
    assert imported == 1
    assert skipped == 0

    count = db.query(Question).filter(Question.subject_id == seeded["subject"].id).count()
    # fixture `seeded` đã có sẵn 1 câu trong môn này -> import thêm 1 thành 2.
    assert count == 2


def test_commit_import_skips_same_subject_duplicate(db, seeded):
    content = "TCP là giao thức tầng nào?"
    db.add(Question(
        content=content, type="SINGLE_CHOICE", difficulty="EASY",
        subject_id=seeded["subject"].id,
    ))
    db.commit()

    # Preview với môn trống (khác) để câu lọt qua bước đọc thử,
    # rồi commit vào môn đã có câu đó -> phải bị chặn ở bước ghi.
    other = Subject(code="ATTT01", name="An toàn thông tin")
    db.add(other)
    db.commit()

    token, _u, _e, _d, _t, _n, _f, _r = preview_import(
        db, _docx_single(content),
        "q.docx", other.id,
    )
    imported, skipped = commit_import(db, token, seeded["subject"].id)
    assert imported == 0
    assert skipped == 1


# --- N+1 ---

def test_get_exams_does_not_fire_query_per_exam(db, seeded):
    # Thêm vài đề nữa để N+1 lộ rõ.
    from app.models.exam import Exam

    exam = seeded["exam"]
    for i in range(4):
        db.add(Exam(
            title=f"Đề phụ {i}", subject_id=seeded["subject"].id,
            duration_minutes=30, total_score=10, is_shuffled=False,
            max_violation_allowed=5, require_safe_browser=False,
            created_by=seeded["admin"].id,
        ))
    db.commit()

    statements = []
    engine = db.get_bind()

    def _before(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _before)
    try:
        exams = ExamService.get_exams(db)
    finally:
        event.remove(engine, "before_cursor_execute", _before)

    assert len(exams) == 5
    assert all(e.question_count == 0 for e in exams if e.id != exam.id)
    # 1 query chính cho Exam + 1 cho subject + 1 cho exam_questions (selectin)
    # Không được tăng theo số đề. Cho phép tối đa 4 để không vỡ khi đổi loader.
    assert len(statements) <= 4, f"N+1: {len(statements)} query cho 5 đề"
