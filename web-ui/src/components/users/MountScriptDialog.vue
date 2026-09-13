<template>
  <q-dialog
    :model-value="modelValue"
    @update:model-value="(v: boolean) => emits('update:modelValue', v)"
    @hide="reset"
  >
    <q-card style="min-width: 720px; max-width: 95vw">
      <q-card-section>
        <div class="text-subtitle1">Mount script for {{ user?.username }}</div>
      </q-card-section>

      <q-card-section v-if="loading" class="text-grey">Loading…</q-card-section>

      <template v-else-if="result">
        <q-card-section v-if="result.shares.length === 0" class="text-negative text-body2">
          No shares are available for {{ user?.username }}
        </q-card-section>

        <template v-else>
          <q-card-section class="q-pt-none q-gutter-sm">
            <q-badge
              v-for="s in result.shares"
              :key="s.name"
              color="teal"
              :label="`${s.name} (${s.path} · ${s.access})`"
            />
          </q-card-section>

          <q-tabs v-model="tab" dense align="left" class="q-px-sm">
            <q-tab name="linux" label="Linux" />
            <q-tab name="windows" label="Windows" />
          </q-tabs>

          <q-tab-panels v-model="tab" animated>
            <q-tab-panel name="linux">
              <div class="row justify-end q-mb-xs">
                <q-btn
                  flat
                  dense
                  round
                  icon="content_copy"
                  title="Copy"
                  @click="copy(result.linux_script)"
                />
              </div>
              <pre class="script-box"><code>{{ result.linux_script }}</code></pre>
            </q-tab-panel>
            <q-tab-panel name="windows">
              <div class="row justify-end q-mb-xs">
                <q-btn
                  flat
                  dense
                  round
                  icon="content_copy"
                  title="Copy"
                  @click="copy(result.windows_script)"
                />
              </div>
              <pre class="script-box"><code>{{ result.windows_script }}</code></pre>
            </q-tab-panel>
          </q-tab-panels>
        </template>
      </template>

      <q-card-section v-else-if="error" class="text-negative">{{ error }}</q-card-section>

      <q-card-actions align="right">
        <q-btn flat label="Close" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import { api } from '@/api';
import type { MountScriptResponse, UserOut } from '@/api/types';

const props = defineProps<{ modelValue: boolean; user: UserOut | null }>();
const emits = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>();

const $q = useQuasar();
const loading = ref(false);
const error = ref('');
const result = ref<MountScriptResponse | null>(null);
const tab = ref('linux');

async function load() {
  if (!props.user) return;
  loading.value = true;
  error.value = '';
  try {
    result.value = (await api.mountScript(props.user.username)).data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'Failed to load mount script';
  } finally {
    loading.value = false;
  }
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    $q.notify({ type: 'positive', message: 'Copied to clipboard' });
  } catch {
    $q.notify({ type: 'negative', message: 'Copy failed' });
  }
}

function reset() {
  result.value = null;
  error.value = '';
  tab.value = 'linux';
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) load();
  }
);
</script>

<style scoped>
.script-box {
  background: rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.55;
}
</style>