import { useEffect, useState } from 'react';
import { greetingsApi } from '../api/greetings';
import {
  GreetingsResponse,
  GreetingChannelOption,
  GuildRoleOption,
  ServerGreetingSettings,
} from '../types';
import { ConfirmModal } from '../components/ConfirmModal';
import { DiscordPreview } from '../components/DiscordPreview';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { InviteManagerCard } from '../components/greetings/InviteManagerCard';
import { RulesAndRoleCard } from '../components/greetings/RulesAndRoleCard';
import { DirectMessagesCard } from '../components/greetings/DirectMessagesCard';
import { RecentActivityTable } from '../components/greetings/RecentActivityTable';
import { toast } from '../hooks/useToast';
import {
  UserPlus,
  UserMinus,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Play,
  RotateCcw,
  Save,
  Server,
  Sparkles,
  BookOpen,
  Mail,
  Link2,
  History,
  Tag,
} from 'lucide-react';

const WELCOME_VARIABLES = [
  { key: '{username}', desc: 'Member username (e.g. JohnDoe)' },
  { key: '{display_name}', desc: 'Server nickname/display name' },
  { key: '{user_mention}', desc: 'Discord mention @User' },
  { key: '{user_id}', desc: 'Unique Discord User ID' },
  { key: '{server_name}', desc: 'Discord Server Name' },
  { key: '{server_id}', desc: 'Discord Server ID' },
  { key: '{member_count}', desc: 'Total member count' },
  { key: '{account_created}', desc: 'Account creation date' },
  { key: '{joined_at}', desc: 'Join date & timestamp' },
  { key: '{rules_url}', desc: 'Official rules link' },
  { key: '{invite_url}', desc: 'Permanent server invite' },
];

const GOODBYE_VARIABLES = [
  { key: '{username}', desc: 'Member username' },
  { key: '{display_name}', desc: 'Server nickname/display name' },
  { key: '{user_id}', desc: 'Unique Discord User ID' },
  { key: '{server_name}', desc: 'Discord Server Name' },
  { key: '{server_id}', desc: 'Discord Server ID' },
  { key: '{member_count}', desc: 'Member count before departure' },
  { key: '{left_at}', desc: 'Departure timestamp' },
  { key: '{invite_url}', desc: 'Permanent server invite' },
];

export const WelcomeGoodbye: React.FC = () => {
  const [data, setData] = useState<GreetingsResponse | null>(null);
  const [channels, setChannels] = useState<GreetingChannelOption[]>([]);
  const [roles, setRoles] = useState<GuildRoleOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingWelcome, setTestingWelcome] = useState(false);
  const [testingGoodbye, setTestingGoodbye] = useState(false);

  const [activeTab, setActiveTab] = useState<'welcome' | 'goodbye' | 'rules' | 'dms' | 'invite' | 'activity'>('welcome');

  const [formData, setFormData] = useState<ServerGreetingSettings | null>(null);
  const [initialData, setInitialData] = useState<ServerGreetingSettings | null>(null);
  const [activeInput, setActiveInput] = useState<string>('welcome_description');

  const [showResetWelcomeModal, setShowResetWelcomeModal] = useState(false);
  const [showResetGoodbyeModal, setShowResetGoodbyeModal] = useState(false);

  const loadData = async () => {
    try {
      const [greetRes, chanRes, roleRes] = await Promise.all([
        greetingsApi.getGreetings(),
        greetingsApi.getChannels(),
        greetingsApi.getRoles(),
      ]);
      setData(greetRes);
      setFormData(greetRes.settings);
      setInitialData(greetRes.settings);
      setChannels(chanRes);
      setRoles(roleRes);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load greeting configuration');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const hasChanges = JSON.stringify(formData) !== JSON.stringify(initialData);

  const handleFieldChange = (updates: Partial<ServerGreetingSettings>) => {
    if (!formData) return;
    setFormData({ ...formData, ...updates });
  };

  const insertVariable = (variableKey: string) => {
    if (!formData || !activeInput) return;
    const current = (formData as any)[activeInput] || '';
    const updated = current ? `${current}${variableKey}` : variableKey;
    handleFieldChange({ [activeInput]: updated });
  };

  const handleSave = async () => {
    if (!formData) return;
    setSaving(true);
    try {
      const res = await greetingsApi.updateGreetings(formData);
      setFormData(res.settings);
      setInitialData(res.settings);
      toast.success('Greetings settings saved successfully!');
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleTestWelcome = async () => {
    setTestingWelcome(true);
    try {
      const res = await greetingsApi.testWelcome();
      toast.success(res.message);
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Test welcome message failed');
    } finally {
      setTestingWelcome(false);
    }
  };

  const handleTestGoodbye = async () => {
    setTestingGoodbye(true);
    try {
      const res = await greetingsApi.testGoodbye();
      toast.success(res.message);
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Test goodbye message failed');
    } finally {
      setTestingGoodbye(false);
    }
  };

  const handleTestDM = async (type: 'welcome-dm' | 'goodbye-dm') => {
    try {
      const res = await greetingsApi.testGreeting(type);
      toast.success(res.message);
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Test DM failed');
    }
  };

  const handleReset = async (systemType: 'welcome' | 'goodbye' | 'welcome_dm' | 'goodbye_dm' | 'rules') => {
    try {
      const res = await greetingsApi.resetSystem(systemType);
      setFormData(res.settings);
      setInitialData(res.settings);
      toast.success(res.message);
      loadData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || `Failed to reset ${systemType}`);
    }
  };
  if (loading || !formData || !data) {
    return (
      <div className="p-8 max-w-7xl mx-auto space-y-6">
        <LoadingSkeleton className="h-28 w-full rounded-2xl" />
        <LoadingSkeleton className="h-96 w-full rounded-2xl" />
      </div>
    );
  }

  const serverName = data.server.server_name || 'PB HERO SERVER';
  const serverId = data.server.server_id || '0';

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-8 animate-fade-in pb-24">
      {/* 1. Header Banner */}
      <div className="bg-gradient-to-r from-gray-900 via-gray-850 to-gray-900 border border-gray-800 rounded-3xl p-6 md:p-8 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-wrap items-center justify-between gap-6 relative z-10">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-400">
              <Server className="w-4 h-4" />
              <span>Personal Guild Automation</span>
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
              Server Greetings & Member Onboarding
            </h1>
            <p className="text-gray-400 text-sm max-w-2xl">
              Professional automated welcome announcements, rules delivery, direct messages, auto-role assignment, and permanent server invite management for <strong className="text-white">{serverName}</strong>.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 bg-gray-950/60 p-4 rounded-2xl border border-gray-800 shrink-0">
            {data.server.server_icon ? (
              <img src={data.server.server_icon} alt="Server" className="w-12 h-12 rounded-xl object-cover shadow" />
            ) : (
              <div className="w-12 h-12 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center font-black">
                PB
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-white text-sm">{serverName}</span>
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800">
                  ONLINE
                </span>
              </div>
              <div className="text-xs text-gray-500 font-mono mt-0.5">
                ID: {serverId} • {data.server.member_count} members
              </div>
            </div>
          </div>
        </div>

        {/* System Stats Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 mt-6 pt-6 border-t border-gray-800/80">
          <div className="bg-gray-950/40 p-3 rounded-xl border border-gray-800/60">
            <span className="text-[11px] text-gray-500 block truncate">Welcome Sent</span>
            <span className="text-base font-extrabold text-white">{data.stats.welcome_sent_today}</span>
          </div>
          <div className="bg-gray-950/40 p-3 rounded-xl border border-gray-800/60">
            <span className="text-[11px] text-gray-500 block truncate">Welcome DMs</span>
            <span className="text-base font-extrabold text-emerald-400">{data.stats.welcome_dms_today ?? 0}</span>
          </div>
          <div className="bg-gray-950/40 p-3 rounded-xl border border-gray-800/60">
            <span className="text-[11px] text-gray-500 block truncate">Rules Delivered</span>
            <span className="text-base font-extrabold text-fuchsia-400">{data.stats.rules_delivered_today ?? 0}</span>
          </div>
          <div className="bg-gray-950/40 p-3 rounded-xl border border-gray-800/60">
            <span className="text-[11px] text-gray-500 block truncate">Roles Assigned</span>
            <span className="text-base font-extrabold text-cyan-400">{data.stats.roles_assigned_today ?? 0}</span>
          </div>
          <div className="bg-gray-950/40 p-3 rounded-xl border border-gray-800/60">
            <span className="text-[11px] text-gray-500 block truncate">Goodbye Sent</span>
            <span className="text-base font-extrabold text-rose-400">{data.stats.goodbye_sent_today}</span>
          </div>
          <div className="bg-gray-950/40 p-3 rounded-xl border border-gray-800/60">
            <span className="text-[11px] text-gray-500 block truncate">Goodbye DMs</span>
            <span className="text-base font-extrabold text-amber-400">{data.stats.goodbye_dms_today ?? 0}</span>
          </div>
          <div className="bg-gray-950/40 p-3 rounded-xl border border-gray-800/60">
            <span className="text-[11px] text-gray-500 block truncate">DM Failures</span>
            <span className="text-base font-extrabold text-gray-400">{data.stats.dm_failures_today ?? 0}</span>
          </div>
        </div>
      </div>
      {/* 2. Unsaved Changes Alert Bar */}
      {hasChanges && (
        <div className="sticky top-4 z-40 bg-indigo-950/90 backdrop-blur-md border border-indigo-700/80 p-4 rounded-2xl shadow-2xl flex items-center justify-between gap-4 animate-bounce-subtle">
          <div className="flex items-center gap-2.5 text-indigo-200 text-sm">
            <Sparkles className="w-5 h-5 text-indigo-400 shrink-0" />
            <span>You have unsaved changes in greeting or onboarding configuration.</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setFormData(initialData)}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-xl text-xs font-bold transition-colors"
            >
              Discard
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-indigo-600/30 transition-all"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Saving...' : 'Save All Settings'}
            </button>
          </div>
        </div>
      )}

      {/* 3. Navigation Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-gray-800 pb-3">
        {[
          { id: 'welcome', label: 'Public Welcome', icon: UserPlus, count: formData.welcome_enabled ? 'ON' : 'OFF' },
          { id: 'goodbye', label: 'Public Goodbye', icon: UserMinus, count: formData.goodbye_enabled ? 'ON' : 'OFF' },
          { id: 'rules', label: 'Rules & Auto Role', icon: BookOpen, count: formData.rules_delivery_enabled || formData.auto_role_enabled ? 'ON' : 'OFF' },
          { id: 'dms', label: 'Welcome & Goodbye DMs', icon: Mail, count: formData.welcome_dm_enabled || formData.goodbye_dm_enabled ? 'ON' : 'OFF' },
          { id: 'invite', label: 'Permanent Invite', icon: Link2, count: data.invite?.is_active ? 'ACTIVE' : 'IDLE' },
          { id: 'activity', label: 'Activity & Audit', icon: History, count: data.recent_activity.length },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id} data-testid={`tab-${tab.id}`} type="button"
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                  : 'bg-gray-850 hover:bg-gray-800 text-gray-400 hover:text-white border border-gray-800'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-md ${
                isActive ? 'bg-indigo-700/80 text-white' : 'bg-gray-800 text-gray-400'
              }`}>
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* TAB CONTENT 1: Public Welcome */}
      {activeTab === 'welcome' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-7 bg-gray-850 rounded-2xl border border-gray-800 shadow-xl overflow-hidden">
            <div className="p-6 border-b border-gray-800 flex items-center justify-between gap-4 bg-gray-900/60">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-indigo-500/10 rounded-xl border border-indigo-500/20 text-indigo-400">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-[10px] font-extrabold uppercase tracking-widest text-indigo-400">WELCOME SYSTEM</div><h2 className="text-lg font-bold text-white">Public Welcome Channel Message</h2>
                  <p className="text-xs text-gray-400">Sent automatically when a member joins the server.</p>
                </div>
              </div>

              <label className="relative inline-flex items-center cursor-pointer shrink-0">
                <input
                  type="checkbox"
                  checked={Boolean(formData.welcome_enabled)}
                  onChange={(e) => handleFieldChange({ welcome_enabled: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
              </label>
            </div>

            <div className="p-6 space-y-6">
              {/* Channel Selector */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                  Destination Channel
                </label>
                <select
                  value={formData.welcome_channel_id || ''}
                  onChange={(e) => handleFieldChange({ welcome_channel_id: e.target.value || null })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="">-- Select Discord Channel --</option>
                  {channels.map((ch) => (
                    <option key={ch.id} value={ch.id}>
                      #{ch.name} ({ch.category}) {ch.can_send ? '✅' : '⚠️ Lacks Send'}
                    </option>
                  ))}
                </select>
              </div>

              {/* Permission Telemetry */}
              {formData.welcome_channel_id && (
                <div className="p-4 bg-gray-900/60 rounded-xl border border-gray-800 space-y-2 text-xs">
                  <span className="font-bold text-gray-300 uppercase tracking-wider text-[11px] block">
                    Bot Channel Access Telemetry
                  </span>
                  <div className="flex flex-wrap gap-4 text-gray-400">
                    <span className="flex items-center gap-1.5">
                      {data.welcome_channel_status.can_view ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400" />}
                      View Channel
                    </span>
                    <span className="flex items-center gap-1.5">
                      {data.welcome_channel_status.can_send ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400" />}
                      Send Messages
                    </span>
                    <span className="flex items-center gap-1.5">
                      {data.welcome_channel_status.can_embed ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400" />}
                      Embed Links
                    </span>
                  </div>
                  {data.welcome_channel_status.warning && (
                    <p className="text-amber-400 text-xs flex items-center gap-1 mt-1">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      {data.welcome_channel_status.warning}
                    </p>
                  )}
                </div>
              )}

              {/* Visual Toggles */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-3 bg-gray-900/40 rounded-xl border border-gray-800 text-xs text-gray-300">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.welcome_use_embed}
                    onChange={(e) => handleFieldChange({ welcome_use_embed: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-indigo-600 focus:ring-indigo-500"
                  />
                  Use Rich Embed
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.welcome_mention_user}
                    onChange={(e) => handleFieldChange({ welcome_mention_user: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-indigo-600 focus:ring-indigo-500"
                  />
                  Mention Member
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.welcome_show_avatar}
                    onChange={(e) => handleFieldChange({ welcome_show_avatar: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-indigo-600 focus:ring-indigo-500"
                  />
                  Show Avatar
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.welcome_show_server_icon}
                    onChange={(e) => handleFieldChange({ welcome_show_server_icon: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-indigo-600 focus:ring-indigo-500"
                  />
                  Server Icon
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.welcome_show_timestamp}
                    onChange={(e) => handleFieldChange({ welcome_show_timestamp: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-indigo-600 focus:ring-indigo-500"
                  />
                  Timestamp
                </label>
              </div>

              {/* Template Editor */}
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                    Message / Embed Title
                  </label>
                  <input
                    type="text"
                    value={formData.welcome_title ?? ''}
                    onFocus={() => setActiveInput('welcome_title')}
                    onChange={(e) => handleFieldChange({ welcome_title: e.target.value })}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                    Message Description
                  </label>
                  <textarea
                    rows={5}
                    value={formData.welcome_description ?? ''}
                    onFocus={() => setActiveInput('welcome_description')}
                    onChange={(e) => handleFieldChange({ welcome_description: e.target.value })}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl p-3 text-sm text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                    Footer
                  </label>
                  <input
                    type="text"
                    value={formData.welcome_footer ?? ''}
                    onFocus={() => setActiveInput('welcome_footer')}
                    onChange={(e) => handleFieldChange({ welcome_footer: e.target.value })}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>

                {/* Variable Insertion Chips */}
                <div className="p-3 bg-gray-900/40 rounded-xl border border-gray-800 space-y-2">
                  <span className="text-[11px] font-bold text-gray-400 flex items-center gap-1.5">
                    <Tag className="w-3.5 h-3.5 text-indigo-400" />
                    Available Variables (Click to insert into focused field):
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {WELCOME_VARIABLES.map((v) => (
                      <button
                        key={v.key}
                        type="button"
                        onClick={() => insertVariable(v.key)}
                        title={v.desc}
                        className="px-2.5 py-1 bg-gray-800 hover:bg-indigo-950 hover:text-indigo-300 text-gray-300 rounded-lg text-xs font-mono border border-gray-700 transition-colors"
                      >
                        {v.key}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-gray-800">
                <button
                  type="button"
                  onClick={() => setShowResetWelcomeModal(true)}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors border border-gray-700"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Reset Welcome Template
                </button>

                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={handleTestWelcome}
                    disabled={testingWelcome || !formData.welcome_channel_id}
                    className="px-4 py-2 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/40 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm disabled:opacity-50"
                  >
                    <Play className="w-3.5 h-3.5" />
                    {testingWelcome ? 'Sending...' : 'Test Welcome'}
                  </button>

                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving || !hasChanges}
                    className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-indigo-600/20 transition-all disabled:opacity-50"
                  >
                    <Save className="w-3.5 h-3.5" />
                    Save Welcome
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="lg:col-span-5 sticky top-24">
            <DiscordPreview
              title={formData.welcome_title}
              description={formData.welcome_description}
              footer={formData.welcome_footer}
              useEmbed={formData.welcome_use_embed}
              mentionUser={formData.welcome_mention_user}
              showAvatar={formData.welcome_show_avatar}
              showServerIcon={formData.welcome_show_server_icon}
              showTimestamp={formData.welcome_show_timestamp}
              serverName={serverName}
              embedColor="#5865F2"
            />
          </div>
        </div>
      )}

      {/* TAB CONTENT 2: Public Goodbye */}
      {activeTab === 'goodbye' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-7 bg-gray-850 rounded-2xl border border-gray-800 shadow-xl overflow-hidden">
            <div className="p-6 border-b border-gray-800 flex items-center justify-between gap-4 bg-gray-900/60">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-rose-500/10 rounded-xl border border-rose-500/20 text-rose-400">
                  <UserMinus className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-[10px] font-extrabold uppercase tracking-widest text-rose-400">GOODBYE SYSTEM</div><h2 className="text-lg font-bold text-white">Public Goodbye / Departure Message</h2>
                  <p className="text-xs text-gray-400">Sent automatically when a member departs the server.</p>
                </div>
              </div>

              <label className="relative inline-flex items-center cursor-pointer shrink-0">
                <input
                  type="checkbox"
                  checked={Boolean(formData.goodbye_enabled)}
                  onChange={(e) => handleFieldChange({ goodbye_enabled: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-rose-600"></div>
              </label>
            </div>

            <div className="p-6 space-y-6">
              {/* Channel Selector */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                  Destination Channel
                </label>
                <select
                  value={formData.goodbye_channel_id || ''}
                  onChange={(e) => handleFieldChange({ goodbye_channel_id: e.target.value || null })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-rose-500"
                >
                  <option value="">-- Select Discord Channel --</option>
                  {channels.map((ch) => (
                    <option key={ch.id} value={ch.id}>
                      #{ch.name} ({ch.category}) {ch.can_send ? '✅' : '⚠️ Lacks Send'}
                    </option>
                  ))}
                </select>
              </div>

              {/* Permission Telemetry */}
              {formData.goodbye_channel_id && (
                <div className="p-4 bg-gray-900/60 rounded-xl border border-gray-800 space-y-2 text-xs">
                  <span className="font-bold text-gray-300 uppercase tracking-wider text-[11px] block">
                    Bot Channel Access Telemetry
                  </span>
                  <div className="flex flex-wrap gap-4 text-gray-400">
                    <span className="flex items-center gap-1.5">
                      {data.goodbye_channel_status.can_view ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400" />}
                      View Channel
                    </span>
                    <span className="flex items-center gap-1.5">
                      {data.goodbye_channel_status.can_send ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400" />}
                      Send Messages
                    </span>
                    <span className="flex items-center gap-1.5">
                      {data.goodbye_channel_status.can_embed ? <CheckCircle className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-rose-400" />}
                      Embed Links
                    </span>
                  </div>
                  {data.goodbye_channel_status.warning && (
                    <p className="text-amber-400 text-xs flex items-center gap-1 mt-1">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      {data.goodbye_channel_status.warning}
                    </p>
                  )}
                </div>
              )}

              {/* Visual Toggles */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-3 bg-gray-900/40 rounded-xl border border-gray-800 text-xs text-gray-300">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.goodbye_use_embed}
                    onChange={(e) => handleFieldChange({ goodbye_use_embed: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-rose-600 focus:ring-rose-500"
                  />
                  Use Rich Embed
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.goodbye_mention_user}
                    onChange={(e) => handleFieldChange({ goodbye_mention_user: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-rose-600 focus:ring-rose-500"
                  />
                  Mention Member
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.goodbye_show_avatar}
                    onChange={(e) => handleFieldChange({ goodbye_show_avatar: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-rose-600 focus:ring-rose-500"
                  />
                  Show Avatar
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.goodbye_show_server_icon}
                    onChange={(e) => handleFieldChange({ goodbye_show_server_icon: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-rose-600 focus:ring-rose-500"
                  />
                  Server Icon
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.goodbye_show_timestamp}
                    onChange={(e) => handleFieldChange({ goodbye_show_timestamp: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-rose-600 focus:ring-rose-500"
                  />
                  Timestamp
                </label>
              </div>

              {/* Template Editor */}
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                    Message / Embed Title
                  </label>
                  <input
                    type="text"
                    value={formData.goodbye_title ?? ''}
                    onFocus={() => setActiveInput('goodbye_title')}
                    onChange={(e) => handleFieldChange({ goodbye_title: e.target.value })}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-rose-500"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                    Message Description
                  </label>
                  <textarea
                    rows={5}
                    value={formData.goodbye_description ?? ''}
                    onFocus={() => setActiveInput('goodbye_description')}
                    onChange={(e) => handleFieldChange({ goodbye_description: e.target.value })}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl p-3 text-sm text-white font-mono focus:outline-none focus:border-rose-500"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                    Footer
                  </label>
                  <input
                    type="text"
                    value={formData.goodbye_footer ?? ''}
                    onFocus={() => setActiveInput('goodbye_footer')}
                    onChange={(e) => handleFieldChange({ goodbye_footer: e.target.value })}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-rose-500"
                  />
                </div>

                {/* Variable Insertion Chips */}
                <div className="p-3 bg-gray-900/40 rounded-xl border border-gray-800 space-y-2">
                  <span className="text-[11px] font-bold text-gray-400 flex items-center gap-1.5">
                    <Tag className="w-3.5 h-3.5 text-rose-400" />
                    Available Variables (Click to insert into focused field):
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {GOODBYE_VARIABLES.map((v) => (
                      <button
                        key={v.key}
                        type="button"
                        onClick={() => insertVariable(v.key)}
                        title={v.desc}
                        className="px-2.5 py-1 bg-gray-800 hover:bg-rose-950 hover:text-rose-300 text-gray-300 rounded-lg text-xs font-mono border border-gray-700 transition-colors"
                      >
                        {v.key}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-gray-800">
                <button
                  type="button"
                  onClick={() => setShowResetGoodbyeModal(true)}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors border border-gray-700"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Reset Goodbye Template
                </button>

                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={handleTestGoodbye}
                    disabled={testingGoodbye || !formData.goodbye_channel_id}
                    className="px-4 py-2 bg-rose-600/30 hover:bg-rose-600/50 text-rose-300 border border-rose-500/40 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm disabled:opacity-50"
                  >
                    <Play className="w-3.5 h-3.5" />
                    {testingGoodbye ? 'Sending...' : 'Test Goodbye'}
                  </button>

                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving || !hasChanges}
                    className="px-5 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-rose-600/20 transition-all disabled:opacity-50"
                  >
                    <Save className="w-3.5 h-3.5" />
                    Save Goodbye
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="lg:col-span-5 sticky top-24">
            <DiscordPreview
              title={formData.goodbye_title}
              description={formData.goodbye_description}
              footer={formData.goodbye_footer}
              useEmbed={formData.goodbye_use_embed}
              mentionUser={formData.goodbye_mention_user}
              showAvatar={formData.goodbye_show_avatar}
              showServerIcon={formData.goodbye_show_server_icon}
              showTimestamp={formData.goodbye_show_timestamp}
              serverName={serverName}
              embedColor="#ED4245"
            />
          </div>
        </div>
      )}

      {/* TAB CONTENT 3: Rules & Auto-Role */}
      {activeTab === 'rules' && (
        <RulesAndRoleCard
          settings={formData}
          onChange={handleFieldChange}
          channels={channels}
          roles={roles}
          onResetRules={() => handleReset('rules')}
          serverName={serverName}
          serverId={serverId}
        />
      )}

      {/* TAB CONTENT 4: Direct Messages */}
      {activeTab === 'dms' && (
        <DirectMessagesCard
          settings={formData}
          onChange={handleFieldChange}
          onTestWelcomeDM={() => handleTestDM('welcome-dm')}
          onTestGoodbyeDM={() => handleTestDM('goodbye-dm')}
          onResetWelcomeDM={() => handleReset('welcome_dm')}
          onResetGoodbyeDM={() => handleReset('goodbye_dm')}
          serverName={serverName}
        />
      )}

      {/* TAB CONTENT 5: Permanent Invite Manager */}
      {activeTab === 'invite' && (
        <InviteManagerCard
          invite={data.invite}
          channels={channels}
          onRefresh={loadData}
          welcomeChannelId={formData.welcome_channel_id}
        />
      )}

      {/* TAB CONTENT 6: Recent Activity & Audit */}
      {activeTab === 'activity' && (
        <RecentActivityTable activities={data.recent_activity || []} />
      )}

      {/* Modals */}
      <ConfirmModal
        isOpen={showResetWelcomeModal}
        onCancel={() => setShowResetWelcomeModal(false)}
        onConfirm={() => {
          handleReset('welcome');
          setShowResetWelcomeModal(false);
        }}
        title="Reset Welcome Settings?"
        message="Are you sure you want to reset the public welcome template to defaults? Any custom message or title will be restored."
        confirmText="Reset to Default"
      />

      <ConfirmModal
        isOpen={showResetGoodbyeModal}
        onCancel={() => setShowResetGoodbyeModal(false)}
        onConfirm={() => {
          handleReset('goodbye');
          setShowResetGoodbyeModal(false);
        }}
        title="Reset Goodbye Settings?"
        message="Are you sure you want to reset the public goodbye template to defaults? Any custom title, message, or footer will be restored."
        confirmText="Reset to Default"
      />
    </div>
  );
};

export default WelcomeGoodbye;



