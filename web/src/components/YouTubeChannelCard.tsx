import React from 'react';
import { YouTubeChannel, DiscordChannel } from '../types';
import { StatusBadge } from './StatusBadge';
import { formatRelativeTime } from '../utils/formatters';
import { Youtube, Play, Trash2, Power, Eye, AlertCircle, Hash } from 'lucide-react';
import { Link } from 'react-router-dom';

interface YouTubeChannelCardProps {
  channel: YouTubeChannel;
  discordChannels: DiscordChannel[];
  onToggle: (id: string, enabled: boolean) => void;
  onTest: (id: string) => void;
  onDelete: (id: string, name: string) => void;
}

export const YouTubeChannelCard: React.FC<YouTubeChannelCardProps> = ({
  channel,
  discordChannels,
  onToggle,
  onTest,
  onDelete,
}) => {
  const getDestinationNames = () => {
    if (!channel.destinations || channel.destinations.length === 0) {
      return 'No destination';
    }
    return channel.destinations
      .map((d) => {
        const found = discordChannels.find((c) => c.id === d.discord_channel_id);
        return found ? `#${found.name}` : `#${d.discord_channel_id}`;
      })
      .join(', ');
  };

  const isHealthy = !channel.last_error;

  return (
    <div className="bg-[#151921] border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-all flex flex-col justify-between shadow-lg">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-red-600/10 border border-red-500/20 flex items-center justify-center text-red-500 shrink-0">
              <Youtube className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Link
                  to={`/youtube/${channel.youtube_channel_id}`}
                  className="font-bold text-white text-base hover:text-[#5865F2] transition-colors truncate block"
                >
                  {channel.channel_name}
                </Link>
                {channel.handle && (
                  <span className="text-xs text-gray-400 font-mono">@{channel.handle.replace('@', '')}</span>
                )}
              </div>
              <span className="text-[11px] text-gray-500 font-mono block truncate">
                {channel.youtube_channel_id}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <StatusBadge
              status={channel.enabled ? 'enabled' : 'disabled'}
              label={channel.enabled ? 'ACTIVE' : 'PAUSED'}
            />
            <StatusBadge
              status={isHealthy ? 'healthy' : 'degraded'}
              label={isHealthy ? 'HEALTHY' : 'ERROR'}
            />
          </div>
        </div>

        {/* Destination & Info */}
        <div className="grid grid-cols-2 gap-3 bg-[#0B0E14] p-3 rounded-lg border border-gray-800 text-xs">
          <div>
            <span className="text-gray-500 block mb-0.5">Destination</span>
            <div className="flex items-center gap-1 text-gray-300 font-medium truncate">
              <Hash className="w-3.5 h-3.5 text-[#5865F2] shrink-0" />
              <span className="truncate">{getDestinationNames()}</span>
            </div>
          </div>
          <div>
            <span className="text-gray-500 block mb-0.5">Last Check</span>
            <span className="text-gray-300 font-medium">
              {formatRelativeTime(channel.last_checked_at)}
            </span>
          </div>
        </div>

        {channel.last_error && (
          <div className="flex items-center gap-2 text-xs text-rose-400 bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/20">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span className="truncate">{channel.last_error}</span>
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex items-center justify-between pt-4 mt-4 border-t border-gray-800 text-xs">
        <Link
          to={`/youtube/${channel.youtube_channel_id}`}
          className="inline-flex items-center gap-1.5 text-gray-300 hover:text-white px-2.5 py-1.5 rounded-lg hover:bg-gray-800 transition-colors"
        >
          <Eye className="w-3.5 h-3.5" />
          <span>Details</span>
        </Link>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => onTest(channel.youtube_channel_id)}
            title="Test feed check"
            className="p-1.5 text-gray-400 hover:text-[#5865F2] hover:bg-[#5865F2]/10 rounded-lg transition-colors"
          >
            <Play className="w-4 h-4" />
          </button>

          <button
            onClick={() => onToggle(channel.youtube_channel_id, !channel.enabled)}
            title={channel.enabled ? 'Pause monitoring' : 'Enable monitoring'}
            className={`p-1.5 rounded-lg transition-colors ${
              channel.enabled
                ? 'text-emerald-400 hover:bg-emerald-500/10'
                : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800'
            }`}
          >
            <Power className="w-4 h-4" />
          </button>

          <button
            onClick={() => onDelete(channel.youtube_channel_id, channel.channel_name)}
            title="Delete channel"
            className="p-1.5 text-gray-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
