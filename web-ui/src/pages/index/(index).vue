<template>
  <q-page class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div class="text-h5">Dashboard</div>
      <q-btn flat round icon="refresh" @click="load" :loading="loading" />
    </div>

    <div v-if="failed" class="text-negative row items-center q-gutter-sm q-mb-md">
      <span>Failed to load dashboard data.</span>
      <q-btn flat dense color="negative" label="Retry" @click="load" :loading="loading" />
    </div>

    <template v-if="stats">
      <div class="dash-grid">
        <q-card v-for="c in cards" :key="c.label" flat bordered class="dash-card">
          <q-card-section>
            <div class="text-h6">{{ c.label }}</div>
          </q-card-section>
          <q-separator inset />
          <q-card-section class="q-pt-none row items-center">
            <q-icon :name="c.icon" :color="c.color" size="32px" class="q-mr-sm" />
            <span class="text-h4">{{ c.value }}</span>
          </q-card-section>
        </q-card>
      </div>

      <q-card flat bordered class="dash-card dash-card--full">
        <q-card-section>
          <div class="text-h6">Expiring memberships (next 7 days)</div>
        </q-card-section>
        <q-separator inset />
        <q-card-section v-if="stats.expiring_memberships.length === 0" class="q-pt-none text-grey">
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
              <td class="text-right">{{ formatDateTime(m.expires_at) }}</td>
            </tr>
          </tbody>
        </q-markup-table>
      </q-card>

      <q-card flat bordered class="dash-card--full">
        <q-card-section>
          <div class="text-h6">API status</div>
        </q-card-section>
        <q-separator inset />
        <q-card-section class="q-pt-none row items-center q-col-gutter-md">
          <q-badge :color="health === 'ok' ? 'positive' : 'negative'">
            {{ health ?? 'unknown' }}
          </q-badge>
          <span class="text-grey">Registry: {{ stats.registry_shares_count }} shares</span>
        </q-card-section>
      </q-card>
    </template>
    <div v-else-if="!failed" class="text-grey">Loading…</div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { api } from '@/api';
import { formatDateTime } from '@/utils/dates';
import type { StatsResponse } from '@/api/types';

const loading = ref(false);
const stats = ref<StatsResponse | null>(null);
const health = ref<string | null>(null);
const failed = ref(false);

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
  failed.value = false;
  try {
    const [s, h] = await Promise.all([api.stats(), api.health()]);
    stats.value = s.data;
    health.value = h.data.status;
  } catch {
    failed.value = true;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>
