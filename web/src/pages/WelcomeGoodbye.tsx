import { useEffect, useState } from 'react';
import { greetingsApi } from '../api/greetings';
import {
  GreetingsResponse,
  GreetingChannelOption,
  GuildRoleOption,
  ServerGreetingSettings,
  GreetingButton,
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
  Palette,
  Image as ImageIcon,
  Layers,
} from 'lucide-react';

const WELCOME_VARIABLES = [
  { key: '{username}', desc: 'Member username (e.g. JohnDoe)' },
  { key: '{display_name}', desc: 'Server nickname / display name' },
  { key: '{user_mention}', desc: 'Discord mention @User' },
  { key: '{user_id}', desc: 'Unique Discord User ID' },
  { key: '{server_name}', desc: 'Discord Server Name' },
  { key: '{server_id}', desc: 'Discord Server ID' },
  { key: '{member_count}', desc: 'Total member count' },
  { key: '{account_created}', desc: 'Account creation date' },
  { key: '{joined_at}', desc: 'Join date & timestamp' },
  { key: '{inviter}', desc: 'Inviter username or Server Vanity URL' },
  { key: '{inviter_mention}', desc: 'Inviter @mention' },
  { key: '{inviter_id}', desc: 'Inviter user ID' },
  { key: '{invite_code}', desc: 'Used invite code' },
  { key: '{invite_channel}', desc: 'Channel invite was created in' },
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

const THEME_PRESETS: Record<string, {
  name: string;
  icon: string;
  welcome_title: string;
  welcome_description: string;
  welcome_accent_color: string;
  goodbye_title: string;
  goodbye_description: string;
  goodbye_accent_color: string;
}> = {
  default: {
    name: 'Default Classic',
    icon: '✨',
    welcome_title: '✨ WELCOME TO {server_name}',
    welcome_description: "Hey {user_mention} 👋\n\nWe're glad to have you here!\n\n👥 You are member #{member_count}\n\n🤝 Invited by: {inviter}\n🔗 Invite: {invite_code}\n\n📜 Please read the server rules.\n🎮 Explore the community and enjoy your stay.",
    welcome_accent_color: '#5865F2',
    goodbye_title: '💙 Goodbye {display_name}',
    goodbye_description: "💙 {display_name} has left {server_name}.\n\nWe hope you enjoyed your time with us.\n\n👥 We are now {member_count} members.\n\nTake care and you're always welcome back.",
    goodbye_accent_color: '#ED4245',
  },
  gaming: {
    name: 'Gaming & Esports',
    icon: '🎮',
    welcome_title: '🎮 WELCOME TO {server_name}',
    welcome_description: "🎮 Player {user_mention} has entered the arena!\n\n⚔️ Party Member #{member_count}\n🎯 Recruited by: {inviter}\n🔗 Portal Key: {invite_code}\n\n📜 Check our guidelines before queuing up.\n🕹️ Good luck and have fun!",
    welcome_accent_color: '#10B981',
    goodbye_title: '💀 PLAYER DISCONNECTED: {display_name}',
    goodbye_description: '{display_name} has left the party.\n\n👥 Current squad: {member_count} players.\n\nRespawn anytime — GG!',
    goodbye_accent_color: '#EF4444',
  },
  minimal: {
    name: 'Minimal & Clean',
    icon: '⚪',
    welcome_title: 'Welcome to {server_name}',
    welcome_description: 'Welcome {user_mention}.\n\nMember #{member_count} • Invited by {inviter}\n\nReview the rules and enjoy your stay.',
    welcome_accent_color: '#71717A',
    goodbye_title: 'Goodbye {display_name}',
    goodbye_description: '{display_name} has left.\n\nCurrent members: {member_count}.',
    goodbye_accent_color: '#71717A',
  },
  luxury: {
    name: 'Luxury & Gold',
    icon: '👑',
    welcome_title: '✨ WELCOME TO {server_name}',
    welcome_description: 'A distinguished welcome to {user_mention} 🥂\n\nIt is our privilege to welcome you as member #{member_count}.\n\n⚜️ Introduced by: {inviter}\n🗝️ Registry Code: {invite_code}\n\nPlease observe server etiquette and enjoy your refined stay.',
    welcome_accent_color: '#D97706',
    goodbye_title: '✨ FAREWELL, {display_name}',
    goodbye_description: '{display_name} has departed from {server_name}.\n\nOur distinguished community now stands at {member_count}.\n\nOur doors remain open for your return.',
    goodbye_accent_color: '#B45309',
  },
  neon: {
    name: 'Neon Cyber',
    icon: '⚡',
    welcome_title: '⚡ SYSTEM ONLINE • {server_name}',
    welcome_description: 'Neon uplink connected: {user_mention} ⚡\n\n🌐 Network Node #{member_count}\n📡 Uplinked by: {inviter}\n⚡ Frequency: {invite_code}\n\nAccess protocols accepted. Welcome to the grid!',
    welcome_accent_color: '#EC4899',
    goodbye_title: '⚡ NODE OFFLINE • {display_name}',
    goodbye_description: 'Node disconnection logged for {display_name}.\n\nActive network size: {member_count} nodes.\n\nReconnection frequency ready.',
    goodbye_accent_color: '#8B5CF6',
  },
};

const DEFAULT_WELCOME_BUTTONS: GreetingButton[] = [
  { id: 'rules', label: 'Read Rules', emoji: '📜', url: '{rules_url}', style: 'link', enabled: true },
  { id: 'explore', label: 'Explore Server', emoji: '🎮', url: '{invite_url}', style: 'link', enabled: true },
  { id: 'invite', label: 'Server Invite', emoji: '🔗', url: '{invite_url}', style: 'link', enabled: false },
  { id: 'support', label: 'Support', emoji: '🆘', url: 'https://discord.gg/pbhero', style: 'link', enabled: false },
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
  const [pendingThemeKey, setPendingThemeKey] = useState<string | null>(null);

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
      toast.error(err.message || err.detail || err.response?.data?.detail || 'Failed to load greeting configuration');
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

  const getWelcomeButtons = (): GreetingButton[] => {
    if (!formData?.welcome_buttons_json) return DEFAULT_WELCOME_BUTTONS;
    if (Array.isArray(formData.welcome_buttons_json)) return formData.welcome_buttons_json;
    try {
      return JSON.parse(formData.welcome_buttons_json as string);
    } catch {
      return DEFAULT_WELCOME_BUTTONS;
    }
  };

  const handleUpdateButton = (index: number, updates: Partial<GreetingButton>) => {
    const current = [...getWelcomeButtons()];
    current[index] = { ...current[index], ...updates };
    handleFieldChange({ welcome_buttons_json: current });
  };

  const applyThemePreset = (themeKey: string) => {
    const preset = THEME_PRESETS[themeKey];
    if (!preset) return;
    if (activeTab === 'welcome') {
      handleFieldChange({
        welcome_theme: themeKey,
        welcome_title: preset.welcome_title,
        welcome_description: preset.welcome_description,
        welcome_accent_color: preset.welcome_accent_color,
      });
    } else if (activeTab === 'goodbye') {
      handleFieldChange({
        goodbye_theme: themeKey,
        goodbye_title: preset.goodbye_title,
        goodbye_description: preset.goodbye_description,
        goodbye_accent_color: preset.goodbye_accent_color,
      });
    }
    setPendingThemeKey(null);
    toast.success(`Applied ${preset.name} theme preset`);
  };

  const handleSave = async () => {
    if (!formData) return;
    if (
      (formData.welcome_title && formData.welcome_title.length > 256) ||
      (formData.goodbye_title && formData.goodbye_title.length > 256)
    ) {
      toast.error('Title exceeds maximum limit of 256 characters.');
      return;
    }
    if (
      (formData.welcome_description && formData.welcome_description.length > 4096) ||
      (formData.goodbye_description && formData.goodbye_description.length > 4096)
    ) {
      toast.error('Description exceeds maximum limit of 4096 characters.');
      return;
    }
    if (
      (formData.welcome_footer && formData.welcome_footer.length > 2048) ||
      (formData.goodbye_footer && formData.goodbye_footer.length > 2048)
    ) {
      toast.error('Footer exceeds maximum limit of 2048 characters.');
      return;
    }
    setSaving(true);
    try {
      const payload: ServerGreetingSettings = {
        ...formData,
        welcome_buttons_json: getWelcomeButtons(),
      };
      const res = await greetingsApi.updateGreetings(payload);
      setFormData(res.settings);
      setInitialData(res.settings);
      if (data) {
        setData({ ...data, settings: res.settings });
      }
      toast.success('Settings saved successfully');
    } catch (err: any) {
      const rawMsg = err.message || err.detail || err.response?.data?.detail || 'Failed to save settings';
      const cleanMsg = rawMsg.startsWith('Failed to save settings')
        ? rawMsg
        : `Failed to save settings: ${rawMsg}`;
      toast.error(cleanMsg);
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
      toast.error(err.message || err.detail || err.response?.data?.detail || 'Test welcome message failed');
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
      toast.error(err.message || err.detail || err.response?.data?.detail || 'Test goodbye message failed');
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
      toast.error(err.message || err.detail || err.response?.data?.detail || 'Test DM failed');
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
      toast.error(err.message || err.detail || err.response?.data?.detail || `Failed to reset ${systemType}`);
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
              <span>Personal Guild Automation • Premium Onboarding 2.0</span>
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
              key={tab.id}
              data-testid={`tab-${tab.id}`}
              type="button"
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
                  <div className="text-[10px] font-extrabold uppercase tracking-widest text-indigo-400">WELCOME SYSTEM</div>
                  <h2 className="text-lg font-bold text-white">Public Welcome Channel Message</h2>
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
              {/* Theme Presets */}
              <div className="space-y-2 p-4 bg-gray-900/50 rounded-2xl border border-gray-800">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                    Premium Theme Presets
                  </span>
                  <span className="text-[11px] text-gray-500">Pick a preset to style presentation defaults</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  {Object.entries(THEME_PRESETS).map(([key, preset]) => {
                    const isSelected = (formData.welcome_theme || 'default') === key;
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setPendingThemeKey(key)}
                        className={`p-2.5 rounded-xl border text-left transition-all flex flex-col gap-1 ${
                          isSelected
                            ? 'bg-indigo-600/20 border-indigo-500 text-white shadow-sm'
                            : 'bg-gray-900 hover:bg-gray-800/80 border-gray-800 text-gray-300'
                        }`}
                      >
                        <div className="flex items-center justify-between w-full">
                          <span className="text-base">{preset.icon}</span>
                          <span
                            className="w-3 h-3 rounded-full border border-gray-700"
                            style={{ backgroundColor: preset.welcome_accent_color }}
                          />
                        </div>
                        <span className="text-xs font-bold truncate">{preset.name.split(' ')[0]}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

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

              {/* Visual & Attribution Toggles */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-gray-900/40 rounded-xl border border-gray-800 text-xs text-gray-300">
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
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.welcome_show_member_count ?? true}
                    onChange={(e) => handleFieldChange({ welcome_show_member_count: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-indigo-600 focus:ring-indigo-500"
                  />
                  Member Count
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.welcome_show_inviter !== false}
                    onChange={(e) => handleFieldChange({ welcome_show_inviter: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-indigo-600 focus:ring-indigo-500"
                  />
                  Show Inviter
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.welcome_show_invite_code !== false}
                    onChange={(e) => handleFieldChange({ welcome_show_invite_code: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-indigo-600 focus:ring-indigo-500"
                  />
                  Show Invite Code
                </label>
              </div>

              {/* Server Branding & Banner UI */}
              <div className="space-y-4 p-4 bg-gray-900/40 rounded-2xl border border-gray-800">
                <span className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Palette className="w-3.5 h-3.5 text-indigo-400" />
                  Server Branding, Accent & Banner
                </span>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
                      Accent Color
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={formData.welcome_accent_color || '#5865F2'}
                        onChange={(e) => handleFieldChange({ welcome_accent_color: e.target.value })}
                        className="w-10 h-10 rounded-xl bg-transparent border border-gray-700 cursor-pointer shrink-0"
                      />
                      <input
                        type="text"
                        value={formData.welcome_accent_color || '#5865F2'}
                        onChange={(e) => handleFieldChange({ welcome_accent_color: e.target.value })}
                        placeholder="#5865F2"
                        className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-xs text-white font-mono uppercase focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
                      Banner Display Mode
                    </label>
                    <select
                      value={formData.welcome_banner_mode || 'none'}
                      onChange={(e) => handleFieldChange({ welcome_banner_mode: e.target.value as any })}
                      className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                    >
                      <option value="none">No Banner Image</option>
                      <option value="server">Server Banner (from Discord)</option>
                      <option value="custom">Custom Image / GIF URL</option>
                    </select>
                  </div>
                </div>

                {formData.welcome_banner_mode === 'custom' && (
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block flex items-center gap-1">
                      <ImageIcon className="w-3.5 h-3.5 text-indigo-400" />
                      Custom Image or GIF URL
                    </label>
                    <input
                      type="url"
                      value={formData.welcome_banner_url ?? ''}
                      onChange={(e) => handleFieldChange({ welcome_banner_url: e.target.value })}
                      placeholder="https://example.com/welcome-banner.gif"
                      className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                    />
                    <p className="text-[10px] text-gray-500">Only secure HTTPS URLs are allowed. Broken images automatically fall back safely.</p>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                      <label className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
                        Author Name
                      </label>
                      <span className={`text-[10px] font-mono ${(formData.welcome_author_text?.length || 0) > 256 ? 'text-rose-400 font-bold' : 'text-gray-500'}`}>
                        {formData.welcome_author_text?.length || 0}/256
                      </span>
                    </div>
                    <input
                      type="text"
                      value={formData.welcome_author_text ?? ''}
                      onFocus={() => setActiveInput('welcome_author_text')}
                      onChange={(e) => handleFieldChange({ welcome_author_text: e.target.value })}
                      placeholder={serverName}
                      className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
                      Author Icon URL
                    </label>
                    <input
                      type="url"
                      value={formData.welcome_author_icon_url ?? ''}
                      onChange={(e) => handleFieldChange({ welcome_author_icon_url: e.target.value })}
                      placeholder="https://... (defaults to Server Icon)"
                      className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>
              </div>

              {/* Template Editor */}
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                      Message / Embed Title
                    </label>
                    <span className={`text-[10px] font-mono ${(formData.welcome_title?.length || 0) > 256 ? 'text-rose-400 font-bold' : 'text-gray-500'}`}>
                      {formData.welcome_title?.length || 0}/256
                    </span>
                  </div>
                  <input
                    type="text"
                    value={formData.welcome_title ?? ''}
                    onFocus={() => setActiveInput('welcome_title')}
                    onChange={(e) => handleFieldChange({ welcome_title: e.target.value })}
                    className={`w-full bg-gray-900 border rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none ${
                      (formData.welcome_title?.length || 0) > 256 ? 'border-rose-500' : 'border-gray-700 focus:border-indigo-500'
                    }`}
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                      Message Description
                    </label>
                    <span className={`text-[10px] font-mono ${(formData.welcome_description?.length || 0) > 4096 ? 'text-rose-400 font-bold' : 'text-gray-500'}`}>
                      {formData.welcome_description?.length || 0}/4096
                    </span>
                  </div>
                  <textarea
                    rows={6}
                    value={formData.welcome_description ?? ''}
                    onFocus={() => setActiveInput('welcome_description')}
                    onChange={(e) => handleFieldChange({ welcome_description: e.target.value })}
                    className={`w-full bg-gray-900 border rounded-xl p-3 text-sm text-white font-mono focus:outline-none ${
                      (formData.welcome_description?.length || 0) > 4096 ? 'border-rose-500' : 'border-gray-700 focus:border-indigo-500'
                    }`}
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                      Footer
                    </label>
                    <span className={`text-[10px] font-mono ${(formData.welcome_footer?.length || 0) > 2048 ? 'text-rose-400 font-bold' : 'text-gray-500'}`}>
                      {formData.welcome_footer?.length || 0}/2048
                    </span>
                  </div>
                  <input
                    type="text"
                    value={formData.welcome_footer ?? ''}
                    onFocus={() => setActiveInput('welcome_footer')}
                    onChange={(e) => handleFieldChange({ welcome_footer: e.target.value })}
                    className={`w-full bg-gray-900 border rounded-xl px-4 py-2 text-sm text-white focus:outline-none ${
                      (formData.welcome_footer?.length || 0) > 2048 ? 'border-rose-500' : 'border-gray-700 focus:border-indigo-500'
                    }`}
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

              {/* Welcome Buttons Configuration */}
              <div className="space-y-3 p-4 bg-gray-900/40 rounded-2xl border border-gray-800">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-indigo-400" />
                    Interactive Welcome Buttons (Action Row)
                  </span>
                  <span className="text-[11px] text-gray-500">Enable buttons to attach below welcome message</span>
                </div>

                <div className="space-y-2.5">
                  {getWelcomeButtons().map((btn, idx) => (
                    <div
                      key={btn.id || idx}
                      className="p-3 bg-gray-950/60 rounded-xl border border-gray-800 flex flex-wrap items-center gap-3 text-xs"
                    >
                      <label className="flex items-center gap-2 cursor-pointer font-bold text-white shrink-0">
                        <input
                          type="checkbox"
                          checked={Boolean(btn.enabled)}
                          onChange={(e) => handleUpdateButton(idx, { enabled: e.target.checked })}
                          className="rounded bg-gray-800 border-gray-700 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span>{idx + 1}.</span>
                      </label>

                      <div className="w-16 shrink-0">
                        <input
                          type="text"
                          value={btn.emoji || ''}
                          onChange={(e) => handleUpdateButton(idx, { emoji: e.target.value })}
                          placeholder="Emoji"
                          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2 py-1 text-center text-xs text-white"
                        />
                      </div>

                      <div className="w-32 shrink-0">
                        <input
                          type="text"
                          value={btn.label || ''}
                          onChange={(e) => handleUpdateButton(idx, { label: e.target.value })}
                          placeholder="Label"
                          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2.5 py-1 text-xs text-white"
                        />
                      </div>

                      <div className="flex-1 min-w-[160px]">
                        <input
                          type="text"
                          value={btn.url || ''}
                          onChange={(e) => handleUpdateButton(idx, { url: e.target.value })}
                          placeholder="https://... or {rules_url}"
                          className={`w-full bg-gray-900 border rounded-lg px-2.5 py-1 text-xs text-white font-mono ${
                            btn.url && !btn.url.startsWith('https://') && !btn.url.startsWith('{')
                              ? 'border-amber-500 text-amber-200'
                              : 'border-gray-700'
                          }`}
                        />
                      </div>

                      <span className="text-[10px] px-2 py-0.5 rounded bg-gray-800 text-gray-400 font-mono">
                        Link
                      </span>
                    </div>
                  ))}
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
              embedColor={formData.welcome_accent_color || '#5865F2'}
              bannerMode={formData.welcome_banner_mode || 'none'}
              bannerUrl={formData.welcome_banner_url}
              serverBannerUrl={data.server.server_banner}
              serverIconUrl={data.server.server_icon}
              authorText={formData.welcome_author_text}
              authorIconUrl={formData.welcome_author_icon_url}
              buttons={getWelcomeButtons()}
              showInviter={formData.welcome_show_inviter !== false}
              showInviteCode={formData.welcome_show_invite_code !== false}
              memberCount={data.server.member_count}
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
                  <div className="text-[10px] font-extrabold uppercase tracking-widest text-rose-400">GOODBYE SYSTEM</div>
                  <h2 className="text-lg font-bold text-white">Public Goodbye / Departure Message</h2>
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
              {/* Theme Presets */}
              <div className="space-y-2 p-4 bg-gray-900/50 rounded-2xl border border-gray-800">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-rose-400" />
                    Goodbye Theme Presets
                  </span>
                  <span className="text-[11px] text-gray-500">Pick a preset to style departure messages</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  {Object.entries(THEME_PRESETS).map(([key, preset]) => {
                    const isSelected = (formData.goodbye_theme || 'default') === key;
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setPendingThemeKey(key)}
                        className={`p-2.5 rounded-xl border text-left transition-all flex flex-col gap-1 ${
                          isSelected
                            ? 'bg-rose-600/20 border-rose-500 text-white shadow-sm'
                            : 'bg-gray-900 hover:bg-gray-800/80 border-gray-800 text-gray-300'
                        }`}
                      >
                        <div className="flex items-center justify-between w-full">
                          <span className="text-base">{preset.icon}</span>
                          <span
                            className="w-3 h-3 rounded-full border border-gray-700"
                            style={{ backgroundColor: preset.goodbye_accent_color }}
                          />
                        </div>
                        <span className="text-xs font-bold truncate">{preset.name.split(' ')[0]}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

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
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.goodbye_show_member_count ?? true}
                    onChange={(e) => handleFieldChange({ goodbye_show_member_count: e.target.checked })}
                    className="rounded bg-gray-800 border-gray-700 text-rose-600 focus:ring-rose-500"
                  />
                  Member Count
                </label>
              </div>

              {/* Departure Branding & Accent */}
              <div className="space-y-4 p-4 bg-gray-900/40 rounded-2xl border border-gray-800">
                <span className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Palette className="w-3.5 h-3.5 text-rose-400" />
                  Departure Branding & Accent Color
                </span>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
                      Accent Color
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={formData.goodbye_accent_color || '#ED4245'}
                        onChange={(e) => handleFieldChange({ goodbye_accent_color: e.target.value })}
                        className="w-10 h-10 rounded-xl bg-transparent border border-gray-700 cursor-pointer shrink-0"
                      />
                      <input
                        type="text"
                        value={formData.goodbye_accent_color || '#ED4245'}
                        onChange={(e) => handleFieldChange({ goodbye_accent_color: e.target.value })}
                        placeholder="#ED4245"
                        className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-xs text-white font-mono uppercase focus:outline-none focus:border-rose-500"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
                      Custom Departure Banner URL
                    </label>
                    <input
                      type="url"
                      value={formData.goodbye_banner_url ?? ''}
                      onChange={(e) => handleFieldChange({ goodbye_banner_url: e.target.value })}
                      placeholder="https://... (optional)"
                      className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-rose-500"
                    />
                  </div>
                </div>
              </div>

              {/* Template Editor */}
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                      Message / Embed Title
                    </label>
                    <span className={`text-[10px] font-mono ${(formData.goodbye_title?.length || 0) > 256 ? 'text-rose-400 font-bold' : 'text-gray-500'}`}>
                      {formData.goodbye_title?.length || 0}/256
                    </span>
                  </div>
                  <input
                    type="text"
                    value={formData.goodbye_title ?? ''}
                    onFocus={() => setActiveInput('goodbye_title')}
                    onChange={(e) => handleFieldChange({ goodbye_title: e.target.value })}
                    className={`w-full bg-gray-900 border rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none ${
                      (formData.goodbye_title?.length || 0) > 256 ? 'border-rose-500' : 'border-gray-700 focus:border-rose-500'
                    }`}
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                      Message Description
                    </label>
                    <span className={`text-[10px] font-mono ${(formData.goodbye_description?.length || 0) > 4096 ? 'text-rose-400 font-bold' : 'text-gray-500'}`}>
                      {formData.goodbye_description?.length || 0}/4096
                    </span>
                  </div>
                  <textarea
                    rows={5}
                    value={formData.goodbye_description ?? ''}
                    onFocus={() => setActiveInput('goodbye_description')}
                    onChange={(e) => handleFieldChange({ goodbye_description: e.target.value })}
                    className={`w-full bg-gray-900 border rounded-xl p-3 text-sm text-white font-mono focus:outline-none ${
                      (formData.goodbye_description?.length || 0) > 4096 ? 'border-rose-500' : 'border-gray-700 focus:border-rose-500'
                    }`}
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                      Footer
                    </label>
                    <span className={`text-[10px] font-mono ${(formData.goodbye_footer?.length || 0) > 2048 ? 'text-rose-400 font-bold' : 'text-gray-500'}`}>
                      {formData.goodbye_footer?.length || 0}/2048
                    </span>
                  </div>
                  <input
                    type="text"
                    value={formData.goodbye_footer ?? ''}
                    onFocus={() => setActiveInput('goodbye_footer')}
                    onChange={(e) => handleFieldChange({ goodbye_footer: e.target.value })}
                    className={`w-full bg-gray-900 border rounded-xl px-4 py-2 text-sm text-white focus:outline-none ${
                      (formData.goodbye_footer?.length || 0) > 2048 ? 'border-rose-500' : 'border-gray-700 focus:border-rose-500'
                    }`}
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
              embedColor={formData.goodbye_accent_color || '#ED4245'}
              bannerUrl={formData.goodbye_banner_url}
              bannerMode={formData.goodbye_banner_url ? 'custom' : 'none'}
              serverIconUrl={data.server.server_icon}
              authorText={formData.goodbye_author_text}
              authorIconUrl={formData.goodbye_author_icon_url}
              memberCount={data.server.member_count}
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

      <ConfirmModal
        isOpen={Boolean(pendingThemeKey)}
        onCancel={() => setPendingThemeKey(null)}
        onConfirm={() => {
          if (pendingThemeKey) applyThemePreset(pendingThemeKey);
        }}
        title={`Apply "${THEME_PRESETS[pendingThemeKey || 'default']?.name || 'Theme'}" Preset?`}
        message="This will update your message title, description, and accent color to match this theme preset. Your other settings will remain intact."
        confirmText="Apply Preset"
      />
    </div>
  );
};


export default WelcomeGoodbye;



