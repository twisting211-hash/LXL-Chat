import pytest


@pytest.mark.asyncio
async def test_register_and_login_flow(client):
    # 1. Register new user
    res = await client.post(
        "/api/auth/register",
        json={"username": "bob_builder", "password": "SecurePassword123"},
    )
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["username"] == "bob_builder"
    assert "password_hash" not in data["user"]

    # 2. Case-insensitive duplicate rejection
    dup_res = await client.post(
        "/api/auth/register",
        json={"username": "BOB_BUILDER", "password": "AnotherPassword123"},
    )
    assert dup_res.status_code == 409
    assert "taken" in dup_res.json()["detail"].lower()

    # 3. Short password validation (<8 chars)
    short_pwd = await client.post(
        "/api/auth/register",
        json={"username": "short_user", "password": "123"},
    )
    assert short_pwd.status_code == 422

    # 4. Invalid username format (symbols not allowed)
    invalid_user = await client.post(
        "/api/auth/register",
        json={"username": "invalid@user!", "password": "ValidPassword123"},
    )
    assert invalid_user.status_code == 422

    # 5. Successful login
    login_res = await client.post(
        "/api/auth/login",
        json={"username": "bob_builder", "password": "SecurePassword123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # 6. Failed login on bad password
    bad_login = await client.post(
        "/api/auth/login",
        json={"username": "bob_builder", "password": "WrongPassword"},
    )
    assert bad_login.status_code == 401

    # 7. Get current user profile
    me_res = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "bob_builder"


@pytest.mark.asyncio
async def test_user_search(client, auth_headers):
    # Register secondary user
    await client.post(
        "/api/auth/register",
        json={"username": "charlie_brown", "password": "Password123"},
    )

    # Search for charlie using alice's auth token
    res = await client.get(
        "/api/users/search?username=charlie",
        headers=auth_headers["headers"],
    )
    assert res.status_code == 200
    users = res.json()
    assert len(users) >= 1
    assert any(u["username"] == "charlie_brown" for u in users)
    # Ensure password hash is never exposed
    for u in users:
        assert "password_hash" not in u
