<template>
  <q-page class="q-pa-md1">
<!--    <div class="text-h5 q-mb-md">Мои шары</div>-->

    <div v-if="loading" class="text-grey">Загрузка…</div>
    <div v-else-if="error" class="text-negative q-mb-md">
      Ошибка загрузки. <q-btn flat dense label="Повторить" @click="load" />
    </div>

    <template v-else>
      <q-tabs
        v-model="tab"
        dense
        inline-label
        active-color="primary"
        indicator-color="primary"
        align="left"
        :breakpoint="0"
        class="text-primary q-mb-md "
      >
        <q-tab name="shares" label="Shared Paths" icon="folder_shared" />
        <q-tab name="scripts" label="Scripts" icon="terminal" />
      </q-tabs>

      <q-tab-panels v-model="tab" animated>
        <q-tab-panel name="shares">
          <q-markup-table v-if="shares.length">
            <thead>
              <tr>
                <th class="text-left">Name</th>
                <th class="text-left">Host</th>
                <th class="text-right">Port</th>
                <th class="text-right">Access</th>
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
          <div v-else class="text-grey">Empty</div>
        </q-tab-panel>

        <q-tab-panel name="scripts">
          <!-- Скрипт mount -->
          <q-card flat bordered class="q-mb-lg">
            <q-card-section>
              <div class="text-h6">Mount Script</div>
            </q-card-section>
            <q-separator inset />
            <q-card-section class="q-gutter-y-sm">
              <p class="q-mb-none">
                <code>nasmount</code> is a single-file cross-platform helper that mounts your
                shared paths. It needs only Python 3, has no dependencies, and works on Linux,
                macOS and Windows. Tokens and settings are stored in
                <code>~/.config/nasmanager/config.json</code>.
              </p>
              <pre class="usage-pre"><code># Quick start
python3 mount-share.py auth      # log in, store tokens
python3 mount-share.py mount     # mount all shares (sudo on Linux/macOS)
python3 mount-share.py umount    # unmount shares from this NAS
python3 mount-share.py status    # list shares with mount status
python3 mount-share.py config    # show config / set --root PATH or --url URL</code></pre>
              <p class="text-caption text-grey q-mb-none">
                <code>mount</code> and <code>umount</code> accept share names, e.g.
                <code>mount-share.py mount photos</code>.
              </p>
            </q-card-section>
            <q-card-actions align="right">
              <q-btn
                color="primary"
                icon="download"
                label="Download script"
                :href="api.mountScriptUrl"
                download="mount-share.py"
              />
            </q-card-actions>
          </q-card>

          <!-- Ручное подключение -->
          <q-card flat bordered>
            <q-card-section>
              <div class="text-h6">Manually conenction</div>
            </q-card-section>
            <q-separator inset />
            <q-card-section>
              <q-tabs v-model="manualTab" class="text-primary" inline-label dense align="left">
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
                  <q-btn
                    flat
                    dense
                    icon="content_copy"
                    label="Копировать"
                    class="q-mt-sm"
                    @click="copyToClipboard(mountScript.linux_script)"
                  />
                </q-tab-panel>
                <q-tab-panel name="windows">
                  <q-input
                    v-model="mountScript.windows_script"
                    type="textarea"
                    readonly
                    filled
                    rows="10"
                  />
                  <q-btn
                    flat
                    dense
                    icon="content_copy"
                    label="Copy"
                    class="q-mt-sm"
                    @click="copyToClipboard(mountScript.windows_script)"
                  />
                </q-tab-panel>
              </q-tab-panels>
            </q-card-section>
          </q-card>
        </q-tab-panel>
      </q-tab-panels>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { api } from '@/api';
import type { ShareOutMe, MountScriptResponse } from '@/api/types';

const loading = ref(true);
const error = ref(false);
const tab = ref('shares');
const manualTab = ref('linux');
const shares = ref<ShareOutMe[]>([]);
const mountScript = ref<MountScriptResponse>({
  username: '',
  host: '',
  port: 445,
  shares: [],
  linux_script: '',
  windows_script: '',
});

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

<style scoped>
.usage-pre {
  margin: 0;
  padding: 12px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.05);
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.6;
}
</style>
