from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class PasswordModal(ModalScreen[str]):
    """Password prompt modal (sudo/smb)."""

    def __init__(self, prompt: str = "Password:"):
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-container"):
            yield Static(self.prompt, id="dialog-label")
            yield Input(password=True, id="password-input")
            yield Button("OK", variant="primary", id="ok")
            yield Button("Cancel", variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#password-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            pwd = self.query_one("#password-input", Input).value
            self.dismiss(pwd)
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


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