from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.deps import get_current_active_user
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserPublic, UserUpdate
from app.utils.exceptions import not_found

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get(
    "/search",
    response_model=List[UserPublic],
    summary="Search users by username",
    description="Searches for users by matching partial username (case-insensitive). Excludes sensitive fields.",
)
async def search_users(
    username: str = Query(..., min_length=1, description="Username query string"),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    query_str = username.strip().lower()
    stmt = (
        select(User)
        .where(
            func.lower(User.username).like(f"%{query_str}%"),
            User.is_active == True,
            User.id != current_user.id,
        )
        .order_by(User.username.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()
    return users


@router.get(
    "/{user_id}",
    response_model=UserPublic,
    summary="Get user by ID",
    description="Fetches public profile for a specific user ID.",
)
async def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.id == user_id, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise not_found("User")
    return user


@router.patch(
    "/me/avatar",
    response_model=UserPublic,
    summary="Update current user avatar",
    description="Updates the profile picture URL for the authenticated user.",
)
async def update_avatar(
    payload: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.avatar_url = payload.avatar_url
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user
