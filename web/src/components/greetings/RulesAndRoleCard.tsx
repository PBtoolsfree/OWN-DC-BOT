import React, { useState } from 'react';
import { ServerGreetingSettings, GreetingChannelOption, GuildRoleOption } from '../../types';
import { BookOpen, Shield, RotateCcw, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { ConfirmModal } from '../ConfirmModal';

interface RulesAndRoleCardProps {
  settings: ServerGreetingSettings;
  onChange: (updates: Partial<ServerGreetingSettings>) => void;
  channels: GreetingChannelOption[];
  roles: GuildRoleOption[];
  onResetRules: () => void;
  serverName?: string;
  serverId?: string;
}

export const RulesAndRoleCard: React.FC<RulesAndRoleCardProps> = ({
  settings,
  onChange,
  channels,
  roles,
  onResetRules,
  serverName = 'PB HERO SERVER',
  serverId = '0',
}) => {
  const [showResetModal, setShowResetModal] = useState(false);

  const selectedRole = roles.find((r) => r.id === settings.auto_role_id);
  const rulesChannelUrl = settings.rules_channel_id
    ? `https://discord.com/channels/${serverId}/${settings.rules_channel_id}`
    : '[Rules channel not selected]';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* 1. Rules Delivery Card */}
      <div className="bg-gray-850 rounded-2xl border border-gray-800 shadow-xl overflow-hidden flex flex-col">
        <div className="p-6 border-b border-gray-800 flex items-center justify-between gap-4 bg-gray-900/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-fuchsia-500/10 rounded-xl border border-fuchsia-500/20 text-fuchsia-400">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Rules Delivery</h2>
              <p className="text-xs text-gray-400">
                Automatically delivers server rules to new members upon joining.
              </p>
            </div>
          </div>

          <label className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={Boolean(settings.rules_delivery_enabled)}
              onChange={(e) => onChange({ rules_delivery_enabled: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-fuchsia-600"></div>
          </label>
        </div>

        <div className="p-6 space-y-5 flex-1">
          {/* Rules Delivery Ownership notice / toggle */}
          <div className="bg-gray-900/60 p-3.5 rounded-xl border border-gray-800 text-xs space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-gray-200">Include rules in Welcome DM</span>
              <label className="relative inline-flex items-center cursor-pointer shrink-0">
                <input
                  type="checkbox"
                  checked={settings.welcome_dm_include_rules ?? true}
                  onChange={(e) => onChange({ welcome_dm_include_rules: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-fuchsia-600"></div>
              </label>
            </div>
            <p className="text-[11px] text-gray-400 leading-relaxed">
              {settings.welcome_dm_include_rules ?? true
                ? "ON: Rules appear inside Welcome DM ({rules_url}). Standalone Rules message is skipped to prevent duplicate delivery."
                : "OFF: Rules link is excluded from Welcome DM. Standalone Rules message will be sent if Rules Delivery is enabled."}
            </p>
          </div>

          {/* Rules Source Selector */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
              Rules Source
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'rules_channel', label: 'Channel Link' },
                { id: 'custom_message', label: 'Custom Message' },
                { id: 'both', label: 'Link + Custom' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onChange({ rules_source: opt.id as any })}
                  className={`py-2 px-3 rounded-xl text-xs font-bold border transition-all ${
                    (settings.rules_source || 'rules_channel') === opt.id
                      ? 'bg-fuchsia-600 text-white border-fuchsia-500 shadow-md shadow-fuchsia-600/20'
                      : 'bg-gray-900 text-gray-400 border-gray-700 hover:text-white'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Rules Channel Selector */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
              Official Rules Channel
            </label>
            <select
              value={settings.rules_channel_id || ''}
              onChange={(e) => onChange({ rules_channel_id: e.target.value || null })}
              className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-fuchsia-500"
            >
              <option value="">-- Select Discord Rules Channel --</option>
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  #{ch.name} ({ch.category})
                </option>
              ))}
            </select>
            {settings.rules_channel_id && (
              <p className="text-[11px] text-gray-500 truncate font-mono">
                Link: <span className="text-fuchsia-400">{rulesChannelUrl}</span>
              </p>
            )}
          </div>

          {/* Custom Message Fields (if custom or both) */}
          {(settings.rules_source === 'custom_message' || settings.rules_source === 'both') && (
            <div className="space-y-4 pt-2 border-t border-gray-800">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                  Rules Embed Title
                </label>
                <input
                  type="text"
                  value={settings.rules_title ?? ''}
                  onChange={(e) => onChange({ rules_title: e.target.value })}
                  placeholder={`📜 ${serverName} RULES`}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-fuchsia-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                  Rules Description
                </label>
                <textarea
                  rows={4}
                  value={settings.rules_description ?? ''}
                  onChange={(e) => onChange({ rules_description: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl p-3 text-sm text-white font-mono focus:outline-none focus:border-fuchsia-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                  Footer
                </label>
                <input
                  type="text"
                  value={settings.rules_footer ?? ''}
                  onChange={(e) => onChange({ rules_footer: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-fuchsia-500"
                />
              </div>
            </div>
          )}

          <div className="pt-2">
            <button
              type="button"
              onClick={() => setShowResetModal(true)}
              className="text-xs text-gray-400 hover:text-white flex items-center gap-1.5 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Rules to Default
            </button>
          </div>
        </div>
      </div>

      {/* 2. Auto Role Card */}
      <div className="bg-gray-850 rounded-2xl border border-gray-800 shadow-xl overflow-hidden flex flex-col">
        <div className="p-6 border-b border-gray-800 flex items-center justify-between gap-4 bg-gray-900/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-cyan-500/10 rounded-xl border border-cyan-500/20 text-cyan-400">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Default Auto Role</h2>
              <p className="text-xs text-gray-400">
                Automatically assigns a role when a new member joins the server.
              </p>
            </div>
          </div>

          <label className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={Boolean(settings.auto_role_enabled)}
              onChange={(e) => onChange({ auto_role_enabled: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-600"></div>
          </label>
        </div>

        <div className="p-6 space-y-5 flex-1">
          <div className="space-y-2">
            <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
              Default Member Role
            </label>
            <select
              value={settings.auto_role_id || ''}
              onChange={(e) => onChange({ auto_role_id: e.target.value || null })}
              className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-cyan-500"
            >
              <option value="">-- No Auto Role Configured --</option>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  @{r.name} ({r.member_count} members) {r.is_assignable ? '✅' : '❌ (Hierarchy)'}
                </option>
              ))}
            </select>
          </div>

          {/* Role Status Telemetry */}
          {selectedRole && (
            <div className={`p-4 rounded-xl border text-xs space-y-2 ${
              selectedRole.is_assignable
                ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-300'
                : 'bg-rose-950/30 border-rose-800/60 text-rose-300'
            }`}>
              <div className="flex items-center gap-2 font-bold">
                {selectedRole.is_assignable ? (
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                ) : (
                  <XCircle className="w-4 h-4 text-rose-400" />
                )}
                <span>Role Assignability: {selectedRole.is_assignable ? 'Assignable ✅' : 'Not Assignable ❌'}</span>
              </div>

              {!selectedRole.is_assignable && (
                <p className="text-rose-200/90 text-xs">
                  ⚠️ Discord role hierarchy restriction: The <strong>PB HERO Bot</strong> role is positioned below @{selectedRole.name} or lacks the <em>Manage Roles</em> permission. To allow assignment, drag the bot role above this role in Discord Server Settings.
                </p>
              )}
            </div>
          )}

          <div className="p-4 bg-gray-900/50 border border-gray-800 rounded-xl text-xs text-gray-400 space-y-2">
            <div className="flex items-center gap-1.5 font-bold text-gray-300">
              <AlertTriangle className="w-4 h-4 text-cyan-400" />
              <span>How Auto Role Works</span>
            </div>
            <p>
              When a new member completes joining, PB HERO will attempt to assign this role. If the member leaves or if the bot lacks permissions, the failure is safely recorded in Server Events without halting the welcome flow.
            </p>
          </div>
        </div>
      </div>

      <ConfirmModal
        isOpen={showResetModal}
        title="Reset Rules Settings?"
        message="This will reset rules title, description, and footer back to default templates. Unsaved changes to other fields will not be affected."
        confirmText="Reset Rules"
        
        onConfirm={() => {
          setShowResetModal(false);
          onResetRules();
        }}
        onCancel={() => setShowResetModal(false)}
      />
    </div>
  );
};

