"""Minimal `net conf` wrappers — replaced by the full sync engine in P3."""

from app.core.exceptions import SambaCommandError


async def _run_net_conf(*args: str) -> str:
    from app.modules.samba.os_manager import run_command

    rc, out, err = await run_command(["net", "conf", *args])
    if rc != 0:
        raise SambaCommandError(err.strip(), cmd=f"net conf {' '.join(args)}")
    return out


async def list_shares() -> list[str]:
    out = await _run_net_conf("listshares")
    return [line.strip() for line in out.splitlines() if line.strip()]


async def show_share(name: str) -> dict[str, str]:
    out = await _run_net_conf("showshare", name)
    params: dict[str, str] = {}
    for line in out.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            params[key.strip()] = value.strip()
    return params


async def add_share(name: str, path: str) -> None:
    await _run_net_conf(
        "addshare", name, path, "writeable=no", "guest_ok=no", "comment=NAS Manager"
    )


async def del_share(name: str) -> None:
    await _run_net_conf("delshare", name)


async def set_parm(share: str, parm: str, value: str) -> None:
    await _run_net_conf("setparm", share, parm, value)


async def get_parm(share: str, parm: str) -> str | None:
    return (await show_share(share)).get(parm)
