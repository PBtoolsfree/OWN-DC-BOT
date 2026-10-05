import { useEffect, useState } from 'react';
import { moderationApi } from '../api/moderation';
import { channelsApi } from '../api/channels';
import { DiscordChannel, ModLogSettings } from '../types';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { toast } from '../hooks/useToast';
import {
  Sliders,
  ShieldAlert,
  Hash,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Save,
  Bell,
  RefreshCw,
} from 'lucide-react';

interface EventToggleConfig {
  key: string;
  label: string;
  description: string;
  category: 'AUTOMOD INTERCEPTIONS' | 'PUNISHMENTS' | 'INVITES' | 'SYSTEM';
}

const LOG_EVENTS: EventToggleConfig[] = [
  // AUTOMOD INTERCEPTIONS
  {
    key: 'policy_violation',
    label: 'Policy Violation',
    description: 'General channel rule violations and denied message content',
    category: 'AUTOMOD INTERCEPTIONS',
  },
  {
    key: 'blocked_link',
    label: 'Blocked Link',
    description: 'Unauthorized URLs, domain allowlist violations, and invite links',
    category: 'AUTOMOD INTERCEPTIONS',
  },
  {
    key: 'blocked_attachment',
    label: 'Blocked Attachment',
    description: 'Images, videos, or files uploaded to restricted channels',
    category: 'AUTOMOD INTERCEPTIONS',
  },
  {
    key: 'blocked_mention',
    label: 'Blocked Mention',
    description: 'Unauthorized @everyone, @here, or role pings',
    category: 'AUTOMOD INTERCEPTIONS',
  },
  {
    key: 'message_delete',
    label: 'Message Delete',
    description: 'Messages purged or deleted by AutoMod enforcement',
    category: 'AUTOMOD INTERCEPTIONS',
  },

  // PUNISHMENTS
  {
    key: 'warning',
    label: 'Warning Issued',
    description: 'Bot automated warnings delivered to violating members',
    category: 'PUNISHMENTS',
  },
  {
    key: 'timeout',
    label: 'Timeout / Mute',
    description: 'Members timed out due to repeat violations or manual mod action',
    category: 'PUNISHMENTS',
  },
  {
    key: 'kick',
    label: 'Kick',
    description: 'Members kicked from the guild',
    category: 'PUNISHMENTS',
  },
  {
    key: 'ban',
    label: 'Ban',
    description: 'Banned accounts from the Discord server',
    category: 'PUNISHMENTS',
  },
  {
    key: 'unban',
    label: 'Unban',
    description: 'Revoked bans or pardoned members',
    category: 'PUNISHMENTS',
  },
  {
    key: 'user_warning',
    label: 'User DM Warning',
    description: 'Direct message notifications dispatched to users',
    category: 'PUNISHMENTS',
  },

  // INVITES
  {
    key: 'invite_join',
    label: 'Invite Join Attribution',
    description: 'Real-time Discord alerts when a member joins via an attributed or tracked invite',
    category: 'INVITES',
  },
  {
    key: 'invite_create',
    label: 'Invite Created',
    description: 'Notifications when new server invite links are generated',
    category: 'INVITES',
  },
  {
    key: 'invite_revoke',
    label: 'Invite Revoked',
    description: 'Audit logs when server invite links are deleted or revoked',
    category: 'INVITES',
  },
  {
    key: 'invite_expire',
    label: 'Invite Expired',
    description: 'Alerts when temporary or expiring invite links reach their time limit',
    category: 'INVITES',
  },

  // SYSTEM
  {
    key: 'manual_action',
    label: 'Manual Moderator Action',
    description: 'Slash commands and administrative actions run by human mods',
    category: 'SYSTEM',
  },
  {
    key: 'bot_error',
    label: 'Bot Error',
    description: 'Internal Discord bot exceptions or API permission errors',
    category: 'SYSTEM',
  },
  {
    key: 'rule_error',
    label: 'Rule Error',
    description: 'Syntax or evaluation error in custom rule conditions',
    category: 'SYSTEM',
  },
  {
    key: 'permission_error',
    label: 'Permission Error',
    description: 'Role hierarchy or Discord permission conflicts preventing an action',
    category: 'SYSTEM',
  },
];

export default function ModeratorSettings() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [channels, setChannels] = useState<DiscordChannel[]>([]);
  const [settings, setSettings] = useState<ModLogSettings>({
    mod_log_channel_id: null,
    mod_log_events: [],
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const [chList, logSettings] = await Promise.all([
        channelsApi.getChannels(),
        moderationApi.getModLogSettings(),
      ]);
      setChannels(chList.filter((c) => c.type === 'text'));
      setSettings(logSettings);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load moderation settings.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggleEvent = (key: string) => {
    setSettings((prev) => {
      const exists = prev.mod_log_events.includes(key);
      return {
        ...prev,
        mod_log_events: exists
          ? prev.mod_log_events.filter((e) => e !== key)
          : [...prev.mod_log_events, key],
      };
    });
  };

  const handleSelectAll = (category: string) => {
    const catKeys = LOG_EVENTS.filter((e) => e.category === category).map((e) => e.key);
    const allSelected = catKeys.every((k) => settings.mod_log_events.includes(k));
    setSettings((prev) => ({
      ...prev,
      mod_log_events: allSelected
        ? prev.mod_log_events.filter((k) => !catKeys.includes(k))
        : Array.from(new Set([...prev.mod_log_events, ...catKeys])),
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await moderationApi.updateModLogSettings({
        mod_log_channel_id: settings.mod_log_channel_id,
        mod_log_events: settings.mod_log_events,
      });
      toast.success('Moderator log settings saved successfully.');
      await loadData();
    } catch (err: any) {
      toast.error(err.message || 'Failed to save log settings.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-gray-800 animate-pulse rounded" />
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  const status = settings.channel_status;
  const categories = ['AUTOMOD INTERCEPTIONS', 'PUNISHMENTS', 'INVITES', 'SYSTEM'] as const;

  return (
    <div className="space-y-8 animate-fade-in max-w-5xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
            <Sliders className="w-7 h-7 text-[#5865F2]" />
            <span>Moderator & Auto-Mod Log Settings</span>
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Configure real-time Discord mod-log channels, incident embeds, and security event triggers.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-[#5865F2]/20 self-start md:self-auto disabled:opacity-50"
        >
          {saving ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          <span>{saving ? 'Saving...' : 'Save Settings'}</span>
        </button>
      </div>

      {/* Discord Log Channel Configuration Card */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6">
        <div className="border-b border-gray-800 pb-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Hash className="w-5 h-5 text-[#5865F2]" />
              <span>Auto-Moderation Log Channel</span>
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">
              The designated Discord text channel where the bot sends structured audit embeds for policy violations.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
          {/* Channel Selector */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-gray-300 block">
              Destination Discord Channel
            </label>
            <select
              value={settings.mod_log_channel_id || ''}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  mod_log_channel_id: e.target.value ? e.target.value : null,
                })
              }
              className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-4 py-3 text-xs text-white focus:outline-none focus:border-[#5865F2]"
            >
              <option value="">— Disabled (Dashboard Database Logs Only) —</option>
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  #{ch.name} {ch.category ? `(${ch.category})` : ''}
                </option>
              ))}
            </select>
            <p className="text-[11px] text-gray-500 leading-relaxed">
              If disabled, moderation events will continue to be safely stored in the web dashboard logs without posting to Discord.
            </p>
          </div>

          {/* Bot Permissions & Verification Box */}
          <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-gray-300 uppercase tracking-wider">
                Bot Channel Access
              </span>
              {status?.status === 'ok' && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-semibold">
                  ACTIVE & READY
                </span>
              )}
              {status?.status === 'not_configured' && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-gray-800 text-gray-400 font-semibold">
                  NOT CONFIGURED
                </span>
              )}
              {status?.status === 'missing_channel' && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-semibold">
                  CHANNEL DELETED
                </span>
              )}
              {status?.status === 'missing_permissions' && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 font-semibold">
                  PERMISSIONS MISSING
                </span>
              )}
              {status?.status === 'bot_offline' && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-semibold">
                  BOT OFFLINE
                </span>
              )}
            </div>

            {settings.mod_log_channel_id ? (
              <div className="space-y-2 pt-1 text-xs">
                <div className="flex items-center justify-between text-gray-400">
                  <span>View Channel</span>
                  {status?.can_view ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400" />
                  )}
                </div>
                <div className="flex items-center justify-between text-gray-400">
                  <span>Send Messages</span>
                  {status?.can_send ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400" />
                  )}
                </div>
                <div className="flex items-center justify-between text-gray-400">
                  <span>Embed Links</span>
                  {status?.can_embed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400" />
                  )}
                </div>

                {status?.warning && (
                  <div className="mt-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
                    <span>{status.warning}</span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-gray-500 italic py-2">
                Select a channel to verify bot send & embed permissions.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Log Settings Event Toggles */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6">
        <div className="border-b border-gray-800 pb-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Bell className="w-5 h-5 text-[#5865F2]" />
                <span>Event Notification Filter Toggles</span>
              </h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Select which moderation actions and security violations are dispatched to the Discord log channel.
              </p>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-xs text-blue-300 flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              <strong className="text-blue-200">How Event Filters Work:</strong> These toggles control{' '}
              <span className="text-white underline">which moderation events are sent to the Discord Auto-Mod log channel</span>.
              They do <span className="text-white font-bold">NOT</span> control whether the moderation action itself occurs.
              All active channel policies, automod filters, warnings, timeouts, and cases are always enforced and logged to the web dashboard.
            </p>
          </div>
        </div>

        <div className="space-y-6">
          {categories.map((cat) => {
            const catEvents = LOG_EVENTS.filter((e) => e.category === cat);
            const allSelected = catEvents.every((e) => settings.mod_log_events.includes(e.key));

            return (
              <div key={cat} className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-[#5865F2]" />
                    <span>{cat}</span>
                  </h3>
                  <button
                    type="button"
                    onClick={() => handleSelectAll(cat)}
                    className="text-[11px] text-[#5865F2] hover:underline font-semibold"
                  >
                    {allSelected ? 'Deselect All' : 'Select All'}
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {catEvents.map((evt) => {
                    const isChecked = settings.mod_log_events.includes(evt.key);
                    return (
                      <div
                        key={evt.key}
                        onClick={() => handleToggleEvent(evt.key)}
                        className={`flex items-start justify-between p-3.5 rounded-xl border cursor-pointer transition-all ${
                          isChecked
                            ? 'bg-[#5865F2]/10 border-[#5865F2]/40 text-white'
                            : 'bg-[#0B0E14] border-gray-800 text-gray-400 hover:border-gray-700'
                        }`}
                      >
                        <div className="pr-3 space-y-0.5">
                          <span className={`text-xs font-bold block ${isChecked ? 'text-white' : 'text-gray-300'}`}>
                            {evt.label}
                          </span>
                          <span className="text-[11px] text-gray-500 leading-snug block">
                            {evt.description}
                          </span>
                        </div>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {}} // handled by parent onClick
                          className="mt-0.5 rounded border-gray-700 bg-gray-900 text-[#5865F2] cursor-pointer"
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
