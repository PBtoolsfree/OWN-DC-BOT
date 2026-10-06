import React, { useState } from 'react';
import { ServerGreetingSettings } from '../../types';
import { Mail, MessageSquare, Play, RotateCcw, ShieldCheck, Tag } from 'lucide-react';
import { ConfirmModal } from '../ConfirmModal';

interface DirectMessagesCardProps {
  settings: ServerGreetingSettings;
  onChange: (updates: Partial<ServerGreetingSettings>) => void;
  onTestWelcomeDM: () => void;
  onTestGoodbyeDM: () => void;
  onResetWelcomeDM: () => void;
  onResetGoodbyeDM: () => void;
  serverName?: string;
}

const WELCOME_DM_VARS = [
  '{username}',
  '{display_name}',
  '{user_mention}',
  '{server_name}',
  '{member_count}',
  '{inviter}',
  '{rules_url}',
  '{invite_url}',
];

const GOODBYE_DM_VARS = [
  '{username}',
  '{display_name}',
  '{server_name}',
  '{member_count}',
  '{invite_url}',
];

export const DirectMessagesCard: React.FC<DirectMessagesCardProps> = ({
  settings,
  onChange,
  onTestWelcomeDM,
  onTestGoodbyeDM,
  onResetWelcomeDM,
  onResetGoodbyeDM,
  serverName = 'PB HERO SERVER',
}) => {
  const [resetModalType, setResetModalType] = useState<'welcome_dm' | 'goodbye_dm' | null>(null);

  const insertVariable = (field: 'welcome_dm_description' | 'goodbye_dm_description', varName: string) => {
    const current = (settings[field] as string) || '';
    onChange({ [field]: current ? `${current} ${varName}` : varName });
  };

  return (
    <div className="space-y-6">
      {/* Privacy Notice Banner */}
      <div className="p-4 bg-blue-950/40 border border-blue-900/60 rounded-2xl flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
        <div className="text-xs text-blue-200/90 space-y-1">
          <p className="font-bold text-blue-300">Discord Member Privacy & DM Handling</p>
          <p>
            PB HERO strictly respects Discord user privacy settings. If a member has direct messages disabled from server members or blocks bot interactions, direct messages fail safely reporting <em>DM unavailable</em> in your server events without interrupting the public onboarding flow.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 1. Welcome DM Card */}
        <div className="bg-gray-850 rounded-2xl border border-gray-800 shadow-xl overflow-hidden flex flex-col">
          <div className="p-6 border-b border-gray-800 flex items-center justify-between gap-4 bg-gray-900/60">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-emerald-500/10 rounded-xl border border-emerald-500/20 text-emerald-400">
                <Mail className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">Welcome Direct Message</h2>
                <p className="text-xs text-gray-400">
                  Sends a private message to a new member after they join.
                </p>
              </div>
            </div>

            <label className="relative inline-flex items-center cursor-pointer shrink-0">
              <input
                type="checkbox"
                checked={Boolean(settings.welcome_dm_enabled)}
                onChange={(e) => onChange({ welcome_dm_enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
            </label>
          </div>

          <div className="p-6 space-y-5 flex-1">
            <div className="flex flex-wrap gap-4 text-xs font-semibold text-gray-300 bg-gray-900/50 p-3 rounded-xl border border-gray-800">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.welcome_dm_use_embed ?? true}
                  onChange={(e) => onChange({ welcome_dm_use_embed: e.target.checked })}
                  className="rounded bg-gray-800 border-gray-700 text-emerald-600 focus:ring-emerald-500"
                />
                Use Rich Embed
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.welcome_dm_show_avatar ?? true}
                  onChange={(e) => onChange({ welcome_dm_show_avatar: e.target.checked })}
                  className="rounded bg-gray-800 border-gray-700 text-emerald-600 focus:ring-emerald-500"
                />
                Show Avatar
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.welcome_dm_show_server_icon ?? true}
                  onChange={(e) => onChange({ welcome_dm_show_server_icon: e.target.checked })}
                  className="rounded bg-gray-800 border-gray-700 text-emerald-600 focus:ring-emerald-500"
                />
                Server Icon
              </label>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                DM Title
              </label>
              <input
                type="text"
                value={settings.welcome_dm_title ?? ''}
                onChange={(e) => onChange({ welcome_dm_title: e.target.value })}
                placeholder={`👋 Welcome to ${serverName}!`}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                  DM Description
                </label>
                <span className="text-[11px] text-gray-500">Supports Markdown & URLs</span>
              </div>
              <textarea
                rows={5}
                value={settings.welcome_dm_description ?? ''}
                onChange={(e) => onChange({ welcome_dm_description: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl p-3 text-sm text-white font-mono focus:outline-none focus:border-emerald-500"
              />

              {/* Variable chips */}
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <Tag className="w-3.5 h-3.5 text-gray-500" />
                <span className="text-[11px] text-gray-500 mr-1">Insert:</span>
                {WELCOME_DM_VARS.map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => insertVariable('welcome_dm_description', v)}
                    className="px-2 py-0.5 bg-gray-800 hover:bg-emerald-950/60 hover:text-emerald-300 text-gray-400 border border-gray-700 rounded text-[11px] font-mono transition-colors"
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                DM Footer
              </label>
              <input
                type="text"
                value={settings.welcome_dm_footer ?? ''}
                onChange={(e) => onChange({ welcome_dm_footer: e.target.value })}
                placeholder="PB HERO SERVER"
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-gray-800">
              <button
                type="button"
                onClick={() => setResetModalType('welcome_dm')}
                className="text-xs text-gray-400 hover:text-white flex items-center gap-1.5 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset Template
              </button>

              <button
                type="button"
                onClick={onTestWelcomeDM}
                className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-md shadow-emerald-600/20 transition-all"
              >
                <Play className="w-3.5 h-3.5" />
                Test Welcome DM
              </button>
            </div>
          </div>
        </div>

        {/* 2. Goodbye DM Card */}
        <div className="bg-gray-850 rounded-2xl border border-gray-800 shadow-xl overflow-hidden flex flex-col">
          <div className="p-6 border-b border-gray-800 flex items-center justify-between gap-4 bg-gray-900/60">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-amber-500/10 rounded-xl border border-amber-500/20 text-amber-400">
                <MessageSquare className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">Goodbye Direct Message</h2>
                <p className="text-xs text-gray-400">
                  Attempts to send a private farewell message when a member leaves.
                </p>
              </div>
            </div>

            <label className="relative inline-flex items-center cursor-pointer shrink-0">
              <input
                type="checkbox"
                checked={Boolean(settings.goodbye_dm_enabled)}
                onChange={(e) => onChange({ goodbye_dm_enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-600"></div>
            </label>
          </div>

          <div className="p-6 space-y-5 flex-1">
            <div className="flex flex-wrap gap-4 text-xs font-semibold text-gray-300 bg-gray-900/50 p-3 rounded-xl border border-gray-800">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.goodbye_dm_use_embed ?? true}
                  onChange={(e) => onChange({ goodbye_dm_use_embed: e.target.checked })}
                  className="rounded bg-gray-800 border-gray-700 text-amber-600 focus:ring-amber-500"
                />
                Use Rich Embed
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.goodbye_dm_show_avatar ?? true}
                  onChange={(e) => onChange({ goodbye_dm_show_avatar: e.target.checked })}
                  className="rounded bg-gray-800 border-gray-700 text-amber-600 focus:ring-amber-500"
                />
                Show Avatar
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.goodbye_dm_show_server_icon ?? true}
                  onChange={(e) => onChange({ goodbye_dm_show_server_icon: e.target.checked })}
                  className="rounded bg-gray-800 border-gray-700 text-amber-600 focus:ring-amber-500"
                />
                Server Icon
              </label>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                DM Title
              </label>
              <input
                type="text"
                value={settings.goodbye_dm_title ?? ''}
                onChange={(e) => onChange({ goodbye_dm_title: e.target.value })}
                placeholder="👋 Goodbye {display_name}"
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                  DM Description
                </label>
                <span className="text-[11px] text-gray-500">Includes Rejoin Invite</span>
              </div>
              <textarea
                rows={5}
                value={settings.goodbye_dm_description ?? ''}
                onChange={(e) => onChange({ goodbye_dm_description: e.target.value })}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl p-3 text-sm text-white font-mono focus:outline-none focus:border-amber-500"
              />

              {/* Variable chips */}
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <Tag className="w-3.5 h-3.5 text-gray-500" />
                <span className="text-[11px] text-gray-500 mr-1">Insert:</span>
                {GOODBYE_DM_VARS.map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => insertVariable('goodbye_dm_description', v)}
                    className="px-2 py-0.5 bg-gray-800 hover:bg-amber-950/60 hover:text-amber-300 text-gray-400 border border-gray-700 rounded text-[11px] font-mono transition-colors"
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                DM Footer
              </label>
              <input
                type="text"
                value={settings.goodbye_dm_footer ?? ''}
                onChange={(e) => onChange({ goodbye_dm_footer: e.target.value })}
                placeholder="PB HERO SERVER"
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
              />
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-gray-800">
              <button
                type="button"
                onClick={() => setResetModalType('goodbye_dm')}
                className="text-xs text-gray-400 hover:text-white flex items-center gap-1.5 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset Template
              </button>

              <button
                type="button"
                onClick={onTestGoodbyeDM}
                className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-md shadow-amber-600/20 transition-all"
              >
                <Play className="w-3.5 h-3.5" />
                Test Goodbye DM
              </button>
            </div>
          </div>
        </div>
      </div>

      <ConfirmModal
        isOpen={resetModalType !== null}
        title={resetModalType === 'welcome_dm' ? 'Reset Welcome DM to default?' : 'Reset Goodbye DM to default?'}
        message="This will reset title, description, and footer back to default templates. Unsaved changes to other fields will not be affected."
        confirmText="Reset Template"
        
        onConfirm={() => {
          if (resetModalType === 'welcome_dm') onResetWelcomeDM();
          else if (resetModalType === 'goodbye_dm') onResetGoodbyeDM();
          setResetModalType(null);
        }}
        onCancel={() => setResetModalType(null)}
      />
    </div>
  );
};

