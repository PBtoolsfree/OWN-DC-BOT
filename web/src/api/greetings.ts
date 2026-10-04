import { apiClient } from './client';
import {
  GreetingsResponse,
  GreetingChannelOption,
  ServerGreetingSettings,
} from '../types';

export const greetingsApi = {
  getGreetings: () => apiClient.get<GreetingsResponse>('/greetings'),

  updateGreetings: (data: Partial<ServerGreetingSettings>) =>
    apiClient.put<{ success: boolean; message: string; settings: ServerGreetingSettings }>('/greetings', data),

  getChannels: () => apiClient.get<GreetingChannelOption[]>('/greetings/channels'),

  testWelcome: () =>
    apiClient.post<{ status: string; message: string; channel_id: string; channel_name: string }>('/greetings/test/welcome'),

  testGoodbye: () =>
    apiClient.post<{ status: string; message: string; channel_id: string; channel_name: string }>('/greetings/test/goodbye'),

  resetSystem: (systemType: 'welcome' | 'goodbye') =>
    apiClient.post<{ success: boolean; message: string; settings: ServerGreetingSettings }>(`/greetings/reset/${systemType}`),
};
