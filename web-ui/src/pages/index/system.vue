<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">System</div>

    <div class="dash-grid">
      <q-card flat bordered class="dash-card-half">
        <q-card-section class="row items-center justify-between q-pb-sm">
          <div class="text-h6">NAS host</div>
          <q-btn flat round dense icon="refresh" @click="loadConfig" :loading="configLoading" />
        </q-card-section>
        <q-separator inset />
        <q-card-section class="q-pt-none">
          <code class="text-subtitle2">
            {{ nasHost ? `${nasHost}:${nasPort}` : 'unknown' }}
          </code>
          <div class="text-caption text-grey q-mt-xs">
            Set via NAS_HOST / NAS_PORT in .env (read-only)
          </div>
        </q-card-section>
      </q-card>

      <q-card flat bordered class="dash-card-half">
        <q-card-section class="row items-center justify-between q-pb-sm">
          <div class="text-h6">API health</div>
          <q-btn flat round dense icon="refresh" @click="loadHealth" :loading="healthLoading" />
        </q-card-section>
        <q-separator inset />
        <q-card-section class="q-pt-none">
          <q-badge :color="health === 'ok' ? 'positive' : 'negative'">
            {{ health ?? 'unknown' }}
          </q-badge>
        </q-card-section>
      </q-card>

      <q-card flat bordered class="dash-card-half">
        <q-card-section>
          <div class="text-h6">Registry sync</div>
        </q-card-section>
        <q-separator inset />
        <q-card-section class="q-pt-sm">
          <q-btn label="Sync now" icon="sync" color="primary" :loading="syncing" @click="runSync" />
          <pre v-if="syncReport" class="q-mt-sm">{{ JSON.stringify(syncReport, null, 2) }}</pre>
        </q-card-section>
      </q-card>

      <q-card flat bordered class="dash-card-half">
        <q-card-section>
          <div class="text-h6">Membership sweep</div>
        </q-card-section>
        <q-separator inset />
        <q-card-section class="q-pt-sm">
          <q-btn
            label="Sweep now"
            icon="cleaning_services"
            color="primary"
            :loading="sweeping"
            @click="runSweep"
          />
          <div v-if="sweepResult" class="q-mt-sm text-grey">
            Processed: {{ sweepResult.processed }}
          </div>
          <pre v-if="sweepResult?.sync" class="q-mt-sm">
            {{ JSON.stringify(sweepResult.sync, null, 2) }}
          </pre>
        </q-card-section>
      </q-card>
    </div>

    <q-card flat bordered class="q-mt-md">
      <q-card-section class="row items-center justify-between q-pb-sm">
        <div class="text-h6">Samba registry</div>
        <q-btn flat round icon="refresh" @click="loadRegistry" :loading="registryLoading" />
      </q-card-section>
      <q-separator inset />
      <q-card-section class="q-pt-none">
        <pre>{{ JSON.stringify(registry, null, 2) }}</pre>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from '@/api';
import type { RegistryState, SyncReport } from '@/api/types';

const $q = useQuasar();
const health = ref<string | null>(null);
const healthLoading = ref(false);
const nasHost = ref<string | null>(null);
const nasPort = ref<number | null>(null);
const configLoading = ref(false);
const syncing = ref(false);
const syncReport = ref<SyncReport | null>(null);
const sweeping = ref(false);
const sweepResult = ref<{ processed: number; sync: SyncReport | null } | null>(null);
const registry = ref<RegistryState>({});
const registryLoading = ref(false);

async function loadHealth() {
  healthLoading.value = true;
  try {
    health.value = (await api.health()).data.status;
  } catch (e: any) {
    health.value = null;
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load health' });
  } finally {
    healthLoading.value = false;
  }
}

async function loadConfig() {
  configLoading.value = true;
  try {
    const data = (await api.config()).data;
    nasHost.value = data.nas_host;
    nasPort.value = data.nas_port;
  } catch (e: any) {
    nasHost.value = null;
    nasPort.value = null;
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load config' });
  } finally {
    configLoading.value = false;
  }
}

async function runSync() {
  syncing.value = true;
  try {
    syncReport.value = (await api.sync()).data;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Sync failed' });
  } finally {
    syncing.value = false;
  }
}

async function runSweep() {
  sweeping.value = true;
  try {
    sweepResult.value = (await api.sweep()).data;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Sweep failed' });
  } finally {
    sweeping.value = false;
  }
}

async function loadRegistry() {
  registryLoading.value = true;
  try {
    registry.value = (await api.registry()).data;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load registry' });
  } finally {
    registryLoading.value = false;
  }
}

onMounted(async () => {
  await Promise.all([loadHealth(), loadConfig(), loadRegistry()]);
});
</script>
