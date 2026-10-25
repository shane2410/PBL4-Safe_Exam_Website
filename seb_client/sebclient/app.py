"""Entry point của SEB Client.

Điểm mấu chốt: chạy Qt TRONG asyncio loop của `qasync`, không phải `app.exec()`.
Lý do: mọi việc mạng (HTTP, Socket.IO heartbeat) đều là async. Nếu dùng
`app.exec()`, các coroutine sẽ không bao giờ được chạy và cửa sổ đứng hình mỗi
lần heartbeat bắn — đúng lỗi mà `qasync` sinh ra để tránh.
"""

from __future__ import annotations

import asyncio
import logging
import sys

import qasync
from PySide6.QtWidgets import QApplication

from .config import load_config
from .logging_setup import setup_logging
from .ui.login_window import LoginWindow
from .api.client import ApiClient

logger = logging.getLogger(__name__)


class SebClientApp:
    """Giữ vòng đời các cửa sổ và tài nguyên dùng chung."""

    def __init__(self, qt_app: QApplication):
        self._qt_app = qt_app
        self._config = load_config()

        problems = self._config.validate()
        if problems:
            for problem in problems:
                logger.error("Cau hinh sai: %s", problem)
            raise SystemExit(1)

        self._api = ApiClient(self._config)
        self._login_window: LoginWindow | None = None
        self._exam_window = None

    def start(self) -> None:
        self._login_window = LoginWindow(self._api)
        self._login_window.login_succeeded.connect(self._on_login_succeeded)
        self._login_window.login_failed.connect(self._on_login_failed)
        self._login_window.show()

    def _on_login_succeeded(self, user: dict, room_code: str) -> None:
        logger.info("San xuat phong %s cho user=%s", room_code, user.get("username"))
        from .ui.exam_window import ExamWindow

        self._exam_window = ExamWindow(
            api=self._api, user=user, room_code=room_code, config=self._config
        )
        self._exam_window.show()
        # start_exam là coroutine (join HTTP + socket). Không await trực tiếp ở
        # đây vì hàm này chạy trong signal của Qt, không phải trong coroutine —
        # await sẽ văng RuntimeError.
        asyncio.ensure_future(self._exam_window.start_exam())

    def _on_login_failed(self, message: str) -> None:
        logger.info("Dang nhap that bai: %s", message)

    async def shutdown(self) -> None:
        """Đóng tài nguyên theo ĐÚNG thứ tự.

        Phải đóng socket và HTTP **trước**, rồi mới đóng cửa sổ. Làm ngược lại
        sẽ phá event loop của qasync: huỷ QWebEngineView rồi mới await
        `socketio.disconnect()` sẽ khiến mọi await sau đó văng
        "Event loop stopped before Future completed".
        """
        logger.info("Dang dong SEB Client")

        if self._exam_window is not None:
            socket = self._exam_window._socket
            if socket is not None:
                try:
                    await socket.disconnect()
                except Exception as exc:  # noqa: BLE001 - đang tắt
                    logger.warning("Loi khi dong socket: %s", exc)

        await self._api.close()

        for window in (self._exam_window, self._login_window):
            if window is None:
                continue
            try:
                if getattr(window, "_kiosk_guard", None) is not None:
                    window._kiosk_guard._allow_close = True
                window.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Loi khi dong cua so: %s", exc)


def main() -> int:
    config = load_config()
    log_file = setup_logging(config.log_dir, config.log_level)
    logger.info("=== %s khoi dong ===", "SEB Client")
    logger.info("Log file: %s", log_file)
    logger.info("Backend: %s", config.backend_url)
    logger.info("Exam origin: %s", config.exam_origin)
    logger.info("Allowed origins: %s", ", ".join(config.allowed_origins))

    # Năng lực thật của máy này. Phần thiếu sẽ báo lên server và cho giảng viên
    # thấy — im lặng thiếu là tạo cảm giác an toàn giả (Quy tắc #5).
    from .osint.platform import report as capability_report

    caps = capability_report()
    logger.info("Nang luc (%s): %s", caps["platform"], ", ".join(caps["capabilities"]))
    if caps["unsupported"]:
        for name, reason in caps["unsupported"].items():
            logger.warning("KHONG ho tro: %s — %s", name, reason)
    if config.headless:
        logger.warning("Chay o che do HEADLESS — khong phai lan chay that")

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("SEB Client")
    # KHÔNG tự thoát khi đóng cửa sổ cuối. Với `True`, đóng cửa sổ thi sẽ làm
    # Qt dừng event loop của qasync ngay giữa lúc một coroutine đang await —
    # mọi `await` sau đó văng "Event loop stopped before Future completed".
    # App tự quyết định lúc thoát qua `SebClientApp.shutdown()`.
    qt_app.setQuitOnLastWindowClosed(False)

    event_loop = qasync.QEventLoop(qt_app)
    asyncio.set_event_loop(event_loop)

    client_app = SebClientApp(qt_app)
    client_app.start()

    with event_loop:
        event_loop.run_forever()

    logger.info("SEB Client ket thuc")
    return 0


if __name__ == "__main__":
    sys.exit(main())