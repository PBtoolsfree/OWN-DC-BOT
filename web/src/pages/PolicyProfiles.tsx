import { useEffect, useState, useMemo } from 'react';
import { policiesApi } from '../api/policies';
import { channelsApi } from '../api/channels';
import { PolicyProfile, DiscordChannel, PolicyValue } from '../types';
import { PolicyPresetCard } from '../components/PolicyPresetCard';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { toast } from '../hooks/useToast';
import {
  Bookmark,
  Plus,
  Search,
  Filter,
  X,
  Check,
  Shield,
  Trash2,
  AlertTriangle,
} from 'lucide-react';

const CATEGORIES = [
  'All',
  'General',
  'Media',
  'Moderation',
  'Announcements',
  'Support',
  'Bots',
  'Events',
  'Community',
  'Private',
  'Other',
];

interface CustomPolicyForm {
  id?: number;
  name: string;
  description: string;
  category: string;
  allow_text: PolicyValue;
  allow_links: PolicyValue;
  allow_images: PolicyValue;
  allow_videos: PolicyValue;
  allow_files: PolicyValue;
  allow_stickers: PolicyValue;
  allow_everyone: PolicyValue;
  allow_here: PolicyValue;
  allow_role_mentions: PolicyValue;
  allow_user_mentions: PolicyValue;
  delete_violations: boolean;
  warn_on_violation: boolean;
  log_violations: boolean;
  send_dm_warning: boolean;
  warning_message: string;
}

const defaultForm: CustomPolicyForm = {
  name: '',
  description: '',
  category: 'General',
  allow_text: 'allow',
  allow_links: 'allow',
  allow_images: 'allow',
  allow_videos: 'allow',
  allow_files: 'allow',
  allow_stickers: 'allow',
  allow_everyone: 'deny',
  allow_here: 'deny',
  allow_role_mentions: 'allow',
  allow_user_mentions: 'allow',
  delete_violations: true,
  warn_on_violation: true,
  log_violations: true,
  send_dm_warning: false,
  warning_message: '',
};

export default function PolicyProfiles() {
  const [loading, setLoading] = useState(true);
  const [profiles, setProfiles] = useState<PolicyProfile[]>([]);
  const [channels, setChannels] = useState<DiscordChannel[]>([]);

  // Search & Filtering
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  // Apply preset dialog state
  const [applyTarget, setApplyTarget] = useState<PolicyProfile | null>(null);
  const [selectedChannelIds, setSelectedChannelIds] = useState<string[]>([]);
  const [isApplying, setIsApplying] = useState(false);

  // Custom policy modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form, setForm] = useState<CustomPolicyForm>(defaultForm);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [profList, chList] = await Promise.all([
        policiesApi.getProfiles(),
        channelsApi.getChannels(),
      ]);
      setProfiles(profList);
      setChannels(chList);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load policy profiles.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Filtered lists
  const filteredProfiles = useMemo(() => {
    return profiles.filter((p) => {
      const matchesSearch =
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (p.description || '').toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory =
        selectedCategory === 'All' ||
        (p.category || 'General').toLowerCase() === selectedCategory.toLowerCase();
      return matchesSearch && matchesCategory;
    });
  }, [profiles, searchQuery, selectedCategory]);

  const builtInPresets = filteredProfiles.filter((p) => p.is_builtin);
  const customPolicies = filteredProfiles.filter((p) => !p.is_builtin);

  // Open Apply modal
  const handleApplyClick = (profile: PolicyProfile) => {
    setApplyTarget(profile);
    setSelectedChannelIds(channels.length > 0 ? [channels[0].id] : []);
  };

  const toggleChannelSelection = (channelId: string) => {
    setSelectedChannelIds((prev) =>
      prev.includes(channelId) ? prev.filter((id) => id !== channelId) : [...prev, channelId]
    );
  };

  const toggleCategoryChannels = (catName: string) => {
    const catChannelIds = channels.filter((c) => (c.category || 'Uncategorized') === catName).map((c) => c.id);
    const allSelected = catChannelIds.every((id) => selectedChannelIds.includes(id));
    if (allSelected) {
      setSelectedChannelIds((prev) => prev.filter((id) => !catChannelIds.includes(id)));
    } else {
      setSelectedChannelIds((prev) => Array.from(new Set([...prev, ...catChannelIds])));
    }
  };

  const handleApplyConfirm = async () => {
    if (!applyTarget || selectedChannelIds.length === 0) return;
    setIsApplying(true);
    try {
      const res = await policiesApi.applyProfile(applyTarget.id, selectedChannelIds);
      toast.success(res.message || `Applied ${applyTarget.name} to ${selectedChannelIds.length} channel(s)`);
      setApplyTarget(null);
    } catch (err: any) {
      toast.error(err.message || 'Failed to apply policy to channels.');
    } finally {
      setIsApplying(false);
    }
  };

  // Open Custom Policy Builder modal
  const handleOpenCreateModal = () => {
    setForm(defaultForm);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (profile: PolicyProfile) => {
    setForm({
      id: profile.id,
      name: profile.name,
      description: profile.description || '',
      category: profile.category || 'General',
      allow_text: profile.allow_text,
      allow_links: profile.allow_links,
      allow_images: profile.allow_images,
      allow_videos: profile.allow_videos,
      allow_files: profile.allow_files,
      allow_stickers: profile.allow_stickers,
      allow_everyone: profile.allow_everyone,
      allow_here: profile.allow_here,
      allow_role_mentions: profile.allow_role_mentions,
      allow_user_mentions: profile.allow_user_mentions,
      delete_violations: profile.delete_violations ?? true,
      warn_on_violation: profile.warn_on_violation ?? true,
      log_violations: profile.log_violations ?? true,
      send_dm_warning: profile.send_dm_warning ?? false,
      warning_message: profile.warning_message || '',
    });
    setIsModalOpen(true);
  };

  const handleSaveCustomPolicy = async () => {
    if (!form.name.trim()) {
      toast.error('Policy name is required.');
      return;
    }
    setIsSubmitting(true);
    try {
      if (form.id) {
        await policiesApi.updateProfile(form.id, form);
        toast.success(`Custom policy "${form.name}" updated successfully.`);
      } else {
        await policiesApi.createProfile(form);
        toast.success(`Custom policy "${form.name}" created successfully.`);
      }
      setIsModalOpen(false);
      await loadData();
    } catch (err: any) {
      toast.error(err.message || 'Failed to save custom policy.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Duplicate profile
  const handleClone = async (profile: PolicyProfile) => {
    try {
      const duplicated = await policiesApi.duplicateProfile(profile.id);
      toast.success(`Created custom policy "${duplicated.name}".`);
      await loadData();
    } catch (err: any) {
      toast.error(err.message || 'Failed to duplicate profile.');
    }
  };

  // Delete custom policy
  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await policiesApi.deleteProfile(deleteTarget.id);
      toast.success(`Deleted policy "${deleteTarget.name}".`);
      setDeleteTarget(null);
      await loadData();
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete custom policy.');
    }
  };

  // Group channels by category for apply dialog
  const channelCategories = useMemo(() => {
    const map = new Map<string, DiscordChannel[]>();
    for (const ch of channels) {
      const cat = ch.category || 'Uncategorized';
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(ch);
    }
    return Array.from(map.entries());
  }, [channels]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-gray-800 animate-pulse rounded" />
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  const renderValueToggle = (
    label: string,
    field: keyof CustomPolicyForm,
    currentValue: PolicyValue
  ) => {
    const options: PolicyValue[] = ['allow', 'deny', 'inherit'];
    return (
      <div className="flex items-center justify-between p-3 bg-[#0B0E14] border border-gray-800 rounded-xl">
        <span className="text-xs font-semibold text-gray-300">{label}</span>
        <div className="flex items-center gap-1 bg-[#151921] p-1 rounded-lg border border-gray-800">
          {options.map((opt) => {
            const isSelected = currentValue === opt;
            let activeClass = 'bg-[#5865F2] text-white';
            if (opt === 'deny') activeClass = 'bg-rose-600 text-white';
            if (opt === 'inherit') activeClass = 'bg-amber-600 text-white';

            return (
              <button
                key={opt}
                type="button"
                onClick={() => setForm({ ...form, [field]: opt })}
                className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase transition-all ${
                  isSelected ? activeClass : 'text-gray-400 hover:text-white'
                }`}
              >
                {opt}
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
            <Bookmark className="w-7 h-7 text-[#5865F2]" />
            <span>Policy Profiles & Presets</span>
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Professional built-in presets and customizable moderation policies for your Discord server.
          </p>
        </div>

        <button
          onClick={handleOpenCreateModal}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-[#5865F2]/20 self-start md:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>+ Create Custom Policy</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-4 flex flex-col md:flex-row gap-4 justify-between items-center shadow-lg">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search policies by name or rule..."
            className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2]"
          />
        </div>

        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0 custom-scrollbar">
          <Filter className="w-3.5 h-3.5 text-gray-500 mr-1 shrink-0" />
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all ${
                selectedCategory === cat
                  ? 'bg-[#5865F2] text-white shadow'
                  : 'bg-[#0B0E14] text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Custom Policies Section */}
      {customPolicies.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-gray-800 pb-2">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              <span>CUSTOM POLICIES</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-mono">
                {customPolicies.length}
              </span>
            </h2>
            <span className="text-xs text-gray-500">Editable & user-defined security policies</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {customPolicies.map((prof) => (
              <PolicyPresetCard
                key={prof.id}
                profile={prof}
                onApply={handleApplyClick}
                onClone={handleClone}
                onEdit={handleOpenEditModal}
                onDelete={(id, name) => setDeleteTarget({ id, name })}
              />
            ))}
          </div>
        </div>
      )}

      {/* Built-in Presets Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between border-b border-gray-800 pb-2">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#5865F2]" />
            <span>BUILT-IN PRESETS</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-[#5865F2]/10 text-[#5865F2] font-mono">
              {builtInPresets.length}
            </span>
          </h2>
          <span className="text-xs text-gray-500">Standardized immutable templates</span>
        </div>

        {builtInPresets.length === 0 ? (
          <div className="text-center py-12 text-gray-500 text-xs bg-[#151921] rounded-2xl border border-gray-800">
            No matching presets found.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {builtInPresets.map((prof) => (
              <PolicyPresetCard
                key={prof.id}
                profile={prof}
                onApply={handleApplyClick}
                onClone={handleClone}
              />
            ))}
          </div>
        )}
      </div>

      {/* Apply to Channel(s) Dialog */}
      {applyTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#151921] border border-gray-800 rounded-2xl max-w-xl w-full shadow-2xl overflow-hidden animate-scale-in max-h-[90vh] flex flex-col">
            <div className="p-5 border-b border-gray-800 bg-[#12161f] flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">
                  Apply Policy: {applyTarget.name.replace(/_/g, ' ')}
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Select one or multiple Discord channels to enforce this policy
                </p>
              </div>
              <button
                onClick={() => setApplyTarget(null)}
                className="p-1 text-gray-400 hover:text-white rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4 flex-1 custom-scrollbar">
              <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 leading-relaxed flex items-center gap-2.5">
                <AlertTriangle className="w-5 h-5 shrink-0 text-amber-400" />
                <span>
                  Applying this policy will update channel rules. Channels with custom overrides will be reset to match this template.
                </span>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs font-semibold text-gray-300">
                  <span>DISCORD CHANNELS (GROUPED BY CATEGORY)</span>
                  <span className="text-[#5865F2] font-mono">
                    {selectedChannelIds.length} Selected
                  </span>
                </div>

                {channelCategories.map(([catName, catChannels]) => {
                  const allCatSelected = catChannels.every((c) => selectedChannelIds.includes(c.id));
                  return (
                    <div key={catName} className="bg-[#0B0E14] border border-gray-800 rounded-xl overflow-hidden">
                      <div className="px-3.5 py-2 bg-[#12161f] border-b border-gray-800 flex items-center justify-between">
                        <span className="text-[11px] font-extrabold uppercase tracking-wider text-gray-400">
                          {catName}
                        </span>
                        <button
                          type="button"
                          onClick={() => toggleCategoryChannels(catName)}
                          className="text-[10px] text-[#5865F2] hover:underline font-semibold"
                        >
                          {allCatSelected ? 'Deselect All' : 'Select All'}
                        </button>
                      </div>
                      <div className="p-2 grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                        {catChannels.map((ch) => {
                          const isSelected = selectedChannelIds.includes(ch.id);
                          return (
                            <button
                              key={ch.id}
                              type="button"
                              onClick={() => toggleChannelSelection(ch.id)}
                              className={`flex items-center justify-between p-2 rounded-lg text-xs font-medium transition-all text-left ${
                                isSelected
                                  ? 'bg-[#5865F2]/20 border border-[#5865F2]/50 text-white'
                                  : 'bg-[#151921] border border-transparent text-gray-400 hover:text-white'
                              }`}
                            >
                              <span className="truncate">#{ch.name}</span>
                              <div
                                className={`w-4 h-4 rounded flex items-center justify-center text-[10px] border ${
                                  isSelected
                                    ? 'bg-[#5865F2] border-[#5865F2] text-white'
                                    : 'border-gray-700 bg-gray-800'
                                }`}
                              >
                                {isSelected && <Check className="w-3 h-3" />}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="flex items-center justify-between p-5 border-t border-gray-800 bg-[#12161f]">
              <span className="text-xs text-gray-400">
                Apply this policy to{' '}
                <strong className="text-white">{selectedChannelIds.length}</strong> channel(s)?
              </span>
              <div className="flex items-center gap-3">
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
                  disabled={isApplying || selectedChannelIds.length === 0}
                  className="px-5 py-2 text-xs font-bold text-white bg-[#5865F2] hover:bg-[#4752c4] rounded-xl transition-all shadow disabled:opacity-50"
                >
                  {isApplying ? 'Applying...' : `Apply (${selectedChannelIds.length})`}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit Custom Policy Builder Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#151921] border border-gray-800 rounded-2xl max-w-2xl w-full shadow-2xl overflow-hidden animate-scale-in max-h-[90vh] flex flex-col">
            <div className="p-5 border-b border-gray-800 bg-[#12161f] flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Shield className="w-5 h-5 text-[#5865F2]" />
                  <span>{form.id ? 'Edit Custom Policy' : 'Create Custom Policy'}</span>
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Configure three-state permission rules and enforcement actions
                </p>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 text-gray-400 hover:text-white rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-6 flex-1 custom-scrollbar">
              {/* Meta fields */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-300">Policy Name *</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="e.g. STRICT LINKS ONLY"
                    className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-gray-300">Category</label>
                  <select
                    value={form.category}
                    onChange={(e) => setForm({ ...form, category: e.target.value })}
                    className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                  >
                    {CATEGORIES.filter((c) => c !== 'All').map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-gray-300">Description / Purpose</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="e.g. Restricts image attachments while allowing normal conversation"
                  className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                />
              </div>

              {/* Rules Grid */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                  Message Content Rules (ALLOW / DENY / INHERIT)
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {renderValueToggle('Allow Text Messages', 'allow_text', form.allow_text)}
                  {renderValueToggle('Allow Embedded Links', 'allow_links', form.allow_links)}
                  {renderValueToggle('Allow Images', 'allow_images', form.allow_images)}
                  {renderValueToggle('Allow Videos', 'allow_videos', form.allow_videos)}
                  {renderValueToggle('Allow Files & Docs', 'allow_files', form.allow_files)}
                  {renderValueToggle('Allow Stickers & Emojis', 'allow_stickers', form.allow_stickers)}
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                  Mentions & Pings
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {renderValueToggle('Allow @everyone', 'allow_everyone', form.allow_everyone)}
                  {renderValueToggle('Allow @here', 'allow_here', form.allow_here)}
                  {renderValueToggle('Allow Role Mentions', 'allow_role_mentions', form.allow_role_mentions)}
                  {renderValueToggle('Allow User Mentions', 'allow_user_mentions', form.allow_user_mentions)}
                </div>
              </div>

              {/* Enforcement Toggles */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                  Violation Handling
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <label className="flex items-center gap-2.5 p-3 bg-[#0B0E14] border border-gray-800 rounded-xl cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.delete_violations}
                      onChange={(e) => setForm({ ...form, delete_violations: e.target.checked })}
                      className="rounded border-gray-700 bg-gray-900 text-[#5865F2]"
                    />
                    <span className="text-xs text-gray-300">Delete Violating Message</span>
                  </label>

                  <label className="flex items-center gap-2.5 p-3 bg-[#0B0E14] border border-gray-800 rounded-xl cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.warn_on_violation}
                      onChange={(e) => setForm({ ...form, warn_on_violation: e.target.checked })}
                      className="rounded border-gray-700 bg-gray-900 text-[#5865F2]"
                    />
                    <span className="text-xs text-gray-300">Warning Message in Channel</span>
                  </label>

                  <label className="flex items-center gap-2.5 p-3 bg-[#0B0E14] border border-gray-800 rounded-xl cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.send_dm_warning}
                      onChange={(e) => setForm({ ...form, send_dm_warning: e.target.checked })}
                      className="rounded border-gray-700 bg-gray-900 text-[#5865F2]"
                    />
                    <span className="text-xs text-gray-300">Send Direct Message (DM) Warning</span>
                  </label>

                  <label className="flex items-center gap-2.5 p-3 bg-[#0B0E14] border border-gray-800 rounded-xl cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.log_violations}
                      onChange={(e) => setForm({ ...form, log_violations: e.target.checked })}
                      className="rounded border-gray-700 bg-gray-900 text-[#5865F2]"
                    />
                    <span className="text-xs text-gray-300">Log Incident in Mod Channel</span>
                  </label>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-gray-300">
                  Custom Warning Message (Optional)
                </label>
                <input
                  type="text"
                  value={form.warning_message}
                  onChange={(e) => setForm({ ...form, warning_message: e.target.value })}
                  placeholder="e.g. Links are not permitted in this channel. Please review server rules."
                  className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 p-5 border-t border-gray-800 bg-[#12161f]">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                disabled={isSubmitting}
                className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveCustomPolicy}
                disabled={isSubmitting}
                className="px-5 py-2 text-xs font-bold text-white bg-[#5865F2] hover:bg-[#4752c4] rounded-xl transition-all shadow disabled:opacity-50"
              >
                {isSubmitting ? 'Saving...' : form.id ? 'Save Changes' : 'Create Policy'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#151921] border border-gray-800 rounded-2xl max-w-sm w-full p-5 shadow-2xl space-y-4 animate-scale-in">
            <div className="flex items-center gap-3 text-rose-400">
              <div className="p-2.5 rounded-xl bg-rose-500/10">
                <Trash2 className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white">Delete Policy Profile?</h3>
            </div>
            <p className="text-xs text-gray-400 leading-relaxed">
              Are you sure you want to permanently delete custom policy{' '}
              <strong className="text-white">"{deleteTarget.name}"</strong>? Existing channels using this preset will retain their current settings.
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                className="px-3.5 py-2 text-xs font-medium text-gray-400 hover:text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                className="px-4 py-2 text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 rounded-xl transition-colors shadow"
              >
                Delete Policy
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
