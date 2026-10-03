import { apiClient } from './client';
import { ModerationCase, BlockedMessage, ServerSettings, ExemptionRule, ModLogSettings } from '../types';

export const moderationApi = {
  getCases: (limit = 100) => apiClient.get<ModerationCase[]>(`/moderation/cases?limit=${limit}`),
  getBlocked: (limit = 100) => apiClient.get<BlockedMessage[]>(`/moderation/blocked?limit=${limit}`),
  getServerSettings: () => apiClient.get<ServerSettings>('/settings/server'),
  updateServerSettings: (data: Partial<ServerSettings>) =>
    apiClient.post<{ success: boolean }>('/settings/server', data),
  getModLogSettings: () => apiClient.get<ModLogSettings>('/moderation/log-settings'),
  updateModLogSettings: (data: { mod_log_channel_id: string | null; mod_log_events: string[] }) =>
    apiClient.put<{ success: boolean; message?: string }>('/moderation/log-settings', data),
  getExemptions: () => apiClient.get<ExemptionRule[]>('/settings/exemptions'),
  addExemption: (data: { rule_type: string; target_id: string; target_name?: string; exempt_from?: string }) =>
    apiClient.post<{ success: boolean; id: number }>('/settings/exemptions', data),
  removeExemption: (ruleId: number) =>
    apiClient.delete<{ success: boolean }>(`/settings/exemptions/${ruleId}`),
};

