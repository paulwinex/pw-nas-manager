<template>
  <q-btn-dropdown flat no-caps :label="auth.username || 'Account'" icon="person">
    <q-list style="min-width: 200px">
      <q-item clickable v-close-popup to="/profile">
        <q-item-section avatar>
          <q-icon name="account_circle" />
        </q-item-section>
        <q-item-section>Profile</q-item-section>
      </q-item>
      <q-item v-if="auth.isAdmin && !inAdminArea" clickable v-close-popup to="/admin">
        <q-item-section avatar>
          <q-icon name="admin_panel_settings" />
        </q-item-section>
        <q-item-section>Admin Panel</q-item-section>
      </q-item>
      <q-item v-if="auth.isAdmin && inAdminArea" clickable v-close-popup to="/">
        <q-item-section avatar>
          <q-icon name="home" />
        </q-item-section>
        <q-item-section>Home</q-item-section>
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
