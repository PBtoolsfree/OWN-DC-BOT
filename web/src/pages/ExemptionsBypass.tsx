import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  Plus,
  Trash2,
  Edit2,
  CheckCircle2,
  AlertTriangle,
  User,
  Users,
  Bot,
  Webhook,
  Info,
  Layers,
  X,
} from 'lucide-react';
import { moderationApi } from '../api/moderation';
import { ModerationExemption, GuildTargets } from '../types';

export const ExemptionsBypass: React.FC = () => {
  const [exemptions, setExemptions] = useState<ModerationExemption[]>([]);
  const [guildTargets, setGuildTargets] = useState<GuildTargets | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [editingExemption, setEditingExemption] = useState<ModerationExemption | null>(null);
  const [confirmBypassAll, setConfirmBypassAll] = useState(false);

  // Form State
  const [targetType, setTargetType] = useState<'user' | 'role' | 'bot' | 'webhook'>('role');
  const [targetId, setTargetId] = useState('');
  const [targetName, setTargetName] = useState('');
  const [scope, setScope] = useState<'global' | 'category' | 'channel' | 'channel_type'>('global');
  const [scopeId, setScopeId] = useState('');
  const [scopeName, setScopeName] = useState('');
  const [channelType, setChannelType] = useState('text');

  // Granular Bypass Flags
  const [bypassAll, setBypassAll] = useState(false);
  const [bypassText, setBypassText] = useState(false);
  const [bypassLinks, setBypassLinks] = useState(false);
  const [bypassImages, setBypassImages] = useState(false);
  const [bypassVideos, setBypassVideos] = useState(false);
  const [bypassFiles, setBypassFiles] = useState(false);
  const [bypassStickers, setBypassStickers] = useState(false);
  const [bypassMentions, setBypassMentions] = useState(false);
  const [bypassSpam, setBypassSpam] = useState(false);
  const [bypassKeywords, setBypassKeywords] = useState(false);
  const [bypassInvites, setBypassInvites] = useState(false);
  const [bypassWarnings, setBypassWarnings] = useState(false);
  const [bypassTimeout, setBypassTimeout] = useState(false);
  const [bypassKick, setBypassKick] = useState(false);
  const [bypassBan, setBypassBan] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [exRes, targetsRes] = await Promise.all([
        moderationApi.getModerationExemptions(),
        moderationApi.getGuildTargets().catch(() => null),
      ]);
      setExemptions(exRes);
      if (targetsRes) setGuildTargets(targetsRes);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load exemptions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const openCreateModal = () => {
    setEditingExemption(null);
    setTargetType('role');
    setTargetId('');
    setTargetName('');
    setScope('global');
    setScopeId('');
    setScopeName('');
    setChannelType('text');
    setBypassAll(false);
    setBypassText(false);
    setBypassLinks(true);
    setBypassImages(false);
    setBypassVideos(false);
    setBypassFiles(false);
    setBypassStickers(false);
    setBypassMentions(false);
    setBypassSpam(true);
    setBypassKeywords(false);
    setBypassInvites(false);
    setBypassWarnings(false);
    setBypassTimeout(false);
    setBypassKick(false);
    setBypassBan(false);
    setModalOpen(true);
  };

  const openEditModal = (ex: ModerationExemption) => {
    setEditingExemption(ex);
    setTargetType(ex.target_type);
    setTargetId(ex.target_id);
    setTargetName(ex.target_name || '');
    setScope(ex.scope);
    setScopeId(ex.scope_id || '');
    setScopeName(ex.scope_name || '');
    setChannelType(ex.channel_type || 'text');
    setBypassAll(ex.bypass_all);
    setBypassText(ex.bypass_text);
    setBypassLinks(ex.bypass_links);
    setBypassImages(ex.bypass_images);
    setBypassVideos(ex.bypass_videos);
    setBypassFiles(ex.bypass_files);
    setBypassStickers(ex.bypass_stickers);
    setBypassMentions(ex.bypass_mentions);
    setBypassSpam(ex.bypass_spam);
    setBypassKeywords(ex.bypass_keywords);
    setBypassInvites(ex.bypass_invites);
    setBypassWarnings(ex.bypass_warnings);
    setBypassTimeout(ex.bypass_timeout);
    setBypassKick(ex.bypass_kick);
    setBypassBan(ex.bypass_ban);
    setModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetId) {
      setError('Please select a target');
      return;
    }

    const payload: Partial<ModerationExemption> = {
      target_type: targetType,
      target_id: targetId,
      target_name: targetName || undefined,
      scope: scope,
      scope_id: scopeId || undefined,
      scope_name: scopeName || undefined,
      channel_type: scope === 'channel_type' ? channelType : undefined,
      bypass_all: bypassAll,
      bypass_text: bypassText,
      bypass_links: bypassLinks,
      bypass_images: bypassImages,
      bypass_videos: bypassVideos,
      bypass_files: bypassFiles,
      bypass_stickers: bypassStickers,
      bypass_mentions: bypassMentions,
      bypass_spam: bypassSpam,
      bypass_keywords: bypassKeywords,
      bypass_invites: bypassInvites,
      bypass_warnings: bypassWarnings,
      bypass_timeout: bypassTimeout,
      bypass_kick: bypassKick,
      bypass_ban: bypassBan,
    };

    try {
      if (editingExemption) {
        await moderationApi.updateModerationExemption(editingExemption.id, payload);
        setSuccessMsg('Exemption updated successfully');
      } else {
        await moderationApi.createModerationExemption(payload);
        setSuccessMsg('Exemption created successfully');
      }
      setModalOpen(false);
      fetchData();
      setTimeout(() => setSuccessMsg(null), 3500);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save exemption');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to remove this exemption rule?')) return;
    try {
      await moderationApi.deleteModerationExemption(id);
      setSuccessMsg('Exemption removed');
      fetchData();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to delete exemption');
    }
  };

  // Find target permissions info
  const selectedRole = guildTargets?.roles?.find((r) => r.id === targetId);
  const selectedMember = guildTargets?.members?.find((m) => m.id === targetId);
  const selectedBot = guildTargets?.bots?.find((b) => b.id === targetId);
  const activePermissions = selectedRole?.permissions || selectedMember?.permissions || selectedBot?.permissions;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-white tracking-wide">Exemptions & Bypass</h1>
              <p className="text-sm text-gray-400">
                Grant trusted users, roles, and bots permission to bypass PB HERO moderation rules
              </p>
            </div>
          </div>
        </div>
        <button
          onClick={openCreateModal}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white text-sm font-semibold rounded-xl shadow-lg shadow-[#5865F2]/20 transition-all cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Add Exemption</span>
        </button>
      </div>

      {/* Precedence & Safety Notice */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2 p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-200">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-sm text-blue-300">PB HERO Bypass Safety & Precedence</h4>
              <p className="text-xs text-blue-300/80 mt-1 leading-relaxed">
                PB HERO bypass <strong>only skips custom PB HERO bot moderation</strong>. Discord native permissions
                and role hierarchy still apply strictly. It will never grant users Discord moderation powers.
              </p>
              <div className="mt-2.5 flex items-center gap-2 flex-wrap text-[11px] font-mono">
                <span className="text-gray-400">Priority:</span>
                <span className="px-2 py-0.5 rounded bg-blue-900/40 text-blue-200 border border-blue-800">1. User</span>
                <span>&gt;</span>
                <span className="px-2 py-0.5 rounded bg-blue-900/40 text-blue-200 border border-blue-800">2. Role</span>
                <span>&gt;</span>
                <span className="px-2 py-0.5 rounded bg-blue-900/40 text-blue-200 border border-blue-800">3. Bot</span>
                <span>&gt;</span>
                <span className="px-2 py-0.5 rounded bg-blue-900/40 text-blue-200 border border-blue-800">4. Channel</span>
                <span>&gt;</span>
                <span className="px-2 py-0.5 rounded bg-blue-900/40 text-blue-200 border border-blue-800">5. Category</span>
              </div>
            </div>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[#1c222d] border border-gray-800 text-gray-300 flex flex-col justify-center">
          <div className="flex items-center gap-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
            <Layers className="w-4 h-4 text-purple-400" />
            <span>Active Exemptions</span>
          </div>
          <div className="text-2xl font-black text-white mt-1">{exemptions.length} Rules</div>
          <span className="text-[11px] text-gray-400 mt-1">Granular per-filter bypass rules configured</span>
        </div>
      </div>

      {/* Feedback Messages */}
      {successMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>{successMsg}</span>
        </div>
      )}
      {error && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      {/* Exemptions List */}
      <div className="bg-[#1c222d] border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h3 className="font-bold text-white text-base">Configured Bypass Rules</h3>
          <span className="text-xs text-gray-400">Deterministic bypass enforcement</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-gray-400">Loading exemptions...</div>
        ) : exemptions.length === 0 ? (
          <div className="p-12 text-center">
            <ShieldAlert className="w-12 h-12 text-gray-600 mx-auto mb-3" />
            <h4 className="text-base font-semibold text-gray-300">No Exemptions Configured</h4>
            <p className="text-xs text-gray-400 mt-1 max-w-sm mx-auto">
              All members and bots are currently subject to channel moderation rules. Click 'Add Exemption' to grant trusted roles or bots bypass access.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {exemptions.map((ex) => {
              const activeCount = [
                ex.bypass_text,
                ex.bypass_links,
                ex.bypass_images,
                ex.bypass_videos,
                ex.bypass_files,
                ex.bypass_stickers,
                ex.bypass_mentions,
                ex.bypass_spam,
                ex.bypass_keywords,
                ex.bypass_invites,
                ex.bypass_warnings,
                ex.bypass_timeout,
                ex.bypass_kick,
                ex.bypass_ban,
              ].filter(Boolean).length;

              return (
                <div key={ex.id} className="p-4 hover:bg-gray-800/40 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-start gap-3.5">
                    <div className="p-2.5 rounded-xl bg-gray-800 text-gray-300 shrink-0 mt-0.5">
                      {ex.target_type === 'role' && <Users className="w-5 h-5 text-indigo-400" />}
                      {ex.target_type === 'user' && <User className="w-5 h-5 text-emerald-400" />}
                      {ex.target_type === 'bot' && <Bot className="w-5 h-5 text-amber-400" />}
                      {ex.target_type === 'webhook' && <Webhook className="w-5 h-5 text-rose-400" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-white text-base">
                          {ex.target_name || `${ex.target_type.toUpperCase()} #${ex.target_id}`}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-gray-800 text-gray-300 border border-gray-700">
                          {ex.target_type}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-purple-900/30 text-purple-300 border border-purple-800/50">
                          Scope: {ex.scope} {ex.scope_name ? `(${ex.scope_name})` : ''}
                        </span>
                        {ex.bypass_all && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-500/20 text-rose-400 border border-rose-500/30">
                            Bypass All
                          </span>
                        )}
                      </div>

                      {/* Active Bypassed Filters */}
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {ex.bypass_all ? (
                          <span className="text-xs text-rose-300 font-medium">Bypasses all PB HERO moderation filters and automated punishments.</span>
                        ) : activeCount === 0 ? (
                          <span className="text-xs text-gray-400 italic">No specific filters bypassed</span>
                        ) : (
                          <>
                            {ex.bypass_links && <span className="px-2 py-0.5 text-[11px] rounded bg-gray-800 text-gray-300">Links</span>}
                            {ex.bypass_invites && <span className="px-2 py-0.5 text-[11px] rounded bg-gray-800 text-gray-300">Invites</span>}
                            {ex.bypass_spam && <span className="px-2 py-0.5 text-[11px] rounded bg-gray-800 text-gray-300">Spam</span>}
                            {ex.bypass_mentions && <span className="px-2 py-0.5 text-[11px] rounded bg-gray-800 text-gray-300">Mentions</span>}
                            {ex.bypass_text && <span className="px-2 py-0.5 text-[11px] rounded bg-gray-800 text-gray-300">Text Filter</span>}
                            {ex.bypass_images && <span className="px-2 py-0.5 text-[11px] rounded bg-gray-800 text-gray-300">Images</span>}
                            {ex.bypass_videos && <span className="px-2 py-0.5 text-[11px] rounded bg-gray-800 text-gray-300">Videos</span>}
                            {ex.bypass_files && <span className="px-2 py-0.5 text-[11px] rounded bg-gray-800 text-gray-300">Files</span>}
                            {ex.bypass_stickers && <span className="px-2 py-0.5 text-[11px] rounded bg-gray-800 text-gray-300">Stickers</span>}
                            {ex.bypass_keywords && <span className="px-2 py-0.5 text-[11px] rounded bg-gray-800 text-gray-300">Keywords</span>}
                            {ex.bypass_warnings && <span className="px-2 py-0.5 text-[11px] rounded bg-amber-900/30 text-amber-300">Warnings</span>}
                            {ex.bypass_timeout && <span className="px-2 py-0.5 text-[11px] rounded bg-amber-900/30 text-amber-300">Timeout</span>}
                            {ex.bypass_kick && <span className="px-2 py-0.5 text-[11px] rounded bg-rose-900/30 text-rose-300">Kick</span>}
                            {ex.bypass_ban && <span className="px-2 py-0.5 text-[11px] rounded bg-rose-900/30 text-rose-300">Ban</span>}
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end md:self-center">
                    <button
                      onClick={() => openEditModal(ex)}
                      className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors cursor-pointer"
                      title="Edit Exemption"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(ex.id)}
                      className="p-2 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition-colors cursor-pointer"
                      title="Delete Exemption"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Create / Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm overflow-y-auto">
          <div className="bg-[#1c222d] border border-gray-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl my-8">
            <div className="p-5 border-b border-gray-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-purple-500/20 text-purple-400">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-white text-lg">
                  {editingExemption ? 'Edit Moderation Exemption' : 'Create Moderation Exemption'}
                </h3>
              </div>
              <button
                onClick={() => setModalOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSave} className="p-6 space-y-6">
              {/* Target Type Selector */}
              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                  Target Type
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {(['role', 'user', 'bot', 'webhook'] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => {
                        setTargetType(t);
                        setTargetId('');
                        setTargetName('');
                      }}
                      className={`p-3 rounded-xl border flex flex-col items-center gap-1.5 text-xs font-bold uppercase transition-all ${
                        targetType === t
                          ? 'bg-[#5865F2]/20 border-[#5865F2] text-white shadow-sm'
                          : 'bg-gray-800/40 border-gray-800 text-gray-400 hover:text-white hover:bg-gray-800'
                      }`}
                    >
                      {t === 'role' && <Users className="w-4 h-4" />}
                      {t === 'user' && <User className="w-4 h-4" />}
                      {t === 'bot' && <Bot className="w-4 h-4" />}
                      {t === 'webhook' && <Webhook className="w-4 h-4" />}
                      <span>{t}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Dynamic Target Selector */}
              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                  Select {targetType.toUpperCase()}
                </label>
                {targetType === 'role' && (
                  <select
                    value={targetId}
                    onChange={(e) => {
                      setTargetId(e.target.value);
                      const r = guildTargets?.roles.find((x) => x.id === e.target.value);
                      if (r) setTargetName(r.name);
                    }}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm focus:border-[#5865F2] focus:outline-none"
                    required
                  >
                    <option value="">-- Choose Discord Role --</option>
                    {guildTargets?.roles.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                )}

                {targetType === 'user' && (
                  <select
                    value={targetId}
                    onChange={(e) => {
                      setTargetId(e.target.value);
                      const m = guildTargets?.members.find((x) => x.id === e.target.value);
                      if (m) setTargetName(m.display_name || m.username);
                    }}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm focus:border-[#5865F2] focus:outline-none"
                    required
                  >
                    <option value="">-- Choose Member --</option>
                    {guildTargets?.members.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.display_name} ({m.username})
                      </option>
                    ))}
                  </select>
                )}

                {targetType === 'bot' && (
                  <select
                    value={targetId}
                    onChange={(e) => {
                      setTargetId(e.target.value);
                      const b = guildTargets?.bots.find((x) => x.id === e.target.value);
                      if (b) setTargetName(b.display_name || b.username);
                    }}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm focus:border-[#5865F2] focus:outline-none"
                    required
                  >
                    <option value="">-- Choose Discord Bot --</option>
                    {guildTargets?.bots.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.display_name} ({b.username})
                      </option>
                    ))}
                  </select>
                )}

                {targetType === 'webhook' && (
                  <input
                    type="text"
                    value={targetId}
                    onChange={(e) => {
                      setTargetId(e.target.value);
                      setTargetName(`Webhook ${e.target.value.slice(0, 6)}`);
                    }}
                    placeholder="Enter Webhook ID or * for all webhooks"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm focus:border-[#5865F2] focus:outline-none"
                    required
                  />
                )}

                {/* Discord Permission Telemetry (Informational) */}
                {activePermissions && (
                  <div className="mt-3 p-3 rounded-xl bg-gray-900/60 border border-gray-800 text-xs text-gray-400">
                    <span className="font-semibold text-gray-300 block mb-1">
                      Discord Permissions Telemetry (Informational only):
                    </span>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {activePermissions.administrator && (
                        <span className="px-2 py-0.5 rounded bg-purple-900/40 text-purple-300 border border-purple-800">
                          Administrator
                        </span>
                      )}
                      {activePermissions.manage_guild && (
                        <span className="px-2 py-0.5 rounded bg-blue-900/40 text-blue-300 border border-blue-800">
                          Manage Server
                        </span>
                      )}
                      {activePermissions.manage_messages && (
                        <span className="px-2 py-0.5 rounded bg-blue-900/40 text-blue-300 border border-blue-800">
                          Manage Messages
                        </span>
                      )}
                      {activePermissions.moderate_members && (
                        <span className="px-2 py-0.5 rounded bg-emerald-900/40 text-emerald-300 border border-emerald-800">
                          Moderate Members
                        </span>
                      )}
                      {activePermissions.kick_members && (
                        <span className="px-2 py-0.5 rounded bg-amber-900/40 text-amber-300 border border-amber-800">
                          Kick Members
                        </span>
                      )}
                      {activePermissions.ban_members && (
                        <span className="px-2 py-0.5 rounded bg-rose-900/40 text-rose-300 border border-rose-800">
                          Ban Members
                        </span>
                      )}
                      {!Object.values(activePermissions).some(Boolean) && (
                        <span className="text-gray-400 italic">No elevated Discord moderation permissions</span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Exemption Scope */}
              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                  Exemption Scope
                </label>
                <div className="grid grid-cols-4 gap-2 mb-3">
                  {(['global', 'category', 'channel', 'channel_type'] as const).map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => {
                        setScope(s);
                        setScopeId('');
                        setScopeName('');
                      }}
                      className={`p-2.5 rounded-xl border text-center text-xs font-semibold uppercase transition-all ${
                        scope === s
                          ? 'bg-purple-600/20 border-purple-500 text-purple-300'
                          : 'bg-gray-800/40 border-gray-800 text-gray-400 hover:text-white'
                      }`}
                    >
                      {s.replace('_', ' ')}
                    </button>
                  ))}
                </div>

                {scope === 'category' && (
                  <select
                    value={scopeId}
                    onChange={(e) => {
                      setScopeId(e.target.value);
                      const cat = guildTargets?.categories.find((c) => c.id === e.target.value);
                      if (cat) setScopeName(cat.name);
                    }}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                    required
                  >
                    <option value="">-- Choose Category --</option>
                    {guildTargets?.categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                )}

                {scope === 'channel' && (
                  <select
                    value={scopeId}
                    onChange={(e) => {
                      setScopeId(e.target.value);
                      const ch = guildTargets?.channels.find((x) => x.id === e.target.value);
                      if (ch) setScopeName(ch.name);
                    }}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                    required
                  >
                    <option value="">-- Choose Channel --</option>
                    {guildTargets?.channels.map((ch) => (
                      <option key={ch.id} value={ch.id}>
                        #{ch.name} ({ch.category})
                      </option>
                    ))}
                  </select>
                )}

                {scope === 'channel_type' && (
                  <div className="grid grid-cols-3 gap-2">
                    {['text', 'voice', 'thread'].map((ct) => (
                      <button
                        key={ct}
                        type="button"
                        onClick={() => setChannelType(ct)}
                        className={`p-2 rounded-lg border text-xs font-bold uppercase ${
                          channelType === ct
                            ? 'bg-purple-600 text-white border-purple-500'
                            : 'bg-gray-900 text-gray-400 border-gray-800'
                        }`}
                      >
                        {ct}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Bypass All Confirmation Box */}
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-bold text-sm text-rose-300">Bypass All PB HERO Moderation</h4>
                    <p className="text-xs text-rose-400/80">
                      Disables all text/media filters and automated warnings, timeouts, kicks, and bans.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={bypassAll}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setConfirmBypassAll(true);
                      } else {
                        setBypassAll(false);
                      }
                    }}
                    className="w-5 h-5 accent-rose-500 rounded cursor-pointer"
                  />
                </div>
              </div>

              {/* Granular Rules Toggles */}
              {!bypassAll && (
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                    Granular Filter Bypass Permissions
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                    {[
                      { label: 'Link Filter', val: bypassLinks, set: setBypassLinks },
                      { label: 'Invite Filter', val: bypassInvites, set: setBypassInvites },
                      { label: 'Spam Filter', val: bypassSpam, set: setBypassSpam },
                      { label: 'Mention Filter', val: bypassMentions, set: setBypassMentions },
                      { label: 'Text Filter', val: bypassText, set: setBypassText },
                      { label: 'Keyword Filter', val: bypassKeywords, set: setBypassKeywords },
                      { label: 'Image Filter', val: bypassImages, set: setBypassImages },
                      { label: 'Video Filter', val: bypassVideos, set: setBypassVideos },
                      { label: 'File Filter', val: bypassFiles, set: setBypassFiles },
                      { label: 'Sticker Filter', val: bypassStickers, set: setBypassStickers },
                      { label: 'Warning System', val: bypassWarnings, set: setBypassWarnings },
                      { label: 'Auto Timeout', val: bypassTimeout, set: setBypassTimeout },
                      { label: 'Auto Kick', val: bypassKick, set: setBypassKick },
                      { label: 'Auto Ban', val: bypassBan, set: setBypassBan },
                    ].map((item) => (
                      <label
                        key={item.label}
                        className={`flex items-center gap-2 p-2.5 rounded-xl border cursor-pointer select-none transition-colors ${
                          item.val
                            ? 'bg-purple-950/40 border-purple-700 text-purple-200'
                            : 'bg-gray-900 border-gray-800 text-gray-400 hover:text-gray-300'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={item.val}
                          onChange={(e) => item.set(e.target.checked)}
                          className="w-4 h-4 accent-purple-600 rounded"
                        />
                        <span>{item.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2.5 text-xs font-semibold text-gray-400 hover:text-white rounded-xl transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl shadow-lg shadow-[#5865F2]/20 transition-all cursor-pointer"
                >
                  {editingExemption ? 'Save Changes' : 'Create Exemption'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirmation Modal for Bypass All */}
      {confirmBypassAll && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="bg-[#1c222d] border border-rose-500/40 rounded-2xl max-w-md w-full p-6 text-center shadow-2xl">
            <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto mb-3" />
            <h3 className="font-extrabold text-white text-lg">Confirm Complete Moderation Bypass</h3>
            <p className="text-xs text-gray-300 mt-2 leading-relaxed">
              Enabling <strong>Bypass All</strong> will skip every single PB HERO filter, warning, timeout, kick, and ban
              for this target. Discord role permissions and hierarchy will still apply.
            </p>
            <div className="flex items-center justify-center gap-3 mt-6">
              <button
                type="button"
                onClick={() => setConfirmBypassAll(false)}
                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-semibold rounded-xl"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setBypassAll(true);
                  setConfirmBypassAll(false);
                }}
                className="px-5 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-rose-600/30"
              >
                Yes, Enable Bypass All
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ExemptionsBypass;
