"""Tests for the single-file nasmount script (stdlib only)."""

import argparse
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import nasmount as m


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class FakeResp:
    def __init__(self, status, payload):
        self.status = status
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def make_opener(routes):
    """Opener mock for nasmount._urlopen: routes keyed by (method, url)."""
    import urllib.error

    def opener(req, timeout=None):
        key = (req.get_method(), req.full_url)
        status, payload = routes.get(key, (404, {"detail": "not found"}))
        if 400 <= status < 600:
            fp = io.BytesIO(json.dumps(payload).encode())
            raise urllib.error.HTTPError(
                req.full_url, status, payload.get("detail", "HTTP error"), {}, fp
            )
        return FakeResp(status, payload)

    return opener


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def test_config_defaults(tmp_path):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    cfg = m.load_config()
    assert cfg.server_url == "http://nas:8000"
    assert cfg.mount_root == ""
    assert cfg.access_token == ""
    assert cfg.refresh_token == ""


def test_config_roundtrip(tmp_path):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    cfg = m.Config(username="alice", access_token="acc", refresh_token="ref")
    m.save_config(cfg)
    loaded = m.load_config()
    assert loaded.username == "alice"
    assert loaded.access_token == "acc"
    assert loaded.refresh_token == "ref"
    assert (tmp_path / "config.json").exists()


def test_config_masks_tokens_when_shown(capsys):
    cfg = m.Config(server_url="http://nas:8000", username="alice")
    cfg.access_token = "secret-access"
    cfg.refresh_token = "secret-refresh"
    m.show_config(cfg)
    out = capsys.readouterr().out
    assert "secret-access" not in out
    assert "secret-refresh" not in out
    assert "alice" in out
    assert "http://nas:8000" in out


def test_mounts_file_roundtrip(tmp_path):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.add_mount("photos", "//nas/photos", "/mnt/nas/photos")
    loaded = m.load_mounts()
    assert loaded == [("photos", "//nas/photos", "/mnt/nas/photos")]


def test_remove_mount(tmp_path):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.add_mount("photos", "//nas/photos", "/mnt/nas/photos")
    m.remove_mounts_where(lambda share, source, target: share == "photos")
    assert m.load_mounts() == []


# ---------------------------------------------------------------------------
# host parsing
# ---------------------------------------------------------------------------

def test_host_from_url():
    assert m.host_from_url("http://nas:8000") == "nas"
    assert m.host_from_url("http://192.168.1.5:8000/") == "192.168.1.5"


# ---------------------------------------------------------------------------
# api
# ---------------------------------------------------------------------------

def test_api_login_uses_form_and_returns_tokens(monkeypatch):
    opener = make_opener({
        ("POST", "http://nas:8000/api/v1/auth/token"): (200, {"access_token": "tok", "refresh_token": "ref"}),
    })
    monkeypatch.setattr(m, "_urlopen", opener)
    result = m.ApiClient("http://nas:8000").login("alice", "pass")
    assert result["access_token"] == "tok"


def test_api_refresh_posts_json(monkeypatch):
    captured = {}

    class Spy(FakeResp):
        def __init__(self):
            super().__init__(200, {"access_token": "t", "refresh_token": "r"})

    def opener(req, timeout=None):
        captured["method"] = req.get_method()
        captured["body"] = req.data
        captured["ctype"] = req.get_header("Content-type")
        return Spy()

    monkeypatch.setattr(m, "_urlopen", opener)
    result = m.ApiClient("http://nas:8000").refresh("oldref")
    assert result["refresh_token"] == "r"
    assert captured["method"] == "POST"
    assert "application/json" in captured["ctype"]
    assert json.loads(captured["body"]) == {"refresh_token": "oldref"}


def test_api_list_shares_sends_bearer_and_returns_list(monkeypatch):
    def opener(req, timeout=None):
        auth = req.get_header("Authorization")
        if "Bearer tok" in auth and req.get_method() == "GET":
            return FakeResp(200, [{"name": "photos", "host": "nas", "port": 1445, "access": "RO"}])
        return FakeResp(401, {"detail": "nope"})

    monkeypatch.setattr(m, "_urlopen", opener)
    shares = m.ApiClient("http://nas:8000").list_shares("tok")
    assert shares[0]["name"] == "photos"


def test_api_raises_on_http_error(monkeypatch):
    opener = make_opener({
        ("GET", "http://nas:8000/api/v1/users/me/shares"): (401, {"detail": "Unauthorized"}),
    })
    monkeypatch.setattr(m, "_urlopen", opener)
    with pytest.raises(m.ApiError) as exc:
        m.ApiClient("http://nas:8000").list_shares("bad")
    assert exc.value.status == 401


# ---------------------------------------------------------------------------
# token handling
# ---------------------------------------------------------------------------

def test_get_valid_token_refreshes_and_saves(monkeypatch, tmp_path):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    opener = make_opener({
        ("POST", "http://nas:8000/api/v1/auth/refresh"): (200, {"access_token": "new", "refresh_token": "newref"}),
    })
    monkeypatch.setattr(m, "_urlopen", opener)
    cfg = m.Config(server_url="http://nas:8000", refresh_token="oldref")
    token = m.get_valid_token(cfg)
    assert token == "new"
    assert cfg.refresh_token == "newref"
    assert m.load_config().access_token == "new"


def test_get_valid_token_without_credentials_raises(monkeypatch):
    monkeypatch.setattr(m, "_urlopen", make_opener({}))
    cfg = m.Config(server_url="http://nas:8000")
    with pytest.raises(m.NotAuthenticated):
        m.get_valid_token(cfg)


def test_get_valid_token_probes_access_and_refreshes_on_401(monkeypatch, tmp_path):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    opener = make_opener({
        ("GET", "http://nas:8000/api/v1/users/me/shares"): (401, {"detail": "expired"}),
        ("POST", "http://nas:8000/api/v1/auth/refresh"): (200, {"access_token": "fresh", "refresh_token": "refresh2"}),
    })
    monkeypatch.setattr(m, "_urlopen", opener)
    cfg = m.Config(server_url="http://nas:8000", access_token="stale", refresh_token="okref")
    token = m.get_valid_token(cfg)
    assert token == "fresh"


# ---------------------------------------------------------------------------
# mount parsers (pure functions)
# ---------------------------------------------------------------------------

LINUX_PROC = (
    "proc /proc proc rw,nosuid 0 0\n"
    "//nas/photos /mnt/nas/photos cifs rw,relatime 0 0\n"
    "/dev/sda1 / ext4 rw 0 0\n"
    "//nas/docs /mnt/nas/docs cifs rw 0 0\n"
)


def test_parse_linux_mounts_filters_smb():
    mounts = m.parse_linux_mounts(LINUX_PROC)
    assert ("//nas/photos", "/mnt/nas/photos") in mounts
    assert ("//nas/docs", "/mnt/nas/docs") in mounts
    assert not any("ext4" in src or src == "proc" for src, _ in mounts)


def test_parse_linux_mounts_unescapes_mountpoints():
    text = "//nas/photos /mnt/nas/my\\040photos cifs rw 0 0\n"
    mounts = m.parse_linux_mounts(text)
    assert mounts == [("//nas/photos", "/mnt/nas/my photos")]


def test_parse_macos_mounts():
    text = (
        "//alice@nas/photos on /Volumes/photos (smbfs, node=00FFFF, nosuid, mounted by paul)\n"
        "/dev/disk1s1 on / (apfs, local)\n"
    )
    mounts = m.parse_macos_mounts(text)
    assert mounts == [("//alice@nas/photos", "/Volumes/photos")]


def test_parse_net_use():
    text = (
        "State       Local  Remote                   Network\n"
        "-------------------------------------------------------------------------------\n"
        "OK          Z:     \\\\nas\\photos             Microsoft Windows Network\n"
        "OK                 \\\\nas\\docs              Microsoft Windows Network\n"
        "The command completed successfully.\n"
    )
    mounts = m.parse_net_use(text)
    assert mounts == [("Z:", "\\\\nas\\photos"), ("", "\\\\nas\\docs")]


def test_source_matching_is_case_insensitive():
    assert m.is_mounted("NAS", "Photos", [("//nas/Photos", "/mnt/x")])
    assert m.is_mounted("nas", "photos", [("//alice@nas/photos", "/Volumes/photos")])
    assert m.is_mounted("nas", "photos", [(r"\\nas\photos", "Z:")])
    assert not m.is_mounted("other", "photos", [("//nas/photos", "/mnt/x")])
    assert not m.is_mounted("nas", "other", [("//nas/photos", "/mnt/x")])


def test_source_host_extraction():
    assert m.source_host("//nas/photos") == "nas"
    assert m.source_host("//alice@nas/photos") == "nas"
    assert m.source_host(r"\\nas\photos") == "nas"


def test_source_share_extraction():
    assert m.source_share("//nas/photos") == "photos"
    assert m.source_share("//alice@nas/movies") == "movies"
    assert m.source_share(r"\\nas\docs") == "docs"


# ---------------------------------------------------------------------------
# mount plans
# ---------------------------------------------------------------------------

def test_mount_plan_linux_uses_cifs_with_full_opts():
    cmd, target, needs_sudo = m.mount_plan("nas", "photos", 1445, "alice", "/mnt/nas", "s3cret", platform="linux")
    joined = " ".join(cmd)
    assert needs_sudo is True
    assert target == "/mnt/nas/photos"
    assert "mount -t cifs //nas/photos" in joined
    assert "username=alice" in joined
    assert "password=s3cret" in joined
    assert "port=1445" in joined
    assert "uid=" in joined and "gid=" in joined


def test_mount_plan_darwin_uses_mount_smbfs():
    cmd, target, needs_sudo = m.mount_plan("nas", "photos", 1445, "alice", "/mnt/nas", "s3cret", platform="darwin")
    joined = " ".join(cmd)
    assert needs_sudo is True
    assert target == "/mnt/nas/photos"
    assert "mount_smbfs" in joined
    assert "//alice:s3cret@nas:1445/photos" in joined


def test_mount_plan_windows_uses_net_use_with_password():
    cmd, target, needs_sudo = m.mount_plan("nas", "photos", 445, "alice", "C:\\mnt", "s3cret", platform="win32")
    joined = " ".join(cmd)
    assert needs_sudo is False
    assert "net use" in joined
    assert r"\\nas\photos" in joined
    assert "s3cret" in joined
    assert "alice" in joined


def test_umount_plan_dispatch():
    cmd, _, needs_sudo = m.umount_plan("//nas/photos", "/mnt/nas/photos", platform="linux")
    assert needs_sudo is True
    assert "umount" in " ".join(cmd)

    cmd, _, needs_sudo = m.umount_plan("//nas/photos", "/Volumes/photos", platform="darwin")
    assert needs_sudo is True
    assert "umount" in " ".join(cmd)

    cmd, _, needs_sudo = m.umount_plan(r"\\nas\photos", "", platform="win32")
    assert needs_sudo is False
    assert "net use" in " ".join(cmd)
    assert "/delete" in " ".join(cmd)


# ---------------------------------------------------------------------------
# run helpers
# ---------------------------------------------------------------------------

def test_run_cmd_reports_success_and_failure():
    ok, _ = m.run_cmd(["echo", "hi"])
    assert ok is True
    ok, msg = m.run_cmd([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert ok is False
    assert "exit code 3" in msg


def test_run_privileged_adds_sudo_when_no_password_needed(monkeypatch):
    monkeypatch.setattr(m, "sudo_needs_password", lambda: False)
    calls = []
    monkeypatch.setattr(m, "run_cmd", lambda cmd, stdin_data=None: (calls.append(cmd), (True, ""))[1])
    ok, _ = m.run_privileged(["mount", "-t", "cifs", "//nas/x", "/mnt/x", "-o", "a=b"])
    assert ok is True
    assert calls[0][0:2] == ["sudo", "-S"]


def test_run_privileged_feeds_sudo_password(monkeypatch):
    monkeypatch.setattr(m, "sudo_needs_password", lambda: True)
    monkeypatch.setattr(m, "_ask_sudo_password", lambda: "sudo-pw")
    seen = {}
    monkeypatch.setattr(m, "run_cmd", lambda cmd, stdin_data=None: (seen.update(cmd=cmd, stdin=stdin_data), (True, ""))[1])
    m.run_privileged(["umount", "/mnt/nas/photos"])
    assert seen["stdin"] == "sudo-pw\n"


def test_ensure_dir_creates_privately(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(m, "run_privileged", lambda cmd, password=False: (calls.append(cmd), (True, ""))[1])
    m.ensure_dir(tmp_path / "sub")
    assert ["mkdir", "-p", str(tmp_path / "sub")] in calls


# ---------------------------------------------------------------------------
# config command
# ---------------------------------------------------------------------------

def test_cmd_config_sets_root(tmp_path, capsys):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", mount_root="/mnt/nas"))
    args = argparse.Namespace(root="/mnt/data", url=None)
    rc = m.cmd_config(m.load_config(), args)
    assert rc == 0
    assert m.load_config().mount_root == "/mnt/data"
    assert "/mnt/data" in capsys.readouterr().out


def test_cmd_config_sets_url(tmp_path, capsys):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://old:8000"))
    args = argparse.Namespace(root=None, url="http://192.168.1.10:8000/")
    rc = m.cmd_config(m.load_config(), args)
    assert rc == 0
    assert m.load_config().server_url == "http://192.168.1.10:8000"


def test_cmd_config_without_args_shows_config(tmp_path, capsys):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", username="alice"))
    rc = m.cmd_config(m.load_config(), argparse.Namespace(root=None, url=None))
    assert rc == 0
    out = capsys.readouterr().out
    assert "http://nas:8000" in out
    assert "alice" in out


# ---------------------------------------------------------------------------
# auth command
# ---------------------------------------------------------------------------

def test_cmd_auth_logs_in_and_saves_tokens(tmp_path, monkeypatch, capsys):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000"))
    opener = make_opener({
        ("POST", "http://nas:8000/api/v1/auth/token"): (200, {"access_token": "acc", "refresh_token": "ref"}),
    })
    monkeypatch.setattr(m, "_urlopen", opener)
    monkeypatch.setattr(m, "_input", lambda prompt="": "alice" if "username" in prompt.lower() else "alice")
    monkeypatch.setattr(m, "_getpass", lambda prompt="": "pass")
    rc = m.cmd_auth(m.load_config(), argparse.Namespace())
    assert rc == 0
    cfg = m.load_config()
    assert cfg.username == "alice"
    assert cfg.access_token == "acc"
    assert "Authentication succeeded" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# mount command
# ---------------------------------------------------------------------------

def fake_shares():
    return [
        {"name": "photos", "host": "nas", "port": 1445, "access": "RW"},
        {"name": "docs", "host": "nas", "port": 1445, "access": "RO"},
    ]


def test_cmd_mount_prompts_for_root_and_mounts_all(tmp_path, monkeypatch):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", mount_root="", username="alice", refresh_token="ref"))

    monkeypatch.setattr(m, "get_valid_token", lambda cfg: "tok")
    monkeypatch.setattr(m.ApiClient, "list_shares", lambda self, token: fake_shares())
    monkeypatch.setattr(m, "_input", lambda prompt="": "")
    monkeypatch.setattr(m, "_ask_smb_password", lambda *a: "s3cret")
    monkeypatch.setattr(m, "run_privileged", lambda cmd, password=None: (True, ""))
    commands = []
    monkeypatch.setattr(m, "run_cmd", lambda cmd, stdin_data=None: (commands.append(cmd), (True, ""))[1])
    monkeypatch.setattr(m, "sudo_needs_password", lambda: False)

    rc = m.cmd_mount(m.load_config(), argparse.Namespace(root=None))
    assert rc == 0
    joined = " ".join(" ".join(c) for c in commands)
    assert "//nas/photos" in joined
    assert "//nas/docs" in joined
    mounted = dict((share, target) for share, source, target in m.load_mounts())
    assert mounted["photos"] == "/mnt/nas/photos"
    assert mounted["docs"] == "/mnt/nas/docs"


def test_cmd_mount_uses_config_root_without_prompt(tmp_path, monkeypatch):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", mount_root="/mnt/store", username="alice", refresh_token="ref"))
    monkeypatch.setattr(m, "get_valid_token", lambda cfg: "tok")
    monkeypatch.setattr(m.ApiClient, "list_shares", lambda self, token: fake_shares())
    monkeypatch.setattr(m, "_input", lambda prompt="": pytest.fail("must not prompt"))
    monkeypatch.setattr(m, "_ask_smb_password", lambda *a: "s3cret")
    monkeypatch.setattr(m, "run_privileged", lambda cmd, password=None: (True, ""))
    targets = []
    monkeypatch.setattr(m, "run_cmd", lambda cmd, stdin_data=None: (targets.append(" ".join(cmd)), (True, ""))[1])
    monkeypatch.setattr(m, "sudo_needs_password", lambda: False)

    m.cmd_mount(m.load_config(), argparse.Namespace(root=None))
    assert any("/mnt/store/photos" in t for t in targets)
    assert m.load_config().mount_root == "/mnt/store"


def test_cmd_mount_root_arg_wins_and_is_saved(tmp_path, monkeypatch):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", mount_root="/mnt/nas", username="alice", refresh_token="ref"))
    monkeypatch.setattr(m, "get_valid_token", lambda cfg: "tok")
    monkeypatch.setattr(m.ApiClient, "list_shares", lambda self, token: fake_shares())
    monkeypatch.setattr(m, "_ask_smb_password", lambda *a: "s3cret")
    monkeypatch.setattr(m, "run_privileged", lambda cmd, password=None: (True, ""))
    targets = []
    monkeypatch.setattr(m, "run_cmd", lambda cmd, stdin_data=None: (targets.append(" ".join(cmd)), (True, ""))[1])
    monkeypatch.setattr(m, "sudo_needs_password", lambda: False)

    m.cmd_mount(m.load_config(), argparse.Namespace(root="/mnt/arg"))
    assert any("/mnt/arg/photos" in t for t in targets)
    assert m.load_config().mount_root == "/mnt/arg"


def test_cmd_mount_requires_auth(tmp_path, monkeypatch, capsys):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", mount_root="/mnt/nas", username="alice"))
    rc = m.cmd_mount(m.load_config(), argparse.Namespace(root=None))
    assert rc == 1
    assert "auth" in capsys.readouterr().out.lower()


def test_cmd_mount_specific_share_only(tmp_path, monkeypatch):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", mount_root="/mnt/nas", username="alice", refresh_token="ref"))
    monkeypatch.setattr(m, "get_valid_token", lambda cfg: "tok")
    monkeypatch.setattr(m.ApiClient, "list_shares", lambda self, token: fake_shares())
    monkeypatch.setattr(m, "_ask_smb_password", lambda *a: "s3cret")
    monkeypatch.setattr(m, "run_privileged", lambda cmd, password=None: (True, ""))
    commands = []
    monkeypatch.setattr(m, "run_cmd", lambda cmd, stdin_data=None: (commands.append(" ".join(cmd)), (True, ""))[1])
    monkeypatch.setattr(m, "sudo_needs_password", lambda: False)

    rc = m.cmd_mount(m.load_config(), argparse.Namespace(root=None, names=["docs"]))
    assert rc == 0
    joined = "\n".join(commands)
    assert "//nas/docs" in joined
    assert "//nas/photos" not in joined
    mounted = [share for share, _source, _target in m.load_mounts()]
    assert mounted == ["docs"]


def test_cmd_mount_unknown_share_reports_error(tmp_path, monkeypatch, capsys):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", mount_root="/mnt/nas", username="alice", refresh_token="ref"))
    monkeypatch.setattr(m, "get_valid_token", lambda cfg: "tok")
    monkeypatch.setattr(m.ApiClient, "list_shares", lambda self, token: fake_shares())
    monkeypatch.setattr(m, "_ask_smb_password", lambda *a: "s3cret")
    monkeypatch.setattr(m, "run_privileged", lambda cmd, password=None: (True, ""))
    monkeypatch.setattr(m, "run_cmd", lambda cmd, stdin_data=None: (True, ""))

    rc = m.cmd_mount(m.load_config(), argparse.Namespace(root=None, names=["ghost"]))
    assert rc == 1
    assert "ghost" in capsys.readouterr().out
    assert m.load_mounts() == []


# ---------------------------------------------------------------------------
# umount command
# ---------------------------------------------------------------------------

def test_cmd_umount_only_unmounts_ours(tmp_path, monkeypatch):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", mount_root="/mnt/nas"))
    m.add_mount("photos", "//nas/photos", "/mnt/nas/photos")

    mounts = [
        ("//nas/photos", "/mnt/nas/photos"),
        ("//nas/docs", "/mnt/nas/docs"),
        ("//other/games", "/mnt/other/games"),
    ]
    monkeypatch.setattr(m, "system_mounts", lambda: mounts)
    commands = []
    monkeypatch.setattr(m, "run_cmd", lambda cmd, stdin_data=None: (commands.append(" ".join(cmd)), (True, ""))[1])
    monkeypatch.setattr(m, "sudo_needs_password", lambda: False)

    rc = m.cmd_umount(m.load_config(), argparse.Namespace())
    assert rc == 0
    joined = "\n".join(commands)
    assert "/mnt/nas/photos" in joined
    assert "/mnt/nas/docs" in joined
    assert "/mnt/other/games" not in joined
    assert m.load_mounts() == []


def test_cmd_umount_matches_alternative_host_from_shares(tmp_path, monkeypatch):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", refresh_token="ref"))

    def fake_get_token(cfg):
        return "tok"

    class FakeApi:
        def __init__(self, url):
            pass

        def list_shares(self, token):
            return [{"name": "photos", "host": "192.168.1.5", "port": 445, "access": "RW"}]

    monkeypatch.setattr(m, "get_valid_token", fake_get_token)
    monkeypatch.setattr(m, "ApiClient", FakeApi)
    monkeypatch.setattr(m, "system_mounts", lambda: [("//192.168.1.5/photos", "/mnt/x"), ("//other/photos", "/mnt/y")])
    commands = []
    monkeypatch.setattr(m, "run_cmd", lambda cmd, stdin_data=None: (commands.append(" ".join(cmd)), (True, ""))[1])
    monkeypatch.setattr(m, "sudo_needs_password", lambda: False)

    m.cmd_umount(m.load_config(), argparse.Namespace())
    joined = "\n".join(commands)
    assert "/mnt/x" in joined
    assert "/mnt/y" not in joined


def test_cmd_umount_works_without_auth_using_server_host(tmp_path, monkeypatch):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000"))
    monkeypatch.setattr(m, "get_valid_token", lambda cfg: (_ for _ in ()).throw(m.NotAuthenticated()))
    monkeypatch.setattr(m, "system_mounts", lambda: [("//nas/photos", "/mnt/nas/photos")])
    commands = []
    monkeypatch.setattr(m, "run_cmd", lambda cmd, stdin_data=None: (commands.append(" ".join(cmd)), (True, ""))[1])
    monkeypatch.setattr(m, "sudo_needs_password", lambda: False)

    rc = m.cmd_umount(m.load_config(), argparse.Namespace())
    assert rc == 0
    assert "/mnt/nas/photos" in "\n".join(commands)


def test_cmd_umount_specific_share_only(tmp_path, monkeypatch):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", mount_root="/mnt/nas"))
    m.add_mount("photos", "//nas/photos", "/mnt/nas/photos")
    m.add_mount("docs", "//nas/docs", "/mnt/nas/docs")
    monkeypatch.setattr(m, "system_mounts", lambda: [
        ("//nas/photos", "/mnt/nas/photos"),
        ("//nas/docs", "/mnt/nas/docs"),
        ("//other/games", "/mnt/other/games"),
    ])
    commands = []
    monkeypatch.setattr(m, "run_cmd", lambda cmd, stdin_data=None: (commands.append(" ".join(cmd)), (True, ""))[1])
    monkeypatch.setattr(m, "sudo_needs_password", lambda: False)

    rc = m.cmd_umount(m.load_config(), argparse.Namespace(names=["docs"]))
    assert rc == 0
    joined = "\n".join(commands)
    assert "/mnt/nas/docs" in joined
    assert "/mnt/nas/photos" not in joined
    remaining = [share for share, _source, _target in m.load_mounts()]
    assert remaining == ["photos"]


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------

def test_cmd_status_lists_shares_with_mounted_markers(tmp_path, monkeypatch, capsys):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", username="alice", refresh_token="ref"))
    monkeypatch.setattr(m, "get_valid_token", lambda cfg: "tok")
    monkeypatch.setattr(m.ApiClient, "list_shares", lambda self, token: fake_shares())
    monkeypatch.setattr(
        m, "system_mounts",
        lambda: [("//nas/photos", "/mnt/nas/photos")],
    )
    rc = m.cmd_status(m.load_config(), argparse.Namespace())
    assert rc == 0
    out = capsys.readouterr().out
    assert "photos" in out
    assert "docs" in out
    assert "[mounted]" in out
    assert "[not mounted]" in out
    assert "RW" in out and "RO" in out


def test_cmd_status_requires_auth(tmp_path, monkeypatch, capsys):
    os.environ["NASMOUNT_CONFIG_DIR"] = str(tmp_path)
    m.save_config(m.Config(server_url="http://nas:8000", username="alice"))
    rc = m.cmd_status(m.load_config(), argparse.Namespace())
    assert rc == 1
    assert "auth" in capsys.readouterr().out.lower()