<template>
  <q-layout view="hHh lpR lFf">
    <q-header class="bg-primary text-white">
      <div class="page-box">
        <q-toolbar>
          <q-btn flat round dense icon="menu" aria-label="Menu" @click="leftOpen = !leftOpen" />
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
      </div>
    </q-header>

    <q-page-container>
      <div class="page-box page-flex q-py-md">
        <aside v-show="leftOpen" class="page-sidebar">
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
        </aside>
        <main class="page-content" style="min-width: 0">
          <router-view />
        </main>
      </div>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();
const leftOpen = ref(true);

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

function measure() {
  if (window.innerWidth < 1024) leftOpen.value = false;
}

onMounted(() => {
  measure();
  window.addEventListener('resize', measure);
});

onUnmounted(() => {
  window.removeEventListener('resize', measure);
});

function logout() {
  auth.logout();
  router.push('/login');
}
</script>
