from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.device import DevicePlatform


class DeviceTokenRegister(BaseModel):
    device_token: str
    platform: DevicePlatform = DevicePlatform.ANDROID


class DeviceTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    device_token: str
    platform: DevicePlatform
    created_at: datetime
    updated_at: datetime
