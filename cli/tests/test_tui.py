import asyncio
import json

import nasmanager.config as cfg

from nasmanager.config import Config
from nasmanager.diff import ShareDiff, ShareStatus
from nasmanager.ui.main import NasManagerApp


def _write_config() -> None:
    cfg.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg.CONFIG_FILE.write_text(json.dumps({"server_url": "http://localhost:9", "username": "alice"}))


async def _mount_scenario() -> list[str]:
    NasManagerApp._do_sync = lambda self: None
    app = NasManagerApp()
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
        names = [s.__class__.__name__ for s in app._screen_stack]
        await pilot.press("escape")
        await pilot.pause()
        return names


def test_mount_selected_hotkey_pushes_password_modal(config_dir):
    """m (mount selected) must actually start the mount flow,
    not just create a coroutine that is never awaited."""
    _write_config()
    names = asyncio.run(_mount_scenario())
    assert "PasswordModal" in names