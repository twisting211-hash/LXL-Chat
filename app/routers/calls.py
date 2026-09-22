from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.deps import get_current_active_user
from app.config import settings
from app.database import get_db
from app.models.call import Call, CallStatus, CallType
from app.models.device import DeviceToken
from app.models.user import User
from app.schemas.call import CallInitiate, CallResponse
from app.schemas.webrtc import IceServer, WebRTCConfigResponse
from app.services.notification import notification_service
from app.utils.exceptions import not_found
from app.websocket.manager import manager

router = APIRouter(prefix="/api/calls", tags=["Calls & WebRTC"])


@router.get(
    "/config",
    response_model=WebRTCConfigResponse,
    summary="Get WebRTC ICE server configuration",
    description="Returns STUN and TURN server credentials for initializing RTCPeerConnection in the client app.",
)
async def get_webrtc_config(
    current_user: User = Depends(get_current_active_user),
):
    servers: List[IceServer] = []

    # Add primary STUN
    if settings.STUN_SERVER:
        servers.append(IceServer(urls=settings.STUN_SERVER))

    # Add secondary STUN
    if settings.STUN_SERVER_SECONDARY:
        servers.append(IceServer(urls=settings.STUN_SERVER_SECONDARY))

    # Add TURN if configured
    if settings.TURN_SERVER:
        turn_entry = IceServer(
            urls=settings.TURN_SERVER,
            username=settings.TURN_USERNAME or None,
            credential=settings.TURN_PASSWORD or None,
        )
        servers.append(turn_entry)

    return WebRTCConfigResponse(ice_servers=servers)


@router.post(
    "/initiate",
    response_model=CallResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate call record",
    description="Creates a call session record before sending the WebRTC call:offer over WebSocket.",
)
async def initiate_call(
    payload: CallInitiate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.receiver_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot place a call to yourself.",
        )

    # Check receiver exists
    rec_res = await db.execute(select(User).where(User.id == payload.receiver_id, User.is_active == True))
    receiver = rec_res.scalar_one_or_none()
    if not receiver:
        raise not_found("Receiver")

    # Check if receiver is already busy
    if manager.is_user_busy(payload.receiver_id):
        raise HTTPException(
            status_code=status.HTTP_486_BUSY_HERE,
            detail="User is currently engaged in another call.",
        )

    now = datetime.now(timezone.utc)
    call = Call(
        caller_id=current_user.id,
        receiver_id=payload.receiver_id,
        chat_id=payload.chat_id,
        call_type=payload.call_type,
        status=CallStatus.INITIATED,
        started_at=now,
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)

    # If receiver is not currently connected to WebSocket, trigger high-priority push notification
    if not manager.is_user_online(payload.receiver_id):
        tok_stmt = select(DeviceToken.device_token).where(DeviceToken.user_id == payload.receiver_id)
        tok_res = await db.execute(tok_stmt)
        tokens = list(tok_res.scalars().all())
        if tokens:
            await notification_service.notify_incoming_call(
                tokens=tokens,
                caller_username=current_user.username,
                call_id=call.id,
                call_type=payload.call_type.value,
            )

    return call


@router.post(
    "/{call_id}/end",
    response_model=CallResponse,
    summary="End call session",
    description="Updates the call record with final status and calculated duration.",
)
async def end_call(
    call_id: int,
    final_status: CallStatus = Query(CallStatus.ENDED),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Call).where(Call.id == call_id)
    res = await db.execute(stmt)
    call = res.scalar_one_or_none()
    if not call:
        raise not_found("Call")

    if current_user.id not in (call.caller_id, call.receiver_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this call.",
        )

    now = datetime.now(timezone.utc)
    call.ended_at = now
    call.status = final_status
    if call.started_at:
        call.duration_seconds = int((now - call.started_at).total_seconds())

    manager.clear_user_call(call.caller_id)
    manager.clear_user_call(call.receiver_id)

    db.add(call)
    await db.commit()
    await db.refresh(call)

    return call


@router.get(
    "/history",
    response_model=List[CallResponse],
    summary="Get call history",
    description="Returns incoming and outgoing call records for the authenticated user.",
)
async def get_call_history(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Call)
        .where(
            or_(Call.caller_id == current_user.id, Call.receiver_id == current_user.id)
        )
        .order_by(desc(Call.started_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    calls = res.scalars().all()
    return calls
