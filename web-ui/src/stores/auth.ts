import { defineStore } from 'pinia';
import { api } from '@/api';

const TOKEN_KEY = 'nas.token';
const USERNAME_KEY = 'nas.username';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || null,
    username: localStorage.getItem(USERNAME_KEY) || '',
    isAdmin: false,
    profileLoaded: false,
  }),

  getters: {
    authenticated: (state) => state.token !== null,
  },

  actions: {
    async login(username: string, password: string) {
      const { data } = await api.login(username, password);
      this.token = data.access_token;
      this.username = username;
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(USERNAME_KEY, username);
      await this.refreshProfile();
    },

    async refreshProfile() {
      const { data } = await api.me();
      this.username = data.username;
      this.isAdmin = data.is_admin;
      this.profileLoaded = true;
      localStorage.setItem(USERNAME_KEY, data.username);
    },

    logout() {
      this.token = null;
      this.username = '';
      this.isAdmin = false;
      this.profileLoaded = false;
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USERNAME_KEY);
    },
  },
});