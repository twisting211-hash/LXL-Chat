from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.call import CallStatus, CallType


class CallInitiate(BaseModel):
    receiver_id: int
    chat_id: Optional[int] = None
    call_type: CallType = CallType.AUDIO


class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    caller_id: int
    receiver_id: int
    chat_id: Optional[int] = None
    call_type: CallType
    status: CallStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
