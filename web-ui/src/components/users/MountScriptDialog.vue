<template>
  <q-dialog
    :model-value="modelValue"
    @update:model-value="(v: boolean) => emits('update:modelValue', v)"
    @hide="reset"
  >
    <q-card style="min-width: 640px; max-width: 95vw">
      <q-card-section>
        <div class="text-subtitle1">Mount script for {{ user?.username }}</div>
      </q-card-section>

      <q-card-section v-if="!result">
        <q-input v-model="password" label="User password" type="password" outlined autofocus />
        <q-btn label="Generate" color="primary" class="q-mt-md" :loading="loading" @click="generate" />
        <div v-if="error" class="text-negative q-mt-sm">{{ error }}</div>
      </q-card-section>

      <template v-else>
        <q-card-section class="q-gutter-sm">
          <q-badge
            v-for="s in result.shares"
            :key="s.name"
            color="teal"
            :label="`${s.name} (${s.path} · ${s.access})`"
          />
        </q-card-section>
        <q-card-section>
          <div class="text-subtitle2 q-mb-sm">Windows</div>
          <q-input type="textarea" readonly :model-value="result.windows_script" rows="6" />
        </q-card-section>
        <q-card-section>
          <div class="text-subtitle2 q-mb-sm">Linux</div>
          <q-input type="textarea" readonly :model-value="result.linux_script" rows="8" />
        </q-card-section>
      </template>

      <q-card-actions align="right">
        <q-btn flat label="Close" v-close-popup @click="reset" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from '@/api';
import type { MountScriptResponse, UserOut } from '@/api/types';

const props = defineProps<{ modelValue: boolean; user: UserOut | null }>();
const emits = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>();

const $q = useQuasar();
const password = ref('');
const loading = ref(false);
const error = ref('');
const result = ref<MountScriptResponse | null>(null);

async function generate() {
  if (!props.user) return;
  loading.value = true;
  error.value = '';
  try {
    result.value = (await api.mountScript(props.user.username, password.value)).data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to generate script';
  } finally {
    loading.value = false;
  }
}

function reset() {
  result.value = null;
  password.value = '';
  error.value = '';
}
</script>
