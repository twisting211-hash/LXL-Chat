from typing import List, Optional, Union
from pydantic import BaseModel


class IceServer(BaseModel):
    urls: Union[str, List[str]]
    username: Optional[str] = None
    credential: Optional[str] = None


class WebRTCConfigResponse(BaseModel):
    ice_servers: List[IceServer]
