from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Awaitable, Callable


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
    # uid/gid подставляются числами (без $(...) — шелла тут нет), пароль sudo — через stdin
    opts = (
        f"username={username},port={port},"
        f"uid={os.getuid()},gid={os.getgid()},dir_mode=0755,file_mode=0644"
    )
    cmd = ["sudo", "-S", "mount", "-t", "cifs", source, target, "-o", opts]
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
        command=["sudo", "-S", "umount", target],
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


PasswordProvider = Callable[[str], Awaitable[str | None]]
Sink = Callable[[str], Awaitable[None] | None]


def _is_sudo_prompt(line: str) -> bool:
    s = line.strip().lower()
    return (
        s.startswith("[sudo]")
        or s.startswith("password") and (":" in s or "for" in s)
    )


async def _emit(sink: Sink, line: str) -> None:
    result = sink(line)
    if asyncio.iscoroutine(result):
        await result


def _terminate(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
    except OSError:
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass


async def run_command_streaming(
    command: MountCommand,
    password_provider: PasswordProvider,
    sink: Sink,
    cancelled: Callable[[], bool],
) -> tuple[bool, str]:
    """Стримит построчно вывод команды в sink.

    - Если в команде есть плейсхолдер <PASSWORD> (Windows net use), пароль
      запрашивается ДО запуска и подставляется в аргументы.
    - Если в stderr появился промпт sudo (Linux), пароль запрашивается через
      password_provider и отправляется в stdin (sudo -S).
    Возвращает (ok, message); message == "cancelled" при отмене.
    """
    cmd_list = list(command.command)

    if "<PASSWORD>" in cmd_list:
        password = await password_provider(f"Password for {command.target or 'mount'}:")
        if password is None or cancelled():
            return False, "cancelled"
        cmd_list = [password if a == "<PASSWORD>" else a for a in cmd_list]

    proc = subprocess.Popen(
        cmd_list,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if cancelled():
        _terminate(proc)
        return False, "cancelled"

    q: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def pump(stream: str) -> None:
        fh = proc.stderr if stream == "err" else proc.stdout
        try:
            for line in fh:
                loop.call_soon_threadsafe(q.put_nowait, ("line", stream, line.rstrip("\n")))
        except Exception:
            pass

    def waiter() -> None:
        try:
            rc = proc.wait()
        except Exception:
            rc = -1
        loop.call_soon_threadsafe(q.put_nowait, ("done", "", rc))

    threading.Thread(target=pump, args=("out",), daemon=True).start()
    threading.Thread(target=pump, args=("err",), daemon=True).start()
    threading.Thread(target=waiter, daemon=True).start()

    while True:
        if cancelled():
            _terminate(proc)
            return False, "cancelled"
        try:
            kind, stream, payload = await asyncio.wait_for(q.get(), timeout=0.1)
        except asyncio.TimeoutError:
            continue
        if kind == "done":
            rc = payload
            break
        if stream == "err" and _is_sudo_prompt(payload):
            pwd = await password_provider(payload)
            if pwd is None:
                _terminate(proc)
                return False, "cancelled"
            proc.stdin.write(pwd + "\n")
            proc.stdin.flush()
        await _emit(sink, payload)

    try:
        while True:
            kind, stream, payload = q.get_nowait()
            if kind == "line":
                await _emit(sink, payload)
    except asyncio.QueueEmpty:
        pass

    return (True, "ok") if rc == 0 else (False, f"exit code {rc}")