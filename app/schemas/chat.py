from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.chat import ChatType, MemberRole
from app.schemas.message import MessageResponse


class ChatCreateDirect(BaseModel):
    target_user_id: int


class ChatCreateGroup(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    member_ids: List[int] = Field(default_factory=list)
    avatar_url: Optional[str] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    avatar_url: Optional[str] = None


class AddMembersRequest(BaseModel):
    user_ids: List[int] = Field(..., min_length=1)


class ChatMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    avatar_url: Optional[str] = None
    role: MemberRole
    joined_at: datetime
    is_online: bool
    last_seen: datetime


class GroupProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    avatar_url: Optional[str] = None
    creator_id: Optional[int] = None
    created_at: datetime


class ChatDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_type: ChatType
    title: str
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    members: List[ChatMemberResponse]
    group_profile: Optional[GroupProfileResponse] = None


class ChatListItem(BaseModel):
    id: int
    chat_type: ChatType
    title: str
    avatar_url: Optional[str] = None
    updated_at: datetime
    unread_count: int
    last_message: Optional[MessageResponse] = None
    other_user: Optional[ChatMemberResponse] = None  # populated for direct chats


class ChatListResponse(BaseModel):
    chats: List[ChatListItem]
