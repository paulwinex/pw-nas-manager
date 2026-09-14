<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Мои шары</div>

    <div v-if="loading" class="text-grey">Загрузка…</div>
    <div v-else-if="error" class="text-negative q-mb-md">
      Ошибка загрузки. <q-btn flat dense label="Повторить" @click="load" />
    </div>

    <template v-else>
      <!-- Список шар -->
      <q-markup-table v-if="shares.length" class="q-mb-lg">
        <thead>
          <tr>
            <th class="text-left">Имя</th>
            <th class="text-left">Хост</th>
            <th class="text-right">Порт</th>
            <th class="text-right">Доступ</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in shares" :key="s.name">
            <td>{{ s.name }}</td>
            <td>{{ s.host }}</td>
            <td class="text-right">{{ s.port }}</td>
            <td class="text-right">
              <q-badge :color="s.access === 'RW' ? 'teal' : 'blue-grey'" :label="s.access" />
            </td>
          </tr>
        </tbody>
      </q-markup-table>
      <div v-else class="text-grey q-mb-lg">Нет доступных шар.</div>

      <!-- Скачать CLI -->
      <q-card flat bordered class="q-mb-lg">
        <q-card-section>
          <div class="text-h6">CLI-утилита</div>
        </q-card-section>
        <q-separator inset />
        <q-card-section class="row q-gutter-sm">
          <q-btn
            color="primary"
            icon="download"
            label="Скачать nasmanager (Linux)"
            :href="`/api/v1/users/me/cli?os=linux`"
          />
          <q-btn
            color="primary"
            icon="download"
            label="Скачать nasmanager (Windows)"
            :href="`/api/v1/users/me/cli?os=windows`"
          />
        </q-card-section>
      </q-card>

      <!-- Ручное подключение -->
      <q-card flat bordered>
        <q-card-section>
          <div class="text-h6">Ручное подключение</div>
        </q-card-section>
        <q-separator inset />
        <q-card-section>
          <q-tabs v-model="manualTab" class="text-primary">
            <q-tab name="linux" label="Linux" />
            <q-tab name="windows" label="Windows" />
          </q-tabs>
          <q-tab-panels v-model="manualTab">
            <q-tab-panel name="linux">
              <q-input
                v-model="mountScript.linux_script"
                type="textarea"
                readonly
                filled
                rows="10"
              />
              <q-btn flat dense icon="content_copy" label="Копировать" class="q-mt-sm"
                     @click="copyToClipboard(mountScript.linux_script)" />
            </q-tab-panel>
            <q-tab-panel name="windows">
              <q-input
                v-model="mountScript.windows_script"
                type="textarea"
                readonly
                filled
                rows="10"
              />
              <q-btn flat dense icon="content_copy" label="Копировать" class="q-mt-sm"
                     @click="copyToClipboard(mountScript.windows_script)" />
            </q-tab-panel>
          </q-tab-panels>
        </q-card-section>
      </q-card>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { api } from '@/api';
import type { ShareOutMe, MountScriptResponse } from '@/api/types';

const loading = ref(true);
const error = ref(false);
const shares = ref<ShareOutMe[]>([]);
const mountScript = ref<MountScriptResponse>({
  username: '',
  host: '',
  port: 445,
  shares: [],
  linux_script: '',
  windows_script: '',
});
const manualTab = ref('linux');

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text);
}

async function load() {
  loading.value = true;
  error.value = false;
  try {
    const [sharesResp, scriptResp] = await Promise.all([
      api.meShares(),
      api.meMountScript(),
    ]);
    shares.value = sharesResp.data;
    mountScript.value = scriptResp.data;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>