from pathlib import Path
from unittest.mock import patch

from nasmanager.config import Config, load_mounts, save_mounts, MountEntry, find_free_drive_letter


def test_config_save_load(config_dir):
    cfg = Config(server_url="http://test:8000", username="alice", access_token="tok123")
    cfg.save()
    loaded = Config.load()
    assert loaded is not None
    assert loaded.server_url == "http://test:8000"
    assert loaded.username == "alice"


def test_config_load_missing():
    with patch("nasmanager.config.CONFIG_FILE", Path("/nonexistent")):
        assert Config.load() is None


def test_mounts_save_load(config_dir):
    entries = [
        MountEntry(share="photos", source_uri="//nas/photos", target="/mnt/nas/photos"),
        MountEntry(share="docs", source_uri="//nas/docs", target="/mnt/nas/docs"),
    ]
    save_mounts(entries)
    loaded = load_mounts()
    assert len(loaded) == 2
    assert loaded[0].share == "photos"


def test_mounts_empty():
    with patch("nasmanager.config.MOUNTS_FILE", Path("/nonexistent")):
        assert load_mounts() == []


def test_find_free_drive_letter_returns_none_on_linux():
    # платформа Linux в CI — free letter не определяется
    assert find_free_drive_letter() is None