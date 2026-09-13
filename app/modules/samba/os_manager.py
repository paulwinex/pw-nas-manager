import asyncio
from pathlib import Path

from app.core.exceptions import Conflict, SambaCommandError
from app.core.settings import get_settings


async def run_command(
    args: list[str], stdin_data: str | None = None
) -> tuple[int, str, str]:
    """Single seam for every OS/samba subprocess call.

    Returns (returncode, stdout, stderr). Tests patch this one function.
    """
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE if stdin_data is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate(
        stdin_data.encode() if stdin_data is not None else None
    )
    return (
        proc.returncode or 0,
        out.decode(errors="replace"),
        err.decode(errors="replace"),
    )


async def user_exists(username: str) -> bool:
    rc, _, _ = await run_command(["id", username])
    return rc == 0


async def create_user(username: str) -> None:
    if await user_exists(username):
        raise Conflict(f"OS user '{username}' already exists")
    rc, _, err = await run_command(
        ["useradd", "-M", "-s", "/usr/sbin/nologin", username]
    )
    if rc != 0:
        raise SambaCommandError(err.strip(), cmd=f"useradd {username}")


async def delete_user(username: str) -> None:
    # Best-effort: tolerate users that never had an OS account (e.g. seeded admin).
    await run_command(["userdel", username])


async def smbpasswd_add(username: str, password: str) -> None:
    rc, _, err = await run_command(
        ["smbpasswd", "-s", "-a", username],
        stdin_data=f"{password}\n{password}\n",
    )
    if rc != 0:
        raise SambaCommandError(err.strip(), cmd=f"smbpasswd -a {username}")


async def smbpasswd_delete(username: str) -> None:
    # Best-effort: tolerate missing samba entries.
    await run_command(["smbpasswd", "-x", username])


async def list_samba_users() -> list[str]:
    """Samba passdb users (tdbsam). Survives container re-creates via the volume."""
    rc, out, _ = await run_command(["pdbedit", "-L"])
    if rc != 0:
        return []
    return [line.split(":", 1)[0] for line in out.splitlines() if line]


async def reconcile_samba_users() -> None:
    """Ensure every samba passdb user has a Unix account.

    /etc/passwd lives inside the container image, so re-creating the container
    (e.g. `just up` after an image rebuild) loses the useradd accounts while the
    samba passdb keeps persisting in the samba-state volume. smbd then fails with
    NT_STATUS_NO_SUCH_USER / getpwnam() failures. Recreate the Unix accounts on boot.
    """
    for username in await list_samba_users():
        if not await user_exists(username):
            await run_command(["useradd", "-M", "-s", "/usr/sbin/nologin", username])


def scan_share_dirs() -> list[str]:
    root = get_settings().share_mount_path
    if not root.is_dir():
        return []
    return sorted(str(root / entry.name) for entry in root.iterdir() if entry.is_dir())
