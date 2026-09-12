from dataclasses import dataclass, field

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models import AccessLevel, GroupShare, Share, User, UserGroup
from app.modules.samba import registry_manager


@dataclass
class TargetShare:
    path: str
    valid_users: list[str] = field(default_factory=list)
    write_list: list[str] = field(default_factory=list)
    read_list: list[str] = field(default_factory=list)


class SyncReport(BaseModel):
    added: list[str] = []
    removed: list[str] = []
    updated: list[str] = []
    params_set: dict[str, list[str]] = {}


async def compute_target(session: AsyncSession) -> dict[str, TargetShare]:
    settings = get_settings()
    shares = (await session.scalars(select(Share).order_by(Share.name))).all()

    target: dict[str, TargetShare] = {}
    for share in shares:
        rows = (
            await session.execute(
                select(User.username, UserGroup.access_level)
                .join(UserGroup, UserGroup.user_id == User.id)
                .join(GroupShare, GroupShare.group_id == UserGroup.group_id)
                .where(GroupShare.share_id == share.id)
            )
        ).all()

        levels: dict[str, set[AccessLevel]] = {}
        for username, level in rows:
            levels.setdefault(username, set()).add(level)

        valid_users = sorted(levels)
        write_list = sorted(
            user for user, user_levels in levels.items() if AccessLevel.RW in user_levels
        )
        read_list = [user for user in valid_users if user not in write_list]

        target[share.name] = TargetShare(
            path=str(settings.share_mount_path / share.path),
            valid_users=valid_users,
            write_list=write_list,
            read_list=read_list,
        )
    return target


def _desired_params(t: TargetShare) -> dict[str, str]:
    settings = get_settings()
    return {
        "force user": settings.samba_service_user,
        "browseable": "yes",
        "valid users": " ".join(t.valid_users),
        "write list": " ".join(t.write_list),
        "read list": " ".join(t.read_list),
    }


async def sync(session: AsyncSession) -> SyncReport:
    target = await compute_target(session)
    current_names = set(await registry_manager.list_shares())

    report = SyncReport()

    for name in sorted(current_names):
        share_target = target.get(name)
        if share_target is None or not share_target.valid_users:
            await registry_manager.del_share(name)
            report.removed.append(name)

    existing = current_names - set(report.removed)

    for name, share_target in sorted(target.items()):
        if not share_target.valid_users:
            continue

        params = _desired_params(share_target)

        if name not in existing:
            await registry_manager.add_share(name, share_target.path)
            report.added.append(name)
            for key, value in sorted(params.items()):
                await registry_manager.set_parm(name, key, value)
            report.params_set[name] = sorted(params)
            continue

        current_params = await registry_manager.show_share(name)
        desired = {"path": share_target.path} | params
        changed = [key for key, value in desired.items() if current_params.get(key) != value]
        if changed:
            for key in sorted(changed):
                await registry_manager.set_parm(name, key, desired[key])
            report.updated.append(name)
            report.params_set[name] = sorted(changed)

    return report


async def registry_state() -> dict[str, dict[str, str]]:
    state: dict[str, dict[str, str]] = {}
    for name in await registry_manager.list_shares():
        state[name] = await registry_manager.show_share(name)
    return state
