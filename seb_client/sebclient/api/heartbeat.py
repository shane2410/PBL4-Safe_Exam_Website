"""Socket.IO client: giữ kết nối phòng thi và gửi heartbeat định kỳ.

Bắt buộc dùng `socketio.AsyncClient`. Bản sync (`socketio.Client`) sẽ chặn
event loop Qt mỗi lần nhận message — biểu hiện là cửa sổ đứng hình.

Mọi việc mạng chạy bằng `await`; hàm gọi từ Qt (`_on_connected`…) được đẩy vào
loop qua `call_soon_threadsafe` khi cần, còn lại thì coroutine gọi thẳng.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

import socketio

from ..constants import (
    EVENT_FORCE_SUBMIT,
    EVENT_HEARTBEAT,
    EVENT_JOIN_ROOM,
    EVENT_STATUS_CHANGE,
    EVENT_VIOLATION,
    HEARTBEAT_INTERVAL_SECONDS,
)

logger = logging.getLogger(__name__)


class ExamSocket:
    """Bọc socket của một phiên thi."""

    def __init__(
        self,
        backend_url: str,
        room_code: str,
        session_token: str,
        interval_seconds: int = HEARTBEAT_INTERVAL_SECONDS,
        on_force_submit: Callable[[dict], None] | None = None,
        on_status_change: Callable[[dict], None] | None = None,
    ):
        self._backend_url = backend_url
        self._room_code = room_code
        self._session_token = session_token
        self._interval = interval_seconds
        self._on_force_submit = on_force_submit
        self._on_status_change = on_status_change

        self._sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_delay=2,
            reconnection_attempts=0,
            logger=False,
            engineio_logger=False,
        )
        self._heartbeat_task: asyncio.Task | None = None
        self._connected = asyncio.Event()
        self._beat_count = 0
        self._alive = True
        self._disconnecting = False
        self._scheduled_close = None
        # Lưu loop ngay lúc khởi tạo: khi cửa sổ đóng, event loop có thể đã
        # không còn chạy, lúc đó `get_event_loop()` trả về loop sai và
        # `run_coroutine_threadsafe` ném RuntimeError.
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        self._sio.on("connect", self._handle_connect)
        self._sio.on("disconnect", self._handle_disconnect)
        self._sio.on(EVENT_FORCE_SUBMIT, self._handle_force_submit)
        self._sio.on(EVENT_STATUS_CHANGE, self._handle_status_change)

    @property
    def connected(self) -> bool:
        return self._sio.connected

    @property
    def beat_count(self) -> int:
        return self._beat_count

    async def connect_and_join(self) -> dict:
        """Kết nối socket và vào phòng. Trả về ack của server."""
        await self._sio.connect(self._backend_url, transports=["websocket"])
        ack = await self._sio.call(
            EVENT_JOIN_ROOM,
            {"room_code": self._room_code, "session_token": self._session_token},
            timeout=15,
        )
        status = (ack or {}).get("status")
        if status != "success":
            message = (ack or {}).get("message", "Không rõ nguyên nhân")
            raise RuntimeError(f"Không vào được phòng: {message}")

        logger.info(
            "Da vao phong %s (session=%s)", self._room_code, (ack or {}).get("session_id")
        )
        self._connected.set()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        return ack or {}

    def send_violation_soon(self, event_type: str, detail: dict | None = None) -> bool:
        """Hẹn gửi vi phạm mà KHÔNG cần await — dùng được từ callback của Qt.

        Guard báo vi phạm từ các Qt timer (clipboard, devtools) nên hàm gọi
        chạy đồng bộ BÊN TRONG event loop Qt. Gọi `ensure_future` ở đó sẽ khiến
        qasync ném RuntimeError "Cannot enter into task ... while another task
        is being executed". `run_coroutine_threadsafe` lên loop đã lưu là cách
        an toàn trong tình huống này.
        """
        if self._loop is None or self._loop.is_closed():
            return False
        if not self._sio.connected:
            logger.debug("Bo qua violation %s: chua co socket", event_type)
            return False
        try:
            asyncio.run_coroutine_threadsafe(
                self.send_violation(event_type, detail), self._loop
            )
        except RuntimeError:
            logger.debug("Khong len lenh gui violation duoc")
            return False
        return True

    async def send_violation(self, event_type: str, detail: dict | None = None) -> dict | None:
        """Báo vi phạm lên server. Không làm treo cửa sổ nếu mất kết nối."""
        if not self._sio.connected:
            logger.warning("Bo qua violation %s: chua co socket", event_type)
            return None
        try:
            from datetime import datetime, timezone

            # Khoá đúng tên trường mà backend đọc: `type` và `clientTimestamp`
            # (xem backend/app/sockets/exam_namespace.py). Gửi `event_type` sẽ
            # bị backend bỏ qua và rơi về mặc định "TAB_SWITCH", làm sai toàn bộ
            # thống kê vi phạm — đã kiểm chứng và gặp trong thực tế.
            ack = await self._sio.call(
                EVENT_VIOLATION,
                {
                    "type": event_type,
                    "detail": detail or {},
                    "clientTimestamp": datetime.now(timezone.utc).isoformat(),
                },
                timeout=8,
            )
        except (socketio.exceptions.SocketIOError, asyncio.TimeoutError) as exc:
            logger.warning("Khong gui duoc violation %s: %s", event_type, exc)
            return None

        if (ack or {}).get("threshold_exceeded"):
            logger.warning("Server bao vuot nguong vi pham: %s", event_type)
        return ack

    async def disconnect(self) -> None:
        # Idempotent: `closeEvent` có thể gọi disconnect trong lúc một lần
        # disconnect khác đang chạy (await cùng task sẽ văng RuntimeError
        # "Cannot enter into task ... while another task is being executed").
        # Phải huỷ task đã hẹn TRƯỚC khi kiểm tra cờ, không phải sau. Nếu
        # `close_best_effort` đã chạy (đặt cờ rồi hẹn task), nhánh `return` sớm
        # sẽ bỏ qua việc huỷ và task treo đó sẽ đụng task đang chạy — qasync ném
        # "Cannot enter into task ... while another task is being executed".
        if self._scheduled_close is not None:
            self._scheduled_close.cancel()
            self._scheduled_close = None

        if self._disconnecting:
            return
        self._disconnecting = True
        self._alive = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        await self._disconnect_inner()

    async def _disconnect_inner(self) -> None:
        if self._sio.connected:
            try:
                await self._sio.disconnect()
            except Exception as exc:  # noqa: BLE001 - đang tắt, lỗi không nên làm sập app
                logger.warning("Loi khi disconnect socket: %s", exc)
        logger.info("Socket da dong")

    async def _heartbeat_loop(self) -> None:
        """Gửi heartbeat mỗi `_interval` giây.

        Dùng `asyncio.sleep`, KHÔNG dùng `while True: sleep; send` kiểu busy —
        và tuyệt đối không gọi API đồng bộ ở đây.
        """
        try:
            while self._alive:
                await asyncio.sleep(self._interval)
                if not self._sio.connected or not self._alive:
                    continue
                try:
                    await self._sio.call(EVENT_HEARTBEAT, {}, timeout=5)
                    self._beat_count += 1
                except (socketio.exceptions.SocketIOError, asyncio.TimeoutError) as exc:
                    logger.warning("Heartbeat that bai: %s", exc)
        except asyncio.CancelledError:
            raise

    def _handle_connect(self) -> None:
        logger.info("Socket da ket noi (sid=%s)", self._sio.sid)

    def _handle_disconnect(self) -> None:
        self._connected.clear()
        logger.warning("Socket mat ket noi")

    def _handle_force_submit(self, data: dict) -> None:
        logger.warning("Server yeu cau nop bai: %s", (data or {}).get("reason"))
        if self._on_force_submit:
            self._on_force_submit(data or {})

    def _handle_status_change(self, data: dict) -> None:
        if self._on_status_change:
            self._on_status_change(data or {})
    def close_best_effort(self) -> None:
        """Ngắt nhịp heartbeat ngay, KHÔNG tạo coroutine mới.

        Cố ý không `run_coroutine_threadsafe` ở đây: coroutine được tạo trong lúc
        một task khác đang chạy sẽ bắt đầu thực thi ngay và qasync ném
        RuntimeError "Cannot enter into task ... while another task is being
        executed" — kể cả khi ta `cancel()` ngay sau đó, vì task đã vào bên
        trong không rút lại được.

        Đóng socket thật sự do `SebClientApp.shutdown()` gọi `disconnect()` ở
        ngữ cảnh await đúng. Ở lúc đóng cửa sổ, heartbeat đã dừng nên server sẽ
        tự đánh dấu mất kết nối sau `HEARTBEAT_TIMEOUT_SECONDS`.
        """
        self._alive = False
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        if self._scheduled_close is not None:
            self._scheduled_close.cancel()
            self._scheduled_close = None
