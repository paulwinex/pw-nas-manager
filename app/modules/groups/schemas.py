from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import AccessLevel

NAME_PATTERN = r"^[a-z][a-z0-9_-]{1,31}$"


class GroupCreate(BaseModel):
    name: str = Field(pattern=NAME_PATTERN)


class GroupOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    is_personal: bool


class MemberCreate(BaseModel):
    user_id: str
    access_level: AccessLevel = AccessLevel.RO
    expires_at: datetime | None = None


class MemberUpdate(BaseModel):
    access_level: AccessLevel | None = None
    expires_at: datetime | None = None


class MemberOut(BaseModel):
    user_id: str
    username: str
    access_level: AccessLevel
    expires_at: datetime | None = None


class LinkShare(BaseModel):
    share_id: str
