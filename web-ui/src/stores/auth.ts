import { defineStore } from 'pinia';
import { api } from '@/api';

const TOKEN_KEY = 'nas.token';
const REFRESH_KEY = 'nas.refresh_token';
const USERNAME_KEY = 'nas.username';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || null,
    refreshToken: localStorage.getItem(REFRESH_KEY) || null,
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
      this.refreshToken = data.refresh_token;
      this.username = username;
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(REFRESH_KEY, data.refresh_token);
      localStorage.setItem(USERNAME_KEY, username);
      await this.refreshProfile();
    },

    async tryRefresh(): Promise<boolean> {
      if (!this.refreshToken) return false;
      try {
        const { data } = await api.refresh(this.refreshToken);
        this.token = data.access_token;
        this.refreshToken = data.refresh_token;
        localStorage.setItem(TOKEN_KEY, data.access_token);
        localStorage.setItem(REFRESH_KEY, data.refresh_token);
        return true;
      } catch {
        this.logout();
        return false;
      }
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
      this.refreshToken = null;
      this.username = '';
      this.isAdmin = false;
      this.profileLoaded = false;
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
      localStorage.removeItem(USERNAME_KEY);
    },
  },
});