# План реализации NAS Manager

Ссылки: требования `todo.txt`, дизайн `docs/superpowers/specs/2026-09-11-nas-manager-design.md`.

## Контракты (общие для всех фаз)

### Настройки (`core/settings.py`, pydantic-settings, `.env`)
`SHARE_HOST_PATH`, `SHARE_MOUNT_PATH` (корень шар), `DB_PATH`, `JWT_SECRET`, `JWT_TTL_MINUTES=60`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `EXPIRY_CHECK_INTERVAL_SECONDS=60`, `SAMBA_SERVICE_USER=service-user`.

### API (`/api/v1`)
- `POST /auth/login {username,password}` → `{access_token, token_type:"bearer"}`; только is_admin.
- Users: `GET /users`, `POST /users {username,password,is_admin}`, `GET /users/{id}`, `DELETE /users/{id}`, `POST /users/{id}/password {new_password}` (smbpasswd -x/-a трюк), `POST /users/{username}/mount-script {password}`.
- Groups: `GET/POST /groups {name}`, `DELETE /groups/{id}`; members: `GET /groups/{id}/members`, `POST /groups/{id}/members {user_id,access_level,expires_at?}`, `DELETE /groups/{id}/members/{user_id}` (личная — 409); shares группы: `GET/POST /groups/{id}/shares {share_id}`, `DELETE /groups/{id}/shares/{share_id}`.
- Shares: `GET /shares`, `GET /shares/available` (скан корня), `POST /shares {name,create_dir=true}`, `DELETE /shares/{id}`.
- Sync: `POST /sync`; отладка: `GET /registry/shares`.

### Модули samba (`modules/samba/`)
- `os_manager.py`: `create_user`, `delete_user`, `scan_share_dirs() -> list[str]` (относительные имена), `ensure_dir(name)`.
- `registry_manager.py`: обёртки `net conf` (`list_shares`, `show_share`, `add_share`, `del_share`, `set_parm`, `get_parm`) + `smbpasswd_add/delete`. Все команды — subprocess.run(capture, check=False), бросают `SambaCommandError(stderr)` при ненулевом коде.
- `sync_engine.py`: `compute_target(session) -> dict[share_name] = {path, valid:[], write:[], read:[]}`; `sync(session) -> SyncReport{added,removed,updated,params_set}` — diff с текущим реестром, идемпотентно.

### Ошибки (`core/exceptions.py`)
`AppError(code,status,detail)` + подклассы (NotFound 404, Conflict 409, Auth 401, Forbidden 403, SambaCommand 502). Handler → `{"error","detail"}`.

## Фазы

- **P1 (инфра+прототип)**: git init; `.gitignore`, `.env(.example)`; Dockerfile/entrypoint/smb.conf-template/compose; justfile (up/down, client-up/down/setup/exec, тест-команды); pyproject; каркас src (settings/database/models/migrations/main). Прогон `net conf` вручную в контейнере → фиксация поведения в entrypoint.
- **P2**: auth (JWT+seed), users CRUD с реальным useradd/smbpasswd + личная группа, unit-тесты (моки subprocess).
- **P3**: groups/shares/links CRUD + RegistrySyncEngine diff + sync endpoint; unit-тесты diff.
- **P4**: expirations+APScheduler sweep, mount-script service, интеграционные скрипты `tests/integration/`.

## Проверка готовности

`just up` → логин по API → создать юзера/группу/шару/связь → из client-контейнера: smbclient список, mount cifs RW пишет файл, RO не пишет; просроченный членство исчезает; удалённая шара пропадает из реестра.
