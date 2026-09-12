<template>
  <q-page class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div class="text-h5">Dashboard</div>
      <q-btn flat round icon="refresh" @click="load" :loading="loading" />
    </div>

    <template v-if="stats">
      <div class="row q-col-gutter-md">
        <q-card v-for="c in cards" :key="c.label" class="col-xs-6 col-md-4 col-xl-2">
          <q-card-section class="text-center">
            <q-icon :name="c.icon" :color="c.color" size="34px" />
            <div class="text-h5 q-mt-xs">{{ c.value }}</div>
            <div class="text-caption text-grey">{{ c.label }}</div>
          </q-card-section>
        </q-card>
      </div>

      <q-card class="q-mt-md">
        <q-card-section>
          <div class="text-subtitle1">Expiring memberships (next 7 days)</div>
        </q-card-section>
        <q-card-section v-if="stats.expiring_memberships.length === 0" class="text-grey">
          None
        </q-card-section>
        <q-markup-table v-else>
          <thead>
            <tr>
              <th class="text-left">User</th>
              <th class="text-left">Group</th>
              <th class="text-right">Access</th>
              <th class="text-right">Expires</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(m, i) in stats.expiring_memberships" :key="i">
              <td class="text-left">{{ m.username }}</td>
              <td class="text-left">{{ m.group_name }}</td>
              <td class="text-right">
                <q-badge
                  :color="m.access_level === 'rw' ? 'teal' : 'blue-grey'"
                  :label="m.access_level.toUpperCase()"
                />
              </td>
              <td class="text-right">{{ formatDate(m.expires_at) }}</td>
            </tr>
          </tbody>
        </q-markup-table>
      </q-card>

      <q-card class="q-mt-md">
        <q-card-section>
          <div class="text-subtitle1">API status</div>
        </q-card-section>
        <q-card-section class="row items-center q-col-gutter-md">
          <q-badge :color="health === 'ok' ? 'positive' : 'negative'">
            {{ health ?? 'unknown' }}
          </q-badge>
          <span class="text-grey">Registry: {{ stats.registry_shares_count }} shares</span>
        </q-card-section>
      </q-card>
    </template>
    <div v-else class="text-grey">Loading…</div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { date } from 'quasar';
import { api } from '@/api';
import type { StatsResponse } from '@/api/types';

const loading = ref(false);
const stats = ref<StatsResponse | null>(null);
const health = ref<string | null>(null);

const cards = computed(() => {
  if (!stats.value) return [];
  const s = stats.value;
  return [
    { label: 'Users', icon: 'people', color: 'primary', value: s.users_count },
    { label: 'Admins', icon: 'admin_panel_settings', color: 'orange', value: s.admins_count },
    { label: 'Groups', icon: 'groups', color: 'secondary', value: s.groups_count },
    { label: 'Shares', icon: 'folder_shared', color: 'teal', value: s.shares_count },
    { label: 'Registry', icon: 'dns', color: 'indigo', value: s.registry_shares_count },
    { label: 'Memberships', icon: 'link', color: 'blue-grey', value: s.memberships_count },
  ];
});

async function load() {
  loading.value = true;
  try {
    const [s, h] = await Promise.all([api.stats(), api.health()]);
    stats.value = s.data;
    health.value = h.data.status;
  } finally {
    loading.value = false;
  }
}

function formatDate(value: string) {
  return date.formatDate(value, 'YYYY-MM-DD HH:mm');
}

onMounted(load);
</script>