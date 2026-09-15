# Web-UI Layout Refactor Design

Date: 2026-09-15
Status: Approved by product owner

## Problem

The web frontend (`web-ui`) currently mixes the regular user area and the admin
area in one menu: `MainLayout` renders a single sidebar that contains the main
items ("Мои шары", "Профиль") plus an "Админка" expansion with the admin items
(Dashboard, Users, Shares, Groups, System). The user area and the admin area
should be separated into two layouts:

- **Regular users** should not have a sidebar at all — a single main page at `/`
  with two tabs, and profile settings reachable from the user menu.
- **Admins** should reach the admin area via an "АДМИНКА" link in the user menu;
  the admin area is its own layout with its own sidebar. The sidebar toggle
  button is desktop-invisible and only shown on mobile, where it opens the menu
  as a drawer over the content.

## Accepted approach: separate admin layout via file-based routing (Option A)

Keep the project's file-based routing (`filenameBasedRouting: true`). Move the
admin pages from `src/pages/index/admin/` to `src/pages/admin/` and give the
admin area its own layout wrapper, mirroring the proven parent/child pattern
already used at the root:

- `src/pages/index.vue` → `/` renders user `MainLayout`; children:
  `(index).vue` → `/`, `profile.vue` → `/profile`.
- `src/pages/admin.vue` → `/admin` renders new `AdminLayout`; children in
  `src/pages/admin/`: `(index).vue` → `/admin` (dashboard), `users.vue`,
  `shares.vue`, `groups.vue`, `system.vue`.

> **File-based routing detail (verified against this toolchain):** the parent
> layout wrapper must be a FILE `src/pages/admin.vue` next to the directory
> `src/pages/admin/` — exactly like the root `src/pages/index.vue` +
> `src/pages/index/`. Putting a wrapper at `src/pages/admin/index.vue` does
> **not** nest the sibling admin pages under it (they become top-level sibling
> routes and render without the layout).

The router guard `if (to.path.startsWith('/admin') && !auth.isAdmin)` keeps
working unchanged because the `/admin/*` paths are preserved.

## Layouts

### MainLayout (reworked, user area)

- Header tool bar: app title "NAS Manager" (click → `/`), user menu on the right.
- **No sidebar, no hamburger button.**
- Content: centered `.page-box` (max-width 1000px) as today.

### AdminLayout (new, `/admin/*`)

- Header tool bar: hamburger button **visible only on mobile** (<1024px),
  app title "NAS Manager" (click → `/`), user menu on the right.
- Desktop (≥1024px): sidebar rendered as the **inline flex `<aside>` inside the
  centered `.page-box`** — exactly the current centered UI. It does **not**
  stick to the viewport edge; there is no toggle button.
- Mobile (<1024px): a real `q-drawer` with `behavior="mobile"` that slides
  **over the content** with a backdrop (it does not shift the content), width
  240px, opened by the hamburger.
- The nav list is extracted into one `AdminNav` component reused by both the
  desktop aside and the mobile drawer.

### Shared user menu (`UserMenu.vue`)

Used by both layouts. Contents:

- "Профиль" → `/profile` (separate page, per owner decision).
- Admin only, when **not** on an admin route: "АДМИНКА" → `/admin`.
- Admin only, when **on** an admin route: "На главную" → `/`.
- Separator, then "Выйти" (logout).

## Main page `/` (two tabs)

Rework `src/pages/index/(index).vue` into `q-tabs`:

- Tab "Мои шары": the existing table of available shares.
- Tab "Скрипты": CLI download buttons (Linux/Windows) **and** the manual mount
  scripts with copy buttons (current "Скачать CLI" + "Ручное подключение"
  blocks).

Both API calls (`api.meShares()`, `api.meMountScript()`) still load in parallel
on mount with a single loading/error state, exactly as today.

## Mobile responsive tweaks

Mobile threshold = current measure point: viewport width < 1024px
(Quasar `$q.screen.lt.md`; Quasar 2 breakpoints: sm=600, md=1024, lg=1440),
to stay consistent with the existing sidebar collapse behavior.

- **Users table**: hide the "Created" (`created_at`) column on mobile via a
  computed `columns` array filtered by `$q.screen.lt.md`.
- **Shares table**: hide the "Comment" (`comment`) column on mobile the same way.
- **System page**: cards one per row on mobile — media query
  `@media (max-width: 1023px)` sets `.dash-card-half { flex-basis: 100% }`.
- **Dashboard page**: cards two per row on mobile — same media query sets
  `.dash-card { flex: 1 1 45%; }`.

## Files

New:

- `src/layouts/AdminLayout.vue`
- `src/components/layout/AdminNav.vue`
- `src/components/layout/UserMenu.vue`
- `src/pages/admin.vue` (wrapper `<AdminLayout />`)
- `src/pages/admin/(index).vue`, `users.vue`, `shares.vue`, `groups.vue`,
  `system.vue` (moved from `src/pages/index/admin/`, via `git mv`)

Modified:

- `src/layouts/MainLayout.vue` (drop sidebar + hamburger, use `UserMenu`)
- `src/pages/index/(index).vue` (two tabs)
- `src/css/app.scss` (responsive card media queries)

Deleted:

- `src/pages/index/admin/` (whole directory relocated)

## Non-goals

- No backend/API changes.
- No changes to profile page contents, login, or 404 flow.
- No change to the mobile threshold (1024px).

## Verification

- `quasar build` succeeds (build only; the dev server is not started).
- No `vue-tsc` type errors (`npm run typecheck`) after `quasar prepare` has
  regenerated the typed router.