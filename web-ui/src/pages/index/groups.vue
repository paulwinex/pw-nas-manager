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
      selection="single"
      :selected-rows="selected ? [selected.id] : []"
      @update:selected="onSelect"
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
            icon="delete"
            color="negative"
            title="Delete"
            :disable="cell.row.is_personal"
            @click="confirmDelete(cell.row)"
          />
        </q-td>
      </template>
    </q-table>

    <div v-if="selected" class="q-mt-lg">
      <div class="text-h6 q-mb-sm">Group: {{ selected.name }}</div>
      <div class="row q-col-gutter-md">
        <q-card class="col-12 col-md-6">
          <q-card-section>
            <div class="text-subtitle1">Members</div>
          </q-card-section>
          <q-card-section class="q-pt-none">
            <q-table
              :rows="members"
              :columns="memberColumns"
              row-key="user_id"
              flat
              hide-bottom
              dense
              :loading="loadingMembers"
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
                    @click="removeMember(cell.row)"
                  />
                </q-td>
              </template>
            </q-table>
            <div class="row q-col-gutter-sm items-end q-mt-md">
              <q-select
                class="col-5"
                v-model="memberForm.user_id"
                :options="availableUsers"
                option-label="username"
                option-value="id"
                label="User"
                outlined
                dense
              />
              <q-select
                class="col-3"
                v-model="memberForm.access_level"
                :options="levels"
                label="Access"
                outlined
                dense
              />
              <q-input
                class="col-4"
                v-model="memberForm.expires_at"
                type="datetime-local"
                label="Expires (optional)"
                outlined
                dense
                clearable
              />
              <div class="col-12 q-mt-sm">
                <q-btn
                  label="Add member"
                  color="primary"
                  :loading="addingMember"
                  :disable="!memberForm.user_id"
                  @click="addMember"
                />
              </div>
            </div>
          </q-card-section>
        </q-card>

        <q-card class="col-12 col-md-6">
          <q-card-section>
            <div class="text-subtitle1">Shares</div>
          </q-card-section>
          <q-card-section class="q-pt-none">
            <q-list bordered separator>
              <q-item v-for="s in groupShares" :key="s.id">
                <q-item-section>
                  <q-item-label>{{ s.name }}</q-item-label>
                  <q-item-label caption>{{ s.path }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-btn flat dense round icon="link_off" color="negative" @click="unlinkShare(s.id)" />
                </q-item-section>
              </q-item>
              <q-item v-if="groupShares.length === 0" class="text-grey">No shares linked</q-item>
            </q-list>
            <div class="row q-col-gutter-sm items-end q-mt-md">
              <q-select
                class="col-8"
                v-model="shareForm.share_id"
                :options="unlinkedShares"
                option-label="name"
                option-value="id"
                label="Share"
                outlined
                dense
              />
              <div class="col-4">
                <q-btn
                  label="Link"
                  color="primary"
                  :loading="linking"
                  :disable="!shareForm.share_id"
                  @click="linkShare(shareForm.share_id)"
                />
              </div>
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

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
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from '@/api';
import { formatDateTime } from '@/utils/dates';
import type { GroupOut, MemberOut, ShareOut, UserOut } from '@/api/types';

const $q = useQuasar();
const groups = ref<GroupOut[]>([]);
const users = ref<UserOut[]>([]);
const shares = ref<ShareOut[]>([]);
const loadingGroups = ref(false);
const selected = ref<GroupOut | null>(null);

const members = ref<MemberOut[]>([]);
const loadingMembers = ref(false);
const groupShares = ref<ShareOut[]>([]);

const createOpen = ref(false);
const createForm = ref({ name: '' });
const createLoading = ref(false);

const deleteOpen = ref(false);
const deleteTarget = ref<GroupOut | null>(null);
const deleteLoading = ref(false);

const memberForm = ref<{ user_id: string | null; access_level: string; expires_at: string | null }>({
  user_id: null,
  access_level: 'ro',
  expires_at: null,
});
const addingMember = ref(false);

const shareForm = ref<{ share_id: string | null }>({ share_id: null });
const linking = ref(false);

const levels = [
  { label: 'RO', value: 'ro' },
  { label: 'RW', value: 'rw' },
];

const columns = [
  { name: 'name', label: 'Name', field: 'name', align: 'left' as const },
  { name: 'is_personal', label: 'Type', field: 'is_personal', align: 'left' as const },
  { name: 'actions', label: '', field: '', align: 'right' as const },
];

const memberColumns = [
  { name: 'username', label: 'User', field: 'username', align: 'left' as const },
  { name: 'access_level', label: 'Access', field: 'access_level', align: 'left' as const },
  { name: 'expires_at', label: 'Expires', field: 'expires_at', align: 'left' as const },
  { name: 'actions', label: '', field: '', align: 'right' as const },
];

const availableUsers = computed(() =>
  users.value.filter((u) => !members.value.some((m) => m.user_id === u.id))
);

const unlinkedShares = computed(() =>
  shares.value.filter((s) => !groupShares.value.some((gs) => gs.id === s.id))
);

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

async function loadUsers() {
  users.value = (await api.listUsers()).data;
}

async function loadShares() {
  shares.value = (await api.listShares()).data;
}

async function onSelect(rows: readonly GroupOut[]) {
  selected.value = rows[0] ?? null;
  if (selected.value) {
    await loadGroupDetail(selected.value.id);
  }
}

async function loadGroupDetail(groupId: string) {
  loadingMembers.value = true;
  try {
    const [m, s] = await Promise.all([api.listMembers(groupId), api.listGroupShares(groupId)]);
    members.value = m.data;
    groupShares.value = s.data;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to load group detail' });
  } finally {
    loadingMembers.value = false;
  }
}

function formatDate(value: string) {
  return formatDateTime(value);
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
  await Promise.all([loadGroups(), loadUsers(), loadShares()]);
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
    selected.value = null;
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to delete group' });
  } finally {
    deleteLoading.value = false;
  }
  await loadGroups();
}

async function addMember() {
  if (!selected.value || !memberForm.value.user_id) return;
  addingMember.value = true;
  try {
    await api.addMember(selected.value.id, {
      user_id: memberForm.value.user_id,
      access_level: memberForm.value.access_level,
      expires_at: memberForm.value.expires_at
        ? new Date(memberForm.value.expires_at).toISOString()
        : null,
    });
    memberForm.value.user_id = null;
    memberForm.value.expires_at = null;
    $q.notify({ type: 'positive', message: 'Member added' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to add member' });
  } finally {
    addingMember.value = false;
  }
  await loadGroupDetail(selected.value.id);
}

async function removeMember(member: MemberOut) {
  if (!selected.value) return;
  try {
    await api.removeMember(selected.value.id, member.user_id);
    $q.notify({ type: 'positive', message: 'Member removed' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to remove member' });
  }
  await loadGroupDetail(selected.value.id);
}

async function linkShare(shareId: string | null) {
  if (!selected.value || !shareId) return;
  linking.value = true;
  try {
    await api.linkShare(selected.value.id, shareId);
    shareForm.value.share_id = null;
    $q.notify({ type: 'positive', message: 'Share linked' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to link share' });
  } finally {
    linking.value = false;
  }
  await loadGroupDetail(selected.value.id);
}

async function unlinkShare(shareId: string) {
  if (!selected.value) return;
  try {
    await api.unlinkShare(selected.value.id, shareId);
    $q.notify({ type: 'positive', message: 'Share unlinked' });
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Failed to unlink share' });
  }
  await loadGroupDetail(selected.value.id);
}

onMounted(async () => {
  await Promise.all([loadGroups(), loadUsers(), loadShares()]);
});
</script>