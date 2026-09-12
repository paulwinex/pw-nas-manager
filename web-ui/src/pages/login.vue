<template>
  <q-page class="login-page flex flex-center">
    <q-card class="login-card" bordered>
      <q-card-section class="text-center q-pt-xl">
        <q-icon name="folder_shared" size="56px" color="primary" />
        <div class="text-h5 q-mt-sm">NAS Manager</div>
        <div class="text-caption text-grey">Sign in to continue</div>
      </q-card-section>

      <q-card-section>
        <q-form @submit="onSubmit" class="q-gutter-md">
          <q-input
            v-model="username"
            label="Username"
            outlined
            autofocus
            :disable="loading"
          />
          <q-input
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            label="Password"
            outlined
            :disable="loading"
          >
            <template v-slot:append>
              <q-icon
                :name="showPassword ? 'visibility_off' : 'visibility'"
                class="cursor-pointer"
                @click="showPassword = !showPassword"
              />
            </template>
          </q-input>

          <div v-if="error" class="text-negative">{{ error }}</div>

          <q-btn
            type="submit"
            label="Sign in"
            color="primary"
            unelevated
            no-caps
            class="full-width"
            :loading="loading"
          />
        </q-form>
      </q-card-section>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();

const username = ref('');
const password = ref('');
const showPassword = ref(false);
const loading = ref(false);
const error = ref('');

async function onSubmit() {
  loading.value = true;
  error.value = '';
  try {
    await auth.login(username.value, password.value);
    await router.push('/');
  } catch (e) {
    if (axios.isAxiosError(e)) {
      if (e.response?.status === 401) {
        error.value = 'Invalid username or password';
      } else if (e.response?.status === 403) {
        error.value = 'Administrator privileges required';
      }
    }
    if (!error.value) {
      error.value = 'Cannot reach the server';
    }
  } finally {
    loading.value = false;
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  background: $dark-page;
}

.login-card {
  width: 100%;
  max-width: 380px;
}
</style>
