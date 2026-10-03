import { apiClient } from './client';
import { SystemStatus, SystemOverview, AuditLogItem } from '../types';

export const systemApi = {
  getStatus: () => apiClient.get<SystemStatus>('/system/status'),
  getOverview: () => apiClient.get<SystemOverview>('/system/overview'),
  getAuditLogs: (limit = 100) => apiClient.get<AuditLogItem[]>(`/audit-logs?limit=${limit}`),
  reload: () => apiClient.post<{ success: boolean; message: string }>('/system/reload', {}),
  restart: () => apiClient.post<{ success: boolean; message: string }>('/system/restart', {}),
  testDb: () => apiClient.post<{ success: boolean; latency_ms: number; message: string }>('/system/test-db', {}),
  testYoutube: () => apiClient.post<{ success: boolean; running: boolean; healthy: boolean; message: string }>('/system/test-youtube', {}),
};
