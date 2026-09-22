from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.chats import router as chats_router
from app.routers.messages import router as messages_router
from app.routers.files import router as files_router
from app.routers.calls import router as calls_router
from app.routers.devices import router as devices_router
from app.routers.health import router as health_router

__all__ = [
    "auth_router",
    "users_router",
    "chats_router",
    "messages_router",
    "files_router",
    "calls_router",
    "devices_router",
    "health_router",
]
