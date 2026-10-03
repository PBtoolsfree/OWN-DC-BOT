import { apiClient } from './client';
import { YouTubeChannel, YouTubeDestination } from '../types';

export interface AddYouTubePayload {
  youtube_input: string;
  discord_channel_id: string;
  notification_role_id?: string | null;
  channel_name?: string;
  upload_enabled?: boolean;
  scheduled_live_enabled?: boolean;
  live_started_enabled?: boolean;
  premiere_enabled?: boolean;
}

export interface UpdateYouTubePayload {
  channel_name?: string;
  destinations?: YouTubeDestination[];
}

export const youtubeApi = {
  getChannels: () => apiClient.get<YouTubeChannel[]>('/youtube/channels'),
  getChannel: (id: string) => apiClient.get<YouTubeChannel>(`/youtube/channels/${id}`),
  addChannel: (data: AddYouTubePayload) =>
    apiClient.post<{ success: boolean; channel_id: string; channel_name: string }>('/youtube/channels', data),
  updateChannel: (id: string, data: UpdateYouTubePayload) =>
    apiClient.put<{ success: boolean }>(`/youtube/channels/${id}`, data),
  deleteChannel: (id: string) =>
    apiClient.delete<{ success: boolean }>(`/youtube/channels/${id}`),
  toggleChannel: (id: string, enabled: boolean) =>
    apiClient.post<{ success: boolean }>(`/youtube/channels/${id}/toggle`, { enabled }),
  testChannel: (id: string) =>
    apiClient.post<{
      success: boolean;
      channel_name?: string;
      entry_count: number;
      error?: string | null;
      entries: Array<{ title: string; video_id: string; url: string; published?: string }>;
    }>(`/youtube/test/${id}`, {}),
  testLive: (id: string) =>
    apiClient.post<{
      success: boolean;
      is_live: boolean;
      is_upcoming?: boolean;
      is_premiere?: boolean;
      status: string;
      title?: string | null;
      video_id?: string | null;
      channel_id?: string;
      scheduled_start?: string | null;
      viewer_count?: number | null;
      error?: string | null;
    }>(`/youtube/test-live/${id}`, {}),
};
