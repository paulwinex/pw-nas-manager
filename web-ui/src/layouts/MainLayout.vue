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