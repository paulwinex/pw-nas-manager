from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, Share, User, UserGroup, UserGroupExpiration
from app.modules.samba import sync_engine
from app.modules.stats.schemas import ExpiringMember, StatsResponse

EXPIRY_WINDOW_DAYS = 7


async def compute_stats(session: AsyncSession) -> StatsResponse:
    users_count = await session.scalar(select(func.count()).select_from(User)) or 0
    admins_count = (
        await session.scalar(
            select(func.count()).select_from(User).where(User.is_admin.is_(True))
        )
        or 0
    )
    groups_count = (
        await session.scalar(
            select(func.count())
            .select_from(Group)
            .where(Group.is_personal.is_(False))
        )
        or 0
    )
    personal_groups_count = (
        await session.scalar(
            select(func.count()).select_from(Group).where(Group.is_personal.is_(True))
        )
        or 0
    )
    shares_count = await session.scalar(select(func.count()).select_from(Share)) or 0
    memberships_count = (
        await session.scalar(
            select(func.count())
            .select_from(UserGroup)
            .join(Group, Group.id == UserGroup.group_id)
            .where(Group.is_personal.is_(False))
        )
        or 0
    )

    registry_shares_count = len(await sync_engine.registry_state())

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=EXPIRY_WINDOW_DAYS)
    rows = (
        await session.execute(
            select(
                UserGroupExpiration.user_id,
                User.username,
                UserGroupExpiration.group_id,
                Group.name,
                UserGroup.access_level,
                UserGroupExpiration.expires_at,
            )
            .join(User, User.id == UserGroupExpiration.user_id)
            .join(Group, Group.id == UserGroupExpiration.group_id)
            .join(
                UserGroup,
                (UserGroup.user_id == UserGroupExpiration.user_id)
                & (UserGroup.group_id == UserGroupExpiration.group_id),
            )
            .where(
                UserGroupExpiration.is_active.is_(True),
                UserGroupExpiration.expires_at >= now,
                UserGroupExpiration.expires_at <= horizon,
            )
            .order_by(UserGroupExpiration.expires_at)
        )
    ).all()
    expiring = [
        ExpiringMember(
            user_id=user_id,
            username=username,
            group_id=group_id,
            group_name=group_name,
            access_level=access_level.value,
            expires_at=expires_at,
        )
        for user_id, username, group_id, group_name, access_level, expires_at in rows
    ]

    return StatsResponse(
        users_count=users_count,
        admins_count=admins_count,
        groups_count=groups_count,
        personal_groups_count=personal_groups_count,
        shares_count=shares_count,
        registry_shares_count=registry_shares_count,
        memberships_count=memberships_count,
        expiring_memberships=expiring,
    )