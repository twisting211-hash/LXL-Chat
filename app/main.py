import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import (
    auth_router,
    calls_router,
    chats_router,
    devices_router,
    files_router,
    health_router,
    messages_router,
    users_router,
)
from app.services.server_status import server_status_service
from app.websocket.endpoint import router as websocket_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("messenger.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for application startup and shutdown."""
    server_status_service.mark_starting()
    app.state.server_status = "starting"
    logger.info("Initializing Private Messenger Backend (starting)...")

    # Ensure local uploads directory exists
    os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.LOCAL_UPLOAD_DIR, "media"), exist_ok=True)
    os.makedirs(os.path.join(settings.LOCAL_UPLOAD_DIR, "avatars"), exist_ok=True)
    os.makedirs(os.path.join(settings.LOCAL_UPLOAD_DIR, "voice"), exist_ok=True)
    os.makedirs(os.path.join(settings.LOCAL_UPLOAD_DIR, "docs"), exist_ok=True)

    # Server is fully initialized and online
    server_status_service.mark_online()
    app.state.server_status = "online"
    logger.info("Private Messenger Backend is ONLINE and ready for traffic.")

    yield

    server_status_service.mark_offline()
    app.state.server_status = "offline"
    logger.info("Shutting down Private Messenger Backend...")


app = FastAPI(
    title="Private Messenger Backend",
    description=(
        "Production-grade, secure backend for personal and small-group private messaging. "
        "Provides 1-to-1 chats, group conversations, real-time WebSockets, WebRTC audio/video call signaling, "
        "push notifications, and multi-provider media storage."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local upload directory for media serving during development
if os.path.exists(settings.LOCAL_UPLOAD_DIR):
    app.mount(
        "/uploads",
        StaticFiles(directory=settings.LOCAL_UPLOAD_DIR),
        name="uploads",
    )


# Consistent error handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats validation errors into consistent detail string."""
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    msg = first_error.get("msg", "Validation error")
    loc = " -> ".join(str(l) for l in first_error.get("loc", []))
    detail = f"{loc}: {msg}" if loc else msg
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Ensures consistent JSON error detail response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catches unhandled errors and logs them safely without exposing stack trace to client."""
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# Include API Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(chats_router)
app.include_router(messages_router)
app.include_router(files_router)
app.include_router(calls_router)
app.include_router(devices_router)
app.include_router(websocket_router)
