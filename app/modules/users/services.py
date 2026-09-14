from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound
from app.core.security import hash_password
from app.core.settings import get_settings
from app.db.models import AccessLevel, Group, GroupShare, User, UserGroup
from app.modules.samba import os_manager, sync_engine
from app.modules.users.schemas import UserCreate


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.scalars(select(User).order_by(User.username))
    return list(result.all())


async def get_user(session: AsyncSession, user_id: str) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound(f"User '{user_id}' not found")
    return user


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    existing = await session.scalar(
        select(User).where(User.username == data.username)
    )
    if existing is not None:
        raise Conflict(f"Username '{data.username}' already exists")

    await os_manager.create_user(data.username)
    try:
        await os_manager.smbpasswd_add(data.username, data.password)
    except Exception:
        await os_manager.delete_user(data.username)
        raise

    user = User(
        username=data.username,
        password_hash=await hash_password(data.password),
        is_admin=data.is_admin,
    )
    session.add(user)

    personal_group = Group(name=data.username, is_personal=True)
    session.add(personal_group)
    await session.flush()
    session.add(
        UserGroup(
            user_id=user.id,
            group_id=personal_group.id,
            access_level=AccessLevel.RW,
        )
    )
    await session.commit()

    await sync_engine.sync(session)
    return user


async def change_password(
    session: AsyncSession, user_id: str, new_password: str
) -> User:
    user = await get_user(session, user_id)
    user.password_hash = await hash_password(new_password)
    await os_manager.smbpasswd_delete(user.username)
    await os_manager.smbpasswd_add(user.username, new_password)
    await session.commit()

    await sync_engine.sync(session)
    return user


async def delete_user(session: AsyncSession, user_id: str) -> None:
    user = await get_user(session, user_id)
    if user.is_admin:
        admin_count = (
            await session.execute(
                select(func.count()).select_from(User).where(User.is_admin.is_(True))
            )
        ).scalar_one()
        if admin_count <= 1:
            raise Conflict("Cannot delete the last admin")

    username = user.username
    personal_group = await session.scalar(
        select(Group).where(Group.name == username, Group.is_personal.is_(True))
    )
    if personal_group is not None:
        await session.execute(
            delete(GroupShare).where(GroupShare.group_id == personal_group.id)
        )
        await session.delete(personal_group)

    await session.execute(delete(UserGroup).where(UserGroup.user_id == user.id))
    await session.delete(user)
    await session.commit()

    await os_manager.smbpasswd_delete(username)
    await os_manager.delete_user(username)

    await sync_engine.sync(session)


async def list_user_shares(
    session: AsyncSession, username: str
) -> list[dict[str, str | int]]:
    user = await session.scalar(select(User).where(User.username == username))
    if user is None:
        raise NotFound(f"User '{username}' not found")

    settings = get_settings()
    target = await sync_engine.compute_target(session)
    shares: list[dict[str, str | int]] = []
    for name, share in sorted(target.items()):
        if username not in share.valid_users:
            continue
        access = "RW" if username in share.write_list else "RO"
        shares.append({
            "name": name,
            "host": settings.nas_host,
            "port": settings.nas_port,
            "access": access,
        })
    return shares


async def build_mount_script(
    session: AsyncSession, username: str
) -> dict[str, object]:
    shares_raw = await list_user_shares(session, username)

    settings = get_settings()
    host = settings.nas_host
    port = settings.nas_port

    shares = [
        {"name": s["name"], "path": rf"\\{s['host']}\{s['name']}", "access": s["access"]}
        for s in shares_raw
    ]

    linux_lines = [
        "#!/usr/bin/env bash",
        "# Root directory for all mounts: from MOUNT_ROOT env or mandatory prompt",
        'if [ -n "${MOUNT_ROOT:-}" ]; then',
        '  echo "MOUNT_ROOT from environment: ${MOUNT_ROOT}"',
        "else",
        '  MOUNT_ROOT=""',
        '  while [ -z "${MOUNT_ROOT}" ]; do',
        '    read -r -p "Mount root path (e.g. /mnt): " MOUNT_ROOT',
        "  done",
        "fi",
        'sudo mkdir -p "${MOUNT_ROOT}"',
        'echo "Mount root: ${MOUNT_ROOT}"',
        "",
        f'read -r -p "Password for {username}: " PASWD',
        "",
    ]
    for s in shares:
        linux_lines.extend(
            [
                f"# {s['name']}",
                f'TARGET_DIR="${{MOUNT_ROOT}}/{s["name"]}"',
                'sudo mkdir -p "${TARGET_DIR}"',
                f'sudo mount -t cifs //{host}/{s["name"]} "${{TARGET_DIR}}" '
                f"-o username={username},password=${{PASWD}},port={port}"
                ",uid=$(id -u),gid=$(id -g),dir_mode=0755,file_mode=0644",
                f'echo "Mounted //{host}/{s["name"]} at ${{TARGET_DIR}}"',
                "",
            ]
        )

    if port == 445:
        windows_script = "\n".join(
            f"net use * \\\\{host}\\{s['name']} /user:{username}" for s in shares
        )
    else:
        # net use doesn't support a custom SMB port; go through a local portproxy.
        windows_script = "\n".join(
            [
                "# Windows 'net use' does not support a custom SMB port.",
                "# Run this once as Administrator to forward 127.0.0.1:445 to the NAS:",
                f"#   netsh interface portproxy add v4tov4 listenport=445 listenaddress=127.0.0.1",
                f"#     connectport={port} connectaddress={host}",
                "",
            ]
            + [
                f"net use * \\\\127.0.0.1\\{s['name']} /user:{username}"
                for s in shares
            ]
        )

    return {
        "username": username,
        "host": host,
        "port": port,
        "shares": shares,
        "windows_script": windows_script,
        "linux_script": "\n".join(linux_lines),
    }
