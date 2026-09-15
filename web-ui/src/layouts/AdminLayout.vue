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
