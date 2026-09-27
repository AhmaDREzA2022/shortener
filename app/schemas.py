from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class ShortenBase(BaseModel):
    url: HttpUrl


class ShortenForm(ShortenBase):
    """Parsed from an HTML form (application/x-www-form-urlencoded)."""


class ShortenRequest(ShortenBase):
    """Parsed from a JSON request body."""


class LinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    url: str
    short_url: str
    clicks: int
    created_at: datetime
