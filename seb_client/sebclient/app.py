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

# Cách mở file cấu hình `.seb`: double-click trên Windows truyền đường dẫn qua
# argv. Trên Linux/macOS cũng vậy khi file được liên kết với binary này.
CONFIG_FILE_SUFFIXES = (".seb", ".seb2")


def _config_file_from_argv(argv: list[str]) -> str | None:
    """Lấy đường dẫn file `.seb` từ argv nếu có.

    Bỏ qua argv[0]. Không dùng argparse: chỉ cần một đối số tuỳ chọn, và một
    đối số lạ không nên làm chương trình thoát với lỗi khó hiểu — bản chạy
    không có đối số phải luôn dùng chế độ thi có backend như trước.
    """
    for arg in argv[1:]:
        if arg.lower().endswith(CONFIG_FILE_SUFFIXES):
            return arg
    return None


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


def _show_fatal(message: str) -> None:
    """Báo lỗi khởi động cho người dùng thấy.

    Bản đóng gói chạy ở chế độ windowed (không console): nếu chỉ ghi log rồi
    `SystemExit` thì người dùng chỉ thấy "bấm không lên". Luôn kèm đường dẫn
    file log để kỹ thuật viên biết xem ở đâu.
    """
    logger.error("%s", message)
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            QApplication(sys.argv)
        QMessageBox.critical(None, "SEB Client không khởi động được", message)
    except Exception as exc:  # noqa: BLE001 - đang báo lỗi, không được nổ thêm
        logger.warning("Khong hien duoc hop thoai loi: %s", exc)


def _install_excepthook() -> None:
    """Chuyển exception không bắt được vào file log.

    Không console nghĩa là `sys.stderr` là None; excepthook mặc định sẽ cố ghi
    vào đó và làm mất dấu vết lỗi thay vì để lại trong log.
    """

    def _hook(exc_type, exc, tb) -> None:
        logger.critical("Loi khong bat duoc", exc_info=(exc_type, exc, tb))

    sys.excepthook = _hook


def _log_capabilities() -> None:
    """Ghi năng lực thật của máy này vào log.

    Phần thiếu phải báo ra, kể cả ở chế độ mở file cấu hình — im lặng thiếu là
    tạo cảm giác an toàn giả.
    """
    from .osint.platform import report as capability_report

    caps = capability_report()
    logger.info("Nang luc (%s): %s", caps["platform"], ", ".join(caps["capabilities"]))
    for name, reason in caps["unsupported"].items():
        logger.warning("KHONG ho tro: %s — %s", name, reason)


def main() -> int:
    config = load_config()
    log_file = setup_logging(config.log_dir, config.log_level)
    _install_excepthook()
    logger.info("=== %s khoi dong ===", "SEB Client")
    logger.info("Log file: %s", log_file)

    # Kiểm tra toàn vẹn và chống phân tích gỡ lỗi (Phase 2)
    from .integrity import enforce_anti_debug, verify_self_integrity

    try:
        verify_self_integrity()
        enforce_anti_debug()
    except SystemExit as exc:
        _show_fatal(str(exc))
        return 1

    # Chế độ "mở file cấu hình" phải được nhận diện TRƯỚC khi validate `.env`:
    # chế độ này không dùng backend, nên một `.env` thiếu khoá không được phép
    # chặn việc mở file cấu hình.
    config_file = _config_file_from_argv(sys.argv)
    if config_file:
        logger.info("Mo bang file cau hinh: %s", config_file)
        _log_capabilities()
        return _run_config_file_mode(config_file, log_file)

    logger.info("Backend: %s", config.backend_url)
    logger.info("Exam origin: %s", config.exam_origin)
    logger.info("Allowed origins: %s", ", ".join(config.allowed_origins))

    problems = config.validate()
    if problems:
        _show_fatal(
            "Cấu hình không hợp lệ:\n- "
            + "\n- ".join(problems)
            + f"\n\nFile log: {log_file}\n"
            "Sửa file .env nằm cạnh chương trình rồi chạy lại."
        )
        return 1

    _log_capabilities()
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
        qt_app.lastWindowClosed.connect(event_loop.stop)
        event_loop.run_forever()
        qt_app.lastWindowClosed.disconnect(event_loop.stop)
        event_loop.run_until_complete(client_app.shutdown())

    logger.info("SEB Client ket thuc")
    return 0


def _run_config_file_mode(config_file: str, log_file) -> int:
    """Chế độ "mở file cấu hình": không backend, không login, không socket.

    Chạy trên `app.exec()` thường (không qasync) vì không có việc mạng nào —
    qasync chỉ cần khi có heartbeat/socket async. Giữ đơn giản giúp lỗi Qt
    không bị che bởi tầng event loop của asyncio.
    """
    from .config_file import ConfigFileError
    from .ui.policy_browser_window import PolicyBrowserWindow

    try:
        from .config_file import load_config_file

        policy = load_config_file(config_file)
    except ConfigFileError as exc:
        _show_fatal(
            f"Không mở được file cấu hình:\n{exc}\n\nFile log: {log_file}"
        )
        return 1

    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.setApplicationName("SEB Client")
    qt_app.setQuitOnLastWindowClosed(True)

    window = PolicyBrowserWindow(policy)
    window.show()
    window.start()

    if policy.unsupported:
        from PySide6.QtWidgets import QMessageBox

        details = "\n".join(f"- {key}: {reason}" for key, reason in policy.unsupported.items())
        QMessageBox.information(
            None,
            "Cấu hình có phần chưa hỗ trợ",
            "File cấu hình yêu cầu những cơ chế client chưa thực hiện được.\n"
            "Trang thi vẫn mở, nhưng mức bảo vệ thấp hơn cấu hình ghi:\n\n"
            f"{details}",
        )

    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
