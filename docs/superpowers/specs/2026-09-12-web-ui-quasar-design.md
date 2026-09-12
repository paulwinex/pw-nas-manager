# Web UI «NAS Manager» on Vue 3 + Quasar 2 (design)

Дата: 2026-09-12

Язык интерфейса: **английский**.

## 1. Цель

Веб-интерфейс для управления NAS (FastAPI + Samba registry sync). Все endpoints API уже
реализованы и admin-only (JWT Bearer, `/api/v1/auth/token` — OAuth2 form, `/api/v1/auth/login` — JSON).

Scaffold UI — пустой проект Quasar 2 (Vite, TS strict, pinia, filename-based routing, hash-роутер)
в `web-ui/`. Финальное приложение раздаёт **тот же** FastAPI: собранный SPA монтируется на
FastAPI статикой.

## 2. Архитектура (dev / prod)

- **Dev**: `quasar dev` (порт Vite, default 9000). Vite dev-proxy в `quasar.config.ts`:
  `'/api': { target: 'http://localhost:8000', changeOrigin: true }`. UI шлёт запросы на
  относительный путь `/api/v1/...` — CORS не нужен.
- **Prod**: multi-stage Dockerfile:
  - стадия `node` (`node:22-alpine`): `yarn install` + `quasar build` → `web-ui/dist`;
  - финальная python-стадия: копирует `web-ui/dist` в образ;
  - `app/main.py`: после `include_router(api_router, prefix="/api/v1")` монтирует
    `StaticFiles(directory=<dist>, html=True)` на `/` **условно** (только если директория
    существует — тестовый контейнер живёт без UI).
- Hash-роутинг (уже включён в scaffold, `vueRouterMode: 'hash'`) → SPA-fallback на сервере
  не нужен: браузер всегда запрашивает `/`.
- Единственная публикуемая точка — порт 8000 (API + статика).

## 3. Сессия и авторизация

- `src/stores/auth.ts` (pinia): `token`, `username`, `isAdmin`; персист в `localStorage`.
  Actions: `login(username, password)` → `POST /auth/token` (form-data); успех → сохранить token,
  затем `GET /auth/me` (см. бэкенд) для `username`/`isAdmin`; `logout()` чистит storage и
  редиректит на `/login`.
- Ошибки: 401 (`Unauthorized`) — «Неверный логин/пароль»; 403 (`Forbidden`) — «Доступ только
  для администратора».
- **Route guard** в `src/router/index.ts` (`defineRouter`): без token → `/login` для любых
  маршрутов кроме `/login`; с token и путь `/login` → `/`.
- **API-клиент** `src/api/client.ts` (axios, добавляется в зависимости): baseURL `''`,
  request-interceptor добавляет `Authorization: Bearer <token>`, response-interceptor на 401 →
  `auth.logout()` + редирект на `/login`.
- Тёмная тема по умолчанию: `quasar.config.ts` → `framework.config = { dark: true }`.
  Предпочтение пользователя (переключатель в Profile) хранится в `localStorage`.

## 4. Роутинг и лэйаут

```
src/pages/login.vue            → /login       (вне лэйаута)
src/pages/index.vue            → лэйаут-корень: MainLayout + boxed-контейнер для router-view
  src/pages/index/(index).vue  → /             Дашборд
  src/pages/index/users.vue    → /users
  src/pages/index/groups.vue   → /groups
  src/pages/index/shares.vue   → /shares
  src/pages/index/system.vue   → /system
  src/pages/index/profile.vue  → /profile
src/pages/[...path].vue        → 404 → редирект на /
```

Демо-файлы scaffold удаляются: `src/pages/index/second.vue`, `src/components/EssentialLink.vue`,
`src/stores/example-store.ts`.

**`src/layouts/MainLayout.vue`** (компонент; `src/pages/index.vue` только подключает его):
- `QHeader` + `QToolbar`: гамбургер (показывает/скрывает QDrawer на малых экранах), заголовок
  «NAS Manager», справа — `QBtn` c аватаром → `QMenu`: **Profile** (`/profile`), **Exit**
  (лог-аут).
- `QDrawer side="left" bordered show-if-above`: навигация `QList` → `router-link` c иконками
  и подсветкой активной страницы: Дашборд (`dashboard`), Users (`people`), Shares
  (`folder_shared`), Groups (`groups`), System (`settings`).
- **Boxed layout**: router-view оборачивается в контейнер `max-width: 1200px`, `margin: 0 auto`,
  `padding: 16px` (класс-хелпер в `app.scss`). Страницы не растягиваются на всю ширину.
- Login — отдельная полноэкранная страница вне лэйаута.

## 5. Страницы

Все тексты интерфейса (заголовки, кнопки, уведомления, сообщения ошибок) — **на английском**.
Описанные ниже экраны:

### Login (`/login`)
Полноэкранная тёмная страница, центрированный `QCard` (max-width ~400px): заголовок,
`QForm` (username, password с переключателем видимости, кнопка «Войти» с `loading`), блок ошибки.
Успех → редирект на `/`.

### Дашборд (`/`, источник: NEW `GET /api/v1/stats`)
- Стат-карточки (QStat/QCard с иконками): пользователи, группы, шары (в БД), шары в реестре
  Samba, всего членств, истекающих ≤7 дней.
- Блок «Скорое истечение»: члены (файл юзера и группы), у которых `expires_at` наступит в течение
  7 дней, отсортированные по дате.
- Health-индикатор (`GET /health`), кнопка «Обновить».

### Users (`/users`)
Таблица: username · бейдж «admin» · created_at · действия.
- **Создать пользователя** (диалог): username (паттерн `[a-z][a-z0-9_-]{1,31}`, hint), password
  (показ/скрытие), `is_admin` (switch) → `POST /users`.
- **Сменить пароль** (диалог): новый пароль → `POST /users/{id}/password`.
- **Группы пользователя** (диалог): список членств юзера (группа · уровень · истечение · удалить
  из группы) и форма добавления (выбор группы — кроме personal; access RW/RO; дата+время
  истечения, опционально) → `POST /groups/{gid}/members` / `DELETE /groups/{gid}/members/{uid}`.
  Данные считаются на клиенте из `GET /groups` + `GET /groups/{id}/members` (отдельного
  endpoint «группы юзера» нет — вводить не будем, YAGNI).
- **Mount-script** (диалог): поле пароля юзера → `POST /users/{username}/mount-script` → список
  шар (name/path/access) + Windows (`net use`) и Linux (`mount -t cifs`) скрипты в read-only
  textarea с кнопками «Копировать».
- **Удалить** (confirm-диалог, danger) → `DELETE /users/{id}`.
- Уведомления через Quasar Notify (успех/ошибка).

### Groups (`/groups`)
Таблица: name · бейдж «personal» · действия (delete — скрыт для personal-групп, сервер всё
равно отклоняет).
- **Создать группу** (диалог) → `POST /groups`.
- Выбор группы → деталь-карточки на той же странице:
  - **Члены**: таблица username · RW/RO · expires_at · удалить из группы; форма добавления
    (выбор юзера из `GET /users`, уровень, истечение) → `POST /groups/{id}/members`.
  - **Шары**: список привязанных шар; добавить (select из `GET /shares`) →
    `POST /groups/{id}/shares`; отвязать → `DELETE /groups/{id}/shares/{share_id}`.
- **Удалить группу** → `DELETE /groups/{id}` (confirm).

### Shares (`/shares`)
Таблица: name · path · действия.
- **Создать шару** (диалог): name; подсказки из `GET /shares/available` (autocomplete) →
  `POST /shares`.
- **Удалить** (confirm) → `DELETE /shares/{id}`.

### System (`/system`)
- Карточка Health: `GET /health`.
- **Синхронизировать реестр**: `POST /sync` → показать `SyncReport` (added/removed/updated).
- **Очистить просроченные**: `POST /expirations/sweep` → `processed` + при необходимости report.
- **Реестр Samba**: `GET /registry/shares` → список ключей + параметры. Кнопка «Обновить».

### Profile (`/profile`)
- Карточка профиля из `GET /auth/me`: username, is_admin, created_at.
- **Сменить пароль**: новый пароль ×2 (валидация совпадения) → `POST /users/{id}/password`
  (id текущего админа из `/auth/me`).
- Переключатель «Тёмная тема» (преф в `localStorage`).

## 6. Бэкенд-донастройки (минимальные)

1. **`GET /api/v1/auth/me`** — в `app/modules/auth/routes.py`:
   `Depends(get_current_admin)` возвращает `User` → ответ `UserOut` (id, username, is_admin,
   created_at). Нужен для Profile и для имени пользователя в шапке.
2. **`GET /api/v1/stats`** — новый модуль `app/modules/stats/` (routes + services):
   - `users_count`, `admins_count`, `groups_count`, `personal_groups_count`,
     `shares_count`, `registry_shares_count` (через `sync_engine.registry_state()`),
     `memberships_count`;
   - `expiring_memberships`: join `UserGroupExpiration` (is_active, `expires_at` в `[now,
     now+7d]`) с `users`/`groups` → список `{user_id, username, group_id, group_name,
     access_level, expires_at}`, сортировка по `expires_at`;
   - `StatsResponse` с этими полями; admin-only.
3. **Статика**. `app/main.py`: пункт 2.2. `UI_DIST_DIR` (env, default `web-ui/dist`) — путь к
   dist; монтировать только если `os.path.isdir`. Порядок: сначала api-роутер (`/api/v1`), потом
   статику на `/` (html=True).
4. **Инфраструктура**: multi-stage `deploy/Dockerfile` (стадия node для `web-ui`), `justfile`:
   рецепты `ui-dev`, `ui-typecheck`, `ui-build`; README — раздел про UI.
   CORS не добавляем (same-origin в prod, vite-proxy в dev).

Изменяемые бэкенд-файлы: `app/modules/auth/routes.py`, `app/main.py`,
`app/modules/stats/{__init__,routes,services}.py`, `deploy/Dockerfile`, `justfile`, README,
`tests` (новые тесты на `/auth/me` и `/stats`).

## 7. Файлы web-ui (новые/изменённые)

- `quasar.config.ts`: `framework.config.dark = true`, `devServer.proxy['/api']`.
- `package.json`: + `axios`.
- `src/api/client.ts`, `src/stores/auth.ts` (`example-store.ts` удаляется).
- `src/router/index.ts`: route guard.
- `src/layouts/MainLayout.vue` (новый), `src/pages/index.vue` (лэйаут-корень + boxed).
- Страницы: `login.vue`, `index/(index).vue`, `index/users.vue`, `index/groups.vue`,
  `index/shares.vue`, `index/system.vue`, `index/profile.vue`.
- Удалить: `index/second.vue`, `components/EssentialLink.vue`, `stores/example-store.ts`,
  демо-контент `index.vue`.
- `src/css/app.scss`: boxed-контейнер и мелкие хелперы.

## 8. Тестирование и проверка

- **Бэкенд**: новые pytest — `/auth/me` (200 с token-админа, 401 без), `/stats` (счётчики
  соответствуют сиженным данным, истекающие членства корректны). Прогнать `just test`
  (существующие 32 теста должны остаться зелёными).
- **Фронтенд**: `yarn typecheck` (`vue-tsc --noEmit`), `yarn build` (`quasar build`).
- **Live smoke**: `just up` → логин admin/admin123 → пробежка по разделам: создать юзер/группу/
  шару, добавить в группу, mount-script диалог, sync/sweep, logout → редирект на `/login`.
  `curl :8000/` отдаёт index.html, `curl :8000/api/v1/health` — ok.
- **Чек-лист по списку пользователя**: тёмная тема по умолчанию; дефолтный лэйаут убран;
  неавторизованные → `/login`; новый лэйаут (сайдбар слева, контент справа); user-меню
  (Profile/Exit); разделы Users/Shares/Groups (+ Дашборд, System, Profile).

## 9. Вне скоупа (YAGNI)

- History-роутинг; фреймворк локализации (i18n) — пока не нужен, UI на английском;
- редактирование username / toggle `is_admin` у существующего юзера (нет таких API);
  отдельные страницы под детали (всё в диалогах/на странице);
- многоязычность, PWA/SSR, развёртывание UI отдельным процессом.