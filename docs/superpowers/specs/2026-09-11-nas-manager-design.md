# NAS Manager — дизайн (spec)

Источник требований: `todo.txt`. Утверждён с уточнениями ниже.

## 1. Архитектура и окружение

- Один привилегированный контейнер `app`: Ubuntu 24.04 + Samba + Python 3.12 (FastAPI). Entrypoint пишет `/etc/samba/smb.conf` (`include = registry`), создаёт сервисного пользователя, инициализирует реестр, запускает `smbd -D`, затем uvicorn.
- Приложение работает от root: нужны `useradd/userdel`, `smbpasswd`, `net conf`.
- Второй тип контейнеров — клиенты (`ss-client-<name>`), ubuntu:24.04, privileged, в docker-сети compose (`nas`), для проверок CIFS/smbclient.
- `.env`: `SHARE_HOST_PATH` (источник на хосте) и `SHARE_MOUNT_PATH` (корень внутри контейнера). Bind-mount `${SHARE_HOST_PATH}:${SHARE_MOUNT_PATH}`. В БД хранится **относительный** путь шары от корня (`photos`, без ведущего `/`).
- Настройки приложения — pydantic-settings, читает `.env`.

## 2. Модель данных (SQLite + Alembic)

Все id — UUID (TEXT). Пути шар в БД относительные.

- `users(id, username UNIQUE, password_hash, created_at, is_admin)`
- `shares(id, name UNIQUE, path UNIQUE)` — path относительный; при создании директории нет — создаётся под корнем и принадлежит service-user.
- `groups(id, name UNIQUE, is_personal)`
- `group_shares(group_id, share_id)` — составной PK.
- `user_groups(user_id, group_id, access_level ro|rw)` — составной PK. Личная группа: ровно 1 участник, удалить участника нельзя.
- `user_group_expirations(id, user_id, group_id, expires_at, is_active)` — временное членство; при просрочке запись деактивируется и членство удаляется из `user_groups`.

Эффективный доступ юзера к шаре = максимум по всем активным группам, связанным с шарой (RW > RO).

## 3. Синхронизация реестра (`RegistrySyncEngine`)

1. Целевое состояние из БД: для каждой шары `valid users` / `write list` / `read list`.
2. Текущее — `net conf listshares` + `net conf showshare <name>`.
3. Diff: удалённые → `delshare`; новые → `addshare ... writeable=no guest_ok=no`; далее `setparm` только изменившихся (`force user service-user`, `browseable yes`, списки доступа). Рестарт smbd запрещён.

Триггеры sync: после любой мутации (юзеры/группы/шары/связи), вручную `POST /api/v1/sync`, после sweep просрочек.

## 4. Auth

`POST /api/v1/auth/login` — только `is_admin=true`, bcrypt-проверка, выдаёт JWT (HS256, TTL из env). Seed первого админа при старте из `ADMIN_USERNAME/ADMIN_PASSWORD`. Пароль при создании юзера прокидывается в `smbpasswd`; в БД только bcrypt-хеш.

## 5. Временные членства и scheduler

APScheduler (AsyncIOScheduler в lifespan, интервал `EXPIRY_CHECK_INTERVAL_SECONDS`, по умолчанию 60): активные просроченные expirations → `is_active=false` + удаление строки из `user_groups` + один sync на проход.

## 6. Mount-script

`POST /api/v1/users/{username}/mount-script` (тело `{password}` — сверка с bcrypt) → список шар `[{"name","path":"\\\\nas\\<name>","access"}]` + готовые скрипты Windows (`net use`) и Linux (`mount -t cifs`).

## 7. Удаления (каскад, файлы не трогаем)

- DELETE user: `userdel`, `smbpasswd -x`, удаление личной группы и её связей, sync.
- DELETE group: снятие всех связей, sync. Личную группу удалить нельзя (409).
- DELETE share: удаление из БД и реестра (`net conf delshare`), sync.

## 8. Ошибки

Кастомные исключения модулей → центральный handler в JSON `{"error": CODE, "detail": msg}` с HTTP-кодом.

## 9. Тесты

Unit (pytest): бизнес-логика, diff-движок, конфликты RO/RW — subprocess замокан. Интеграция (`tests/integration/`): скрипты поднимают app+client, через API создают юзеров/группы/шары; из client проверяют: RO не пишет, RW пишет, просроченный доступ исчезает, удалённая шара пропадает.

## 10. Отклонения от структуры ТЗ (разд. 9)

- Код в корневом пакете `app/` (не `src/app`): проект не-packaged (`[tool.uv] package = false`), всё запускается через `uv run`.
- Всё приложение асинхронное: SQLAlchemy async + aiosqlite, `asyncio.create_subprocess_exec` для samba/OS-команд, APScheduler AsyncIOScheduler. bcrypt — в threadpool.
- Модели БД централизованы в `app/db/models.py`; `AccessLevel(enum.StrEnum)`.
- Порты 445/139 на хост не маппятся (хостовый smbd занят); клиенты подключаются по docker-сети к hostname `nas`. Публикуется только 8000.
- `net conf init` в сборке Ubuntu не существует — registry.tdb создаётся автоматически первой же командой `net conf`; рестарт smbd для применения реестра не требуется (проверено прототипом). Для записи на шаре обязателен `force user = service-user`.
