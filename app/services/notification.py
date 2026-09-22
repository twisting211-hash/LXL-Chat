import logging
from typing import Any, Dict, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Global flag to track Firebase initialization status
_firebase_initialized = False


def _init_firebase_if_needed():
    global _firebase_initialized
    if _firebase_initialized:
        return True

    if not (
        settings.FIREBASE_PROJECT_ID
        and settings.FIREBASE_CLIENT_EMAIL
        and settings.FIREBASE_PRIVATE_KEY
    ):
        logger.info(
            "Firebase Cloud Messaging credentials not set. Push notifications will run in dry-run mode."
        )
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Handle escaped newlines in private key from environment variables
        private_key = settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n")

        cred_dict = {
            "type": "service_account",
            "project_id": settings.FIREBASE_PROJECT_ID,
            "private_key": private_key,
            "client_email": settings.FIREBASE_CLIENT_EMAIL,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin SDK successfully initialized.")
        return True
    except Exception as e:
        logger.warning(f"Failed to initialize Firebase Admin SDK: {e}")
        return False


class NotificationService:
    """
    Push notification service abstracting Firebase Cloud Messaging (FCM).
    Delivers notifications to registered devices (iOS, Android, Web).
    """

    async def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> int:
        """
        Sends push notification to multiple device tokens.
        Returns the number of successful deliveries.
        """
        if not tokens:
            return 0

        if not _init_firebase_if_needed():
            logger.debug(
                f"[FCM Dry-Run] Title: {title} | Body: {body} | Recipients: {len(tokens)}"
            )
            return len(tokens)

        try:
            from firebase_admin import messaging

            message = messaging.MulticastMessage(
                tokens=tokens,
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="default",
                        channel_id="messages",
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound="default", badge=1)
                    )
                ),
            )
            response = messaging.send_each_for_multicast(message)
            logger.info(
                f"FCM batch sent: {response.success_count} success, {response.failure_count} failures."
            )
            return response.success_count
        except Exception as e:
            logger.error(f"Error sending Firebase notification: {e}")
            return 0

    async def notify_new_message(
        self,
        tokens: List[str],
        sender_username: str,
        chat_title: str,
        chat_id: int,
        message_snippet: str,
        message_id: int,
    ):
        title = f"{sender_username} ({chat_title})" if chat_title != sender_username else sender_username
        data = {
            "type": "new_message",
            "chat_id": str(chat_id),
            "message_id": str(message_id),
            "sender_username": sender_username,
        }
        await self.send_multicast(tokens, title=title, body=message_snippet, data=data)

    async def notify_incoming_call(
        self,
        tokens: List[str],
        caller_username: str,
        call_id: int,
        call_type: str,
    ):
        title = f"Incoming {call_type.capitalize()} Call"
        body = f"{caller_username} is calling you..."
        data = {
            "type": "incoming_call",
            "call_id": str(call_id),
            "caller_username": caller_username,
            "call_type": call_type,
        }
        await self.send_multicast(tokens, title=title, body=body, data=data)

    async def notify_server_online(
        self,
        tokens: List[str],
        status_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Sends '🟢 Server is online' push notification exclusively to the owner's devices.
        Used when the server starts up from Render sleep.
        """
        title = "🟢 Server is online"
        body = "Your private messenger backend is online and ready on Render."
        data = {
            "type": "server:online",
            "status": "online",
            "service": "messenger-backend",
        }
        if status_data:
            data.update({k: str(v) for k, v in status_data.items()})
        await self.send_multicast(tokens, title=title, body=body, data=data)


notification_service = NotificationService()
