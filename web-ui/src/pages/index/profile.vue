<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Профиль</div>

    <q-card class="q-mb-md" flat bordered>
      <q-card-section>
        <div class="row items-center">
          <q-avatar color="primary" text-color="white" size="56px" icon="person" />
          <div>
            <div class="text-h6 q-ml-sm">{{ auth.username }}</div>
            <div class="text-caption text-grey q-ml-sm">
              {{ auth.isAdmin ? 'Администратор' : 'Пользователь' }}
            </div>
          </div>
        </div>
      </q-card-section>
    </q-card>

    <q-card class="q-mb-md" flat bordered>
      <q-card-section>
        <div class="text-subtitle1">Оформление</div>
      </q-card-section>
      <q-card-section class="q-pt-none">
        <q-toggle :model-value="$q.dark.isActive" label="Тёмная тема" @update:model-value="(v: boolean) => toggleDark(v)" />
      </q-card-section>
    </q-card>

    <q-card flat bordered>
      <q-card-section>
        <div class="text-subtitle1">Смена пароля</div>
      </q-card-section>
      <q-card-section class="q-pt-none">
        <q-form @submit="changePassword">
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-4">
              <q-input
                v-model="pwd.new"
                dense
                label="Новый пароль"
                type="password"
                outlined
                @update:model-value="pwd.error = ''"
              />
            </div>
            <div class="col-12 col-md-4">
              <q-input
                v-model="pwd.confirm"
                dense
                label="Подтверждение"
                type="password"
                outlined
                :error="!!pwd.error"
                :error-message="pwd.error"
                @update:model-value="pwd.error = ''"
              />
            </div>
          </div>
          <div class="row items-center q-mt-md">
            <q-btn label="Сменить пароль" type="submit" color="primary" :loading="saving" />
            <q-btn flat label="Выйти" class="q-ml-sm" @click="logout" />
          </div>
        </q-form>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useQuasar } from 'quasar';
import { useRouter } from 'vue-router';
import { api } from '@/api';
import { useAuthStore } from '@/stores/auth';

const $q = useQuasar();
const router = useRouter();
const auth = useAuthStore();
const saving = ref(false);
const pwd = ref({ new: '', confirm: '', error: '' });

function toggleDark(value: boolean) {
  $q.dark.set(value);
  localStorage.setItem('nas.dark', value ? '1' : '0');
}

function logout() {
  auth.logout();
  router.push('/login');
}

async function changePassword() {
  pwd.value.error = '';
  if (!pwd.value.new) {
    pwd.value.error = 'Введите новый пароль';
    return;
  }
  if (pwd.value.new !== pwd.value.confirm) {
    pwd.value.error = 'Пароли не совпадают';
    return;
  }
  saving.value = true;
  try {
    await api.changeMyPassword(pwd.value.new);
    $q.notify({ type: 'positive', message: 'Пароль изменён. Перелогиньтесь.' });
    pwd.value.new = '';
    pwd.value.confirm = '';
  } catch (e: any) {
    $q.notify({ type: 'negative', message: e?.response?.data?.detail ?? 'Не удалось сменить пароль' });
  } finally {
    saving.value = false;
  }
}
</script>