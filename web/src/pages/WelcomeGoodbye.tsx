import { useEffect, useState, useRef } from 'react';
import { greetingsApi } from '../api/greetings';
import {
  GreetingsResponse,
  GreetingChannelOption,
  ServerGreetingSettings,
} from '../types';
import { ConfirmModal } from '../components/ConfirmModal';
import { DiscordPreview } from '../components/DiscordPreview';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { toast } from '../hooks/useToast';
import {
  UserPlus,
  UserMinus,
  Hash,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Play,
  RotateCcw,
  Save,
  Server,
  Sparkles,
  ShieldAlert,
  Clock,
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
];

const GOODBYE_VARIABLES = [
  { key: '{username}', desc: 'Member username' },
  { key: '{display_name}', desc: 'Server nickname/display name' },
  { key: '{user_id}', desc: 'Unique Discord User ID' },
  { key: '{server_name}', desc: 'Discord Server Name' },
  { key: '{server_id}', desc: 'Discord Server ID' },
  { key: '{member_count}', desc: 'Member count before leave' },
  { key: '{left_at}', desc: 'Departure timestamp' },
];

export default function WelcomeGoodbye() {
  const [loading, setLoading] = useState(true);
  const [savingWelcome, setSavingWelcome] = useState(false);
  const [savingGoodbye, setSavingGoodbye] = useState(false);
  const [testingWelcome, setTestingWelcome] = useState(false);
  const [testingGoodbye, setTestingGoodbye] = useState(false);

  const [data, setData] = useState<GreetingsResponse | null>(null);
  const [channels, setChannels] = useState<GreetingChannelOption[]>([]);

  // Working state
  const [welcomeSettings, setWelcomeSettings] = useState<Partial<ServerGreetingSettings>>({});
  const [goodbyeSettings, setGoodbyeSettings] = useState<Partial<ServerGreetingSettings>>({});
  const [allowMassMentions, setAllowMassMentions] = useState(false);

  // Original saved state for dirty tracking
  const [origWelcome, setOrigWelcome] = useState<Partial<ServerGreetingSettings>>({});
  const [origGoodbye, setOrigGoodbye] = useState<Partial<ServerGreetingSettings>>({});

  // Reset confirmation modals
  const [resetModal, setResetModal] = useState<'welcome' | 'goodbye' | null>(null);

  // Focus tracking for variable insertion
  const [focusedField, setFocusedField] = useState<'welcome_title' | 'welcome_desc' | 'welcome_footer' | 'goodbye_title' | 'goodbye_desc' | 'goodbye_footer'>('welcome_desc');

  const welcomeTitleRef = useRef<HTMLInputElement>(null);
  const welcomeDescRef = useRef<HTMLTextAreaElement>(null);
  const welcomeFooterRef = useRef<HTMLInputElement>(null);
  const goodbyeTitleRef = useRef<HTMLInputElement>(null);
  const goodbyeDescRef = useRef<HTMLTextAreaElement>(null);
  const goodbyeFooterRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [greetingsRes, channelsRes] = await Promise.all([
        greetingsApi.getGreetings(),
        greetingsApi.getChannels().catch(() => [] as GreetingChannelOption[]),
      ]);
      setData(greetingsRes);
      setChannels(channelsRes);

      const s = greetingsRes.settings;
      const wState: Partial<ServerGreetingSettings> = {
        welcome_enabled: s.welcome_enabled,
        welcome_channel_id: s.welcome_channel_id,
        welcome_title: s.welcome_title,
        welcome_description: s.welcome_description,
        welcome_footer: s.welcome_footer,
        welcome_mention_user: s.welcome_mention_user,
        welcome_show_avatar: s.welcome_show_avatar,
        welcome_show_server_icon: s.welcome_show_server_icon,
        welcome_show_member_count: s.welcome_show_member_count,
        welcome_show_timestamp: s.welcome_show_timestamp,
        welcome_use_embed: s.welcome_use_embed,
      };
      const gState: Partial<ServerGreetingSettings> = {
        goodbye_enabled: s.goodbye_enabled,
        goodbye_channel_id: s.goodbye_channel_id,
        goodbye_title: s.goodbye_title,
        goodbye_description: s.goodbye_description,
        goodbye_footer: s.goodbye_footer,
        goodbye_mention_user: s.goodbye_mention_user,
        goodbye_show_avatar: s.goodbye_show_avatar,
        goodbye_show_server_icon: s.goodbye_show_server_icon,
        goodbye_show_member_count: s.goodbye_show_member_count,
        goodbye_show_timestamp: s.goodbye_show_timestamp,
        goodbye_use_embed: s.goodbye_use_embed,
      };

      setWelcomeSettings(wState);
      setOrigWelcome(wState);
      setGoodbyeSettings(gState);
      setOrigGoodbye(gState);
      setAllowMassMentions(Boolean(s.allow_mass_mentions));
    } catch (err: any) {
      toast.error(err.message || 'Failed to load greetings configuration');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const isWelcomeDirty = JSON.stringify(welcomeSettings) !== JSON.stringify(origWelcome);
  const isGoodbyeDirty = JSON.stringify(goodbyeSettings) !== JSON.stringify(origGoodbye);

  const handleInsertVariable = (variableKey: string) => {
    if (focusedField === 'welcome_title') {
      const cur = welcomeSettings.welcome_title || '';
      setWelcomeSettings({ ...welcomeSettings, welcome_title: cur + variableKey });
      welcomeTitleRef.current?.focus();
    } else if (focusedField === 'welcome_desc') {
      const cur = welcomeSettings.welcome_description || '';
      setWelcomeSettings({ ...welcomeSettings, welcome_description: cur + variableKey });
      welcomeDescRef.current?.focus();
    } else if (focusedField === 'welcome_footer') {
      const cur = welcomeSettings.welcome_footer || '';
      setWelcomeSettings({ ...welcomeSettings, welcome_footer: cur + variableKey });
      welcomeFooterRef.current?.focus();
    } else if (focusedField === 'goodbye_title') {
      const cur = goodbyeSettings.goodbye_title || '';
      setGoodbyeSettings({ ...goodbyeSettings, goodbye_title: cur + variableKey });
      goodbyeTitleRef.current?.focus();
    } else if (focusedField === 'goodbye_desc') {
      const cur = goodbyeSettings.goodbye_description || '';
      setGoodbyeSettings({ ...goodbyeSettings, goodbye_description: cur + variableKey });
      goodbyeDescRef.current?.focus();
    } else if (focusedField === 'goodbye_footer') {
      const cur = goodbyeSettings.goodbye_footer || '';
      setGoodbyeSettings({ ...goodbyeSettings, goodbye_footer: cur + variableKey });
      goodbyeFooterRef.current?.focus();
    }
  };

  const handleSaveWelcome = async () => {
    try {
      setSavingWelcome(true);
      const res = await greetingsApi.updateGreetings({
        ...welcomeSettings,
        allow_mass_mentions: allowMassMentions,
      });
      toast.success('Welcome settings saved successfully');
      setOrigWelcome(welcomeSettings);
      if (res.settings) {
        setData((prev) => (prev ? { ...prev, settings: res.settings } : prev));
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to save welcome settings');
    } finally {
      setSavingWelcome(false);
    }
  };

  const handleSaveGoodbye = async () => {
    try {
      setSavingGoodbye(true);
      const res = await greetingsApi.updateGreetings({
        ...goodbyeSettings,
        allow_mass_mentions: allowMassMentions,
      });
      toast.success('Goodbye settings saved successfully');
      setOrigGoodbye(goodbyeSettings);
      if (res.settings) {
        setData((prev) => (prev ? { ...prev, settings: res.settings } : prev));
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to save goodbye settings');
    } finally {
      setSavingGoodbye(false);
    }
  };

  const handleTestWelcome = async () => {
    try {
      setTestingWelcome(true);
      const res = await greetingsApi.testWelcome();
      toast.success(res.message || 'Test welcome message sent to Discord!');
      const refreshed = await greetingsApi.getGreetings();
      setData(refreshed);
    } catch (err: any) {
      toast.error(err.message || 'Failed to send test welcome message');
    } finally {
      setTestingWelcome(false);
    }
  };

  const handleTestGoodbye = async () => {
    try {
      setTestingGoodbye(true);
      const res = await greetingsApi.testGoodbye();
      toast.success(res.message || 'Test goodbye message sent to Discord!');
      const refreshed = await greetingsApi.getGreetings();
      setData(refreshed);
    } catch (err: any) {
      toast.error(err.message || 'Failed to send test goodbye message');
    } finally {
      setTestingGoodbye(false);
    }
  };

  const handleConfirmReset = async () => {
    if (!resetModal) return;
    const system = resetModal;
    setResetModal(null);
    try {
      const res = await greetingsApi.resetSystem(system);
      toast.success(res.message);
      await loadData();
    } catch (err: any) {
      toast.error(err.message || `Failed to reset ${system} settings`);
    }
  };

  const handleToggleMassMentions = async (checked: boolean) => {
    setAllowMassMentions(checked);
    try {
      await greetingsApi.updateGreetings({ allow_mass_mentions: checked });
      toast.success(checked ? 'Mass mentions enabled' : 'Mass mentions disabled');
    } catch (err: any) {
      setAllowMassMentions(!checked);
      toast.error(err.message || 'Failed to update mass mentions setting');
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 max-w-7xl mx-auto pb-12">
        <div className="h-8 w-64 bg-gray-800 animate-pulse rounded" />
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  const serverName = data?.server?.server_name || 'PB HERO SERVER';
  const serverId = data?.server?.server_id || 'Configured Guild';
  const memberCount = data?.server?.member_count || 142;
  const isBotOnline = data?.server?.bot_online ?? false;

  const selectedWelcomeChannel = channels.find(
    (c) => String(c.id) === String(welcomeSettings.welcome_channel_id)
  );
  const selectedGoodbyeChannel = channels.find(
    (c) => String(c.id) === String(goodbyeSettings.goodbye_channel_id)
  );

  const categories = Array.from(new Set(channels.map((c) => c.category || 'Uncategorized')));

  const renderPreviewText = (template?: string | null, isGoodbye: boolean = false) => {
    if (!template) return '';
    return template
      .replace(/\{username\}/g, isGoodbye ? 'LeavingUser' : 'NewMember')
      .replace(/\{display_name\}/g, isGoodbye ? 'Leaving User' : 'New Member')
      .replace(/\{user_mention\}/g, isGoodbye ? '@LeavingUser' : '@NewMember')
      .replace(/\{user_id\}/g, '987654321012345678')
      .replace(/\{server_name\}/g, serverName)
      .replace(/\{server_id\}/g, serverId)
      .replace(/\{member_count\}/g, String(memberCount))
      .replace(/\{account_created\}/g, '2023-08-15')
      .replace(/\{joined_at\}/g, 'Just now')
      .replace(/\{left_at\}/g, 'Just now');
  };

  return (
    <div className="space-y-8 animate-fade-in max-w-7xl mx-auto pb-16">
      {/* Top Banner: Connected Server Info */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-[#5865F2]/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#5865F2] to-[#3b47c3] flex items-center justify-center font-black text-white text-xl shadow-lg shadow-[#5865F2]/20">
              <Server className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-black text-white tracking-tight">
                  SERVER GREETINGS AUTOMATION
                </h1>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-[#5865F2]/20 text-[#858eff] border border-[#5865F2]/30">
                  SINGLE SERVER BOT
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-4 mt-1.5 text-xs text-gray-400">
                <span className="flex items-center gap-1.5 text-gray-200 font-semibold">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  {serverName}
                </span>
                <span className="text-gray-600">•</span>
                <span>Server ID: <code className="font-mono text-gray-300">{serverId}</code></span>
                <span className="text-gray-600">•</span>
                <span>Total Members: <strong className="text-white">{memberCount}</strong></span>
                <span className="text-gray-600">•</span>
                <span className="flex items-center gap-1">
                  Bot Status:
                  {isBotOnline ? (
                    <span className="text-emerald-400 font-medium">Online & Ready</span>
                  ) : (
                    <span className="text-amber-400 font-medium">Connecting...</span>
                  )}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="bg-[#0f1218] px-4 py-2.5 rounded-xl border border-gray-800 text-center">
              <div className="text-[10px] font-semibold text-gray-400 uppercase">Welcome Sent Today</div>
              <div className="text-lg font-black text-emerald-400">
                {data?.stats?.welcome_sent_today ?? 0}
              </div>
            </div>
            <div className="bg-[#0f1218] px-4 py-2.5 rounded-xl border border-gray-800 text-center">
              <div className="text-[10px] font-semibold text-gray-400 uppercase">Goodbye Sent Today</div>
              <div className="text-lg font-black text-rose-400">
                {data?.stats?.goodbye_sent_today ?? 0}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* ================= WELCOME SYSTEM CARD ================= */}
        <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between space-y-6">
          <div className="space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-gray-800">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white tracking-wide">WELCOME SYSTEM</h2>
                  <p className="text-xs text-gray-400">Sent automatically when a new member joins</p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wider ${
                    welcomeSettings.welcome_enabled
                      ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                      : 'bg-gray-800 text-gray-400 border border-gray-700'
                  }`}
                >
                  {welcomeSettings.welcome_enabled ? 'ACTIVE' : 'DISABLED'}
                </span>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(welcomeSettings.welcome_enabled)}
                    onChange={(e) =>
                      setWelcomeSettings({
                        ...welcomeSettings,
                        welcome_enabled: e.target.checked,
                      })
                    }
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-500" />
                </label>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2">
                <Hash className="w-3.5 h-3.5 text-[#5865F2]" />
                Destination Channel
              </label>
              <select
                value={welcomeSettings.welcome_channel_id || ''}
                onChange={(e) =>
                  setWelcomeSettings({
                    ...welcomeSettings,
                    welcome_channel_id: e.target.value || null,
                  })
                }
                className="w-full bg-[#0f1218] border border-gray-700 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#5865F2] transition-colors"
              >
                <option value="">-- Select Discord Text Channel --</option>
                {categories.map((cat) => (
                  <optgroup key={cat} label={`📂 ${cat}`}>
                    {channels
                      .filter((c) => (c.category || 'Uncategorized') === cat)
                      .map((c) => (
                        <option
                          key={c.id}
                          value={c.id}
                          disabled={!c.is_selectable}
                        >
                          #{c.name} {c.type === 'announcement' ? '📢' : ''} (ID: {c.id}) {!c.is_selectable ? '— [No Send Permission]' : ''}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>

              <div className="bg-[#0b0e14] border border-gray-800 rounded-xl p-3.5 space-y-2 text-xs">
                <div className="flex items-center justify-between text-[11px] font-bold text-gray-400 uppercase tracking-wider">
                  <span>Bot Channel Access</span>
                  {selectedWelcomeChannel && (
                    <span className="font-mono text-gray-300">#{selectedWelcomeChannel.name}</span>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-2 text-center pt-1">
                  <div className="bg-[#151921] p-2 rounded-lg border border-gray-800">
                    <div className="text-[10px] text-gray-400 mb-1">View Channel</div>
                    {selectedWelcomeChannel?.can_view ? (
                      <span className="text-emerald-400 font-bold flex items-center justify-center gap-1">
                        <CheckCircle className="w-3.5 h-3.5" /> YES
                      </span>
                    ) : (
                      <span className="text-rose-400 font-bold flex items-center justify-center gap-1">
                        <XCircle className="w-3.5 h-3.5" /> NO
                      </span>
                    )}
                  </div>
                  <div className="bg-[#151921] p-2 rounded-lg border border-gray-800">
                    <div className="text-[10px] text-gray-400 mb-1">Send Messages</div>
                    {selectedWelcomeChannel?.can_send ? (
                      <span className="text-emerald-400 font-bold flex items-center justify-center gap-1">
                        <CheckCircle className="w-3.5 h-3.5" /> YES
                      </span>
                    ) : (
                      <span className="text-rose-400 font-bold flex items-center justify-center gap-1">
                        <XCircle className="w-3.5 h-3.5" /> NO
                      </span>
                    )}
                  </div>
                  <div className="bg-[#151921] p-2 rounded-lg border border-gray-800">
                    <div className="text-[10px] text-gray-400 mb-1">Embed Links</div>
                    {selectedWelcomeChannel?.can_embed ? (
                      <span className="text-emerald-400 font-bold flex items-center justify-center gap-1">
                        <CheckCircle className="w-3.5 h-3.5" /> YES
                      </span>
                    ) : (
                      <span className="text-rose-400 font-bold flex items-center justify-center gap-1">
                        <XCircle className="w-3.5 h-3.5" /> NO
                      </span>
                    )}
                  </div>
                </div>

                {welcomeSettings.welcome_channel_id && selectedWelcomeChannel && (!selectedWelcomeChannel.can_send || !selectedWelcomeChannel.can_view) && (
                  <div className="bg-rose-500/10 border border-rose-500/30 rounded-lg p-2.5 text-rose-300 text-xs flex items-center gap-2 mt-2">
                    <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>Selected channel is unavailable or bot lacks SEND_MESSAGES permission.</span>
                  </div>
                )}
                {welcomeSettings.welcome_channel_id && !selectedWelcomeChannel && (
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-2.5 text-amber-300 text-xs flex items-center gap-2 mt-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    <span>Selected channel is unavailable. It may have been deleted in Discord.</span>
                  </div>
                )}
              </div>
            </div>

            <div className="bg-[#0f1218] border border-gray-800 rounded-xl p-4 space-y-3">
              <h3 className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                Visual Display Options
              </h3>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(welcomeSettings.welcome_use_embed)}
                    onChange={(e) =>
                      setWelcomeSettings({ ...welcomeSettings, welcome_use_embed: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-[#5865F2] focus:ring-0"
                  />
                  <span className="text-gray-300">Rich Embed</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(welcomeSettings.welcome_mention_user)}
                    onChange={(e) =>
                      setWelcomeSettings({ ...welcomeSettings, welcome_mention_user: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-[#5865F2] focus:ring-0"
                  />
                  <span className="text-gray-300">Mention New Member</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(welcomeSettings.welcome_show_avatar)}
                    onChange={(e) =>
                      setWelcomeSettings({ ...welcomeSettings, welcome_show_avatar: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-[#5865F2] focus:ring-0"
                  />
                  <span className="text-gray-300">Show User Avatar</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(welcomeSettings.welcome_show_server_icon)}
                    onChange={(e) =>
                      setWelcomeSettings({ ...welcomeSettings, welcome_show_server_icon: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-[#5865F2] focus:ring-0"
                  />
                  <span className="text-gray-300">Show Server Icon</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(welcomeSettings.welcome_show_member_count)}
                    onChange={(e) =>
                      setWelcomeSettings({ ...welcomeSettings, welcome_show_member_count: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-[#5865F2] focus:ring-0"
                  />
                  <span className="text-gray-300">Show Member Count</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(welcomeSettings.welcome_show_timestamp)}
                    onChange={(e) =>
                      setWelcomeSettings({ ...welcomeSettings, welcome_show_timestamp: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-[#5865F2] focus:ring-0"
                  />
                  <span className="text-gray-300">Show Timestamp</span>
                </label>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-gray-300 block mb-1">
                  Message / Embed Title
                </label>
                <input
                  ref={welcomeTitleRef}
                  type="text"
                  value={welcomeSettings.welcome_title || ''}
                  onFocus={() => setFocusedField('welcome_title')}
                  onChange={(e) =>
                    setWelcomeSettings({ ...welcomeSettings, welcome_title: e.target.value })
                  }
                  placeholder="👋 Welcome to {server_name}!"
                  className="w-full bg-[#0f1218] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-300 block mb-1">
                  Message / Embed Description
                </label>
                <textarea
                  ref={welcomeDescRef}
                  rows={4}
                  value={welcomeSettings.welcome_description || ''}
                  onFocus={() => setFocusedField('welcome_desc')}
                  onChange={(e) =>
                    setWelcomeSettings({ ...welcomeSettings, welcome_description: e.target.value })
                  }
                  placeholder="Welcome {user_mention} to {server_name}! ❤️"
                  className="w-full bg-[#0f1218] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2] font-mono"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-300 block mb-1">Footer Text</label>
                <input
                  ref={welcomeFooterRef}
                  type="text"
                  value={welcomeSettings.welcome_footer || ''}
                  onFocus={() => setFocusedField('welcome_footer')}
                  onChange={(e) =>
                    setWelcomeSettings({ ...welcomeSettings, welcome_footer: e.target.value })
                  }
                  placeholder="PB HERO SERVER"
                  className="w-full bg-[#0f1218] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                />
              </div>

              <div className="bg-[#0b0e14] border border-gray-800 rounded-xl p-3 space-y-1.5">
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
                  Available Variables (Click to insert into focused field)
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {WELCOME_VARIABLES.map((v) => (
                    <button
                      key={v.key}
                      type="button"
                      title={v.desc}
                      onClick={() => handleInsertVariable(v.key)}
                      className="px-2 py-1 bg-[#151921] hover:bg-[#5865F2]/20 hover:text-[#858eff] border border-gray-800 hover:border-[#5865F2]/40 rounded text-[11px] font-mono text-gray-300 transition-colors"
                    >
                      {v.key}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <DiscordPreview
              title={renderPreviewText(welcomeSettings.welcome_title, false)}
              description={renderPreviewText(welcomeSettings.welcome_description, false)}
              footer={renderPreviewText(welcomeSettings.welcome_footer, false)}
              useEmbed={welcomeSettings.welcome_use_embed}
              mentionUser={welcomeSettings.welcome_mention_user}
              mentionTag="@NewMember"
              showAvatar={welcomeSettings.welcome_show_avatar}
              showServerIcon={welcomeSettings.welcome_show_server_icon}
              showTimestamp={welcomeSettings.welcome_show_timestamp}
              embedColor="#5865F2"
              serverName={serverName}
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-gray-800">
            <button
              type="button"
              onClick={() => setResetModal('welcome')}
              className="px-3 py-2 text-xs font-semibold text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-xl transition-colors flex items-center gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Welcome
            </button>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                disabled={testingWelcome || !welcomeSettings.welcome_channel_id}
                onClick={handleTestWelcome}
                className="px-3.5 py-2 text-xs font-bold text-white bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 rounded-xl transition-all shadow flex items-center gap-1.5"
              >
                <Play className="w-3.5 h-3.5 text-emerald-400" />
                {testingWelcome ? 'Testing...' : 'Test Welcome'}
              </button>

              <button
                type="button"
                disabled={savingWelcome || !isWelcomeDirty}
                onClick={handleSaveWelcome}
                className="px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-800 disabled:text-gray-600 rounded-xl transition-all shadow flex items-center gap-1.5"
              >
                <Save className="w-3.5 h-3.5" />
                {savingWelcome ? 'Saving...' : 'Save Welcome'}
              </button>
            </div>
          </div>
        </div>
        {/* ================= GOODBYE SYSTEM CARD ================= */}
        <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl flex flex-col justify-between space-y-6">
          <div className="space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-gray-800">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-rose-500/10 text-rose-400 flex items-center justify-center">
                  <UserMinus className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white tracking-wide">GOODBYE SYSTEM</h2>
                  <p className="text-xs text-gray-400">Sent automatically when a member leaves the server</p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wider ${
                    goodbyeSettings.goodbye_enabled
                      ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                      : 'bg-gray-800 text-gray-400 border border-gray-700'
                  }`}
                >
                  {goodbyeSettings.goodbye_enabled ? 'ACTIVE' : 'DISABLED'}
                </span>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(goodbyeSettings.goodbye_enabled)}
                    onChange={(e) =>
                      setGoodbyeSettings({
                        ...goodbyeSettings,
                        goodbye_enabled: e.target.checked,
                      })
                    }
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-rose-500" />
                </label>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-gray-300 uppercase tracking-wider flex items-center gap-2">
                <Hash className="w-3.5 h-3.5 text-rose-400" />
                Destination Channel
              </label>
              <select
                value={goodbyeSettings.goodbye_channel_id || ''}
                onChange={(e) =>
                  setGoodbyeSettings({
                    ...goodbyeSettings,
                    goodbye_channel_id: e.target.value || null,
                  })
                }
                className="w-full bg-[#0f1218] border border-gray-700 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-rose-500 transition-colors"
              >
                <option value="">-- Select Discord Text Channel --</option>
                {categories.map((cat) => (
                  <optgroup key={cat} label={`📂 ${cat}`}>
                    {channels
                      .filter((c) => (c.category || 'Uncategorized') === cat)
                      .map((c) => (
                        <option
                          key={c.id}
                          value={c.id}
                          disabled={!c.is_selectable}
                        >
                          #{c.name} {c.type === 'announcement' ? '📢' : ''} (ID: {c.id}) {!c.is_selectable ? '— [No Send Permission]' : ''}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>

              <div className="bg-[#0b0e14] border border-gray-800 rounded-xl p-3.5 space-y-2 text-xs">
                <div className="flex items-center justify-between text-[11px] font-bold text-gray-400 uppercase tracking-wider">
                  <span>Bot Channel Access</span>
                  {selectedGoodbyeChannel && (
                    <span className="font-mono text-gray-300">#{selectedGoodbyeChannel.name}</span>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-2 text-center pt-1">
                  <div className="bg-[#151921] p-2 rounded-lg border border-gray-800">
                    <div className="text-[10px] text-gray-400 mb-1">View Channel</div>
                    {selectedGoodbyeChannel?.can_view ? (
                      <span className="text-emerald-400 font-bold flex items-center justify-center gap-1">
                        <CheckCircle className="w-3.5 h-3.5" /> YES
                      </span>
                    ) : (
                      <span className="text-rose-400 font-bold flex items-center justify-center gap-1">
                        <XCircle className="w-3.5 h-3.5" /> NO
                      </span>
                    )}
                  </div>
                  <div className="bg-[#151921] p-2 rounded-lg border border-gray-800">
                    <div className="text-[10px] text-gray-400 mb-1">Send Messages</div>
                    {selectedGoodbyeChannel?.can_send ? (
                      <span className="text-emerald-400 font-bold flex items-center justify-center gap-1">
                        <CheckCircle className="w-3.5 h-3.5" /> YES
                      </span>
                    ) : (
                      <span className="text-rose-400 font-bold flex items-center justify-center gap-1">
                        <XCircle className="w-3.5 h-3.5" /> NO
                      </span>
                    )}
                  </div>
                  <div className="bg-[#151921] p-2 rounded-lg border border-gray-800">
                    <div className="text-[10px] text-gray-400 mb-1">Embed Links</div>
                    {selectedGoodbyeChannel?.can_embed ? (
                      <span className="text-emerald-400 font-bold flex items-center justify-center gap-1">
                        <CheckCircle className="w-3.5 h-3.5" /> YES
                      </span>
                    ) : (
                      <span className="text-rose-400 font-bold flex items-center justify-center gap-1">
                        <XCircle className="w-3.5 h-3.5" /> NO
                      </span>
                    )}
                  </div>
                </div>

                {goodbyeSettings.goodbye_channel_id && selectedGoodbyeChannel && (!selectedGoodbyeChannel.can_send || !selectedGoodbyeChannel.can_view) && (
                  <div className="bg-rose-500/10 border border-rose-500/30 rounded-lg p-2.5 text-rose-300 text-xs flex items-center gap-2 mt-2">
                    <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>Selected channel is unavailable or bot lacks SEND_MESSAGES permission.</span>
                  </div>
                )}
                {goodbyeSettings.goodbye_channel_id && !selectedGoodbyeChannel && (
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-2.5 text-amber-300 text-xs flex items-center gap-2 mt-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    <span>Selected channel is unavailable. It may have been deleted in Discord.</span>
                  </div>
                )}
              </div>
            </div>

            <div className="bg-[#0f1218] border border-gray-800 rounded-xl p-4 space-y-3">
              <h3 className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-rose-400" />
                Visual Display Options
              </h3>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(goodbyeSettings.goodbye_use_embed)}
                    onChange={(e) =>
                      setGoodbyeSettings({ ...goodbyeSettings, goodbye_use_embed: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-rose-500 focus:ring-0"
                  />
                  <span className="text-gray-300">Rich Embed</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(goodbyeSettings.goodbye_mention_user)}
                    onChange={(e) =>
                      setGoodbyeSettings({ ...goodbyeSettings, goodbye_mention_user: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-rose-500 focus:ring-0"
                  />
                  <span className="text-gray-300">Mention User Tag</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(goodbyeSettings.goodbye_show_avatar)}
                    onChange={(e) =>
                      setGoodbyeSettings({ ...goodbyeSettings, goodbye_show_avatar: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-rose-500 focus:ring-0"
                  />
                  <span className="text-gray-300">Show User Avatar</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(goodbyeSettings.goodbye_show_server_icon)}
                    onChange={(e) =>
                      setGoodbyeSettings({ ...goodbyeSettings, goodbye_show_server_icon: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-rose-500 focus:ring-0"
                  />
                  <span className="text-gray-300">Show Server Icon</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(goodbyeSettings.goodbye_show_member_count)}
                    onChange={(e) =>
                      setGoodbyeSettings({ ...goodbyeSettings, goodbye_show_member_count: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-rose-500 focus:ring-0"
                  />
                  <span className="text-gray-300">Show Member Count</span>
                </label>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(goodbyeSettings.goodbye_show_timestamp)}
                    onChange={(e) =>
                      setGoodbyeSettings({ ...goodbyeSettings, goodbye_show_timestamp: e.target.checked })
                    }
                    className="rounded bg-gray-900 border-gray-700 text-rose-500 focus:ring-0"
                  />
                  <span className="text-gray-300">Show Timestamp</span>
                </label>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-gray-300 block mb-1">
                  Message / Embed Title
                </label>
                <input
                  ref={goodbyeTitleRef}
                  type="text"
                  value={goodbyeSettings.goodbye_title || ''}
                  onFocus={() => setFocusedField('goodbye_title')}
                  onChange={(e) =>
                    setGoodbyeSettings({ ...goodbyeSettings, goodbye_title: e.target.value })
                  }
                  placeholder="👋 Goodbye {display_name}"
                  className="w-full bg-[#0f1218] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-rose-500"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-300 block mb-1">
                  Message / Embed Description
                </label>
                <textarea
                  ref={goodbyeDescRef}
                  rows={4}
                  value={goodbyeSettings.goodbye_description || ''}
                  onFocus={() => setFocusedField('goodbye_desc')}
                  onChange={(e) =>
                    setGoodbyeSettings({ ...goodbyeSettings, goodbye_description: e.target.value })
                  }
                  placeholder="**{display_name}** has left {server_name}."
                  className="w-full bg-[#0f1218] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-rose-500 font-mono"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-300 block mb-1">Footer Text</label>
                <input
                  ref={goodbyeFooterRef}
                  type="text"
                  value={goodbyeSettings.goodbye_footer || ''}
                  onFocus={() => setFocusedField('goodbye_footer')}
                  onChange={(e) =>
                    setGoodbyeSettings({ ...goodbyeSettings, goodbye_footer: e.target.value })
                  }
                  placeholder="PB HERO SERVER"
                  className="w-full bg-[#0f1218] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-rose-500"
                />
              </div>

              <div className="bg-[#0b0e14] border border-gray-800 rounded-xl p-3 space-y-1.5">
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
                  Available Variables (Click to insert into focused field)
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {GOODBYE_VARIABLES.map((v) => (
                    <button
                      key={v.key}
                      type="button"
                      title={v.desc}
                      onClick={() => handleInsertVariable(v.key)}
                      className="px-2 py-1 bg-[#151921] hover:bg-rose-500/20 hover:text-rose-300 border border-gray-800 hover:border-rose-500/40 rounded text-[11px] font-mono text-gray-300 transition-colors"
                    >
                      {v.key}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <DiscordPreview
              title={renderPreviewText(goodbyeSettings.goodbye_title, true)}
              description={renderPreviewText(goodbyeSettings.goodbye_description, true)}
              footer={renderPreviewText(goodbyeSettings.goodbye_footer, true)}
              useEmbed={goodbyeSettings.goodbye_use_embed}
              mentionUser={goodbyeSettings.goodbye_mention_user}
              mentionTag="@LeavingUser"
              showAvatar={goodbyeSettings.goodbye_show_avatar}
              showServerIcon={goodbyeSettings.goodbye_show_server_icon}
              showTimestamp={goodbyeSettings.goodbye_show_timestamp}
              embedColor="#ED4245"
              serverName={serverName}
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-gray-800">
            <button
              type="button"
              onClick={() => setResetModal('goodbye')}
              className="px-3 py-2 text-xs font-semibold text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-xl transition-colors flex items-center gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Goodbye
            </button>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                disabled={testingGoodbye || !goodbyeSettings.goodbye_channel_id}
                onClick={handleTestGoodbye}
                className="px-3.5 py-2 text-xs font-bold text-white bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 rounded-xl transition-all shadow flex items-center gap-1.5"
              >
                <Play className="w-3.5 h-3.5 text-rose-400" />
                {testingGoodbye ? 'Testing...' : 'Test Goodbye'}
              </button>

              <button
                type="button"
                disabled={savingGoodbye || !isGoodbyeDirty}
                onClick={handleSaveGoodbye}
                className="px-4 py-2 text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 disabled:bg-gray-800 disabled:text-gray-600 rounded-xl transition-all shadow flex items-center gap-1.5"
              >
                <Save className="w-3.5 h-3.5" />
                {savingGoodbye ? 'Saving...' : 'Save Goodbye'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Advanced Settings */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-wide">ADVANCED SETTINGS & SAFETY CONTROLS</h3>
            <p className="text-xs text-gray-400">Protections against accidental mass server notifications</p>
          </div>
        </div>

        <div className="bg-[#0b0e14] border border-gray-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="text-xs font-bold text-white flex items-center gap-2">
              <span>Allow Mass Mentions (@everyone, @here)</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
                DEFAULT: OFF
              </span>
            </div>
            <p className="text-xs text-gray-400 max-w-2xl leading-relaxed">
              When disabled, any accidental @everyone or @here in templates will be rejected at save time and sanitized in Discord delivery to prevent unexpected server-wide pings.
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={allowMassMentions}
              onChange={(e) => handleToggleMassMentions(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500" />
          </label>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#5865F2]/10 text-[#858eff] flex items-center justify-center">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white tracking-wide">RECENT GREETING ACTIVITY</h3>
              <p className="text-xs text-gray-400">Live delivery logs for joins, departures, and test dispatches</p>
            </div>
          </div>
          <button
            type="button"
            onClick={loadData}
            className="text-xs text-gray-400 hover:text-white px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors flex items-center gap-1.5"
          >
            <RotateCcw className="w-3 h-3" /> Refresh
          </button>
        </div>

        {data?.recent_activity && data.recent_activity.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-gray-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0b0e14] text-gray-400 uppercase text-[10px] tracking-wider border-b border-gray-800">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Event</th>
                  <th className="py-3 px-4">Member / Username</th>
                  <th className="py-3 px-4">Target Channel</th>
                  <th className="py-3 px-4">Delivery Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 font-mono">
                {data.recent_activity.map((act) => (
                  <tr key={act.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="py-3 px-4 text-gray-400 whitespace-nowrap">
                      {new Date(act.timestamp).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </td>
                    <td className="py-3 px-4">
                      {act.event_type === 'welcome' ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 uppercase">
                          WELCOME {act.is_test ? '🧪 TEST' : ''}
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30 uppercase">
                          GOODBYE {act.is_test ? '🧪 TEST' : ''}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-sans text-gray-200 font-medium">
                      {act.username}
                    </td>
                    <td className="py-3 px-4 text-gray-300">
                      #{act.channel_name}
                    </td>
                    <td className="py-3 px-4">
                      {act.status === 'delivered' ? (
                        <span className="inline-flex items-center gap-1.5 text-emerald-400 font-sans font-semibold">
                          <CheckCircle className="w-3.5 h-3.5" /> Delivered
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-rose-400 font-sans font-semibold" title={act.error_message || ''}>
                          <XCircle className="w-3.5 h-3.5" /> Failed
                          {act.error_message && (
                            <span className="text-[10px] text-gray-400 font-mono">({act.error_message})</span>
                          )}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center bg-[#0b0e14] border border-gray-800 rounded-xl text-gray-400 text-xs">
            No recent welcome or goodbye activity recorded yet.
          </div>
        )}
      </div>

      <ConfirmModal
        isOpen={Boolean(resetModal)}
        title={`Reset ${resetModal === 'welcome' ? 'Welcome' : 'Goodbye'} Settings?`}
        message={`Are you sure you want to reset the ${
          resetModal === 'welcome' ? 'Welcome' : 'Goodbye'
        } message template and settings back to system defaults? The other greeting system will remain untouched.`}
        confirmText="Reset to Default"
        isDangerous={true}
        onConfirm={handleConfirmReset}
        onCancel={() => setResetModal(null)}
      />
    </div>
  );
}
