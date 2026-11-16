"""Cửa sổ thi: chứa QWebEngineView, các guard, và vòng đời phiên thi.

Trách nhiệm:
* nạp trang thi vào `QWebEngineView`
* gắn/bỏ guard theo `security_policy` do server trả về
* giữ kết nối socket (heartbeat) và báo vi phạm lên server
* phản ứng với `force_submit` từ giám sát

Không phản ứng trực tiếp với vi phạm bằng cách phạt thí sinh — server là nơi
duy nhất quyết định tự nộp bài.
"""

from __future__ import annotations

import asyncio
import logging

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineScript,
    QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow

from ..api.heartbeat import ExamSocket
from ..config import ClientConfig
from ..constants import (
    ATTESTATION_REFRESH_SECONDS,
    CLIENT_TYPE,
    CLIENT_VERSION,
    HEADER_ATTESTATION,
    HEADER_CLIENT_TYPE,
    HEADER_CLIENT_VERSION,
    HEADER_DEVICE_FINGERPRINT,
    RESULTS_PATH_SUFFIX,
    VIOLATION_TAB_SWITCH,
)
from ..guards.base import BaseGuard
from .blocked_overlay import BlockedOverlay
from .request_interceptor import ClientIdentityInterceptor
from .warning_overlay import WarningOverlay
from .web_page import GuardedWebEnginePage
from ..guards.clipboard_guard import ClipboardGuard
from ..guards.devtools_guard import DevToolsGuard
from ..guards.download_guard import DownloadGuard
from ..guards.keyboard_guard import KeyboardGuard
from ..guards.kiosk_guard import KioskGuard
from ..guards.navigation_guard import NavigationGuard
from ..guards.session_guard import SessionGuard
from ..osint.platform import create_adapter

logger = logging.getLogger(__name__)


class ExamWindow(QMainWindow):
    def __init__(self, api, user: dict, room_code: str, config: ClientConfig, parent=None):
        super().__init__(parent)
        self._api = api
        self._user = user
        self._room_code = room_code
        self._config = config

        self._page = None
        self._os = None
        self._os_report: dict = {}
        self._blocked = False
        self._blocked_overlay = None
        self._device_key = None
        self._attested = False
        self._device_id: str | None = None
        self._state: dict | None = None
        self._socket: ExamSocket | None = None
        self._guards: list[BaseGuard] = []
        self._session_token: str | None = None
        self._ever_fullscreen = False
        self._attest_timer = None
        self._attest_inflight = False
        # Lưu event loop của qasync ngay lúc tạo cửa sổ: `_on_time_expired`
        # chạy trong slot QTimer (đồng bộ) nên cần loop này để đẩy coroutine
        # nộp bài vào. Lưu sớm vì lúc đóng cửa sổ loop có thể đã ngừng.
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        self.setWindowTitle(f"Phòng thi {room_code}")
        self._build_view()
        self._build_os_adapter()
        self._build_guards()
        self.show()

    # ------------------------------------------------------------------ view

    def _build_view(self) -> None:
        # Profile tạm (off-the-record): KHÔNG ghi cache/cookie/token xuống đĩa.
        # Xem _install_bootstrap_script() để hiểu vì sao không dùng profile có tên.
        self._profile = QWebEngineProfile()
        self._profile.setHttpCacheType(QWebEngineProfile.NoCache)

        # Gắn định danh client cho request do TRANG WEB phát ra. Thiếu bước này
        # thì server coi phiên đã xác thực SEB là web thường -> trả
        # `restricted_mode = true` và cộng oan UNAUTHORIZED_CLIENT.
        self._interceptor = ClientIdentityInterceptor(
            header_provider=self._client_headers,
            allowed_origins=self._config.allowed_origins,
            parent=self._profile,
        )
        self._profile.setUrlRequestInterceptor(self._interceptor)

        # lambda để tra cứu `self._report_violation` tại thời điểm gọi. Truyền
        # thẳng bound method sẽ khóa cứng vào hàm cũ, khiến các guard thay
        # reporter sau này không còn được gọi.
        page = GuardedWebEnginePage(
            self._profile, self, reporter=lambda t, d: self._report_violation(t, d)
        )
        self._page = page
        page.settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
        page.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
        page.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        page.settings().setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, False)
        page.settings().setAttribute(QWebEngineSettings.PluginsEnabled, False)
        page.settings().setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)

        # Trang web thi tự gọi `document.documentElement.requestFullscreen()`
        # (hook useFullscreenLock). Không nối signal này thì lời hứa JS KHÔNG
        # BAO GIỜ settle: nút "Bắt đầu thi" treo, thí sinh không vào được phòng.
        page.fullScreenRequested.connect(self._on_fullscreen_requested)

        # Biết khi nào thí sinh đã nộp xong để mở khoá kiosk — nếu không họ bị
        # kẹt trong cửa sổ không đóng được ở trang kết quả.
        page.urlChanged.connect(self._on_url_changed)

        self.web_view = QWebEngineView(page)
        self.setCentralWidget(self.web_view)

    def _client_headers(self) -> dict[str, str]:
        """Header định danh, đọc tại thời điểm request (token có TTL 5 phút)."""
        headers = {
            HEADER_CLIENT_TYPE: CLIENT_TYPE,
            HEADER_CLIENT_VERSION: CLIENT_VERSION,
        }
        token = self._api.attestation_token
        if token:
            headers[HEADER_ATTESTATION] = token
        fingerprint = self._api.device_fingerprint
        if fingerprint:
            headers[HEADER_DEVICE_FINGERPRINT] = fingerprint
        return headers

    def _on_fullscreen_requested(self, request) -> None:
        """Chấp nhận yêu cầu fullscreen từ trang và áp lên cửa sổ Qt."""
        if request.toggleOn():
            request.accept()
            self.showFullScreen()
            self._ever_fullscreen = True
            logger.info("Trang yeu cau fullscreen -> da bat")
        else:
            request.accept()
            # KioskGuard đang giữ fullscreen; chỉ thoát khi phiên đã kết thúc.
            if getattr(self, "_blocked", False):
                self.showNormal()
            logger.info("Trang yeu cau thoat fullscreen (bi bo qua khi dang thi)")

    def _on_url_changed(self, url) -> None:
        """Phiên kết thúc khi web app chuyển sang trang kết quả.

        Web app điều hướng sang `/exam/results` sau khi nộp thành công. Client
        không có kênh nào khác để biết việc này (`submit` là request của trang),
        nên đây là tín hiệu duy nhất. Không bắt thì thí sinh đứng ở trang kết
        quả trong cửa sổ kiosk không đóng được.
        """
        if self._blocked:
            return
        path = url.path() if hasattr(url, "path") else ""
        if path.rstrip("/").endswith(RESULTS_PATH_SUFFIX):
            logger.info("Web app da nop bai -> ket thuc phien, mo khoa cua so")
            self._show_blocked("Bạn đã nộp bài. Có thể đóng cửa sổ này.")

    def _build_os_adapter(self) -> None:
        """Tạo adapter hệ điều hành đúng một lần và chia sẻ cho các guard.

        Adapter phải là MỘT thể hiện duy nhất: `RegisterHotKey` của Windows hay
        listener của clipboard đều là tài nguyên hệ thống, tạo nhiều bản sẽ đăng
        ký trùng và chặn nhầm.
        """
        self._os = create_adapter()
        self._os_report = self._os_capability_report()
        logger.info("OS adapter: %s", self._os.describe())
        for name, reason in self._os_report["unsupported"].items():
            logger.warning("KHONG ho tro %s — %s", name, reason)

    def _os_capability_report(self) -> dict:
        from ..osint.capability_matrix import unsupported as _unsupported
        from ..osint.platform import detect_platform

        key = detect_platform()
        return {"platform": key, "unsupported": _unsupported(key)}

    def _build_guards(self) -> None:
        self._navigation_guard = NavigationGuard(
            self, self._config.allowed_origins, reporter=self._report_violation
        )
        self._keyboard_guard = KeyboardGuard(self, reporter=self._report_violation)
        self._devtools_guard = DevToolsGuard(self, reporter=self._report_violation)
        self._clipboard_guard = ClipboardGuard(self, reporter=self._report_violation, os_adapter=self._os)
        self._download_guard = DownloadGuard(self, reporter=self._report_violation)
        self._kiosk_guard = KioskGuard(self, reporter=self._report_violation, os_adapter=self._os)
        self._session_guard = SessionGuard(
            self,
            on_expired=self._on_time_expired,
            os_adapter=self._os,
            on_window_switch=self._on_window_switch,
        )
        self._guards = [
            self._navigation_guard,
            self._keyboard_guard,
            self._devtools_guard,
            self._clipboard_guard,
            self._download_guard,
            self._kiosk_guard,
            self._session_guard,
        ]

    async def _attest(self) -> None:
        """Chạy challenge-response Ed25519 trước khi vào phòng."""
        from ..api.attestation import ClientAttestor
        from ..osint.keystore import load_or_create

        self._device_key = load_or_create(self._config.key_dir)
        logger.info(
            "Thiet bi %s (weak_key_storage=%s)",
            self._device_key.device_id,
            self._device_key.weak_storage,
        )

        result = await ClientAttestor(self._api, self._device_key).attest()
        self._attested = result.attested
        if result.device_id:
            self._device_id = result.device_id

    # -------------------------------------------------------------- lifecycle

    async def start_exam(self) -> bool:
        """Xác thực client → vào phòng → mở socket → nạp trang. Trả False nếu hỏng."""
        try:
            await self._attest()
        except Exception as exc:  # noqa: BLE001
            logger.error("Khong xac thuc duoc client: %s", exc)
            self._set_error(f"Không xác thực được thiết bị: {exc}")
            return False

        if not self._attested:
            # Vẫn cho thi nếu GV chưa bắt buộc SEB — server tự quyết định có
            # mở `restricted_mode` hay không. Client chỉ KHÔNG được giả vờ đã
            # xác thực (Quy tắc #4).
            logger.warning("Khong xac thuc duoc client, van cho vao phong")

        try:
            self._state = await self._api.join_exam(self._room_code)
        except Exception as exc:  # noqa: BLE001 - cửa sổ phải sống sót để báo lỗi
            logger.error("Khong vao duoc phong %s: %s", self._room_code, exc)
            self._set_error(str(exc))
            return False

        self._session_token = self._state["session_token"]
        # Mốc hết giờ do SERVER quyết định — không tự cộng từ đồng hồ máy thí sinh.
        self._session_guard.set_deadline(self._state.get("remaining_seconds"))

        try:
            self._socket = ExamSocket(
                backend_url=self._config.backend_url,
                room_code=self._room_code,
                session_token=self._session_token,
                access_token=self._api.access_token or "",
                interval_seconds=self._config.heartbeat_interval,
                on_force_submit=self._on_force_submit,
            )
            await self._socket.connect_and_join()
        except Exception as exc:  # noqa: BLE001
            logger.error("Khong ket noi duoc socket: %s", exc)
            self._set_error(f"Không kết nối được phòng thi: {exc}")
            return False

        for guard in self._guards:
            guard.install()

        self.load_exam_page()
        self._start_attestation_refresh()
        logger.info("Bat dau thi: %s", self._state.get("exam_title"))
        return True

    def _start_attestation_refresh(self) -> None:
        """Attest lại định kỳ trong suốt phiên thi.

        Attestation token sống 5 phút, còn ca thi có thể dài 45-120 phút. Nếu
        chỉ attest một lần lúc join, mọi request do trang web phát ra sau phút
        thứ 5 sẽ mang token hết hạn -> server coi là web thường -> nếu thí sinh
        F5 (join lại) họ bị đẩy sang `restricted_mode` giữa kỳ thi.

        Chạy bằng `QTimer` (không phải coroutine) vì phải sống suốt vòng đời
        cửa sổ và không được chặn Qt event loop.
        """
        from PySide6.QtCore import QTimer

        self._attest_timer = QTimer(self)
        self._attest_timer.setInterval(ATTESTATION_REFRESH_SECONDS * 1000)
        self._attest_timer.timeout.connect(self._refresh_attestation)
        self._attest_timer.start()

    def _refresh_attestation(self) -> None:
        """Attest lại trên event loop qasync — không await trong slot Qt."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        if getattr(self, "_attest_inflight", False):
            return
        self._attest_inflight = True

        async def _run() -> None:
            try:
                from ..api.attestation import ClientAttestor

                result = await ClientAttestor(self._api, self._device_key).attest()
                if result.attested:
                    logger.info("Attest lai thanh cong")
                else:
                    logger.warning("Attest lai that bai: %s", result.reason)
            except Exception as exc:  # noqa: BLE001 - không được làm sập phiên thi
                logger.warning("Loi khi attest lai: %s", exc)
            finally:
                self._attest_inflight = False

        try:
            asyncio.run_coroutine_threadsafe(_run(), loop)
        except RuntimeError as exc:
            self._attest_inflight = False
            logger.warning("Khong len lich duoc attest lai: %s", exc)

    def load_exam_page(self) -> None:
        if not self._session_token:
            return
        self._install_bootstrap_script()
        # URL lấy từ cấu hình (`SEB_EXAM_URL_TEMPLATE`), không hardcode. Mã phòng
        # được quote trong config nên không thể chèn ký tự lạ vào URL.
        self.web_view.load(QUrl(self._config.build_exam_url(self._room_code)))

    def _install_bootstrap_script(self) -> None:
        """Tiêm token vào web app trước khi script của nó chạy.

        Web app là React + Zustand: store đọc `localStorage.access_token` và
        `localStorage.user` LÚC KHỞI TẠO MODULE. Nếu tiêm sau, `ProtectedRoute`
        đã kịp kết luận là chưa đăng nhập và chuyển hướng về `/login`.

        Vì sao dùng profile tạm thay vì profile có tên: tiêm token vào
        localStorage của một profile *lâu dài* nghĩa là access token nằm trên
        đĩa sau khi client đóng. Profile off-the-record chỉ tồn tại trong RAM.

        Hạn chế đã biết: token vẫn đọc được bằng JavaScript trong trang. Cách
        đúng là cấp một *entry token* ngắn hạn chỉ mở được phòng thi thay vì
        access token đầy đủ — đã ghi ở docs/PLAN.md.
        """
        import json

        token = self._api.access_token
        user = self._api.user
        if not token or not user:
            logger.error("Khong co token de bootstrap trang thi")
            return

        # json.dumps xử lý dấu nháy/ký tự đặc biệt — không ghép chuỗi tay.
        source = (
            "try {"
            f"localStorage.setItem('access_token', {json.dumps(token)});"
            f"localStorage.setItem('user', {json.dumps(json.dumps(user))});"
            "} catch (e) { console.error('SEB bootstrap failed', e); }"
        )

        script = QWebEngineScript()
        script.setName("seb_bootstrap_auth")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
        script.setSourceCode(source)
        self._profile.scripts().insert(script)
        logger.info("Da tien token vao trang thi")

    def reload_exam(self) -> None:
        """Đưa trang về đúng URL thi sau khi bị điều hướng trái phép."""
        logger.info("Nap lai trang thi")
        self.load_exam_page()

    def _set_error(self, message: str) -> None:
        safe = (
            message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        self.web_view.setHtml(
            "<body style='font-family:sans-serif;padding:40px;background:#f8fafc;color:#0f172a'>"
            "<h2>Không vào được phòng thi</h2>"
            f"<p>{safe}</p><p>Vui lòng liên hệ giám thị.</p></body>"
        )

    # -------------------------------------------------------------- reporting

    def _report_violation(self, event_type: str, detail: dict) -> None:
        """Được guard gọi. Chạy đồng bộ trong Qt event loop nên phải hẹn, không await."""
        if self._socket is None:
            logger.warning("Guard bao %s nhung chua co socket", event_type)
            return
        self._socket.send_violation_soon(event_type, detail)

    def _on_force_submit(self, data: dict) -> None:
        """Server bắt buộc nộp bài (vượt ngưỡng vi phạm, đăng nhập trùng...)."""
        reason = data.get("reason") or "Phiên thi đã bị khoá."
        logger.warning("Server force_submit: %s", reason)
        self._show_blocked(reason)

    def _on_window_switch(self) -> None:
        """Thí sinh chuyển sang ứng dụng khác — phát hiện ở tầng hệ điều hành.

        Khác với `useVisibilityMonitor` của web app (chỉ thấy tab trình duyệt),
        đây là chuyển sang **ứng dụng khác hoàn toàn** — cơ chế mạnh hơn nhiều.
        """
        self._report_violation(VIOLATION_TAB_SWITCH, {"detected": "os_window_switch"})

    def _on_time_expired(self) -> None:
        """Hết giờ làm bài theo đồng hồ đếm ngược của client.

        QUAN TRỌNG: phải chủ động nộp bài từ client.

        `_show_blocked` ẩn `web_view`, nên trang React bên trong KHÔNG còn cơ
        hội gửi POST /exam-sessions/submit. Trước đây chỉ hiện thông báo "đã
        thu bài" trong khi server vẫn để phiên IN_PROGRESS và chưa chấm điểm.
        """
        logger.warning("Hết giờ — nộp bài (AUTO_TIMEOUT) rồi thông báo cho thí sinh")
        self._submit_after_timeout()
        self._show_blocked("Đã hết thời gian làm bài. Bài của bạn đã được hệ thống thu.")

    def _submit_after_timeout(self) -> None:
        """Gửi submit AUTO_TIMEOUT mà không chặn Qt event loop.

        `_on_time_expired` chạy trong slot của QTimer (đồng bộ), nên không thể
        `await` trực tiếp. Dùng `run_coroutine_threadsafe` lên loop đã lưu —
        cùng cách `ExamSocket.send_violation_soon` làm, tránh lỗi
        "Cannot enter into task ... while another task is being executed".
        """
        if not self._session_token:
            logger.error("Hết giờ nhưng chưa có session_token — không thể nộp bài")
            return

        loop = self._loop
        if loop is None or loop.is_closed():
            logger.error("Hết giờ nhưng event loop không dùng được — bỏ qua nộp bài")
            return

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._api.submit_exam(self._session_token, submit_type="AUTO_TIMEOUT"),
                loop,
            )
            future.add_done_callback(self._log_timeout_submit)
        except RuntimeError as exc:
            logger.error("Không lên lịch được nộp bài khi hết giờ: %s", exc)

    @staticmethod
    def _log_timeout_submit(future) -> None:
        try:
            future.result()
        except Exception as exc:  # noqa: BLE001 - chỉ ghi log, màn hình đã khoá
            logger.error("Nộp bài khi hết giờ thất bại: %s", exc)

    def _show_blocked(self, reason: str) -> None:
        """Dừng toàn bộ cơ chế giám sát rồi hiện màn hình chặn.

        Phải dừng guard trước: phiên đã kết thúc mà vẫn đếm vi phạm thì mọi
        thao tác sau đó của thí sinh (chuyển tab để đọc lý do, thoát client)
        đều bị ghi nhận oan.
        """
        if self._blocked:
            return
        self._blocked = True

        for guard in self._guards:
            try:
                guard.uninstall()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Loi go guard %s: %s", type(guard).__name__, exc)

        # QWebEngineView vẽ bằng native rendering, nên widget con bình thường
        # KHÔNG nổi lên trên nó — thử overlay trên view sẽ bị trang web che mất
        # (đã gặp: overlay có hiện nhưng đề thi vẫn nằm đè lên trên).
        # Vì phiên đã kết thúc nên ẩn view là hợp lý và chắc chắn đúng.
        if self.web_view is not None:
            self.web_view.setVisible(False)

        self._blocked_overlay = BlockedOverlay(reason, parent=self)
        # Đặt làm central widget để chiếm TRỌN vùng nội dung. `setGeometry` trên
        # widget con không đủ: layout của overlay tự co lại theo nội dung.
        # `setCentralWidget` sẽ xoá central widget cũ, nên web_view được giữ
        # tham chiếu riêng và dọn qua `_release_webengine`.
        self.setCentralWidget(self._blocked_overlay)
        self._blocked_overlay.show()
        logger.info("Da hien man hinh chan: %s", reason)

    # ------------------------------------------------------------ fullscreen

    def closeEvent(self, event):  # noqa: N802
        logger.info("Dong cua so thi")
        timer = getattr(self, "_attest_timer", None)
        if timer is not None:
            timer.stop()
            timer = None
        for guard in self._guards:
            try:
                guard.uninstall()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Loi go guard %s: %s", type(guard).__name__, exc)
        if self._socket:
            # Không `await`/`ensure_future` ngay trong closeEvent: nếu sự kiện này
            # xảy ra giữa một coroutine đang chạy, qasync ném RuntimeError.
            # `close_best_effort` đã lưu sẵn event loop nên an toàn ở đây.
            self._socket.close_best_effort()
        if self._blocked_overlay is not None:
            self._blocked_overlay.setParent(None)
            self._blocked_overlay = None
        # Khi đã hiện màn hình chặn thì cho phép đóng thật — nếu không người dùng
        # bị kẹt vĩnh viễn trong một cửa sổ không đóng được.
        self._kiosk_guard._allow_close = True
        self._release_webengine()
        super().closeEvent(event)

    def _release_webengine(self) -> None:
        """Huỷ view/page/profile TRƯỚC khi QApplication bị phá huỷ.

        Nếu không, QWebEngineView còn sống tới lúc trình thông dịch Python
        dọn dẹp sẽ làm segfault trong `runCleanupFunctions` (thấy rõ trong
        faulthandler: QWidget::~QWidget -> QWindow::close -> processCloseEvent).
        Đây là lỗi vòng đời đối tượng của Qt WebEngine, không phải lỗi logic.
        """
        import shiboken6

        for obj in (self.web_view, self._page):
            if obj is not None and not shiboken6.isValid(obj):
                continue
            if obj is not None:
                shiboken6.delete(obj)
        self.web_view = None
        self._page = None
