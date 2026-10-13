import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

logger = logging.getLogger(__name__)

# Cấu hình logging cơ bản để các thông điệp vận hành (khởi động heartbeat, phát hiện
# đăng nhập trùng, ghi nhận vi phạm...) hiện ra. Mặc định Python chỉ in từ mức WARNING
# nên các thông điệp INFO sẽ bị bỏ qua.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
# Socket.IO rất ồn nếu bật logger
logging.getLogger("socketio").setLevel(logging.WARNING)
logging.getLogger("engineio").setLevel(logging.WARNING)

from app.core.config import settings
from app.api.routers import (
    auth_router,
    question_router,
    exam_router,
    exam_session_router,
    report_router,
    settings_router,
    security_router,
    admin_router,
)
from app.sockets.socket_server import sio
from app.sockets.exam_namespace import register_exam_socket_handlers, active_sockets
from app.sockets.monitor_namespace import register_monitor_socket_handlers
from app.services.heartbeat_monitor import start_heartbeat_monitor

# Initialize FastAPI app
fastapi_app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Hệ thống thi trắc nghiệm trực tuyến với cơ chế khoá an toàn và giám sát thời gian thực",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Configure CORS
# KHÔNG được dùng allow_origins=["*"] cùng allow_credentials=True: theo đặc tả CORS,
# trình duyệt sẽ từ chối preflight khi gửi cookie/Authorization qua cross-origin.
# Danh sách origin lấy từ settings.CORS_ORIGINS.
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Client-Required"],
)

# Register Routers
fastapi_app.include_router(auth_router.router, prefix=settings.API_V1_STR)
fastapi_app.include_router(question_router.router, prefix=settings.API_V1_STR)
fastapi_app.include_router(exam_router.router, prefix=settings.API_V1_STR)
fastapi_app.include_router(exam_session_router.router, prefix=settings.API_V1_STR)
fastapi_app.include_router(report_router.router, prefix=settings.API_V1_STR)
fastapi_app.include_router(settings_router.router, prefix=settings.API_V1_STR)
fastapi_app.include_router(security_router.router, prefix=settings.API_V1_STR)
fastapi_app.include_router(admin_router.router, prefix=settings.API_V1_STR)

@fastapi_app.get("/")
def root():
    return {
        "system": settings.PROJECT_NAME,
        "status": "online",
        "docs": "/docs",
        "version": "3.0.0"
    }

# Register Socket.IO event handlers
register_exam_socket_handlers()
register_monitor_socket_handlers()

# Vòng quét heartbeat nền: phát hiện thí sinh mất kết nối giữa kỳ thi.
# Trước đây HEARTBEAT_TIMEOUT_SECONDS có trong config nhưng không được dùng ở đâu.
_HEARTBEAT_TASK = None

@fastapi_app.on_event("startup")
async def _start_background_tasks():
    global _HEARTBEAT_TASK
    _HEARTBEAT_TASK = start_heartbeat_monitor(active_sockets, sio)
    logger.info("Đã khởi động vòng quét heartbeat")

@fastapi_app.on_event("shutdown")
async def _stop_background_tasks():
    global _HEARTBEAT_TASK
    if _HEARTBEAT_TASK:
        _HEARTBEAT_TASK.cancel()
        logger.info("Đã dừng vòng quét heartbeat")

# Wrap FastAPI with Socket.IO ASGIApp
# This ensures that both REST API endpoints and Socket.IO WebSocket connections run on the same port seamlessly
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)
