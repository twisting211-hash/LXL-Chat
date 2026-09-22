from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.deps import get_current_active_user
from app.database import get_db
from app.models.device import DevicePlatform, DeviceToken
from app.models.user import User
from app.schemas.device import DeviceTokenRegister, DeviceTokenResponse

router = APIRouter(prefix="/api/devices", tags=["Push Notifications"])


@router.post(
    "/register",
    response_model=DeviceTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Register device push token",
    description="Registers or updates the mobile device FCM push token for the authenticated user.",
)
async def register_device(
    payload: DeviceTokenRegister,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clean_token = payload.device_token.strip()
    if not clean_token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="device_token cannot be blank.",
        )

    # Check if token already exists for user
    stmt = select(DeviceToken).where(
        DeviceToken.user_id == current_user.id,
        DeviceToken.device_token == clean_token,
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing:
        existing.platform = payload.platform
        existing.updated_at = now
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return existing

    new_device = DeviceToken(
        user_id=current_user.id,
        device_token=clean_token,
        platform=payload.platform,
        created_at=now,
        updated_at=now,
    )
    db.add(new_device)
    await db.commit()
    await db.refresh(new_device)

    return new_device


@router.delete(
    "/{token}",
    status_code=status.HTTP_200_OK,
    summary="Unregister device push token",
    description="De-registers a push token upon user logout from the mobile client.",
)
async def unregister_device(
    token: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = delete(DeviceToken).where(
        DeviceToken.user_id == current_user.id,
        DeviceToken.device_token == token.strip(),
    )
    await db.execute(stmt)
    await db.commit()

    return {"status": "ok", "message": "Device token unregistered successfully"}
