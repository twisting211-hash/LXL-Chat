from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CallType(str, PyEnum):
    AUDIO = "audio"
    VIDEO = "video"


class CallStatus(str, PyEnum):
    INITIATED = "initiated"
    RINGING = "ringing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ENDED = "ended"
    MISSED = "missed"
    BUSY = "busy"


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    caller_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    receiver_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chat_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True, index=True
    )
    call_type: Mapped[CallType] = mapped_column(
        Enum(CallType, name="call_type_enum"),
        default=CallType.AUDIO,
        nullable=False,
    )
    status: Mapped[CallStatus] = mapped_column(
        Enum(CallStatus, name="call_status_enum"),
        default=CallStatus.INITIATED,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_calls_caller_receiver", "caller_id", "receiver_id"),
        Index("idx_calls_started_at", "started_at"),
    )
