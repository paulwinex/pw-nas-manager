import axios from 'axios';
import type { AxiosRequestConfig } from 'axios';

const client = axios.create({ baseURL: '' });

let tokenGetter: () => string | null = () => null;
let onUnauthorized: (() => void) | null = null;
let refreshHandler: (() => Promise<boolean>) | null = null;

export function configureAuth(
  getToken: () => string | null,
  handler: () => void,
  refresh?: () => Promise<boolean>,
) {
  tokenGetter = getToken;
  onUnauthorized = handler;
  refreshHandler = refresh || null;
}

client.interceptors.request.use((config) => {
  const token = tokenGetter();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };
    const isRefreshRequest = originalRequest.url?.includes('/auth/refresh');
    if (error?.response?.status === 401 && !originalRequest._retry && refreshHandler && !isRefreshRequest) {
      originalRequest._retry = true;
      const ok = await refreshHandler();
      if (ok) {
        return client(originalRequest);
      }
    }
    if (error?.response?.status === 401 && onUnauthorized) {
      onUnauthorized();
    }
    return Promise.reject(error);
  },
);

export default client;