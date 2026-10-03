/**
 * PB HERO Dashboard TypeScript Types
 */

export type PolicyValue = 'allow' | 'deny' | 'inherit';

export interface SystemStatus {
  status: 'ok' | 'degraded';
  bot: {
    connected: boolean;
    latency_ms: number;
    guild_name: string;
    guild_members: number;
    uptime: number;
  };
  database: {
    connected: boolean;
  };
  youtube: {
    running: boolean;
    healthy: boolean;
  };
  system: {
    version: string;
    python: string;
  };
}

export interface SystemOverview {
  youtube_channels: number;
  youtube_enabled: number;
  notifications_today: number;
  blocked_messages_today: number;
  moderation_cases_today: number;
  active_policies: number;
}

export interface YouTubeDestination {
  id?: number;
  discord_channel_id: string;
  notification_role_id?: string | null;
  upload_enabled: boolean;
  scheduled_live_enabled: boolean;
  live_started_enabled: boolean;
  premiere_enabled: boolean;
}

export interface YouTubeChannel {
  id: number;
  youtube_channel_id: string;
  channel_name: string;
  handle?: string | null;
  enabled: boolean;
  feed_url: string;
  last_checked_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  destinations: YouTubeDestination[];
}

export interface DiscordChannel {
  id: string;
  name: string;
  type: 'text' | 'voice' | 'stage' | 'forum';
  category: string;
  category_id?: string | null;
  position: number;
}

export interface DiscordRole {
  id: string;
  name: string;
  color: string;
  position: number;
}

export interface ChannelPolicy {
  id?: number;
  discord_channel_id: string;
  channel_name?: string;
  category_name?: string;
  channel_type?: string;
  allow_text: PolicyValue;
  allow_links: PolicyValue;
  allow_images: PolicyValue;
  allow_videos: PolicyValue;
  allow_files: PolicyValue;
  allow_stickers: PolicyValue;
  allow_everyone: PolicyValue;
  allow_here: PolicyValue;
  allow_role_mentions: PolicyValue;
  allow_user_mentions: PolicyValue;
  allowed_domains?: string[] | string | null;
  preset_name?: string | null;
  enabled: boolean;
  delete_violations: boolean;
  warn_on_violation: boolean;
  log_violations: boolean;
  warning_message?: string | null;
}

export interface PolicyProfile {
  id: number;
  name: string;
  description?: string;
  is_builtin: boolean;
  allow_text: PolicyValue;
  allow_links: PolicyValue;
  allow_images: PolicyValue;
  allow_videos: PolicyValue;
  allow_files: PolicyValue;
  allow_stickers: PolicyValue;
  allow_everyone: PolicyValue;
  allow_here: PolicyValue;
  allow_role_mentions: PolicyValue;
  allow_user_mentions: PolicyValue;
}

export interface ModerationCase {
  case_number: number;
  target_user_id: string;
  target_username: string;
  moderator_user_id: string;
  moderator_username: string;
  action: string;
  reason: string;
  duration?: number | null;
  created_at: string;
}

export interface BlockedMessage {
  id: number;
  channel_id: string;
  user_id: string;
  username: string;
  content_preview: string;
  reason: string;
  rule: string;
  created_at: string;
}

export interface ServerSettings {
  mod_log_channel_id?: string | null;
  admin_role_ids: string[];
  moderator_role_ids: string[];
  global_allowed_domains: string[];
  warning_message_template?: string;
  default_timeout_duration: number;
}

export interface ExemptionRule {
  id: number;
  rule_type: 'user' | 'role' | 'channel';
  target_id: string;
  target_name?: string;
  exempt_from: string;
}

export interface AuditLogItem {
  id: number;
  actor: string;
  action: string;
  target?: string | null;
  details?: string | null;
  created_at: string;
}

export interface PolicySimulationResult {
  allowed: boolean;
  reason: string;
  rule?: string;
}

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastMessage {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
}
