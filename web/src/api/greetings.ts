import { apiClient } from './client';
import {
  GreetingsResponse,
  GreetingChannelOption,
  GuildRoleOption,
  ServerGreetingSettings,
  ServerInviteSettings,
} from '../types';

export const greetingsApi = {
  getGreetings: () => apiClient.get<GreetingsResponse>('/greetings'),

  updateGreetings: (data: Partial<ServerGreetingSettings>) =>
    apiClient.put<{ success: boolean; message: string; settings: ServerGreetingSettings }>('/greetings', data),

  getChannels: () => apiClient.get<GreetingChannelOption[]>('/greetings/channels'),

  getRoles: () => apiClient.get<GuildRoleOption[]>('/greetings/roles'),

  getRules: () =>
    apiClient.get<{
      rules_delivery_enabled: boolean;
      rules_source: string;
      rules_channel_id: string | null;
      rules_title: string | null;
      rules_description: string | null;
      rules_footer: string | null;
      rules_button_text: string | null;
      rules_url: string;
    }>('/greetings/rules'),

  updateRules: (data: any) =>
    apiClient.put<{ success: boolean; message: string; rules_url: string }>('/greetings/rules', data),

  getInvite: () =>
    apiClient.get<{
      invite: ServerInviteSettings;
      channel_name: string | null;
      is_permanent: boolean;
    }>('/greetings/invite'),

  generateInvite: (channelId?: string) =>
    apiClient.post<{
      success: boolean;
      invite_code: string;
      invite_url: string;
      channel_id: string;
      channel_name: string;
      is_permanent: boolean;
      verification_status: string;
    }>('/greetings/invite/generate', { channel_id: channelId }),

  verifyInvite: () =>
    apiClient.post<{
      status: string;
      is_valid: boolean;
      is_permanent: boolean;
      invite_url?: string;
      message: string;
    }>('/greetings/invite/verify'),

  regenerateInvite: (channelId?: string) =>
    apiClient.post<{
      success: boolean;
      invite_code: string;
      invite_url: string;
      channel_id: string;
      channel_name: string;
      is_permanent: boolean;
      verification_status: string;
    }>('/greetings/invite/regenerate', { confirm: true, channel_id: channelId }),

  testGreeting: (systemType: 'welcome' | 'goodbye' | 'welcome-dm' | 'goodbye-dm') =>
    apiClient.post<{ status: string; message: string; channel_id?: string; channel_name?: string }>(`/greetings/test/${systemType}`),

  testWelcome: () =>
    apiClient.post<{ status: string; message: string; channel_id: string; channel_name: string }>('/greetings/test/welcome'),

  testGoodbye: () =>
    apiClient.post<{ status: string; message: string; channel_id: string; channel_name: string }>('/greetings/test/goodbye'),

  resetSystem: (systemType: 'welcome' | 'goodbye' | 'welcome_dm' | 'goodbye_dm' | 'rules') =>
    apiClient.post<{ success: boolean; message: string; settings: ServerGreetingSettings }>(`/greetings/reset/${systemType}`),
};
