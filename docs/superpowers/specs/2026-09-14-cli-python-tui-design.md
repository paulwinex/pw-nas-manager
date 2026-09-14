# Дизайн: CLI self-service на Python + Textual (Nuitka-бинарь)

Дата: 2026-09-14

## 0. Статус и отношение к другим спекам

Этот документ **заменяет §4** («CLI `nasmanager.sh` / `nasmanager.ps1`») спецификации
`2026-09-14-self-service-cli-design.md` и корректирует связанные с ним пункты:
§3.2 (кнопки скачивания CLI), §2.2 (эндпоинт отдачи клиента), §5.2 (тестирование CLI).
Всё остальное из той спеки (auth с refresh-токенами, self-service эндпоинты, web SPA,
порядок имплементации) остаётся в силе.

**Решение владельца:** вместо двух самодостаточных скриптов (`nasmanager.sh`/`.ps1`)
делаем один Python-пакет с TUI на Textual, который собирается Nuitka в
автономный бинарь на каждую платформу. Один код на обе платформы.

## 1. Требования и критерии

- Аудитория — технические пользователи/админы; на клиенте Python ставить не требуется
  (Nuitka-onefile).
- UI — интерактивный: wizard первого запуска, статус-таблица с выбором стрелками,
  наглядный диф синхронизации (новые шары / отозванные).
- Монтирование на Linux требует root; пароль запрашивается только в момент mount.
- Два бинарных артефакта (Linux, Windows) — единственные отличия платформ локализованы
  в одном модуле монтирования.
- Web-UI скачивает бинарь (кнопка на странице «Мои шары»).

## 2. Структура пакета

```
cli/
  pyproject.toml                # uv; python >= 3.10; deps: textual, httpx
  src/nasmanager/
    __main__.py                 # argparse: --version; иначе запуск TUI
    version.py                  # __version__ (используется в Nuitka-сборке и --version)
    app.py                      # Textual App: DataTable + footer bindings, worker'ы
    config.py                   # config.json + mounts; chmod 600; wizard-создание
    api.py                      # httpx-клиент: login/refresh/shares; retry на 401
    auth.py                     # логика токенов: refresh, logout
    mount_engine.py             # ЕДИНСТВЕННОЕ место с платформенными ветками
    ui/
      wizard.py                 # первый запуск: server_url, логин, mount_root
      main.py                   # экран статус-таблицы + диф
      dialogs.py                # модалки: пароль sudo, пароль smb, вход
  dist/                         # артефакты Nuitka (bind-mount в контейнер приложения)
  build_linux.sh                # сборка Linux-бинар (запускается на Linux)
  build_windows.ps1             # сборка Windows-бинар (запускается на Windows)
```

- Ядро (конфиг, api, auth, diff) полностью общее для платформ.
- Платформенные отличия только в `mount_engine.py` + в wizard (windows_mode на Windows).
- Конфиг-пути (как в прежней спеке §4.2):
  - Linux: `${HOME}/.config/nasmanager/config.json` и `mounts`;
  - Windows: `${USERPROFILE}\.config\nasmanager\config.json` и `mounts`;
  - права на `config.json` — 600 (Linux; на Windows — user profile).

### 2.1 config.json
```json
{
  "server_url": "http://nas:8000",
  "mount_root": "/mnt/nas",
  "windows_mode": "drive",
  "username": "bob",
  "access_token": "…",
  "refresh_token": "…"
}
```
Пароль никогда не сохраняется.

### 2.2 Файл mounts (динамика, как в прежней спеке §4.3)
```
# share  source_uri  target
photos  //nas/photos /mnt/nas/photos
```
- Linux: target = `<mount_root>/<share>`.
- Windows drive: target = буква (`X:`); folder: папка (`C:\nas\photos`); unc: UNC-путь.
- `umount`/статус читают только этот файл + реальное состояние; конфиг не трогают.

## 3. TUI

### 3.1 Wizard (первый запуск, нет config.json)
Экран с Input'ами: `server_url` (default `http://nas:8000`) → `username` + пароль →
`mount_root` (default `/mnt/nas`; Windows `C:\nas`) → на Windows также `windows_mode`.
После ввода: `POST /auth/login` → сохранить access+refresh+username, создать пустой
`mounts`, `chmod 600`. Ошибка логина → остаться на экране с сообщением.

### 3.2 Главный экран — статус-таблица
Textual `DataTable`, колонки: `Share | Access | Status`.
- Статусы: `новая` (в API, нет в mounts), `подключена` (в mounts и реально смонтирована),
  `подключена (без реального mount)` (запись есть, смонтирована нет), `доступ отозван`
  (в mounts, но нет в API). Цветовая подсветка строк.
- Реальное состояние проверяется:
  - Linux: парс `/proc/mounts` (читается обычным юзером, без sudo) — ищем source `//host/share` или target;
  - Windows: сканирование вывода `net use`.
- Footer с bindings: `m` mount выбранных, `M` mount всех неотозванных, `u` umount выбранных,
  `U` umount всех, `p` dry-run preview выбранных/всех, `s` sync (перезапрос `/users/me/shares` + пересчёт),
  `q` quit, `?` справка.

### 3.3 Диф синхронизации
- При запуске и по `s`: загрузить `/users/me/shares`, сравнить с `mounts` и реальным состоянием.
- Шары из API без записи в mounts → строка `новая`, предлагается смонтировать (`m`/`M`).
- Записи mounts без шары в API (доступ отозван) → строка `доступ отозван`, `u`/`U` размонтируют
  и удалят строку со сноской «access removed, unmounted».
- Идемпотентность: перед mount — повторная проверка; уже смонтированное помечается `already mounted`.

### 3.4 Dry-run (preview) режим
- `p` — показывает, какие действия/команды были бы выполнены для выбранных строк (или всех,
  если ничего не выбрано), БЕЗ реальных действий.
- Окно-превью: для каждой строки распечатывается команда, которая выполнилась бы
  (Linux: `sudo mount ...`/`sudo umount ...`; Windows: `net use ...`/`mklink /J ...`),
  статус из диффа (`новая`/`подключена`/`доступ отозван`) и флаг `already-mounted` где применимо.
- Из превью можно уточнить парольный поток (какая модалка появилась бы), но он не запрашивается.
- Реализуется через тот же `mount_engine`, что и реальные действия, — с флагом `dry_run=True`:
  команды собираются и возвращаются, но не выполняются.

## 4. Монтирование (mount_engine.py)

`mount_engine` принимает `dry_run: bool` (default False). При `dry_run=True` планируемые
команды собираются и возвращаются списком без выполнения; пароль в таких случаях не запрашивается.

### 4.1 Linux
1. Проверка реального состояния: парс `/proc/mounts` (без root).
2. `sudo mkdir -p <mount_root>/<share>`.
3. Получение пароля: env `NAS_PASSWORD`, иначе модалка в TUI (Input, password-mode).
4. Попробовать `sudo -n` (кэш прав); при неудаче — `sudo -S mount`, пароль в stdin.
5. Команда:
   `sudo mount -t cifs //<host>/<share> <target> -o credentials=<tmp file>,port=<port>,uid=$(id -u),gid=$(id -g),dir_mode=0755,file_mode=0644`
   cred-файл: `mkstemp` + `chmod 600`, запись `username=<u>\npassword=<p>`, удаление по `trap`/finally.
6. Запись строки в `mounts`.

### 4.2 Windows (по `windows_mode`)
- `drive`: свободная буква — перебор `A:`..`Z:` через `os.path.exists(f"{l}:\\")`; `net use X: \\<host>\<share> /user:<username> <password>`.
- `folder`: UNC-монтирование `net use \\<host>\<share> /user:<username> <password>` + junction `mklink /J <mount_root>\<share> \\<host>\<share>` (junction — без прав админа).
- `unc`: `net use \\<host>\<share> /user:<username> <password>`.
- Пароль: env `NAS_PASSWORD` или модалка; не логируется.

### 4.3 Umount
- Linux: `sudo umount <target>` (если реально смонтировано), затем удаление строки из `mounts`.
- Windows по типу target: буква диска → `net use X: /delete`; folder — удалить junction
  (`Remove-Item` без риска -recurse) + `net use \\host\share /delete`; unc — `net use \\host\share /delete`.
- Некритичные ошибки не роняют приложение, выводятся как предупреждения.

## 5. Auth

- Токены (access+refresh) в config.json; доступ 600.
- 401 на `/users/me/shares` → `POST /auth/refresh` → обновить пару → retry запроса.
- Refresh протух/отсутствует → модалка входа (username+password) → `/auth/login` → сохранить пару.
- `logout` (сомнительная полезность, но тривиально) — по желанию; не в первой версии.

## 6. Backend и доставка бинаря

- Из прежней спеки убирается `scripts/nasmanager.sh|ps1` и `GET /users/me/cli-script?os=sh|ps1`.
- `build_mount_script` остаётся — только для блока «Ручное подключение» на web-странице.
- Новый эндпоинт: **`GET /users/me/cli?os=linux|windows`** (под `get_current_user`) →
  `FileResponse` из `CLI_DIST_DIR` (env, default `/app/cli-dist`).
  Имя резолвится glob'ом по `cli-dist/nasmanager-<os>-*` (версия не зашита в web);
  `Content-Disposition: attachment; filename=<найденное имя>`. Нет файла → 404.
- `deploy/compose.yml`: volume `../cli/dist:/app/cli-dist:ro`.
- Web-страница «Мои шары»: кнопки «Скачать nasmanager (Linux)» / «Скачать nasmanager (Windows)»
  → `GET /users/me/cli?os=linux|windows`; blob-скачивание как и прежде.
- Ожидающие обновления артефакта (новой версии) пересобираются на месте и кладутся в `cli/dist/`
  с каноническими именами `nasmanager-linux-x86_64` / `nasmanager-windows-x86_64.exe`.

## 7. Сборка (Nuitka)

- Linux (на Linux-хосте), `just cli-build-linux`:
  `uv run nuitka --standalone --onefile --include-package-data=textual --include-package=httpx --output-filename=dist/nasmanager-linux-x86_64 src/nasmanager`
- Windows (на Windows-машине), `build_windows.ps1` — та же команда через `python -m nuitka`
  или `uv run nuitka`, `--output-filename=dist\nasmanager-windows-x86_64.exe`.
- Nuitka не кросс-компилирует → оба артефакта собираются на своей ОС. Инструкция в README.
- `nasmanager --version` печатает версию пакета.

## 8. Тестирование

- **Backend** (pytest, TestClient): `GET /users/me/cli?os=linux|windows` отдаёт файл/404,
  отдаёт с правильным имя attachment; не-admin имеет доступ, admin-эндпоинты по-прежнему 403.
- **CLI-логика** (python-тесты, без TUI-рендеринга):
  - config: чтение/запись/миграция, chmod;
  - api: login/refresh/shares через `httpx.MockTransport`, retry на 401, rotation;
  - diff: сравнение API-списка, mounts и реального состояния;
  - mount_engine: сборка команд и парольный поток через mock subprocess.
  Тесты кладутся в `cli/tests/`, запуск: `uv run pytest` (на хосте или в приложении).
- **Manual**: Linux-бинарь кладётся в привилегированный клиент `just client-up pc1`
  (ubuntu onefile — Python на клиенте отсутствует, это же проверка автономности);
  `just client-setup pc1` для cifs-utils. Windows — ручной прогон на реальной машине.
- README: заметка о ручной проверке.

## 9. Порядок имплементации

1. Backend: эндпоинт `GET /users/me/cli?os=...`, volume в compose. (+тест)
2. CLI-пакет: скелет, config, api, auth, diff-логика. (+тесты без TUI)
3. CLI TUI: wizard, статус-таблица, bindings, диф. Manual в клиент-контейнере (пакет, не бинарь).
4. mount_engine Linux: mount/umount, sudo `-n`/`-S` поток, `/proc/mounts`, idempotency. (+тесты; manual в pc1)
5. mount_engine Windows: drive/folder/unc. Manual на Windows.
6. Nuitka-сборки: `build_linux.sh`, `build_windows.ps1`, `just cli-build-linux`; проверить onefile в pc1.
7. Web: кнопки скачивания, убрать старые `cli-script?os=sh|ps1` ссылки. Сборка web.
8. README: раздел CLI/установка бинаря.

## 10. Отличия от прежнего решения (для ретроспективы)

| Аспект | было (sh+ps1) | стало (Python+Textual) |
|---|---|---|
| Коды | 2 скрипта | 1 пакет, платформы в mount_engine |
| Интерактив | флаги, `select`/net use | wizard, DataTable, стрелки |
| Root | всегда sudo mount | `sudo -n`/`-S`, пароль только в момент mount |
| Доставка | скачивание .sh/.ps1 | Nuitka-onefile `.exe`/ELF, скачивание того и другого |
| Зависимости клиента | нет | нет (бинарь), логика тестируется Python исхода |
| Поддержка | bash+ps1 логика ×2 | Python один код |