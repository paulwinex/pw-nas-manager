from datetime import datetime

from pydantic import BaseModel


class ExpiringMember(BaseModel):
    user_id: str
    username: str
    group_id: str
    group_name: str
    access_level: str
    expires_at: datetime


class StatsResponse(BaseModel):
    users_count: int
    admins_count: int
    groups_count: int
    personal_groups_count: int
    shares_count: int
    registry_shares_count: int
    memberships_count: int
    expiring_memberships: list[ExpiringMember]