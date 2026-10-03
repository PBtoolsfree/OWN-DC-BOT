import { apiClient } from './client';
import { ChannelPolicy, PolicyProfile, PolicySimulationResult, ModerationChannelInfo } from '../types';

export const policiesApi = {
  getPolicies: () => apiClient.get<ChannelPolicy[]>('/policies'),
  getChannelPolicy: (channelId: string) => apiClient.get<ChannelPolicy | null>(`/policies/${channelId}`),
  saveChannelPolicy: (channelId: string, data: Partial<ChannelPolicy>) =>
    apiClient.post<{ success: boolean; message?: string; policy?: ChannelPolicy }>(`/policies/${channelId}`, data),
  deleteChannelPolicy: (channelId: string) =>
    apiClient.delete<{ success: boolean; message?: string }>(`/policies/${channelId}`),
  getProfiles: () => apiClient.get<PolicyProfile[]>('/policies/profiles'),
  getProfile: (id: number) => apiClient.get<PolicyProfile>(`/policies/profiles/${id}`),
  createProfile: (data: Partial<PolicyProfile>) =>
    apiClient.post<PolicyProfile>('/policies/profiles', data),
  updateProfile: (id: number, data: Partial<PolicyProfile>) =>
    apiClient.put<PolicyProfile>(`/policies/profiles/${id}`, data),
  deleteProfile: (id: number) =>
    apiClient.delete<{ success: boolean; message?: string }>(`/policies/profiles/${id}`),
  duplicateProfile: (id: number, new_name?: string) =>
    apiClient.post<PolicyProfile>(`/policies/profiles/${id}/duplicate`, { new_name }),
  applyProfile: (id: number, channelIds: string[]) =>
    apiClient.post<{ success: boolean; message: string; applied_count: number; channel_ids: string[] }>(
      `/policies/profiles/${id}/apply`,
      { channel_ids: channelIds }
    ),
  getModerationChannels: () =>
    apiClient.get<ModerationChannelInfo[]>('/moderation/channels'),
  simulatePolicy: (data: {
    channel_id?: string;
    content: string;
    role_ids?: string[];
    has_attachment?: boolean;
    attachment_type?: string;
    policy_override?: any;
  }) => apiClient.post<PolicySimulationResult>('/policies/simulate', data),
};

