import { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { youtubeApi } from '../api/youtube';
import { channelsApi } from '../api/channels';
import {
  YouTubeChannel,
  DiscordChannel,
  DiscordRole,
  NotificationTemplate,
  YouTubeEventType,
} from '../types';
import { YouTubeChannelCard } from '../components/YouTubeChannelCard';
import { YouTubeChannelModal } from '../components/YouTubeChannelModal';
import { NotificationPreview } from '../components/NotificationPreview';
import { ConfirmModal } from '../components/ConfirmModal';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { EmptyState } from '../components/EmptyState';
import { toast } from '../hooks/useToast';
import {
  Youtube,
  Plus,
  Bell,
  Sliders,
  CheckCircle2,
  ListTree,
  ExternalLink,
  RotateCcw,
  Save,
  Video,
  Radio,
  Clock,
  Sparkles,
} from 'lucide-react';

const VALID_TABS = ['channels', 'notifications', 'settings'] as const;
type TabType = (typeof VALID_TABS)[number];

const EVENT_METADATA: Record<
  YouTubeEventType,
  {
    label: string;
    icon: typeof Video;
    badge: string;
    button: string;
    borderColor: string;
    sampleTitle: string;
    variables: string[];
    descriptionHelp: string;
  }
> = {
  upload: {
    label: 'New Video',
    icon: Video,
    badge: 'NEW VIDEO',
    button: 'Watch Video',
    borderColor: '#ED4245',
    sampleTitle: 'PB HERO Bot Update: New Features Released',
    variables: ['{channel_name}', '{video_title}', '{video_url}', '{channel_id}', '{published_at}'],
    descriptionHelp: 'Sent when a new video is published to YouTube.',
  },
  scheduled_live: {
    label: 'Scheduled Live',
    icon: Clock,
    badge: 'SCHEDULED',
    button: 'Watch Live',
    borderColor: '#FEE75C',
    sampleTitle: 'Community Q&A and Bot Showcase',
    variables: ['{channel_name}', '{video_title}', '{video_url}', '{scheduled_start}'],
    descriptionHelp: 'Sent when a live stream is scheduled with a future start time.',
  },
  live_started: {
    label: 'Live Started',
    icon: Radio,
    badge: 'LIVE',
    button: 'Watch Live',
    borderColor: '#ED4245',
    sampleTitle: 'EPIC LIVESTREAM: PB HERO Discord Bot Walkthrough',
    variables: ['{channel_name}', '{video_title}', '{video_url}', '{viewer_count}', '{started_at}'],
    descriptionHelp: 'Sent immediately when the channel goes live on YouTube.',
  },
  premiere: {
    label: 'Premiere',
    icon: Sparkles,
    badge: 'PREMIERE',
    button: 'Watch Premiere',
    borderColor: '#9B59B6',
    sampleTitle: 'Special Premiere: Season 2 Launch',
    variables: ['{channel_name}', '{video_title}', '{video_url}', '{scheduled_start}'],
    descriptionHelp: 'Sent when a scheduled video premiere is announced.',
  },
};

const DEFAULT_TEMPLATES: Record<YouTubeEventType, NotificationTemplate> = {
  upload: {
    event_type: 'upload',
    title_template: '🎬 NEW VIDEO — {channel_name}',
    description_template: '**{video_title}**\n\nA new video is now available on YouTube.',
    mention_role: 'PB Gang',
    footer_text: 'PB HERO Personal Bot',
    show_thumbnail: true,
    show_timestamp: true,
    enable_button: true,
  },
  scheduled_live: {
    event_type: 'scheduled_live',
    title_template: '⏰ LIVE SCHEDULED — {channel_name}',
    description_template: '**{video_title}**\n\nThe livestream is scheduled to start soon.',
    mention_role: 'PB Gang',
    footer_text: 'PB HERO Personal Bot',
    show_thumbnail: true,
    show_timestamp: true,
    enable_button: true,
  },
  live_started: {
    event_type: 'live_started',
    title_template: '🔴 {channel_name} IS NOW LIVE!',
    description_template: '**{video_title}**\n\nJoin the stream now on YouTube.',
    mention_role: 'PB Gang',
    footer_text: 'PB HERO Personal Bot',
    show_thumbnail: true,
    show_timestamp: true,
    enable_button: true,
  },
  premiere: {
    event_type: 'premiere',
    title_template: '🎬 PREMIERE — {channel_name}',
    description_template: '**{video_title}**\n\nA new YouTube Premiere is scheduled.',
    mention_role: 'PB Gang',
    footer_text: 'PB HERO Personal Bot',
    show_thumbnail: true,
    show_timestamp: true,
    enable_button: true,
  },
};

export default function YouTube() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get('tab');
  const currentTab: TabType =
    rawTab && (VALID_TABS as readonly string[]).includes(rawTab)
      ? (rawTab as TabType)
      : 'channels';

  // Normalize URL query parameter if invalid or missing
  useEffect(() => {
    if (!rawTab || !(VALID_TABS as readonly string[]).includes(rawTab)) {
      setSearchParams({ tab: 'channels' }, { replace: true });
    }
  }, [rawTab, setSearchParams]);

  const [loading, setLoading] = useState(true);
  const [channels, setChannels] = useState<YouTubeChannel[]>([]);
  const [discordChannels, setDiscordChannels] = useState<DiscordChannel[]>([]);
  const [roles, setRoles] = useState<DiscordRole[]>([]);

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  // Notification Template State
  const [templates, setTemplates] =
    useState<Record<YouTubeEventType, NotificationTemplate>>(DEFAULT_TEMPLATES);
  const [activeEvent, setActiveEvent] = useState<YouTubeEventType>('upload');
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [lastFocusedField, setLastFocusedField] = useState<'title' | 'description' | 'footer'>('description');
  const titleInputRef = useRef<HTMLInputElement>(null);
  const descTextareaRef = useRef<HTMLTextAreaElement>(null);
  const footerInputRef = useRef<HTMLInputElement>(null);

  // Settings state
  const [pollInterval, setPollInterval] = useState('60');
  const [liveInterval, setLiveInterval] = useState('30');
  const [savingSettings, setSavingSettings] = useState(false);

  // Feed test state
  const [testResult, setTestResult] = useState<{
    channelId: string;
    success: boolean;
    entries: any[];
    error?: string | null;
  } | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [ytList, chList, rList, tmplList] = await Promise.all([
        youtubeApi.getChannels(),
        channelsApi.getChannels(),
        channelsApi.getRoles(),
        youtubeApi.getTemplates().catch(() => []),
      ]);
      setChannels(ytList);
      setDiscordChannels(chList);
      setRoles(rList);

      if (tmplList && Array.isArray(tmplList) && tmplList.length > 0) {
        const map = { ...DEFAULT_TEMPLATES };
        for (const item of tmplList) {
          if (item.event_type && (map as any)[item.event_type]) {
            map[item.event_type as YouTubeEventType] = item;
          }
        }
        setTemplates(map);
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to load YouTube data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTabChange = (newTab: TabType) => {
    setSearchParams({ tab: newTab });
  };

  const currentTemplate = templates[activeEvent] || DEFAULT_TEMPLATES[activeEvent];

  const updateActiveField = <K extends keyof NotificationTemplate>(
    field: K,
    val: NotificationTemplate[K]
  ) => {
    setTemplates((prev) => ({
      ...prev,
      [activeEvent]: {
        ...prev[activeEvent],
        [field]: val,
      },
    }));
  };

  const handleInsertVariable = (variable: string) => {
    if (lastFocusedField === 'title') {
      const current = currentTemplate.title_template || '';
      updateActiveField('title_template', current ? `${current} ${variable}` : variable);
      titleInputRef.current?.focus();
    } else if (lastFocusedField === 'footer') {
      const current = currentTemplate.footer_text || '';
      updateActiveField('footer_text', current ? `${current} ${variable}` : variable);
      footerInputRef.current?.focus();
    } else {
      const current = currentTemplate.description_template || '';
      updateActiveField('description_template', current ? `${current} ${variable}` : variable);
      descTextareaRef.current?.focus();
    }
  };

  const validateTemplate = (t: NotificationTemplate, event: YouTubeEventType): string | null => {
    if (!t.title_template || !t.title_template.trim()) {
      return 'Notification Title Template cannot be empty.';
    }
    if (t.title_template.length > 256) {
      return `Title template exceeds maximum limit of 256 characters (currently ${t.title_template.length}).`;
    }
    if (!t.description_template || !t.description_template.trim()) {
      return 'Embed Description cannot be empty.';
    }
    if (t.description_template.length > 2000) {
      return `Description template exceeds maximum limit of 2000 characters (currently ${t.description_template.length}).`;
    }
    if (t.footer_text && t.footer_text.length > 256) {
      return `Footer text exceeds maximum limit of 256 characters (currently ${t.footer_text.length}).`;
    }

    // Check for unsupported variables
    const allowed = new Set(EVENT_METADATA[event].variables);
    const extractVars = (str: string) => str.match(/\{[a-zA-Z0-9_]+\}/g) || [];
    const used = [
      ...extractVars(t.title_template),
      ...extractVars(t.description_template),
      ...extractVars(t.footer_text || ''),
    ];

    for (const v of used) {
      if (!allowed.has(v)) {
        return `Variable "${v}" is not supported for ${EVENT_METADATA[event].label}. Available variables: ${EVENT_METADATA[event].variables.join(', ')}`;
      }
    }

    return null;
  };

  const handleSaveTemplate = async () => {
    const errorMsg = validateTemplate(currentTemplate, activeEvent);
    if (errorMsg) {
      toast.error(errorMsg);
      return;
    }

    setSavingTemplate(true);
    try {
      const res = await youtubeApi.updateTemplate(activeEvent, {
        title_template: currentTemplate.title_template,
        description_template: currentTemplate.description_template,
        mention_role: currentTemplate.mention_role,
        footer_text: currentTemplate.footer_text,
        show_thumbnail: currentTemplate.show_thumbnail,
        show_timestamp: currentTemplate.show_timestamp,
        enable_button: currentTemplate.enable_button,
      });

      if (res.template) {
        setTemplates((prev) => ({
          ...prev,
          [activeEvent]: res.template,
        }));
      }
      toast.success(`${EVENT_METADATA[activeEvent].label} template saved successfully`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to save template');
    } finally {
      setSavingTemplate(false);
    }
  };

  const handleResetTemplateConfirm = async () => {
    try {
      const res = await youtubeApi.resetTemplate(activeEvent);
      if (res.template) {
        setTemplates((prev) => ({
          ...prev,
          [activeEvent]: res.template,
        }));
      } else {
        setTemplates((prev) => ({
          ...prev,
          [activeEvent]: DEFAULT_TEMPLATES[activeEvent],
        }));
      }
      toast.success(`${EVENT_METADATA[activeEvent].label} template reset to default`);
      setIsResetModalOpen(false);
    } catch (err: any) {
      toast.error(err.message || 'Failed to reset template');
    }
  };

  const renderPreviewText = (text: string, event: YouTubeEventType) => {
    if (!text) return '';
    return text
      .replace(/\{channel_name\}/g, 'PB HERO GAMER')
      .replace(/\{channel_id\}/g, 'UC123456789PBHERO')
      .replace(/\{video_title\}/g, EVENT_METADATA[event].sampleTitle)
      .replace(/\{video_url\}/g, 'https://youtube.com/watch?v=dQw4w9WgXcQ')
      .replace(/\{published_at\}/g, 'Today at 6:00 PM')
      .replace(/\{scheduled_start\}/g, 'Tomorrow at 8:00 PM UTC')
      .replace(/\{viewer_count\}/g, '1,420')
      .replace(/\{started_at\}/g, 'Just now');
  };

  const handleAddChannel = async (payload: any) => {
    const res = await youtubeApi.addChannel(payload);
    toast.success(`Added YouTube channel: ${res.channel_name}`);
    await loadData();
  };

  const handleToggleChannel = async (id: string, enabled: boolean) => {
    try {
      await youtubeApi.toggleChannel(id, enabled);
      toast.success(enabled ? 'Channel monitoring enabled' : 'Channel monitoring paused');
      setChannels((prev) =>
        prev.map((c) => (c.youtube_channel_id === id ? { ...c, enabled } : c))
      );
    } catch (err: any) {
      toast.error(err.message || 'Failed to toggle channel status');
    }
  };

  const handleTestChannel = async (id: string) => {
    try {
      toast.info('Testing YouTube feed parser...');
      const res = await youtubeApi.testChannel(id);
      if (res.success) {
        toast.success(`Feed check succeeded (${res.entry_count} entries found)`);
        setTestResult({
          channelId: id,
          success: true,
          entries: res.entries,
        });
      } else {
        toast.error(res.error || 'Feed check failed');
        setTestResult({
          channelId: id,
          success: false,
          entries: [],
          error: res.error,
        });
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to test feed');
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await youtubeApi.deleteChannel(deleteTarget.id);
      toast.success(`Deleted channel: ${deleteTarget.name}`);
      setChannels((prev) => prev.filter((c) => c.youtube_channel_id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete channel');
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
            <Youtube className="w-7 h-7 text-red-500" />
            <span>YouTube Monitor</span>
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Private RSS feed parser & live stream detector for single-server Discord broadcasts.
          </p>
        </div>

        <button
          onClick={() => setIsAddModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-[#5865F2]/20"
        >
          <Plus className="w-4 h-4" />
          <span>Add YouTube Channel</span>
        </button>
      </div>

      {/* Navigation tabs */}
      <div className="flex items-center gap-2 border-b border-gray-800 pb-2">
        <button
          onClick={() => handleTabChange('channels')}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-colors ${
            currentTab === 'channels'
              ? 'bg-[#5865F2] text-white shadow'
              : 'text-gray-400 hover:text-white hover:bg-gray-800'
          }`}
        >
          <ListTree className="w-4 h-4" />
          <span>Channels ({channels.length})</span>
        </button>

        <button
          onClick={() => handleTabChange('notifications')}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-colors ${
            currentTab === 'notifications'
              ? 'bg-[#5865F2] text-white shadow'
              : 'text-gray-400 hover:text-white hover:bg-gray-800'
          }`}
        >
          <Bell className="w-4 h-4" />
          <span>Notification Templates</span>
        </button>

        <button
          onClick={() => handleTabChange('settings')}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-colors ${
            currentTab === 'settings'
              ? 'bg-[#5865F2] text-white shadow'
              : 'text-gray-400 hover:text-white hover:bg-gray-800'
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>Settings</span>
        </button>
      </div>

      {/* Tab: Channels */}
      {currentTab === 'channels' && (
        <div className="space-y-6">
          {loading ? (
            <LoadingSkeleton rows={4} />
          ) : channels.length === 0 ? (
            <EmptyState
              title="No YouTube Channels Monitored"
              description="Add YouTube creators, live streamers, or your own channel to receive automatic announcements in your Discord server."
              icon={Youtube}
              actionText="+ Add First Channel"
              onAction={() => setIsAddModalOpen(true)}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {channels.map((ch) => (
                <YouTubeChannelCard
                  key={ch.id}
                  channel={ch}
                  discordChannels={discordChannels}
                  onToggle={handleToggleChannel}
                  onTest={handleTestChannel}
                  onDelete={(id, name) => setDeleteTarget({ id, name })}
                />
              ))}
            </div>
          )}

          {/* Test feed drawer / card */}
          {testResult && (
            <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-3">
              <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                <span className="text-xs font-bold text-white uppercase tracking-wider">
                  Feed Test Result
                </span>
                <button
                  onClick={() => setTestResult(null)}
                  className="text-xs text-gray-400 hover:text-white"
                >
                  Close
                </button>
              </div>

              {testResult.success ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs text-emerald-400">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Feed parsed successfully. Showing latest video entries:</span>
                  </div>
                  <div className="divide-y divide-gray-800 bg-[#0B0E14] rounded-xl p-3 border border-gray-800 text-xs">
                    {testResult.entries.map((e, idx) => (
                      <div key={idx} className="py-2 flex items-center justify-between">
                        <span className="font-medium text-white truncate pr-4">{e.title}</span>
                        <a
                          href={e.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[#5865F2] hover:underline flex items-center gap-1 shrink-0"
                        >
                          <span>Watch</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-xs text-rose-400">Error: {testResult.error}</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab: Notification Template Editor & Live Preview */}
      {currentTab === 'notifications' && (
        <div className="space-y-6">
          {/* Event-specific template navigation pills */}
          <div className="bg-[#151921] border border-gray-800 p-2 rounded-2xl flex flex-wrap items-center gap-2">
            {(Object.keys(EVENT_METADATA) as YouTubeEventType[]).map((evtKey) => {
              const meta = EVENT_METADATA[evtKey];
              const IconComp = meta.icon;
              const isActive = activeEvent === evtKey;
              return (
                <button
                  key={evtKey}
                  type="button"
                  onClick={() => setActiveEvent(evtKey)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                    isActive
                      ? 'bg-[#5865F2] text-white shadow-md shadow-[#5865F2]/25'
                      : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
                  }`}
                >
                  <IconComp className="w-4 h-4" />
                  <span>{meta.label}</span>
                </button>
              );
            })}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
            {/* Form */}
            <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                <div>
                  <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                    <span>{EVENT_METADATA[activeEvent].label} Template</span>
                  </h2>
                  <p className="text-[11px] text-gray-400 mt-0.5">
                    {EVENT_METADATA[activeEvent].descriptionHelp}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsResetModalOpen(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-gray-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reset to Default</span>
                </button>
              </div>

              {/* Title Input */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-gray-300 block">
                    Notification Title Template <span className="text-red-400">*</span>
                  </label>
                  <span className="text-[10px] text-gray-500 font-mono">
                    {currentTemplate.title_template?.length || 0}/256
                  </span>
                </div>
                <input
                  ref={titleInputRef}
                  type="text"
                  maxLength={256}
                  value={currentTemplate.title_template}
                  onFocus={() => setLastFocusedField('title')}
                  onChange={(e) => updateActiveField('title_template', e.target.value)}
                  placeholder="🎬 NEW VIDEO — {channel_name}"
                  className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                />
              </div>

              {/* Description Input */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-gray-300 block">
                    Embed Description <span className="text-red-400">*</span>
                  </label>
                  <span className="text-[10px] text-gray-500 font-mono">
                    {currentTemplate.description_template?.length || 0}/2000
                  </span>
                </div>
                <textarea
                  ref={descTextareaRef}
                  rows={4}
                  maxLength={2000}
                  value={currentTemplate.description_template}
                  onFocus={() => setLastFocusedField('description')}
                  onChange={(e) => updateActiveField('description_template', e.target.value)}
                  placeholder="**{video_title}**&#10;&#10;A new video is now available on YouTube."
                  className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-[#5865F2] font-mono leading-relaxed"
                />
              </div>

              {/* Variable helper */}
              <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">
                    Available Variables
                  </span>
                  <span className="text-[10px] text-gray-500">
                    Click to insert into {lastFocusedField}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {EVENT_METADATA[activeEvent].variables.map((variable) => (
                    <button
                      key={variable}
                      type="button"
                      onClick={() => handleInsertVariable(variable)}
                      className="px-2 py-1 bg-gray-800 hover:bg-[#5865F2]/20 hover:text-[#5865F2] hover:border-[#5865F2]/40 border border-gray-700 rounded-lg text-[11px] font-mono text-gray-300 transition-colors"
                      title={`Insert ${variable}`}
                    >
                      {variable}
                    </button>
                  ))}
                </div>
              </div>

              {/* Mention Role & Footer */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-300 block">Mention Role</label>
                  <input
                    type="text"
                    value={currentTemplate.mention_role || ''}
                    onChange={(e) => updateActiveField('mention_role', e.target.value)}
                    placeholder="e.g. YouTube Notifications"
                    className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-gray-300 block">Footer Text</label>
                    <span className="text-[10px] text-gray-500 font-mono">
                      {currentTemplate.footer_text?.length || 0}/256
                    </span>
                  </div>
                  <input
                    ref={footerInputRef}
                    type="text"
                    maxLength={256}
                    value={currentTemplate.footer_text || ''}
                    onFocus={() => setLastFocusedField('footer')}
                    onChange={(e) => updateActiveField('footer_text', e.target.value)}
                    placeholder="PB HERO Personal Bot"
                    className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                  />
                </div>
              </div>

              {/* Visual Elements checkboxes */}
              <div className="space-y-2 pt-2 border-t border-gray-800">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
                  Visual Elements
                </span>
                <div className="grid grid-cols-3 gap-2">
                  <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={currentTemplate.show_thumbnail}
                      onChange={(e) => updateActiveField('show_thumbnail', e.target.checked)}
                      className="rounded border-gray-700 text-[#5865F2]"
                    />
                    <span>Show Thumbnail</span>
                  </label>

                  <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={currentTemplate.show_timestamp}
                      onChange={(e) => updateActiveField('show_timestamp', e.target.checked)}
                      className="rounded border-gray-700 text-[#5865F2]"
                    />
                    <span>Show Timestamp</span>
                  </label>

                  <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={currentTemplate.enable_button}
                      onChange={(e) => updateActiveField('enable_button', e.target.checked)}
                      className="rounded border-gray-700 text-[#5865F2]"
                    />
                    <span>Watch Button</span>
                  </label>
                </div>
              </div>

              {/* Save Button */}
              <div className="pt-2">
                <button
                  type="button"
                  disabled={savingTemplate}
                  onClick={handleSaveTemplate}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl shadow transition-colors disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                  <span>{savingTemplate ? 'Saving Template...' : 'Save Template'}</span>
                </button>
              </div>
            </div>

            {/* Live Preview Panel */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                  Discord Embed Live Preview ({EVENT_METADATA[activeEvent].label})
                </span>
                <span className="text-[10px] text-gray-500 font-mono">Real-time dynamic rendering</span>
              </div>
              <NotificationPreview
                title={renderPreviewText(currentTemplate.title_template, activeEvent)}
                description={renderPreviewText(currentTemplate.description_template, activeEvent)}
                footer={renderPreviewText(currentTemplate.footer_text || '', activeEvent)}
                mentionRoleName={currentTemplate.mention_role || undefined}
                showThumbnail={currentTemplate.show_thumbnail}
                showTimestamp={currentTemplate.show_timestamp}
                enableButton={currentTemplate.enable_button}
                videoTitle={EVENT_METADATA[activeEvent].sampleTitle}
                channelName="PB HERO GAMER"
                buttonLabel={EVENT_METADATA[activeEvent].button}
                badgeText={EVENT_METADATA[activeEvent].badge}
                borderColor={EVENT_METADATA[activeEvent].borderColor}
              />
            </div>
          </div>
        </div>
      )}

      {/* Tab: Settings */}
      {currentTab === 'settings' && (
        <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl max-w-xl space-y-6">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-800 pb-3">
            YouTube Monitoring Polling Intervals
          </h2>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300 block">
                RSS Feed Poll Interval (Seconds)
              </label>
              <input
                type="number"
                min="30"
                max="3600"
                value={pollInterval}
                onChange={(e) => setPollInterval(e.target.value)}
                className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
              />
              <span className="text-[11px] text-gray-500">
                Frequency to check YouTube XML feeds for uploaded videos and premieres (Default: 60s).
              </span>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300 block">
                Live Status Check Interval (Seconds)
              </label>
              <input
                type="number"
                min="15"
                max="1800"
                value={liveInterval}
                onChange={(e) => setLiveInterval(e.target.value)}
                className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
              />
              <span className="text-[11px] text-gray-500">
                Frequency to verify stream status for scheduled/ongoing livestreams (Default: 30s).
              </span>
            </div>

            <button
              onClick={() => {
                setSavingSettings(true);
                setTimeout(() => {
                  setSavingSettings(false);
                  toast.success('YouTube polling parameters saved.');
                }, 500);
              }}
              disabled={savingSettings}
              className="px-5 py-2 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl shadow transition-colors"
            >
              {savingSettings ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </div>
      )}

      {/* Add Modal */}
      <YouTubeChannelModal
        isOpen={isAddModalOpen}
        channels={discordChannels}
        roles={roles}
        onClose={() => setIsAddModalOpen(false)}
        onSubmit={handleAddChannel}
      />

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={!!deleteTarget}
        title="Delete YouTube Channel"
        message={`Are you sure you want to stop monitoring and delete "${deleteTarget?.name}"? Scheduled notifications and event histories will be removed.`}
        confirmText="Delete Channel"
        isDangerous
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* Reset Template Confirmation Modal */}
      <ConfirmModal
        isOpen={isResetModalOpen}
        title={`Reset ${EVENT_METADATA[activeEvent].label} Template`}
        message={`Reset ${EVENT_METADATA[activeEvent].label} template to default? This will only reset settings for this event.`}
        confirmText="Reset to Default"
        isDangerous
        onConfirm={handleResetTemplateConfirm}
        onCancel={() => setIsResetModalOpen(false)}
      />
    </div>
  );
}
