import asyncio

from textual.app import App

from nasmanager.ui.mountlog import MountLogScreen


class _Host(App):
    def __init__(self):
        super().__init__()
        self.screen_obj: MountLogScreen | None = None
        self.pw_result = "unset"

    def on_mount(self):
        self.screen_obj = MountLogScreen("Mount 1 share(s)")
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


def test_enter_after_cancel_does_not_resubmit():
    async def run():
        app = _Host()
        async with app.run_test() as pilot:
            for _ in range(5):
                await pilot.pause()
            await pilot.press("ctrl+c")
            for _ in range(5):
                await pilot.pause()
            app.screen_obj.query_one("#pw-input").value = "secret"
            await pilot.press("enter")
            for _ in range(5):
                await pilot.pause()
            return app.pw_result, app.screen_obj.is_cancelled()

    result, cancelled = asyncio.run(run())
    assert result is None
    assert cancelled is True


def test_double_enter_resolves_once():
    async def run():
        app = _Host()
        async with app.run_test() as pilot:
            for _ in range(5):
                await pilot.pause()
            app.screen_obj.query_one("#pw-input").value = "secret"
            await pilot.press("enter")
            await pilot.press("enter")
            for _ in range(5):
                await pilot.pause()
            return app.pw_result

    assert asyncio.run(run()) == "secret"


def test_ask_password_returns_none_after_cancel():
    async def run():
        app = _Host()
        async with app.run_test() as pilot:
            for _ in range(5):
                await pilot.pause()
            await pilot.press("ctrl+c")
            for _ in range(5):
                await pilot.pause()
            again = await app.screen_obj.ask_password("[sudo] password for alice:")
            return again

    assert asyncio.run(run()) is None


def test_final_mode_pop_on_escape():
    async def run():
        app = _Host()
        async with app.run_test() as pilot:
            for _ in range(5):
                await pilot.pause()
            app.screen_obj.set_final()
            await pilot.press("escape")
            for _ in range(5):
                await pilot.pause()
            names = [s.__class__.__name__ for s in app._screen_stack]
            return names

    names = asyncio.run(run())
    assert names == ["Screen"]


def test_log_line_writes_to_richlog():
    import asyncio
    from nasmanager.ui.mountlog import MountLogScreen
    from textual.widgets import RichLog

    async def run():
        app = _Host()
        async with app.run_test() as pilot:
            for _ in range(5):
                await pilot.pause()
            await app.screen_obj.log_line("hello log")
            await pilot.pause()
            rl = app.screen_obj.query_one("#mount-log", RichLog)
            return any(str(strip.text) == "hello log" for strip in rl.lines)

    assert asyncio.run(run()) is True