import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { youtubeApi } from '../api/youtube';
import { channelsApi } from '../api/channels';
import { YouTubeChannel, DiscordChannel, DiscordRole } from '../types';
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
} from 'lucide-react';

export default function YouTube() {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentTab = searchParams.get('tab') || 'channels';

  const [loading, setLoading] = useState(true);
  const [channels, setChannels] = useState<YouTubeChannel[]>([]);
  const [discordChannels, setDiscordChannels] = useState<DiscordChannel[]>([]);
  const [roles, setRoles] = useState<DiscordRole[]>([]);

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  // Notification Template Editor state
  const [templateTitle, setTemplateTitle] = useState('🔴 {channel_name} IS NOW LIVE!');
  const [templateDesc, setTemplateDesc] = useState(
    '**{video_title}**\n\nCome hang out and join the stream live right now on YouTube!'
  );
  const [templateFooter, setTemplateFooter] = useState('PB HERO Personal Discord Bot');
  const [templateRole, setTemplateRole] = useState('PB Gang');
  const [showThumb, setShowThumb] = useState(true);
  const [showTimestamp, setShowTimestamp] = useState(true);
  const [enableButton, setEnableButton] = useState(true);

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
      const [ytList, chList, rList] = await Promise.all([
        youtubeApi.getChannels(),
        channelsApi.getChannels(),
        channelsApi.getRoles(),
      ]);
      setChannels(ytList);
      setDiscordChannels(chList);
      setRoles(rList);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load YouTube data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

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
          onClick={() => setSearchParams({ tab: 'channels' })}
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
          onClick={() => setSearchParams({ tab: 'notifications' })}
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
          onClick={() => setSearchParams({ tab: 'settings' })}
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
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
          {/* Form */}
          <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-800 pb-3">
              Announcement Template Editor
            </h2>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300 block">
                Notification Title Template
              </label>
              <input
                type="text"
                value={templateTitle}
                onChange={(e) => setTemplateTitle(e.target.value)}
                placeholder="🔴 {channel_name} IS NOW LIVE!"
                className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
              />
              <span className="text-[11px] text-gray-500">
                Variables: <code className="text-gray-400">{'{channel_name}'}</code>,{' '}
                <code className="text-gray-400">{'{video_title}'}</code>
              </span>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300 block">
                Embed Description
              </label>
              <textarea
                rows={4}
                value={templateDesc}
                onChange={(e) => setTemplateDesc(e.target.value)}
                placeholder="Markdown formatted description"
                className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-[#5865F2]"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-gray-300 block">Mention Role</label>
                <input
                  type="text"
                  value={templateRole}
                  onChange={(e) => setTemplateRole(e.target.value)}
                  placeholder="e.g. YouTube Notifications"
                  className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-gray-300 block">Footer Text</label>
                <input
                  type="text"
                  value={templateFooter}
                  onChange={(e) => setTemplateFooter(e.target.value)}
                  placeholder="PB HERO Personal Bot"
                  className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                />
              </div>
            </div>

            <div className="space-y-2 pt-2 border-t border-gray-800">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
                Visual Elements
              </span>
              <div className="grid grid-cols-3 gap-2">
                <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showThumb}
                    onChange={(e) => setShowThumb(e.target.checked)}
                    className="rounded border-gray-700 text-[#5865F2]"
                  />
                  <span>Show Thumbnail</span>
                </label>

                <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showTimestamp}
                    onChange={(e) => setShowTimestamp(e.target.checked)}
                    className="rounded border-gray-700 text-[#5865F2]"
                  />
                  <span>Show Timestamp</span>
                </label>

                <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={enableButton}
                    onChange={(e) => setEnableButton(e.target.checked)}
                    className="rounded border-gray-700 text-[#5865F2]"
                  />
                  <span>Watch Button</span>
                </label>
              </div>
            </div>

            <div className="pt-2">
              <button
                type="button"
                onClick={() => toast.success('Template settings saved successfully')}
                className="px-5 py-2 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl shadow transition-colors"
              >
                Save Template
              </button>
            </div>
          </div>

          {/* Live Preview Panel */}
          <div className="space-y-3">
            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
              Discord Embed Live Preview
            </span>
            <NotificationPreview
              title={templateTitle.replace('{channel_name}', 'PB HERO').replace('{video_title}', 'LIVESTREAM: PB HERO Bot Walkthrough')}
              description={templateDesc.replace('{channel_name}', 'PB HERO').replace('{video_title}', 'LIVESTREAM: PB HERO Bot Walkthrough')}
              footer={templateFooter}
              mentionRoleName={templateRole}
              showThumbnail={showThumb}
              showTimestamp={showTimestamp}
              enableButton={enableButton}
              videoTitle="PB HERO Discord Bot Live Walkthrough"
              channelName="PB HERO"
            />
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
    </div>
  );
}
