from __future__ import annotations

import platform

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from nasmanager.api import ApiClient, ApiError
from nasmanager.config import Config


class WizardScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Quit")]

    def __init__(self):
        super().__init__()
        self.step = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard"):
            yield Static("Настройка NAS Manager", id="title")
            yield Label("Адрес сервера:")
            yield Input(value="http://nas:8000", id="server_url")
            yield Label("Логин:")
            yield Input(id="username")
            yield Label("Пароль:")
            yield Input(password=True, id="password")
            yield Label("Корневая папка для шар:")
            default_root = "C:\\nas" if platform.system() == "Windows" else "/mnt/nas"
            yield Input(value=default_root, id="mount_root")
            yield Button("Далее", variant="primary", id="next")
            yield Static("", id="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next":
            self._try_login()

    def _try_login(self) -> None:
        server = self.query_one("#server_url", Input).value.strip()
        username = self.query_one("#username", Input).value.strip()
        password = self.query_one("#password", Input).value
        mount_root = self.query_one("#mount_root", Input).value.strip()

        if not server or not username or not password:
            self.query_one("#error", Static).update("Все поля обязательны")
            return

        api = ApiClient(server)
        try:
            tokens = api.login(username, password)
        except ApiError as e:
            self.query_one("#error", Static).update(f"Ошибка: {e.detail}")
            return

        cfg = Config(
            server_url=server,
            mount_root=mount_root,
            username=username,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
        )
        if platform.system() == "Windows":
            cfg.windows_mode = "drive"
        cfg.save()
        self.app.config = cfg
        self.app.pop_screen()