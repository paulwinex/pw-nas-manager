import { defineRouter } from '#q-app';
import { routes, handleHotUpdate } from 'vue-router/auto-routes';
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';
import { configureAuth } from '@/api/client';
import { useAuthStore } from '@/stores/auth';

export default defineRouter(() => {
  const createHistory = import.meta.env.QUASAR_SERVER
    ? createMemoryHistory
    : (import.meta.env.QUASAR_VUE_ROUTER_MODE === 'history' ? createWebHistory : createWebHashHistory);

  const Router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createHistory(import.meta.env.QUASAR_VUE_ROUTER_BASE),
  });

  Router.beforeEach(async (to) => {
    const auth = useAuthStore();
    if (to.path !== '/login' && !auth.authenticated) {
      return { path: '/login' };
    }
    if (to.path === '/login' && auth.authenticated) {
      return { path: '/' };
    }
    if (to.path !== '/login' && auth.authenticated && !auth.profileLoaded) {
      try {
        await auth.refreshProfile();
      } catch {
        auth.logout();
        return { path: '/login' };
      }
    }
    // Admin guard
    if (to.path.startsWith('/admin') && !auth.isAdmin) {
      return { path: '/' };
    }
    return true;
  });

  configureAuth(
    () => useAuthStore().token,
    () => {
      useAuthStore().logout();
      Router.push('/login');
    },
    () => useAuthStore().tryRefresh(),
  );

  if (import.meta.hot) {
    handleHotUpdate(Router);
  }

  return Router;
});