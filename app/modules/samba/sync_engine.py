"""Stub sync engine — the real diff engine lands in P3."""

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(slots=True)
class SyncReport:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    params_set: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.added or self.removed or self.updated or self.params_set)


async def sync(session: AsyncSession) -> SyncReport:
    """No-op in P2; called after every mutation so P3 can fill it in."""
    return SyncReport()
