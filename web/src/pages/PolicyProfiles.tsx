import { useEffect, useState } from 'react';
import { policiesApi } from '../api/policies';
import { channelsApi } from '../api/channels';
import { PolicyProfile, DiscordChannel } from '../types';
import { PolicyPresetCard } from '../components/PolicyPresetCard';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { toast } from '../hooks/useToast';
import { Bookmark } from 'lucide-react';

export default function PolicyProfiles() {
  const [loading, setLoading] = useState(true);
  const [profiles, setProfiles] = useState<PolicyProfile[]>([]);
  const [channels, setChannels] = useState<DiscordChannel[]>([]);

  // Apply preset dialog state
  const [applyTarget, setApplyTarget] = useState<PolicyProfile | null>(null);
  const [selectedChannelId, setSelectedChannelId] = useState<string>('');
  const [isApplying, setIsApplying] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [profList, chList] = await Promise.all([
        policiesApi.getProfiles(),
        channelsApi.getChannels(),
      ]);
      setProfiles(profList);
      setChannels(chList);
      if (chList.length > 0) {
        setSelectedChannelId(chList[0].id);
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to load policy profiles.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleApplyClick = (profile: PolicyProfile) => {
    setApplyTarget(profile);
  };

  const handleApplyConfirm = async () => {
    if (!applyTarget || !selectedChannelId) return;

    const channel = channels.find((c) => c.id === selectedChannelId);
    setIsApplying(true);

    try {
      await policiesApi.saveChannelPolicy(selectedChannelId, {
        channel_name: channel?.name,
        category_name: channel?.category,
        channel_type: channel?.type,
        preset_name: applyTarget.name,
        allow_text: applyTarget.allow_text,
        allow_links: applyTarget.allow_links,
        allow_images: applyTarget.allow_images,
        allow_videos: applyTarget.allow_videos,
        allow_files: applyTarget.allow_files,
        allow_stickers: applyTarget.allow_stickers,
        allow_everyone: applyTarget.allow_everyone,
        allow_here: applyTarget.allow_here,
        allow_role_mentions: applyTarget.allow_role_mentions,
        allow_user_mentions: applyTarget.allow_user_mentions,
        enabled: true,
      });

      toast.success(
        `Applied preset "${applyTarget.name.replace(/_/g, ' ')}" to #${channel?.name}`
      );
      setApplyTarget(null);
    } catch (err: any) {
      toast.error(err.message || 'Failed to apply preset.');
    } finally {
      setIsApplying(false);
    }
  };

  const handleClone = (profile: PolicyProfile) => {
    toast.info(`Cloned ${profile.name} to custom draft.`);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-gray-800 animate-pulse rounded" />
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  const selectedChannel = channels.find((c) => c.id === selectedChannelId);

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
          <Bookmark className="w-7 h-7 text-[#5865F2]" />
          <span>Policy Profiles & Presets</span>
        </h1>
        <p className="text-xs text-gray-400 mt-1">
          Standardized, reusable security templates for text channels, media rooms, and announcement channels.
        </p>
      </div>

      {/* Preset Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {profiles.map((prof) => (
          <PolicyPresetCard
            key={prof.id}
            profile={prof}
            onApply={handleApplyClick}
            onClone={handleClone}
          />
        ))}
      </div>

      {/* Apply Preset Dialog with explicit confirmation */}
      {applyTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#151921] border border-gray-800 rounded-2xl max-w-md w-full shadow-2xl overflow-hidden animate-scale-in">
            <div className="p-5 border-b border-gray-800 bg-[#12161f]">
              <h3 className="text-base font-semibold text-white">
                Apply Preset: {applyTarget.name.replace(/_/g, ' ')}
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Configure channel permissions to match preset
              </p>
            </div>

            <div className="p-5 space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-gray-300 block">
                  Select Destination Channel
                </label>
                <select
                  value={selectedChannelId}
                  onChange={(e) => setSelectedChannelId(e.target.value)}
                  className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                >
                  {channels.map((ch) => (
                    <option key={ch.id} value={ch.id}>
                      #{ch.name} {ch.category ? `(${ch.category})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 leading-relaxed">
                <strong>Notice:</strong> Applying this preset will overwrite existing custom permission overrides for{' '}
                <span className="font-semibold text-white">#{selectedChannel?.name}</span>.
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 p-5 border-t border-gray-800 bg-[#12161f]">
              <button
                type="button"
                onClick={() => setApplyTarget(null)}
                disabled={isApplying}
                className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApplyConfirm}
                disabled={isApplying || !selectedChannelId}
                className="px-5 py-2 text-xs font-semibold text-white bg-[#5865F2] hover:bg-[#4752c4] rounded-lg transition-all shadow disabled:opacity-50"
              >
                {isApplying ? 'Applying...' : `Apply to #${selectedChannel?.name}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
