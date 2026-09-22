from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    avatar_url: Optional[str] = None


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    avatar_url: Optional[str] = None
    is_online: bool
    is_active: bool
    last_seen: datetime
    created_at: datetime


class UserUpdate(BaseModel):
    avatar_url: Optional[str] = None


class UserSearchResponse(BaseModel):
    users: list[UserPublic]
