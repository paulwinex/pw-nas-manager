from pathlib import Path
from unittest.mock import patch


import pytest


@pytest.fixture()
def config_dir(tmp_path: Path):
    """Подменяем домашнюю директорию для конфигов."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    with patch("nasmanager.config.CONFIG_DIR", fake_home / ".config" / "nasmanager"), \
         patch("nasmanager.config.CONFIG_FILE", fake_home / ".config" / "nasmanager" / "config.json"), \
         patch("nasmanager.config.MOUNTS_FILE", fake_home / ".config" / "nasmanager" / "mounts"):
        yield fake_home / ".config" / "nasmanager"