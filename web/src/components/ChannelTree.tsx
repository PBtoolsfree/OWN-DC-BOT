import React, { useState } from 'react';
import { DiscordChannel, ChannelPolicy } from '../types';
import { Hash, Volume2, Shield, Search, ChevronDown, ChevronRight, Radio } from 'lucide-react';

interface ChannelTreeProps {
  channels: DiscordChannel[];
  policies: ChannelPolicy[];
  selectedChannelId: string | null;
  onSelectChannel: (channelId: string) => void;
}

export const ChannelTree: React.FC<ChannelTreeProps> = ({
  channels,
  policies,
  selectedChannelId,
  onSelectChannel,
}) => {
  const [search, setSearch] = useState('');
  const [collapsedCategories, setCollapsedCategories] = useState<Record<string, boolean>>({});

  // Filter channels
  const filteredChannels = channels.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.category?.toLowerCase().includes(search.toLowerCase())
  );

  // Group by category
  const categories: Record<string, DiscordChannel[]> = {};
  filteredChannels.forEach((ch) => {
    const cat = ch.category || 'Uncategorized';
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(ch);
  });

  const toggleCategory = (cat: string) => {
    setCollapsedCategories((prev) => ({ ...prev, [cat]: !prev[cat] }));
  };

  const getChannelIcon = (type: string) => {
    switch (type) {
      case 'voice':
        return <Volume2 className="w-4 h-4 text-emerald-400 shrink-0" />;
      case 'stage':
        return <Radio className="w-4 h-4 text-indigo-400 shrink-0" />;
      case 'text':
      default:
        return <Hash className="w-4 h-4 text-gray-400 shrink-0" />;
    }
  };

  const hasCustomPolicy = (channelId: string) => {
    return policies.some((p) => p.discord_channel_id === channelId && p.enabled);
  };

  return (
    <div className="bg-[#151921] border border-gray-800 rounded-2xl flex flex-col h-full shadow-lg overflow-hidden">
      <div className="p-4 border-b border-gray-800 space-y-3 bg-[#12161f]">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">Discord Channels</h3>
          <span className="text-[11px] bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full font-mono">
            {channels.length}
          </span>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="w-4 h-4 text-gray-500 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search channels..."
            className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2] transition-colors"
          />
        </div>
      </div>

      {/* Tree list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {Object.keys(categories).length === 0 ? (
          <div className="text-center py-8 text-xs text-gray-500">No channels found</div>
        ) : (
          Object.entries(categories).map(([category, catChannels]) => {
            const isCollapsed = !!collapsedCategories[category];

            return (
              <div key={category} className="space-y-1">
                <button
                  type="button"
                  onClick={() => toggleCategory(category)}
                  className="flex items-center gap-1.5 w-full text-left px-2 py-1 text-[11px] font-bold text-gray-400 hover:text-gray-200 uppercase tracking-wider transition-colors"
                >
                  {isCollapsed ? (
                    <ChevronRight className="w-3.5 h-3.5 text-gray-500" />
                  ) : (
                    <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
                  )}
                  <span className="truncate">{category}</span>
                  <span className="text-[10px] text-gray-600 font-mono ml-auto">
                    {catChannels.length}
                  </span>
                </button>

                {!isCollapsed && (
                  <div className="space-y-0.5 pl-2">
                    {catChannels.map((channel) => {
                      const isSelected = selectedChannelId === channel.id;
                      const custom = hasCustomPolicy(channel.id);

                      return (
                        <button
                          key={channel.id}
                          type="button"
                          onClick={() => onSelectChannel(channel.id)}
                          className={`flex items-center justify-between w-full px-2.5 py-1.5 rounded-lg text-xs transition-all ${
                            isSelected
                              ? 'bg-[#5865F2] text-white font-medium shadow'
                              : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                          }`}
                        >
                          <div className="flex items-center gap-2 truncate">
                            {getChannelIcon(channel.type)}
                            <span className="truncate">{channel.name}</span>
                          </div>

                          {custom && (
                            <span
                              title="Active Policy Configured"
                              className={`p-1 rounded-full ${
                                isSelected ? 'bg-white/20 text-white' : 'bg-emerald-500/10 text-emerald-400'
                              }`}
                            >
                              <Shield className="w-3 h-3" />
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
