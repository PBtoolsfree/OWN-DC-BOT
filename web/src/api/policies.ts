import { apiClient } from './client';
import { ChannelPolicy, PolicyProfile, PolicySimulationResult } from '../types';

export const policiesApi = {
  getPolicies: () => apiClient.get<ChannelPolicy[]>('/policies'),
  getChannelPolicy: (channelId: string) => apiClient.get<ChannelPolicy | null>(`/policies/${channelId}`),
  saveChannelPolicy: (channelId: string, data: Partial<ChannelPolicy>) =>
    apiClient.post<{ success: boolean }>(`/policies/${channelId}`, data),
  deleteChannelPolicy: (channelId: string) =>
    apiClient.delete<{ success: boolean }>(`/policies/${channelId}`),
  getProfiles: () => apiClient.get<PolicyProfile[]>('/policies/profiles'),
  simulatePolicy: (data: {
    channel_id: string;
    content: string;
    role_ids?: string[];
    has_attachment?: boolean;
    attachment_type?: string;
  }) => apiClient.post<PolicySimulationResult>('/policies/simulate', data),
};
