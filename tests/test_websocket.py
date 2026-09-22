import pytest
from app.websocket.manager import ConnectionManager


@pytest.mark.asyncio
async def test_health_check(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json() == {
        "status": "ok",
        "service": "messenger-backend",
    }


@pytest.mark.asyncio
async def test_webrtc_config_endpoint(client, auth_headers):
    res = await client.get("/api/calls/config", headers=auth_headers["headers"])
    assert res.status_code == 200
    data = res.json()
    assert "ice_servers" in data
    assert len(data["ice_servers"]) >= 1


def test_connection_manager_state():
    mgr = ConnectionManager()
    assert not mgr.is_user_online(999)
    assert len(mgr.get_online_user_ids()) == 0

    mgr.set_user_in_call(1, 100)
    assert mgr.is_user_busy(1)
    assert not mgr.is_user_busy(2)

    mgr.clear_user_call(1)
    assert not mgr.is_user_busy(1)
