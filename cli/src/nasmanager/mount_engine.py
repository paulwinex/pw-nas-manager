from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


@dataclass
class MountCommand:
    description: str
    command: list[str]
    is_mount: bool  # True=mount, False=umount
    target: str = ""  # фактический target (путь/буква/Junction), куда примонтируется


def is_mounted_linux(target: str) -> bool:
    try:
        result = subprocess.run(
            ["grep", "-q", target, "/proc/mounts"],
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def is_mounted_windows(target: str) -> bool:
    """Проверка по drive letter (X:) или UNC."""
    if target.endswith(":"):
        return target.lower() in _windows_drives()
    if target.startswith("\\\\"):
        result = subprocess.run(
            ["net", "use"], capture_output=True, text=True, encoding="cp1252", errors="replace"
        )
        return target.lower() in result.stdout.lower()
    return False


def _windows_drives() -> set[str]:
    result = subprocess.run(
        ["wmic", "logicaldisk", "get", "DeviceID"],
        capture_output=True, text=True, encoding="cp1252", errors="replace"
    )
    drives = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.endswith(":"):
            drives.add(line.lower())
    return drives


def plan_mount(
    share: str, host: str, port: int, username: str, mount_root: str,
    windows_mode: str = "drive", target_override: str | None = None,
) -> MountCommand:
    if sys.platform == "win32":
        return _plan_mount_windows(share, host, username, mount_root, windows_mode, target_override)
    return _plan_mount_linux(share, host, port, username, mount_root)


def _plan_mount_linux(share, host, port, username, mount_root) -> MountCommand:
    target = f"{mount_root}/{share}"
    source = f"//{host}/{share}"
    cmd = [
        "sudo", "mount", "-t", "cifs", source, target,
        "-o", f"username={username},port={port},uid=$(id -u),gid=$(id -g),dir_mode=0755,file_mode=0644",
    ]
    return MountCommand(description=f"mount {share} → {target}", command=cmd, is_mount=True, target=target)


def _plan_mount_windows(share, host, username, mount_root, windows_mode, target_override) -> MountCommand:
    source = f"\\\\{host}\\{share}"
    if windows_mode == "unc":
        cmd = ["net", "use", source, f"/user:{username}", "<PASSWORD>"]
        return MountCommand(description=f"mount {share} (UNC)", command=cmd, is_mount=True, target=source)
    if windows_mode == "folder":
        target = target_override or f"{mount_root}\\{share}"
        cmd = ["cmd", "/c", "mklink", "/J", target, source]
        return MountCommand(description=f"mount {share} → {target} (junction)", command=cmd, is_mount=True, target=target)
    # drive
    from nasmanager.config import find_free_drive_letter
    letter = find_free_drive_letter() or "X"
    cmd = ["net", "use", f"{letter}:", source, f"/user:{username}", "<PASSWORD>"]
    return MountCommand(description=f"mount {share} → {letter}:", command=cmd, is_mount=True, target=f"{letter}:")


def plan_umount(target: str) -> MountCommand:
    if sys.platform == "win32":
        if target.endswith(":"):
            return MountCommand(
                description=f"umount {target}",
                command=["net", "use", target, "/delete"],
                is_mount=False,
                target=target,
            )
        if target.startswith("\\\\"):
            return MountCommand(
                description=f"umount UNC {target}",
                command=["net", "use", target, "/delete"],
                is_mount=False,
                target=target,
            )
        return MountCommand(
            description=f"remove junction {target}",
            command=["cmd", "/c", "rmdir", target],
            is_mount=False,
            target=target,
        )
    return MountCommand(
        description=f"umount {target}",
        command=["sudo", "umount", target],
        is_mount=False,
        target=target,
    )


def execute_command(cmd: MountCommand, dry_run: bool = False, password: str | None = None) -> tuple[bool, str]:
    """Выполнить команду. dry_run=True → печатает команду без выполнения. Возвращает (ok, message)."""
    if dry_run:
        return True, f"[dry-run] {' '.join(cmd.command)}"

    actual = list(cmd.command)
    actual = [password if p == "<PASSWORD>" else p for p in actual]

    try:
        result = subprocess.run(
            actual, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or f"exit code {result.returncode}"
        return True, "ok"
    except Exception as e:
        return False, str(e)