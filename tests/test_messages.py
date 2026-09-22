import pytest


@pytest.mark.asyncio
async def test_message_operations(client, auth_headers):
    # Create another user and direct chat
    reg_u = await client.post(
        "/api/auth/register",
        json={"username": "eve_tester", "password": "Password123"},
    )
    eve_id = reg_u.json()["user"]["id"]
    eve_token = reg_u.json()["access_token"]
    eve_headers = {"Authorization": f"Bearer {eve_token}"}

    chat_res = await client.post(
        "/api/chats",
        headers=auth_headers["headers"],
        json={"chat_type": "direct", "target_user_id": eve_id},
    )
    chat_id = chat_res.json()["id"]

    # 1. Send text message
    msg_res = await client.post(
        f"/api/chats/{chat_id}/messages",
        headers=auth_headers["headers"],
        json={"text": "Hello Eve, how are you?", "message_type": "text"},
    )
    assert msg_res.status_code == 201
    msg_data = msg_res.json()
    msg_id = msg_data["id"]
    assert msg_data["text"] == "Hello Eve, how are you?"
    assert msg_data["chat_id"] == chat_id

    # 2. Retrieve history
    history_res = await client.get(
        f"/api/chats/{chat_id}/messages",
        headers=eve_headers,
    )
    assert history_res.status_code == 200
    msgs = history_res.json()["messages"]
    assert len(msgs) >= 1
    assert msgs[-1]["id"] == msg_id

    # 3. Mark delivered and read
    deliv_res = await client.post(
        f"/api/messages/{msg_id}/delivered",
        headers=eve_headers,
    )
    assert deliv_res.status_code == 200
    assert "delivered_at" in deliv_res.json()

    read_res = await client.post(
        f"/api/chats/{chat_id}/read?last_message_id={msg_id}",
        headers=eve_headers,
    )
    assert read_res.status_code == 200

    # 4. Edit message
    edit_res = await client.patch(
        f"/api/messages/{msg_id}",
        headers=auth_headers["headers"],
        json={"text": "Hello Eve, edited text!"},
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["text"] == "Hello Eve, edited text!"
    assert edit_res.json()["edited_at"] is not None

    # Eve cannot edit Alice's message
    eve_edit = await client.patch(
        f"/api/messages/{msg_id}",
        headers=eve_headers,
        json={"text": "Eve trying to hack message"},
    )
    assert eve_edit.status_code == 403

    # 5. Delete message
    del_res = await client.delete(
        f"/api/messages/{msg_id}",
        headers=auth_headers["headers"],
    )
    assert del_res.status_code == 200

    # Verify message is no longer returned in normal history
    updated_hist = await client.get(
        f"/api/chats/{chat_id}/messages",
        headers=eve_headers,
    )
    remaining_ids = [m["id"] for m in updated_hist.json()["messages"]]
    assert msg_id not in remaining_ids
