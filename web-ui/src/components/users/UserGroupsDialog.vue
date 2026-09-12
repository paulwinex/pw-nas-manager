<template>
  <q-dialog
    :model-value="modelValue"
    @update:model-value="(v: boolean) => emits('update:modelValue', v)"
  >
    <q-card style="min-width: 560px; max-width: 90vw">
      <q-card-section>
        <div class="text-subtitle1">Groups of {{ user?.username }}</div>
      </q-card-section>

      <q-card-section>
        <q-table
          :rows="memberships"
          :columns="columns"
          row-key="group_id"
          flat
          hide-bottom
          dense
          :loading="loading"
        >
          <template v-slot:body-cell-access_level="cell">
            <q-td :props="cell">
              <q-badge
                :color="cell.value === 'rw' ? 'teal' : 'blue-grey'"
                :label="String(cell.value).toUpperCase()"
              />
            </q-td>
          </template>
          <template v-slot:body-cell-expires_at="cell">
            <q-td :props="cell">{{ cell.value ? formatDate(cell.value as string) : '—' }}</q-td>
          </template>
          <template v-slot:body-cell-actions="cell">
            <q-td :props="cell" class="text-right">
              <q-btn
                flat
                dense
                round
                icon="remove_circle_outline"
                color="negative"
                title="Remove from group"
                @click="remove(cell.row)"
              />
            </q-td>
          </template>
        </q-table>
      </q-card-section>

      <q-card-section>
        <div class="text-subtitle2 q-mb-sm">Add to group</div>
        <div class="row q-col-gutter-sm items-end">
          <q-select
            class="col-4"
            v-model="form.group_id"
            :options="addableGroups"
            option-label="name"
            option-value="id"
            label="Group"
            outlined
            dense
          />
          <q-select
            class="col-3"
            v-model="form.access_level"
            :options="levels"
            label="Access"
            outlined
            dense
          />
          <q-input
            class="col-5"
            v-model="form.expires_at"
            type="datetime-local"
            label="Expires (optional)"
            outlined
            dense
            clearable
          />
          <div class="col-12 q-mt-sm">
            <q-btn
              label="Add"
              color="primary"
              :loading="adding"
              :disable="!form.group_id"
              @click="add"
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
import { formatDateTime } from '@/utils/dates';
import type { GroupOut, MemberOut, UserOut } from '@/api/types';

const props = defineProps<{ modelValue: boolean; user: UserOut | null }>();
const emits = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>();

type UserMembership = MemberOut & { group_name: string; group_id: string };

const $q = useQuasar();
const groups = ref<GroupOut[]>([]);
const memberships = ref<UserMembership[]>([]);
const loading = ref(false);
const adding = ref(false);
const form = ref<{ group_id: string | null; access_level: string; expires_at: string | null }>({
  group_id: null,
  access_level: 'ro',
  expires_at: null,
});
const levels = [
  { label: 'RO', value: 'ro' },
  { label: 'RW', value: 'rw' },
];
const columns = [
  { name: 'group_name', label: 'Group', field: 'group_name', align: 'left' as const },
  { name: 'access_level', label: 'Access', field: 'access_level', align: 'left' as const },
  { name: 'expires_at', label: 'Expires', field: 'expires_at', align: 'left' as const },
  { name: 'actions', label: '', field: '', align: 'right' as const },
];

const addableGroups = computed(() =>
  groups.value.filter(
    (g) => !g.is_personal && !memberships.value.some((m) => m.group_id === g.id)
  )
);

async function load() {
  if (!props.user) return;
  loading.value = true;
  try {
    groups.value = (await api.listGroups()).data;
    const rows: UserMembership[] = [];
    const uid = props.user.id;
    for (const g of groups.value) {
      const members = (await api.listMembers(g.id)).data;
      const mine = members.find((m) => m.user_id === uid);
      if (mine) rows.push({ ...mine, group_name: g.name, group_id: g.id });
    }
    memberships.value = rows;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load groups' });
  } finally {
    loading.value = false;
  }
}

function resetForm() {
  form.value.group_id = null;
  form.value.access_level = 'ro';
  form.value.expires_at = null;
}

async function add() {
  if (!props.user || !form.value.group_id) return;
  adding.value = true;
  try {
    await api.addMember(form.value.group_id, {
      user_id: props.user.id,
      access_level: form.value.access_level,
      expires_at: form.value.expires_at ? new Date(form.value.expires_at).toISOString() : null,
    });
    $q.notify({ type: 'positive', message: 'Added to group' });
    resetForm();
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to add' });
  } finally {
    adding.value = false;
  }
  await load();
}

async function remove(row: UserMembership) {
  try {
    await api.removeMember(row.group_id, row.user_id);
    $q.notify({ type: 'positive', message: 'Removed from group' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to remove' });
  }
  await load();
}

function formatDate(value: string) {
  return formatDateTime(value);
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) load();
  }
);
</script>
