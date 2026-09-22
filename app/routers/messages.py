from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.auth.deps import get_current_active_user
from app.database import get_db
from app.models.chat import Chat, ChatMember, MemberRole
from app.models.device import DeviceToken
from app.models.message import Message, MessageType
from app.models.user import User
from app.schemas.message import (
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    MessageUpdate,
)
from app.services.chat_service import get_chat_participant_ids, get_user_chat_member
from app.services.notification import notification_service
from app.utils.exceptions import forbidden, not_found
from app.websocket.manager import manager

router = APIRouter(tags=["Messages"])


@router.post(
    "/api/chats/{chat_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send message to chat",
    description="Sends a new message (text, image, video, audio/voice, or file) to the conversation and broadcasts it in real-time.",
)
async def send_message(
    chat_id: int,
    payload: MessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify sender membership in chat
    membership = await get_user_chat_member(db, chat_id, current_user.id)
    if not membership:
        raise forbidden("You are not a participant in this conversation")

    # Validate message content: must contain either text or file_url
    if not (payload.text and payload.text.strip()) and not payload.file_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message must include either text content or an attachment URL.",
        )

    # Validate reply target if provided
    if payload.reply_to_id:
        reply_stmt = select(Message).where(
            Message.id == payload.reply_to_id, Message.chat_id == chat_id
        )
        reply_res = await db.execute(reply_stmt)
        if not reply_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Referenced reply message does not exist in this chat.",
            )

    now = datetime.now(timezone.utc)
    new_message = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        message_type=payload.message_type,
        text=payload.text.strip() if payload.text else None,
        file_url=payload.file_url,
        file_name=payload.file_name,
        file_size=payload.file_size,
        reply_to_id=payload.reply_to_id,
        created_at=now,
    )
    db.add(new_message)

    # Update chat updated_at
    await db.execute(
        update(Chat).where(Chat.id == chat_id).values(updated_at=now)
    )

    # Update sender's last read message id
    await db.flush()
    membership.last_read_message_id = new_message.id
    membership.last_read_at = now
    db.add(membership)

    await db.commit()

    # Re-query message with relations for serialization
    stmt = (
        select(Message)
        .where(Message.id == new_message.id)
        .options(
            selectinload(Message.sender),
            selectinload(Message.reply_to).selectinload(Message.sender),
        )
    )
    res = await db.execute(stmt)
    full_message = res.scalar_one()

    resp = MessageResponse.model_validate(full_message)

    # Broadcast real-time WebSocket event to chat participants
    participant_ids = await get_chat_participant_ids(db, chat_id)
    await manager.broadcast_to_users(
        participant_ids,
        "message:new",
        resp.model_dump(mode="json"),
    )

    # Trigger push notification to offline members
    offline_member_ids = [
        uid for uid in participant_ids if uid != current_user.id and not manager.is_user_online(uid)
    ]
    if offline_member_ids:
        tok_stmt = select(DeviceToken.device_token).where(
            DeviceToken.user_id.in_(offline_member_ids)
        )
        tok_res = await db.execute(tok_stmt)
        tokens = list(tok_res.scalars().all())

        if tokens:
            snippet = payload.text if payload.text else f"Sent an attachment: {payload.message_type.value}"
            await notification_service.notify_new_message(
                tokens=tokens,
                sender_username=current_user.username,
                chat_title=current_user.username,
                chat_id=chat_id,
                message_snippet=snippet,
                message_id=new_message.id,
            )

    return resp


@router.get(
    "/api/chats/{chat_id}/messages",
    response_model=MessageListResponse,
    summary="Get chat message history",
    description="Retrieves messages for a conversation, ordered chronologically. Supports cursor pagination with before_id.",
)
async def get_messages(
    chat_id: int,
    limit: int = Query(50, ge=1, le=100),
    before_id: Optional[int] = Query(None, description="Fetch messages older than this message ID"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_user_chat_member(db, chat_id, current_user.id)
    if not membership:
        raise forbidden("You are not a participant in this conversation")

    query = (
        select(Message)
        .where(Message.chat_id == chat_id, Message.deleted_at.is_(None))
        .options(
            selectinload(Message.sender),
            selectinload(Message.reply_to).selectinload(Message.sender),
        )
    )

    if before_id:
        query = query.where(Message.id < before_id)

    query = query.order_by(desc(Message.id)).limit(limit + 1)
    res = await db.execute(query)
    messages = list(res.scalars().all())

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    # Return in ascending order for UI consumption
    messages.reverse()
    next_cursor = messages[0].id if messages and has_more else None

    return MessageListResponse(
        messages=[MessageResponse.model_validate(m) for m in messages],
        has_more=has_more,
        next_cursor=next_cursor,
    )


@router.patch(
    "/api/messages/{message_id}",
    response_model=MessageResponse,
    summary="Edit message",
    description="Edits text content of a message. Only original sender can edit.",
)
async def edit_message(
    message_id: int,
    payload: MessageUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Message)
        .where(Message.id == message_id, Message.deleted_at.is_(None))
        .options(
            selectinload(Message.sender),
            selectinload(Message.reply_to).selectinload(Message.sender),
        )
    )
    res = await db.execute(stmt)
    message = res.scalar_one_or_none()
    if not message:
        raise not_found("Message")

    if message.sender_id != current_user.id:
        raise forbidden("You can only edit your own messages")

    message.text = payload.text.strip()
    message.edited_at = datetime.now(timezone.utc)
    db.add(message)
    await db.commit()
    await db.refresh(message)

    resp = MessageResponse.model_validate(message)

    # Broadcast message:edited
    participant_ids = await get_chat_participant_ids(db, message.chat_id)
    await manager.broadcast_to_users(
        participant_ids,
        "message:edited",
        resp.model_dump(mode="json"),
    )

    return resp


@router.delete(
    "/api/messages/{message_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete message",
    description="Soft-deletes a message. Only sender or group owner has permission.",
)
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Message).where(Message.id == message_id, Message.deleted_at.is_(None))
    res = await db.execute(stmt)
    message = res.scalar_one_or_none()
    if not message:
        raise not_found("Message")

    # Check permission: sender or group owner
    membership = await get_user_chat_member(db, message.chat_id, current_user.id)
    is_owner = membership and membership.role == MemberRole.OWNER
    if message.sender_id != current_user.id and not is_owner:
        raise forbidden("You do not have permission to delete this message")

    message.deleted_at = datetime.now(timezone.utc)
    db.add(message)
    await db.commit()

    participant_ids = await get_chat_participant_ids(db, message.chat_id)
    await manager.broadcast_to_users(
        participant_ids,
        "message:deleted",
        {"message_id": message.id, "chat_id": message.chat_id},
    )

    return {"status": "ok", "message_id": message.id}


@router.post(
    "/api/messages/{message_id}/delivered",
    status_code=status.HTTP_200_OK,
    summary="Mark message delivered",
    description="Updates message status to delivered and broadcasts message:delivered event.",
)
async def mark_message_delivered(
    message_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Message).where(Message.id == message_id, Message.deleted_at.is_(None))
    res = await db.execute(stmt)
    message = res.scalar_one_or_none()
    if not message:
        raise not_found("Message")

    now = datetime.now(timezone.utc)
    if not message.delivered_at:
        message.delivered_at = now
        db.add(message)
        await db.commit()

    # Notify sender
    await manager.send_to_user(
        message.sender_id,
        "message:delivered",
        {"message_id": message.id, "chat_id": message.chat_id, "delivered_at": now.isoformat()},
    )

    return {"status": "ok", "delivered_at": now.isoformat()}


@router.post(
    "/api/chats/{chat_id}/read",
    status_code=status.HTTP_200_OK,
    summary="Mark chat messages as read",
    description="Marks all messages in the conversation up to last_message_id as read by current user.",
)
async def mark_chat_read(
    chat_id: int,
    last_message_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_user_chat_member(db, chat_id, current_user.id)
    if not membership:
        raise forbidden("You are not a participant in this conversation")

    now = datetime.now(timezone.utc)

    # Determine highest message ID in chat if not provided
    if not last_message_id:
        high_stmt = select(func.max(Message.id)).where(Message.chat_id == chat_id)
        high_res = await db.execute(high_stmt)
        last_message_id = high_res.scalar_one() or 0

    # Update messages read_at
    await db.execute(
        update(Message)
        .where(
            Message.chat_id == chat_id,
            Message.id <= last_message_id,
            Message.sender_id != current_user.id,
            Message.read_at.is_(None),
        )
        .values(read_at=now, delivered_at=func.coalesce(Message.delivered_at, now))
    )

    # Update user's membership last_read
    membership.last_read_message_id = last_message_id
    membership.last_read_at = now
    db.add(membership)
    await db.commit()

    # Broadcast message:read to chat members
    participant_ids = await get_chat_participant_ids(db, chat_id)
    await manager.broadcast_to_users(
        participant_ids,
        "message:read",
        {
            "chat_id": chat_id,
            "reader_id": current_user.id,
            "last_read_message_id": last_message_id,
            "read_at": now.isoformat(),
        },
    )

    return {"status": "ok", "last_read_message_id": last_message_id}
