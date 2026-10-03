import { apiClient } from './client';
import {
  ModerationCase,
  BlockedMessage,
  ServerSettings,
  ExemptionRule,
  ModLogSettings,
  ModerationExemption,
  AutomodRule,
  WarningRecord,
  WarningEscalationRule,
  GuildTargets,
  ModerationOverviewStats,
} from '../types';

export const moderationApi = {
  // Cases & Stats
  getCases: (params?: number | { limit?: number; search?: string; action?: string; user_id?: string; channel_id?: string; case_id?: string }) => {
    const q = new URLSearchParams();
    if (typeof params === 'number') {
      q.set('limit', String(params));
    } else if (params) {
      if (params.limit) q.set('limit', String(params.limit));
      if (params.search) q.set('search', params.search);
      if (params.action && params.action !== 'all') q.set('action', params.action);
      if (params.user_id) q.set('user_id', params.user_id);
      if (params.channel_id && params.channel_id !== 'all') q.set('channel_id', params.channel_id);
      if (params.case_id) q.set('case_id', params.case_id);
    }
    return apiClient.get<ModerationCase[]>(`/moderation/cases?${q.toString()}`);
  },
  getCaseDetails: (caseIdentifier: string) =>
    apiClient.get<ModerationCase>(`/moderation/cases/${encodeURIComponent(caseIdentifier)}`),
  getStats: () => apiClient.get<ModerationOverviewStats>('/moderation/stats'),
  getBlocked: (limit = 100) => apiClient.get<BlockedMessage[]>(`/moderation/blocked?limit=${limit}`),

  // Mod Log Settings
  getModLogSettings: () => apiClient.get<ModLogSettings>('/moderation/log-settings'),
  updateModLogSettings: (data: { mod_log_channel_id: string | null; mod_log_events: string[] }) =>
    apiClient.put<{ success: boolean; message?: string }>('/moderation/log-settings', data),

  // Guild targets for selector
  getGuildTargets: () => apiClient.get<GuildTargets>('/moderation/guild-targets'),

  // Granular Exemptions
  getModerationExemptions: () => apiClient.get<ModerationExemption[]>('/moderation/exemptions'),
  createModerationExemption: (data: Partial<ModerationExemption>) =>
    apiClient.post<{ success: boolean; id: number }>('/moderation/exemptions', data),
  updateModerationExemption: (id: number, data: Partial<ModerationExemption>) =>
    apiClient.put<{ success: boolean }>((`/moderation/exemptions/${id}`), data),
  deleteModerationExemption: (id: number) =>
    apiClient.delete<{ success: boolean }>(`/moderation/exemptions/${id}`),

  // Automod Rules
  getAutomodRules: () => apiClient.get<AutomodRule[]>('/moderation/automod-rules'),
  createAutomodRule: (data: Partial<AutomodRule>) =>
    apiClient.post<{ success: boolean; id: number }>('/moderation/automod-rules', data),
  updateAutomodRule: (id: number, data: Partial<AutomodRule>) =>
    apiClient.put<{ success: boolean }>(`/moderation/automod-rules/${id}`, data),
  deleteAutomodRule: (id: number) =>
    apiClient.delete<{ success: boolean }>(`/moderation/automod-rules/${id}`),

  // Warnings & Actions
  getWarnings: (params?: { user_id?: string; active_only?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.user_id) q.set('user_id', params.user_id);
    if (params?.active_only !== undefined) q.set('active_only', String(params.active_only));
    return apiClient.get<WarningRecord[]>(`/moderation/warnings?${q.toString()}`);
  },
  issueWarning: (data: {
    user_id: string;
    username?: string;
    channel_id?: string;
    channel_name?: string;
    rule?: string;
    reason: string;
    severity?: string;
    points?: number;
  }) => apiClient.post<{ success: boolean; warning_id: string; case_id: string }>('/moderation/warnings', data),
  revokeWarning: (warningId: string, reason?: string) =>
    apiClient.delete<{ success: boolean }>(
      `/moderation/warnings/${encodeURIComponent(warningId)}${reason ? `?reason=${encodeURIComponent(reason)}` : ''}`
    ),
  clearUserWarnings: (userId: string) =>
    apiClient.delete<{ success: boolean; cleared_count: number }>(`/moderation/warnings/user/${userId}`),
  getWarningsStats: () =>
    apiClient.get<{ active_warnings: number; warnings_today: number; decay_days: number; mode: string }>(
      '/moderation/warnings/stats'
    ),

  // Escalation Ladder
  getEscalationRules: () => apiClient.get<WarningEscalationRule[]>('/moderation/escalation-rules'),
  createEscalationRule: (data: Partial<WarningEscalationRule>) =>
    apiClient.post<{ success: boolean; id: number }>('/moderation/escalation-rules', data),
  updateEscalationRule: (id: number, data: Partial<WarningEscalationRule>) =>
    apiClient.put<{ success: boolean }>(`/moderation/escalation-rules/${id}`, data),
  deleteEscalationRule: (id: number) =>
    apiClient.delete<{ success: boolean }>(`/moderation/escalation-rules/${id}`),

  // Quick Setup / Easy Mode
  getQuickSetupPreview: () =>
    apiClient.get<{
      styles: Record<string, { name: string; description: string; actions: string[]; decay_days: number }>;
    }>('/moderation/quick-setup'),
  applyQuickSetup: (style: string) =>
    apiClient.post<{ success: boolean; message: string }>('/moderation/quick-setup', { style }),

  // Legacy/Compatibility server settings & exemptions
  getServerSettings: () => apiClient.get<ServerSettings>('/settings/server'),
  updateServerSettings: (data: Partial<ServerSettings>) =>
    apiClient.post<{ success: boolean }>('/settings/server', data),
  getExemptions: () => apiClient.get<ExemptionRule[]>('/settings/exemptions'),
  addExemption: (data: { rule_type: string; target_id: string; target_name?: string; exempt_from?: string }) =>
    apiClient.post<{ success: boolean; id: number }>('/settings/exemptions', data),
  removeExemption: (ruleId: number) =>
    apiClient.delete<{ success: boolean }>(`/settings/exemptions/${ruleId}`),
};


