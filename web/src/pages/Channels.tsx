import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { channelsApi } from '../api/channels';
import { policiesApi } from '../api/policies';
import { systemApi } from '../api/system';
import { DiscordChannel, ChannelPolicy, SystemStatus } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { toast } from '../hooks/useToast';
import {
  Hash,
  Volume2,
  Radio,
  Users,
  Search,
  ChevronRight,
} from 'lucide-react';

export default function Channels() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [channels, setChannels] = useState<DiscordChannel[]>([]);
  const [policies, setPolicies] = useState<ChannelPolicy[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [chList, polList, sysStatus] = await Promise.all([
          channelsApi.getChannels(),
          policiesApi.getPolicies(),
          systemApi.getStatus(),
        ]);
        setChannels(chList);
        setPolicies(polList);
        setSystemStatus(sysStatus);
      } catch (err: any) {
        toast.error(err.message || 'Failed to load channels');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-gray-800 animate-pulse rounded" />
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  const guildName = systemStatus?.bot?.guild_name || 'PB HERO SERVER';
  const memberCount = systemStatus?.bot?.guild_members || 0;

  // Filter channels
  const filtered = channels.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.category?.toLowerCase().includes(search.toLowerCase())
  );

  // Group by category
  const categories: Record<string, DiscordChannel[]> = {};
  filtered.forEach((ch) => {
    const cat = ch.category || 'Uncategorized';
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(ch);
  });

  const getChannelIcon = (type: string) => {
    switch (type) {
      case 'voice':
        return <Volume2 className="w-4 h-4 text-emerald-400" />;
      case 'stage':
        return <Radio className="w-4 h-4 text-indigo-400" />;
      case 'text':
      default:
        return <Hash className="w-4 h-4 text-gray-400" />;
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
          <Hash className="w-7 h-7 text-[#5865F2]" />
          <span>Server Channels</span>
        </h1>
        <p className="text-xs text-gray-400 mt-1">
          Explore all text and voice channels within the dedicated Discord guild.
        </p>
      </div>

      {/* Connected Server Card (Single-Server Enforcement) */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-[#5865F2] flex items-center justify-center text-white font-black text-lg shadow-lg">
            PB
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 uppercase font-bold tracking-wider">
                CONNECTED SERVER
              </span>
              <StatusBadge status="online" label="ACTIVE GUILD" />
            </div>
            <h2 className="text-xl font-bold text-white tracking-wide">{guildName}</h2>
          </div>
        </div>

        <div className="flex items-center gap-6 text-xs text-gray-300">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-indigo-400" />
            <span>
              <strong>{memberCount}</strong> Members
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Hash className="w-4 h-4 text-emerald-400" />
            <span>
              <strong>{channels.length}</strong> Total Channels
            </span>
          </div>
        </div>
      </div>

      {/* Search Input */}
      <div className="max-w-md">
        <div className="relative">
          <Search className="w-4 h-4 text-gray-500 absolute left-3.5 top-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search channels by name or category..."
            className="w-full bg-[#151921] border border-gray-800 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2]"
          />
        </div>
      </div>

      {/* Channels Grouped by Category */}
      <div className="space-y-6">
        {Object.entries(categories).map(([catName, catChannels]) => (
          <div
            key={catName}
            className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-lg space-y-4"
          >
            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
              <h3 className="text-xs font-bold text-gray-300 uppercase tracking-wider flex items-center gap-2">
                <span>{catName}</span>
                <span className="text-gray-600 font-mono text-[11px]">({catChannels.length})</span>
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {catChannels.map((channel) => {
                const policy = policies.find((p) => p.discord_channel_id === channel.id);
                const isConfigured = !!policy && policy.enabled;

                return (
                  <div
                    key={channel.id}
                    onClick={() => navigate(`/moderator/policies/${channel.id}`)}
                    className="p-3.5 rounded-xl bg-[#0B0E14] border border-gray-800/80 hover:border-[#5865F2]/50 hover:bg-gray-800/30 transition-all cursor-pointer group flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="p-2 rounded-lg bg-gray-800/80 group-hover:bg-[#5865F2]/10 transition-colors">
                        {getChannelIcon(channel.type)}
                      </div>
                      <div className="min-w-0">
                        <span className="text-xs font-semibold text-white group-hover:text-[#5865F2] transition-colors block truncate">
                          {channel.name}
                        </span>
                        <span className="text-[10px] text-gray-500 font-mono block">
                          {channel.type.toUpperCase()}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <StatusBadge
                        status={isConfigured ? 'enabled' : 'inherit'}
                        label={isConfigured ? 'POLICY SET' : 'INHERITED'}
                      />
                      <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-white transition-colors" />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
