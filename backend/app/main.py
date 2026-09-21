from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from app.core.config import settings
from app.api.routers import (
    auth_router,
    question_router,
    exam_router,
    exam_session_router,
    report_router,
)
from app.sockets.socket_server import sio
from app.sockets.exam_namespace import register_exam_socket_handlers
from app.sockets.monitor_namespace import register_monitor_socket_handlers

# Initialize FastAPI app
fastapi_app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Hệ thống thi trắc nghiệm trực tuyến với cơ chế khoá an toàn và giám sát thời gian thực",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Configure CORS
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for local and LAN demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
fastapi_app.include_router(auth_router.router, prefix=settings.API_V1_STR)
fastapi_app.include_router(question_router.router, prefix=settings.API_V1_STR)
fastapi_app.include_router(exam_router.router, prefix=settings.API_V1_STR)
fastapi_app.include_router(exam_session_router.router, prefix=settings.API_V1_STR)
fastapi_app.include_router(report_router.router, prefix=settings.API_V1_STR)

@fastapi_app.get("/")
def root():
    return {
        "system": settings.PROJECT_NAME,
        "status": "online",
        "docs": "/docs",
        "version": "2.0.0"
    }

# Register Socket.IO event handlers
register_exam_socket_handlers()
register_monitor_socket_handlers()

# Wrap FastAPI with Socket.IO ASGIApp
# This ensures that both REST API endpoints and Socket.IO WebSocket connections run on the same port seamlessly
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)
