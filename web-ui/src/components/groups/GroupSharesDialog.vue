<template>
  <q-dialog
    :model-value="modelValue"
    @update:model-value="(v: boolean) => emits('update:modelValue', v)"
  >
    <q-card style="min-width: 560px; max-width: 90vw">
      <q-card-section>
        <div class="text-subtitle1">Shares of {{ group?.name }}</div>
      </q-card-section>

      <q-card-section>
        <q-table
          :rows="shares"
          :columns="columns"
          row-key="id"
          flat
          hide-bottom
          dense
          :loading="loading"
        >
          <template v-slot:body-cell-name="cell">
            <q-td :props="cell">
              <div>{{ cell.value }}</div>
              <div class="text-caption text-grey">{{ cell.row.path }}</div>
            </q-td>
          </template>
          <template v-slot:body-cell-actions="cell">
            <q-td :props="cell" class="text-right">
              <q-btn
                flat
                dense
                round
                icon="link_off"
                color="negative"
                title="Unlink"
                @click="unlink(cell.row)"
              />
            </q-td>
          </template>
        </q-table>
      </q-card-section>

      <q-card-section>
        <div class="text-subtitle2 q-mb-sm">Link share</div>
        <div class="row q-col-gutter-sm items-end">
          <q-select
            class="col-8"
            v-model="form.share_id"
            :options="availableShares"
            option-label="name"
            option-value="id"
            emit-value
            map-options
            label="Share"
            outlined
            dense
          />
          <div class="col-4">
            <q-btn
              label="Link"
              color="primary"
              :loading="linking"
              :disable="!form.share_id"
              @click="link"
            />
          </div>
        </div>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat label="Close" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import { api } from '@/api';
import type { GroupOut, ShareOut } from '@/api/types';

const props = defineProps<{ modelValue: boolean; group: GroupOut | null }>();
const emits = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>();

const $q = useQuasar();
const shares = ref<ShareOut[]>([]);
const allShares = ref<ShareOut[]>([]);
const loading = ref(false);
const linking = ref(false);
const form = ref<{ share_id: string | null }>({ share_id: null });

const columns = [
  { name: 'name', label: 'Share', field: 'name', align: 'left' as const },
  { name: 'actions', label: '', field: '', align: 'right' as const },
];

const availableShares = computed(() =>
  allShares.value.filter((s) => !shares.value.some((x) => x.id === s.id))
);

async function load() {
  if (!props.group) return;
  loading.value = true;
  try {
    const [all, linked] = await Promise.all([
      api.listShares(),
      api.listGroupShares(props.group.id),
    ]);
    allShares.value = all.data;
    shares.value = linked.data;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load shares' });
  } finally {
    loading.value = false;
  }
}

async function link() {
  if (!props.group || !form.value.share_id) return;
  linking.value = true;
  try {
    await api.linkShare(props.group.id, form.value.share_id);
    form.value.share_id = null;
    $q.notify({ type: 'positive', message: 'Share linked' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to link share' });
  } finally {
    linking.value = false;
  }
  await load();
}

async function unlink(share: ShareOut) {
  if (!props.group) return;
  try {
    await api.unlinkShare(props.group.id, share.id);
    $q.notify({ type: 'positive', message: 'Share unlinked' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to unlink share' });
  }
  await load();
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) load();
  }
);
</script>