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

    async def log_line(self, line: str) -> None:
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