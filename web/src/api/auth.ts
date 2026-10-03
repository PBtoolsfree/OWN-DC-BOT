import { apiClient } from './client';

export interface AuthUser {
  authenticated: boolean;
  username: string;
  guild_id: string;
}

export const authApi = {
  getMe: () => apiClient.get<AuthUser>('/auth/me'),
  login: (data: { username: string; password: string }) =>
    apiClient.post<{ success: boolean; username: string; guild_id: string }>('/auth/login', data),
  logout: () => apiClient.post<{ success: boolean }>('/auth/logout', {}),
};
