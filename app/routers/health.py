from typing import Optional
from fastapi import APIRouter, Response
from pydantic import BaseModel
from app.services.server_status import server_status_service

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "messenger-backend"
    server_status: Optional[str] = None


class DetailedServerStatusResponse(BaseModel):
    status: str = "ok"
    service: str = "messenger-backend"
    server_status: str = "online"
    uptime_seconds: float
    owner_configured: bool


@router.get(
    "/health",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    summary="Service Health Check",
    description=(
        "Lightweight, unauthenticated health check endpoint for Render health probes "
        "and mobile application cold-start detection. Returns HTTP 200 with status ok "
        "and service name when the server is fully running."
    ),
)
async def health_check(response: Response, detailed: bool = False):
    """
    Returns HTTP 200:
    {
      "status": "ok",
      "service": "messenger-backend"
    }
    when the backend is fully running.
    No authentication required.
    """
    current_state = server_status_service.get_status()
    response.headers["X-Server-Status"] = current_state

    status_str = "ok" if server_status_service.is_online() else current_state

    if detailed:
        return HealthResponse(
            status=status_str,
            service=server_status_service.service_name,
            server_status=current_state,
        )

    return HealthResponse(
        status=status_str,
        service=server_status_service.service_name,
    )


@router.get(
    "/api/server/status",
    response_model=DetailedServerStatusResponse,
    summary="Get Server Status & Cold-Start Details",
    description="Returns detailed server status (starting, online), uptime in seconds, and owner notification status.",
)
async def get_server_status():
    """
    Provides server operational status and uptime details for diagnostics.
    """
    current_state = server_status_service.get_status()
    return DetailedServerStatusResponse(
        status="ok" if server_status_service.is_online() else current_state,
        service=server_status_service.service_name,
        server_status=current_state,
        uptime_seconds=server_status_service.get_uptime_seconds(),
        owner_configured=bool(server_status_service.is_owner()),
    )
