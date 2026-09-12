from pydantic import BaseModel, Field

NAME_PATTERN = r"^[a-z][a-z0-9_-]{1,31}$"


class ShareCreate(BaseModel):
    name: str = Field(pattern=NAME_PATTERN)


class ShareOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    path: str