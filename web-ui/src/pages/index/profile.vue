<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Profile</div>

    <q-card class="q-mb-md">
      <q-card-section>
        <div class="row items-center q-col-gutter-md">
          <q-avatar color="primary" text-color="white" size="56px" icon="person" />
          <div>
            <div class="text-h6">{{ me?.username }}</div>
            <div class="text-caption text-grey">
              Administrator · created {{ me ? formatDate(me.created_at) : '…' }}
            </div>
          </div>
        </div>
      </q-card-section>
    </q-card>

    <q-card class="q-mb-md">
      <q-card-section>
        <div class="text-subtitle1">Appearance</div>
      </q-card-section>
      <q-card-section class="q-pt-none">
        <q-toggle :model-value="$q.dark.isActive" label="Dark theme" @update:model-value="(v: boolean) => toggleDark(v)" />
      </q-card-section>
    </q-card>

    <q-card>
      <q-card-section>
        <div class="text-subtitle1">Change password</div>
      </q-card-section>
      <q-card-section class="q-pt-none">
        <q-form @submit="changePassword">
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-4">
              <q-input v-model="pwd.new" label="New password" type="password" outlined />
            </div>
            <div class="col-12 col-md-4">
              <q-input
                v-model="pwd.confirm"
                label="Confirm"
                type="password"
                outlined
                :error="!!pwd.error"
                :error-message="pwd.error"
              />
            </div>
          </div>
          <q-btn label="Save" type="submit" color="primary" class="q-mt-md" :loading="saving" />
        </q-form>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from '@/api';
import { formatDateTime } from '@/utils/dates';
import type { UserOut } from '@/api/types';

const $q = useQuasar();
const me = ref<UserOut | null>(null);
const saving = ref(false);
const pwd = ref({ new: '', confirm: '', error: '' });

async function load() {
  try {
    me.value = (await api.me()).data;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load profile' });
  }
}

function formatDate(value: string) {
  return formatDateTime(value);
}

function toggleDark(value: boolean) {
  $q.dark.set(value);
  localStorage.setItem('nas.dark', value ? '1' : '0');
}

async function changePassword() {
  pwd.value.error = '';
  if (pwd.value.new !== pwd.value.confirm) {
    pwd.value.error = 'Passwords do not match';
    return;
  }
  if (!me.value) return;
  saving.value = true;
  try {
    await api.changeUserPassword(me.value.id, pwd.value.new);
    $q.notify({ type: 'positive', message: 'Password updated' });
    pwd.value.new = '';
    pwd.value.confirm = '';
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to update password' });
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>