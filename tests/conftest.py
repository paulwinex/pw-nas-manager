import os
import sqlite3
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="nas-test-")
os.environ["DB_PATH"] = str(Path(_TMP) / "test.db")
_SHARE_ROOT = Path(tempfile.mkdtemp(prefix="nas-share-"))
os.environ["SHARE_MOUNT_PATH"] = str(_SHARE_ROOT)

from app.core.settings import get_settings  # noqa: E402

get_settings.cache_clear()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.modules.samba import os_manager  # noqa: E402

_TABLES = (
    "users",
    "shares",
    "groups",
    "group_shares",
    "user_groups",
    "user_group_expirations",
    "refresh_tokens",
)


@pytest.fixture()
def db_path() -> str:
    return os.environ["DB_PATH"]


@pytest.fixture()
def share_root() -> Path:
    return _SHARE_ROOT


@pytest.fixture()
def client(db_path: str):
    conn = sqlite3.connect(db_path)
    for table in _TABLES:
        try:
            conn.execute(f"DELETE FROM {table}")  # noqa: S608
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._responses: dict[str, tuple[int, str, str]] = {}

    async def __call__(self, args: list[str], stdin_data: str | None = None):
        self.calls.append({"args": list(args), "stdin": stdin_data})
        joined = " ".join(args)
        for prefix, response in self._responses.items():
            if joined.startswith(prefix):
                return response
        if args and args[0] == "id":
            return 1, "", ""
        return 0, "", ""

    def set_response(self, prefix: str, rc: int = 0, stdout: str = "", stderr: str = "") -> None:
        self._responses[prefix] = (rc, stdout, stderr)

    def find(self, *parts: str) -> list[dict]:
        return [c for c in self.calls if all(p in c["args"] for p in parts)]


@pytest.fixture()
def fake_runner(monkeypatch) -> FakeRunner:
    runner = FakeRunner()
    monkeypatch.setattr(os_manager, "run_command", runner)
    return runner


def login(client: TestClient, username: str = "admin", password: str = "admin123"):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    response = login(client)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture()
def auth(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
