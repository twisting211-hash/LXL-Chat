import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger("messenger.server_status")


class ServerStatusService:
    """
    Manages server lifecycle state (starting, online, offline), cold-start detection,
    and owner-only server:online notifications for Render sleep/wake cycles.
    """

    def __init__(self):
        self.status: str = "starting"
        self.service_name: str = "messenger-backend"
        self.started_at: Optional[datetime] = None
        self._boot_count: int = 0

    def mark_starting(self):
        """Called when server begins initialization."""
        self.status = "starting"
        logger.info("[ServerStatus] Server state set to: STARTING")

    def mark_online(self):
        """Called when FastAPI lifespan startup finishes."""
        self.status = "online"
        self.started_at = datetime.now(timezone.utc)
        self._boot_count += 1
        logger.info(
            f"[ServerStatus] Server state set to: ONLINE (Boot #{self._boot_count} at {self.started_at.isoformat()})"
        )

    def mark_offline(self):
        """Called when FastAPI lifespan shuts down."""
        self.status = "offline"
        logger.info("[ServerStatus] Server state set to: OFFLINE")

    def is_online(self) -> bool:
        return self.status == "online"

    def get_status(self) -> str:
        return self.status

    def get_uptime_seconds(self) -> float:
        if not self.started_at:
            return 0.0
        return round((datetime.now(timezone.utc) - self.started_at).total_seconds(), 2)

    def is_owner(self, username: Optional[str] = None, user_id: Optional[int] = None) -> bool:
        """
        Determines if the given user is the designated owner.
        Configured via OWNER_USERNAME environment variable.
        Never checks hardcoded credentials or passwords.
        """
        owner_username = (settings.OWNER_USERNAME or "").strip().lower()
        if not owner_username:
            return False

        if username and username.strip().lower() == owner_username:
            return True

        return False

    def get_server_online_event_payload(self) -> Dict[str, Any]:
        """Payload for the 'server:online' event."""
        return {
            "service": self.service_name,
            "status": "online",
            "message": "🟢 Server is online",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": self.get_uptime_seconds(),
        }

    async def notify_owner_server_online(
        self,
        db: Optional[AsyncSession] = None,
        fcm_tokens: Optional[List[str]] = None,
    ) -> bool:
        """
        Sends the server:online event specifically and exclusively to the owner's account.
        Will NOT broadcast to other users.
        Dispatches via:
        1. WebSocket if the owner is currently connected
        2. FCM push notification if device tokens are available
        """
        from app.websocket.manager import manager
        from app.services.notification import notification_service

        owner_username = (settings.OWNER_USERNAME or "").strip().lower()
        if not owner_username:
            logger.debug("[ServerStatus] No OWNER_USERNAME configured. Skipping owner notification.")
            return False

        logger.info(f"[ServerStatus] Preparing owner notification for: {owner_username}")

        owner_id: Optional[int] = None
        device_tokens: List[str] = list(fcm_tokens or [])

        if db:
            from app.models.user import User
            from app.models.device import DeviceToken

            stmt = select(User).where(User.username == owner_username)
            res = await db.execute(stmt)
            owner_user = res.scalar_one_or_none()

            if owner_user:
                owner_id = owner_user.id
                if not device_tokens:
                    token_stmt = select(DeviceToken.token).where(DeviceToken.user_id == owner_id)
                    token_res = await db.execute(token_stmt)
                    device_tokens = list(token_res.scalars().all())

        payload = self.get_server_online_event_payload()

        # 1. Dispatch WebSocket event if owner has active socket connections
        if owner_id and manager.is_user_online(owner_id):
            await manager.send_to_user(owner_id, "server:online", payload)
            logger.info(f"[ServerStatus] Dispatched 'server:online' WebSocket event to owner (user_id={owner_id}).")

        # 2. Dispatch Push Notification via FCM if tokens exist
        if device_tokens:
            await notification_service.notify_server_online(
                tokens=device_tokens,
                status_data=payload,
            )
            logger.info(f"[ServerStatus] Dispatched 'server:online' push notification to {len(device_tokens)} device(s).")

        return True


server_status_service = ServerStatusService()
