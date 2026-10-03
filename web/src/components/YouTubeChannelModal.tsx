import React, { useState } from 'react';
import { DiscordChannel, DiscordRole } from '../types';
import { validateYouTubeInput } from '../utils/validation';
import { X, Youtube, Loader2, CheckSquare, Square } from 'lucide-react';

interface YouTubeChannelModalProps {
  isOpen: boolean;
  channels: DiscordChannel[];
  roles?: DiscordRole[];
  onClose: () => void;
  onSubmit: (data: {
    youtube_input: string;
    discord_channel_id: string;
    notification_role_id?: string | null;
    upload_enabled: boolean;
    scheduled_live_enabled: boolean;
    live_started_enabled: boolean;
    premiere_enabled: boolean;
  }) => Promise<void>;
}

export const YouTubeChannelModal: React.FC<YouTubeChannelModalProps> = ({
  isOpen,
  channels,
  roles = [],
  onClose,
  onSubmit,
}) => {
  const [youtubeInput, setYoutubeInput] = useState('');
  const [destinationChannelId, setDestinationChannelId] = useState(channels[0]?.id || '');
  const [notificationRoleId, setNotificationRoleId] = useState<string>('');
  const [uploadEnabled, setUploadEnabled] = useState(true);
  const [scheduledLiveEnabled, setScheduledLiveEnabled] = useState(true);
  const [liveStartedEnabled, setLiveStartedEnabled] = useState(true);
  const [premiereEnabled, setPremiereEnabled] = useState(true);

  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setApiError(null);

    const validation = validateYouTubeInput(youtubeInput);
    if (!validation.valid) {
      setValidationError(validation.error || 'Invalid YouTube identifier.');
      return;
    }

    if (!destinationChannelId) {
      setValidationError('Please select a destination Discord channel.');
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit({
        youtube_input: youtubeInput.trim(),
        discord_channel_id: destinationChannelId,
        notification_role_id: notificationRoleId ? notificationRoleId : null,
        upload_enabled: uploadEnabled,
        scheduled_live_enabled: scheduledLiveEnabled,
        live_started_enabled: liveStartedEnabled,
        premiere_enabled: premiereEnabled,
      });
      // Reset form
      setYoutubeInput('');
      setNotificationRoleId('');
      onClose();
    } catch (err: any) {
      setApiError(err.message || 'Failed to add YouTube channel.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#151921] border border-gray-800 rounded-2xl max-w-lg w-full shadow-2xl overflow-hidden animate-scale-in">
        <div className="flex items-center justify-between p-5 border-b border-gray-800 bg-[#12161f]">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-red-500/10 text-red-500">
              <Youtube className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Add YouTube Channel</h3>
              <p className="text-xs text-gray-400">Direct RSS & Live Stream monitoring</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-gray-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {apiError && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300">
              {apiError}
            </div>
          )}

          {/* YouTube identifier */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 block">
              YouTube Channel URL / Handle
            </label>
            <input
              type="text"
              value={youtubeInput}
              onChange={(e) => {
                setYoutubeInput(e.target.value);
                setValidationError(null);
              }}
              placeholder="@handle or https://youtube.com/@handle or UCxxxx"
              disabled={submitting}
              className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2] transition-colors"
            />
            {validationError && (
              <p className="text-xs text-rose-400 mt-1">{validationError}</p>
            )}
            <p className="text-[11px] text-gray-500">
              Examples: <code className="text-gray-400">@MrBeast</code>,{' '}
              <code className="text-gray-400">https://youtube.com/@mkbhd</code>,{' '}
              <code className="text-gray-400">UCBJycsmduvYEL83R_U4JriQ</code>
            </p>
          </div>

          {/* Destination Discord Channel */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 block">
              Destination Discord Channel
            </label>
            <select
              value={destinationChannelId}
              onChange={(e) => setDestinationChannelId(e.target.value)}
              disabled={submitting}
              className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#5865F2] transition-colors"
            >
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  #{ch.name} {ch.category ? `(${ch.category})` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Notification Role */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 block">
              Notification Role (Optional)
            </label>
            <select
              value={notificationRoleId}
              onChange={(e) => setNotificationRoleId(e.target.value)}
              disabled={submitting}
              className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#5865F2] transition-colors"
            >
              <option value="">None (No mention)</option>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  @{r.name}
                </option>
              ))}
            </select>
          </div>

          {/* Notification Types */}
          <div className="space-y-2 pt-2">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
              Notification Types
            </span>
            <div className="grid grid-cols-2 gap-2 bg-[#0B0E14] p-3 rounded-xl border border-gray-800">
              <button
                type="button"
                onClick={() => setUploadEnabled(!uploadEnabled)}
                className="flex items-center gap-2 p-1.5 rounded hover:bg-gray-800 text-left transition-colors"
              >
                {uploadEnabled ? (
                  <CheckSquare className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Square className="w-4 h-4 text-gray-500" />
                )}
                <span className="text-xs text-gray-300">New Video</span>
              </button>

              <button
                type="button"
                onClick={() => setScheduledLiveEnabled(!scheduledLiveEnabled)}
                className="flex items-center gap-2 p-1.5 rounded hover:bg-gray-800 text-left transition-colors"
              >
                {scheduledLiveEnabled ? (
                  <CheckSquare className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Square className="w-4 h-4 text-gray-500" />
                )}
                <span className="text-xs text-gray-300">Scheduled Live</span>
              </button>

              <button
                type="button"
                onClick={() => setLiveStartedEnabled(!liveStartedEnabled)}
                className="flex items-center gap-2 p-1.5 rounded hover:bg-gray-800 text-left transition-colors"
              >
                {liveStartedEnabled ? (
                  <CheckSquare className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Square className="w-4 h-4 text-gray-500" />
                )}
                <span className="text-xs text-gray-300">Live Started</span>
              </button>

              <button
                type="button"
                onClick={() => setPremiereEnabled(!premiereEnabled)}
                className="flex items-center gap-2 p-1.5 rounded hover:bg-gray-800 text-left transition-colors"
              >
                {premiereEnabled ? (
                  <CheckSquare className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Square className="w-4 h-4 text-gray-500" />
                )}
                <span className="text-xs text-gray-300">Premiere</span>
              </button>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-xs font-medium text-white bg-[#5865F2] hover:bg-[#4752c4] rounded-lg transition-all shadow disabled:opacity-50"
            >
              {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>{submitting ? 'Resolving...' : 'Save Channel'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
