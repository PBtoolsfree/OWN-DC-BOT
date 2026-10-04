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
  // Voice Policy controls
  allow_connect?: PolicyValue;
  allow_speak?: PolicyValue;
  allow_video?: PolicyValue;
  allow_stream?: PolicyValue;
  allow_soundboard?: PolicyValue;
  allow_voice_activity?: PolicyValue;
  allow_priority_speaker?: PolicyValue;
  allow_mute_members?: PolicyValue;
  allow_deafen_members?: PolicyValue;
  allow_move_members?: PolicyValue;
  allowed_domains?: string[] | string | null;
  preset_name?: string | null;
  enabled: boolean;
  delete_violations: boolean;
  warn_on_violation: boolean;
  log_violations: boolean;
  send_dm_warning?: boolean;
  warning_message?: string | null;
}

export interface PolicyProfile {
  id: number;
  name: string;
  description?: string;
  category?: string;
  policy_type?: 'text' | 'voice' | 'general';
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
  // Voice Policy controls
  allow_connect?: PolicyValue;
  allow_speak?: PolicyValue;
  allow_video?: PolicyValue;
  allow_stream?: PolicyValue;
  allow_soundboard?: PolicyValue;
  allow_voice_activity?: PolicyValue;
  allow_priority_speaker?: PolicyValue;
  allow_mute_members?: PolicyValue;
  allow_deafen_members?: PolicyValue;
  allow_move_members?: PolicyValue;
  allowed_domains?: string[];
  delete_violations?: boolean;
  warn_on_violation?: boolean;
  log_violations?: boolean;
  send_dm_warning?: boolean;
  warning_message?: string | null;
}

export interface ModLogSettings {
  mod_log_channel_id: string | null;
  mod_log_events: string[];
  channel_status?: {
    status: 'ok' | 'missing_channel' | 'missing_permissions' | 'bot_offline' | 'not_configured' | 'error';
    channel_name: string | null;
    can_view: boolean;
    can_send: boolean;
    can_embed: boolean;
    warning: string | null;
  };
}

export interface ModerationChannelInfo {
  id: string;
  name: string;
  type: 'text' | 'voice' | 'stage' | 'forum';
  category: string;
  category_id?: string | null;
  position: number;
  has_override: boolean;
  preset_name: string;
  enabled: boolean;
}

export interface ModerationCase {
  id?: number;
  case_number: number;
  case_id?: string;
  target_user_id: string;
  target_username: string;
  target_avatar_url?: string | null;
  moderator_user_id: string;
  moderator_username: string;
  action: string;
  reason: string;
  duration?: number | null;
  channel_id?: string | null;
  channel_name?: string | null;
  rule?: string | null;
  policy_name?: string | null;
  warning_id?: string | null;
  severity?: string;
  dm_status?: string;
  discord_log_status?: string;
  executor?: string;
  created_at: string;
}

export interface ModerationExemption {
  id: number;
  target_type: 'user' | 'role' | 'bot' | 'webhook';
  target_id: string;
  target_name?: string | null;
  scope: 'global' | 'category' | 'channel' | 'channel_type';
  scope_id?: string | null;
  scope_name?: string | null;
  channel_type?: string | null;
  bypass_all: boolean;
  bypass_text: boolean;
  bypass_links: boolean;
  bypass_images: boolean;
  bypass_videos: boolean;
  bypass_files: boolean;
  bypass_stickers: boolean;
  bypass_mentions: boolean;
  bypass_spam: boolean;
  bypass_keywords: boolean;
  bypass_invites: boolean;
  bypass_warnings: boolean;
  bypass_timeout: boolean;
  bypass_kick: boolean;
  bypass_ban: boolean;
  created_at?: string | null;
}

export interface AutomodRule {
  id: number;
  rule_type: string;
  name: string;
  description?: string | null;
  enabled: boolean;
  scope: string;
  scope_id?: string | null;
  scope_name?: string | null;
  threshold: number;
  time_window_seconds: number;
  action: string;
  action_duration?: number | null;
  send_dm: boolean;
  log_event: boolean;
  custom_keywords?: string[] | null;
  allowed_invites?: string[] | null;
  cooldown_seconds: number;
  created_at?: string | null;
}

export interface WarningRecord {
  id: number;
  warning_id: string;
  case_id: string;
  user_id: string;
  username: string;
  channel_id?: string | null;
  channel_name?: string | null;
  rule: string;
  reason: string;
  moderator: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  points: number;
  status: 'active' | 'expired' | 'revoked';
  action_taken: string;
  dm_status: string;
  created_at?: string | null;
  expires_at?: string | null;
  revoked_at?: string | null;
  revoked_by?: string | null;
}

export interface WarningEscalationRule {
  id: number;
  threshold: number;
  mode: 'count' | 'points';
  action: 'warn' | 'timeout' | 'kick' | 'ban';
  duration?: number | null;
  send_dm: boolean;
  delete_message_history_days?: number;
  reason_template?: string | null;
}

export interface GuildTargetMember {
  id: string;
  username: string;
  display_name: string;
  bot: boolean;
  roles: string[];
  permissions: {
    administrator?: boolean;
    manage_guild?: boolean;
    manage_messages?: boolean;
    moderate_members?: boolean;
    kick_members?: boolean;
    ban_members?: boolean;
  };
}

export interface GuildTargetRole {
  id: string;
  name: string;
  color: string;
  position: number;
  permissions: {
    administrator?: boolean;
    manage_guild?: boolean;
    manage_messages?: boolean;
    moderate_members?: boolean;
    kick_members?: boolean;
    ban_members?: boolean;
  };
}

export interface GuildTargets {
  roles: GuildTargetRole[];
  members: GuildTargetMember[];
  bots: GuildTargetMember[];
  channels: { id: string; name: string; type: string; category: string; category_id?: string | null }[];
  categories: { id: string; name: string }[];
}

export interface ModerationOverviewStats {
  active_warnings: number;
  warnings_today: number;
  timeouts_today: number;
  kicks_today: number;
  bans_today: number;
  messages_blocked: number;
  cases_today: number;
  top_violations: { reason: string; count: number }[];
  recent_cases: {
    case_number: number;
    case_id: string;
    target_username: string;
    action: string;
    reason: string;
    channel_name?: string | null;
    created_at?: string | null;
  }[];
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

export type YouTubeEventType = 'upload' | 'scheduled_live' | 'live_started' | 'premiere';

export interface NotificationTemplate {
  id?: number;
  event_type: YouTubeEventType;
  title_template: string;
  description_template: string;
  mention_role?: string | null;
  footer_text?: string | null;
  show_thumbnail: boolean;
  show_timestamp: boolean;
  enable_button: boolean;
  updated_at?: string | null;
}



export interface ServerGreetingSettings {
  id: number;
  guild_id: string;
  welcome_enabled: boolean;
  welcome_channel_id: string | null;
  welcome_title: string | null;
  welcome_description: string | null;
  welcome_footer: string | null;
  welcome_mention_user: boolean;
  welcome_show_avatar: boolean;
  welcome_show_server_icon: boolean;
  welcome_show_member_count: boolean;
  welcome_show_timestamp: boolean;
  welcome_use_embed: boolean;
  goodbye_enabled: boolean;
  goodbye_channel_id: string | null;
  goodbye_title: string | null;
  goodbye_description: string | null;
  goodbye_footer: string | null;
  goodbye_mention_user: boolean;
  goodbye_show_avatar: boolean;
  goodbye_show_server_icon: boolean;
  goodbye_show_member_count: boolean;
  goodbye_show_timestamp: boolean;
  goodbye_use_embed: boolean;
  allow_mass_mentions: boolean;

  // Rules Delivery
  rules_delivery_enabled?: boolean;
  rules_source?: 'rules_channel' | 'custom_message' | 'both';
  rules_channel_id?: string | null;
  rules_title?: string | null;
  rules_description?: string | null;
  rules_footer?: string | null;
  rules_button_text?: string | null;

  // Auto Role
  auto_role_enabled?: boolean;
  auto_role_id?: string | null;

  // Welcome DM
  welcome_dm_enabled?: boolean;
  welcome_dm_title?: string | null;
  welcome_dm_description?: string | null;
  welcome_dm_footer?: string | null;
  welcome_dm_use_embed?: boolean;
  welcome_dm_show_avatar?: boolean;
  welcome_dm_show_server_icon?: boolean;
  welcome_dm_show_timestamp?: boolean;

  // Goodbye DM
  goodbye_dm_enabled?: boolean;
  goodbye_dm_title?: string | null;
  goodbye_dm_description?: string | null;
  goodbye_dm_footer?: string | null;
  goodbye_dm_use_embed?: boolean;
  goodbye_dm_show_avatar?: boolean;
  goodbye_dm_show_server_icon?: boolean;
  goodbye_dm_show_timestamp?: boolean;

  created_at?: string | null;
  updated_at?: string | null;
}

export interface ServerInviteSettings {
  id: number;
  guild_id: string;
  invite_channel_id: string | null;
  invite_code: string | null;
  invite_url: string | null;
  is_active: boolean;
  max_age: number;
  max_uses: number;
  temporary: boolean;
  verification_status: string;
  verification_error: string | null;
  last_verified_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface GuildRoleOption {
  id: string;
  name: string;
  color: string;
  position: number;
  member_count: number;
  is_assignable: boolean;
  is_managed: boolean;
}

export interface GreetingChannelTelemetry {
  status: 'ok' | 'not_configured' | 'bot_offline' | 'missing_channel' | 'permission_denied';
  channel_name: string | null;
  can_view: boolean;
  can_send: boolean;
  can_embed: boolean;
  warning: string | null;
}

export interface GreetingRecentActivity {
  id: string;
  timestamp: string;
  event_type: string;
  username: string;
  user_id: string;
  channel_id: string | null;
  channel_name: string;
  status: 'delivered' | 'failed';
  error_message?: string | null;
  is_test?: boolean;
}

export interface GreetingChannelOption {
  id: string;
  name: string;
  type: string;
  category: string;
  category_id?: string | null;
  position: number;
  can_view: boolean;
  can_send: boolean;
  can_embed: boolean;
  is_selectable: boolean;
}

export interface GreetingsResponse {
  settings: ServerGreetingSettings;
  invite?: ServerInviteSettings;
  server: {
    server_id: string;
    server_name: string;
    member_count: number;
    server_icon: string | null;
    bot_online: boolean;
  };
  welcome_channel_status: GreetingChannelTelemetry;
  goodbye_channel_status: GreetingChannelTelemetry;
  rules_channel_status?: {
    status: string;
    channel_name: string | null;
    can_view: boolean;
    warning?: string | null;
  };
  recent_activity: GreetingRecentActivity[];
  stats: {
    welcome_sent_today: number;
    goodbye_sent_today: number;
    welcome_dms_today?: number;
    goodbye_dms_today?: number;
    rules_delivered_today?: number;
    roles_assigned_today?: number;
    dm_failures_today?: number;
  };
}
