"""Parse câu hỏi từ file .docx để nhập hàng loạt vào ngân hàng câu hỏi.

Hỗ trợ HAI định dạng, tự động nhận diện theo thứ tự:

1. **BẢNG WORD** (độ tin cậy cao) — mỗi dòng là một câu hỏi, các cột là
   nội dung / lựa chọn / đáp án. Bảng tự chứa ranh giới nên ít phải đoán.

2. **VĂN BẢN PHÂN TÁCH** — dùng khi GV gõ trực tiếp trong Word::

       Câu 1: Tiến trình nào đang chờ I/O?
       A. Ready
       B. Running
       C. Waiting
       Đáp án: C

Nguyên tắc thiết kế:
- **Không ném lỗi khi parse.** Câu hỏi hỏng được báo về dạng danh sách lỗi kèm số
  dòng để GV tự sửa — bỏ qua câu hỏi lỗi chứ không làm hỏng cả file.
- **Tự suy ra loại câu hỏi** từ số đáp án đúng, không bắt GV phải khai.
- **Chuẩn hoá đáp án** về chữ cái A/B/C/D để chịu được nhiều cách viết.
"""

import hashlib
import io
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from docx import Document

logger = logging.getLogger(__name__)

# --- Hằng số nhận diện ---
OPTION_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H"]
MAX_QUESTION_LENGTH = 4000
MAX_OPTION_LENGTH = 1000

# Từ khoá nhận diện cột trong bảng Word (không phân biệt hoa thường)
HEADER_QUESTION_KEYWORDS = ("câu hỏi", "cau hoi", "nội dung", "noi dung", "question", "nội dung câu")
HEADER_ANSWER_KEYWORDS = ("đáp án", "dap an", "answer", "đáp án đúng", "key")
HEADER_DIFFICULTY_KEYWORDS = ("độ khó", "do kho", "mức độ", "difficulty", "khó")
HEADER_TYPE_KEYWORDS = ("loại", "loai", "type", "dạng")

# Mẫu câu hỏi trong văn bản phân tách: "Câu 1:", "Câu 1.", "1.", "1)", "1:"
RE_QUESTION_START = re.compile(
    r"^\s*(?:câu\s*)?(\d+)\s*[.):]\s*(.+)$",
    re.IGNORECASE,
)
# Mẫu lựa chọn: "A.", "A)", "A:", "A -", hoặc chỉ "A." đứng đầu dòng
RE_OPTION_START = re.compile(r"^\s*([A-Ha-h])\s*[.):\-]\s*(.+)$", re.IGNORECASE)
# Mẫu dòng đáp án: "Đáp án: A,C" / "Answer: AC" / "ĐÁP ÁN - B"
RE_ANSWER_LINE = re.compile(
    r"^\s*(?:đáp\s*án\s*đúng\s*:?|đáp\s*án\s*:?|answer\s*:?|key\s*:?)\s*[-–]?\s*(.+)$",
    re.IGNORECASE,
)


@dataclass
class ParsedOption:
    content: str
    is_correct: bool = False


@dataclass
class ParsedQuestion:
    content: str
    type: str = "SINGLE_CHOICE"
    difficulty: str = "MEDIUM"
    options: List[ParsedOption] = field(default_factory=list)
    source_row: Optional[int] = None


@dataclass
class ParseError:
    row: Optional[int]
    reason: str
    snippet: str = ""


@dataclass
class ParseResult:
    questions: List[ParsedQuestion] = field(default_factory=list)
    errors: List[ParseError] = field(default_factory=list)
    format_used: str = "unknown"
    total_rows: int = 0


# ---------------------------------------------------------------- chuẩn hoá

def normalize_text(text: str) -> str:
    """Chuẩn hoá khoảng trắng + ký tự không ngắt được thành space thường."""
    if not text:
        return ""
    text = text.replace(" ", " ").replace("", "")
    text = re.sub(r"[\t\r\n]+", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def content_fingerprint(content: str) -> str:
    """Khoá so trùng: bỏ khoảng trắng, không phân biệt hoa thường, bỏ dấu câu."""
    plain = normalize_text(content).lower()
    plain = re.sub(r"[^\w\s]", "", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def parse_answer_letters(raw: str, option_count: int) -> Tuple[List[int], Optional[str]]:
    """Chuyển chuỗi đáp án thô thành danh sách chỉ số option (0-based).

    Chấp nhận: ``C`` · ``A,C`` · ``AC`` · ``A C`` · ``1,3`` · ``a) c)`` · ``A.B.C``
    Trả về (danh sách chỉ số hợp lệ, lý do lỗi nếu có).
    """
    if not raw or not raw.strip():
        return [], "Thiếu đáp án"

    original = raw.strip()
    # Bỏ nhãn dạng "A)" "a." trước khi tách
    cleaned = re.sub(r"(?i)([a-h])\s*[.):\-]", r"\1", raw)
    cleaned = re.sub(r"[;,/&|+]", ",", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)

    # Ưu tiên tách theo dấu phẩy trước — an toàn hơn với chuỗi liền chữ cái.
    # Xét "AC" là [A, C] nhưng chỉ khi chuỗi đó dài <= số lựa chọn; nếu dài hơn
    # thì chắc chắn là nhãn dạng "A)" bị dính liền, tách từng chữ sẽ hỏng.
    if "," in cleaned:
        parts = [p for p in cleaned.split(",") if p]
    elif re.fullmatch(r"[A-Ha-h]+", cleaned) and len(cleaned) <= option_count:
        parts = list(cleaned)
    else:
        parts = [p for p in re.split(r"[,\s]+", cleaned) if p]

    letters = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if re.fullmatch(r"[A-Ha-h]", p):
            letters.append(p.upper())
        elif re.fullmatch(r"\d+", p):
            n = int(p)
            if not (1 <= n <= option_count):
                return [], (
                    f"Đáp án '{original}' vượt quá số lựa chọn ({option_count})"
                )
            letters.append(OPTION_LETTERS[n - 1])
        else:
            return [], (
                f"Không hiểu đáp án '{original}'. "
                f"Cách viết hợp lệ: A, A,C, AC hoặc 1,3."
            )

    # Bỏ trùng, giữ thứ tự
    seen, unique = set(), []
    for ch in letters:
        if ch not in seen:
            seen.add(ch)
            unique.append(ch)

    if not unique:
        return [], "Thiếu đáp án"

    invalid = [c for c in unique if OPTION_LETTERS.index(c) >= option_count]
    if invalid:
        return [], (
            f"Đáp án {', '.join(invalid)} vượt quá số lựa chọn ({option_count})"
        )

    return [OPTION_LETTERS.index(c) for c in unique], None


def infer_type(correct_indices: List[int]) -> str:
    """Suy ra loại câu hỏi từ số đáp án đúng."""
    if len(correct_indices) == 0:
        return "FILL_BLANK"
    if len(correct_indices) == 1:
        return "SINGLE_CHOICE"
    return "MULTI_CHOICE"


def normalize_difficulty(raw: str) -> str:
    value = normalize_text(raw).upper()
    mapping = {
        "EASY": "EASY", "DỄ": "EASY", "DE": "EASY", "KHO": "HARD",
        "HARD": "HARD", "KHÓ": "HARD", "TRUNG BINH": "MEDIUM",
        "TRUNG BÌNH": "MEDIUM", "MEDIUM": "MEDIUM", "TB": "MEDIUM",
    }
    return mapping.get(value, "MEDIUM")


# ------------------------------------------------------- parser: bảng Word

def _classify_header_cell(text: str) -> Optional[str]:
    value = normalize_text(text).lower()
    if not value:
        return None
    if any(k in value for k in HEADER_ANSWER_KEYWORDS):
        return "answer"
    if any(k in value for k in HEADER_DIFFICULTY_KEYWORDS):
        return "difficulty"
    if any(k in value for k in HEADER_TYPE_KEYWORDS):
        return "type"
    if any(k in value for k in HEADER_QUESTION_KEYWORDS):
        return "question"
    # Cột chứa đúng một chữ cái A-H đơn lẻ → cột lựa chọn
    if re.fullmatch(r"[A-Ha-h]\.?", value):
        return "option"
    return None


def _looks_like_header(row_cells: List[str]) -> bool:
    kinds = [_classify_header_cell(c) for c in row_cells]
    return "question" in kinds and "answer" in kinds


def parse_table(doc) -> ParseResult:
    """Parse dạng bảng Word."""
    result = ParseResult(format_used="table")

    table = doc.tables[0]
    rows = [[cell.text for cell in row.cells] for row in table.rows]
    if not rows:
        return result

    header_row = 0
    if not _looks_like_header(rows[0]):
        # Không có dòng tiêu đề → tự đoán: cột 0 = câu hỏi, các cột 1..n-1 = lựa chọn,
        # cột cuối = đáp án.
        header_row = -1
        col_map = {"question": 0, "answer": len(rows[0]) - 1}
        option_cols = list(range(1, len(rows[0]) - 1))
    else:
        col_map, option_cols = {}, []
        for idx, cell in enumerate(rows[0]):
            kind = _classify_header_cell(cell)
            if kind == "option":
                option_cols.append(idx)
            elif kind:
                col_map[kind] = idx

        if "question" not in col_map or "answer" not in col_map:
            return ParseResult(
                format_used="table",
                errors=[
                    ParseError(
                        row=1,
                        reason="Dòng tiêu đề thiếu cột 'Câu hỏi' hoặc 'Đáp án'",
                        snippet=" | ".join(normalize_text(c) for c in rows[0]),
                    )
                ],
            )

    data_rows = rows[1:] if header_row == 0 else rows
    result.total_rows = len(data_rows)

    for offset, cells in enumerate(data_rows):
        row_no = offset + (2 if header_row == 0 else 1)

        def cell_of(kind):
            idx = col_map.get(kind)
            return normalize_text(cells[idx]) if idx is not None and idx < len(cells) else ""

        content = cell_of("question")
        if not content:
            result.errors.append(ParseError(row=row_no, reason="Nội dung câu hỏi rỗng"))
            continue
        if len(content) > MAX_QUESTION_LENGTH:
            result.errors.append(
                ParseError(row=row_no, reason="Nội dung câu hỏi quá dài (trên 4000 ký tự)")
            )
            continue

        options: List[ParsedOption] = []
        for col in option_cols:
            if col >= len(cells):
                continue
            text = normalize_text(cells[col])
            if text:
                options.append(ParsedOption(content=text[:MAX_OPTION_LENGTH]))

        raw_answer = cell_of("answer")
        # Đánh dấu đúng trước, để biết số lựa chọn hợp lệ
        indices, error = parse_answer_letters(raw_answer, len(options))
        if error:
            result.errors.append(
                ParseError(row=row_no, reason=error, snippet=content[:60])
            )
            continue

        for i in indices:
            options[i].is_correct = True

        qtype = normalize_text(cell_of("type")).upper()
        if qtype not in ("SINGLE_CHOICE", "MULTI_CHOICE", "FILL_BLANK"):
            qtype = infer_type(indices)

        result.questions.append(
            ParsedQuestion(
                content=content,
                type=qtype,
                difficulty=normalize_difficulty(cell_of("difficulty")),
                options=options,
                source_row=row_no,
            )
        )

    return result


# ------------------------------------------ parser: văn bản phân tách

def parse_text(doc) -> ParseResult:
    """Parse dạng văn bản phân tách (Câu N: / A. / Đáp án:)."""
    result = ParseResult(format_used="text")

    lines = [p.text for p in doc.paragraphs]
    lines = [l for l in lines if normalize_text(l)]

    if not lines:
        return result

    questions: List[ParsedQuestion] = []
    errors: List[ParseError] = []
    current: Optional[dict] = None

    def flush():
        nonlocal current
        if current is None:
            return
        row_no = current["row"]
        content = current["content"]
        options = current["options"]
        raw_answer = current["answer"]

        if not content:
            errors.append(ParseError(row=row_no, reason="Nội dung câu hỏi rỗng"))
            current = None
            return
        if len(content) > MAX_QUESTION_LENGTH:
            errors.append(
                ParseError(row=row_no, reason="Nội dung câu hỏi quá dài (trên 4000 ký tự)")
            )
            current = None
            return
        if not options:
            # Câu nhập đáp án tự do — không cần đáp án đúng
            questions.append(
                ParsedQuestion(
                    content=content, type="FILL_BLANK",
                    difficulty="MEDIUM", options=[], source_row=row_no,
                )
            )
            current = None
            return

        indices, error = parse_answer_letters(raw_answer, len(options))
        if error:
            errors.append(ParseError(row=row_no, reason=error, snippet=content[:60]))
            current = None
            return

        for i in indices:
            options[i].is_correct = True

        questions.append(
            ParsedQuestion(
                content=content,
                type=infer_type(indices),
                difficulty="MEDIUM",
                options=options,
                source_row=row_no,
            )
        )
        current = None

    for idx, raw in enumerate(lines):
        line_no = idx + 1
        text = normalize_text(raw)
        if not text:
            continue

        answer_match = RE_ANSWER_LINE.match(text)
        if answer_match and current is not None:
            current["answer"] = answer_match.group(1)
            continue

        option_match = RE_OPTION_START.match(text)
        # Dòng lựa chọn chỉ hợp lệ khi đang có câu hỏi đang mở
        if option_match and current is not None:
            current["options"].append(
                ParsedOption(content=normalize_text(option_match.group(2))[:MAX_OPTION_LENGTH])
            )
            continue

        question_match = RE_QUESTION_START.match(text)
        # "Câu 1: ..." hoặc "1." — luôn mở câu hỏi mới
        starts_new = bool(question_match)
        # Dòng đầu tiên của file, chưa có câu hỏi nào đang mở -> coi là câu hỏi.
        # Đây là trường hợp GV không đánh số câu.
        if not starts_new and current is None:
            starts_new = True

        if starts_new:
            flush()
            content = question_match.group(2) if question_match else text
            current = {
                "row": line_no,
                "content": normalize_text(content),
                "options": [],
                "answer": "",
            }
            continue

        # Dòng nối tiếp không có nhãn -> nối vào nội dung câu hỏi đang dở
        if current is not None and not current["options"]:
            current["content"] = normalize_text(f"{current['content']} {text}")

    flush()

    result.questions = questions
    result.errors = errors
    result.total_rows = len(questions) + len(errors)
    return result


# -------------------------------------------------------------- entrypoint

def parse_docx(file_bytes: bytes) -> ParseResult:
    """Parse file .docx, tự nhận diện định dạng.

    Không ném lỗi về dù file hỏng — trả về ParseResult rỗng kèm lỗi giải thích.
    """
    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as exc:
        logger.warning("Không đọc được file .docx: %s", exc)
        return ParseResult(
            errors=[
                ParseError(
                    row=None,
                    reason="Không đọc được file. Hãy chắc chắn đây là file .docx "
                           "(không phải .doc cũ hoặc .pdf).",
                )
            ]
        )

    # Ưu tiên bảng nếu có — độ tin cậy cao hơn văn bản phân tách
    if doc.tables:
        table_result = parse_table(doc)
        if table_result.questions or table_result.errors:
            return table_result

    return parse_text(doc)
