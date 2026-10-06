import { apiClient } from './client';
import {
  FreeGameHealth,
  FreeGameOffer,
  FreeGameSettings,
  FreeGameSourceHealth,
  FreeGameStats,
} from '../types';

export const freegamesApi = {
  getSettings: () => apiClient.get<FreeGameSettings>('/freegames/settings'),

  updateSettings: (payload: Partial<FreeGameSettings>) =>
    apiClient.put<{ success: boolean; settings: FreeGameSettings }>('/freegames/settings', payload),

  getOffers: (params?: { status?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.status && params.status !== 'ALL') {
      query.append('status', params.status);
    }
    if (params?.limit !== undefined) {
      query.append('limit', String(params.limit));
    }
    if (params?.offset !== undefined) {
      query.append('offset', String(params.offset));
    }
    const qStr = query.toString();
    return apiClient.get<{ offers: FreeGameOffer[]; count: number }>(
      `/freegames/offers${qStr ? `?${qStr}` : ''}`
    );
  },

  getSources: () => apiClient.get<{ sources: FreeGameSourceHealth[] }>('/freegames/sources'),

  getHealth: () => apiClient.get<FreeGameHealth>('/freegames/health'),

  getStats: () => apiClient.get<FreeGameStats>('/freegames/stats'),

  syncOffers: () =>
    apiClient.post<{
      success: boolean;
      total_found?: number;
      new_offers?: number;
      message?: string;
      errors?: string[];
    }>('/freegames/sync'),

  testNotification: () =>
    apiClient.post<{
      success: boolean;
      message?: string;
      channel_id?: number | string;
    }>('/freegames/test'),
};
