# NAS Manager

Manage Samba shares through a REST API: users → groups → shares, synchronized with
the Samba registry (`net conf`), with auto-expiry of temporary access.

Everything runs in a single Docker container (`nas-app`): Samba (`smbd`) + a FastAPI app.
Nothing needs to be installed on the host — only Docker.

## Features

- **Users** — create/delete, change password, admin rights. Actually creates an OS user
  and a Samba account (`useradd` + `smbpasswd`).
- **Groups** — every user gets a personal group (RW, cannot be deleted).
- **Shares** — registered in the Samba registry and exported from a directory inside
  the share root (the directory must already exist on the server).
- **Access** — group members get the group's shares. Permissions: `rw` / `ro`.
  If a user is in several groups, rights combine (RW wins).
- **Temporary access** — a member can have an `expires_at`; a background scheduler
  (APScheduler) revokes expired access and re-syncs Samba.
- **Sync engine** — compares the desired state (database) with the Samba registry and
  applies the diff (`valid users` / `write list` / `read list` change on the fly).
- **Mount script** — an endpoint returns ready-to-use mount commands
  (Windows `net use` / Linux `mount -t cifs`) for a specific user.

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

**Запуск из исходников (без сборки бинаря):**
```bash
just cli-run
```

**Тесты CLI:**
```bash
just cli-test
```

## Running

Requires Docker (Linux). Samba ports `445/139` are not published to the host — the
container lives in its own docker network and clients connect to the hostname `nas`.

### 1. Configuration

Copy the example and edit if needed:

```bash
cp .env.example .env
```

Variables:

| Variable | Default | Description |
|---|---|---|
| `SHARE_HOST_PATH` | `./share` | host path where share directories live |
| `SHARE_MOUNT_PATH` | `/mnt/share` | share root inside the container |
| `DB_PATH` | `/data/app.db` | SQLite file inside the container (volume `./data`) |
| `SAMBA_SERVICE_USER` | `service-user` | system user that serves the shares |
| `WORKGROUP` | `WORKGROUP` | Samba workgroup |
| `JWT_SECRET` | `change-me-in-dev` | **must be changed** to a secret |
| `JWT_TTL_MINUTES` | `60` | token lifetime |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / `admin123` | first admin (created on first start) |
| `EXPIRY_CHECK_INTERVAL_SECONDS` | `60` | how often expired temporary access is checked |

### 2. Start

```bash
just up          # docker compose build + up -d
```

Or without `just`:

```bash
docker compose -f deploy/compose.yml --project-directory . up -d --build
```

After startup the API is available at `http://localhost:8000`, interactive docs at
`http://localhost:8000/docs`. Health check: `http://localhost:8000/api/v1/health`.

> Shares served over Samba are reached by the hostname `nas` inside the docker network
> (e.g. `//nas/photos`). Samba is not reachable outside that network.

### Web UI (web-ui)

- Admin panel: Vue 3 + Quasar 2 in `web-ui/`.
- Dev: `just ui-dev` — dev server, `/api` is proxied to `http://localhost:8000` (no CORS needed).
- Type-check: `just ui-typecheck`. Build: `just ui-build` (output in `web-ui/dist/spa`).
- Prod: multi-stage build — the UI is built and served by FastAPI at `/`
  (port 8000). If `ui-dist` is absent from the image, the UI is not mounted.
- Login: `http://localhost:8000` → Sign in (admin/admin123). `/docs` — Swagger as before.

## External port and Samba access

`docker compose` publishes only the **HTTP port 8000** (API and `/docs`) to the host.
Samba ports **445** (SMB) and **139** (NetBIOS) are not forwarded out of the container:
they are usually already taken by the host `smbd`, and forwarding would create a conflict.

So shares are mounted from a client machine as follows:

- **client on the same docker network**: by the hostname `nas` (e.g. `//nas/photos`);
  the container name resolves via docker's DNS in the `nas` network;
- **Windows host and other machines**: cannot reach the container directly until Samba
  is exposed. Options:
  - publish the ports on the host (`445/139`) and use the Docker host's address —
    the host's Samba must be stopped/reconfigured to free those ports;
  - mount the shares on the NAS host itself (`mount -t cifs //nas/...` in its
    docker network) and re-share them with the host's own Samba/NFS;
  - set up a separate externally visible service (reverse-proxying 445 is non-standard
    for SMB and not recommended).

For development the "client on the docker network" path is handy
(`just client-up`, `just integration`).

## API

All endpoints except `/auth/login`, `/auth/token` and `/health` require an
`Authorization: Bearer <token>` header. Tokens are issued to admins.

Swagger UI (`http://localhost:8000/docs`) has an **Authorize** button: enter the
admin's **username and password**, and Swagger will request a token itself via
`POST /api/v1/auth/token` and attach it to every request.

To log in programmatically, either works (both return the same JWT):

```bash
# JSON (request body)
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'

# form (same as the Authorize button)
curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -d 'username=admin&password=admin123'
```

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | login (JSON), returns a JWT |
| POST | `/api/v1/auth/token` | login (form, for the Authorize button), returns a JWT |

### Users
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/users` | list users |
| POST | `/api/v1/users` | create a user (`username`, `password`, `is_admin`) |
| GET | `/api/v1/users/{user_id}` | user details |
| POST | `/api/v1/users/{user_id}/password` | change password |
| DELETE | `/api/v1/users/{user_id}` | delete a user (cascade from groups/shares) |
| GET | `/api/v1/users/{username}/mount-script` | mount scripts for the user's shares |

### Groups
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/groups` | list groups |
| POST | `/api/v1/groups` | create a group |
| DELETE | `/api/v1/groups/{group_id}` | delete a group (personal groups cannot be deleted) |
| GET | `/api/v1/groups/{group_id}/members` | group members (with `expires_at`) |
| POST | `/api/v1/groups/{group_id}/members` | add a member: `user_id`, `access_level` (`rw`/`ro`), optional `expires_at` |
| PATCH | `/api/v1/groups/{group_id}/members/{user_id}` | edit a member's `access_level` / `expires_at` |
| DELETE | `/api/v1/groups/{group_id}/members/{user_id}` | remove a member |
| GET | `/api/v1/groups/{group_id}/shares` | group shares |
| POST | `/api/v1/groups/{group_id}/shares` | attach a share: `share_id` |
| DELETE | `/api/v1/groups/{group_id}/shares/{share_id}` | detach a share |

### Shares
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/shares` | list shares |
| POST | `/api/v1/shares` | register a share (path must already exist in the share root) |
| PATCH | `/api/v1/shares/{share_id}` | edit a share (name/path/comment) |
| DELETE | `/api/v1/shares/{share_id}` | delete a share (files are not touched) |
| GET | `/api/v1/shares/available` | full paths in the share root that are not yet registered |

### Utilities
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/sync` | force sync of the Samba registry with the database |
| POST | `/api/v1/expirations/sweep` | immediately revoke expired temporary access |
| GET | `/api/v1/registry/shares` | actual share state in the Samba registry |
| GET | `/api/v1/stats` | counts and expiring memberships |

## Example workflow

```bash
BASE=http://localhost:8000/api/v1
TOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | jq -r .access_token)
AUTH="Authorization: Bearer $TOKEN"

# create the share directory, then users
mkdir -p share/photos
alice=$(curl -s -X POST $BASE/users -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"alicepw"}' | jq -r .id)
bob=$(curl -s -X POST $BASE/users -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"username":"bob","password":"bobpw"}' | jq -r .id)

# group and share
team=$(curl -s -X POST $BASE/groups -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"team"}' | jq -r .id)
photos=$(curl -s -X POST $BASE/shares -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"photos","path":"/mnt/share/photos"}' | jq -r .id)

# bindings and permissions
curl -s -X POST $BASE/groups/$team/shares -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"share_id\":\"$photos\"}" >/dev/null
curl -s -X POST $BASE/groups/$team/members -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$alice\",\"access_level\":\"rw\"}" >/dev/null
curl -s -X POST $BASE/groups/$team/members -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$bob\",\"access_level\":\"ro\"}" >/dev/null
```

Permissions are applied to Samba automatically after every change; inspect the result
with: `docker exec nas-app net conf showshare photos`.

## Mounting a share on a client

Samba listens only in the docker network, hostname `nas`. Windows:

```text
net use Z: \\nas\photos /user:alice alicepw
```

Linux:

```bash
mount -t cifs //nas/photos /mnt/photos -o username=alice,password=alicepw
```

Ready-to-use commands per user are returned by the mount-script endpoint:

```bash
curl -s -X GET $BASE/users/alice/mount-script -H "$AUTH"
```

## Tests

Unit tests (mock OS/Samba calls, run in a one-off container — own compose, no shared
network):

```bash
just test
```

Integration tests (require a running `nas-app` and a client container):

```bash
just client-up pc1      # create a client
just client-setup pc1   # install smbclient/cifs-utils
just integration pc1    # full E2E: rw/ro rights, access expiry, mount-script
```

The integration creates temporary objects with a unique suffix and cleans up after
itself (including via `trap` on failure).

## Common commands (`just`)

| Command | What it does |
|---|---|
| `just up` | build and start |
| `just down` | stop |
| `just build` | rebuild the image |
| `just restart` | restart the container (code is picked up via bind-mount) |
| `just logs` | application logs |
| `just test` | unit tests |
| `just integration pc1` | integration tests |
| `just smb-list pc1 alice alicepw` | list shares as seen by a user |
| `just mount-share pc1 photos alice alicepw /mnt/photos` | mount a share inside the client |
| `just smoke-registry` | list shares in the Samba registry |

## Structure

```
app/
  api/v1/          API routes
  core/            settings, database, scheduler
  db/              SQLite models
  modules/
    auth/          JWT authorization
    users/         users + mount script
    groups/        groups, members, share links, expired-access sweep
    shares/        shares
    samba/         net conf registry, sync engine, OS integration
deploy/            Dockerfile, compose files, entrypoint, smb.conf
web-ui/            admin panel (Vue 3 + Quasar)
tests/             unit and integration tests
docs/              spec and plan
```