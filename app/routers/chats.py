from datetime import datetime, timezone
from typing import List, Optional, Union
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.auth.deps import get_current_active_user
from app.database import get_db
from app.models.chat import Chat, ChatMember, ChatType, GroupProfile, MemberRole
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import (
    AddMembersRequest,
    ChatDetailResponse,
    ChatListItem,
    ChatListResponse,
    ChatMemberResponse,
    GroupProfileResponse,
    GroupUpdate,
)
from app.schemas.message import MessageResponse
from app.services.chat_service import (
    create_group_chat,
    get_chat_participant_ids,
    get_or_create_direct_chat,
    get_user_chat_member,
)
from app.utils.exceptions import forbidden, not_found
from app.websocket.manager import manager

router = APIRouter(prefix="/api/chats", tags=["Chats"])


class CreateChatRequest(BaseModel):
    chat_type: ChatType = ChatType.DIRECT
    target_user_id: Optional[int] = None
    name: Optional[str] = Field(None, max_length=100)
    member_ids: Optional[List[int]] = Field(default_factory=list)
    avatar_url: Optional[str] = None


@router.post(
    "",
    response_model=ChatDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or get chat",
    description="Creates or opens a 1-to-1 conversation (idempotent), or creates a new group chat.",
)
async def create_chat(
    payload: CreateChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.chat_type == ChatType.DIRECT:
        if not payload.target_user_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="target_user_id is required for direct chats",
            )
        if payload.target_user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot start a direct conversation with yourself",
            )

        # Verify target user exists
        stmt = select(User).where(User.id == payload.target_user_id, User.is_active == True)
        res = await db.execute(stmt)
        target_user = res.scalar_one_or_none()
        if not target_user:
            raise not_found("Target user")

        chat, is_new = await get_or_create_direct_chat(db, current_user.id, target_user.id)
    else:
        # Group chat
        group_name = (payload.name or "").strip()
        if not group_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Group name is required",
            )

        member_ids = payload.member_ids or []
        chat = await create_group_chat(
            db=db,
            creator_id=current_user.id,
            name=group_name,
            member_ids=member_ids,
            avatar_url=payload.avatar_url,
        )

    # Format response
    return await _build_chat_detail_response(chat, current_user.id)


@router.get(
    "",
    response_model=ChatListResponse,
    summary="List user chats",
    description="Returns all active conversations the user is a participant in, with last message and unread count.",
)
async def list_chats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Find chats user belongs to
    member_stmt = (
        select(ChatMember.chat_id)
        .where(ChatMember.user_id == current_user.id)
    )
    res = await db.execute(member_stmt)
    chat_ids = list(res.scalars().all())

    if not chat_ids:
        return ChatListResponse(chats=[])

    # Fetch full chat models with members and group profiles
    stmt = (
        select(Chat)
        .where(Chat.id.in_(chat_ids))
        .order_by(desc(Chat.updated_at))
        .options(
            selectinload(Chat.members).selectinload(ChatMember.user),
            selectinload(Chat.group_profile),
        )
    )
    result = await db.execute(stmt)
    chats = result.scalars().all()

    chat_items: List[ChatListItem] = []
    for c in chats:
        # Get last message
        msg_stmt = (
            select(Message)
            .where(Message.chat_id == c.id, Message.deleted_at.is_(None))
            .order_by(desc(Message.created_at))
            .limit(1)
            .options(selectinload(Message.sender))
        )
        msg_res = await db.execute(msg_stmt)
        last_msg = msg_res.scalar_one_or_none()

        # Unread count: messages sent by others after my last_read_message_id
        my_membership = next((m for m in c.members if m.user_id == current_user.id), None)
        last_read_id = my_membership.last_read_message_id if my_membership else 0
        last_read_id = last_read_id or 0

        unread_stmt = (
            select(func.count(Message.id))
            .where(
                Message.chat_id == c.id,
                Message.sender_id != current_user.id,
                Message.id > last_read_id,
                Message.deleted_at.is_(None),
            )
        )
        unread_res = await db.execute(unread_stmt)
        unread_count = unread_res.scalar_one() or 0

        # Title & avatar
        if c.chat_type == ChatType.DIRECT:
            other = next((m.user for m in c.members if m.user_id != current_user.id), None)
            title = other.username if other else "Private Chat"
            avatar = other.avatar_url if other else None
            other_user_resp = (
                ChatMemberResponse(
                    user_id=other.id,
                    username=other.username,
                    avatar_url=other.avatar_url,
                    role=MemberRole.MEMBER,
                    joined_at=c.created_at,
                    is_online=manager.is_user_online(other.id),
                    last_seen=other.last_seen,
                )
                if other
                else None
            )
        else:
            title = c.group_profile.name if c.group_profile else "Group Chat"
            avatar = c.group_profile.avatar_url if c.group_profile else None
            other_user_resp = None

        chat_items.append(
            ChatListItem(
                id=c.id,
                chat_type=c.chat_type,
                title=title,
                avatar_url=avatar,
                updated_at=c.updated_at,
                unread_count=unread_count,
                last_message=MessageResponse.model_validate(last_msg) if last_msg else None,
                other_user=other_user_resp,
            )
        )

    return ChatListResponse(chats=chat_items)


@router.get(
    "/{chat_id}",
    response_model=ChatDetailResponse,
    summary="Get chat details",
    description="Fetches chat metadata and member roster. Verifies caller is a chat participant.",
)
async def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    member = await get_user_chat_member(db, chat_id, current_user.id)
    if not member:
        raise forbidden("You are not a participant in this conversation")

    stmt = (
        select(Chat)
        .where(Chat.id == chat_id)
        .options(
            selectinload(Chat.members).selectinload(ChatMember.user),
            selectinload(Chat.group_profile),
        )
    )
    res = await db.execute(stmt)
    chat = res.scalar_one_or_none()
    if not chat:
        raise not_found("Chat")

    return await _build_chat_detail_response(chat, current_user.id)


@router.patch(
    "/{chat_id}",
    response_model=ChatDetailResponse,
    summary="Rename or update group chat",
    description="Updates group chat name or avatar. Only group OWNER has permission.",
)
async def update_group(
    chat_id: int,
    payload: GroupUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    member = await get_user_chat_member(db, chat_id, current_user.id)
    if not member or member.role != MemberRole.OWNER:
        raise forbidden("Only the group owner can update group details")

    stmt = (
        select(Chat)
        .where(Chat.id == chat_id)
        .options(
            selectinload(Chat.members).selectinload(ChatMember.user),
            selectinload(Chat.group_profile),
        )
    )
    res = await db.execute(stmt)
    chat = res.scalar_one_or_none()
    if not chat or chat.chat_type != ChatType.GROUP or not chat.group_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update group chats",
        )

    if payload.name is not None:
        chat.group_profile.name = payload.name.strip()
    if payload.avatar_url is not None:
        chat.group_profile.avatar_url = payload.avatar_url

    chat.updated_at = datetime.now(timezone.utc)
    db.add(chat)
    await db.commit()
    await db.refresh(chat)

    return await _build_chat_detail_response(chat, current_user.id)


@router.post(
    "/{chat_id}/members",
    response_model=ChatDetailResponse,
    summary="Add members to group",
    description="Adds new members to an existing group chat.",
)
async def add_group_members(
    chat_id: int,
    payload: AddMembersRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify current user is in group
    current_membership = await get_user_chat_member(db, chat_id, current_user.id)
    if not current_membership:
        raise forbidden("You must be a member of the group to add participants")

    # Fetch chat
    stmt = (
        select(Chat)
        .where(Chat.id == chat_id)
        .options(
            selectinload(Chat.members).selectinload(ChatMember.user),
            selectinload(Chat.group_profile),
        )
    )
    res = await db.execute(stmt)
    chat = res.scalar_one_or_none()
    if not chat or chat.chat_type != ChatType.GROUP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only add members to group chats",
        )

    existing_uids = {m.user_id for m in chat.members}
    for uid in payload.user_ids:
        if uid not in existing_uids:
            # Check user exists
            u_res = await db.execute(select(User).where(User.id == uid, User.is_active == True))
            u = u_res.scalar_one_or_none()
            if u:
                new_m = ChatMember(chat_id=chat.id, user_id=uid, role=MemberRole.MEMBER)
                db.add(new_m)

    chat.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Refresh chat with updated members
    res = await db.execute(stmt)
    chat = res.scalar_one()

    # Real-time event notification to participants
    member_ids = [m.user_id for m in chat.members]
    await manager.broadcast_to_users(
        member_ids,
        "chat:members_updated",
        {"chat_id": chat_id, "action": "members_added"},
    )

    return await _build_chat_detail_response(chat, current_user.id)


@router.delete(
    "/{chat_id}/members/{user_id}",
    response_model=ChatDetailResponse,
    summary="Remove member from group",
    description="Removes a member from group chat. Only group OWNER or the user themselves can perform this.",
)
async def remove_group_member(
    chat_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    current_membership = await get_user_chat_member(db, chat_id, current_user.id)
    if not current_membership:
        raise forbidden("You are not in this group")

    # Only owner can remove someone else; or user removing themselves
    if current_user.id != user_id and current_membership.role != MemberRole.OWNER:
        raise forbidden("Only the group owner can remove other participants")

    target_membership = await get_user_chat_member(db, chat_id, user_id)
    if not target_membership:
        raise not_found("Group member")

    await db.delete(target_membership)
    await db.commit()

    stmt = (
        select(Chat)
        .where(Chat.id == chat_id)
        .options(
            selectinload(Chat.members).selectinload(ChatMember.user),
            selectinload(Chat.group_profile),
        )
    )
    res = await db.execute(stmt)
    chat = res.scalar_one()

    # Broadcast update
    participant_ids = [m.user_id for m in chat.members] + [user_id]
    await manager.broadcast_to_users(
        participant_ids,
        "chat:members_updated",
        {"chat_id": chat_id, "action": "member_removed", "user_id": user_id},
    )

    return await _build_chat_detail_response(chat, current_user.id)


@router.post(
    "/{chat_id}/leave",
    status_code=status.HTTP_200_OK,
    summary="Leave group chat",
    description="Leaves the group conversation.",
)
async def leave_group(
    chat_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_user_chat_member(db, chat_id, current_user.id)
    if not membership:
        raise not_found("Group membership")

    # If owner leaves and other members remain, reassign ownership
    if membership.role == MemberRole.OWNER:
        other_stmt = (
            select(ChatMember)
            .where(ChatMember.chat_id == chat_id, ChatMember.user_id != current_user.id)
            .order_by(ChatMember.joined_at.asc())
            .limit(1)
        )
        res = await db.execute(other_stmt)
        next_owner = res.scalar_one_or_none()
        if next_owner:
            next_owner.role = MemberRole.OWNER
            db.add(next_owner)

    await db.delete(membership)
    await db.commit()

    # Broadcast leave event
    remaining_ids = await get_chat_participant_ids(db, chat_id)
    await manager.broadcast_to_users(
        remaining_ids,
        "chat:member_left",
        {"chat_id": chat_id, "user_id": current_user.id, "username": current_user.username},
    )

    return {"status": "ok", "message": "Successfully left the group"}


async def _build_chat_detail_response(chat: Chat, current_user_id: int) -> ChatDetailResponse:
    members_resp = []
    for m in chat.members:
        u = m.user
        members_resp.append(
            ChatMemberResponse(
                user_id=u.id,
                username=u.username,
                avatar_url=u.avatar_url,
                role=m.role,
                joined_at=m.joined_at,
                is_online=manager.is_user_online(u.id),
                last_seen=u.last_seen,
            )
        )

    if chat.chat_type == ChatType.DIRECT:
        other = next((m.user for m in chat.members if m.user_id != current_user_id), None)
        title = other.username if other else "Private Chat"
        avatar = other.avatar_url if other else None
        group_profile_resp = None
    else:
        gp = chat.group_profile
        title = gp.name if gp else "Group Chat"
        avatar = gp.avatar_url if gp else None
        group_profile_resp = (
            GroupProfileResponse(
                name=gp.name,
                avatar_url=gp.avatar_url,
                creator_id=gp.creator_id,
                created_at=gp.created_at,
            )
            if gp
            else None
        )

    return ChatDetailResponse(
        id=chat.id,
        chat_type=chat.chat_type,
        title=title,
        avatar_url=avatar,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        members=members_resp,
        group_profile=group_profile_resp,
    )
