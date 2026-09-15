# Web-UI Layout Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the single combined MainLayout into a sidebar-less user layout plus a separate admin layout with its own sidebar/drawer, and make the user home page two-tabbed.

**Architecture:** Keep Quasar file-based routing. `src/pages/index.vue` stays the user layout (`/`), admin pages move from `src/pages/index/admin/` to `src/pages/admin/` with a new `admin.vue` wrapper (a FILE, mirroring the root `src/pages/index.vue` + `src/pages/index/` pattern — `pages/admin/index.vue` does NOT nest sibling pages) + `AdminLayout.vue`. Two shared components (`UserMenu.vue`, `AdminNav.vue`) are reused by both layouts. Mobile (<1024px) gets a `behavior="mobile"` `q-drawer` (overlay, does not shift content); desktop keeps the centered `.page-box` with an inline `<aside>` sidebar.

**Tech Stack:** Vue 3, Quasar 2 (`q-layout`, `q-drawer`, `q-tabs`, `$q.screen`), vue-router auto-routes, TypeScript strict, Pinia auth store.

---

> **Test strategy note:** `web-ui` has no JS unit test framework. Verification = `yarn typecheck` (`vue-tsc --noEmit`) and `yarn build` (`quasar build`, SPA only, never `quasar dev`). Run `npx quasar prepare` whenever page files move so `src/router/typed-router.d.ts` regenerates. Do not start the dev server.

## File Structure

New:
- `web-ui/src/components/layout/UserMenu.vue` — shared user dropdown (profile / admin entry / logout)
- `web-ui/src/components/layout/AdminNav.vue` — admin nav list (shared by aside + drawer)
- `web-ui/src/layouts/AdminLayout.vue` — admin layout: desktop inline aside, mobile overlay drawer
- `web-ui/src/pages/admin.vue` — route wrapper `<AdminLayout />` for `/admin` (a FILE next to the `pages/admin/` directory, mirroring the root `pages/index.vue` pattern)
- `web-ui/src/pages/admin/{groups,shares,system,users}.vue` — moved from `src/pages/index/admin/`
- `web-ui/src/pages/admin/(index).vue` — moved dashboard

Modified:
- `web-ui/src/layouts/MainLayout.vue` — remove sidebar + hamburger, use `UserMenu`
- `web-ui/src/pages/index/(index).vue` — two tabs: "Мои шары" / "Скрипты"
- `web-ui/src/css/app.scss` — responsive card media queries

Deleted (moved):
- `web-ui/src/pages/index/admin/` (whole directory relocated)

Route map after refactor (regenerated into `web-ui/src/router/typed-router.d.ts`):
- `/` → `pages/index.vue` (`MainLayout`), children `(index).vue`, `profile.vue`
- `/admin` → `pages/admin.vue` (`AdminLayout`), children `(index).vue` (dashboard), `users.vue`, `shares.vue`, `groups.vue`, `system.vue`

---

### Task 1: Shared components — `UserMenu.vue` and `AdminNav.vue`

**Files:**
- Create: `web-ui/src/components/layout/UserMenu.vue`
- Create: `web-ui/src/components/layout/AdminNav.vue`

- [ ] **Step 1: Create `web-ui/src/components/layout/UserMenu.vue`**

```vue
<template>
  <q-btn-dropdown flat no-caps :label="auth.username || 'Account'" icon="person">
    <q-list style="min-width: 200px">
      <q-item clickable v-close-popup to="/profile">
        <q-item-section avatar>
          <q-icon name="account_circle" />
        </q-item-section>
        <q-item-section>Профиль</q-item-section>
      </q-item>
      <q-item v-if="auth.isAdmin && !inAdminArea" clickable v-close-popup to="/admin">
        <q-item-section avatar>
          <q-icon name="admin_panel_settings" />
        </q-item-section>
        <q-item-section>АДМИНКА</q-item-section>
      </q-item>
      <q-item v-if="auth.isAdmin && inAdminArea" clickable v-close-popup to="/">
        <q-item-section avatar>
          <q-icon name="home" />
        </q-item-section>
        <q-item-section>На главную</q-item-section>
      </q-item>
      <q-separator />
      <q-item clickable v-close-popup @click="logout">
        <q-item-section avatar>
          <q-icon name="logout" />
        </q-item-section>
        <q-item-section>Выйти</q-item-section>
      </q-item>
    </q-list>
  </q-btn-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const inAdminArea = computed(() => route.path.startsWith('/admin'));

function logout() {
  auth.logout();
  router.push('/login');
}
</script>
```

- [ ] **Step 2: Create `web-ui/src/components/layout/AdminNav.vue`**

```vue
<template>
  <q-list padding>
    <q-item
      v-for="item in items"
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
</template>

<script setup lang="ts">
const items = [
  { to: '/admin', label: 'Dashboard', icon: 'dashboard' },
  { to: '/admin/users', label: 'Users', icon: 'people' },
  { to: '/admin/shares', label: 'Shares', icon: 'folder_shared' },
  { to: '/admin/groups', label: 'Groups', icon: 'groups' },
  { to: '/admin/system', label: 'System', icon: 'settings' },
];
</script>
```

- [ ] **Step 3: Verify typecheck**

Run: `yarn typecheck` (in `web-ui/`)
Expected: no errors (`vue-tsc` exits 0).

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/components/layout/UserMenu.vue web-ui/src/components/layout/AdminNav.vue
git commit -m "feat(ui): add shared UserMenu and AdminNav components"
```

---

### Task 2: Rework `MainLayout.vue` into the sidebar-less user layout

**Files:**
- Modify: `web-ui/src/layouts/MainLayout.vue` (whole file)

- [ ] **Step 1: Replace the contents of `web-ui/src/layouts/MainLayout.vue` with:**

```vue
<template>
  <q-layout view="hHh lpR lFf">
    <q-header class="bg-primary text-white">
      <div class="page-box">
        <q-toolbar>
          <q-toolbar-title class="cursor-pointer" @click="router.push('/')">
            NAS Manager
          </q-toolbar-title>
          <UserMenu />
        </q-toolbar>
      </div>
    </q-header>

    <q-page-container>
      <div class="page-box q-py-md">
        <main class="page-content" style="min-width: 0">
          <router-view />
        </main>
      </div>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import UserMenu from '@/components/layout/UserMenu.vue';

const router = useRouter();
</script>
```

This drops the sidebar, the "Админка" expansion, the hamburger toggle, and the resize logic entirely.

- [ ] **Step 2: Verify typecheck**

Run: `yarn typecheck`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/layouts/MainLayout.vue
git commit -m "feat(ui): user layout without sidebar; menu via app bar dropdown"
```

---

### Task 3: Create `AdminLayout.vue` and the `/admin` route wrapper

Desktop (`>=1024px`): inline `<aside>` sidebar inside the centered `.page-box` — same UI as today, no toggle button. Mobile (`<1024px`): hamburger opens a `q-drawer` (`behavior="mobile"`) that overlays content.

**Files:**
- Create: `web-ui/src/layouts/AdminLayout.vue`
- Create: `web-ui/src/pages/admin.vue`

- [ ] **Step 1: Create `web-ui/src/layouts/AdminLayout.vue`**

```vue
<template>
  <q-layout view="hHh lpR lFf">
    <q-header class="bg-primary text-white">
      <div class="page-box">
        <q-toolbar>
          <q-btn
            v-if="isMobile"
            flat
            round
            dense
            icon="menu"
            aria-label="Menu"
            @click="drawerOpen = true"
          />
          <q-toolbar-title class="cursor-pointer" @click="router.push('/')">
            NAS Manager
          </q-toolbar-title>
          <UserMenu />
        </q-toolbar>
      </div>
    </q-header>

    <q-drawer
      v-if="isMobile"
      v-model="drawerOpen"
      side="left"
      behavior="mobile"
      :width="240"
      bordered
    >
      <AdminNav />
    </q-drawer>

    <q-page-container>
      <div class="page-box page-flex q-py-md">
        <aside v-if="!isMobile" class="page-sidebar">
          <AdminNav />
        </aside>
        <main class="page-content" style="min-width: 0">
          <router-view />
        </main>
      </div>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useRoute, useRouter } from 'vue-router';
import AdminNav from '@/components/layout/AdminNav.vue';
import UserMenu from '@/components/layout/UserMenu.vue';

const $q = useQuasar();
const router = useRouter();
const route = useRoute();

const drawerOpen = ref(false);
const isMobile = computed(() => $q.screen.lt.md);

watch(
  () => route.fullPath,
  () => {
    drawerOpen.value = false;
  },
);
</script>
```

- [ ] **Step 2: Create `web-ui/src/pages/admin.vue`**

```vue
<template>
  <AdminLayout />
</template>

<script setup lang="ts">
import AdminLayout from '@/layouts/AdminLayout.vue';
</script>
```

- [ ] **Step 3: Verify typecheck**

Run: `yarn typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/layouts/AdminLayout.vue web-ui/src/pages/admin.vue
git commit -m "feat(ui): admin layout with sidebar (desktop) and overlay drawer (mobile)"
```

---

### Task 4: Move admin pages and apply mobile responsive tweaks

**Files:**
- Move: `web-ui/src/pages/index/admin/` → `web-ui/src/pages/admin/`
- Modify: `web-ui/src/pages/admin/users.vue` (columns)
- Modify: `web-ui/src/pages/admin/shares.vue` (columns)
- Modify: `web-ui/src/css/app.scss` (media queries)
- Regenerate: `web-ui/src/router/typed-router.d.ts` (via `quasar prepare`)

- [ ] **Step 1: Move the directory**

```bash
git mv web-ui/src/pages/index/admin web-ui/src/pages/admin
```

Result files: `(index).vue`, `groups.vue`, `shares.vue`, `system.vue`, `users.vue` under `web-ui/src/pages/admin/` (the parent wrapper is the FILE `web-ui/src/pages/admin.vue` created in Task 3 — do not create an `admin/index.vue`).

- [ ] **Step 2: `users.vue` — hide "Created" column on mobile**

In `web-ui/src/pages/admin/users.vue`, replace the plain `columns` array (currently around lines 134-139):

```ts
const columns = [
  { name: 'username', label: 'Username', field: 'username', align: 'left' as const },
  { name: 'is_admin', label: 'Role', field: 'is_admin', align: 'left' as const },
  { name: 'created_at', label: 'Created', field: 'created_at', align: 'left' as const },
  { name: 'actions', label: '', field: '', align: 'right' as const },
];
```

with a computed version:

```ts
const columns = computed<QTableColumn[]>(() => {
  const cols: QTableColumn[] = [
    { name: 'username', label: 'Username', field: 'username', align: 'left' },
    { name: 'is_admin', label: 'Role', field: 'is_admin', align: 'left' },
  ];
  if (!$q.screen.lt.md) {
    cols.push({ name: 'created_at', label: 'Created', field: 'created_at', align: 'left' });
  }
  cols.push({ name: 'actions', label: '', field: '', align: 'right' });
  return cols;
});
```

`$q` (from `useQuasar()`) and `computed` are already imported in this file. Also add the `QTableColumn` import to the existing `import { useQuasar } from 'quasar';` line:

```ts
import { useQuasar } from 'quasar';
import type { QTableColumn } from 'quasar';
```

Keep the `body-cell-created_at` slot and `formatDate` as-is — the slot is simply unused while the column is hidden.

- [ ] **Step 3: `shares.vue` — hide "Comment" column on mobile**

In `web-ui/src/pages/admin/shares.vue`, replace the plain `columns` array (currently around lines 139-144):

```ts
const columns = [
  { name: 'name', label: 'Name', field: 'name', align: 'left' as const },
  { name: 'path', label: 'Path', field: 'path', align: 'left' as const },
  { name: 'comment', label: 'Comment', field: 'comment', align: 'left' as const },
  { name: 'actions', label: '', field: '', align: 'right' as const },
];
```

with:

```ts
const columns = computed<QTableColumn[]>(() => {
  const cols: QTableColumn[] = [
    { name: 'name', label: 'Name', field: 'name', align: 'left' },
    { name: 'path', label: 'Path', field: 'path', align: 'left' },
  ];
  if (!$q.screen.lt.md) {
    cols.push({ name: 'comment', label: 'Comment', field: 'comment', align: 'left' });
  }
  cols.push({ name: 'actions', label: '', field: '', align: 'right' });
  return cols;
});
```

`$q` (from `useQuasar()`) and `computed` are already imported in this file. Also add the `QTableColumn` import to the existing `import { useQuasar } from 'quasar';` line:

```ts
import { useQuasar } from 'quasar';
import type { QTableColumn } from 'quasar';
```

- [ ] **Step 4: `app.scss` — responsive card grids**

Append to `web-ui/src/css/app.scss`:

```scss
@media (max-width: 1023px) {
  .dash-card {
    flex: 1 1 45%;
  }

  .dash-card-half {
    flex: 1 1 100%;
  }
}
```

This makes Dashboard cards 2 per row and System cards 1 per row on mobile (`<1024px`). No changes to the `system.vue`/dashboard page bodies are needed.

- [ ] **Step 5: Regenerate the typed router**

Run: `npx quasar prepare`
Expected: rewrites `web-ui/src/router/typed-router.d.ts`. Confirm the file now maps `src/pages/admin.vue` as the `/admin` parent with the admin children nested under it (and no longer lists them under `src/pages/index/admin/`). If the admin children are NOT nested under the `/admin` route record, the wrapper must be a FILE `src/pages/admin.vue` next to the directory `src/pages/admin/` (mirroring root `index.vue` + `index/`) — `pages/admin/index.vue` does not nest.

- [ ] **Step 6: Verify typecheck**

Run: `yarn typecheck`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add web-ui/src/pages/index/admin web-ui/src/pages/admin web-ui/src/css/app.scss web-ui/src/router/typed-router.d.ts
git commit -m "feat(ui): move admin pages under /admin; responsive table columns and card grids"
```

---

### Task 5: Rework the home page into two tabs

**Files:**
- Modify: `web-ui/src/pages/index/(index).vue` (whole file)

- [ ] **Step 1: Replace the contents of `web-ui/src/pages/index/(index).vue` with:**

```vue
<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Мои шары</div>

    <div v-if="loading" class="text-grey">Загрузка…</div>
    <div v-else-if="error" class="text-negative q-mb-md">
      Ошибка загрузки. <q-btn flat dense label="Повторить" @click="load" />
    </div>

    <template v-else>
      <q-tabs v-model="tab" class="text-primary q-mb-md">
        <q-tab name="shares" label="Мои шары" icon="folder_shared" />
        <q-tab name="scripts" label="Скрипты" icon="terminal" />
      </q-tabs>

      <q-tab-panels v-model="tab" animated>
        <q-tab-panel name="shares">
          <q-markup-table v-if="shares.length">
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
          <div v-else class="text-grey">Нет доступных шар.</div>
        </q-tab-panel>

        <q-tab-panel name="scripts">
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
                  <q-btn
                    flat
                    dense
                    icon="content_copy"
                    label="Копировать"
                    class="q-mt-sm"
                    @click="copyToClipboard(mountScript.linux_script)"
                  />
                </q-tab-panel>
                <q-tab-panel name="windows">
                  <q-input
                    v-model="mountScript.windows_script"
                    type="textarea"
                    readonly
                    filled
                    rows="10"
                  />
                  <q-btn
                    flat
                    dense
                    icon="content_copy"
                    label="Копировать"
                    class="q-mt-sm"
                    @click="copyToClipboard(mountScript.windows_script)"
                  />
                </q-tab-panel>
              </q-tab-panels>
            </q-card-section>
          </q-card>
        </q-tab-panel>
      </q-tab-panels>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { api } from '@/api';
import type { ShareOutMe, MountScriptResponse } from '@/api/types';

const loading = ref(true);
const error = ref(false);
const tab = ref('shares');
const manualTab = ref('linux');
const shares = ref<ShareOutMe[]>([]);
const mountScript = ref<MountScriptResponse>({
  username: '',
  host: '',
  port: 445,
  shares: [],
  linux_script: '',
  windows_script: '',
});

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

- [ ] **Step 2: Verify typecheck**

Run: `yarn typecheck`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add 'web-ui/src/pages/index/(index).vue'
git commit -m "feat(ui): home page with shares and scripts tabs"
```

---

### Task 6: Final verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Prepare + typecheck**

Run: `npx quasar prepare && yarn typecheck`
Expected: both exit 0 (no errors).

- [ ] **Step 2: Production build (do not start the dev server)**

Run: `yarn build`
Expected: `quasar build` completes and writes `web-ui/dist/spa` with no errors. The router builds with `//admin` parent route and `/admin/*` children.

- [ ] **Step 3: Commit any regenerated artifacts**

```bash
git status --short
```

If `web-ui/src/router/typed-router.d.ts` or `web-ui/.quasar/**` changed and is tracked, stage and commit:

```bash
git add web-ui/src/router/typed-router.d.ts
git commit -m "chore(ui): regenerate typed router"
```

(Commit only if there are staged changes.)

---

## Spec Coverage Check (self-review)

- Regular user: no sidebar → Task 2 (MainLayout) ✓
- One home page with two tabs → Task 5 ✓
- Profile via user menu → `UserMenu.vue` in Task 1, `/profile` untouched ✓
- Title click → `/` → both layouts ✓
- Admin: "АДМИНКА" entry in user menu → Task 1 (`UserMenu.vue`) ✓
- Separate admin layout with sidebar → Task 3 ✓
- Hamburger only on mobile; drawer overlays content (not shifting) → Task 3 (`q-drawer behavior="mobile"`) ✓
- Drawer must not stick to viewport edge on desktop; UI stays centered with inline aside → Task 3 (desktop `<aside>` inside `.page-box`) ✓
- Users table hides Created on mobile → Task 4 ✓
- Shares table hides Comment on mobile → Task 4 ✓
- System cards 1/row, Dashboard cards 2/row on mobile → Task 4 (media queries) ✓
- Build-only testing → Task 6 ✓