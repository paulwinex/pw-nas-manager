import client from './client';
import type {
  GroupOut,
  MemberOut,
  MountScriptResponse,
  RegistryState,
  ShareOut,
  StatsResponse,
  SyncReport,
  UserOut,
} from './types';

export const api = {
  // auth
  login: (username: string, password: string) => {
    const form = new URLSearchParams();
    form.set('username', username);
    form.set('password', password);
    return client.post<{ access_token: string; token_type: string }>('/api/v1/auth/token', form);
  },
  me: () => client.get<UserOut>('/api/v1/auth/me'),
  stats: () => client.get<StatsResponse>('/api/v1/stats'),
  health: () => client.get<{ status: string }>('/api/v1/health'),

  // users
  listUsers: () => client.get<UserOut[]>('/api/v1/users'),
  createUser: (body: { username: string; password: string; is_admin: boolean }) =>
    client.post<UserOut>('/api/v1/users', body),
  changeUserPassword: (id: string, newPassword: string) =>
    client.post<UserOut>(`/api/v1/users/${id}/password`, { new_password: newPassword }),
  deleteUser: (id: string) => client.delete<void>(`/api/v1/users/${id}`),
  mountScript: (username: string, password: string) =>
    client.post<MountScriptResponse>(`/api/v1/users/${username}/mount-script`, { password }),

  // groups
  listGroups: () => client.get<GroupOut[]>('/api/v1/groups'),
  createGroup: (name: string) => client.post<GroupOut>('/api/v1/groups', { name }),
  deleteGroup: (id: string) => client.delete<void>(`/api/v1/groups/${id}`),
  listMembers: (groupId: string) => client.get<MemberOut[]>(`/api/v1/groups/${groupId}/members`),
  addMember: (
    groupId: string,
    body: { user_id: string; access_level: string; expires_at: string | null }
  ) => client.post<MemberOut>(`/api/v1/groups/${groupId}/members`, body),
  removeMember: (groupId: string, userId: string) =>
    client.delete<void>(`/api/v1/groups/${groupId}/members/${userId}`),
  listGroupShares: (groupId: string) => client.get<ShareOut[]>(`/api/v1/groups/${groupId}/shares`),
  linkShare: (groupId: string, shareId: string) =>
    client.post<ShareOut>(`/api/v1/groups/${groupId}/shares`, { share_id: shareId }),
  unlinkShare: (groupId: string, shareId: string) =>
    client.delete<void>(`/api/v1/groups/${groupId}/shares/${shareId}`),

  // shares
  listShares: () => client.get<ShareOut[]>('/api/v1/shares'),
  availableDirs: () => client.get<string[]>('/api/v1/shares/available'),
  createShare: (name: string) => client.post<ShareOut>('/api/v1/shares', { name }),
  deleteShare: (id: string) => client.delete<void>(`/api/v1/shares/${id}`),

  // system
  sync: () => client.post<SyncReport>('/api/v1/sync'),
  sweep: () =>
    client.post<{ processed: number; sync: SyncReport | null }>('/api/v1/expirations/sweep'),
  registry: () => client.get<RegistryState>('/api/v1/registry/shares'),
};
