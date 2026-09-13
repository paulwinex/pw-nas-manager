<template>
  <q-page class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div class="text-h5">Groups</div>
      <q-btn label="Create group" icon="add" color="primary" @click="createOpen = true" />
    </div>

    <q-table
      :rows="groups"
      :columns="columns"
      row-key="id"
      :loading="loadingGroups"
      flat
      bordered
    >
      <template v-slot:body-cell-is_personal="cell">
        <q-td :props="cell">
          <q-badge :color="cell.value ? 'purple' : 'blue-grey'" :label="cell.value ? 'personal' : 'group'" />
        </q-td>
      </template>
      <template v-slot:body-cell-actions="cell">
        <q-td :props="cell" class="text-right">
          <q-btn
            flat
            round
            dense
            icon="folder_shared"
            color="primary"
            title="Shares"
            @click="openShares(cell.row)"
          />
          <q-btn
            flat
            round
            dense
            icon="delete"
            color="negative"
            title="Delete"
            :disable="cell.row.is_personal"
            @click="confirmDelete(cell.row)"
          />
        </q-td>
      </template>
    </q-table>

    <q-dialog v-model="createOpen">
      <q-card style="min-width: 340px">
        <q-card-section>
          <div class="text-subtitle1">Create group</div>
        </q-card-section>
        <q-card-section>
          <q-input v-model="createForm.name" label="Name" hint="lowercase letters, digits, - _" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn label="Create" color="primary" :loading="createLoading" @click="createGroup" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="deleteOpen">
      <q-card>
        <q-card-section class="text-h6">Delete {{ deleteTarget?.name }}?</q-card-section>
        <q-card-section class="text-grey">
          This removes the group, its members and linked shares from the registry.
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup @click="deleteOpen = false" />
          <q-btn label="Delete" color="negative" :loading="deleteLoading" @click="doDelete" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <GroupSharesDialog v-model="sharesOpen" :group="sharesTarget" />
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from '@/api';
import type { GroupOut } from '@/api/types';
import GroupSharesDialog from '@/components/groups/GroupSharesDialog.vue';

const $q = useQuasar();
const groups = ref<GroupOut[]>([]);
const loadingGroups = ref(false);

const columns = [
  { name: 'name', label: 'Name', field: 'name', align: 'left' as const },
  { name: 'is_personal', label: 'Type', field: 'is_personal', align: 'left' as const },
  { name: 'actions', label: '', field: '', align: 'right' as const },
];

const createOpen = ref(false);
const createForm = ref({ name: '' });
const createLoading = ref(false);

const deleteOpen = ref(false);
const deleteTarget = ref<GroupOut | null>(null);
const deleteLoading = ref(false);

const sharesOpen = ref(false);
const sharesTarget = ref<GroupOut | null>(null);

async function loadGroups() {
  loadingGroups.value = true;
  try {
    groups.value = (await api.listGroups()).data;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load groups' });
  } finally {
    loadingGroups.value = false;
  }
}

async function createGroup() {
  createLoading.value = true;
  try {
    await api.createGroup(createForm.value.name);
    createOpen.value = false;
    createForm.value.name = '';
    $q.notify({ type: 'positive', message: 'Group created' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to create group' });
  } finally {
    createLoading.value = false;
  }
  await loadGroups();
}

function confirmDelete(group: GroupOut) {
  deleteTarget.value = group;
  deleteOpen.value = true;
}

async function doDelete() {
  if (!deleteTarget.value) return;
  deleteLoading.value = true;
  try {
    await api.deleteGroup(deleteTarget.value.id);
    deleteOpen.value = false;
    $q.notify({ type: 'positive', message: 'Group deleted' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to delete group' });
  } finally {
    deleteLoading.value = false;
  }
  await loadGroups();
}

function openShares(group: GroupOut) {
  sharesTarget.value = group;
  sharesOpen.value = true;
}

onMounted(loadGroups);
</script>