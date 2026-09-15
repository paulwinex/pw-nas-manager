# Mount Log Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the silent mount/umount flow in the CLI TUI with a terminal-style streaming log screen where the sudo password is requested inline and Ctrl+C aborts the batch.

**Architecture:** Add an asyncio streaming runner to `mount_engine.py` that pipes `Popen` stdout/stderr line-by-line to a callback, requests the password inline (pre-substitution for Windows `net use`, sudo-prompt detection on Linux stderr), and honors a cancel flag. Add a new `MountLogScreen` (RichLog + inline hidden password input). Rewire `_mount_shares` / `_umount_shares` in `main.py` to push the log screen and stream into it; auto-close on success, stay open on errors, close on cancel.

**Tech Stack:** Python 3.11+, Textual (RichLog, Screen, Input, Label), asyncio, subprocess.Popen, pytest. Shared repo `justfile`: CLI tests run via `just cli-test` (`cd cli && uv run --extra dev python -m pytest -v`).

**Repo state:** branch `feat/self-service-cli`; working tree clean except untracked decoys `docs/superpowers/specs/2026-09-14-self-service-cli-design.md` and `zfs-manual.md` (do not commit).

---

### Task 1: Streaming runner + Linux mount fixes in `mount_engine.py`

Root causes of «mounting does nothing» fixed here:
1. `sudo mount ...` runs with `capture_output=True`, no stdin/tty → sudo silently fails (`sudo: a terminal is required...`). Fix: `sudo -S`, password via stdin on demand.
2. `-o "uid=$(id -u),gid=$(id -g)"` is passed as one argv element with no shell → literal `$(id -u)` reaches mount/cifs. Fix: numeric uid/gid from `os.getuid()`/`os.getgid()`.

**Files:**
- Modify: `cli/src/nasmanager/mount_engine.py` (imports `os`, `asyncio`, `queue`, `threading`, `typing`, `Callable`, `Awaitable`; add `run_command_streaming`, `_is_sudo_prompt`, `_emit`; change `_plan_mount_linux`, `plan_umount` linux branch)
- Test: `cli/tests/test_mount_engine.py`

- [ ] **Step 1: Write the failing tests**

Append to `cli/tests/test_mount_engine.py`:

```python
import asyncio

from nasmanager.config import find_free_drive_letter  # already imported above
from nasmanager.mount_engine import (
    MountCommand,
    execute_command,
    plan_mount,
    plan_umount,
    run_command_streaming,
)

_SECS = ["python3", "-c"]


def _collect(cmd, provider, cancelled=lambda: False):
    lines = []

    async def sink(line):
        lines.append(line)

    async def run():
        return await run_command_streaming(cmd, provider, sink, cancelled)

    ok, msg = asyncio.run(run())
    return ok, msg, lines


def test_plan_mount_linux_uid_is_numeric():
    import re
    cmd = plan_mount("photos", "nas", 1445, "alice", "/mnt/nas")
    joined = " ".join(cmd.command)
    assert re.search(r"uid=\d+", joined)
    assert "-S" in joined


def test_plan_umount_linux_uses_sudo_S():
    import sys
    if sys.platform == "win32":
        import pytest
        pytest.skip("Windows only")
    cmd = plan_umount("/mnt/nas/photos")
    joined = " ".join(cmd.command)
    assert "-S" in joined


def test_streaming_streams_output():
    cmd = MountCommand(description="t", command=["echo", "hello"], is_mount=True)
    ok, msg, lines = _collect(cmd, lambda p: None)
    assert ok is True
    assert "hello" in lines


def test_streaming_merges_stderr():
    script = "import sys; sys.stderr.write('boom\\n'); sys.stderr.flush()"
    cmd = MountCommand(description="t", command=_SECS + [script], is_mount=True)
    ok, msg, lines = _collect(cmd, lambda p: None)
    assert ok is True
    assert lines == ["boom"]


def test_streaming_password_placeholder_substituted_upfront():
    calls = []

    async def provider(prompt):
        calls.append(prompt)
        return "sec"

    script = "import sys; print(sys.argv[1])"
    cmd = MountCommand(description="t", command=_SECS + [script, "<PASSWORD>"], is_mount=True)
    ok, msg, lines = _collect(cmd, provider)
    assert ok is True
    assert len(calls) == 1
    assert lines == ["sec"]


def test_streaming_sudo_prompt_forwards_and_sends_password():
    script = (
        "import sys; sys.stderr.write('[sudo] password for alice:\\n'); "
        "sys.stderr.flush(); pwd = sys.stdin.readline(); "
        "print('OK' if pwd == 'secret\\n' else 'BAD')"
    )
    cmd = MountCommand(description="t", command=_SECS + [script], is_mount=True)

    async def provider(prompt):
        return "secret"

    ok, msg, lines = _collect(cmd, provider)
    assert ok is True
    assert lines == ["[sudo] password for alice:", "OK"]


def test_streaming_cancel_terminates_and_reports_cancelled():
    script = "import time; time.sleep(60)"
    cmd = MountCommand(description="t", command=_SECS + [script], is_mount=True)
    ok, msg, lines = _collect(cmd, lambda p: None, cancelled=lambda: True)
    assert ok is False
    assert msg == "cancelled"


def test_streaming_password_provider_none_cancels():
    script = "import sys; print('should not run')"
    cmd = MountCommand(description="t", command=_SECS + [script, "<PASSWORD>"], is_mount=True)

    async def provider(prompt):
        return None

    ok, msg, lines = _collect(cmd, provider)
    assert ok is False
    assert msg == "cancelled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/paul/pw/dev/projects/nas/simple-share/cli && uv run --extra dev python -m pytest tests/test_mount_engine.py -v`
Expected: FAIL — `ImportError: cannot import name 'run_command_streaming' from 'nasmanager.mount_engine'`, plus `-S`/`uid=\d+` assertion failures.

- [ ] **Step 3: Implement the streaming runner and Linux fixes**

`cli/src/nasmanager/mount_engine.py` — replace the whole file body with:

```python
from __future__ import annotations

import asyncio
import os
import queue as _queue
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

    q: _queue.Queue = _queue.Queue()
    loop = asyncio.get_running_loop()

    def pump(stream: str) -> None:
        fh = proc.stderr if stream == "err" else proc.stdout
        try:
            for line in fh:
                loop.call_soon_threadsafe(q.put, ("line", stream, line.rstrip("\n")))
        except Exception:
            pass

    def waiter() -> None:
        try:
            rc = proc.wait()
        except Exception:
            rc = -1
        loop.call_soon_threadsafe(q.put, ("done", "", rc))

    threading.Thread(target=pump, args=("out",), daemon=True).start()
    threading.Thread(target=pump, args=("err",), daemon=True).start()
    threading.Thread(target=waiter, daemon=True).start()

    while True:
        if cancelled():
            _terminate(proc)
            return False, "cancelled"
        try:
            kind, stream, payload = q.get(timeout=0.1)
        except _queue.Empty:
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
    except _queue.Empty:
        pass

    return (True, "ok") if rc == 0 else (False, f"exit code {rc}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/paul/pw/dev/projects/nas/simple-share/cli && uv run --extra dev python -m pytest tests/test_mount_engine.py -v`
Expected: PASS (all mount_engine tests incl. the 7 new ones).

- [ ] **Step 5: Commit**

```bash
git add cli/src/nasmanager/mount_engine.py cli/tests/test_mount_engine.py
git commit -m "feat(cli): streaming command runner with inline sudo password"
```

---

### Task 2: `MountLogScreen`

**Files:**
- Create: `cli/src/nasmanager/ui/mountlog.py`
- Test: `cli/tests/test_mountlog.py`

- [ ] **Step 1: Write the failing tests**

Create `cli/tests/test_mountlog.py`:

```python
import asyncio

from textual.app import App

from nasmanager.ui.mountlog import MountLogScreen


class _Host(App):
    def __init__(self):
        super().__init__()
        self.screen_obj: MountLogScreen | None = None
        self.pw_result = "unset"

    def on_mount(self):
        self.screen_obj = MountLogScreen("Mount 1 share(s)", "alice")
        self.push_screen(self.screen_obj)
        asyncio.get_running_loop().create_task(self._ask())

    async def _ask(self):
        await self.screen_obj.wait_ready()
        self.pw_result = await self.screen_obj.ask_password("[sudo] password for alice:")


def test_ask_password_resolves_on_enter():
    async def run():
        app = _Host()
        async with app.run_test() as pilot:
            for _ in range(5):
                await pilot.pause()
            app.screen_obj.query_one("#pw-input").value = "secret"
            await pilot.press("enter")
            for _ in range(5):
                await pilot.pause()
            return app.pw_result

    assert asyncio.run(run()) == "secret"


def test_ctrl_c_cancels_password_prompt():
    async def run():
        app = _Host()
        async with app.run_test() as pilot:
            for _ in range(5):
                await pilot.pause()
            await pilot.press("ctrl+c")
            for _ in range(5):
                await pilot.pause()
            return app.pw_result, app.screen_obj.is_cancelled()

    result, cancelled = asyncio.run(run())
    assert result is None
    assert cancelled is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/paul/pw/dev/projects/nas/simple-share/cli && uv run --extra dev python -m pytest tests/test_mountlog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nasmanager.ui.mountlog'`.

- [ ] **Step 3: Implement `MountLogScreen`**

Create `cli/src/nasmanager/ui/mountlog.py`:

```python
from __future__ import annotations

import asyncio
from threading import Event

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, Label, RichLog, Static


class MountLogScreen(Screen):
    """Терминальный лог монтирования/размонтирования. Ctrl+C отменяет батч."""

    BINDINGS = [
        Binding("ctrl+c", "cancel", "Cancel"),
        Binding("escape", "close_final", "Close"),
    ]

    def __init__(self, title: str, username: str) -> None:
        super().__init__()
        self.title_text = title
        self.username = username
        self.ready = Event()
        self._cancelled = False
        self._final = False
        self._pw_future: asyncio.Future | None = None

    def compose(self) -> ComposeResult:
        yield Static(self.title_text, id="mount-title")
        yield RichLog(id="mount-log", markup=False, highlight=True, auto_scroll=True)
        with Vertical(id="pw-row"):
            yield Label(id="pw-label")
            yield Input(password=True, id="pw-input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#mount-log", RichLog).focus()
        self.ready.set()

    async def wait_ready(self) -> None:
        await asyncio.to_thread(self.ready.wait, 5.0)

    async def log(self, line: str) -> None:
        self.query_one("#mount-log", RichLog).write(line)

    async def ask_password(self, prompt: str) -> str | None:
        if self._cancelled:
            return None
        self.query_one("#pw-label", Label).update(prompt)
        self.query_one("#pw-row", Vertical).display = True
        inp = self.query_one("#pw-input", Input)
        inp.value = ""
        inp.focus()
        self._pw_future = asyncio.get_running_loop().create_future()
        return await self._pw_future

    def _hide_password(self) -> None:
        self.query_one("#pw-row", Vertical).display = False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "pw-input":
            self.action_submit()

    def action_submit(self) -> None:
        if self._pw_future and not self._pw_future.done():
            self._pw_future.set_result(self.query_one("#pw-input", Input).value)
        self._hide_password()

    def action_cancel(self) -> None:
        self._cancelled = True
        if self._pw_future and not self._pw_future.done():
            self._pw_future.set_result(None)
        self._hide_password()

    def is_cancelled(self) -> bool:
        return self._cancelled

    def set_final(self) -> None:
        self._final = True

    def _pop_if_top(self) -> None:
        stack = self.app._screen_stack
        if self._final and len(stack) > 1 and stack[-1] is self:
            self.app.pop_screen()

    def action_close_final(self) -> None:
        self._pop_if_top()

    def on_key(self, event) -> None:
        if self._final and event.key != "ctrl+c":
            self._pop_if_top()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/paul/pw/dev/projects/nas/simple-share/cli && uv run --extra dev python -m pytest tests/test_mountlog.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add cli/src/nasmanager/ui/mountlog.py cli/tests/test_mountlog.py
git commit -m "feat(cli): terminal-style mount log screen with inline password and Ctrl+C"
```

---

### Task 3: Rewire mount/umount flows in `main.py` (drop PasswordModal)

**Files:**
- Modify: `cli/src/nasmanager/ui/main.py` (imports; `_mount_shares`; `_umount_shares`; remove `PasswordModal` usage)
- Modify: `cli/src/nasmanager/ui/dialogs.py` (remove now-unused `PasswordModal` class)
- Modify: `cli/tests/test_tui.py` (update `m`-test to assert `MountLogScreen` push + auto-close)

- [ ] **Step 1: Update the failing TUI test**

Replace `cli/tests/test_tui.py` entirely with:

```python
import asyncio
import json
from unittest.mock import patch

import nasmanager.config as cfg

from nasmanager.config import Config
from nasmanager.diff import ShareDiff, ShareStatus
from nasmanager.ui.main import NasManagerApp


def _write_config() -> None:
    cfg.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg.CONFIG_FILE.write_text(json.dumps({"server_url": "http://localhost:9", "username": "alice"}))


async def _fake_runner(cmd, provider, sink, cancelled):
    await sink("$ fake command")
    await sink("ok")
    return (True, "ok")


async def _mount_scenario() -> tuple[list[str], list[str]]:
    NasManagerApp._do_sync = lambda self: None
    app = NasManagerApp()
    with patch("nasmanager.ui.main.run_command_streaming", _fake_runner):
        async with app.run_test() as pilot:
            await pilot.pause()
            app.config = Config(server_url="http://localhost:9", username="alice")
            app.diff_data = [
                ShareDiff(
                    name="photos", host="nas", port=445, access="rw",
                    target="", status=ShareStatus.NEW,
                )
            ]
            app._render_table()
            await pilot.press("m")
            for _ in range(3):
                await pilot.pause()
            pushed = [s.__class__.__name__ for s in app._screen_stack]
            await asyncio.sleep(0.7)  # let the auto-close beat pass
            for _ in range(3):
                await pilot.pause()
            closed = [s.__class__.__name__ for s in app._screen_stack]
            return pushed, closed


def test_mount_selected_opens_mount_log_and_autocloses(config_dir):
    """m must start the mount flow via MountLogScreen (worker-based, no dangling coroutine)
    and auto-close it on success."""
    _write_config()
    pushed, closed = asyncio.run(_mount_scenario())
    assert "MountLogScreen" in pushed
    assert closed == ["Screen"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/paul/pw/dev/projects/nas/simple-share/cli && uv run --extra dev python -m pytest tests/test_tui.py -v`
Expected: FAIL — `"MountLogScreen" in pushed` fails (screen stack still `['Screen']`; mount flow pushes `PasswordModal`).

- [ ] **Step 3: Implement the new flows**

`cli/src/nasmanager/ui/main.py` changes:

- Imports: remove `PasswordModal` from the `dialogs` import (keep `LoginModal`); add:

```python
from nasmanager.mount_engine import (
    execute_command,
    is_mounted_linux,
    is_mounted_windows,
    plan_mount,
    plan_umount,
    run_command_streaming,
)
from nasmanager.ui.mountlog import MountLogScreen
```

- Replace `action_mount_selected` / `action_mount_all` / `_mount_shares` / `action_umount_selected` / `action_umount_all` / `_umount_shares` with:

```python
    def action_mount_selected(self) -> None:
        table = self.query_one("#status-table", DataTable)
        cursor = table.cursor_coordinate
        if cursor.row < len(self.diff_data):
            self.run_worker(self._mount_shares([self.diff_data[cursor.row]]))

    def action_mount_all(self) -> None:
        new_shares = [d for d in self.diff_data if d.status == ShareStatus.NEW]
        self.run_worker(self._mount_shares(new_shares))

    async def _mount_shares(self, shares) -> None:
        if not self.config:
            return
        title = f"Mount {len(shares)} share(s)"
        screen = MountLogScreen(title, self.config.username)
        self.push_screen(screen)
        await screen.wait_ready()
        await screen.log(f"# {title}")
        await self._with_mount_log(screen, shares, mount=True)

    async def _umount_shares(self, shares) -> None:
        title = f"Unmount {len(shares)} share(s)"
        screen = MountLogScreen(title, self.config.username)
        self.push_screen(screen)
        await screen.wait_ready()
        await screen.log(f"# {title}")
        await self._with_mount_log(screen, shares, mount=False)

    async def _with_mount_log(self, screen, shares, mount: bool) -> None:
        errors: list[str] = []
        for d in shares:
            await screen.log("")
            if mount:
                if not self.config:
                    return
                cmd = plan_mount(
                    d.name, d.host, d.port, self.config.username,
                    self.config.mount_root, self.config.windows_mode,
                )
            else:
                cmd = plan_umount(d.target)
            await screen.log(f"$ {' '.join(cmd.command)}")
            ok, msg = await run_command_streaming(
                cmd, screen.ask_password, screen.log, screen.is_cancelled
            )
            if screen.is_cancelled():
                await screen.log("Cancelled")
                break
            if ok:
                if mount:
                    entry = MountEntry(
                        share=d.name,
                        source_uri=f"//{d.host}/{d.name}",
                        target=cmd.target,
                    )
                    mounts = load_mounts()
                    mounts.append(entry)
                    save_mounts(mounts)
                else:
                    mounts = load_mounts()
                    mounts = [m for m in mounts if m.share != d.name]
                    save_mounts(mounts)
                await screen.log(f"ok: {d.name}")
            else:
                errors.append(f"{d.name}: {msg}")
                await screen.log(f"error: {d.name}: {msg}")

        if not errors and not screen.is_cancelled():
            await screen.log("All done")
            await asyncio.sleep(0.6)
            self.pop_screen()
            self._do_sync()
        elif screen.is_cancelled():
            await screen.log("Cancelled")
            await asyncio.sleep(0.4)
            self.pop_screen()
        else:
            screen.set_final()
            await screen.log("Errors — press any key to close")
```

`cli/src/nasmanager/ui/dialogs.py` — remove the `PasswordModal` class (lines 9–36) and its now-unused imports, keeping `LoginModal`:

```python
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class LoginModal(ModalScreen[tuple[str, str] | None]):
    """Modal for login."""

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-container"):
            yield Static("Login", id="dialog-label")
            yield Input(placeholder="username", id="username-input")
            yield Input(password=True, placeholder="password", id="password-input")
            yield Button("Sign in", variant="primary", id="ok")
            yield Button("Cancel", variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#username-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            u = self.query_one("#username-input", Input).value
            p = self.query_one("#password-input", Input).value
            self.dismiss((u, p))
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
```

- [ ] **Step 4: Run the full CLI test suite**

Run: `cd /home/paul/pw/dev/projects/nas/simple-share/cli && uv run --extra dev python -m pytest -v`
Expected: PASS (all CLI tests; previous 19 passed + 2 new mountlog + 2 new tui-adjusted; ensure no stale `PasswordModal` references).

- [ ] **Step 5: Sanity — grep for leftovers**

Run: `rg -n "PasswordModal|password-modal" cli/src cli/tests`
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add cli/src/nasmanager/ui/main.py cli/src/nasmanager/ui/dialogs.py cli/tests/test_tui.py
git commit -m "feat(cli): mount/umount via streaming log screen; remove PasswordModal"
```

---

## Post-Plan Checks

1. **Spec coverage:** the spec's four sections map to Task 1 (streaming runner + sudo/net use password handling + cancel), Task 2 (MountLogScreen: log, inline prompt, Ctrl+C), Task 3 (data flow `m/M/u/U` → log, auto-close on success, stay open on errors, cancel closes).
2. **Placeholder scan:** every code step contains full code; no TBD.
3. **Type consistency:** `run_command_streaming(command, password_provider, sink, cancelled) -> tuple[bool, str]`; `ask_password(prompt: str) -> str | None`; `log(line: str) -> None`; `is_cancelled() -> bool`; all signatures match across Task 1/Task 2/Task 3 (see `_with_mount_log` call).

## Verification

- `just cli-test` green.
- Manual: `just cli-run`, `m`, enter password at inline prompt, watch streaming lines; `Ctrl+C` mid-batch aborts; errors leave the log open.