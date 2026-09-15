import asyncio

from nasmanager.config import find_free_drive_letter
from nasmanager.mount_engine import (
    MountCommand,
    execute_command,
    plan_mount,
    plan_umount,
    run_command_streaming,
)


def test_plan_mount_linux():
    cmd = plan_mount("photos", "nas", 1445, "alice", "/mnt/nas")
    assert cmd.is_mount is True
    assert "cifs" in " ".join(cmd.command)
    assert "//nas/photos" in " ".join(cmd.command)


def test_plan_mount_linux_does_not_use_windows():
    cmd = plan_mount("photos", "nas", 1445, "alice", "/mnt/nas")
    joined = " ".join(cmd.command)
    assert "net" not in joined
    assert "mklink" not in joined


def test_plan_umount_linux():
    cmd = plan_umount("/mnt/nas/photos")
    assert cmd.is_mount is False
    assert "umount" in " ".join(cmd.command)


def test_execute_dry_run():
    cmd = MountCommand(description="test", command=["echo", "hello"], is_mount=True)
    ok, msg = execute_command(cmd, dry_run=True)
    assert ok is True
    assert "dry-run" in msg


def test_execute_real():
    cmd = MountCommand(description="test", command=["echo", "hello"], is_mount=True)
    ok, msg = execute_command(cmd, dry_run=False)
    assert ok is True


def test_windows_umount_drive():
    """windows-ветка plan_umount для drive letter — только если платформа win32;
       на Linux не проверяется (иначе упадёт)."""
    import sys
    if sys.platform != "win32":
        import pytest
        pytest.skip("Windows only")
    cmd = plan_umount("X:")
    assert "net" in " ".join(cmd.command)
    assert "/delete" in " ".join(cmd.command)


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


def test_streaming_large_output_not_dropped():
    script = "import sys; [print(i) for i in range(5000)]"
    cmd = MountCommand(description="t", command=_SECS + [script], is_mount=True)

    async def provider(prompt):
        return None

    ok, msg, lines = _collect(cmd, provider)
    assert ok is True
    assert len(lines) == 5000
    assert lines[0] == "0"
    assert lines[-1] == "4999"