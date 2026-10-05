import { apiClient } from './client';
import {
  DiscordTrackedInvite,
  InviteActivitySettings,
  InviteChannelOption,
  InviteJoinRecord,
  InviteLeaderboardEntry,
  InviteOverviewStats,
  InviteTrackerHealth,
  UserInviteProfile,
} from '../types';

export interface GetInvitesParams {
  status?: string;
  search?: string;
  channel_id?: number;
  page?: number;
  page_size?: number;
}

export interface GetInvitesResponse {
  items: DiscordTrackedInvite[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GetJoinsParams {
  source_type?: string;
  search?: string;
  invite_code?: string;
  inviter_id?: number;
  page?: number;
  page_size?: number;
}

export interface GetJoinsResponse {
  items: InviteJoinRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface InviteDetailsResponse {
  invite: DiscordTrackedInvite;
  joins: InviteJoinRecord[];
  total_joins: number;
}

export const invitesApi = {
  getInvites: (params?: GetInvitesParams) => {
    const query = new URLSearchParams();
    if (params?.status && params.status !== 'ALL') query.append('status', params.status);
    if (params?.search) query.append('search', params.search);
    if (params?.channel_id) query.append('channel_id', params.channel_id.toString());
    if (params?.page) query.append('page', params.page.toString());
    if (params?.page_size) query.append('page_size', params.page_size.toString());
    const qStr = query.toString();
    return apiClient.get<GetInvitesResponse>(`/moderation/invites${qStr ? `?${qStr}` : ''}`);
  },

  getInviteDetails: (code: string) =>
    apiClient.get<InviteDetailsResponse>(`/moderation/invites/${encodeURIComponent(code)}`),

  getLeaderboard: (limit: number = 50) =>
    apiClient.get<{ leaderboard: InviteLeaderboardEntry[] }>(`/moderation/invites/leaderboard?limit=${limit}`),

  getUserProfile: (userId: string | number) =>
    apiClient.get<UserInviteProfile>(`/moderation/invites/users/${userId}`),

  getJoinsHistory: (params?: GetJoinsParams) => {
    const query = new URLSearchParams();
    if (params?.source_type && params.source_type !== 'ALL') query.append('source_type', params.source_type);
    if (params?.search) query.append('search', params.search);
    if (params?.invite_code) query.append('invite_code', params.invite_code);
    if (params?.inviter_id) query.append('inviter_id', params.inviter_id.toString());
    if (params?.page) query.append('page', params.page.toString());
    if (params?.page_size) query.append('page_size', params.page_size.toString());
    const qStr = query.toString();
    return apiClient.get<GetJoinsResponse>(`/moderation/invites/joins${qStr ? `?${qStr}` : ''}`);
  },

  getStats: (timeframe: string = 'all') =>
    apiClient.get<InviteOverviewStats>(`/moderation/invites/stats?timeframe=${timeframe}`),

  getHealth: () =>
    apiClient.get<InviteTrackerHealth>('/moderation/invites/health'),

  syncInvites: () =>
    apiClient.post<{ status: string; tracked_invites: number; active_invites: number; last_sync: string }>('/moderation/invites/sync'),

  revokeInvite: (code: string) =>
    apiClient.delete<{ success: boolean; invite_code: string; deleted_from_discord: boolean; status: string }>(`/moderation/invites/${encodeURIComponent(code)}`),

  getActivitySettings: () =>
    apiClient.get<InviteActivitySettings>('/moderation/invites/activity-settings'),

  updateActivitySettings: (payload: Partial<InviteActivitySettings>) =>
    apiClient.put<InviteActivitySettings>('/moderation/invites/activity-settings', payload),

  resetActivitySettings: () =>
    apiClient.post<InviteActivitySettings>('/moderation/invites/activity-settings/reset'),

  testActivityLog: () =>
    apiClient.post<{ success: boolean; channel_id: string; channel_name: string; message_id: string }>('/moderation/invites/activity-settings/test'),

  getActivityChannels: () =>
    apiClient.get<InviteChannelOption[]>('/moderation/invites/channels'),
};
