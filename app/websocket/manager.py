import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections per user ID.
    Supports multi-device connectivity (multiple WebSockets per user),
    real-time event broadcasting, and WebRTC peer-to-peer signaling.
    """

    def __init__(self):
        # Maps user_id -> Set of active WebSocket instances
        self.active_connections: Dict[int, Set[WebSocket]] = defaultdict(set)
        # Maps user_id -> set of active call IDs they are currently participating in
        self.active_calls: Dict[int, Optional[int]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> bool:
        """
        Registers a new WebSocket connection for a user.
        Returns True if this is the user's first connection (transitioned to online).
        """
        await websocket.accept()
        is_first = len(self.active_connections[user_id]) == 0
        self.active_connections[user_id].add(websocket)
        logger.info(
            f"User {user_id} connected (Active sockets: {len(self.active_connections[user_id])})"
        )
        return is_first

    async def disconnect(self, user_id: int, websocket: WebSocket) -> bool:
        """
        Removes a WebSocket connection.
        Returns True if the user has no more active connections (transitioned to offline).
        """
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                self.active_calls.pop(user_id, None)
                logger.info(f"User {user_id} disconnected (Now offline)")
                return True
        return False

    def is_user_online(self, user_id: int) -> bool:
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

    def get_online_user_ids(self) -> Set[int]:
        return set(self.active_connections.keys())

    async def send_event(self, websocket: WebSocket, event: str, data: Any):
        """Sends a JSON-encoded event to a single WebSocket."""
        payload = {"event": event, "data": data}
        try:
            await websocket.send_text(json.dumps(payload, default=str))
        except Exception as e:
            logger.debug(f"Failed to send socket message: {e}")

    async def send_to_user(self, user_id: int, event: str, data: Any):
        """Sends an event to all active devices of a specific user."""
        if user_id not in self.active_connections:
            return

        dead_sockets = set()
        sockets = list(self.active_connections[user_id])
        for ws in sockets:
            try:
                await self.send_event(ws, event, data)
            except Exception:
                dead_sockets.add(ws)

        for ws in dead_sockets:
            self.active_connections[user_id].discard(ws)

    async def broadcast_to_users(
        self,
        user_ids: List[int],
        event: str,
        data: Any,
        exclude_user_id: Optional[int] = None,
    ):
        """Broadcasts an event to a list of users (e.g., chat members)."""
        for uid in set(user_ids):
            if exclude_user_id is not None and uid == exclude_user_id:
                continue
            await self.send_to_user(uid, event, data)

    # --- Call state helpers ---
    def set_user_in_call(self, user_id: int, call_id: int):
        self.active_calls[user_id] = call_id

    def clear_user_call(self, user_id: int):
        self.active_calls.pop(user_id, None)

    def is_user_busy(self, user_id: int) -> bool:
        return self.active_calls.get(user_id) is not None


manager = ConnectionManager()
