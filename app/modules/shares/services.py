from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound
from app.db.models import GroupShare, Share
from app.modules.samba import os_manager, sync_engine


async def list_shares(session: AsyncSession) -> list[Share]:
    result = await session.scalars(select(Share).order_by(Share.name))
    return list(result.all())


async def available_dirs(session: AsyncSession) -> list[str]:
    registered = set((await session.scalars(select(Share.path))).all())
    return [
        name for name in os_manager.scan_share_dirs() if name not in registered
    ]


async def get_share(session: AsyncSession, share_id: str) -> Share:
    share = await session.get(Share, share_id)
    if share is None:
        raise NotFound(f"Share '{share_id}' not found")
    return share


async def create_share(session: AsyncSession, name: str) -> Share:
    existing = await session.scalar(
        select(Share).where((Share.name == name) | (Share.path == name))
    )
    if existing is not None:
        raise Conflict(f"Share '{name}' already exists")

    await os_manager.ensure_dir(name)

    share = Share(name=name, path=name)
    session.add(share)
    await session.commit()

    await sync_engine.sync(session)
    return share


async def delete_share(session: AsyncSession, share_id: str) -> None:
    share = await get_share(session, share_id)

    await session.execute(delete(GroupShare).where(GroupShare.share_id == share.id))
    await session.delete(share)
    await session.commit()

    await sync_engine.sync(session)