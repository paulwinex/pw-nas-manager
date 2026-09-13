from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound
from app.db.models import (
    AccessLevel,
    Group,
    GroupShare,
    Share,
    User,
    UserGroup,
    UserGroupExpiration,
)
from app.modules.samba import sync_engine
from app.modules.groups.schemas import MemberCreate, MemberUpdate


async def list_groups(session: AsyncSession) -> list[Group]:
    result = await session.scalars(select(Group).order_by(Group.name))
    return list(result.all())


async def get_group(session: AsyncSession, group_id: str) -> Group:
    group = await session.get(Group, group_id)
    if group is None:
        raise NotFound(f"Group '{group_id}' not found")
    return group


async def create_group(session: AsyncSession, name: str) -> Group:
    existing = await session.scalar(select(Group).where(Group.name == name))
    if existing is not None:
        raise Conflict(f"Group '{name}' already exists")

    group = Group(name=name, is_personal=False)
    session.add(group)
    await session.commit()

    await sync_engine.sync(session)
    return group


async def delete_group(session: AsyncSession, group_id: str) -> None:
    group = await get_group(session, group_id)
    if group.is_personal:
        raise Conflict(f"Cannot delete personal group '{group.name}'")

    await session.execute(delete(GroupShare).where(GroupShare.group_id == group.id))
    await session.execute(delete(UserGroup).where(UserGroup.group_id == group.id))
    await session.delete(group)
    await session.commit()

    await sync_engine.sync(session)


async def list_members(session: AsyncSession, group_id: str) -> list[dict[str, object]]:
    await get_group(session, group_id)
    rows = (
        await session.execute(
            select(
                User.id,
                User.username,
                UserGroup.access_level,
                UserGroupExpiration.expires_at,
            )
            .join(UserGroup, UserGroup.user_id == User.id)
            .outerjoin(
                UserGroupExpiration,
                (UserGroupExpiration.user_id == User.id)
                & (UserGroupExpiration.group_id == group_id)
                & (UserGroupExpiration.is_active.is_(True)),
            )
            .where(UserGroup.group_id == group_id)
            .order_by(User.username)
        )
    ).all()
    return [
        {
            "user_id": user_id,
            "username": username,
            "access_level": access_level,
            "expires_at": expires_at,
        }
        for user_id, username, access_level, expires_at in rows
    ]


async def add_member(
    session: AsyncSession, group_id: str, data: MemberCreate
) -> dict[str, object]:
    group = await get_group(session, group_id)
    user = await session.get(User, data.user_id)
    if user is None:
        raise NotFound(f"User '{data.user_id}' not found")

    existing = await session.scalar(
        select(UserGroup).where(
            UserGroup.group_id == group_id, UserGroup.user_id == data.user_id
        )
    )
    if existing is not None:
        raise Conflict(
            f"User '{user.username}' is already a member of group '{group.name}'"
        )

    if group.is_personal:
        member_count = await session.scalar(
            select(func.count()).select_from(UserGroup).where(
                UserGroup.group_id == group_id
            )
        )
        if member_count >= 1:
            raise Conflict(f"Personal group '{group.name}' already has a member")

    session.add(
        UserGroup(
            user_id=data.user_id,
            group_id=group_id,
            access_level=data.access_level,
        )
    )
    if data.expires_at is not None:
        expiration = await session.scalar(
            select(UserGroupExpiration).where(
                UserGroupExpiration.user_id == data.user_id,
                UserGroupExpiration.group_id == group_id,
            )
        )
        if expiration is None:
            session.add(
                UserGroupExpiration(
                    user_id=data.user_id,
                    group_id=group_id,
                    expires_at=data.expires_at,
                    is_active=True,
                )
            )
        else:
            expiration.expires_at = data.expires_at
            expiration.is_active = True
    await session.commit()

    await sync_engine.sync(session)
    return {
        "user_id": data.user_id,
        "username": user.username,
        "access_level": data.access_level,
        "expires_at": data.expires_at,
    }


async def update_member(
    session: AsyncSession, group_id: str, user_id: str, data: MemberUpdate
) -> dict[str, object]:
    group = await get_group(session, group_id)
    membership = await session.scalar(
        select(UserGroup).where(
            UserGroup.group_id == group_id, UserGroup.user_id == user_id
        )
    )
    if membership is None:
        raise NotFound(f"User '{user_id}' is not a member of group '{group.name}'")

    if data.access_level is not None:
        membership.access_level = data.access_level

    expiration = await session.scalar(
        select(UserGroupExpiration).where(
            UserGroupExpiration.user_id == user_id,
            UserGroupExpiration.group_id == group_id,
        )
    )
    if data.expires_at is not None:
        if expiration is None:
            session.add(
                UserGroupExpiration(
                    user_id=user_id,
                    group_id=group_id,
                    expires_at=data.expires_at,
                    is_active=True,
                )
            )
        else:
            expiration.expires_at = data.expires_at
            expiration.is_active = True
    elif expiration is not None:
        expiration.is_active = False
    await session.commit()

    await sync_engine.sync(session)

    user = await session.get(User, user_id)
    assert user is not None
    return {
        "user_id": user_id,
        "username": user.username,
        "access_level": membership.access_level,
        "expires_at": data.expires_at,
    }


async def remove_member(session: AsyncSession, group_id: str, user_id: str) -> None:
    group = await get_group(session, group_id)
    if group.is_personal:
        raise Conflict(f"Cannot remove member from personal group '{group.name}'")

    membership = await session.scalar(
        select(UserGroup).where(
            UserGroup.group_id == group_id, UserGroup.user_id == user_id
        )
    )
    if membership is None:
        raise NotFound(
            f"User '{user_id}' is not a member of group '{group.name}'"
        )

    await session.delete(membership)
    await session.execute(
        UserGroupExpiration.__table__.update()
        .where(
            (UserGroupExpiration.user_id == user_id)
            & (UserGroupExpiration.group_id == group_id)
            & (UserGroupExpiration.is_active.is_(True))
        )
        .values(is_active=False)
    )
    await session.commit()

    await sync_engine.sync(session)


async def sweep_expired_memberships(session: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    expirations = (
        await session.scalars(
            select(UserGroupExpiration).where(
                UserGroupExpiration.is_active.is_(True),
                UserGroupExpiration.expires_at <= now,
            )
        )
    ).all()
    if not expirations:
        return 0

    groups = {g.id: g for g in (await session.scalars(select(Group))).all()}
    for expiration in expirations:
        expiration.is_active = False
        group = groups.get(expiration.group_id)
        if group is None or group.is_personal:
            continue
        await session.execute(
            delete(UserGroup).where(
                (UserGroup.user_id == expiration.user_id)
                & (UserGroup.group_id == expiration.group_id)
            )
        )
    await session.commit()
    return len(expirations)


async def list_group_shares(session: AsyncSession, group_id: str) -> list[Share]:
    await get_group(session, group_id)
    result = await session.scalars(
        select(Share)
        .join(GroupShare, GroupShare.share_id == Share.id)
        .where(GroupShare.group_id == group_id)
        .order_by(Share.name)
    )
    return list(result.all())


async def link_share(session: AsyncSession, group_id: str, share_id: str) -> Share:
    await get_group(session, group_id)
    share = await session.get(Share, share_id)
    if share is None:
        raise NotFound(f"Share '{share_id}' not found")

    existing = await session.scalar(
        select(GroupShare).where(
            GroupShare.group_id == group_id, GroupShare.share_id == share_id
        )
    )
    if existing is None:
        session.add(GroupShare(group_id=group_id, share_id=share_id))
        await session.commit()

    await sync_engine.sync(session)
    return share


async def unlink_share(session: AsyncSession, group_id: str, share_id: str) -> None:
    await get_group(session, group_id)

    link = await session.scalar(
        select(GroupShare).where(
            GroupShare.group_id == group_id, GroupShare.share_id == share_id
        )
    )
    if link is None:
        raise NotFound(
            f"Share '{share_id}' is not linked to group '{group_id}'"
        )

    await session.delete(link)
    await session.commit()

    await sync_engine.sync(session)