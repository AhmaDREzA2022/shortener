from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class ShortenRequest(BaseModel):
    url: HttpUrl

class LinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    url: str
    short_url: str
    clicks: int
    created_at: datetime
