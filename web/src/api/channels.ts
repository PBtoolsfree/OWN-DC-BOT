import { apiClient } from './client';
import { DiscordChannel, DiscordRole } from '../types';

export const channelsApi = {
  getChannels: () => apiClient.get<DiscordChannel[]>('/channels'),
  getRoles: () => apiClient.get<DiscordRole[]>('/channels/roles'),
};
