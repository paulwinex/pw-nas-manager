<template>
  <q-dialog
    :model-value="modelValue"
    @update:model-value="(v: boolean) => emits('update:modelValue', v)"
  >
    <q-card
      style="min-width: 560px; max-width: 90vw; max-height: 90vh"
      class="column no-wrap"
    >
      <q-card-section>
        <div class="text-subtitle1">Shares of {{ group?.name }}</div>
      </q-card-section>

      <q-card-section class="q-py-sm">
        <q-input
          v-model="filter"
          dense
          clearable
          debounce="150"
          placeholder="Filter by name or path"
        >
          <template v-slot:prepend>
            <q-icon name="search" />
          </template>
        </q-input>
      </q-card-section>

      <q-card-section class="col scroll">
        <q-table
          :rows="filteredShares"
          :columns="columns"
          row-key="id"
          flat
          hide-bottom
          dense
          :loading="loading"
          :pagination="{ rowsPerPage: 0 }"
        >
          <template v-slot:body-cell-name="cell">
            <q-td :props="cell">
              <div>{{ cell.value }}</div>
              <div class="text-caption text-grey">{{ cell.row.path }}</div>
            </q-td>
          </template>
          <template v-slot:body-cell-linked="cell">
            <q-td :props="cell" class="text-right">
              <div class="row items-center no-wrap justify-end">
                <q-spinner
                  v-if="pending.has(cell.row.id)"
                  size="xs"
                  color="primary"
                  class="q-mr-sm"
                />
                <q-toggle
                  :model-value="linkedIds.has(cell.row.id)"
                  :disable="pending.has(cell.row.id)"
                  @update:model-value="toggle(cell.row)"
                />
              </div>
            </q-td>
          </template>
        </q-table>
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
const allShares = ref<ShareOut[]>([]);
const linked = ref<ShareOut[]>([]);
const filter = ref('');
const pending = ref(new Set<string>());
const loading = ref(false);

const columns = [
  { name: 'name', label: 'Share', field: 'name', align: 'left' as const, sortable: true },
  { name: 'linked', label: '', field: '', align: 'right' as const },
];

const linkedIds = computed(() => new Set(linked.value.map((s) => s.id)));

const filteredShares = computed(() => {
  const q = filter.value.trim().toLowerCase();
  if (!q) return allShares.value;
  return allShares.value.filter(
    (s) => s.name.toLowerCase().includes(q) || s.path.toLowerCase().includes(q)
  );
});

async function load() {
  if (!props.group) return;
  loading.value = true;
  try {
    const [all, groupShares] = await Promise.all([
      api.listShares(),
      api.listGroupShares(props.group.id),
    ]);
    allShares.value = all.data;
    linked.value = groupShares.data;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load shares' });
  } finally {
    loading.value = false;
  }
}

async function toggle(share: ShareOut) {
  if (!props.group || pending.value.has(share.id)) return;
  const isLinkedNow = linkedIds.value.has(share.id);
  pending.value.add(share.id);
  try {
    if (isLinkedNow) {
      await api.unlinkShare(props.group.id, share.id);
      linked.value = linked.value.filter((s) => s.id !== share.id);
      $q.notify({ type: 'positive', message: 'Share unlinked' });
    } else {
      await api.linkShare(props.group.id, share.id);
      linked.value.push(share);
      $q.notify({ type: 'positive', message: 'Share linked' });
    }
  } catch (e: any) {
    $q.notify({
      type: 'negative',
      message: e?.response?.data?.detail ?? (isLinkedNow ? 'Failed to unlink share' : 'Failed to link share'),
    });
  } finally {
    pending.value.delete(share.id);
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) load();
  }
);
</script>
