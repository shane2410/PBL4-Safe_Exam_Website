"""Test 3 lỗi tương thích web ↔ SEB Client (P0).

Mỗi test ứng với một lỗi đã xảy ra thật khi chạy web app bên trong
QWebEngineView:

1. `requestFullscreen()` không bao giờ settle -> nút "Bắt đầu thi" treo.
2. Request do trang phát ra không có header định danh -> server coi phiên đã
   xác thực SEB là web thường, trả `restricted_mode=true`.
3. Nộp bài xong web app chuyển sang `/exam/results` nhưng client không biết
   -> thí sinh kẹt trong cửa sổ kiosk.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from sebclient.ui.request_interceptor import _origin_key  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ------------------------------------------------------- origin allow-list

@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://localhost:5173/exam/room", "http://localhost:5173"),
        ("http://127.0.0.1:8000/api/x", "http://127.0.0.1:8000"),
        ("https://exam.truong.edu.vn/room", "https://exam.truong.edu.vn:443"),
        ("http://example.edu/x", "http://example.edu:80"),
        ("HTTP://Example.EDU/x", "http://example.edu:80"),
        # Không phải origin dùng được
        ("file:///etc/passwd", None),
        ("about:blank", None),
        ("data:text/html,<p>x", None),
        ("", None),
        ("not a url", None),
    ],
)
def test_origin_key(url, expected):
    assert _origin_key(url) == expected


def test_origin_key_scheme_must_match():
    """http và https là hai origin khác nhau — không được gộp."""
    assert _origin_key("http://a.b/x") != _origin_key("https://a.b/x")


# ------------------------------------------------ header injection logic

class _Headers(dict):
    pass


class _FakeRequestInfo:
    """Bắt chước QWebEngineUrlRequestInfo cho phần logic thuần."""

    def __init__(self, url: str):
        self._url = QUrl(url)
        self.headers = _Headers()

    def requestUrl(self):  # noqa: N802
        return self._url

    def setHttpHeader(self, name: bytes, value: bytes):  # noqa: N802
        self.headers[name.decode("latin-1")] = value.decode("latin-1")


def _make_interceptor(origins, headers=None):
    from sebclient.ui.request_interceptor import ClientIdentityInterceptor

    return ClientIdentityInterceptor(
        header_provider=lambda: headers if headers is not None else {"X-Client-Type": "seb"},
        allowed_origins=origins,
    )


def test_interceptor_injects_into_allowed_origin():
    interceptor = _make_interceptor(["http://localhost:5173"])
    info = _FakeRequestInfo("http://localhost:5173/api/exam-sessions/join")

    interceptor.interceptRequest(info)

    assert info.headers["X-Client-Type"] == "seb"
    assert interceptor.injected_count == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://evil.com/api/x",           # origin lạ
        "http://localhost:5173.evil.com/x",  # không được khớp tiền tố
        "http://localhost:5174/x",          # sai cổng
        "https://localhost:5173/x",         # sai scheme
    ],
)
def test_interceptor_never_leaks_token_to_foreign_origin(url):
    """Attestation token là credential — gửi kèm ra ngoài là rò rỉ."""
    interceptor = _make_interceptor(["http://localhost:5173"])
    info = _FakeRequestInfo(url)

    interceptor.interceptRequest(info)

    assert info.headers == {}
    assert interceptor.injected_count == 0


def test_interceptor_skips_empty_header_values():
    interceptor = _make_interceptor(
        ["http://localhost:5173"],
        headers={"X-Client-Type": "seb", "X-Attestation-Token": "", "X-Device-Fingerprint": None},
    )
    info = _FakeRequestInfo("http://localhost:5173/x")

    interceptor.interceptRequest(info)

    assert info.headers == {"X-Client-Type": "seb"}


def test_interceptor_reads_headers_per_request():
    """Token được làm mới sau mỗi lần attest — không được cache giá trị cũ."""
    state = {"token": "old"}
    from sebclient.ui.request_interceptor import ClientIdentityInterceptor

    interceptor = ClientIdentityInterceptor(
        header_provider=lambda: {"X-Attestation-Token": state["token"]},
        allowed_origins=["http://localhost:5173"],
    )

    first = _FakeRequestInfo("http://localhost:5173/x")
    interceptor.interceptRequest(first)
    assert first.headers["X-Attestation-Token"] == "old"

    state["token"] = "new"
    second = _FakeRequestInfo("http://localhost:5173/y")
    interceptor.interceptRequest(second)
    assert second.headers["X-Attestation-Token"] == "new"


def test_interceptor_survives_provider_exception():
    """Lỗi cung cấp header không được chặn request (trang phải tải được)."""
    from sebclient.ui.request_interceptor import ClientIdentityInterceptor

    def boom():
        raise RuntimeError("provider hỏng")

    interceptor = ClientIdentityInterceptor(header_provider=boom, allowed_origins=["http://a.b"])
    info = _FakeRequestInfo("http://a.b/x")

    interceptor.interceptRequest(info)  # không được ném

    assert info.headers == {}


# ------------------------------------------------- fullscreen request

class _FakeFullScreenRequest:
    def __init__(self, toggle_on: bool):
        self._toggle_on = toggle_on
        self.accepted = False

    def toggleOn(self):  # noqa: N802
        return self._toggle_on

    def accept(self):
        self.accepted = True


def _bare_exam_window():
    """Đối tượng tối thiểu mang state mà handler của ExamWindow cần.

    Không tạo `ExamWindow` thật: hàm khởi tạo dựng `QWebEngineView` (cần GPU/
    display thật) và `QMainWindow.__new__` bị Qt chặn. Các handler được test ở
    đây chỉ đọc state và gọi `showFullScreen/showNormal`, nên gọi hàm chưa gắn
    (unbound) trên một object thuần là đủ và cô lập đúng phần logic.
    """

    class Bare:
        pass

    window = Bare()
    window._blocked = False
    window._ever_fullscreen = False
    window._fullscreen_calls = []

    window.showFullScreen = lambda: window._fullscreen_calls.append("full")
    window.showNormal = lambda: window._fullscreen_calls.append("normal")
    return window


def _on_fullscreen_requested(window, request):
    from sebclient.ui.exam_window import ExamWindow

    return ExamWindow._on_fullscreen_requested(window, request)


def _on_url_changed(window, url):
    from sebclient.ui.exam_window import ExamWindow

    return ExamWindow._on_url_changed(window, url)


def test_fullscreen_on_is_accepted(qapp):
    window = _bare_exam_window()
    request = _FakeFullScreenRequest(True)

    _on_fullscreen_requested(window, request)

    assert request.accepted is True
    assert window._fullscreen_calls == ["full"]
    assert window._ever_fullscreen is True


def test_fullscreen_off_ignored_while_exam_running(qapp):
    """Thoát fullscreen giữa giờ thi là vi phạm — không được tự hạ cửa sổ."""
    window = _bare_exam_window()
    request = _FakeFullScreenRequest(False)

    _on_fullscreen_requested(window, request)

    assert request.accepted is True
    assert window._fullscreen_calls == []


def test_fullscreen_off_allowed_after_session_ends(qapp):
    window = _bare_exam_window()
    window._blocked = True
    request = _FakeFullScreenRequest(False)

    _on_fullscreen_requested(window, request)

    assert window._fullscreen_calls == ["normal"]


# ----------------------------------------------- results-page detection

@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://localhost:5173/exam/results", True),
        ("http://localhost:5173/exam/results/", True),
        ("http://localhost:5173/exam/results?score=8", True),
        ("http://localhost:5173/exam/room?room=A1", False),
        ("http://localhost:5173/exam/join", False),
        ("http://localhost:5173/teacher/reports", False),
    ],
)
def test_results_navigation_detected(qapp, url, expected):
    window = _bare_exam_window()
    blocked_reasons = []
    window._show_blocked = lambda reason: blocked_reasons.append(reason)

    _on_url_changed(window, QUrl(url))

    assert bool(blocked_reasons) is expected


def test_results_detection_ignored_when_already_blocked(qapp):
    """Không hiện lại màn hình chặn nhiều lần (hết giờ rồi mới điều hướng)."""
    window = _bare_exam_window()
    window._blocked = True
    blocked_reasons = []
    window._show_blocked = lambda reason: blocked_reasons.append(reason)

    _on_url_changed(window, QUrl("http://localhost:5173/exam/results"))

    assert blocked_reasons == []


def test_native_fallback_exit_button(qapp):
    from PySide6.QtWidgets import QPushButton
    from sebclient.ui.blocked_overlay import BlockedOverlay

    overlay = BlockedOverlay("SEB_REQUIRED", title="Không vào được phòng thi")
    exit_requests = []
    overlay.exit_requested.connect(lambda: exit_requests.append(True))
    button = overlay.findChild(QPushButton)
    assert button.text() == "Thoát SEB"
    button.click()
    assert exit_requests == [True]


def test_exam_window_on_window_switch_reports_violation():
    """Kiểm tra _on_window_switch gọi đúng VIOLATION_TAB_SWITCH không bị NameError."""
    from sebclient.constants import VIOLATION_TAB_SWITCH
    from sebclient.ui.exam_window import ExamWindow

    window = _bare_exam_window()
    reported = []
    window._report_violation = lambda evt, detail: reported.append((evt, detail))

    ExamWindow._on_window_switch(window)
    assert len(reported) == 1
    assert reported[0][0] == VIOLATION_TAB_SWITCH
    assert reported[0][1] == {"detected": "os_window_switch"}
