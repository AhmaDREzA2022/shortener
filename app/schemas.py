from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


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

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime