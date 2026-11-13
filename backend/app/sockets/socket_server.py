import socketio

from app.core.config import settings

# `cors_allowed_origins` phải khớp danh sách origin của REST API. Trước đây để
# `"*"` nên bất kỳ website nào cũng mở được socket tới backend.
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.CORS_ORIGINS,
    logger=False,
    engineio_logger=False
)
