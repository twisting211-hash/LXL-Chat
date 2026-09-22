import pytest
from app.config import settings
from app.services.server_status import server_status_service


@pytest.mark.asyncio
async def test_health_check_endpoint(client):
    """
    Validates:
    - GET /health returns HTTP 200
    - Exact JSON: {"status": "ok", "service": "messenger-backend"}
    - No authentication required
    - X-Server-Status header is present
    """
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data == {
        "status": "ok",
        "service": "messenger-backend",
    }
    assert res.headers.get("x-server-status") == "online"


@pytest.mark.asyncio
async def test_health_check_detailed_status(client):
    """
    Validates GET /health?detailed=true includes server_status = online
    """
    res = await client.get("/health?detailed=true")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "messenger-backend"
    assert data["server_status"] == "online"


@pytest.mark.asyncio
async def test_detailed_server_status_endpoint(client):
    """
    Validates GET /api/server/status returns full diagnostics.
    """
    res = await client.get("/api/server/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "messenger-backend"
    assert data["server_status"] == "online"
    assert "uptime_seconds" in data
    assert "owner_configured" in data


def test_server_status_service_lifecycle():
    """
    Tests ServerStatusService state transitions and uptime tracking.
    """
    service = server_status_service
    assert service.is_online() is True
    assert service.get_status() == "online"
    assert service.get_uptime_seconds() >= 0.0

    payload = service.get_server_online_event_payload()
    assert payload["service"] == "messenger-backend"
    assert payload["status"] == "online"
    assert payload["message"] == "🟢 Server is online"
    assert "timestamp" in payload


def test_owner_detection_without_hardcoded_secrets(monkeypatch):
    """
    Ensures owner matching is dynamic and case-insensitive based purely on OWNER_USERNAME env var.
    Never checks hardcoded credentials.
    """
    service = server_status_service

    # When OWNER_USERNAME is empty, no user is owner
    monkeypatch.setattr(settings, "OWNER_USERNAME", "")
    assert service.is_owner("alice") is False
    assert service.is_owner("admin") is False

    # When OWNER_USERNAME is set to 'sys_admin'
    monkeypatch.setattr(settings, "OWNER_USERNAME", "sys_admin")
    assert service.is_owner("sys_admin") is True
    assert service.is_owner("SYS_ADMIN") is True
    assert service.is_owner("Sys_Admin") is True
    assert service.is_owner("regular_user") is False
    assert service.is_owner(None) is False
