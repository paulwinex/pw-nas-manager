<template>
  <q-page class="q-pa-md">
    <div class="row items-center justify-between q-mb-md">
      <div class="text-h5">Users</div>
      <q-btn label="Create user" icon="add" color="primary" @click="createOpen = true" />
    </div>

    <q-table :rows="users" :columns="columns" row-key="id" :loading="loading" flat bordered>
      <template v-slot:body-cell-is_admin="cell">
        <q-td :props="cell">
          <q-badge :color="cell.value ? 'orange' : 'blue-grey'" :label="cell.value ? 'admin' : 'user'" />
        </q-td>
      </template>
      <template v-slot:body-cell-created_at="cell">
        <q-td :props="cell">{{ formatDate(cell.value as string) }}</q-td>
      </template>
      <template v-slot:body-cell-actions="cell">
        <q-td :props="cell" class="text-right">
          <q-btn flat round dense icon="key" title="Set password" @click="openPassword(cell.row)" />
          <q-btn flat round dense icon="group_add" title="Groups" @click="openGroups(cell.row)" />
          <q-btn flat round dense icon="terminal" title="Mount script" @click="openMountScript(cell.row)" />
          <q-btn
            flat
            round
            dense
            icon="delete"
            color="negative"
            title="Delete"
            @click="openDelete(cell.row)"
          />
        </q-td>
      </template>
      <template v-slot:no-data>
        <span class="text-grey">No users</span>
      </template>
    </q-table>

    <q-dialog v-model="createOpen">
      <q-card style="min-width: 360px">
        <q-card-section>
          <div class="text-subtitle1">Create user</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input
            v-model="createForm.username"
            label="Username"
            hint="lowercase letters, digits, - _"
            :error="!!createError"
            :error-message="createError"
          />
          <q-input v-model="createForm.password" label="Password" type="password" />
          <q-toggle v-model="createForm.is_admin" label="Administrator" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn label="Create" color="primary" :loading="createLoading" @click="createUser" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="passwordOpen">
      <q-card style="min-width: 360px">
        <q-card-section>
          <div class="text-subtitle1">Set password for {{ selected?.username }}</div>
        </q-card-section>
        <q-card-section>
          <q-input v-model="passwordForm.new" label="New password" type="password" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn label="Save" color="primary" :loading="passwordLoading" @click="savePassword" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="deleteOpen">
      <q-card>
        <q-card-section class="text-h6">Delete {{ selected?.username }}?</q-card-section>
        <q-card-section class="text-grey">
          This removes the user and all memberships, and deletes the Samba account.
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn label="Delete" color="negative" :loading="deleteLoading" @click="deleteUser" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <UserGroupsDialog v-model="groupsOpen" :user="selected" />
    <MountScriptDialog v-model="mountOpen" :user="selected" />
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from '@/api';
import { formatDateTime } from '@/utils/dates';
import type { UserOut } from '@/api/types';
import UserGroupsDialog from '@/components/users/UserGroupsDialog.vue';
import MountScriptDialog from '@/components/users/MountScriptDialog.vue';

const $q = useQuasar();
const users = ref<UserOut[]>([]);
const loading = ref(false);
const selected = ref<UserOut | null>(null);

const columns = [
  { name: 'username', label: 'Username', field: 'username', align: 'left' as const },
  { name: 'is_admin', label: 'Role', field: 'is_admin', align: 'left' as const },
  { name: 'created_at', label: 'Created', field: 'created_at', align: 'left' as const },
  { name: 'actions', label: '', field: '', align: 'right' as const },
];

const createOpen = ref(false);
const createForm = ref({ username: '', password: '', is_admin: false });
const createError = ref('');
const createLoading = ref(false);

const passwordOpen = ref(false);
const passwordForm = ref({ new: '' });
const passwordLoading = ref(false);

const deleteOpen = ref(false);
const deleteLoading = ref(false);

const groupsOpen = ref(false);
const mountOpen = ref(false);

async function load() {
  loading.value = true;
  try {
    users.value = (await api.listUsers()).data;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load users' });
  } finally {
    loading.value = false;
  }
}

function formatDate(value: string) {
  return formatDateTime(value);
}

async function createUser() {
  createError.value = '';
  createLoading.value = true;
  try {
    await api.createUser(createForm.value);
    createOpen.value = false;
    createForm.value = { username: '', password: '', is_admin: false };
    $q.notify({ type: 'positive', message: 'User created' });
  } catch (e: any) {
    const detail = e?.response?.data?.detail;
    createError.value = Array.isArray(detail)
      ? detail.map((d: { msg: string }) => d.msg).join('; ')
      : (detail ?? 'Failed to create user');
  } finally {
    createLoading.value = false;
  }
  await load();
}

function openPassword(user: UserOut) {
  selected.value = user;
  passwordForm.value.new = '';
  passwordOpen.value = true;
}

async function savePassword() {
  if (!selected.value) return;
  passwordLoading.value = true;
  try {
    await api.changeUserPassword(selected.value.id, passwordForm.value.new);
    passwordOpen.value = false;
    $q.notify({ type: 'positive', message: 'Password updated' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to update password' });
  } finally {
    passwordLoading.value = false;
  }
}

function openDelete(user: UserOut) {
  selected.value = user;
  deleteOpen.value = true;
}

async function deleteUser() {
  if (!selected.value) return;
  deleteLoading.value = true;
  try {
    await api.deleteUser(selected.value.id);
    deleteOpen.value = false;
    $q.notify({ type: 'positive', message: 'User deleted' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to delete user' });
  } finally {
    deleteLoading.value = false;
  }
  await load();
}

function openGroups(user: UserOut) {
  selected.value = user;
  groupsOpen.value = true;
}

function openMountScript(user: UserOut) {
  selected.value = user;
  mountOpen.value = true;
}

onMounted(load);
</script>
