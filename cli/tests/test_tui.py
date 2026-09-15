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