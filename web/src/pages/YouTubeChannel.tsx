import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { youtubeApi } from '../api/youtube';
import { channelsApi } from '../api/channels';
import { YouTubeChannel, DiscordChannel, DiscordRole, YouTubeDestination } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { ConfirmModal } from '../components/ConfirmModal';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { formatRelativeTime } from '../utils/formatters';
import { toast } from '../hooks/useToast';
import {
  Youtube,
  ArrowLeft,
  Play,
  Radio,
  Save,
  Power,
  Trash2,
  ExternalLink,
  AlertCircle,
  CheckSquare,
  Square,
} from 'lucide-react';

export default function YouTubeChannelDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [channel, setChannel] = useState<YouTubeChannel | null>(null);
  const [discordChannels, setDiscordChannels] = useState<DiscordChannel[]>([]);
  const [roles, setRoles] = useState<DiscordRole[]>([]);

  // Editable fields
  const [channelName, setChannelName] = useState('');
  const [destinationChannelId, setDestinationChannelId] = useState('');
  const [notificationRoleId, setNotificationRoleId] = useState('');
  const [uploadEnabled, setUploadEnabled] = useState(true);
  const [scheduledLiveEnabled, setScheduledLiveEnabled] = useState(true);
  const [liveStartedEnabled, setLiveStartedEnabled] = useState(true);
  const [premiereEnabled, setPremiereEnabled] = useState(true);

  const [saving, setSaving] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  useEffect(() => {
    if (!id) return;

    async function loadChannel() {
      setLoading(true);
      try {
        const [ch, chList, rList] = await Promise.all([
          youtubeApi.getChannel(id!),
          channelsApi.getChannels(),
          channelsApi.getRoles(),
        ]);
        setChannel(ch);
        setDiscordChannels(chList);
        setRoles(rList);

        setChannelName(ch.channel_name);
        const dest = ch.destinations?.[0];
        if (dest) {
          setDestinationChannelId(dest.discord_channel_id);
          setNotificationRoleId(dest.notification_role_id || '');
          setUploadEnabled(dest.upload_enabled);
          setScheduledLiveEnabled(dest.scheduled_live_enabled);
          setLiveStartedEnabled(dest.live_started_enabled);
          setPremiereEnabled(dest.premiere_enabled);
        } else if (chList.length > 0) {
          setDestinationChannelId(chList[0].id);
        }
      } catch (err: any) {
        toast.error(err.message || 'Channel not found');
        navigate('/youtube');
      } finally {
        setLoading(false);
      }
    }

    loadChannel();
  }, [id, navigate]);

  const handleSave = async () => {
    if (!id) return;
    setSaving(true);
    try {
      const destination: YouTubeDestination = {
        discord_channel_id: destinationChannelId,
        notification_role_id: notificationRoleId || null,
        upload_enabled: uploadEnabled,
        scheduled_live_enabled: scheduledLiveEnabled,
        live_started_enabled: liveStartedEnabled,
        premiere_enabled: premiereEnabled,
      };

      await youtubeApi.updateChannel(id, {
        channel_name: channelName,
        destinations: [destination],
      });

      toast.success('YouTube channel configuration saved.');
      // Refresh channel state
      const updated = await youtubeApi.getChannel(id);
      setChannel(updated);
    } catch (err: any) {
      toast.error(err.message || 'Failed to update channel');
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async () => {
    if (!channel || !id) return;
    try {
      const nextState = !channel.enabled;
      await youtubeApi.toggleChannel(id, nextState);
      setChannel({ ...channel, enabled: nextState });
      toast.success(nextState ? 'Channel enabled' : 'Channel disabled');
    } catch (err: any) {
      toast.error(err.message || 'Failed to toggle channel');
    }
  };

  const handleTestFeed = async () => {
    if (!id) return;
    try {
      toast.info('Testing XML feed...');
      const res = await youtubeApi.testChannel(id);
      if (res.success) {
        toast.success(`Feed active! Found ${res.entry_count} latest videos.`);
      } else {
        toast.error(res.error || 'Feed check failed');
      }
    } catch (err: any) {
      toast.error(err.message || 'Feed check error');
    }
  };

  const handleTestLive = async () => {
    if (!id) return;
    try {
      toast.info('Checking YouTube live detector...');
      const res = await youtubeApi.testLive(id);
      if (res.is_live) {
        toast.success(`Stream is LIVE: "${res.title || 'Live Stream'}"`);
      } else {
        toast.info('Channel is currently offline (no active stream detected).');
      }
    } catch (err: any) {
      toast.error(err.message || 'Live check failed');
    }
  };

  const handleDelete = async () => {
    if (!id) return;
    try {
      await youtubeApi.deleteChannel(id);
      toast.success('Channel deleted.');
      navigate('/youtube');
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete channel');
    }
  };

  if (loading || !channel) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-gray-800 animate-pulse rounded" />
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  const isHealthy = !channel.last_error;

  return (
    <div className="space-y-8 animate-fade-in max-w-5xl">
      {/* Back navigation & Header */}
      <div className="flex items-center gap-3">
        <Link
          to="/youtube"
          className="p-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2">
            <span>{channel.channel_name}</span>
            <StatusBadge
              status={channel.enabled ? 'enabled' : 'disabled'}
              label={channel.enabled ? 'MONITORING' : 'PAUSED'}
            />
            <StatusBadge
              status={isHealthy ? 'healthy' : 'degraded'}
              label={isHealthy ? 'HEALTHY' : 'ERROR'}
            />
          </h1>
          <span className="text-xs text-gray-400 font-mono">
            ID: {channel.youtube_channel_id} {channel.handle ? `• @${channel.handle.replace('@', '')}` : ''}
          </span>
        </div>
      </div>

      {/* Action Buttons Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[#151921] border border-gray-800 p-4 rounded-2xl shadow-lg">
        <div className="flex items-center gap-2">
          <button
            onClick={handleTestFeed}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-xl text-xs font-semibold transition-colors"
          >
            <Play className="w-3.5 h-3.5 text-emerald-400" />
            <span>Test Feed</span>
          </button>

          <button
            onClick={handleTestLive}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-xl text-xs font-semibold transition-colors"
          >
            <Radio className="w-3.5 h-3.5 text-red-500" />
            <span>Test Live Status</span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleToggle}
            className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors ${
              channel.enabled
                ? 'bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 border border-amber-500/20'
                : 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/20'
            }`}
          >
            <Power className="w-3.5 h-3.5" />
            <span>{channel.enabled ? 'Pause Channel' : 'Enable Channel'}</span>
          </button>

          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-5 py-2 bg-[#5865F2] hover:bg-[#4752c4] text-white rounded-xl text-xs font-bold transition-all shadow disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{saving ? 'Saving...' : 'Save Configuration'}</span>
          </button>

          <button
            onClick={() => setIsDeleteModalOpen(true)}
            className="p-2 text-rose-400 hover:bg-rose-500/10 rounded-xl transition-colors border border-rose-500/20"
            title="Delete channel"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left Card: Channel Information & Destinations */}
        <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-800 pb-3 flex items-center gap-2">
            <Youtube className="w-4 h-4 text-red-500" />
            <span>Channel & Discord Destination</span>
          </h2>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 block">Channel Display Name</label>
            <input
              type="text"
              value={channelName}
              onChange={(e) => setChannelName(e.target.value)}
              className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 block">Destination Channel</label>
            <select
              value={destinationChannelId}
              onChange={(e) => setDestinationChannelId(e.target.value)}
              className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
            >
              {discordChannels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  #{ch.name} {ch.category ? `(${ch.category})` : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 block">Notification Role Mention</label>
            <select
              value={notificationRoleId}
              onChange={(e) => setNotificationRoleId(e.target.value)}
              className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
            >
              <option value="">None (No mention)</option>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  @{r.name}
                </option>
              ))}
            </select>
          </div>

          <div className="pt-2">
            <span className="text-xs font-semibold text-gray-400 block mb-1">Feed URL</span>
            <a
              href={channel.feed_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-[#5865F2] hover:underline font-mono break-all flex items-center gap-1"
            >
              <span>{channel.feed_url}</span>
              <ExternalLink className="w-3.5 h-3.5 shrink-0" />
            </a>
          </div>
        </div>

        {/* Right Card: Notification Types & Health Telemetry */}
        <div className="space-y-6">
          {/* Notification toggles */}
          <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-800 pb-3">
              Notification Events
            </h2>

            <div className="space-y-2">
              <button
                type="button"
                onClick={() => setUploadEnabled(!uploadEnabled)}
                className="flex items-center justify-between w-full p-2.5 rounded-xl bg-[#0B0E14] border border-gray-800 hover:bg-gray-800/40 text-xs transition-colors"
              >
                <span className="text-gray-300 font-medium">New Video Uploads</span>
                {uploadEnabled ? (
                  <CheckSquare className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Square className="w-4 h-4 text-gray-500" />
                )}
              </button>

              <button
                type="button"
                onClick={() => setScheduledLiveEnabled(!scheduledLiveEnabled)}
                className="flex items-center justify-between w-full p-2.5 rounded-xl bg-[#0B0E14] border border-gray-800 hover:bg-gray-800/40 text-xs transition-colors"
              >
                <span className="text-gray-300 font-medium">Scheduled Livestreams</span>
                {scheduledLiveEnabled ? (
                  <CheckSquare className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Square className="w-4 h-4 text-gray-500" />
                )}
              </button>

              <button
                type="button"
                onClick={() => setLiveStartedEnabled(!liveStartedEnabled)}
                className="flex items-center justify-between w-full p-2.5 rounded-xl bg-[#0B0E14] border border-gray-800 hover:bg-gray-800/40 text-xs transition-colors"
              >
                <span className="text-gray-300 font-medium">Live Stream Started</span>
                {liveStartedEnabled ? (
                  <CheckSquare className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Square className="w-4 h-4 text-gray-500" />
                )}
              </button>

              <button
                type="button"
                onClick={() => setPremiereEnabled(!premiereEnabled)}
                className="flex items-center justify-between w-full p-2.5 rounded-xl bg-[#0B0E14] border border-gray-800 hover:bg-gray-800/40 text-xs transition-colors"
              >
                <span className="text-gray-300 font-medium">Video Premieres</span>
                {premiereEnabled ? (
                  <CheckSquare className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Square className="w-4 h-4 text-gray-500" />
                )}
              </button>
            </div>
          </div>

          {/* Telemetry card */}
          <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-3">
            <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-800 pb-3">
              Monitoring Health & Diagnostics
            </h2>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-[#0B0E14] border border-gray-800 p-3 rounded-xl">
                <span className="text-gray-500 block mb-0.5">Last Poll Check</span>
                <span className="text-white font-medium">
                  {formatRelativeTime(channel.last_checked_at)}
                </span>
              </div>

              <div className="bg-[#0B0E14] border border-gray-800 p-3 rounded-xl">
                <span className="text-gray-500 block mb-0.5">Last Successful Feed</span>
                <span className="text-emerald-400 font-medium">
                  {formatRelativeTime(channel.last_success_at)}
                </span>
              </div>
            </div>

            {channel.last_error && (
              <div className="flex items-start gap-2 text-xs text-rose-400 bg-rose-500/10 p-3 rounded-xl border border-rose-500/20">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold block">Last Error Encountered:</span>
                  <span className="text-rose-300 font-mono text-[11px] leading-relaxed">
                    {channel.last_error}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <ConfirmModal
        isOpen={isDeleteModalOpen}
        title="Delete YouTube Channel"
        message={`Delete "${channel.channel_name}"? YouTube monitoring for this creator will cease immediately.`}
        confirmText="Delete Channel"
        isDangerous
        onConfirm={handleDelete}
        onCancel={() => setIsDeleteModalOpen(false)}
      />
    </div>
  );
}
