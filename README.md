# NAS Manager

Управление Samba-шарами через REST API: пользователи → группы → шары, синхронизация
с реестром Samba (`net conf`), автопродление/снятие временных доступов.

Всё работает в один Docker-контейнер (`nas-app`): Samba (`smbd`) + FastAPI-приложение.
На хосте ничего устанавливать не нужно — только Docker.

## Возможности

- **Пользователи** — создание/удаление, смена пароля, права администратора.
  Реально создаёт OS-пользователя и запись в Samba (`useradd` + `smbpasswd`).
- **Группы** — у каждого пользователя есть личная группа (RW, удалить нельзя).
- **Шары** — создаются каталоги в корне шар и добавляются в реестр Samba.
- **Доступы** — член группы → шары группы. Права: `rw` / `ro`.
  Если пользователь в нескольких группах — права складываются (RW приоритетнее).
- **Временный доступ** — у члена группы можно задать `expires_at`; фоновый
  планировщик (APScheduler) снимает доступ после истечения и синхронизирует Samba.
- **Синхронизация** — движок сравнивает желаемое состояние (БД) с реестром Samba
  и применяет diff (`valid users` / `write list` / `read list` меняются на лету).
- **Mount-script** — эндпоинт выдаёт готовые команды подключения шар
  (Windows `net use` / Linux `mount -t cifs`) для конкретного пользователя.

## Запуск

Требуется Docker (Linux). Порт `445/139` на хост не пробрасывается —
контейнер живёт в своей docker-сети, клиенты подключаются к имени `nas`.

### 1. Конфигурация

Скопируйте пример и при необходимости отредактируйте:

```bash
cp .env.example .env
```

Переменные:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `SHARE_HOST_PATH` | `./share` | путь на хосте, куда ложатся каталоги шар |
| `SHARE_MOUNT_PATH` | `/mnt/share` | корень шар внутри контейнера |
| `DB_PATH` | `/data/app.db` | файл SQLite внутри контейнера (volume `./data`) |
| `SAMBA_SERVICE_USER` | `service-user` | системный пользователь, от имени которого шары отдаются |
| `WORKGROUP` | `WORKGROUP` | рабочая группа Samba |
| `JWT_SECRET` | `change-me-in-dev` | **обязательно смените** на секрет |
| `JWT_TTL_MINUTES` | `60` | время жизни токена |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / `admin123` | первый администратор (создаётся при первом запуске) |
| `EXPIRY_CHECK_INTERVAL_SECONDS` | `60` | как часто проверяются истёкшие временные доступы |

### 2. Запуск

```bash
just up          # docker compose build + up -d
```

Или без `just`:

```bash
docker compose -f deploy/compose.yml --project-directory . up -d --build
```

После старта API доступен на `http://localhost:8000`, интерактивная документация —
`http://localhost:8000/docs`. Служебная проверка: `http://localhost:8000/api/v1/health`.

> Шары, звучащие через Samba, подключаются к имени `nas` в docker-сети
> (например `//nas/photos`). Снаружи этой сети Samba не слушается.

### Веб-интерфейс (web-ui)

- Админка: Vue 3 + Quasar 2 в `web-ui/` (английский язык).
- Dev: `just ui-dev` — dev-сервер, `/api` уходит на `http://localhost:8000` (CORS не нужен).
- Type-check: `just ui-typecheck`. Сборка: `just ui-build` (в `web-ui/dist/spa`).
- Prod: образ собирается многоступенчато — UI собирается и раздаётся FastAPI по `/`
  (порт 8000). Если `ui-dist` в образе отсутствует, UI не монтируется.
- Логин: `http://localhost:8000` → Sign in (admin/admin123). `/docs` — Swagger как раньше.

## Порт и доступ к Samba извне

`docker compose` публикует на хост **только HTTP-порт 8000** (API и `/docs`).
Порты Samba **445** (SMB) и **139** (NetBIOS) в контейнере на хост не пробрасываются:
обычно они уже заняты хостовым `smbd`, а проброс создал бы конфликт.

Поэтому из клиентской машины шары подключаются так:

- **клиент в той же docker-сети**: по имени `nas` (пример: `//nas/photos`);
  для этого в docker-сети `nas` работает `dns`-резолвинг имени контейнера;
- **Windows-хост и другие машины**: напрямую к контейнеру не попадут, пока Samba
  не будет объявлена наружу. Варианты:
  - пробросить порты на хост (`445/139`) и пользоваться сетевым адресом Docker-хоста —
    потребуется остановить/перенастроить хостовый Samba, чтобы освободить порты;
  - примонтировать шары на самом NAS-хосте (`mount -t cifs //nas/...` в его
    docker-сети) и расшарить их уже обычным Samba/NFS от имени хоста;
  - настроить отдельный снаружи видимый сервис (обратный прокси на 445 — нестандартно
    для SMB и не рекомендуется).

Для разработки удобен путь «клиент в docker-сети» (`just client-up`, `just integration`).

## API

Все эндпоинты, кроме `/auth/login`, `/auth/token` и `/health`, требуют заголовок
`Authorization: Bearer <token>`. Токен получают администраторы.

В Swagger UI (`http://localhost:8000/docs`) доступна кнопка **Authorize**:
в ней вводятся **имя пользователя и пароль** администратора, Swagger сам запрашивает
токен через `POST /api/v1/auth/token` и подставляет его во все запросы.

Программно войти можно одним из двух способов (оба выдают одинаковый JWT):

```bash
# JSON (тело запроса)
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'

# форма (как кнопка Authorize)
curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -d 'username=admin&password=admin123'
```

### Auth
| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/v1/auth/login` | вход (JSON), возвращает JWT |
| POST | `/api/v1/auth/token` | вход (form, для кнопки Authorize), возвращает JWT |

### Users
| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/v1/users` | список пользователей |
| POST | `/api/v1/users` | создать пользователя (тело: `username`, `password`, `is_admin`) |
| GET | `/api/v1/users/{user_id}` | информация о пользователе |
| POST | `/api/v1/users/{user_id}/password` | сменить пароль |
| DELETE | `/api/v1/users/{user_id}` | удалить пользователя (каскадно из групп/шар) |
| POST | `/api/v1/users/{username}/mount-script` | скрипты подключения шар (тело: `password`) |

### Groups
| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/v1/groups` | список групп |
| POST | `/api/v1/groups` | создать группу |
| DELETE | `/api/v1/groups/{group_id}` | удалить группу (личные группы нельзя) |
| GET | `/api/v1/groups/{group_id}/members` | члены группы (с полем `expires_at`) |
| POST | `/api/v1/groups/{group_id}/members` | добавить члена: `user_id`, `access_level` (`rw`/`ro`), `expires_at` (необязательно) |
| DELETE | `/api/v1/groups/{group_id}/members/{user_id}` | убрать члена |
| GET | `/api/v1/groups/{group_id}/shares` | шары группы |
| POST | `/api/v1/groups/{group_id}/shares` | привязать шару: `share_id` |
| DELETE | `/api/v1/groups/{group_id}/shares/{share_id}` | отвязать шару |

### Shares
| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/v1/shares` | список шаров |
| POST | `/api/v1/shares` | создать шар (создаёт каталог в корне) |
| DELETE | `/api/v1/shares/{share_id}` | удалить шар (файлы не трогаются) |
| GET | `/api/v1/shares/available` | каталоги в корне, ещё не зарегистрированные как шары |

### Служебные
| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/v1/sync` | принудительно синхронизировать реестр Samba с БД |
| POST | `/api/v1/expirations/sweep` | немедленно снять истёкшие временные доступы |
| GET | `/api/v1/registry/shares` | фактическое состояние шаров в реестре Samba |

## Пример рабочего сценария

```bash
BASE=http://localhost:8000/api/v1
TOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | jq -r .access_token)
AUTH="Authorization: Bearer $TOKEN"

# пользователи
alice=$(curl -s -X POST $BASE/users -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"alicepw"}' | jq -r .id)
bob=$(curl -s -X POST $BASE/users -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"username":"bob","password":"bobpw"}' | jq -r .id)

# группа и шара
team=$(curl -s -X POST $BASE/groups -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"team"}' | jq -r .id)
photos=$(curl -s -X POST $BASE/shares -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"photos"}' | jq -r .id)

# привязки и права
curl -s -X POST $BASE/groups/$team/shares -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"share_id\":\"$photos\"}" >/dev/null
curl -s -X POST $BASE/groups/$team/members -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$alice\",\"access_level\":\"rw\"}" >/dev/null
curl -s -X POST $BASE/groups/$team/members -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$bob\",\"access_level\":\"ro\"}" >/dev/null
```

После каждого изменения доступы применяются в Samba автоматически;
проверить выдачу: `docker exec nas-app net conf showshare photos`.

## Подключение шары клиентом

Samba слушает только в docker-сети, имя хоста — `nas`. Windows:

```text
net use Z: \\nas\photos /user:alice alicepw
```

Linux:

```bash
mount -t cifs //nas/photos /mnt/photos -o username=alice,password=alicepw
```

Готовые команды под ключи пользователя отдаёт эндпоинт mount-script:

```bash
curl -s -X POST $BASE/users/alice/mount-script -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"password":"alicepw"}'
```

## Тесты

Юнит-тесты (мокают работу с ОС/Samba, гоняются в одноразовом контейнере):

```bash
just test
```

Интеграционные (нужен запущенный `nas-app` и клиентский контейнер):

```bash
just client-up pc1      # создать клиент
just client-setup pc1   # поставить smbclient/cifs-utils
just integration pc1    # полный E2E: права rw/ro, протухание доступа, mount-script
```

Интеграция создаёт временные объекты с уникальным суффиксом и убирает их за собой
(в том числе через `trap` при падении).

## Частые команды (`just`)

| Команда | Что делает |
|---|---|
| `just up` | собрать и запустить |
| `just down` | остановить |
| `just build` | пересобрать образ |
| `just restart` | перезапустить контейнер (код подхватывается через bind-mount) |
| `just logs` | логи приложения |
| `just test` | юнит-тесты |
| `just integration pc1` | интеграционные тесты |
| `just smb-list pc1 alice alicepw` | список шар глазами пользователя |
| `just mount-share pc1 photos alice alicepw /mnt/photos` | смонтировать шару в клиенте |
| `just smoke-registry` | список шаров в реестре Samba |

## Структура

```
app/
  api/v1/          роуты API
  core/            настройки, БД, планировщик
  db/              модели SQLite
  modules/
    auth/          JWT-авторизация
    users/         пользователи + mount-script
    groups/        группы, члены, связи с шарами, sweep истёкших доступов
    shares/        шары
    samba/         net conf / реестр, sync-движок, работу с ОС
deploy/            Dockerfile, compose, entrypoint, smb.conf
tests/             юнит- и интеграционные тесты
docs/              спецификация и план
```