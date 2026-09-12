from datetime import datetime

from pydantic import BaseModel, Field

USERNAME_PATTERN = r"^[a-z][a-z0-9_-]{1,31}$"


class UserCreate(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    password: str
    is_admin: bool = False


class PasswordChange(BaseModel):
    new_password: str


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    username: str
    created_at: datetime
    is_admin: bool
