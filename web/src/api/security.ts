import { apiClient } from './client';

export const securityApi = {
  changePassword: (data: { current_password: string; new_password: string }) =>
    apiClient.post<{ success: boolean; message: string }>('/security/change-password', data),
};
