import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, update
from app.auth.deps import authenticate_websocket
from app.database import AsyncSessionLocal
from app.models.chat import ChatMember
from app.models.user import User
from app.services.server_status import server_status_service
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time chat, typing events, presence, and WebRTC signaling.
    Client connects with token: ws://.../ws?token=<JWT_ACCESS_TOKEN>
    """
    # 1. Authenticate WebSocket Handshake
    async with AsyncSessionLocal() as db:
        user = await authenticate_websocket(token, db)
        if not user:
            logger.warning("Rejected unauthorized WebSocket connection attempt.")
            await websocket.close(code=4001, reason="Unauthorized")
            return

        user_id = user.id
        username = user.username

    # 2. Register Connection with Manager
    is_first = await manager.connect(user_id, websocket)

    # 3. If first connection, update DB status and broadcast user:online
    if is_first:
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(is_online=True, last_seen=now)
            )
            await db.commit()

        # Broadcast online event to all connected clients
        online_users = list(manager.get_online_user_ids())
        await manager.broadcast_to_users(
            online_users,
            "user:online",
            {"user_id": user_id, "username": username},
            exclude_user_id=user_id,
        )

    # Send initial welcome & current online users list to client
    await manager.send_event(
        websocket,
        "connection:ready",
        {
            "user_id": user_id,
            "username": username,
            "online_users": list(manager.get_online_user_ids()),
        },
    )

    # If this connected user is the designated owner, dispatch the server:online event.
    # Enables the mobile app to display "🟢 Server is online" exclusively for the owner.
    # Regular users do NOT receive this event.
    if server_status_service.is_owner(username=username, user_id=user_id):
        await manager.send_event(
            websocket,
            "server:online",
            server_status_service.get_server_online_event_payload(),
        )
        logger.info(f"Delivered 'server:online' event to owner user: {username}")

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                message_json = json.loads(raw_text)
            except json.JSONDecodeError:
                # Handle simple plain ping
                if raw_text.strip() == "ping":
                    await manager.send_event(websocket, "pong", {"timestamp": datetime.now(timezone.utc).isoformat()})
                continue

            event = message_json.get("event")
            data = message_json.get("data", {})

            if not event:
                continue

            # Heartbeat ping/pong
            if event == "ping":
                await manager.send_event(websocket, "pong", {"timestamp": datetime.now(timezone.utc).isoformat()})
                continue

            # Typing status: start / stop (in-memory relay only, no DB writes)
            elif event in ("typing:start", "typing:stop"):
                chat_id = data.get("chat_id")
                if chat_id:
                    async with AsyncSessionLocal() as db:
                        # Verify user is a member of the chat
                        stmt = select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
                        res = await db.execute(stmt)
                        member_ids = list(res.scalars().all())

                    if user_id in member_ids:
                        await manager.broadcast_to_users(
                            member_ids,
                            event,
                            {
                                "chat_id": chat_id,
                                "user_id": user_id,
                                "username": username,
                            },
                            exclude_user_id=user_id,
                        )

            # WebRTC Signaling: call:offer
            elif event == "call:offer":
                target_user_id = data.get("target_user_id")
                call_id = data.get("call_id")
                offer = data.get("offer")
                call_type = data.get("call_type", "audio")

                if not target_user_id or not offer:
                    continue

                # Check if target is already in another call
                if manager.is_user_busy(target_user_id):
                    await manager.send_to_user(
                        user_id,
                        "call:busy",
                        {
                            "call_id": call_id,
                            "target_user_id": target_user_id,
                            "reason": "User is currently busy on another call",
                        },
                    )
                    continue

                manager.set_user_in_call(user_id, call_id)
                manager.set_user_in_call(target_user_id, call_id)

                await manager.send_to_user(
                    target_user_id,
                    "call:offer",
                    {
                        "call_id": call_id,
                        "caller_id": user_id,
                        "caller_username": username,
                        "call_type": call_type,
                        "offer": offer,
                    },
                )

            # WebRTC Signaling: call:answer
            elif event == "call:answer":
                target_user_id = data.get("target_user_id")
                call_id = data.get("call_id")
                answer = data.get("answer")

                if target_user_id and answer:
                    await manager.send_to_user(
                        target_user_id,
                        "call:answer",
                        {
                            "call_id": call_id,
                            "responder_id": user_id,
                            "answer": answer,
                        },
                    )

            # WebRTC Signaling: call:ice-candidate
            elif event == "call:ice-candidate":
                target_user_id = data.get("target_user_id")
                candidate = data.get("candidate")
                call_id = data.get("call_id")

                if target_user_id and candidate:
                    await manager.send_to_user(
                        target_user_id,
                        "call:ice-candidate",
                        {
                            "call_id": call_id,
                            "from_user_id": user_id,
                            "candidate": candidate,
                        },
                    )

            # WebRTC Signaling: call:reject
            elif event == "call:reject":
                target_user_id = data.get("target_user_id")
                call_id = data.get("call_id")
                reason = data.get("reason", "declined")

                manager.clear_user_call(user_id)
                if target_user_id:
                    manager.clear_user_call(target_user_id)
                    await manager.send_to_user(
                        target_user_id,
                        "call:reject",
                        {
                            "call_id": call_id,
                            "rejecter_id": user_id,
                            "reason": reason,
                        },
                    )

            # WebRTC Signaling: call:end
            elif event == "call:end":
                target_user_id = data.get("target_user_id")
                call_id = data.get("call_id")

                manager.clear_user_call(user_id)
                if target_user_id:
                    manager.clear_user_call(target_user_id)
                    await manager.send_to_user(
                        target_user_id,
                        "call:end",
                        {
                            "call_id": call_id,
                            "ended_by": user_id,
                        },
                    )

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: user_id={user_id}")
    except Exception as e:
        logger.error(f"WebSocket unexpected error for user_id={user_id}: {e}")
    finally:
        is_last = await manager.disconnect(user_id, websocket)
        if is_last:
            manager.clear_user_call(user_id)
            now = datetime.now(timezone.utc)
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(is_online=False, last_seen=now)
                )
                await db.commit()

            # Broadcast user:offline with last_seen
            online_users = list(manager.get_online_user_ids())
            await manager.broadcast_to_users(
                online_users,
                "user:offline",
                {
                    "user_id": user_id,
                    "username": username,
                    "last_seen": now.isoformat(),
                },
            )
