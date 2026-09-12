<template>
  <q-page class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div class="text-h5">Shares</div>
      <q-btn label="Create share" icon="add" color="primary" @click="createOpen = true" />
    </div>

    <q-table :rows="shares" :columns="columns" row-key="id" :loading="loading" flat bordered>
      <template v-slot:body-cell-actions="cell">
        <q-td :props="cell" class="text-right">
          <q-btn
            flat
            round
            dense
            icon="delete"
            color="negative"
            title="Delete"
            @click="confirmDelete(cell.row)"
          />
        </q-td>
      </template>
      <template v-slot:no-data>
        <span class="text-grey">No shares</span>
      </template>
    </q-table>

    <q-dialog v-model="createOpen">
      <q-card style="min-width: 400px">
        <q-card-section>
          <div class="text-subtitle1">Create share</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="form.name" label="Name" hint="lowercase letters, digits, - _" />
          <div class="text-caption text-grey">
            Available paths on the server:
            <span v-if="dirs.length === 0" class="text-grey">(none detected)</span>
          </div>
          <q-chip
            v-for="d in dirs"
            :key="d"
            dense
            size="sm"
            :label="d"
            clickable
            @click="form.name = d"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn label="Create" color="primary" :loading="creating" :disable="!form.name" @click="createShare" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="deleteOpen">
      <q-card>
        <q-card-section class="text-h6">Delete {{ deleteTarget?.name }}?</q-card-section>
        <q-card-section class="text-grey">
          The share directory is kept on disk; it is removed from the Samba registry.
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup @click="deleteOpen = false" />
          <q-btn label="Delete" color="negative" :loading="deleting" @click="doDelete" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from '@/api';
import type { ShareOut } from '@/api/types';

const $q = useQuasar();
const shares = ref<ShareOut[]>([]);
const dirs = ref<string[]>([]);
const loading = ref(false);

const createOpen = ref(false);
const form = ref({ name: '' });
const creating = ref(false);

const deleteOpen = ref(false);
const deleteTarget = ref<ShareOut | null>(null);
const deleting = ref(false);

const columns = [
  { name: 'name', label: 'Name', field: 'name', align: 'left' as const },
  { name: 'path', label: 'Path', field: 'path', align: 'left' as const },
  { name: 'actions', label: '', field: '', align: 'right' as const },
];

async function load() {
  loading.value = true;
  try {
    shares.value = (await api.listShares()).data;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load shares' });
  } finally {
    loading.value = false;
  }
}

async function loadDirs() {
  try {
    dirs.value = (await api.availableDirs()).data;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load available paths' });
  }
}

async function createShare() {
  creating.value = true;
  try {
    await api.createShare(form.value.name);
    createOpen.value = false;
    form.value.name = '';
    $q.notify({ type: 'positive', message: 'Share created' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to create share' });
  } finally {
    creating.value = false;
  }
  await load();
}

function confirmDelete(share: ShareOut) {
  deleteTarget.value = share;
  deleteOpen.value = true;
}

async function doDelete() {
  if (!deleteTarget.value) return;
  deleting.value = true;
  try {
    await api.deleteShare(deleteTarget.value.id);
    deleteOpen.value = false;
    $q.notify({ type: 'positive', message: 'Share deleted' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to delete share' });
  } finally {
    deleting.value = false;
  }
  await load();
}

onMounted(async () => {
  await Promise.all([load(), loadDirs()]);
});
</script>