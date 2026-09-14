# Self-Service CLI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать self-service API для обычных пользователей, веб-страницу «Мои шары» с кнопками скачивания CLI, и CLI `nasmanager` (Python + Textual, бинарь через Nuitka) с TUI: wizard, статус-таблица, dry-run, mount/umount.

**Architecture:** Backend раскрывает эндпоинты для обычных пользователей (`/auth/login` без is_admin, `/auth/refresh`, `/auth/me`, `/users/me/shares|mount-script|password|cli`). Web SPA: переносит админку под `/admin`, корень — «Мои шары» + скачивание CLI + профиль. CLI — отдельный Python-пакет `cli/nasmanager` с Textual TUI, собирается Nuitka-onefile на Linux/Windows, отдаётся через `/users/me/cli?os=`.

**Tech Stack:** Python 3.11+ (FastAPI, SQLAlchemy 2 async, httpx, httpx, PyJWT, bcrypt), Quasar 3 (Vue 3, TypeScript, Pinia), Textual, httpx (CLI), Nuitka, uv.

**Spec:** `docs/superpowers/specs/2026-09-14-self-service-cli-design.md` (backend + web), `2026-09-14-cli-python-tui-design.md` (CLI).

---

## File Structure

### Backend (существующие/новые файлы)

| Файл | Ответственность |
|---|---|
| `app/core/settings.py` | Добавить `refresh_ttl_minutes`, `cli_dist_dir` |
| `app/db/models.py` | Новая модель `RefreshToken` |
| `app/core/database.py:38` | Миграция: `CREATE TABLE IF NOT EXISTS refresh_tokens` |
| `app/core/security.py` | Добавить `hash_token`, `create_refresh_token` |
| `app/modules/auth/dependencies.py` | Новый `get_current_user` (без is_admin) |
| `app/modules/auth/schemas.py` | Новые: `LoginResponse`, `RefreshRequest`, `TokenPair` |
| `app/modules/auth/routes.py` | Login для всех, `/auth/refresh`, обновить `/auth/me` |
| `app/modules/users/services.py` | Рефактор: `list_user_shares` хелпер |
| `app/modules/users/schemas.py` | Новый `ShareOutMe` |
| `app/modules/users/me_routes.py` | **Новый** roутер `/users/me/*` |
| `app/api/v1/router.py` | Включить `me_router`, убрать `get_current_admin` с `/auth/me` |
| `tests/conftest.py` | Добавить `refresh_tokens` в `_TABLES`, обновить `login()` |
| `tests/test_auth.py` | Тесты: login для не-admin, refresh, rotation |
| `tests/test_self_service.py` | **Новый**: `/me/shares`, mount-script, password, admin 403 |
| `deploy/compose.yml` | Volume `cli/dist:/app/cli-dist:ro` |

### CLI (новый пакет)

| Файл | Ответственность |
|---|---|
| `cli/pyproject.toml` | Пакет: textual, httpx; dev: pytest, nuitka |
| `cli/src/nasmanager/__init__.py` | `__version__` |
| `cli/src/nasmanager/__main__.py` | `--version`; запуск TUI |
| `cli/src/nasmanager/config.py` | Чтение/запись `~/.config/nasmanager/config.json` + `mounts` |
| `cli/src/nasmanager/api.py` | httpx-клиент: login/refresh/shares |
| `cli/src/nasmanager/auth.py` | Хранение токенов, rotate, logout |
| `cli/src/nasmanager/diff.py` | Логика дифа: API vs mounts vs реальное состояние |
| `cli/src/nasmanager/mount_engine.py` | Linux/Windows mount/umount, dry_run, проверка `/proc/mounts` |
| `cli/src/nasmanager/ui/wizard.py` | Textual screen: первый запуск |
| `cli/src/nasmanager/ui/main.py` | Textual App: DataTable + bindings |
| `cli/src/nasmanager/ui/dialogs.py` | Модалки: пароль, логин |
| `cli/tests/conftest.py` | Fake httpx transport |
| `cli/tests/test_config.py` | |
| `cli/tests/test_api.py` | |
| `cli/tests/test_diff.py` | |
| `cli/tests/test_mount_engine.py` | |
| `cli/build_linux.sh` | Nuitka Linux onefile |
| `cli/build_windows.ps1` | Nuitka Windows onefile |

### Web UI (изменения)

| Файл | Ответственность |
|---|---|
| `web-ui/src/pages/admin/(index).vue` | **Переехал** из `pages/index/(index).vue` (admin dashboard) |
| `web-ui/src/pages/admin/users.vue` | **Переехал** из `pages/index/users.vue` |
| `web-ui/src/pages/admin/shares.vue` | **Переехал** из `pages/index/shares.vue` |
| `web-ui/src/pages/admin/groups.vue` | **Переехал** из `pages/index/groups.vue` |
| `web-ui/src/pages/admin/system.vue` | **Переехал** из `pages/index/system.vue` |
| `web-ui/src/pages/index/my-shares.vue` | **Новый**: / — список шар, скачивание CLI, mount-script |
| `web-ui/src/pages/index/profile.vue` | Существует, дополнить сменой пароля |
| `web-ui/src/router/index.ts` | Admin-guard: `/admin/*` → isAdmin |
| `web-ui/src/layouts/MainLayout.vue` | navItems: Мои шары, Профиль; Админка (visible isAdmin) |
| `web-ui/src/api/types.ts` | Новый `ShareOutMe` |
| `web-ui/src/api/index.ts` | Добавить `meShares()`, `meMountScript()`, `changeMyPassword()`, `refresh()`, `cliUrl()` |
| `web-ui/src/api/client.ts` | Refresh interceptor (silent refresh на 401) |
| `web-ui/src/stores/auth.ts` | Сохранять refresh_token; `tryRefresh()` |

---

## Task 1: Backend foundation — Settings, RefreshToken модель, get_current_user

**Files:**
- Modify: `app/core/settings.py`
- Modify: `app/db/models.py`
- Modify: `app/core/database.py:38`
- Modify: `app/core/security.py`
- Modify: `app/modules/auth/dependencies.py`

- [ ] **Step 1: Добавить настройки**

`app/core/settings.py` — добавить после `expiry_check_interval_seconds`:

```python
    refresh_ttl_minutes: int = 10080  # 7 дней
    cli_dist_dir: Path = Path("./cli-dist")
```

- [ ] **Step 2: Модель RefreshToken**

`app/db/models.py` — добавить в конец файла (после `UserGroupExpiration`):

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

- [ ] **Step 3: Миграция**

`app/core/database.py` — добавить в `_migrate` после существующего ALTER:

```python
    # Create refresh_tokens table if not exists (for existing DBs)
    sync_conn.execute(text("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash VARCHAR(64) UNIQUE NOT NULL,
            expires_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL
        )
    """))
```

- [ ] **Step 4: Хелперы токенов в security.py**

`app/core/security.py` — добавить в конец:

```python
import hashlib
import secrets
from datetime import timedelta


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_refresh_token_value() -> str:
    return secrets.token_urlsafe(48)


def create_refresh_token_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(timezone.utc) + timedelta(minutes=settings.refresh_ttl_minutes)
```

- [ ] **Step 5: get_current_user dependency**

`app/modules/auth/dependencies.py` — добавить после `get_current_admin`:

```python
async def get_current_user(
    token: str | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if token is None:
        raise Unauthorized("Authentication required")
    subject = decode_access_token(token)
    user = await session.get(User, subject)
    if user is None:
        raise Unauthorized("User no longer exists")
    return user
```

- [ ] **Step 6: Commit**

```bash
git add app/core/settings.py app/db/models.py app/core/database.py app/core/security.py app/modules/auth/dependencies.py
git commit -m "feat(backend): refresh token model, settings, get_current_user"
```

---

## Task 2: Auth routes — login для всех, /auth/refresh, /auth/me для любого

**Files:**
- Modify: `app/modules/auth/routes.py`
- Modify: `app/modules/auth/schemas.py` (создать, если нет) или прямо в routes
- Modify: `app/api/v1/router.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Схемы ответов**

`app/modules/auth/routes.py` — обновить импорты и схемы в начале файла:

```python
from datetime import datetime, timezone

import jwt

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import Forbidden, Unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token_expiry,
    create_refresh_token_value,
    decode_access_token,
    hash_token,
    verify_password,
)
from app.core.settings import get_settings
from app.db.models import RefreshToken, User
from app.modules.auth.dependencies import get_current_user
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
```

- [ ] **Step 2: Login без проверки is_admin**

Заменить функцию `login` в `app/modules/auth/routes.py`:

```python
@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest, session: AsyncSession = Depends(get_session)
) -> LoginResponse:
    user = await session.scalar(select(User).where(User.username == body.username))
    if user is None or not await verify_password(body.password, user.password_hash):
        raise Unauthorized("Invalid credentials")
    # Убрана проверка is_admin — доступны любые учётные записи

    access = create_access_token(user.id)

    refresh_value = create_refresh_token_value()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_value),
        expires_at=create_refresh_token_expiry(),
    )
    session.add(rt)
    await session.commit()

    return LoginResponse(access_token=access, refresh_token=refresh_value)
```

- [ ] **Step 3: Обновить token endpoint**

Заменить функцию `token`:

```python
@router.post("/token", response_model=LoginResponse)
async def token(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    """Form-based login used by the Swagger UI 'Authorize' button."""
    user = await session.scalar(select(User).where(User.username == form.username))
    if user is None or not await verify_password(form.password, user.password_hash):
        raise Unauthorized("Invalid credentials")
    # Убрана проверка is_admin

    access = create_access_token(user.id)

    refresh_value = create_refresh_token_value()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_value),
        expires_at=create_refresh_token_expiry(),
    )
    session.add(rt)
    await session.commit()

    return LoginResponse(access_token=access, refresh_token=refresh_value)
```

- [ ] **Step 4: /auth/me для любого пользователя**

Заменить функцию `me`:

```python
@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current)
```

- [ ] **Step 5: /auth/refresh**

Добавить в конец `app/modules/auth/routes.py`:

```python
@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    body: RefreshRequest, session: AsyncSession = Depends(get_session)
) -> LoginResponse:
    token_hash = hash_token(body.refresh_token)
    rt = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    if rt is None:
        raise Unauthorized("Invalid refresh token")

    now = datetime.now(timezone.utc)
    if rt.expires_at < now:
        await session.delete(rt)
        await session.commit()
        raise Unauthorized("Refresh token expired")

    # Rotation: удалить старый, создать новый
    await session.delete(rt)
    await session.flush()

    user = await session.get(User, rt.user_id)
    if user is None:
        raise Unauthorized("User no longer exists")

    access = create_access_token(user.id)
    refresh_value = create_refresh_token_value()
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_value),
        expires_at=create_refresh_token_expiry(),
    )
    session.add(new_rt)
    await session.commit()

    return LoginResponse(access_token=access, refresh_token=refresh_value)
```

- [ ] **Step 6: Подключить get_current_user в router.py**

`app/api/v1/router.py` — добавить импорт:

```python
from app.modules.auth.dependencies import get_current_user  # noqa: F401
```

(Импорт нужен для дедупликации, но реально `get_current_user` используется в `me_routes.py` — см. Task 3.)

- [ ] **Step 7: Обновить conftest.py**

`tests/conftest.py` — в `_TABLES` добавить `"refresh_tokens"`:

```python
_TABLES = (
    "users",
    "shares",
    "groups",
    "group_shares",
    "user_groups",
    "user_group_expirations",
    "refresh_tokens",
)
```

Также обновить helper `login()` чтобы возвращать оба токена (опционально; пока оставим как есть — тесты будут работать с access_token).

- [ ] **Step 8: Commit**

```bash
git add app/modules/auth/routes.py app/api/v1/router.py tests/conftest.py
git commit -m "feat(backend): open login to all users, /auth/refresh, /auth/me for non-admin"
```

---

## Task 3: Self-service routes — /users/me/*

**Files:**
- Modify: `app/modules/users/services.py`
- Create: `app/modules/users/me_routes.py`
- Modify: `app/modules/users/schemas.py`
- Modify: `app/api/v1/router.py`

- [ ] **Step 1: Рефактор helper — list_user_shares**

`app/modules/users/services.py` — добавить ДО `build_mount_script`:

```python
async def list_user_shares(session: AsyncSession, username: str) -> list[dict[str, str]]:
    user = await session.scalar(select(User).where(User.username == username))
    if user is None:
        raise NotFound(f"User '{username}' not found")

    settings = get_settings()
    target = await sync_engine.compute_target(session)
    shares = []
    for name, share in sorted(target.items()):
        if username not in share.valid_users:
            continue
        access = "RW" if username in share.write_list else "RO"
        shares.append({
            "name": name,
            "host": settings.nas_host,
            "port": settings.nas_port,
            "access": access,
        })
    return shares
```

Затем переписать `build_mount_script` чтобы использовать `list_user_shares`:

```python
async def build_mount_script(
    session: AsyncSession, username: str
) -> dict[str, object]:
    shares_raw = await list_user_shares(session, username)
    if not shares_raw:
        raise NotFound(f"User '{username}' not found")

    settings = get_settings()
    host = settings.nas_host
    port = settings.nas_port

    shares = [
        {"name": s["name"], "path": rf"\\{s['host']}\{s['name']}", "access": s["access"]}
        for s in shares_raw
    ]

    linux_lines = [
        "#!/usr/bin/env bash",
        'if [ -n "${MOUNT_ROOT:-}" ]; then',
        '  echo "MOUNT_ROOT from environment: ${MOUNT_ROOT}"',
        "else",
        '  MOUNT_ROOT=""',
        '  while [ -z "${MOUNT_ROOT}" ]; do',
        '    read -r -p "Mount root path (e.g. /mnt): " MOUNT_ROOT',
        "  done",
        "fi",
        'sudo mkdir -p "${MOUNT_ROOT}"',
        'echo "Mount root: ${MOUNT_ROOT}"',
        "",
        f'read -r -p "Password for {username}: " PASWD',
        "",
    ]
    for s in shares:
        linux_lines.extend([
            f"# {s['name']}",
            f'TARGET_DIR="${{MOUNT_ROOT}}/{s["name"]}"',
            'sudo mkdir -p "${TARGET_DIR}"',
            f'sudo mount -t cifs //{host}/{s["name"]} "${{TARGET_DIR}}" '
            f"-o username={username},password=${{PASWD}},port={port}"
            ",uid=$(id -u),gid=$(id -g),dir_mode=0755,file_mode=0644",
            f'echo "Mounted //{host}/{s["name"]}" at ${{TARGET_DIR}}"',
            "",
        ])

    if port == 445:
        windows_script = "\n".join(
            f"net use * \\\\{host}\\{s['name']} /user:{username}" for s in shares
        )
    else:
        # net use doesn't support a custom SMB port; go through a local portproxy.
        windows_script = "\n".join(
            [
                "# Windows 'net use' does not support a custom SMB port.",
                "# Run this once as Administrator to forward 127.0.0.1:445 to the NAS:",
                f"#   netsh interface portproxy add v4tov4 listenport=445 listenaddress=127.0.0.1",
                f"#     connectport={port} connectaddress={host}",
                "",
            ]
            + [
                f"net use * \\\\127.0.0.1\\{s['name']} /user:{username}"
                for s in shares
            ]
        )

    return {
        "username": username,
        "host": host,
        "port": port,
        "shares": shares,
        "linux_script": "\n".join(linux_lines),
        "windows_script": windows_script,
    }
```

- [ ] **Step 2: Схема ShareOutMe**

`app/modules/users/schemas.py` — добавить после `MountScriptResponse`:

```python
class ShareOutMe(BaseModel):
    name: str
    host: str
    port: int
    access: str
```

- [ ] **Step 3: Self-service roутер**

Создать `app/modules/users/me_routes.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import Unauthorized
from app.db.models import User
from app.modules.auth.dependencies import get_current_user
from app.modules.users import services
from app.modules.users.schemas import (
    MountScriptResponse,
    PasswordChange,
    ShareOutMe,
)

router = APIRouter(
    prefix="/users/me",
    tags=["self-service"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/shares", response_model=list[ShareOutMe])
async def my_shares(
    current: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ShareOutMe]:
    shares = await services.list_user_shares(session, current.username)
    return [ShareOutMe(**s) for s in shares]


@router.get("/mount-script", response_model=MountScriptResponse)
async def my_mount_script(
    current: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MountScriptResponse:
    data = await services.build_mount_script(session, current.username)
    return MountScriptResponse(**data)


@router.post("/password", status_code=204)
async def change_my_password(
    body: PasswordChange,
    current: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await services.change_password(session, current.id, body.new_password)
```

- [ ] **Step 4: Включить roутер в api_router**

`app/api/v1/router.py` — добавить импорт и include (ДО `users_router`):

```python
from app.modules.users.me_routes import router as me_router
# ... существующий код ...
api_router.include_router(me_router)   # ДО users_router, чтобы /users/me не ловился как /{user_id}
api_router.include_router(auth_router)
api_router.include_router(users_router)
```

- [ ] **Step 5: Commit**

```bash
git add app/modules/users/services.py app/modules/users/schemas.py app/modules/users/me_routes.py app/api/v1/router.py
git commit -m "feat(backend): self-service /users/me/* routes, refactor list_user_shares"
```

---

## Task 4: CLI binary serving + compose volume

**Files:**
- Modify: `app/modules/users/me_routes.py`
- Modify: `deploy/compose.yml`

- [ ] **Step 1: Эндпоинт cli**

`app/modules/users/me_routes.py` — добавить импорт и эндпоинт:

```python
import glob
from pathlib import Path

from fastapi.responses import FileResponse

from app.core.settings import get_settings

# ... существующий код ...

@router.get("/cli")
async def download_cli(
    os: str,
    current: User = Depends(get_current_user),
) -> FileResponse:
    settings = get_settings()
    dist_dir = settings.cli_dist_dir
    if os == "linux":
        pattern = str(dist_dir / "nasmanager-linux-*")
    elif os == "windows":
        pattern = str(dist_dir / "nasmanager-windows-*")
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="os must be 'linux' or 'windows'")

    matches = sorted(glob.glob(pattern))
    if not matches:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="CLI binary not found")

    filepath = Path(matches[-1])
    return FileResponse(filepath, filename=filepath.name, media_type="application/octet-stream")
```

- [ ] **Step 2: Volume в compose**

`deploy/compose.yml` — добавить в volumes сервиса `app`:

```yaml
    volumes:
      - ${SHARE_HOST_PATH}:${SHARE_MOUNT_PATH}
      - ./data:/data
      - /data/samba-state:/var/lib/samba
      - ../cli/dist:/app/cli-dist:ro
```

- [ ] **Step 3: Commit**

```bash
git add app/modules/users/me_routes.py deploy/compose.yml
git commit -m "feat(backend): GET /users/me/cli endpoint, cli-dist volume"
```

---

## Task 5: Backend tests

**Files:**
- Create: `tests/test_self_service.py`
- Modify: `tests/test_auth.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Тест auth (login для не-admin, refresh, rotation)**

Добавить в `tests/test_auth.py` (в конце файла):

```python
def test_login_non_admin(client):
    """Логин обычного пользователя (не admin) успешен."""
    client.post("/api/v1/users", json={"username": "alice", "password": "pass123"})
    resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "pass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_password(client):
    client.post("/api/v1/users", json={"username": "alice", "password": "pass123"})
    resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


def test_refresh_token_rotation(client):
    """Refresh: старый токен инвалидируется, новый работает."""
    client.post("/api/v1/users", json={"username": "alice", "password": "pass123"})
    login_resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "pass123"})
    refresh = login_resp.json()["refresh_token"]

    # Первый refresh — ОК
    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]
    assert new_refresh != refresh

    # Старый refresh — инвалидирован
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 401

    # Новый refresh работает
    r3 = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert r3.status_code == 200


def test_me_non_admin(client):
    """GET /auth/me работает для обычного пользователя."""
    client.post("/api/v1/users", json={"username": "alice", "password": "pass123"})
    login_resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "pass123"})
    token = login_resp.json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"
```

- [ ] **Step 2: Тесты self-service**

Создать `tests/test_self_service.py`:

```python
import pytest


def _login_user(client, username="alice", password="pass123"):
    client.post("/api/v1/users", json={"username": username, "password": password})
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_my_shares(client, fake_runner):
    """Юзер видит свои шары через /users/me/shares."""
    token = _login_user(client)
    resp = client.get("/api/v1/users/me/shares", headers=_auth(token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_my_mount_script(client, fake_runner):
    token = _login_user(client)
    resp = client.get("/api/v1/users/me/mount-script", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "alice"
    assert "linux_script" in data


def test_my_password_change(client):
    token = _login_user(client)
    resp = client.post(
        "/api/v1/users/me/password",
        json={"new_password": "newpass"},
        headers=_auth(token),
    )
    assert resp.status_code == 204
    # Проверяем новым паролем
    login_resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "newpass"})
    assert login_resp.status_code == 200


def test_admin_endpoints_403_for_non_admin(client):
    """Не-admin не может удалить юзера."""
    token = _login_user(client, "alice", "pass123")
    # Создадим bob от admin
    admin_token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    bob = client.post("/api/v1/users", json={"username": "bob", "password": "pass123"}, headers=_auth(admin_token)).json()
    # Alice пытается удалить bob
    resp = client.delete(f"/api/v1/users/{bob['id']}", headers=_auth(token))
    assert resp.status_code == 403


def test_cli_endpoint_404_if_no_binary(client):
    token = _login_user(client)
    resp = client.get("/api/v1/users/me/cli?os=linux", headers=_auth(token))
    assert resp.status_code == 404
```

- [ ] **Step 3: Запустить тесты**

```bash
just test
```

Ожидаемо: все тесты проходят. Если падают — исправить.

- [ ] **Step 4: Commit**

```bash
git add tests/test_auth.py tests/test_self_service.py
git commit -m "test(backend): self-service and auth tests"
```

---

## Task 6: Web — перенос страниц, guards, toolbar

**Files:**
- Move: `web-ui/src/pages/index/(index).vue` → `web-ui/src/pages/admin/(index).vue`
- Move: `web-ui/src/pages/index/users.vue` → `web-ui/src/pages/admin/users.vue`
- Move: `web-ui/src/pages/index/shares.vue` → `web-ui/src/pages/admin/shares.vue`
- Move: `web-ui/src/pages/index/groups.vue` → `web-ui/src/pages/admin/groups.vue`
- Move: `web-ui/src/pages/index/system.vue` → `web-ui/src/pages/admin/system.vue`
- Modify: `web-ui/src/router/index.ts`
- Modify: `web-ui/src/layouts/MainLayout.vue`

- [ ] **Step 1: Перенести admin-страницы**

```bash
cd web-ui
mkdir -p src/pages/admin
git mv src/pages/index/\(index\).vue src/pages/admin/\(index\).vue
git mv src/pages/index/users.vue src/pages/admin/users.vue
git mv src/pages/index/shares.vue src/pages/admin/shares.vue
git mv src/pages/index/groups.vue src/pages/admin/groups.vue
git mv src/pages/index/system.vue src/pages/admin/system.vue
```

- [ ] **Step 2: Router guard для admin**

`web-ui/src/router/index.ts` — в `Router.beforeEach` добавить после проверки `profileLoaded`:

```typescript
  Router.beforeEach(async (to) => {
    const auth = useAuthStore();
    if (to.path !== '/login' && !auth.authenticated) {
      return { path: '/login' };
    }
    if (to.path === '/login' && auth.authenticated) {
      return { path: '/' };
    }
    if (to.path !== '/login' && auth.authenticated && !auth.profileLoaded) {
      try {
        await auth.refreshProfile();
      } catch {
        auth.logout();
        return { path: '/login' };
      }
    }
    // Admin guard
    if (to.path.startsWith('/admin') && !auth.isAdmin) {
      return { path: '/' };
    }
    return true;
  });
```

- [ ] **Step 3: Toolbar — navItems**

`web-ui/src/layouts/MainLayout.vue` — заменить `navItems` на:

```typescript
const navItems = computed(() => {
  const items = [
    { to: '/', label: 'Мои шары', icon: 'folder_shared' },
    { to: '/profile', label: 'Профиль', icon: 'account_circle' },
  ];
  if (auth.isAdmin) {
    items.push({ to: '/admin', label: 'Админка', icon: 'admin_panel_settings' });
  }
  return items;
});
```

Добавить `import { computed } from 'vue';` в `<script setup>`.

- [ ] **Step 4: Commit**

```bash
cd ..
git add web-ui/
git commit -m "feat(web): restructure pages — admin to /admin, root for user pages"
```

---

## Task 7: Web — страницы «Мои шары» и «Профиль»

**Files:**
- Create: `web-ui/src/pages/index/my-shares.vue`
- Modify: `web-ui/src/pages/index/profile.vue`

- [ ] **Step 1: Страница «Мои шары»**

Создать `web-ui/src/pages/index/my-shares.vue`:

```vue
<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Мои шары</div>

    <div v-if="loading" class="text-grey">Загрузка…</div>
    <div v-else-if="error" class="text-negative q-mb-md">
      Ошибка загрузки. <q-btn flat dense label="Повторить" @click="load" />
    </div>

    <template v-else>
      <!-- Список шар -->
      <q-markup-table v-if="shares.length" class="q-mb-lg">
        <thead>
          <tr>
            <th class="text-left">Имя</th>
            <th class="text-left">Хост</th>
            <th class="text-right">Порт</th>
            <th class="text-right">Доступ</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in shares" :key="s.name">
            <td>{{ s.name }}</td>
            <td>{{ s.host }}</td>
            <td class="text-right">{{ s.port }}</td>
            <td class="text-right">
              <q-badge :color="s.access === 'RW' ? 'teal' : 'blue-grey'" :label="s.access" />
            </td>
          </tr>
        </tbody>
      </q-markup-table>
      <div v-else class="text-grey q-mb-lg">Нет доступных шар.</div>

      <!-- Скачать CLI -->
      <q-card flat bordered class="q-mb-lg">
        <q-card-section>
          <div class="text-h6">CLI-утилита</div>
        </q-card-section>
        <q-separator inset />
        <q-card-section class="row q-gutter-sm">
          <q-btn
            color="primary"
            icon="download"
            label="Скачать nasmanager (Linux)"
            :href="`/api/v1/users/me/cli?os=linux`"
          />
          <q-btn
            color="primary"
            icon="download"
            label="Скачать nasmanager (Windows)"
            :href="`/api/v1/users/me/cli?os=windows`"
          />
        </q-card-section>
      </q-card>

      <!-- Ручное подключение -->
      <q-card flat bordered>
        <q-card-section>
          <div class="text-h6">Ручное подключение</div>
        </q-card-section>
        <q-separator inset />
        <q-card-section>
          <q-tabs v-model="manualTab" class="text-primary">
            <q-tab name="linux" label="Linux" />
            <q-tab name="windows" label="Windows" />
          </q-tabs>
          <q-tab-panels v-model="manualTab">
            <q-tab-panel name="linux">
              <q-input
                v-model="mountScript.linux_script"
                type="textarea"
                readonly
                filled
                rows="10"
              />
              <q-btn flat dense icon="content_copy" label="Копировать" class="q-mt-sm"
                     @click="copyToClipboard(mountScript.linux_script)" />
            </q-tab-panel>
            <q-tab-panel name="windows">
              <q-input
                v-model="mountScript.windows_script"
                type="textarea"
                readonly
                filled
                rows="10"
              />
              <q-btn flat dense icon="content_copy" label="Копировать" class="q-mt-sm"
                     @click="copyToClipboard(mountScript.windows_script)" />
            </q-tab-panel>
          </q-tab-panels>
        </q-card-section>
      </q-card>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { api } from '@/api';
import type { ShareOutMe, MountScriptResponse } from '@/api/types';

const loading = ref(true);
const error = ref(false);
const shares = ref<ShareOutMe[]>([]);
const mountScript = ref<MountScriptResponse>({
  username: '',
  host: '',
  port: 445,
  shares: [],
  linux_script: '',
  windows_script: '',
});
const manualTab = ref('linux');

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text);
}

async function load() {
  loading.value = true;
  error.value = false;
  try {
    const [sharesResp, scriptResp] = await Promise.all([
      api.meShares(),
      api.meMountScript(),
    ]);
    shares.value = sharesResp.data;
    mountScript.value = scriptResp.data;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>
```

- [ ] **Step 2: Страница «Профиль»**

Обновить `web-ui/src/pages/index/profile.vue` — расширить существующую страницу:

```vue
<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Профиль</div>

    <q-card flat bordered style="max-width: 400px">
      <q-card-section>
        <div class="text-subtitle1">Пользователь: {{ auth.username }}</div>
      </q-card-section>
      <q-separator inset />
      <q-card-section>
        <div class="text-subtitle2 q-mb-sm">Смена пароля</div>
        <q-input
          v-model="newPassword"
          type="password"
          label="Новый пароль"
          class="q-mb-sm"
          filled
        />
        <q-input
          v-model="confirmPassword"
          type="password"
          label="Повторите пароль"
          class="q-mb-md"
          filled
        />
        <q-btn
          color="primary"
          label="Сменить пароль"
          :disable="!newPassword || newPassword !== confirmPassword"
          :loading="saving"
          @click="changePassword"
        />
        <div v-if="saved" class="text-positive q-mt-sm">Пароль изменён. Перелогиньтесь.</div>
        <div v-if="saveError" class="text-negative q-mt-sm">{{ saveError }}</div>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { api } from '@/api';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const newPassword = ref('');
const confirmPassword = ref('');
const saving = ref(false);
const saved = ref(false);
const saveError = ref('');

async function changePassword() {
  saving.value = true;
  saved.value = false;
  saveError.value = '';
  try {
    await api.changeMyPassword(newPassword.value);
    saved.value = true;
    newPassword.value = '';
    confirmPassword.value = '';
  } catch (e: any) {
    saveError.value = e.response?.data?.detail || 'Ошибка';
  } finally {
    saving.value = false;
  }
}
</script>
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/
git commit -m "feat(web): my-shares page with CLI download, profile with password change"
```

---

## Task 8: Web — API client + auth store (refresh)

**Files:**
- Modify: `web-ui/src/api/types.ts`
- Modify: `web-ui/src/api/index.ts`
- Modify: `web-ui/src/api/client.ts`
- Modify: `web-ui/src/stores/auth.ts`

- [ ] **Step 1: Типы**

`web-ui/src/api/types.ts` — добавить в конец:

```typescript
export interface ShareOutMe {
  name: string;
  host: string;
  port: number;
  access: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
```

- [ ] **Step 2: API methods**

`web-ui/src/api/index.ts` — добавить:

```typescript
  // self-service
  meShares: () => client.get<ShareOutMe[]>('/api/v1/users/me/shares'),
  meMountScript: () => client.get<MountScriptResponse>('/api/v1/users/me/mount-script'),
  changeMyPassword: (newPassword: string) =>
    client.post<void>('/api/v1/users/me/password', { new_password: newPassword }),
  cliUrl: (os: string) => `/api/v1/users/me/cli?os=${os}`,
  refresh: (refreshToken: string) =>
    client.post<LoginResponse>('/api/v1/auth/refresh', { refresh_token: refreshToken }),
```

Обновить `login` чтобы возвращать `LoginResponse` (включает refresh_token):

```typescript
  login: (username: string, password: string) => {
    const form = new URLSearchParams();
    form.set('username', username);
    form.set('password', password);
    return client.post<LoginResponse>('/api/v1/auth/token', form);
  },
```

- [ ] **Step 3: Silent refresh interceptor**

`web-ui/src/api/client.ts` — обновить `configureAuth` и interceptor:

```typescript
import axios from 'axios';
import type { AxiosRequestConfig } from 'axios';

const client = axios.create({ baseURL: '' });

let tokenGetter: () => string | null = () => null;
let onUnauthorized: (() => void) | null = null;
let refreshHandler: (() => Promise<boolean>) | null = null;

export function configureAuth(
  getToken: () => string | null,
  handler: () => void,
  refresh?: () => Promise<boolean>,
) {
  tokenGetter = getToken;
  onUnauthorized = handler;
  refreshHandler = refresh || null;
}

client.interceptors.request.use((config) => {
  const token = tokenGetter();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };
    if (error?.response?.status === 401 && !originalRequest._retry && refreshHandler) {
      originalRequest._retry = true;
      const ok = await refreshHandler();
      if (ok) {
        return client(originalRequest);
      }
    }
    if (error?.response?.status === 401 && onUnauthorized) {
      onUnauthorized();
    }
    return Promise.reject(error);
  },
);

export default client;
```

- [ ] **Step 4: Auth store — refresh_token**

`web-ui/src/stores/auth.ts` — обновить:

```typescript
import { defineStore } from 'pinia';
import { api } from '@/api';

const TOKEN_KEY = 'nas.token';
const REFRESH_KEY = 'nas.refresh_token';
const USERNAME_KEY = 'nas.username';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || null,
    refreshToken: localStorage.getItem(REFRESH_KEY) || null,
    username: localStorage.getItem(USERNAME_KEY) || '',
    isAdmin: false,
    profileLoaded: false,
  }),

  getters: {
    authenticated: (state) => state.token !== null,
  },

  actions: {
    async login(username: string, password: string) {
      const { data } = await api.login(username, password);
      this.token = data.access_token;
      this.refreshToken = data.refresh_token;
      this.username = username;
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(REFRESH_KEY, data.refresh_token);
      localStorage.setItem(USERNAME_KEY, username);
      await this.refreshProfile();
    },

    async tryRefresh(): Promise<boolean> {
      if (!this.refreshToken) return false;
      try {
        const { data } = await api.refresh(this.refreshToken);
        this.token = data.access_token;
        this.refreshToken = data.refresh_token;
        localStorage.setItem(TOKEN_KEY, data.access_token);
        localStorage.setItem(REFRESH_KEY, data.refresh_token);
        return true;
      } catch {
        this.logout();
        return false;
      }
    },

    async refreshProfile() {
      const { data } = await api.me();
      this.username = data.username;
      this.isAdmin = data.is_admin;
      this.profileLoaded = true;
      localStorage.setItem(USERNAME_KEY, data.username);
    },

    logout() {
      this.token = null;
      this.refreshToken = null;
      this.username = '';
      this.isAdmin = false;
      this.profileLoaded = false;
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
      localStorage.removeItem(USERNAME_KEY);
    },
  },
});
```

- [ ] **Step 5: Подключить refresh в configureAuth**

`web-ui/src/router/index.ts` — обновить вызов `configureAuth`:

```typescript
  configureAuth(
    () => useAuthStore().token,
    () => {
      useAuthStore().logout();
      Router.push('/login');
    },
    () => useAuthStore().tryRefresh(),
  );
```

- [ ] **Step 6: Commit**

```bash
git add web-ui/
git commit -m "feat(web): API client, auth store with silent refresh, types"
```

---

## Task 9: Web build verification

- [ ] **Step 1: Typecheck**

```bash
cd web-ui && yarn typecheck
```

Ожидаемо: ошибок нет.

- [ ] **Step 2: Build**

```bash
cd web-ui && yarn build
```

Ожидаемо: build успешен.

- [ ] **Step 3: Commit (если были фиксы)**

```bash
git add web-ui/
git commit -m "fix(web): typecheck and build fixes"
```

---

## Task 10: CLI — проект + config

**Files:**
- Create: `cli/pyproject.toml`
- Create: `cli/src/nasmanager/__init__.py`
- Create: `cli/src/nasmanager/__main__.py`
- Create: `cli/src/nasmanager/config.py`
- Create: `cli/tests/conftest.py`
- Create: `cli/tests/test_config.py`

- [ ] **Step 1: pyproject.toml**

Создать `cli/pyproject.toml`:

```toml
[project]
name = "nasmanager"
version = "0.1.0"
description = "NAS share manager with TUI"
requires-python = ">=3.11"
dependencies = [
    "textual>=0.80",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "nuitka>=2.0",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: __init__.py**

Создать `cli/src/nasmanager/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: __main__.py**

Создать `cli/src/nasmanager/__main__.py`:

```python
import sys


def main():
    if "--version" in sys.argv:
        from nasmanager import __version__
        print(f"nasmanager {__version__}")
        return

    from nasmanager.ui.main import NasManagerApp
    app = NasManagerApp()
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: config.py**

Создать `cli/src/nasmanager/config.py`:

```python
from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field, asdict
from pathlib import Path


CONFIG_DIR = Path.home() / ".config" / "nasmanager"
CONFIG_FILE = CONFIG_DIR / "config.json"
MOUNTS_FILE = CONFIG_DIR / "mounts"


@dataclass
class Config:
    server_url: str = "http://nas:8000"
    mount_root: str = "/mnt/nas"
    windows_mode: str = "drive"
    username: str = ""
    access_token: str = ""
    refresh_token: str = ""

    @classmethod
    def load(cls) -> Config | None:
        if not CONFIG_FILE.exists():
            return None
        data = json.loads(CONFIG_FILE.read_text())
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))
        CONFIG_FILE.chmod(0o600)


@dataclass
class MountEntry:
    share: str
    source_uri: str
    target: str


def load_mounts() -> list[MountEntry]:
    if not MOUNTS_FILE.exists():
        return []
    entries = []
    for line in MOUNTS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            entries.append(MountEntry(share=parts[0], source_uri=parts[1], target=parts[2]))
    return entries


def save_mounts(entries: list[MountEntry]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["# share  source_uri  target"]
    for e in entries:
        lines.append(f"{e.share}  {e.source_uri}  {e.target}")
    MOUNTS_FILE.write_text("\n".join(lines) + "\n")
    MOUNTS_FILE.chmod(0o600)


def find_free_drive_letter() -> str | None:
    """Windows: найти свободную букву диска A-Z."""
    if platform.system() != "Windows":
        return None
    for letter in "ZXWVUTSRQPONMLKJIHGFEDCBA":
        if not os.path.exists(f"{letter}:\\"):
            return letter
    return None
```

- [ ] **Step 5: Тесты config**

Создать `cli/tests/conftest.py`:

```python
import tempfile
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
```

Создать `cli/tests/test_config.py`:

```python
from nasmanager.config import Config, load_mounts, save_mounts, MountEntry, CONFIG_DIR


def test_config_save_load(config_dir):
    cfg = Config(server_url="http://test:8000", username="alice", access_token="tok123")
    cfg.save()
    loaded = Config.load()
    assert loaded is not None
    assert loaded.server_url == "http://test:8000"
    assert loaded.username == "alice"


def test_config_load_missing():
    from unittest.mock import patch
    with patch("nasmanager.config.CONFIG_FILE", __import__("pathlib").Path("/nonexistent")):
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
    from unittest.mock import patch
    with patch("nasmanager.config.MOUNTS_FILE", __import__("pathlib").Path("/nonexistent")):
        assert load_mounts() == []
```

- [ ] **Step 6: Запустить тесты**

```bash
cd cli && uv run pytest tests/test_config.py -v
```

Ожидаемо: все проходят.

- [ ] **Step 7: Commit**

```bash
git add cli/
git commit -m "feat(cli): project setup, config.py, config tests"
```

---

## Task 11: CLI — api.py + auth.py

**Files:**
- Create: `cli/src/nasmanager/api.py`
- Create: `cli/src/nasmanager/auth.py`
- Create: `cli/tests/test_api.py`

- [ ] **Step 1: api.py**

Создать `cli/src/nasmanager/api.py`:

```python
from __future__ import annotations

import httpx


class ApiError(Exception):
    def __init__(self, status: int, detail: str = ""):
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP {status}: {detail}")


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=10)

    def login(self, username: str, password: str) -> dict:
        resp = self.client.post(
            "/api/v1/auth/token",
            data={"username": username, "password": password},
        )
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        return resp.json()

    def refresh(self, refresh_token: str) -> dict:
        resp = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        return resp.json()

    def list_shares(self, access_token: str) -> list[dict]:
        resp = self.client.get(
            "/api/v1/users/me/shares",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code == 401:
            raise ApiError(401)
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 2: auth.py**

Создать `cli/src/nasmanager/auth.py`:

```python
from __future__ import annotations

from nasmanager.api import ApiClient, ApiError
from nasmanager.config import Config


def login_or_refresh(config: Config, api: ApiClient) -> str:
    """Вернуть валидный access_token. Если access_token протух — refresh, если refresh тоже — login (выбрасывает ApiError 401)."""
    if config.access_token:
        try:
            api.list_shares(config.access_token)
            return config.access_token
        except ApiError as e:
            if e.status != 401:
                raise

    if config.refresh_token:
        try:
            tokens = api.refresh(config.refresh_token)
            config.access_token = tokens["access_token"]
            config.refresh_token = tokens["refresh_token"]
            config.save()
            return config.access_token
        except ApiError:
            pass

    raise ApiError(401, "Need interactive login")
```

- [ ] **Step 3: Тесты api**

Создать `cli/tests/test_api.py`:

```python
import httpx

from nasmanager.api import ApiClient, ApiError


def _mock_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/v1/auth/token" and request.method == "POST":
        return httpx.Response(200, json={"access_token": "tok", "refresh_token": "ref", "token_type": "bearer"})
    if request.url.path == "/api/v1/users/me/shares" and request.method == "GET":
        auth = request.headers.get("authorization", "")
        if "Bearer tok" in auth:
            return httpx.Response(200, json=[{"name": "photos", "host": "nas", "port": 1445, "access": "RO"}])
        return httpx.Response(401, json={"detail": "Unauthorized"})
    if request.url.path == "/api/v1/auth/refresh" and request.method == "POST":
        return httpx.Response(200, json={"access_token": "newtok", "refresh_token": "newref", "token_type": "bearer"})
    return httpx.Response(404)


def test_login():
    transport = httpx.MockTransport(_mock_handler)
    api = ApiClient(base_url="http://test")
    api.client = httpx.Client(transport=transport, base_url="http://test")
    result = api.login("alice", "pass")
    assert result["access_token"] == "tok"


def test_list_shares_ok():
    transport = httpx.MockTransport(_mock_handler)
    api = ApiClient(base_url="http://test")
    api.client = httpx.Client(transport=transport, base_url="http://test")
    shares = api.list_shares("tok")
    assert shares[0]["name"] == "photos"


def test_list_shares_401():
    transport = httpx.MockTransport(_mock_handler)
    api = ApiClient(base_url="http://test")
    api.client = httpx.Client(transport=transport, base_url="http://test")
    import pytest
    with pytest.raises(ApiError) as exc:
        api.list_shares("badtoken")
    assert exc.value.status == 401


def test_refresh():
    transport = httpx.MockTransport(_mock_handler)
    api = ApiClient(base_url="http://test")
    api.client = httpx.Client(transport=transport, base_url="http://test")
    tokens = api.refresh("oldref")
    assert tokens["access_token"] == "newtok"
```

Запустить: `cd cli && uv run pytest tests/test_api.py -v` — проверить.

- [ ] **Step 4: Commit**

```bash
git add cli/
git commit -m "feat(cli): api client, auth helper, tests"
```

---

## Task 12: CLI — diff + mount_engine

**Files:**
- Create: `cli/src/nasmanager/diff.py`
- Create: `cli/src/nasmanager/mount_engine.py`
- Create: `cli/tests/test_diff.py`
- Create: `cli/tests/test_mount_engine.py`

- [ ] **Step 1: diff.py**

Создать `cli/src/nasmanager/diff.py`:

```python
from __future__ import annotations

import enum
from dataclasses import dataclass

from nasmanager.config import MountEntry


class ShareStatus(str, enum.Enum):
    NEW = "new"
    MOUNTED = "mounted"
    MOUNTED_NOT_REAL = "mounted_not_real"
    REVOKED = "revoked"


@dataclass
class ShareDiff:
    name: str
    host: str
    port: int
    access: str
    target: str
    status: ShareStatus


def compute_diff(
    api_shares: list[dict],
    mounts: list[MountEntry],
    is_mounted_fn,  # callable(target) -> bool
) -> list[ShareDiff]:
    """Сопоставить шары из API с записями mounts и реальным состоянием.

    Для NEW-шары target пустой (ещё не монтировалась); для MOUNTED_NOT_REAL
    и REVOKED — из записи mounts. Возвращает сортированный по имени список.
    """
    api_map = {s["name"]: s for s in api_shares}
    mount_map = {m.share: m for m in mounts}
    result = []

    for name, share in api_map.items():
        entry = mount_map.get(name)
        if entry is None:
            status = ShareStatus.NEW
            target = ""
        elif is_mounted_fn(entry.target):
            status = ShareStatus.MOUNTED
            target = entry.target
        else:
            status = ShareStatus.MOUNTED_NOT_REAL
            target = entry.target
        result.append(ShareDiff(
            name=name, host=share["host"], port=share["port"],
            access=share["access"], target=target, status=status,
        ))

    for name, entry in mount_map.items():
        if name not in api_map:
            result.append(ShareDiff(
                name=name, host="", port=0, access="",
                target=entry.target, status=ShareStatus.REVOKED,
            ))

    return sorted(result, key=lambda d: d.name)
```

- [ ] **Step 2: mount_engine.py**

Создать `cli/src/nasmanager/mount_engine.py`:

```python
from __future__ import annotations

import subprocess
import sys
import platform
from dataclasses import dataclass


@dataclass
class MountCommand:
    description: str
    command: list[str]
    is_mount: bool  # True=mount, False=umount
    target: str = ""  # фактический target (путь/буква/Junction), куда примонтируется


def is_mounted_linux(target: str) -> bool:
    try:
        result = subprocess.run(
            ["grep", "-q", target, "/proc/mounts"],
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def is_mounted_windows(target: str) -> bool:
    """Проверка по drive letter (X:) или UNC."""
    if target.endswith(":"):
        return target.lower() in _windows_drives()
    if target.startswith("\\\\"):
        result = subprocess.run(
            ["net", "use"], capture_output=True, text=True, encoding="cp1252", errors="replace"
        )
        return target.lower() in result.stdout.lower()
    return False


def _windows_drives() -> set[str]:
    result = subprocess.run(
        ["wmic", "logicaldisk", "get", "DeviceID"],
        capture_output=True, text=True, encoding="cp1252", errors="replace"
    )
    drives = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.endswith(":"):
            drives.add(line.lower())
    return drives


def plan_mount(
    share: str, host: str, port: int, username: str, mount_root: str,
    windows_mode: str = "drive", target_override: str | None = None,
) -> MountCommand:
    if sys.platform == "win32":
        return _plan_mount_windows(share, host, username, mount_root, windows_mode, target_override)
    return _plan_mount_linux(share, host, port, username, mount_root)


def _plan_mount_linux(share, host, port, username, mount_root) -> MountCommand:
    target = f"{mount_root}/{share}"
    source = f"//{host}/{share}"
    cmd = [
        "sudo", "mount", "-t", "cifs", source, target,
        "-o", f"username={username},port={port},uid=$(id -u),gid=$(id -g),dir_mode=0755,file_mode=0644",
    ]
    return MountCommand(description=f"mount {share} → {target}", command=cmd, is_mount=True, target=target)


def _plan_mount_windows(share, host, username, mount_root, windows_mode, target_override) -> MountCommand:
    source = f"\\\\{host}\\{share}"
    if windows_mode == "unc":
        cmd = ["net", "use", source, f"/user:{username}", "<PASSWORD>"]
        return MountCommand(description=f"mount {share} (UNC)", command=cmd, is_mount=True, target=source)
    if windows_mode == "folder":
        target = target_override or f"{mount_root}\\{share}"
        cmd = ["cmd", "/c", "mklink", "/J", target, source]
        return MountCommand(description=f"mount {share} → {target} (junction)", command=cmd, is_mount=True, target=target)
    # drive
    from nasmanager.config import find_free_drive_letter
    letter = find_free_drive_letter() or "X"
    cmd = ["net", "use", f"{letter}:", source, f"/user:{username}", "<PASSWORD>"]
    return MountCommand(description=f"mount {share} → {letter}:", command=cmd, is_mount=True, target=f"{letter}:")


def plan_umount(target: str) -> MountCommand:
    if sys.platform == "win32":
        if target.endswith(":"):
            return MountCommand(
                description=f"umount {target}",
                command=["net", "use", target, "/delete"],
                is_mount=False,
                target=target,
            )
        if target.startswith("\\\\"):
            return MountCommand(
                description=f"umount UNC {target}",
                command=["net", "use", target, "/delete"],
                is_mount=False,
                target=target,
            )
        return MountCommand(
            description=f"remove junction {target}",
            command=["cmd", "/c", "rmdir", target],
            is_mount=False,
            target=target,
        )
    return MountCommand(
        description=f"umount {target}",
        command=["sudo", "umount", target],
        is_mount=False,
        target=target,
    )


def execute_command(cmd: MountCommand, dry_run: bool = False, password: str | None = None) -> tuple[bool, str]:
    """Выполнить команду. dry_run=True → печатает команду без выполнения. Возвращает (ok, message)."""
    if dry_run:
        return True, f"[dry-run] {' '.join(cmd.command)}"

    actual = list(cmd.command)
    # Заменить <PASSWORD> на реальный пароль если есть
    actual = [password if p == "<PASSWORD>" else p for p in actual]

    try:
        result = subprocess.run(
            actual, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or f"exit code {result.returncode}"
        return True, "ok"
    except Exception as e:
        return False, str(e)
```

- [ ] **Step 3: Тесты diff**

Создать `cli/tests/test_diff.py`:

```python
from nasmanager.config import MountEntry
from nasmanager.diff import compute_diff, ShareStatus


def test_new_share():
    api = [{"name": "photos", "host": "nas", "port": 1445, "access": "RO"}]
    mounts = []
    diff = compute_diff(api, mounts, lambda t: False)
    assert len(diff) == 1
    assert diff[0].status == ShareStatus.NEW


def test_mounted_share():
    api = [{"name": "photos", "host": "nas", "port": 1445, "access": "RO"}]
    mounts = [MountEntry(share="photos", source_uri="//nas/photos", target="/mnt/nas/photos")]
    diff = compute_diff(api, mounts, lambda t: True)
    assert diff[0].status == ShareStatus.MOUNTED


def test_revoked_share():
    api = []
    mounts = [MountEntry(share="photos", source_uri="//nas/photos", target="/mnt/nas/photos")]
    diff = compute_diff(api, mounts, lambda t: True)
    assert diff[0].status == ShareStatus.REVOKED
```

- [ ] **Step 4: Тесты mount_engine**

Создать `cli/tests/test_mount_engine.py`:

```python
from nasmanager.mount_engine import plan_mount, plan_umount, execute_command


def test_plan_mount_linux():
    cmd = plan_mount("photos", "nas", 1445, "alice", "/mnt/nas")
    assert cmd.is_mount is True
    assert "cifs" in " ".join(cmd.command)
    assert "//nas/photos" in " ".join(cmd.command)


def test_plan_umount_linux():
    cmd = plan_umount("/mnt/nas/photos")
    assert cmd.is_mount is False
    assert "umount" in " ".join(cmd.command)


def test_execute_dry_run():
    from nasmanager.mount_engine import MountCommand
    cmd = MountCommand(description="test", command=["echo", "hello"], is_mount=True)
    ok, msg = execute_command(cmd, dry_run=True)
    assert ok is True
    assert "dry-run" in msg


def test_execute_real():
    from nasmanager.mount_engine import MountCommand
    cmd = MountCommand(description="test", command=["echo", "hello"], is_mount=True)
    ok, msg = execute_command(cmd, dry_run=False)
    assert ok is True
```

- [ ] **Step 5: Запустить тесты**

```bash
cd cli && uv run pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add cli/
git commit -m "feat(cli): diff logic, mount_engine, dry-run, tests"
```

---

## Task 13: CLI — TUI (wizard + main screen + dialogs)

**Files:**
- Create: `cli/src/nasmanager/ui/__init__.py`
- Create: `cli/src/nasmanager/ui/wizard.py`
- Create: `cli/src/nasmanager/ui/main.py`
- Create: `cli/src/nasmanager/ui/dialogs.py`

- [ ] **Step 1: ui/__init__.py**

Создать `cli/src/nasmanager/ui/__init__.py` (пустой файл).

- [ ] **Step 2: dialogs.py — модалки**

Создать `cli/src/nasmanager/ui/dialogs.py`:

```python
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Header, Input, Label, Static


class PasswordModal(ModalScreen[str]):
    """Модалка для ввода пароля (sudo/smb)."""

    def __init__(self, prompt: str = "Password:"):
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-container"):
            yield Static(self.prompt, id="dialog-label")
            yield Input(password=True, id="password-input", focus_on_load=True)
            yield Button("OK", variant="primary", id="ok")
            yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            pwd = self.query_one("#password-input", Input).value
            self.dismiss(pwd)
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class LoginModal(ModalScreen[tuple[str, str] | None]):
    """Модалка для логина."""

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-container"):
            yield Static("Логин", id="dialog-label")
            yield Input(placeholder="username", id="username-input", focus_on_load=True)
            yield Input(password=True, placeholder="password", id="password-input")
            yield Button("Войти", variant="primary", id="ok")
            yield Button("Отмена", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            u = self.query_one("#username-input", Input).value
            p = self.query_one("#password-input", Input).value
            self.dismiss((u, p))
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
```

- [ ] **Step 3: wizard.py — экран первого запуска**

Создать `cli/src/nasmanager/ui/wizard.py`:

```python
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
```

- [ ] **Step 4: main.py — главный App**

Создать `cli/src/nasmanager/ui/main.py`:

```python
from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Footer, Header, Static

from nasmanager.api import ApiClient, ApiError
from nasmanager.auth import login_or_refresh
from nasmanager.config import Config, load_mounts, MountEntry
from nasmanager.diff import compute_diff, ShareStatus
from nasmanager.mount_engine import (
    execute_command,
    is_mounted_linux,
    is_mounted_windows,
    plan_mount,
    plan_umount,
)
from nasmanager.ui.dialogs import LoginModal, PasswordModal
from nasmanager.ui.wizard import WizardScreen


class NasManagerApp(App):
    CSS = """
    #status-table { height: 1fr; }
    .new { color: green; }
    .mounted { color: cyan; }
    .revoked { color: red; }
    """

    BINDINGS = [
        Binding("m", "mount_selected", "Mount selected"),
        Binding("M", "mount_all", "Mount all new"),
        Binding("u", "umount_selected", "Unmount selected"),
        Binding("U", "umount_all", "Unmount all revoked"),
        Binding("p", "preview", "Dry-run preview"),
        Binding("s", "sync", "Sync"),
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self):
        super().__init__()
        self.config: Config | None = None
        self.api: ApiClient | None = None
        self.diff_data: list = []

    def on_mount(self) -> None:
        self.config = Config.load()
        if self.config is None:
            self.push_screen(WizardScreen(), self._on_wizard_done)
        else:
            self.api = ApiClient(self.config.server_url)
            self._do_sync()

    def _on_wizard_done(self, result) -> None:
        self.config = Config.load()
        if self.config is not None:
            self.api = ApiClient(self.config.server_url)
            self._do_sync()

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="status-table")
        yield Static("Нажмите ? для помощи", id="help-bar")
        yield Footer()

    def action_sync(self) -> None:
        self._do_sync()

    def _do_sync(self) -> None:
        self.run_worker(self._sync_worker, exclusive=True)

    async def _sync_worker(self) -> None:
        if not self.config or not self.api:
            return
        try:
            token = await asyncio.to_thread(login_or_refresh, self.config, self.api)
            shares = await asyncio.to_thread(self.api.list_shares, token)
        except ApiError as e:
            if e.status == 401:
                result = await self.push_screen_wait(LoginModal())
                if result is None:
                    return
                username, password = result
                try:
                    tokens = await asyncio.to_thread(self.api.login, username, password)
                    self.config.access_token = tokens["access_token"]
                    self.config.refresh_token = tokens["refresh_token"]
                    self.config.save()
                    shares = await asyncio.to_thread(self.api.list_shares, tokens["access_token"])
                except ApiError:
                    self.query_one("#help-bar", Static).update("Ошибка логина")
                    return
            else:
                self.query_one("#help-bar", Static).update(f"Ошибка API: {e.detail}")
                return

        mounts = load_mounts()
        import sys
        mounted_fn = is_mounted_linux if sys.platform != "win32" else is_mounted_windows
        self.diff_data = compute_diff(shares, mounts, mounted_fn)
        self._render_table()

    def _render_table(self) -> None:
        table = self.query_one("#status-table", DataTable)
        table.clear()
        table.add_columns("Share", "Access", "Status", "Target")
        for d in self.diff_data:
            status_text = {
                ShareStatus.NEW: "🆕 новая",
                ShareStatus.MOUNTED: "✅ подключена",
                ShareStatus.MOUNTED_NOT_REAL: "⚠️ подключена (нет mount)",
                ShareStatus.REVOKED: "❌ отозвана",
            }[d.status]
            table.add_row(d.name, d.access, status_text, d.target)

    def action_mount_selected(self) -> None:
        table = self.query_one("#status-table", DataTable)
        cursor = table.cursor_coordinate
        if cursor.row < len(self.diff_data):
            self._mount_shares([self.diff_data[cursor.row]])

    def action_mount_all(self) -> None:
        new_shares = [d for d in self.diff_data if d.status == ShareStatus.NEW]
        self._mount_shares(new_shares)

    async def _mount_shares(self, shares) -> None:
        if not self.config:
            return
        password = await self.push_screen_wait(PasswordModal("Пароль для sudo/mount:"))
        if password is None:
            return

        for d in shares:
            cmd = plan_mount(
                d.name, d.host, d.port, self.config.username,
                self.config.mount_root, self.config.windows_mode,
            )
            ok, msg = await asyncio.to_thread(execute_command, cmd, False, password)
            if ok:
                entry = MountEntry(
                    share=d.name,
                    source_uri=f"//{d.host}/{d.name}",
                    target=cmd.target,
                )
                mounts = load_mounts()
                mounts.append(entry)
                from nasmanager.config import save_mounts
                save_mounts(mounts)
            self.query_one("#help-bar", Static).update(f"{d.name}: {'ok' if ok else msg}")

        self._do_sync()

    def action_umount_selected(self) -> None:
        table = self.query_one("#status-table", DataTable)
        cursor = table.cursor_coordinate
        if cursor.row < len(self.diff_data):
            self._umount_shares([self.diff_data[cursor.row]])

    def action_umount_all(self) -> None:
        revoked = [d for d in self.diff_data if d.status == ShareStatus.REVOKED]
        self._umount_shares(revoked)

    async def _umount_shares(self, shares) -> None:
        from nasmanager.config import save_mounts
        for d in shares:
            cmd = plan_umount(d.target)
            ok, msg = await asyncio.to_thread(execute_command, cmd, False)
            mounts = load_mounts()
            mounts = [m for m in mounts if m.share != d.name]
            save_mounts(mounts)
            self.query_one("#help-bar", Static).update(f"{d.name}: {'umount ok' if ok else msg}")
        self._do_sync()

    def action_preview(self) -> None:
        lines = []
        for d in self.diff_data:
            if d.status == ShareStatus.NEW:
                cmd = plan_mount(d.name, d.host, d.port, self.config.username, self.config.mount_root)
                lines.append(f"[dry-run] {d.name}: {cmd.description}")
            elif d.status == ShareStatus.REVOKED:
                cmd = plan_umount(d.target)
                lines.append(f"[dry-run] {d.name}: {cmd.description}")
            else:
                lines.append(f"[skip]   {d.name}: {d.status.value}")
        self.query_one("#help-bar", Static).update(" | ".join(lines) if lines else "Нет действий")

    def action_help(self) -> None:
        help_text = (
            "m=mount selected | M=mount all new | u=umount selected | "
            "U=umount all revoked | p=preview dry-run | s=sync | q=quit"
        )
        self.query_one("#help-bar", Static).update(help_text)
```

- [ ] **Step 5: Commit**

```bash
git add cli/src/nasmanager/ui/
git commit -m "feat(cli): TUI — wizard, main screen with table, dialogs, dry-run preview"
```

---

## Task 14: CLI — Nuitka builds + justfile targets

**Files:**
- Create: `cli/build_linux.sh`
- Create: `cli/build_windows.ps1`
- Modify: `justfile`

- [ ] **Step 1: build_linux.sh**

Создать `cli/build_linux.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
uv run --with nuitka \
  --no-cache \
  nuitka --standalone --onefile \
    --include-package=textual \
    --include-package-data=textual \
    --include-package=httpx \
    --output-filename=dist/nasmanager-linux-x86_64 \
    src/nasmanager
```

```bash
chmod +x cli/build_linux.sh
```

- [ ] **Step 2: build_windows.ps1**

Создать `cli/build_windows.ps1`:

```powershell
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force -Path dist | Out-Null
uv run --with nuitka `
  --no-cache `
  nuitka --standalone --onefile `
    --include-package=textual `
    --include-package-data=textual `
    --include-package=httpx `
    --output-filename=dist\nasmanager-windows-x86_64.exe `
    src\nasmanager
```

- [ ] **Step 3: добавить targets в justfile**

Добавить в `justfile` (в секцию `# ---------- Clients ----------` или в конец):

```makefile
# ---------- CLI ----------

## Build CLI for Linux (requires uv + nuitka)
cli-build-linux:
	bash cli/build_linux.sh

## Run CLI tests
cli-test:
	cd cli && uv run pytest -v

## Build CLI for Windows (run on Windows machine)
## cli-build-windows: run cli/build_windows.ps1 on Windows
```

- [ ] **Step 4: Commit**

```bash
git add cli/build_linux.sh cli/build_windows.ps1 justfile
git commit -m "feat(cli): Nuitka build scripts, justfile targets"
```

---

## Task 15: README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Добавить раздел CLI**

Добавить в `README.md` перед разделом «Running»:

```markdown
## Self-Service & CLI

### Веб-интерфейс
- `/` — «Мои шары»: список доступных шар, кнопки скачивания CLI, ручное подключение.
- `/profile` — профиль, смена пароля.
- `/admin` — панель администратора (только для admin-учётных записей).

### CLI `nasmanager`
Python-пакет с TUI (Textual), собирается в автономный бинарь через Nuitka.

**Установка:**
- Скачайте бинарь со страницы «Мои шары» в web-интерфейсе.
- Linux: `chmod +x nasmanager-linux-x86_64 && ./nasmanager-linux-x86_64`
- Windows: запустите `nasmanager-windows-x86_64.exe`

**Команды TUI:**
| Клавиша | Действие |
|---|---|
| `m` | Mount выбранной шары |
| `M` | Mount всех новых шар |
| `u` | Umount выбранной шары |
| `U` | Umount всех отозванных шар |
| `p` | Dry-run preview |
| `s` | Sync (обновить список шар) |
| `q` | Выход |

**Сборка из исходников:**
```bash
just cli-build-linux   # Linux
# Windows: cli/build_windows.ps1
```

**Тесты CLI:**
```bash
just cli-test
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add CLI and self-service section to README"
```

---

## Task 16: Финальная проверка

- [ ] **Step 1: Backend tests**

```bash
just test
```

Все тесты проходят.

- [ ] **Step 2: CLI tests**

```bash
just cli-test
```

Все тесты проходят.

- [ ] **Step 3: Web build**

```bash
cd web-ui && yarn typecheck && yarn build
```

Без ошибок.

- [ ] **Step 4: Manual integration (если есть docker-окружение)**

```bash
just up
```

Проверить в браузере: логин обычного пользователя → страница «Мои шары», кнопки скачивания, смена пароля в «Профиль», admin → `/admin`.

- [ ] **Step 5: Финальный commit (если были фиксы)**

```bash
git add -A && git commit -m "fix: final integration fixes"
```
