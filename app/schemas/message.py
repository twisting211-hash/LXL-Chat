from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.message import MessageType


class MessageCreate(BaseModel):
    message_type: MessageType = MessageType.TEXT
    text: Optional[str] = Field(None, max_length=10000)
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    reply_to_id: Optional[int] = None


class MessageUpdate(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)


class MessageSenderPublic(BaseModel):
    id: int
    username: str
    avatar_url: Optional[str] = None


class MessageReplySnippet(BaseModel):
    id: int
    sender_id: int
    sender_username: Optional[str] = None
    message_type: MessageType
    text: Optional[str] = None
    file_name: Optional[str] = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    sender_id: int
    sender: Optional[MessageSenderPublic] = None
    message_type: MessageType
    text: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    reply_to_id: Optional[int] = None
    reply_to: Optional[MessageReplySnippet] = None
    
    created_at: datetime
    edited_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    has_more: bool
    next_cursor: Optional[int] = None
