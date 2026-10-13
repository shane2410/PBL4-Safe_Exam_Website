"""Test cho bộ parse câu hỏi từ file .docx.

Bao phủ cả hai định dạng (bảng Word và văn bản phân tách), các cách viết đáp án,
tự suy ra loại câu hỏi, và việc báo lỗi theo dòng thay vì làm hỏng cả file.
"""

import io

import pytest
from docx import Document

from app.services.import_service import (
    content_fingerprint,
    normalize_difficulty,
    normalize_text,
    parse_answer_letters,
    parse_docx,
)


def docx_from_table(rows):
    """Tạo file .docx chứa một bảng Word."""
    doc = Document()
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.rows[r].cells[c].text = value
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def docx_from_paragraphs(lines):
    """Tạo file .docx chứa các đoạn văn."""
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ------------------------------------------------------- chuẩn hoá đáp án

@pytest.mark.parametrize(
    "raw,count,expected",
    [
        ("C", 4, [2]),
        ("c", 4, [2]),
        ("A,C", 4, [0, 2]),
        ("AC", 4, [0, 2]),
        ("A C", 4, [0, 2]),
        ("a) c)", 4, [0, 2]),
        ("1,3", 4, [0, 2]),
        ("A, B, D", 4, [0, 1, 3]),
        # Có dấu phẩy -> tách theo dấu phẩy. "A,C" với 3 lựa chọn là [A, C]
        ("A,C", 3, [0, 2]),
        ("A,B", 2, [0, 1]),
        # Không dấu phẩy: coi là chuỗi chữ cái khi độ dài <= số lựa chọn
        ("AB", 4, [0, 1]),
    ],
)
def test_parse_answer_variants(raw, count, expected):
    indices, error = parse_answer_letters(raw, count)
    assert error is None
    assert indices == expected


@pytest.mark.parametrize("raw", ["", "   ", "Z", "9", "A,B,C,D,E"])
def test_parse_answer_invalid(raw):
    indices, error = parse_answer_letters(raw, 4)
    assert error is not None


def test_parse_answer_number_out_of_range():
    indices, error = parse_answer_letters("5", 4)
    assert error is not None
    assert "vượt quá" in error


# ---------------------------------------------------------- chuẩn hoá khác

def test_normalize_text_collapses_whitespace():
    assert normalize_text("  Câu   hỏi\n\n thứ\thai  ") == "Câu hỏi thứ hai"


def test_normalize_text_handles_nbsp():
    assert normalize_text("A B") == "A B"


def test_fingerprint_ignores_case_and_punctuation():
    a = content_fingerprint("Quá trình là gì?")
    b = content_fingerprint("  quá trình  là gì ")
    c = content_fingerprint("QUÁ TRÌNH LÀ GÌ")
    assert a == b == c


@pytest.mark.parametrize(
    "raw,expected",
    [("DỄ", "EASY"), ("easy", "EASY"), ("Khó", "HARD"), ("Trung bình", "MEDIUM"),
     ("khoá", "MEDIUM"), ("", "MEDIUM"), ("lạ", "MEDIUM")],
)
def test_normalize_difficulty(raw, expected):
    assert normalize_difficulty(raw) == expected


# ------------------------------------------------------- định dạng bảng Word

def test_parse_table_with_header():
    data = docx_from_table([
        ["Câu hỏi", "A", "B", "C", "D", "Đáp án"],
        ["Tiến trình nào chờ I/O?", "Ready", "Running", "Waiting", "Terminated", "C"],
        ["Câu nào đúng?", "Sai", "Đúng", "Sai", "Sai", "B"],
    ])
    result = parse_docx(data)

    assert result.format_used == "table"
    assert len(result.questions) == 2
    assert len(result.errors) == 0

    q1 = result.questions[0]
    assert q1.type == "SINGLE_CHOICE"
    assert [o.is_correct for o in q1.options] == [False, False, True, False]
    assert q1.source_row == 2


def test_parse_table_infers_multi_choice():
    data = docx_from_table([
        ["Câu hỏi", "A", "B", "C", "Đáp án"],
        ["Chọn các câu đúng", "đúng", "sai", "đúng", "A,C"],
    ])
    result = parse_docx(data)
    assert result.questions[0].type == "MULTI_CHOICE"
    assert [o.is_correct for o in result.questions[0].options] == [True, False, True]


def test_parse_table_without_header_row():
    """Không có dòng tiêu đề → tự đoán cột đầu = câu hỏi, cột cuối = đáp án."""
    data = docx_from_table([
        ["Câu hỏi không tiêu đề", "đúng", "sai", "B"],
        ["Câu hỏi thứ hai", "sai", "đúng", "A"],
    ])
    result = parse_docx(data)
    assert len(result.questions) == 2
    assert result.questions[0].options[1].is_correct is True


def test_parse_table_with_difficulty_column():
    data = docx_from_table([
        ["Câu hỏi", "A", "B", "Đáp án", "Độ khó"],
        ["Câu dễ", "đúng", "sai", "A", "Dễ"],
        ["Câu khó", "đúng", "sai", "A", "Khó"],
    ])
    result = parse_docx(data)
    assert result.questions[0].difficulty == "EASY"
    assert result.questions[1].difficulty == "HARD"


def test_parse_table_reports_error_row():
    data = docx_from_table([
        ["Câu hỏi", "A", "B", "Đáp án"],
        ["Câu hợp lệ", "đúng", "sai", "A"],
        ["Câu thiếu đáp án", "đúng", "sai", ""],
        ["Câu đáp án vô lý", "đúng", "sai", "A,Z"],
    ])
    result = parse_docx(data)

    assert len(result.questions) == 1
    assert len(result.errors) == 2
    # Lỗi phải chỉ đúng số dòng để GV biết sửa ở đâu
    assert {e.row for e in result.errors} == {3, 4}
    assert "Không hiểu đáp án" in result.errors[1].reason


def test_parse_table_skips_empty_content():
    data = docx_from_table([
        ["Câu hỏi", "A", "B", "Đáp án"],
        ["", "đúng", "sai", "A"],
        ["Câu thật", "đúng", "sai", "A"],
    ])
    result = parse_docx(data)
    assert len(result.questions) == 1
    assert result.errors[0].row == 2


# ------------------------------------------------- định dạng văn bản phân tách

def test_parse_text_format():
    data = docx_from_paragraphs([
        "Câu 1: Tiến trình nào đang chờ I/O?",
        "A. Ready",
        "B. Running",
        "C. Waiting",
        "Đáp án: C",
        "Câu 2: Thuật toán nào gây đói?",
        "A. RR",
        "B. SJF",
        "Đáp án: B",
    ])
    result = parse_docx(data)

    assert result.format_used == "text"
    assert len(result.questions) == 2
    assert result.questions[0].type == "SINGLE_CHOICE"
    assert [o.is_correct for o in result.questions[0].options] == [False, False, True]


def test_parse_text_multi_choice():
    data = docx_from_paragraphs([
        "Câu 1: Chọn các câu đúng về bế tắc?",
        "A. Loại trừ",
        "B. Giữ và chờ",
        "C. Không cướp",
        "Đáp án: A, B, C",
    ])
    result = parse_docx(data)
    assert result.questions[0].type == "MULTI_CHOICE"
    assert all(o.is_correct for o in result.questions[0].options)


def test_parse_text_missing_answer_reports_error():
    data = docx_from_paragraphs([
        "Câu 1: Câu không có đáp án?",
        "A. Một",
        "B. Hai",
        "Câu 2: Câu có đáp án?",
        "A. Một",
        "B. Hai",
        "Đáp án: A",
    ])
    result = parse_docx(data)

    assert len(result.questions) == 1
    assert len(result.errors) == 1
    assert result.errors[0].reason == "Thiếu đáp án"
    # Lỗi phải chỉ đúng dòng để GV biết sửa ở đâu
    assert result.errors[0].row == 1


def test_parse_text_multiline_question_continues():
    data = docx_from_paragraphs([
        "Câu 1: Một câu hỏi",
        "rất dài bị xuống dòng",
        "A. Một",
        "B. Hai",
        "Đáp án: A",
    ])
    result = parse_docx(data)
    assert "rất dài bị xuống dòng" in result.questions[0].content


def test_parse_text_question_without_numbering():
    """Câu hỏi không đánh số vẫn phải nhận diện được."""
    data = docx_from_paragraphs([
        "Tiến trình nào đang chờ một sự kiện I/O hoàn thành?",
        "A. Ready",
        "B. Running",
        "Đáp án: B",
    ])
    result = parse_docx(data)
    assert len(result.questions) == 1
    assert result.questions[0].options[1].is_correct is True


# ------------------------------------------------------------- trường hợp lỗi

def test_parse_invalid_file_returns_error_not_exception():
    result = parse_docx("đây không phải file docx".encode("utf-8"))
    assert result.questions == []
    assert len(result.errors) == 1
    assert "docx" in result.errors[0].reason.lower()


def test_parse_empty_document():
    result = parse_docx(docx_from_paragraphs([]))
    assert result.questions == []
    assert result.errors == []
