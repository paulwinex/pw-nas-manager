from __future__ import annotations

import enum
from dataclasses import dataclass

from nasmanager.config import MountEntry


class ShareStatus(str, enum.Enum):
    NEW = "new"
    MOUNTED = "mounted"
    MOUNTED_NOT_REAL = "mounted_not_real"
    REVOKED = "revoked"


@dataclass
class ShareDiff:
    name: str
    host: str
    port: int
    access: str
    target: str
    status: ShareStatus


def compute_diff(
    api_shares: list[dict],
    mounts: list[MountEntry],
    is_mounted_fn,  # callable(target) -> bool
) -> list[ShareDiff]:
    """Сопоставить шары из API с записями mounts и реальным состоянием.

    Для NEW-шары target пустой (ещё не монтировалась); для MOUNTED_NOT_REAL
    и REVOKED — из записи mounts. Возвращает сортированный по имени список.
    """
    api_map = {s["name"]: s for s in api_shares}
    mount_map = {m.share: m for m in mounts}
    result = []

    for name, share in api_map.items():
        entry = mount_map.get(name)
        if entry is None:
            status = ShareStatus.NEW
            target = ""
        elif is_mounted_fn(entry.target):
            status = ShareStatus.MOUNTED
            target = entry.target
        else:
            status = ShareStatus.MOUNTED_NOT_REAL
            target = entry.target
        result.append(ShareDiff(
            name=name, host=share["host"], port=share["port"],
            access=share["access"], target=target, status=status,
        ))

    for name, entry in mount_map.items():
        if name not in api_map:
            result.append(ShareDiff(
                name=name, host="", port=0, access="",
                target=entry.target, status=ShareStatus.REVOKED,
            ))

    return sorted(result, key=lambda d: d.name)