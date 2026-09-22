import pytest


@pytest.mark.asyncio
async def test_direct_and_group_chats(client, auth_headers):
    # Register user B
    reg_b = await client.post(
        "/api/auth/register",
        json={"username": "david_test", "password": "Password123"},
    )
    user_b_id = reg_b.json()["user"]["id"]

    # 1. Create direct chat between Alice and David
    chat_res = await client.post(
        "/api/chats",
        headers=auth_headers["headers"],
        json={"chat_type": "direct", "target_user_id": user_b_id},
    )
    assert chat_res.status_code == 201
    chat_data = chat_res.json()
    chat_id = chat_data["id"]
    assert chat_data["chat_type"] == "direct"
    assert len(chat_data["members"]) == 2

    # 2. Idempotent direct chat creation returns the same chat
    repeat_res = await client.post(
        "/api/chats",
        headers=auth_headers["headers"],
        json={"chat_type": "direct", "target_user_id": user_b_id},
    )
    assert repeat_res.status_code == 201
    assert repeat_res.json()["id"] == chat_id

    # 3. Create group chat
    group_res = await client.post(
        "/api/chats",
        headers=auth_headers["headers"],
        json={
            "chat_type": "group",
            "name": "Secret Project",
            "member_ids": [user_b_id],
        },
    )
    assert group_res.status_code == 201
    group_data = group_res.json()
    group_id = group_data["id"]
    assert group_data["chat_type"] == "group"
    assert group_data["title"] == "Secret Project"

    # Verify Alice is OWNER and David is MEMBER
    roles = {m["user_id"]: m["role"] for m in group_data["members"]}
    assert roles[auth_headers["user"]["id"]] == "owner"
    assert roles[user_b_id] == "member"

    # 4. Rename group chat as owner
    rename_res = await client.patch(
        f"/api/chats/{group_id}",
        headers=auth_headers["headers"],
        json={"name": "Renamed Project Group"},
    )
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "Renamed Project Group"

    # 5. List user chats
    list_res = await client.get("/api/chats", headers=auth_headers["headers"])
    assert list_res.status_code == 200
    chats = list_res.json()["chats"]
    assert len(chats) >= 2
