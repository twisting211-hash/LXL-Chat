from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.chat import Chat, ChatMember, ChatType, GroupProfile, MemberRole
from app.models.message import Message
from app.models.user import User


async def get_or_create_direct_chat(
    db: AsyncSession, user_a_id: int, user_b_id: int
) -> Tuple[Chat, bool]:
    """
    Finds existing direct chat between two users or creates a new one.
    Returns (Chat, is_new: bool).
    """
    if user_a_id == user_b_id:
        raise ValueError("Cannot create a direct conversation with yourself.")

    # Check for direct chat where both are members
    stmt = (
        select(Chat)
        .join(ChatMember, Chat.id == ChatMember.chat_id)
        .where(Chat.chat_type == ChatType.DIRECT)
        .where(ChatMember.user_id.in_([user_a_id, user_b_id]))
        .group_by(Chat.id)
        .having(func.count(ChatMember.user_id) == 2)
        .options(
            selectinload(Chat.members).selectinload(ChatMember.user),
            selectinload(Chat.group_profile),
        )
    )
    result = await db.execute(stmt)
    existing_chat = result.scalar_one_or_none()

    if existing_chat:
        return existing_chat, False

    # Create new direct chat
    new_chat = Chat(chat_type=ChatType.DIRECT)
    db.add(new_chat)
    await db.flush()

    member_a = ChatMember(
        chat_id=new_chat.id,
        user_id=user_a_id,
        role=MemberRole.MEMBER,
    )
    member_b = ChatMember(
        chat_id=new_chat.id,
        user_id=user_b_id,
        role=MemberRole.MEMBER,
    )
    db.add_all([member_a, member_b])
    await db.commit()

    # Re-query with eager loads
    stmt = (
        select(Chat)
        .where(Chat.id == new_chat.id)
        .options(
            selectinload(Chat.members).selectinload(ChatMember.user),
            selectinload(Chat.group_profile),
        )
    )
    res = await db.execute(stmt)
    created = res.scalar_one()
    return created, True


async def create_group_chat(
    db: AsyncSession,
    creator_id: int,
    name: str,
    member_ids: List[int],
    avatar_url: Optional[str] = None,
) -> Chat:
    """
    Creates a new group conversation with the creator as OWNER.
    """
    new_chat = Chat(chat_type=ChatType.GROUP)
    db.add(new_chat)
    await db.flush()

    # Add group profile
    group_profile = GroupProfile(
        chat_id=new_chat.id,
        name=name,
        avatar_url=avatar_url,
        creator_id=creator_id,
    )
    db.add(group_profile)

    # Add creator as owner
    owner_member = ChatMember(
        chat_id=new_chat.id,
        user_id=creator_id,
        role=MemberRole.OWNER,
    )
    db.add(owner_member)

    # Add initial members (excluding duplicate creator)
    unique_members = set(m for m in member_ids if m != creator_id)
    for uid in unique_members:
        member = ChatMember(
            chat_id=new_chat.id,
            user_id=uid,
            role=MemberRole.MEMBER,
        )
        db.add(member)

    await db.commit()

    # Fetch with relationships
    stmt = (
        select(Chat)
        .where(Chat.id == new_chat.id)
        .options(
            selectinload(Chat.members).selectinload(ChatMember.user),
            selectinload(Chat.group_profile),
        )
    )
    res = await db.execute(stmt)
    return res.scalar_one()


async def get_user_chat_member(
    db: AsyncSession, chat_id: int, user_id: int
) -> Optional[ChatMember]:
    """Retrieves membership record for authorization check."""
    stmt = select(ChatMember).where(
        and_(ChatMember.chat_id == chat_id, ChatMember.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_chat_participant_ids(db: AsyncSession, chat_id: int) -> List[int]:
    """Retrieves all user IDs in a chat."""
    stmt = select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
