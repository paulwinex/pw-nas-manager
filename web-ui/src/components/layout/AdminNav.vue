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