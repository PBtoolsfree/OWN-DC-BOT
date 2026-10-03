import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { policiesApi } from '../api/policies';
import { channelsApi } from '../api/channels';
import { DiscordChannel, ChannelPolicy, PolicyProfile, DiscordRole } from '../types';
import { ChannelTree } from '../components/ChannelTree';
import { ChannelPolicyEditor } from '../components/ChannelPolicyEditor';
import { PolicyTesterModal } from '../components/PolicyTesterModal';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { EmptyState } from '../components/EmptyState';
import { toast } from '../hooks/useToast';
import { Layers, Hash } from 'lucide-react';

export default function ChannelPolicies() {
  const { channelId } = useParams<{ channelId?: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [channels, setChannels] = useState<DiscordChannel[]>([]);
  const [roles, setRoles] = useState<DiscordRole[]>([]);
  const [policies, setPolicies] = useState<ChannelPolicy[]>([]);
  const [profiles, setProfiles] = useState<PolicyProfile[]>([]);

  const [selectedChannelId, setSelectedChannelId] = useState<string | null>(null);
  const [activePolicy, setActivePolicy] = useState<ChannelPolicy | null>(null);
  const [isSimulatorOpen, setIsSimulatorOpen] = useState(false);

  // Load all initial data
  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [chList, polList, profList, roleList] = await Promise.all([
          channelsApi.getChannels(),
          policiesApi.getPolicies(),
          policiesApi.getProfiles(),
          channelsApi.getRoles(),
        ]);

        setChannels(chList);
        setPolicies(polList);
        setProfiles(profList);
        setRoles(roleList);

        // Determine initially selected channel
        let targetId = channelId;
        if (!targetId && chList.length > 0) {
          targetId = chList[0].id;
        }

        if (targetId) {
          setSelectedChannelId(targetId);
          const foundPol = polList.find((p) => p.discord_channel_id === targetId) || null;
          setActivePolicy(foundPol);
        }
      } catch (err: any) {
        toast.error(err.message || 'Failed to load channel policies.');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [channelId]);

  // Sync selected channel when URL param changes
  useEffect(() => {
    if (channelId && channelId !== selectedChannelId) {
      setSelectedChannelId(channelId);
      const foundPol = policies.find((p) => p.discord_channel_id === channelId) || null;
      setActivePolicy(foundPol);
    }
  }, [channelId, policies, selectedChannelId]);

  const handleSelectChannel = (id: string) => {
    setSelectedChannelId(id);
    navigate(`/moderator/policies/${id}`);
    const foundPol = policies.find((p) => p.discord_channel_id === id) || null;
    setActivePolicy(foundPol);
  };

  const handleSavePolicy = async (policyData: Partial<ChannelPolicy>) => {
    if (!selectedChannelId) return;
    try {
      await policiesApi.saveChannelPolicy(selectedChannelId, policyData);
      toast.success('Channel policy saved successfully.');

      // Refresh policies list
      const updatedList = await policiesApi.getPolicies();
      setPolicies(updatedList);
      const foundPol = updatedList.find((p) => p.discord_channel_id === selectedChannelId) || null;
      setActivePolicy(foundPol);
    } catch (err: any) {
      toast.error(err.message || 'Could not save channel policy.');
      throw err;
    }
  };

  const handleDeletePolicy = async () => {
    if (!selectedChannelId) return;
    try {
      await policiesApi.deleteChannelPolicy(selectedChannelId);
      toast.success('Channel policy reset to default server inheritance.');

      const updatedList = await policiesApi.getPolicies();
      setPolicies(updatedList);
      setActivePolicy(null);
    } catch (err: any) {
      toast.error(err.message || 'Could not delete channel policy.');
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-gray-800 animate-pulse rounded" />
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  const selectedChannel = channels.find((c) => c.id === selectedChannelId);

  return (
    <div className="space-y-6 animate-fade-in h-[calc(100vh-8.5rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
            <Layers className="w-7 h-7 text-[#5865F2]" />
            <span>Channel Policies</span>
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Fine-grained channel-specific permission overrides, link blocking, and media rules.
          </p>
        </div>
      </div>

      {/* 2-Column Layout: Left Channel Tree, Right Policy Editor */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 flex-1 min-h-0">
        {/* Left Tree (4 cols) */}
        <div className="md:col-span-4 h-full">
          <ChannelTree
            channels={channels}
            policies={policies}
            selectedChannelId={selectedChannelId}
            onSelectChannel={handleSelectChannel}
          />
        </div>

        {/* Right Editor (8 cols) */}
        <div className="md:col-span-8 h-full">
          {selectedChannel ? (
            <ChannelPolicyEditor
              channel={selectedChannel}
              policy={activePolicy}
              profiles={profiles}
              onSave={handleSavePolicy}
              onDeletePolicy={activePolicy ? handleDeletePolicy : undefined}
              onOpenSimulator={() => setIsSimulatorOpen(true)}
            />
          ) : (
            <EmptyState
              title="Select a Channel"
              description="Choose a Discord text or voice channel from the tree on the left to inspect and configure its moderation policies."
              icon={Hash}
            />
          )}
        </div>
      </div>

      {/* Policy Tester Modal */}
      <PolicyTesterModal
        isOpen={isSimulatorOpen}
        channels={channels}
        roles={roles}
        initialChannelId={selectedChannelId || undefined}
        onClose={() => setIsSimulatorOpen(false)}
      />
    </div>
  );
}
