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
    is_mounted_linux,
    is_mounted_windows,
    plan_mount,
    plan_umount,
    run_command_streaming,
)
from nasmanager.ui.dialogs import LoginModal
from nasmanager.ui.mountlog import MountLogScreen
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
        yield Static("Press ? for help", id="help-bar")
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
                    self.query_one("#help-bar", Static).update(f"Login error: {e}")
                    return
            else:
                self.query_one("#help-bar", Static).update(f"API error: {e.detail}")
                return
        except Exception as e:
            self.query_one("#help-bar", Static).update(f"Sync error: {e}")
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
                ShareStatus.NEW: "🆕 new",
                ShareStatus.MOUNTED: "✅ mounted",
                ShareStatus.MOUNTED_NOT_REAL: "⚠️ mounted (no mount)",
                ShareStatus.REVOKED: "❌ revoked",
            }[d.status]
            table.add_row(d.name, d.access, status_text, d.target)

    def action_mount_selected(self) -> None:
        table = self.query_one("#status-table", DataTable)
        cursor = table.cursor_coordinate
        if cursor.row < len(self.diff_data):
            self.run_worker(self._mount_shares([self.diff_data[cursor.row]]))

    def action_mount_all(self) -> None:
        new_shares = [d for d in self.diff_data if d.status == ShareStatus.NEW]
        self.run_worker(self._mount_shares(new_shares))

    async def _mount_shares(self, shares: list[ShareDiff]) -> None:
        if not self.config:
            return
        title = f"Mount {len(shares)} share(s)"
        screen = MountLogScreen(title)
        self.push_screen(screen)
        await screen.wait_ready()
        await screen.log_line(f"# {title}")
        await self._with_mount_log(screen, shares, mount=True)

    def action_umount_selected(self) -> None:
        table = self.query_one("#status-table", DataTable)
        cursor = table.cursor_coordinate
        if cursor.row < len(self.diff_data):
            self.run_worker(self._umount_shares([self.diff_data[cursor.row]]))

    def action_umount_all(self) -> None:
        revoked = [d for d in self.diff_data if d.status == ShareStatus.REVOKED]
        self.run_worker(self._umount_shares(revoked))

    async def _umount_shares(self, shares: list[ShareDiff]) -> None:
        title = f"Unmount {len(shares)} share(s)"
        screen = MountLogScreen(title)
        self.push_screen(screen)
        await screen.wait_ready()
        await screen.log_line(f"# {title}")
        await self._with_mount_log(screen, shares, mount=False)

    async def _with_mount_log(self, screen: MountLogScreen, shares: list[ShareDiff], mount: bool) -> None:
        errors: list[str] = []
        for d in shares:
            await screen.log_line("")
            if mount:
                if not self.config:
                    return
                cmd = plan_mount(
                    d.name, d.host, d.port, self.config.username,
                    self.config.mount_root, self.config.windows_mode,
                )
            else:
                cmd = plan_umount(d.target)
            await screen.log_line(f"$ {' '.join(cmd.command)}")
            ok, msg = await run_command_streaming(
                cmd, screen.ask_password, screen.log_line, screen.is_cancelled
            )
            if screen.is_cancelled():
                await screen.log_line("Cancelled")
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
                await screen.log_line(f"ok: {d.name}")
            else:
                errors.append(f"{d.name}: {msg}")
                await screen.log_line(f"error: {d.name}: {msg}")

        if not errors and not screen.is_cancelled():
            await screen.log_line("All done")
            await asyncio.sleep(0.6)
            self.pop_screen()
            self._do_sync()
        elif screen.is_cancelled():
            await screen.log_line("Cancelled")
            await asyncio.sleep(0.4)
            self.pop_screen()
        else:
            screen.set_final()
            await screen.log_line("Errors — press any key to close")

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
        self.query_one("#help-bar", Static).update(" | ".join(lines) if lines else "No actions")

    def action_help(self) -> None:
        help_text = (
            "m=mount selected | M=mount all new | u=umount selected | "
            "U=umount all revoked | p=preview dry-run | s=sync | q=quit"
        )
        self.query_one("#help-bar", Static).update(help_text)