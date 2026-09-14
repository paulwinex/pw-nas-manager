from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, asdict
from pathlib import Path


CONFIG_DIR = Path.home() / ".config" / "nasmanager"
CONFIG_FILE = CONFIG_DIR / "config.json"
MOUNTS_FILE = CONFIG_DIR / "mounts"


@dataclass
class Config:
    server_url: str = "http://nas:8000"
    mount_root: str = "/mnt/nas"
    windows_mode: str = "drive"
    username: str = ""
    access_token: str = ""
    refresh_token: str = ""

    @classmethod
    def load(cls) -> Config | None:
        if not CONFIG_FILE.exists():
            return None
        data = json.loads(CONFIG_FILE.read_text())
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))
        CONFIG_FILE.chmod(0o600)


@dataclass
class MountEntry:
    share: str
    source_uri: str
    target: str


def load_mounts() -> list[MountEntry]:
    if not MOUNTS_FILE.exists():
        return []
    entries = []
    for line in MOUNTS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            entries.append(MountEntry(share=parts[0], source_uri=parts[1], target=parts[2]))
    return entries


def save_mounts(entries: list[MountEntry]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# share  source_uri  target"]
    for e in entries:
        lines.append(f"{e.share}  {e.source_uri}  {e.target}")
    MOUNTS_FILE.write_text("\n".join(lines) + "\n")
    MOUNTS_FILE.chmod(0o600)


def find_free_drive_letter() -> str | None:
    """Windows: найти свободную букву диска A-Z."""
    if platform.system() != "Windows":
        return None
    for letter in "ZXWVUTSRQPONMLKJIHGFEDCBA":
        if not os.path.exists(f"{letter}:\\"):
            return letter
    return None