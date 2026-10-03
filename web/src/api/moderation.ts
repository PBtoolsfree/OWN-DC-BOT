import { apiClient } from './client';
import { ModerationCase, BlockedMessage, ServerSettings, ExemptionRule } from '../types';

export const moderationApi = {
  getCases: (limit = 100) => apiClient.get<ModerationCase[]>(`/moderation/cases?limit=${limit}`),
  getBlocked: (limit = 100) => apiClient.get<BlockedMessage[]>(`/moderation/blocked?limit=${limit}`),
  getServerSettings: () => apiClient.get<ServerSettings>('/settings/server'),
  updateServerSettings: (data: Partial<ServerSettings>) =>
    apiClient.post<{ success: boolean }>('/settings/server', data),
  getExemptions: () => apiClient.get<ExemptionRule[]>('/settings/exemptions'),
  addExemption: (data: { rule_type: string; target_id: string; target_name?: string; exempt_from?: string }) =>
    apiClient.post<{ success: boolean; id: number }>('/settings/exemptions', data),
  removeExemption: (ruleId: number) =>
    apiClient.delete<{ success: boolean }>(`/settings/exemptions/${ruleId}`),
};
