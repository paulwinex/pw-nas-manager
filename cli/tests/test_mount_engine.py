from nasmanager.config import find_free_drive_letter
from nasmanager.mount_engine import (
    MountCommand,
    execute_command,
    plan_mount,
    plan_umount,
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