import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,30}[a-z0-9]$")


class ShortenBase(BaseModel):
    url: HttpUrl
    alias: str | None = None

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not ALIAS_RE.match(v):
            raise ValueError(
                "Alias must be 3-32 chars: lowercase letters, digits, dash, underscore; "
                "must start and end with a letter or digit"
            )
        return v

class ShortenForm(ShortenBase):
    pass


class ShortenRequest(ShortenBase):
    pass

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
