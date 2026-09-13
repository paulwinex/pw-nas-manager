# Web UI (Vue 3 + Quasar 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin web-UI «NAS Manager» (Anglophone UI) on Vue 3 + Quasar 2 — manage users/groups/shares, login/logout, dashboard, system tools — served in production by the existing FastAPI app.

**Architecture:** Quasar SPA in `web-ui/`, hash router, dark theme by default, boxed layout (sidebar + toolbar). Dev: Vite dev-server proxies `/api` → `http://localhost:8000`. Prod: multi-stage Dockerfile builds the SPA and FastAPI serves `web-ui/dist/spa` via `StaticFiles(html=True)` on `/`. Backend additions: `GET /api/v1/auth/me` and `GET /api/v1/stats`.

**Tech Stack:** Vue 3 (Composition API), Quasar 2 (QComponents, `date` util), pinia, vue-router 5 auto-routes, axios, TypeScript strict; backend: FastAPI, pytest.

**Repo layout reminder:** `just build` = `docker compose -f deploy/compose.yml --project-directory . build` (true working dir is repo root for `-f/-project-directory`); `just test` runs the whole pytest suite in the `tools` service reusing image `nas-manager:dev` and does **not** accept extra args, so targeted runs use `docker compose -f deploy/compose.yml --project-directory . run --rm test uv run pytest <path> -v`; `just ui-dev`, `just ui-typecheck`, `just ui-build` (added in Task 4) run yarn commands in `web-ui/`. Frontend test strategy: there is **no JS test runner** in the scaffold, so the failing-test step for frontend work is `yarn typecheck` (type errors fail the build) followed by `yarn build`.

---

## Phase A — Backend

### Task 1: `GET /api/v1/auth/me`

**Files:**
- Modify: `app/modules/auth/routes.py`
- Test: `tests/test_auth.py`

- [x] **Step 1: Write the failing tests**

Append to `tests/test_auth.py`:

```python
def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_current_admin(client, auth):
    response = client.get("/api/v1/auth/me", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["is_admin"] is True
    assert body["id"]
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `docker compose -f deploy/compose.yml --project-directory . run --rm test uv run pytest tests/test_auth.py -k me -v`
Expected: FAIL — `404 Not Found` (endpoint missing).

- [x] **Step 3: Implement the endpoint**

In `app/modules/auth/routes.py`, update imports and add the route:

```python
from app.modules.users.schemas import UserOut
from app.modules.auth.dependencies import get_current_admin
```

```python
@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_admin)) -> UserOut:
    return UserOut.model_validate(current)
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `docker compose -f deploy/compose.yml --project-directory . run --rm test uv run pytest tests/test_auth.py -k me -v`
Expected: 2 passed.

- [x] **Step 5: Run the full backend suite**

Run: `just test`
Expected: previous 32 + 2 = `34 passed` (all green).

- [x] **Step 6: Commit**

```bash
git add app/modules/auth/routes.py tests/test_auth.py
git commit -m "feat(auth): GET /auth/me for the current admin"
```

### Task 2: `GET /api/v1/stats` (dashboard metrics)

**Files:**
- Create: `app/modules/stats/__init__.py`, `app/modules/stats/schemas.py`, `app/modules/stats/services.py`, `app/modules/stats/routes.py`
- Modify: `app/api/v1/router.py`
- Test: `tests/test_stats.py`

- [x] **Step 1: Write the failing tests**

Create `tests/test_stats.py`:

```python
from datetime import datetime, timedelta, timezone


def test_stats_requires_auth(client):
    assert client.get("/api/v1/stats").status_code == 401


def test_stats_counts_and_expiring(client, auth, fake_runner):
    user = client.post(
        "/api/v1/users", headers=auth, json={"username": "zuser", "password": "secret123"}
    )
    assert user.status_code == 201, user.text
    group = client.post("/api/v1/groups", headers=auth, json={"name": "zteam"})
    assert group.status_code == 201, group.text
    share = client.post("/api/v1/shares", headers=auth, json={"name": "zdata"})
    assert share.status_code == 201, share.text

    expires = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    member = client.post(
        f"/api/v1/groups/{group.json()['id']}/members",
        headers=auth,
        json={"user_id": user.json()["id"], "access_level": "rw", "expires_at": expires},
    )
    assert member.status_code == 201, member.text

    stats = client.get("/api/v1/stats", headers=auth)
    assert stats.status_code == 200
    body = stats.json()
    assert body["users_count"] == 2  # admin + zuser
    assert body["admins_count"] == 1
    assert body["groups_count"] == 1
    assert body["shares_count"] == 1
    assert body["memberships_count"] == 1
    assert body["registry_shares_count"] == 0
    assert len(body["expiring_memberships"]) == 1
    exp = body["expiring_memberships"][0]
    assert exp["username"] == "zuser"
    assert exp["group_name"] == "zteam"
    assert exp["access_level"] == "rw"


def test_stats_excludes_far_expiry(client, auth, fake_runner):
    user = client.post(
        "/api/v1/users", headers=auth, json={"username": "zuser2", "password": "secret123"}
    ).json()
    group = client.post("/api/v1/groups", headers=auth, json={"name": "zteam2"}).json()
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    client.post(
        f"/api/v1/groups/{group['id']}/members",
        headers=auth,
        json={"user_id": user["id"], "access_level": "ro", "expires_at": expires},
    )
    body = client.get("/api/v1/stats", headers=auth).json()
    assert body["expiring_memberships"] == []
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `docker compose -f deploy/compose.yml --project-directory . run --rm test uv run pytest tests/test_stats.py -v`
Expected: FAIL — `404` on `/api/v1/stats`.

- [x] **Step 3: Implement the stats module**

`app/modules/stats/schemas.py`:

```python
from datetime import datetime

from pydantic import BaseModel


class ExpiringMember(BaseModel):
    user_id: str
    username: str
    group_id: str
    group_name: str
    access_level: str
    expires_at: datetime


class StatsResponse(BaseModel):
    users_count: int
    admins_count: int
    groups_count: int
    personal_groups_count: int
    shares_count: int
    registry_shares_count: int
    memberships_count: int
    expiring_memberships: list[ExpiringMember]
```

`app/modules/stats/services.py`:

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, Share, User, UserGroup, UserGroupExpiration
from app.modules.samba import sync_engine
from app.modules.stats.schemas import ExpiringMember, StatsResponse

EXPIRY_WINDOW_DAYS = 7


async def compute_stats(session: AsyncSession) -> StatsResponse:
    users_count = await session.scalar(select(func.count()).select_from(User)) or 0
    admins_count = (
        await session.scalar(
            select(func.count()).select_from(User).where(User.is_admin.is_(True))
        )
        or 0
    )
    groups_count = await session.scalar(select(func.count()).select_from(Group)) or 0
    personal_groups_count = (
        await session.scalar(
            select(func.count()).select_from(Group).where(Group.is_personal.is_(True))
        )
        or 0
    )
    shares_count = await session.scalar(select(func.count()).select_from(Share)) or 0
    memberships_count = await session.scalar(select(func.count()).select_from(UserGroup)) or 0

    registry_shares_count = len(await sync_engine.registry_state())

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=EXPIRY_WINDOW_DAYS)
    rows = (
        await session.execute(
            select(
                UserGroupExpiration.user_id,
                User.username,
                UserGroupExpiration.group_id,
                Group.name,
                UserGroup.access_level,
                UserGroupExpiration.expires_at,
            )
            .join(User, User.id == UserGroupExpiration.user_id)
            .join(Group, Group.id == UserGroupExpiration.group_id)
            .join(
                UserGroup,
                (UserGroup.user_id == UserGroupExpiration.user_id)
                & (UserGroup.group_id == UserGroupExpiration.group_id),
            )
            .where(
                UserGroupExpiration.is_active.is_(True),
                UserGroupExpiration.expires_at >= now,
                UserGroupExpiration.expires_at <= horizon,
            )
            .order_by(UserGroupExpiration.expires_at)
        )
    ).all()
    expiring = [
        ExpiringMember(
            user_id=user_id,
            username=username,
            group_id=group_id,
            group_name=group_name,
            access_level=access_level.value,
            expires_at=expires_at,
        )
        for user_id, username, group_id, group_name, access_level, expires_at in rows
    ]

    return StatsResponse(
        users_count=users_count,
        admins_count=admins_count,
        groups_count=groups_count,
        personal_groups_count=personal_groups_count,
        shares_count=shares_count,
        registry_shares_count=registry_shares_count,
        memberships_count=memberships_count,
        expiring_memberships=expiring,
    )
```

`app/modules/stats/routes.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_admin
from app.modules.stats.schemas import StatsResponse
from app.modules.stats.services import compute_stats

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("", response_model=StatsResponse)
async def get_stats(session: AsyncSession = Depends(get_session)) -> StatsResponse:
    return await compute_stats(session)
```

`app/modules/stats/__init__.py`: empty file.

Register in `app/api/v1/router.py` (add import + include):

```python
from app.modules.stats.routes import router as stats_router
```

```python
api_router.include_router(stats_router)
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `docker compose -f deploy/compose.yml --project-directory . run --rm test uv run pytest tests/test_stats.py -v`
Expected: 3 passed.

- [x] **Step 5: Run the full backend suite**

Run: `just test`
Expected: `37 passed`.

- [x] **Step 6: Commit**

```bash
git add app/modules/stats app/api/v1/router.py tests/test_stats.py
git commit -m "feat(stats): GET /api/v1/stats for the dashboard"
```

### Task 3: Serve the built UI from FastAPI

**Files:**
- Modify: `app/core/settings.py`
- Modify: `app/main.py`

- [x] **Step 1: Add `ui_dist_dir` setting**

In `app/core/settings.py`, extend `Settings`:

```python
    ui_dist_dir: Path = Path("./ui-dist")
```

- [x] **Step 2: Mount static files conditionally**

In `app/main.py`, change imports and `create_app()`:

```python
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from app.core.settings import get_settings
```

```python
def create_app() -> FastAPI:
    app = FastAPI(title="NAS Manager", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    dist_dir = Path(get_settings().ui_dist_dir)
    if dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="ui")
    return app
```

- [x] **Step 3: Verify tests still pass (no dist → no mount)**

Run: `just test`
Expected: `37 passed` (path `ui-dist` does not exist in the test env → UI not mounted, `/api` untouched).

- [x] **Step 4: Verify the endpoint list**

Run: `docker compose -f deploy/compose.yml --project-directory . run --rm test uv run pytest tests/test_auth.py -k me -v`
Expected: 2 passed.

- [x] **Step 5: Commit**

```bash
git add app/core/settings.py app/main.py
git commit -m "feat: serve web-ui dist from FastAPI when present"
```

### Task 4: Infra — Dockerfile multi-stage, .dockerignore, just recipes, README

**Files:**
- Modify: `deploy/Dockerfile`
- Create: `.dockerignore`
- Modify: `justfile`
- Modify: `README.md`

- [x] **Step 1: Multi-stage Dockerfile**

Rewrite `deploy/Dockerfile`:

```dockerfile
# --- UI build stage ---
FROM node:22-alpine AS ui-build
WORKDIR /app/ui
COPY web-ui/package.json web-ui/yarn.lock ./
RUN yarn install --frozen-lockfile
COPY web-ui ./
RUN yarn build

# --- Python runtime ---
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        samba smbclient python3 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml ./
RUN uv sync --all-extras

ENV PATH="/app/.venv/bin:$PATH" \
    UV_NO_SYNC=1

COPY app ./app
COPY deploy/smb.conf.template ./deploy/smb.conf.template
COPY deploy/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --from=ui-build /app/ui/dist/spa ./ui-dist
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p /mnt/share /data /var/lib/samba/private /var/log/samba

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
```

- [x] **Step 2: Create `.dockerignore` (repo root)**

```gitignore
.git/
.venv/
__pycache__/
*.pyc
*.pyo
.env
data/
share/
docs/
tests/
web-ui/node_modules/
web-ui/dist/
```

- [x] **Step 3: Add just recipes for the UI**

Append to `justfile` (a new section before `# ---------- Clients ----------`):

```just
# ---------- UI (web-ui) ----------

## Start the Quasar dev server (proxies /api to localhost:8000)
[working-directory: 'web-ui']
ui-dev:
    yarn dev

## Type-check the frontend
[working-directory: 'web-ui']
ui-typecheck:
    yarn typecheck

## Build the frontend production bundle
[working-directory: 'web-ui']
ui-build:
    yarn build
```

- [x] **Step 4: Rebuild the image and check it still boots**

Run: `just build`
Then: `just up` (or `docker compose -f deploy/compose.yml --project-directory . up -d`)
Then: `curl -s http://localhost:8000/api/v1/health`
Expected: `{"status":"ok"}`.

- [x] **Step 5: Update README**

In `README.md`, rewrite section 4 (or the run/options part) to include:

```markdown
### Веб-интерфейс (web-ui)

- Админка: Vue 3 + Quasar 2 в `web-ui/` (английский язык).
- Dev: `just ui-dev` — dev-сервер, `/api` уходит на `http://localhost:8000` (CORS не нужен).
- Type-check: `just ui-typecheck`. Сборка: `just ui-build` (в `web-ui/dist/spa`).
- Prod: образ собирается многоступенчато — UI собирается и раздаётся FastAPI по `/`
  (порт 8000). Если `ui-dist` в образе отсутствует, UI не монтируется.
- Логин: `http://localhost:8000` → Sign in (admin/admin123). `/docs` — Swagger как раньше.
```

- [x] **Step 6: Commit**

```bash
git add deploy/Dockerfile .dockerignore justfile README.md
git commit -m "build: multi-stage Dockerfile builds and serves web-ui"
```

---

## Phase B — Frontend foundation

> Node engines in `web-ui/package.json` require Node >= 22.12 — the host already has it (scaffold deps installed). All yarn commands below run with working dir `web-ui/`.

### Task 5: Dark theme, vite proxy, axios

**Files:**
- Modify: `web-ui/quasar.config.ts`
- Modify: `web-ui/package.json`, `web-ui/yarn.lock`
- Create: `web-ui/src/boot/dark.ts`

- [x] **Step 1: Install axios**

Run (workdir `web-ui`): `yarn add axios`
Expected: axios added to `dependencies` in `package.json` and `yarn.lock` updated.

- [x] **Step 2: Configure dark theme + proxy in `quasar.config.ts`**

In the `framework` block, set config and plugins:

```ts
    framework: {
      config: {
        dark: true
      },
      plugins: []
    },
```

In `devServer`, keep `open: true` and add the proxy:

```ts
    devServer: {
      // vueDevtools: true,
      // https: true,
      open: true, // opens browser window automatically
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true
        }
      }
    },
```

In the `boot:` list:

```ts
    boot: [
      'dark'
    ],
```

- [x] **Step 3: Dark persistence boot file**

Create `web-ui/src/boot/dark.ts`:

```ts
import { Dark } from 'quasar';

export default () => {
  const saved = localStorage.getItem('nas.dark');
  Dark.set(saved === null ? true : saved === '1');
};
```

> NOTE: use `Dark.set` (the "outside a Vue file" API), NOT `useQuasar()` — `useQuasar()` is `undefined` in a boot-file's non-component context and would crash the app at boot (blank page). `useQuasar` remains available for component SFCs.

- [x] **Step 4: Verify type-check**

Run: `just ui-typecheck`
Expected: exit 0 (config/boot compile).

- [x] **Step 5: Commit**

```bash
git add web-ui/package.json web-ui/yarn.lock web-ui/quasar.config.ts web-ui/src/boot/dark.ts
git commit -m "feat(ui): dark theme by default + dev proxy for /api"
```

- [x] **Step 6: Commit the remaining scaffold baseline**

The Quasar scaffold files (`index.html`, `src/App.vue`, `src/router/`, `src/pages/`, `src/css/`, `tsconfig.json`, `env.d.ts`, `postcss.config.js`, `public/`, `.vscode/`, `.gitignore`, `.editorconfig`, `web-ui/README.md`) are only committed here — otherwise a clean checkout cannot build the UI. They should still be committed AFTER the axios/dark change so the first UI commit stays focused:

```bash
git add web-ui
git commit -m "chore(ui): commit Quasar scaffold baseline"
```

(Delete any stray non-scaffold files in `web-ui/` first: `pnpm-workspace.yaml` and the throwaway `test-quasar*.mjs` harnesses.)

### Task 6: API client, types, typed endpoints

**Files:**
- Create: `web-ui/src/api/client.ts`
- Create: `web-ui/src/api/types.ts`
- Create: `web-ui/src/api/index.ts`

- [x] **Step 1: Write API client**

`web-ui/src/api/client.ts`:

```ts
import axios from 'axios';

const client = axios.create({ baseURL: '' });

let tokenGetter: () => string | null = () => null;
let onUnauthorized: (() => void) | null = null;

export function configureAuth(getToken: () => string | null, handler: () => void) {
  tokenGetter = getToken;
  onUnauthorized = handler;
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
  (error) => {
    if (error?.response?.status === 401 && onUnauthorized) {
      onUnauthorized();
    }
    return Promise.reject(error);
  }
);

export default client;
```

- [x] **Step 2: Write shared types**

`web-ui/src/api/types.ts`:

```ts
export interface UserOut {
  id: string;
  username: string;
  created_at: string;
  is_admin: boolean;
}

export interface GroupOut {
  id: string;
  name: string;
  is_personal: boolean;
}

export type AccessLevel = 'ro' | 'rw';

export interface MemberOut {
  user_id: string;
  username: string;
  access_level: AccessLevel;
  expires_at: string | null;
}

export interface ShareOut {
  id: string;
  name: string;
  path: string;
}

export interface SyncReport {
  added: string[];
  removed: string[];
  updated: string[];
  params_set: Record<string, string[]>;
}

export interface ExpiringMember {
  user_id: string;
  username: string;
  group_id: string;
  group_name: string;
  access_level: AccessLevel;
  expires_at: string;
}

export interface StatsResponse {
  users_count: number;
  admins_count: number;
  groups_count: number;
  personal_groups_count: number;
  shares_count: number;
  registry_shares_count: number;
  memberships_count: number;
  expiring_memberships: ExpiringMember[];
}

export type RegistryState = Record<string, Record<string, string>>;

export interface ShareAccess {
  name: string;
  path: string;
  access: string;
}

export interface MountScriptResponse {
  username: string;
  shares: ShareAccess[];
  windows_script: string;
  linux_script: string;
}
```

- [x] **Step 3: Write typed endpoints**

`web-ui/src/api/index.ts`:

```ts
import client from './client';
import type {
  GroupOut,
  MemberOut,
  MountScriptResponse,
  RegistryState,
  ShareOut,
  StatsResponse,
  SyncReport,
  UserOut,
} from './types';

export const api = {
  // auth
  login: (username: string, password: string) => {
    const form = new URLSearchParams();
    form.set('username', username);
    form.set('password', password);
    return client.post<{ access_token: string; token_type: string }>('/api/v1/auth/token', form);
  },
  me: () => client.get<UserOut>('/api/v1/auth/me'),
  stats: () => client.get<StatsResponse>('/api/v1/stats'),
  health: () => client.get<{ status: string }>('/api/v1/health'),

  // users
  listUsers: () => client.get<UserOut[]>('/api/v1/users'),
  createUser: (body: { username: string; password: string; is_admin: boolean }) =>
    client.post<UserOut>('/api/v1/users', body),
  changeUserPassword: (id: string, newPassword: string) =>
    client.post<UserOut>(`/api/v1/users/${id}/password`, { new_password: newPassword }),
  deleteUser: (id: string) => client.delete<void>(`/api/v1/users/${id}`),
  mountScript: (username: string, password: string) =>
    client.post<MountScriptResponse>(`/api/v1/users/${username}/mount-script`, { password }),

  // groups
  listGroups: () => client.get<GroupOut[]>('/api/v1/groups'),
  createGroup: (name: string) => client.post<GroupOut>('/api/v1/groups', { name }),
  deleteGroup: (id: string) => client.delete<void>(`/api/v1/groups/${id}`),
  listMembers: (groupId: string) => client.get<MemberOut[]>(`/api/v1/groups/${groupId}/members`),
  addMember: (
    groupId: string,
    body: { user_id: string; access_level: string; expires_at: string | null }
  ) => client.post<MemberOut>(`/api/v1/groups/${groupId}/members`, body),
  removeMember: (groupId: string, userId: string) =>
    client.delete<void>(`/api/v1/groups/${groupId}/members/${userId}`),
  listGroupShares: (groupId: string) => client.get<ShareOut[]>(`/api/v1/groups/${groupId}/shares`),
  linkShare: (groupId: string, shareId: string) =>
    client.post<ShareOut>(`/api/v1/groups/${groupId}/shares`, { share_id: shareId }),
  unlinkShare: (groupId: string, shareId: string) =>
    client.delete<void>(`/api/v1/groups/${groupId}/shares/${shareId}`),

  // shares
  listShares: () => client.get<ShareOut[]>('/api/v1/shares'),
  availableDirs: () => client.get<string[]>('/api/v1/shares/available'),
  createShare: (name: string) => client.post<ShareOut>('/api/v1/shares', { name }),
  deleteShare: (id: string) => client.delete<void>(`/api/v1/shares/${id}`),

  // system
  sync: () => client.post<SyncReport>('/api/v1/sync'),
  sweep: () =>
    client.post<{ processed: number; sync: SyncReport | null }>('/api/v1/expirations/sweep'),
  registry: () => client.get<RegistryState>('/api/v1/registry/shares'),
};
```

- [x] **Step 4: Verify type-check**

Run: `just ui-typecheck`
Expected: exit 0.

- [x] **Step 5: Commit**

```bash
git add web-ui/src/api
git commit -m "feat(ui): typed API client and endpoints"
```

### Task 7: Auth store + route guard

**Files:**
- Create: `web-ui/src/stores/auth.ts`
- Delete: `web-ui/src/stores/example-store.ts`
- Modify: `web-ui/src/router/index.ts`

- [x] **Step 1: Write the auth store**

Create `web-ui/src/stores/auth.ts`:

```ts
import { defineStore } from 'pinia';
import { api } from '@/api';

const TOKEN_KEY = 'nas.token';
const USERNAME_KEY = 'nas.username';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || null,
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
      this.username = username;
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(USERNAME_KEY, username);
      await this.refreshProfile();
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
      this.username = '';
      this.isAdmin = false;
      this.profileLoaded = false;
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USERNAME_KEY);
    },
  },
});
```

- [x] **Step 2: Delete the demo store**

Run: `rm web-ui/src/stores/example-store.ts`

- [x] **Step 3: Add the route guard + 401 handling**

Rewrite `web-ui/src/router/index.ts`:

```ts
import { defineRouter } from '#q-app';
import { routes, handleHotUpdate } from 'vue-router/auto-routes';
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';
import { configureAuth } from '@/api/client';
import { useAuthStore } from '@/stores/auth';

export default defineRouter(() => {
  const createHistory = import.meta.env.QUASAR_SERVER
    ? createMemoryHistory
    : (import.meta.env.QUASAR_VUE_ROUTER_MODE === 'history' ? createWebHistory : createWebHashHistory);

  const Router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createHistory(import.meta.env.QUASAR_VUE_ROUTER_BASE),
  });

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
    return true;
  });

  configureAuth(
    () => useAuthStore().token,
    () => {
      useAuthStore().logout();
      Router.push('/login');
    }
  );

  if (import.meta.hot) {
    handleHotUpdate(Router);
  }

  return Router;
});
```

- [x] **Step 4: Verify type-check**

Run: `just ui-typecheck`
Expected: exit 0.

- [x] **Step 5: Commit**

```bash
git add web-ui/src/stores/auth.ts web-ui/src/router/index.ts
git rm web-ui/src/stores/example-store.ts
git commit -m "feat(ui): auth store, route guard and 401 handling"
```

### Task 8: MainLayout + layout root, remove demo files

**Files:**
- Create: `web-ui/src/layouts/MainLayout.vue`
- Rewrite: `web-ui/src/pages/index.vue`
- Rewrite: `web-ui/src/css/app.scss`
- Delete: `web-ui/src/pages/index/second.vue`, `web-ui/src/components/EssentialLink.vue`

- [x] **Step 1: Create MainLayout**

`web-ui/src/layouts/MainLayout.vue`:

```vue
<template>
  <q-layout view="hHh lpR lFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-btn flat round dense icon="menu" aria-label="Menu" @click="leftDrawerOpen = !leftDrawerOpen" />
        <q-toolbar-title class="cursor-pointer" @click="router.push('/')">
          NAS Manager
        </q-toolbar-title>
        <q-btn-dropdown flat no-caps :label="auth.username || 'Account'" icon="person">
          <q-list style="min-width: 200px">
            <q-item clickable v-close-popup to="/profile">
              <q-item-section avatar>
                <q-icon name="account_circle" />
              </q-item-section>
              <q-item-section>Profile</q-item-section>
            </q-item>
            <q-separator />
            <q-item clickable v-close-popup @click="logout">
              <q-item-section avatar>
                <q-icon name="logout" />
              </q-item-section>
              <q-item-section>Exit</q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>
      </q-toolbar>
    </q-header>

    <q-drawer v-model="leftDrawerOpen" show-if-above bordered>
      <q-list padding>
        <q-item
          v-for="item in navItems"
          :key="item.to"
          clickable
          :to="item.to"
          exact
          class="rounded-borders q-mb-xs"
        >
          <q-item-section avatar>
            <q-icon :name="item.icon" />
          </q-item-section>
          <q-item-section>{{ item.label }}</q-item-section>
        </q-item>
      </q-list>
    </q-drawer>

    <q-page-container>
      <main class="page-box q-py-md">
        <router-view />
      </main>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();
const leftDrawerOpen = ref(false);

const navItems = [
  { to: '/', label: 'Dashboard', icon: 'dashboard' },
  { to: '/users', label: 'Users', icon: 'people' },
  { to: '/shares', label: 'Shares', icon: 'folder_shared' },
  { to: '/groups', label: 'Groups', icon: 'groups' },
  { to: '/system', label: 'System', icon: 'settings' },
];

function logout() {
  auth.logout();
  router.push('/login');
}
</script>
```

- [x] **Step 2: Rewrite the layout root page**

`web-ui/src/pages/index.vue`:

```vue
<template>
  <MainLayout />
</template>

<script setup lang="ts">
import MainLayout from '@/layouts/MainLayout.vue';
</script>
```

- [x] **Step 3: Boxed container helper**

`web-ui/src/css/app.scss`:

```scss
.page-box {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
}
```

- [x] **Step 4: Delete demo files**

Run:
```bash
rm web-ui/src/pages/index/second.vue web-ui/src/components/EssentialLink.vue
```

- [x] **Step 5: Verify type-check + build**

Run: `just ui-typecheck`
Expected: exit 0.
Run: `just ui-build`
Expected: SPA bundles to `web-ui/dist/spa`.

- [x] **Step 6: Commit**

```bash
git add web-ui/src/layouts web-ui/src/pages/index.vue web-ui/src/css/app.scss
git rm web-ui/src/pages/index/second.vue web-ui/src/components/EssentialLink.vue
git commit -m "feat(ui): boxed MainLayout with nav drawer and user menu"
```

---

## Phase C — Pages

> Every page below is verified with `just ui-typecheck` before its commit. After the last page, run `just ui-build` again.

### Task 9: Login page

**Files:**
- Create: `web-ui/src/pages/login.vue`
- Rewrite: `web-ui/src/pages/index/(index).vue` to a placeholder (Dashboard lands in Task 10)

- [x] **Step 1: Create the login page**

`web-ui/src/pages/login.vue`:

```vue
<template>
  <q-page class="login-page flex flex-center">
    <q-card class="login-card">
      <q-card-section class="text-center q-pt-xl">
        <q-icon name="folder_shared" size="56px" color="primary" />
        <div class="text-h5 q-mt-sm">NAS Manager</div>
        <div class="text-caption text-grey">Sign in to continue</div>
      </q-card-section>

      <q-card-section>
        <q-form @submit="onSubmit" class="q-gutter-md">
          <q-input
            v-model="username"
            label="Username"
            outlined
            autofocus
            :disable="loading"
          />
          <q-input
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            label="Password"
            outlined
            :disable="loading"
          >
            <template v-slot:append>
              <q-icon
                :name="showPassword ? 'visibility_off' : 'visibility'"
                class="cursor-pointer"
                @click="showPassword = !showPassword"
              />
            </template>
          </q-input>

          <div v-if="error" class="text-negative">{{ error }}</div>

          <q-btn
            type="submit"
            label="Sign in"
            color="primary"
            unelevated
            class="full-width"
            :loading="loading"
          />
        </q-form>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();

const username = ref('');
const password = ref('');
const showPassword = ref(false);
const loading = ref(false);
const error = ref('');

async function onSubmit() {
  loading.value = true;
  error.value = '';
  try {
    await auth.login(username.value, password.value);
    router.push('/');
  } catch (e: any) {
    const status = e?.response?.status;
    if (status === 401) {
      error.value = 'Invalid username or password';
    } else if (status === 403) {
      error.value = 'Administrator privileges required';
    } else {
      error.value = 'Cannot reach the server';
    }
  } finally {
    loading.value = false;
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  background: $dark;
}

.login-card {
  width: 100%;
  max-width: 380px;
}
</style>
```

- [x] **Step 2: Placeholder dashboard**

Temporarily replace the contents of `web-ui/src/pages/index/(index).vue` with:

```vue
<template>
  <q-page class="q-pa-md">
    <div class="text-h5">Dashboard</div>
  </q-page>
</template>
```

- [x] **Step 3: Verify type-check**

Run: `just ui-typecheck`
Expected: exit 0.

- [x] **Step 4: Commit**

```bash
git add web-ui/src/pages/login.vue web-ui/src/pages/index/\(index\).vue
git commit -m "feat(ui): login page"
```

### Task 10: Dashboard page

**Files:**
- Rewrite: `web-ui/src/pages/index/(index).vue`

- [x] **Step 1: Implement the dashboard**

Rewrite `web-ui/src/pages/index/(index).vue`:

```vue
<template>
  <q-page class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div class="text-h5">Dashboard</div>
      <q-btn flat round icon="refresh" @click="load" :loading="loading" />
    </div>

    <template v-if="stats">
      <div class="row q-col-gutter-md">
        <q-card v-for="c in cards" :key="c.label" class="col-xs-6 col-md-4 col-xl-2">
          <q-card-section class="text-center">
            <q-icon :name="c.icon" :color="c.color" size="34px" />
            <div class="text-h5 q-mt-xs">{{ c.value }}</div>
            <div class="text-caption text-grey">{{ c.label }}</div>
          </q-card-section>
        </q-card>
      </div>

      <q-card class="q-mt-md">
        <q-card-section>
          <div class="text-subtitle1">Expiring memberships (next 7 days)</div>
        </q-card-section>
        <q-card-section v-if="stats.expiring_memberships.length === 0" class="text-grey">
          None
        </q-card-section>
        <q-markup-table v-else>
          <thead>
            <tr>
              <th class="text-left">User</th>
              <th class="text-left">Group</th>
              <th class="text-right">Access</th>
              <th class="text-right">Expires</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(m, i) in stats.expiring_memberships" :key="i">
              <td class="text-left">{{ m.username }}</td>
              <td class="text-left">{{ m.group_name }}</td>
              <td class="text-right">
                <q-badge
                  :color="m.access_level === 'rw' ? 'teal' : 'blue-grey'"
                  :label="m.access_level.toUpperCase()"
                />
              </td>
              <td class="text-right">{{ formatDate(m.expires_at) }}</td>
            </tr>
          </tbody>
        </q-markup-table>
      </q-card>

      <q-card class="q-mt-md">
        <q-card-section>
          <div class="text-subtitle1">API status</div>
        </q-card-section>
        <q-card-section class="row items-center q-col-gutter-md">
          <q-badge :color="health === 'ok' ? 'positive' : 'negative'">
            {{ health ?? 'unknown' }}
          </q-badge>
          <span class="text-grey">Registry: {{ stats.registry_shares_count }} shares</span>
        </q-card-section>
      </q-card>
    </template>
    <div v-else class="text-grey">Loading…</div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { date } from 'quasar';
import { api } from '@/api';
import type { StatsResponse } from '@/api/types';

const loading = ref(false);
const stats = ref<StatsResponse | null>(null);
const health = ref<string | null>(null);

const cards = computed(() => {
  if (!stats.value) return [];
  const s = stats.value;
  return [
    { label: 'Users', icon: 'people', color: 'primary', value: s.users_count },
    { label: 'Admins', icon: 'admin_panel_settings', color: 'orange', value: s.admins_count },
    { label: 'Groups', icon: 'groups', color: 'secondary', value: s.groups_count },
    { label: 'Shares', icon: 'folder_shared', color: 'teal', value: s.shares_count },
    { label: 'Registry', icon: 'dns', color: 'indigo', value: s.registry_shares_count },
    { label: 'Memberships', icon: 'link', color: 'blue-grey', value: s.memberships_count },
  ];
});

async function load() {
  loading.value = true;
  try {
    const [s, h] = await Promise.all([api.stats(), api.health()]);
    stats.value = s.data;
    health.value = h.data.status;
  } finally {
    loading.value = false;
  }
}

function formatDate(value: string) {
  return date.formatDate(value, 'YYYY-MM-DD HH:mm');
}

onMounted(load);
</script>
```

- [x] **Step 2: Verify type-check**

Run: `just ui-typecheck`
Expected: exit 0.

- [x] **Step 3: Commit**

```bash
git add web-ui/src/pages/index/\(index\).vue
git commit -m "feat(ui): dashboard with stats and expiring memberships"
```

### Task 11: User membership and mount-script dialogs (shared components)

**Files:**
- Create: `web-ui/src/components/users/UserGroupsDialog.vue`
- Create: `web-ui/src/components/users/MountScriptDialog.vue`

- [x] **Step 1: Create `UserGroupsDialog.vue`**

```vue
<template>
  <q-dialog
    :model-value="modelValue"
    @update:model-value="(v: boolean) => emits('update:modelValue', v)"
  >
    <q-card style="min-width: 560px; max-width: 90vw">
      <q-card-section>
        <div class="text-subtitle1">Groups of {{ user?.username }}</div>
      </q-card-section>

      <q-card-section>
        <q-table
          :rows="memberships"
          :columns="columns"
          row-key="group_id"
          flat
          hide-bottom
          dense
          :loading="loading"
        >
          <template v-slot:body-cell-access_level="cell">
            <q-td :props="cell">
              <q-badge
                :color="cell.value === 'rw' ? 'teal' : 'blue-grey'"
                :label="String(cell.value).toUpperCase()"
              />
            </q-td>
          </template>
          <template v-slot:body-cell-expires_at="cell">
            <q-td :props="cell">{{ cell.value ? formatDate(cell.value as string) : '—' }}</q-td>
          </template>
          <template v-slot:body-cell-actions="cell">
            <q-td :props="cell" class="text-right">
              <q-btn
                flat
                dense
                round
                icon="remove_circle_outline"
                color="negative"
                title="Remove from group"
                @click="remove(cell.row)"
              />
            </q-td>
          </template>
        </q-table>
      </q-card-section>

      <q-card-section>
        <div class="text-subtitle2 q-mb-sm">Add to group</div>
        <div class="row q-col-gutter-sm items-end">
          <q-select
            class="col-4"
            v-model="form.group_id"
            :options="addableGroups"
            option-label="name"
            option-value="id"
            label="Group"
            outlined
            dense
          />
          <q-select
            class="col-3"
            v-model="form.access_level"
            :options="levels"
            label="Access"
            outlined
            dense
          />
          <q-input
            class="col-5"
            v-model="form.expires_at"
            type="datetime-local"
            label="Expires (optional)"
            outlined
            dense
            clearable
          />
          <div class="col-12 q-mt-sm">
            <q-btn
              label="Add"
              color="primary"
              :loading="adding"
              :disable="!form.group_id"
              @click="add"
            />
          </div>
        </div>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat label="Close" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { date, useQuasar } from 'quasar';
import { api } from '@/api';
import type { GroupOut, MemberOut, UserOut } from '@/api/types';

const props = defineProps<{ modelValue: boolean; user: UserOut | null }>();
const emits = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>();

type UserMembership = MemberOut & { group_name: string; group_id: string };

const $q = useQuasar();
const groups = ref<GroupOut[]>([]);
const memberships = ref<UserMembership[]>([]);
const loading = ref(false);
const adding = ref(false);
const form = ref<{ group_id: string | null; access_level: string; expires_at: string | null }>({
  group_id: null,
  access_level: 'ro',
  expires_at: null,
});
const levels = [
  { label: 'RO', value: 'ro' },
  { label: 'RW', value: 'rw' },
];
const columns = [
  { name: 'group_name', label: 'Group', field: 'group_name', align: 'left' },
  { name: 'access_level', label: 'Access', field: 'access_level', align: 'left' },
  { name: 'expires_at', label: 'Expires', field: 'expires_at', align: 'left' },
  { name: 'actions', label: '', field: '', align: 'right' },
];

const addableGroups = computed(() =>
  groups.value.filter(
    (g) => !g.is_personal && !memberships.value.some((m) => m.group_id === g.id)
  )
);

async function load() {
  if (!props.user) return;
  loading.value = true;
  try {
    groups.value = (await api.listGroups()).data;
    const rows: UserMembership[] = [];
    for (const g of groups.value) {
      const members = (await api.listMembers(g.id)).data;
      const mine = members.find((m) => m.user_id === props.user!.id);
      if (mine) rows.push({ ...mine, group_name: g.name, group_id: g.id });
    }
    memberships.value = rows;
  } finally {
    loading.value = false;
  }
}

async function add() {
  if (!props.user || !form.value.group_id) return;
  adding.value = true;
  try {
    await api.addMember(form.value.group_id, {
      user_id: props.user.id,
      access_level: form.value.access_level,
      expires_at: form.value.expires_at ? new Date(form.value.expires_at).toISOString() : null,
    });
    $q.notify({ type: 'positive', message: 'Added to group' });
    form.value.group_id = null;
    form.value.expires_at = null;
    await load();
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to add' });
  } finally {
    adding.value = false;
  }
}

async function remove(row: UserMembership) {
  try {
    await api.removeMember(row.group_id, row.user_id);
    $q.notify({ type: 'positive', message: 'Removed from group' });
    await load();
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to remove' });
  }
}

function formatDate(value: string) {
  return date.formatDate(value, 'YYYY-MM-DD HH:mm');
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) load();
  }
);
</script>
```

- [x] **Step 2: Create `MountScriptDialog.vue`**

```vue
<template>
  <q-dialog
    :model-value="modelValue"
    @update:model-value="(v: boolean) => emits('update:modelValue', v)"
  >
    <q-card style="min-width: 640px; max-width: 95vw">
      <q-card-section>
        <div class="text-subtitle1">Mount script for {{ user?.username }}</div>
      </q-card-section>

      <q-card-section v-if="!result">
        <q-input v-model="password" label="User password" type="password" outlined autofocus />
        <q-btn label="Generate" color="primary" class="q-mt-md" :loading="loading" @click="generate" />
        <div v-if="error" class="text-negative q-mt-sm">{{ error }}</div>
      </q-card-section>

      <template v-else>
        <q-card-section class="q-gutter-sm">
          <q-badge
            v-for="s in result.shares"
            :key="s.name"
            color="teal"
            :label="`${s.name} (${s.path} · ${s.access})`"
          />
        </q-card-section>
        <q-card-section>
          <div class="text-subtitle2 q-mb-sm">Windows</div>
          <q-input type="textarea" readonly :model-value="result.windows_script" rows="6" />
        </q-card-section>
        <q-card-section>
          <div class="text-subtitle2 q-mb-sm">Linux</div>
          <q-input type="textarea" readonly :model-value="result.linux_script" rows="8" />
        </q-card-section>
      </template>

      <q-card-actions align="right">
        <q-btn flat label="Close" v-close-popup @click="reset" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from '@/api';
import type { MountScriptResponse, UserOut } from '@/api/types';

const props = defineProps<{ modelValue: boolean; user: UserOut | null }>();
const emits = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>();

const $q = useQuasar();
const password = ref('');
const loading = ref(false);
const error = ref('');
const result = ref<MountScriptResponse | null>(null);

async function generate() {
  if (!props.user) return;
  loading.value = true;
  error.value = '';
  try {
    result.value = (await api.mountScript(props.user.username, password.value)).data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to generate script';
  } finally {
    loading.value = false;
  }
}

function reset() {
  result.value = null;
  password.value = '';
  error.value = '';
}
</script>
```

- [x] **Step 3: Verify type-check**

Run: `just ui-typecheck`
Expected: exit 0.

- [x] **Step 4: Commit**

```bash
git add web-ui/src/components/users
git commit -m "feat(ui): user groups and mount-script dialogs"
```

### Task 12: Users page

**Files:**
- Create: `web-ui/src/pages/index/users.vue`

- [x] **Step 1: Implement the Users page**

`web-ui/src/pages/index/users.vue`:

```vue
<template>
  <q-page class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div class="text-h5">Users</div>
      <q-btn label="Create user" icon="add" color="primary" @click="createOpen = true" />
    </div>

    <q-table :rows="users" :columns="columns" row-key="id" :loading="loading" flat bordered>
      <template v-slot:body-cell-is_admin="cell">
        <q-td :props="cell">
          <q-badge :color="cell.value ? 'orange' : 'blue-grey'" :label="cell.value ? 'admin' : 'user'" />
        </q-td>
      </template>
      <template v-slot:body-cell-created_at="cell">
        <q-td :props="cell">{{ formatDate(cell.value as string) }}</q-td>
      </template>
      <template v-slot:body-cell-actions="cell">
        <q-td :props="cell" class="text-right">
          <q-btn flat round dense icon="key" title="Set password" @click="openPassword(cell.row)" />
          <q-btn flat round dense icon="group_add" title="Groups" @click="openGroups(cell.row)" />
          <q-btn flat round dense icon="terminal" title="Mount script" @click="openMountScript(cell.row)" />
          <q-btn
            flat
            round
            dense
            icon="delete"
            color="negative"
            title="Delete"
            @click="openDelete(cell.row)"
          />
        </q-td>
      </template>
      <template v-slot:no-data>
        <span class="text-grey">No users</span>
      </template>
    </q-table>

    <q-dialog v-model="createOpen">
      <q-card style="min-width: 360px">
        <q-card-section>
          <div class="text-subtitle1">Create user</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input
            v-model="createForm.username"
            label="Username"
            hint="lowercase letters, digits, - _"
            :error="!!createError"
            :error-message="createError"
          />
          <q-input v-model="createForm.password" label="Password" type="password" />
          <q-toggle v-model="createForm.is_admin" label="Administrator" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn label="Create" color="primary" :loading="createLoading" @click="createUser" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="passwordOpen">
      <q-card style="min-width: 360px">
        <q-card-section>
          <div class="text-subtitle1">Set password for {{ selected?.username }}</div>
        </q-card-section>
        <q-card-section>
          <q-input v-model="passwordForm.new" label="New password" type="password" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn label="Save" color="primary" :loading="passwordLoading" @click="savePassword" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="deleteOpen">
      <q-card>
        <q-card-section class="text-h6">Delete {{ selected?.username }}?</q-card-section>
        <q-card-section class="text-grey">
          This removes the user and all memberships, and deletes the Samba account.
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn label="Delete" color="negative" :loading="deleteLoading" @click="deleteUser" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <UserGroupsDialog v-model="groupsOpen" :user="selected" />
    <MountScriptDialog v-model="mountOpen" :user="selected" />
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { date, useQuasar } from 'quasar';
import { api } from '@/api';
import type { UserOut } from '@/api/types';
import UserGroupsDialog from '@/components/users/UserGroupsDialog.vue';
import MountScriptDialog from '@/components/users/MountScriptDialog.vue';

const $q = useQuasar();
const users = ref<UserOut[]>([]);
const loading = ref(false);
const selected = ref<UserOut | null>(null);

const columns = [
  { name: 'username', label: 'Username', field: 'username', align: 'left' },
  { name: 'is_admin', label: 'Role', field: 'is_admin', align: 'left' },
  { name: 'created_at', label: 'Created', field: 'created_at', align: 'left' },
  { name: 'actions', label: '', field: '', align: 'right' },
];

const createOpen = ref(false);
const createForm = ref({ username: '', password: '', is_admin: false });
const createError = ref('');
const createLoading = ref(false);

const passwordOpen = ref(false);
const passwordForm = ref({ new: '' });
const passwordLoading = ref(false);

const deleteOpen = ref(false);
const deleteLoading = ref(false);

const groupsOpen = ref(false);
const mountOpen = ref(false);

async function load() {
  loading.value = true;
  try {
    users.value = (await api.listUsers()).data;
  } finally {
    loading.value = false;
  }
}

function formatDate(value: string) {
  return date.formatDate(value, 'YYYY-MM-DD HH:mm');
}

async function createUser() {
  createError.value = '';
  createLoading.value = true;
  try {
    await api.createUser(createForm.value);
    createOpen.value = false;
    $q.notify({ type: 'positive', message: 'User created' });
    await load();
  } catch (e: any) {
    createError.value = e?.response?.data?.detail ?? 'Failed to create user';
  } finally {
    createLoading.value = false;
  }
}

function openPassword(user: UserOut) {
  selected.value = user;
  passwordForm.value.new = '';
  passwordOpen.value = true;
}

async function savePassword() {
  if (!selected.value) return;
  passwordLoading.value = true;
  try {
    await api.changeUserPassword(selected.value.id, passwordForm.value.new);
    passwordOpen.value = false;
    $q.notify({ type: 'positive', message: 'Password updated' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to update password' });
  } finally {
    passwordLoading.value = false;
  }
}

function openDelete(user: UserOut) {
  selected.value = user;
  deleteOpen.value = true;
}

async function deleteUser() {
  if (!selected.value) return;
  deleteLoading.value = true;
  try {
    await api.deleteUser(selected.value.id);
    deleteOpen.value = false;
    $q.notify({ type: 'positive', message: 'User deleted' });
    await load();
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to delete user' });
  } finally {
    deleteLoading.value = false;
  }
}

function openGroups(user: UserOut) {
  selected.value = user;
  groupsOpen.value = true;
}

function openMountScript(user: UserOut) {
  selected.value = user;
  mountOpen.value = true;
}

onMounted(load);
</script>
```

- [x] **Step 2: Verify type-check**

Run: `just ui-typecheck`
Expected: exit 0.

- [x] **Step 3: Commit**

```bash
git add web-ui/src/pages/index/users.vue
git commit -m "feat(ui): users page with create, password, groups, mount-script, delete"
```

### Task 13: Groups page

**Files:**
- Create: `web-ui/src/pages/index/groups.vue`

- [x] **Step 1: Implement the Groups page**

`web-ui/src/pages/index/groups.vue`:

```vue
<template>
  <q-page class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div class="text-h5">Groups</div>
      <q-btn label="Create group" icon="add" color="primary" @click="createOpen = true" />
    </div>

    <q-table
      :rows="groups"
      :columns="columns"
      row-key="id"
      :loading="loadingGroups"
      flat
      bordered
      selection="single"
      :selected-rows="selected ? [selected.id] : []"
      @update:selected="onSelect"
    >
      <template v-slot:body-cell-is_personal="cell">
        <q-td :props="cell">
          <q-badge :color="cell.value ? 'purple' : 'blue-grey'" :label="cell.value ? 'personal' : 'group'" />
        </q-td>
      </template>
      <template v-slot:body-cell-actions="cell">
        <q-td :props="cell" class="text-right">
          <q-btn
            flat
            round
            dense
            icon="delete"
            color="negative"
            title="Delete"
            :disable="cell.row.is_personal"
            @click="confirmDelete(cell.row)"
          />
        </q-td>
      </template>
    </q-table>

    <div v-if="selected" class="q-mt-lg">
      <div class="text-h6 q-mb-sm">Group: {{ selected.name }}</div>
      <div class="row q-col-gutter-md">
        <q-card class="col-12 col-md-6">
          <q-card-section>
            <div class="text-subtitle1">Members</div>
          </q-card-section>
          <q-card-section class="q-pt-none">
            <q-table
              :rows="members"
              :columns="memberColumns"
              row-key="user_id"
              flat
              hide-bottom
              dense
              :loading="loadingMembers"
            >
              <template v-slot:body-cell-access_level="cell">
                <q-td :props="cell">
                  <q-badge
                    :color="cell.value === 'rw' ? 'teal' : 'blue-grey'"
                    :label="String(cell.value).toUpperCase()"
                  />
                </q-td>
              </template>
              <template v-slot:body-cell-expires_at="cell">
                <q-td :props="cell">{{ cell.value ? formatDate(cell.value as string) : '—' }}</q-td>
              </template>
              <template v-slot:body-cell-actions="cell">
                <q-td :props="cell" class="text-right">
                  <q-btn
                    flat
                    dense
                    round
                    icon="remove_circle_outline"
                    color="negative"
                    @click="removeMember(cell.row)"
                  />
                </q-td>
              </template>
            </q-table>
            <div class="row q-col-gutter-sm items-end q-mt-md">
              <q-select
                class="col-5"
                v-model="memberForm.user_id"
                :options="availableUsers"
                option-label="username"
                option-value="id"
                label="User"
                outlined
                dense
              />
              <q-select
                class="col-3"
                v-model="memberForm.access_level"
                :options="levels"
                label="Access"
                outlined
                dense
              />
              <q-input
                class="col-4"
                v-model="memberForm.expires_at"
                type="datetime-local"
                label="Expires (optional)"
                outlined
                dense
                clearable
              />
              <div class="col-12 q-mt-sm">
                <q-btn
                  label="Add member"
                  color="primary"
                  :loading="addingMember"
                  :disable="!memberForm.user_id"
                  @click="addMember"
                />
              </div>
            </div>
          </q-card-section>
        </q-card>

        <q-card class="col-12 col-md-6">
          <q-card-section>
            <div class="text-subtitle1">Shares</div>
          </q-card-section>
          <q-card-section class="q-pt-none">
            <q-list bordered separator>
              <q-item v-for="s in groupShares" :key="s.id">
                <q-item-section>
                  <q-item-label>{{ s.name }}</q-item-label>
                  <q-item-label caption>{{ s.path }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn flat dense round icon="link_off" color="negative" @click="unlinkShare(s.id)" />
                </q-item-section>
              </q-item>
              <q-item v-if="groupShares.length === 0" class="text-grey">No shares linked</q-item>
            </q-list>
            <div class="row q-col-gutter-sm items-end q-mt-md">
              <q-select
                class="col-8"
                v-model="shareForm.share_id"
                :options="unlinkedShares"
                option-label="name"
                option-value="id"
                label="Share"
                outlined
                dense
              />
              <div class="col-4">
                <q-btn
                  label="Link"
                  color="primary"
                  :loading="linking"
                  :disable="!shareForm.share_id"
                  @click="linkShare(shareForm.share_id)"
                />
              </div>
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <q-dialog v-model="createOpen">
      <q-card style="min-width: 340px">
        <q-card-section>
          <div class="text-subtitle1">Create group</div>
        </q-card-section>
        <q-card-section>
          <q-input v-model="createForm.name" label="Name" hint="lowercase letters, digits, - _" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn label="Create" color="primary" :loading="createLoading" @click="createGroup" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="deleteOpen">
      <q-card>
        <q-card-section class="text-h6">Delete {{ deleteTarget?.name }}?</q-card-section>
        <q-card-section class="text-grey">
          This removes the group, its members and linked shares from the registry.
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup @click="deleteOpen = false" />
          <q-btn label="Delete" color="negative" :loading="deleteLoading" @click="doDelete" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { date, useQuasar } from 'quasar';
import { api } from '@/api';
import type { GroupOut, MemberOut, ShareOut, UserOut } from '@/api/types';

const $q = useQuasar();
const groups = ref<GroupOut[]>([]);
const users = ref<UserOut[]>([]);
const shares = ref<ShareOut[]>([]);
const loadingGroups = ref(false);
const selected = ref<GroupOut | null>(null);

const members = ref<MemberOut[]>([]);
const loadingMembers = ref(false);
const groupShares = ref<ShareOut[]>([]);

const createOpen = ref(false);
const createForm = ref({ name: '' });
const createLoading = ref(false);

const deleteOpen = ref(false);
const deleteTarget = ref<GroupOut | null>(null);
const deleteLoading = ref(false);

const memberForm = ref<{ user_id: string | null; access_level: string; expires_at: string | null }>({
  user_id: null,
  access_level: 'ro',
  expires_at: null,
});
const addingMember = ref(false);

const shareForm = ref<{ share_id: string | null }>({ share_id: null });
const linking = ref(false);

const levels = [
  { label: 'RO', value: 'ro' },
  { label: 'RW', value: 'rw' },
];

const columns = [
  { name: 'name', label: 'Name', field: 'name', align: 'left' },
  { name: 'is_personal', label: 'Type', field: 'is_personal', align: 'left' },
  { name: 'actions', label: '', field: '', align: 'right' },
];

const memberColumns = [
  { name: 'username', label: 'User', field: 'username', align: 'left' },
  { name: 'access_level', label: 'Access', field: 'access_level', align: 'left' },
  { name: 'expires_at', label: 'Expires', field: 'expires_at', align: 'left' },
  { name: 'actions', label: '', field: '', align: 'right' },
];

const availableUsers = computed(() =>
  users.value.filter((u) => !members.value.some((m) => m.user_id === u.id))
);

const unlinkedShares = computed(() =>
  shares.value.filter((s) => !groupShares.value.some((gs) => gs.id === s.id))
);

async function loadGroups() {
  loadingGroups.value = true;
  try {
    groups.value = (await api.listGroups()).data;
  } finally {
    loadingGroups.value = false;
  }
}

async function loadUsers() {
  users.value = (await api.listUsers()).data;
}

async function loadShares() {
  shares.value = (await api.listShares()).data;
}

async function onSelect(rows: GroupOut[]) {
  selected.value = rows[0] ?? null;
  if (selected.value) {
    await loadGroupDetail(selected.value.id);
  }
}

async function loadGroupDetail(groupId: string) {
  loadingMembers.value = true;
  try {
    const [m, s] = await Promise.all([api.listMembers(groupId), api.listGroupShares(groupId)]);
    members.value = m.data;
    groupShares.value = s.data;
  } finally {
    loadingMembers.value = false;
  }
}

function formatDate(value: string) {
  return date.formatDate(value, 'YYYY-MM-DD HH:mm');
}

async function createGroup() {
  createLoading.value = true;
  try {
    await api.createGroup(createForm.value.name);
    createOpen.value = false;
    $q.notify({ type: 'positive', message: 'Group created' });
    await Promise.all([loadGroups(), loadUsers(), loadShares()]);
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to create group' });
  } finally {
    createLoading.value = false;
  }
}

function confirmDelete(group: GroupOut) {
  deleteTarget.value = group;
  deleteOpen.value = true;
}

async function doDelete() {
  if (!deleteTarget.value) return;
  deleteLoading.value = true;
  try {
    await api.deleteGroup(deleteTarget.value.id);
    deleteOpen.value = false;
    $q.notify({ type: 'positive', message: 'Group deleted' });
    selected.value = null;
    await loadGroups();
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to delete group' });
  } finally {
    deleteLoading.value = false;
  }
}

async function addMember() {
  if (!selected.value || !memberForm.value.user_id) return;
  addingMember.value = true;
  try {
    await api.addMember(selected.value.id, {
      user_id: memberForm.value.user_id,
      access_level: memberForm.value.access_level,
      expires_at: memberForm.value.expires_at
        ? new Date(memberForm.value.expires_at).toISOString()
        : null,
    });
    memberForm.value.user_id = null;
    memberForm.value.expires_at = null;
    $q.notify({ type: 'positive', message: 'Member added' });
    await loadGroupDetail(selected.value.id);
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to add member' });
  } finally {
    addingMember.value = false;
  }
}

async function removeMember(member: MemberOut) {
  if (!selected.value) return;
  try {
    await api.removeMember(selected.value.id, member.user_id);
    $q.notify({ type: 'positive', message: 'Member removed' });
    await loadGroupDetail(selected.value.id);
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to remove member' });
  }
}

async function linkShare(shareId: string | null) {
  if (!selected.value || !shareId) return;
  linking.value = true;
  try {
    await api.linkShare(selected.value.id, shareId);
    shareForm.value.share_id = null;
    $q.notify({ type: 'positive', message: 'Share linked' });
    await loadGroupDetail(selected.value.id);
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to link share' });
  } finally {
    linking.value = false;
  }
}

async function unlinkShare(shareId: string) {
  if (!selected.value) return;
  try {
    await api.unlinkShare(selected.value.id, shareId);
    $q.notify({ type: 'positive', message: 'Share unlinked' });
    await loadGroupDetail(selected.value.id);
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to unlink share' });
  }
}

onMounted(async () => {
  await Promise.all([loadGroups(), loadUsers(), loadShares()]);
});
</script>
```

- [x] **Step 2: Verify type-check**

Run: `just ui-typecheck`
Expected: exit 0.

- [x] **Step 3: Commit**

```bash
git add web-ui/src/pages/index/groups.vue
git commit -m "feat(ui): groups page with members and linked shares"
```

### Task 14: Shares page

**Files:**
- Create: `web-ui/src/pages/index/shares.vue`

- [x] **Step 1: Implement the Shares page**

`web-ui/src/pages/index/shares.vue`:

```vue
<template>
  <q-page class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div class="text-h5">Shares</div>
      <q-btn label="Create share" icon="add" color="primary" @click="createOpen = true" />
    </div>

    <q-table :rows="shares" :columns="columns" row-key="id" :loading="loading" flat bordered>
      <template v-slot:body-cell-actions="cell">
        <q-td :props="cell" class="text-right">
          <q-btn
            flat
            round
            dense
            icon="delete"
            color="negative"
            title="Delete"
            @click="confirmDelete(cell.row)"
          />
        </q-td>
      </template>
      <template v-slot:no-data>
        <span class="text-grey">No shares</span>
      </template>
    </q-table>

    <q-dialog v-model="createOpen">
      <q-card style="min-width: 400px">
        <q-card-section>
          <div class="text-subtitle1">Create share</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="form.name" label="Name" hint="lowercase letters, digits, - _" />
          <div class="text-caption text-grey">
            Available paths on the server:
            <span v-if="dirs.length === 0" class="text-grey">(none detected)</span>
          </div>
          <q-chip
            v-for="d in dirs"
            :key="d"
            dense
            size="sm"
            :label="d"
            clickable
            @click="form.name = d"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn label="Create" color="primary" :loading="creating" :disable="!form.name" @click="createShare" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="deleteOpen">
      <q-card>
        <q-card-section class="text-h6">Delete {{ deleteTarget?.name }}?</q-card-section>
        <q-card-section class="text-grey">
          The share directory is kept on disk; it is removed from the Samba registry.
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup @click="deleteOpen = false" />
          <q-btn label="Delete" color="negative" :loading="deleting" @click="doDelete" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from '@/api';
import type { ShareOut } from '@/api/types';

const $q = useQuasar();
const shares = ref<ShareOut[]>([]);
const dirs = ref<string[]>([]);
const loading = ref(false);

const createOpen = ref(false);
const form = ref({ name: '' });
const creating = ref(false);

const deleteOpen = ref(false);
const deleteTarget = ref<ShareOut | null>(null);
const deleting = ref(false);

const columns = [
  { name: 'name', label: 'Name', field: 'name', align: 'left' },
  { name: 'path', label: 'Path', field: 'path', align: 'left' },
  { name: 'actions', label: '', field: '', align: 'right' },
];

async function load() {
  loading.value = true;
  try {
    shares.value = (await api.listShares()).data;
  } finally {
    loading.value = false;
  }
}

async function loadDirs() {
  dirs.value = (await api.availableDirs()).data;
}

async function createShare() {
  creating.value = true;
  try {
    await api.createShare(form.value.name);
    createOpen.value = false;
    form.value.name = '';
    $q.notify({ type: 'positive', message: 'Share created' });
    await load();
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to create share' });
  } finally {
    creating.value = false;
  }
}

function confirmDelete(share: ShareOut) {
  deleteTarget.value = share;
  deleteOpen.value = true;
}

async function doDelete() {
  if (!deleteTarget.value) return;
  deleting.value = true;
  try {
    await api.deleteShare(deleteTarget.value.id);
    deleteOpen.value = false;
    $q.notify({ type: 'positive', message: 'Share deleted' });
    await load();
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to delete share' });
  } finally {
    deleting.value = false;
  }
}

onMounted(async () => {
  await Promise.all([load(), loadDirs()]);
});
</script>
```

- [x] **Step 2: Verify type-check**

Run: `just ui-typecheck`
Expected: exit 0.

- [x] **Step 3: Commit**

```bash
git add web-ui/src/pages/index/shares.vue
git commit -m "feat(ui): shares page"
```

### Task 15: System page

**Files:**
- Create: `web-ui/src/pages/index/system.vue`

- [x] **Step 1: Implement the System page**

`web-ui/src/pages/index/system.vue`:

```vue
<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">System</div>

    <div class="row q-col-gutter-md">
      <q-card class="col-12 col-md-4">
        <q-card-section>
          <div class="text-subtitle1">API health</div>
        </q-card-section>
        <q-card-section class="row items-center q-col-gutter-md">
          <q-badge :color="health === 'ok' ? 'positive' : 'negative'">
            {{ health ?? 'unknown' }}
          </q-badge>
          <q-btn flat round dense icon="refresh" @click="loadHealth" :loading="healthLoading" />
        </q-card-section>
      </q-card>

      <q-card class="col-12 col-md-4">
        <q-card-section>
          <div class="text-subtitle1">Registry sync</div>
        </q-card-section>
        <q-card-section class="q-pt-none">
          <q-btn label="Sync now" icon="sync" color="primary" :loading="syncing" @click="runSync" />
          <pre v-if="syncReport" class="q-mt-sm">{{ JSON.stringify(syncReport, null, 2) }}</pre>
        </q-card-section>
      </q-card>

      <q-card class="col-12 col-md-4">
        <q-card-section>
          <div class="text-subtitle1">Membership sweep</div>
        </q-card-section>
        <q-card-section class="q-pt-none">
          <q-btn
            label="Sweep now"
            icon="cleaning_services"
            color="warning"
            :loading="sweeping"
            @click="runSweep"
          />
          <div v-if="sweepResult" class="q-mt-sm text-grey">
            Processed: {{ sweepResult.processed }}
          </div>
          <pre v-if="sweepResult?.sync" class="q-mt-sm">
            {{ JSON.stringify(sweepResult.sync, null, 2) }}
          </pre>
        </q-card-section>
      </q-card>
    </div>

    <q-card class="q-mt-md">
      <q-card-section class="row items-center justify-between">
        <div class="text-subtitle1">Samba registry</div>
        <q-btn flat round icon="refresh" @click="loadRegistry" :loading="registryLoading" />
      </q-card-section>
      <q-card-section class="q-pt-none">
        <pre>{{ JSON.stringify(registry, null, 2) }}</pre>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from '@/api';
import type { RegistryState, SyncReport } from '@/api/types';

const health = ref<string | null>(null);
const healthLoading = ref(false);
const syncing = ref(false);
const syncReport = ref<SyncReport | null>(null);
const sweeping = ref(false);
const sweepResult = ref<{ processed: number; sync: SyncReport | null } | null>(null);
const registry = ref<RegistryState>({});
const registryLoading = ref(false);

async function loadHealth() {
  healthLoading.value = true;
  try {
    health.value = (await api.health()).data.status;
  } finally {
    healthLoading.value = false;
  }
}

async function runSync() {
  syncing.value = true;
  try {
    syncReport.value = (await api.sync()).data;
  } finally {
    syncing.value = false;
  }
}

async function runSweep() {
  sweeping.value = true;
  try {
    sweepResult.value = (await api.sweep()).data;
  } finally {
    sweeping.value = false;
  }
}

async function loadRegistry() {
  registryLoading.value = true;
  try {
    registry.value = (await api.registry()).data;
  } finally {
    registryLoading.value = false;
  }
}

onMounted(async () => {
  await Promise.all([loadHealth(), loadRegistry()]);
});
</script>
```

- [x] **Step 2: Verify type-check**

Run: `just ui-typecheck`
Expected: exit 0.

- [x] **Step 3: Commit**

```bash
git add web-ui/src/pages/index/system.vue
git commit -m "feat(ui): system page with sync, sweep, registry"
```

### Task 16: Profile page

**Files:**
- Create: `web-ui/src/pages/index/profile.vue`

- [x] **Step 1: Implement the Profile page**

`web-ui/src/pages/index/profile.vue`:

```vue
<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Profile</div>

    <q-card class="q-mb-md">
      <q-card-section>
        <div class="row items-center q-col-gutter-md">
          <q-avatar color="primary" text-color="white" size="56px" icon="person" />
          <div>
            <div class="text-h6">{{ me?.username }}</div>
            <div class="text-caption text-grey">
              Administrator · created {{ me ? formatDate(me.created_at) : '…' }}
            </div>
          </div>
        </div>
      </q-card-section>
    </q-card>

    <q-card class="q-mb-md">
      <q-card-section>
        <div class="text-subtitle1">Appearance</div>
      </q-card-section>
      <q-card-section class="q-pt-none">
        <q-toggle :model-value="$q.dark.isActive" label="Dark theme" @update:model-value="(v: boolean) => toggleDark(v)" />
      </q-card-section>
    </q-card>

    <q-card>
      <q-card-section>
        <div class="text-subtitle1">Change password</div>
      </q-card-section>
      <q-card-section class="q-pt-none">
        <q-form @submit="changePassword">
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-4">
              <q-input v-model="pwd.new" label="New password" type="password" outlined />
            </div>
            <div class="col-12 col-md-4">
              <q-input
                v-model="pwd.confirm"
                label="Confirm"
                type="password"
                outlined
                :error="!!pwd.error"
                :error-message="pwd.error"
              />
            </div>
          </div>
          <q-btn label="Save" type="submit" color="primary" class="q-mt-md" :loading="saving" />
        </q-form>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { date, useQuasar } from 'quasar';
import { api } from '@/api';
import type { UserOut } from '@/api/types';

const $q = useQuasar();
const me = ref<UserOut | null>(null);
const saving = ref(false);
const pwd = ref({ new: '', confirm: '', error: '' });

async function load() {
  me.value = (await api.me()).data;
}

function formatDate(value: string) {
  return date.formatDate(value, 'YYYY-MM-DD HH:mm');
}

function toggleDark(value: boolean) {
  $q.dark.set(value);
  localStorage.setItem('nas.dark', value ? '1' : '0');
}

async function changePassword() {
  pwd.value.error = '';
  if (pwd.value.new !== pwd.value.confirm) {
    pwd.value.error = 'Passwords do not match';
    return;
  }
  if (!me.value) return;
  saving.value = true;
  try {
    await api.changeUserPassword(me.value.id, pwd.value.new);
    $q.notify({ type: 'positive', message: 'Password updated' });
    pwd.value.new = '';
    pwd.value.confirm = '';
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to update password' });
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>
```

- [x] **Step 2: Verify type-check**

Run: `just ui-typecheck`
Expected: exit 0.

- [x] **Step 3: Commit**

```bash
git add web-ui/src/pages/index/profile.vue
git commit -m "feat(ui): profile page"
```

---

## Phase D — Full verification

### Task 17: End-to-end verification

**Files:**
- (no source changes unless a bug is found)

- [x] **Step 1: Backend suite**

Run: `just test`
Expected: `37 passed`.

- [x] **Step 2: Frontend type-check + build**

Run: `just ui-typecheck`
Expected: exit 0.
Run: `just ui-build`
Expected: `web-ui/dist/spa` produced without errors.

- [x] **Step 3: Rebuild the full image and boot**

Run: `just build`
Run: `just up`
Then:
```bash
curl -s http://localhost:8000/api/v1/health
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/
```
Expected: `{"status":"ok"}` and `200` (index.html served from the SPA).

- [x] **Step 4: Manual smoke (browser or curl+screenshots)**

- `http://localhost:8000/` → redirected to `#/login` (no token);
- Sign in with `admin/admin123` → redirect to Dashboard;
- Dark theme on by default; sidebar shows Dashboard/Users/Shares/Groups/System;
- User menu (top-right) shows Profile and Exit;
- Users: create `smoke1` (admin role off), set password, open Groups dialog, add to a group,
  generate a mount script, delete;
- Groups: create `smoke_grp`, add `smoke1` (RW, expiry +3 days), link the existing share;
- Shares: create `smoke_share`, delete it;
- System: Sync now / Sweep now / registry view;
- Profile: change own password, toggle dark theme off and back, reload (preference kept);
- Exit → back to `/login`; open `/` while logged out → redirected to `/login`.

- [x] **Step 5: Dashboard data check**

On Dashboard verify the stat cards and the «Expiring memberships» row for `smoke1` (expiry +3 days).

- [x] **Step 6: Cleanup & final commit**

Delete the smoke entities through the UI (or via `curl`), run `just test` once more, and commit any
fixes:

```bash
git add -A
git commit -m "verify: web-ui end-to-end"
```

---

## Self-review notes (checked at authoring time)

- Spec coverage: dark theme → Task 5; remove default layout → Task 8; login + redirect
  unauthenticated → Tasks 7, 9; new layout with left sidebar/main right + boxed → Task 8;
  user menu Profile/Exit → Task 8; Users/Shares/Groups pages → Tasks 12–14; Dashboard → Task 10;
  System → Task 15; Profile → Task 16; mount-script dialog in Users → Task 11 (component) + Task 12;
  /auth/me + /stats backend → Tasks 1–2; static serving → Tasks 3–4; English UI → all pages.
- No placeholders: every file lists full code; every command has expected output.
- Type consistency: API object method names used in pages (`api.listUsers`, `api.addMember`,
  `api.mountScript`, `api.sweep`, `api.registry`, …) match `src/api/index.ts` exactly; DTO fields
  match backend schemas (verified against `app/modules/*/schemas.py`).