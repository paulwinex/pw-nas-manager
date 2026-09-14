from __future__ import annotations

import asyncio
import sys

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static

from nasmanager.api import ApiClient, ApiError
from nasmanager.auth import login_or_refresh
from nasmanager.config import Config, load_mounts, MountEntry, save_mounts
from nasmanager.diff import compute_diff, ShareStatus
from nasmanager.mount_engine import (
    execute_command,
    is_mounted_linux,
    is_mounted_windows,
    plan_mount,
    plan_umount,
)
from nasmanager.ui.dialogs import LoginModal, PasswordModal
from nasmanager.ui.wizard import WizardScreen


class NasManagerApp(App):
    CSS = """
    #status-table { height: 1fr; }
    .new { color: green; }
    .mounted { color: cyan; }
    .revoked { color: red; }
    """

    BINDINGS = [
        Binding("m", "mount_selected", "Mount selected"),
        Binding("M", "mount_all", "Mount all new"),
        Binding("u", "umount_selected", "Unmount selected"),
        Binding("U", "umount_all", "Unmount all revoked"),
        Binding("p", "preview", "Dry-run preview"),
        Binding("s", "sync", "Sync"),
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self):
        super().__init__()
        self.config: Config | None = None
        self.api: ApiClient | None = None
        self.diff_data: list = []

    def on_mount(self) -> None:
        self.config = Config.load()
        if self.config is None:
            self.push_screen(WizardScreen(), self._on_wizard_done)
        else:
            self.api = ApiClient(self.config.server_url)
            self._do_sync()

    def _on_wizard_done(self, result) -> None:
        self.config = Config.load()
        if self.config is not None:
            self.api = ApiClient(self.config.server_url)
            self._do_sync()

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="status-table")
        yield Static("Нажмите ? для помощи", id="help-bar")
        yield Footer()

    def action_sync(self) -> None:
        self._do_sync()

    def _do_sync(self) -> None:
        self.run_worker(self._sync_worker, exclusive=True)

    async def _sync_worker(self) -> None:
        if not self.config or not self.api:
            return
        try:
            token = await asyncio.to_thread(login_or_refresh, self.config, self.api)
            shares = await asyncio.to_thread(self.api.list_shares, token)
        except ApiError as e:
            if e.status == 401:
                result = await self.push_screen_wait(LoginModal())
                if result is None:
                    return
                username, password = result
                try:
                    tokens = await asyncio.to_thread(self.api.login, username, password)
                    self.config.access_token = tokens["access_token"]
                    self.config.refresh_token = tokens["refresh_token"]
                    self.config.save()
                    shares = await asyncio.to_thread(self.api.list_shares, tokens["access_token"])
                except Exception as e:
                    self.query_one("#help-bar", Static).update(f"Ошибка логина: {e}")
                    return
            else:
                self.query_one("#help-bar", Static).update(f"Ошибка API: {e.detail}")
                return
        except Exception as e:
            self.query_one("#help-bar", Static).update(f"Ошибка синка: {e}")
            return

        mounts = load_mounts()
        mounted_fn = is_mounted_linux if sys.platform != "win32" else is_mounted_windows
        self.diff_data = compute_diff(shares, mounts, mounted_fn)
        self._render_table()

    def _render_table(self) -> None:
        table = self.query_one("#status-table", DataTable)
        table.clear()
        if not table.columns:
            table.add_columns("Share", "Access", "Status", "Target")
        for d in self.diff_data:
            status_text = {
                ShareStatus.NEW: "🆕 новая",
                ShareStatus.MOUNTED: "✅ подключена",
                ShareStatus.MOUNTED_NOT_REAL: "⚠️ подключена (нет mount)",
                ShareStatus.REVOKED: "❌ отозвана",
            }[d.status]
            table.add_row(d.name, d.access, status_text, d.target)

    def action_mount_selected(self) -> None:
        table = self.query_one("#status-table", DataTable)
        cursor = table.cursor_coordinate
        if cursor.row < len(self.diff_data):
            self._mount_shares([self.diff_data[cursor.row]])

    def action_mount_all(self) -> None:
        new_shares = [d for d in self.diff_data if d.status == ShareStatus.NEW]
        self._mount_shares(new_shares)

    async def _mount_shares(self, shares) -> None:
        if not self.config:
            return
        password = await self.push_screen_wait(PasswordModal("Пароль для sudo/mount:"))
        if password is None:
            return

        for d in shares:
            cmd = plan_mount(
                d.name, d.host, d.port, self.config.username,
                self.config.mount_root, self.config.windows_mode,
            )
            ok, msg = await asyncio.to_thread(execute_command, cmd, False, password)
            if ok:
                entry = MountEntry(
                    share=d.name,
                    source_uri=f"//{d.host}/{d.name}",
                    target=cmd.target,
                )
                mounts = load_mounts()
                mounts.append(entry)
                save_mounts(mounts)
            self.query_one("#help-bar", Static).update(f"{d.name}: {'ok' if ok else msg}")

        self._do_sync()

    def action_umount_selected(self) -> None:
        table = self.query_one("#status-table", DataTable)
        cursor = table.cursor_coordinate
        if cursor.row < len(self.diff_data):
            self._umount_shares([self.diff_data[cursor.row]])

    def action_umount_all(self) -> None:
        revoked = [d for d in self.diff_data if d.status == ShareStatus.REVOKED]
        self._umount_shares(revoked)

    async def _umount_shares(self, shares) -> None:
        for d in shares:
            cmd = plan_umount(d.target)
            ok, msg = await asyncio.to_thread(execute_command, cmd, False)
            mounts = load_mounts()
            mounts = [m for m in mounts if m.share != d.name]
            save_mounts(mounts)
            self.query_one("#help-bar", Static).update(f"{d.name}: {'umount ok' if ok else msg}")
        self._do_sync()

    def action_preview(self) -> None:
        if not self.config:
            return
        lines = []
        for d in self.diff_data:
            if d.status == ShareStatus.NEW:
                cmd = plan_mount(d.name, d.host, d.port, self.config.username, self.config.mount_root)
                lines.append(f"[dry-run] {d.name}: {cmd.description}")
            elif d.status == ShareStatus.REVOKED:
                cmd = plan_umount(d.target)
                lines.append(f"[dry-run] {d.name}: {cmd.description}")
            else:
                lines.append(f"[skip]   {d.name}: {d.status.value}")
        self.query_one("#help-bar", Static).update(" | ".join(lines) if lines else "Нет действий")

    def action_help(self) -> None:
        help_text = (
            "m=mount selected | M=mount all new | u=umount selected | "
            "U=umount all revoked | p=preview dry-run | s=sync | q=quit"
        )
        self.query_one("#help-bar", Static).update(help_text)