import React, { useState, useEffect } from 'react';
import { ChannelPolicy, DiscordChannel, PolicyProfile, PolicyValue } from '../types';
import { PermissionToggle } from './PermissionToggle';
import { Shield, Save, RotateCcw, Play, Check, X, Minus, Globe, Trash2 } from 'lucide-react';

interface ChannelPolicyEditorProps {
  channel: DiscordChannel;
  policy: ChannelPolicy | null;
  profiles: PolicyProfile[];
  onSave: (policyData: Partial<ChannelPolicy>) => Promise<void>;
  onDeletePolicy?: () => Promise<void>;
  onOpenSimulator: () => void;
}

export const ChannelPolicyEditor: React.FC<ChannelPolicyEditorProps> = ({
  channel,
  policy,
  profiles,
  onSave,
  onDeletePolicy,
  onOpenSimulator,
}) => {
  // Policy states
  const [allowText, setAllowText] = useState<PolicyValue>('inherit');
  const [allowLinks, setAllowLinks] = useState<PolicyValue>('inherit');
  const [allowImages, setAllowImages] = useState<PolicyValue>('inherit');
  const [allowVideos, setAllowVideos] = useState<PolicyValue>('inherit');
  const [allowFiles, setAllowFiles] = useState<PolicyValue>('inherit');
  const [allowStickers, setAllowStickers] = useState<PolicyValue>('inherit');
  const [allowEveryone, setAllowEveryone] = useState<PolicyValue>('inherit');
  const [allowHere, setAllowHere] = useState<PolicyValue>('inherit');
  const [allowRoleMentions, setAllowRoleMentions] = useState<PolicyValue>('inherit');
  const [allowUserMentions, setAllowUserMentions] = useState<PolicyValue>('inherit');

  // Rules and actions
  const [allowedDomains, setAllowedDomains] = useState<string>('');
  const [warningMessage, setWarningMessage] = useState<string>('');
  const [presetName, setPresetName] = useState<string>('CUSTOM');
  const [deleteViolations, setDeleteViolations] = useState<boolean>(true);
  const [warnOnViolation, setWarnOnViolation] = useState<boolean>(true);
  const [logViolations, setLogViolations] = useState<boolean>(true);
  const [enabled, setEnabled] = useState<boolean>(true);

  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Sync state when policy or channel changes
  useEffect(() => {
    if (policy) {
      setAllowText(policy.allow_text || 'inherit');
      setAllowLinks(policy.allow_links || 'inherit');
      setAllowImages(policy.allow_images || 'inherit');
      setAllowVideos(policy.allow_videos || 'inherit');
      setAllowFiles(policy.allow_files || 'inherit');
      setAllowStickers(policy.allow_stickers || 'inherit');
      setAllowEveryone(policy.allow_everyone || 'inherit');
      setAllowHere(policy.allow_here || 'inherit');
      setAllowRoleMentions(policy.allow_role_mentions || 'inherit');
      setAllowUserMentions(policy.allow_user_mentions || 'inherit');

      if (Array.isArray(policy.allowed_domains)) {
        setAllowedDomains(policy.allowed_domains.join(', '));
      } else if (typeof policy.allowed_domains === 'string') {
        setAllowedDomains(policy.allowed_domains);
      } else {
        setAllowedDomains('');
      }

      setWarningMessage(policy.warning_message || '');
      setPresetName(policy.preset_name || 'CUSTOM');
      setDeleteViolations(policy.delete_violations ?? true);
      setWarnOnViolation(policy.warn_on_violation ?? true);
      setLogViolations(policy.log_violations ?? true);
      setEnabled(policy.enabled ?? true);
    } else {
      // Default inherit
      setAllowText('inherit');
      setAllowLinks('inherit');
      setAllowImages('inherit');
      setAllowVideos('inherit');
      setAllowFiles('inherit');
      setAllowStickers('inherit');
      setAllowEveryone('inherit');
      setAllowHere('inherit');
      setAllowRoleMentions('inherit');
      setAllowUserMentions('inherit');
      setAllowedDomains('');
      setWarningMessage('');
      setPresetName('INHERITED');
      setDeleteViolations(true);
      setWarnOnViolation(true);
      setLogViolations(true);
      setEnabled(true);
    }
    setHasChanges(false);
  }, [channel.id, policy]);

  const handleApplyPreset = (profile: PolicyProfile) => {
    setAllowText(profile.allow_text);
    setAllowLinks(profile.allow_links);
    setAllowImages(profile.allow_images);
    setAllowVideos(profile.allow_videos);
    setAllowFiles(profile.allow_files);
    setAllowStickers(profile.allow_stickers);
    setAllowEveryone(profile.allow_everyone);
    setAllowHere(profile.allow_here);
    setAllowRoleMentions(profile.allow_role_mentions);
    setAllowUserMentions(profile.allow_user_mentions);
    setPresetName(profile.name);
    setHasChanges(true);
  };

  const handleDiscard = () => {
    if (policy) {
      setAllowText(policy.allow_text || 'inherit');
      setAllowLinks(policy.allow_links || 'inherit');
      setAllowImages(policy.allow_images || 'inherit');
      setAllowVideos(policy.allow_videos || 'inherit');
      setAllowFiles(policy.allow_files || 'inherit');
      setAllowStickers(policy.allow_stickers || 'inherit');
      setAllowEveryone(policy.allow_everyone || 'inherit');
      setAllowHere(policy.allow_here || 'inherit');
      setAllowRoleMentions(policy.allow_role_mentions || 'inherit');
      setAllowUserMentions(policy.allow_user_mentions || 'inherit');
      setAllowedDomains(Array.isArray(policy.allowed_domains) ? policy.allowed_domains.join(', ') : policy.allowed_domains || '');
      setWarningMessage(policy.warning_message || '');
      setPresetName(policy.preset_name || 'CUSTOM');
    }
    setHasChanges(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const parsedDomains = allowedDomains
        .split(',')
        .map((d) => d.trim())
        .filter(Boolean);

      await onSave({
        channel_name: channel.name,
        category_name: channel.category,
        channel_type: channel.type,
        allow_text: allowText,
        allow_links: allowLinks,
        allow_images: allowImages,
        allow_videos: allowVideos,
        allow_files: allowFiles,
        allow_stickers: allowStickers,
        allow_everyone: allowEveryone,
        allow_here: allowHere,
        allow_role_mentions: allowRoleMentions,
        allow_user_mentions: allowUserMentions,
        allowed_domains: parsedDomains,
        warning_message: warningMessage,
        preset_name: presetName,
        delete_violations: deleteViolations,
        warn_on_violation: warnOnViolation,
        log_violations: logViolations,
        enabled,
      });
      setHasChanges(false);
    } finally {
      setSaving(false);
    }
  };

  const renderSummaryBadge = (label: string, value: PolicyValue) => {
    let color = 'bg-gray-800 text-gray-400 border-gray-700';
    let icon = <Minus className="w-3 h-3" />;
    if (value === 'allow') {
      color = 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
      icon = <Check className="w-3 h-3" />;
    } else if (value === 'deny') {
      color = 'bg-rose-500/15 text-rose-400 border-rose-500/30';
      icon = <X className="w-3 h-3" />;
    }

    return (
      <span
        key={label}
        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-bold border ${color}`}
      >
        <span>{label}</span>
        {icon}
      </span>
    );
  };

  return (
    <div className="bg-[#151921] border border-gray-800 rounded-2xl shadow-xl overflow-hidden flex flex-col h-full">
      {/* Header bar */}
      <div className="p-6 border-b border-gray-800 bg-[#12161f] flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold text-white">#{channel.name}</span>
            <span className="text-xs text-gray-500 font-mono">({channel.id})</span>
            <span className="bg-[#5865F2]/20 text-[#5865F2] border border-[#5865F2]/30 px-2.5 py-0.5 rounded-full text-xs font-semibold">
              {presetName}
            </span>
          </div>
          <span className="text-xs text-gray-400 mt-1 block">
            Category: <strong className="text-gray-200">{channel.category || 'None'}</strong> • Type: <strong className="text-gray-200">{channel.type.toUpperCase()}</strong>
          </span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenSimulator}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-xl text-xs font-medium transition-colors shadow"
          >
            <Play className="w-3.5 h-3.5 text-amber-400" />
            <span>Policy Tester</span>
          </button>

          <button
            type="button"
            onClick={handleDiscard}
            disabled={!hasChanges || saving}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-gray-800/80 hover:bg-gray-800 text-gray-300 hover:text-white rounded-xl text-xs font-medium transition-colors disabled:opacity-40"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Discard</span>
          </button>

          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-5 py-2 bg-[#5865F2] hover:bg-[#4752c4] text-white rounded-xl text-xs font-semibold transition-all shadow disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{saving ? 'Saving...' : 'Save Changes'}</span>
          </button>
        </div>
      </div>

      {/* Main editor content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Visual Summary Box */}
        <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">
              Live Policy Rule Summary
            </span>
            <span className="text-[11px] text-gray-500">Auto updates while configuring</span>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {renderSummaryBadge('TEXT', allowText)}
            {renderSummaryBadge('IMAGE', allowImages)}
            {renderSummaryBadge('LINK', allowLinks)}
            {renderSummaryBadge('VIDEOS', allowVideos)}
            {renderSummaryBadge('FILES', allowFiles)}
            {renderSummaryBadge('MENTIONS', allowUserMentions)}
            {renderSummaryBadge('@EVERYONE', allowEveryone)}
          </div>
        </div>

        {/* Quick Presets Dropdown */}
        <div className="bg-[#12161f] border border-gray-800 rounded-xl p-4 flex items-center justify-between gap-4">
          <div>
            <span className="text-xs font-semibold text-white block">Load from Preset</span>
            <span className="text-[11px] text-gray-400">Quickly apply standard rule presets</span>
          </div>
          <div className="flex items-center gap-2">
            <select
              onChange={(e) => {
                const found = profiles.find((p) => p.name === e.target.value);
                if (found) handleApplyPreset(found);
              }}
              defaultValue=""
              className="bg-[#0B0E14] border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#5865F2]"
            >
              <option value="" disabled>
                Select preset to apply...
              </option>
              {profiles.map((p) => (
                <option key={p.id} value={p.name}>
                  {p.name.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Section: Message & Content Filtering */}
        <div className="space-y-3">
          <h4 className="text-xs font-bold text-[#5865F2] uppercase tracking-wider flex items-center gap-2">
            <Shield className="w-4 h-4" />
            <span>Message Content Filtering</span>
          </h4>

          <div className="bg-[#0B0E14] border border-gray-800 rounded-xl divide-y divide-gray-800/60 overflow-hidden">
            <PermissionToggle
              label="Allow Text Messages"
              description="Permit plain text conversations"
              value={allowText}
              onChange={(v) => {
                setAllowText(v);
                setHasChanges(true);
              }}
            />

            <PermissionToggle
              label="Allow Embedded Links (URLs)"
              description="Permit URLs and hyperlinks"
              value={allowLinks}
              onChange={(v) => {
                setAllowLinks(v);
                setHasChanges(true);
              }}
            />

            <PermissionToggle
              label="Allow Images"
              description="Permit JPEG, PNG, WEBP and GIF attachments"
              value={allowImages}
              onChange={(v) => {
                setAllowImages(v);
                setHasChanges(true);
              }}
            />

            <PermissionToggle
              label="Allow Videos"
              description="Permit MP4, MOV, WEBM video uploads"
              value={allowVideos}
              onChange={(v) => {
                setAllowVideos(v);
                setHasChanges(true);
              }}
            />

            <PermissionToggle
              label="Allow Files & Documents"
              description="Permit PDF, ZIP and generic binary attachments"
              value={allowFiles}
              onChange={(v) => {
                setAllowFiles(v);
                setHasChanges(true);
              }}
            />

            <PermissionToggle
              label="Allow Stickers & External Emojis"
              description="Permit Discord custom stickers and external emote usage"
              value={allowStickers}
              onChange={(v) => {
                setAllowStickers(v);
                setHasChanges(true);
              }}
            />
          </div>
        </div>

        {/* Section: Mentions */}
        <div className="space-y-3">
          <h4 className="text-xs font-bold text-[#5865F2] uppercase tracking-wider">
            Mentions & Pings
          </h4>

          <div className="bg-[#0B0E14] border border-gray-800 rounded-xl divide-y divide-gray-800/60 overflow-hidden">
            <PermissionToggle
              label="Allow @everyone"
              description="Permit server-wide announcement broadcast ping"
              value={allowEveryone}
              onChange={(v) => {
                setAllowEveryone(v);
                setHasChanges(true);
              }}
            />

            <PermissionToggle
              label="Allow @here"
              description="Permit active online members ping"
              value={allowHere}
              onChange={(v) => {
                setAllowHere(v);
                setHasChanges(true);
              }}
            />

            <PermissionToggle
              label="Allow Role Mentions"
              description="Permit pinging specific Discord roles"
              value={allowRoleMentions}
              onChange={(v) => {
                setAllowRoleMentions(v);
                setHasChanges(true);
              }}
            />

            <PermissionToggle
              label="Allow User Mentions"
              description="Permit direct @user pings"
              value={allowUserMentions}
              onChange={(v) => {
                setAllowUserMentions(v);
                setHasChanges(true);
              }}
            />
          </div>
        </div>

        {/* Section: Allowed Domains */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-gray-400" />
            <label className="text-xs font-semibold text-gray-300 block">
              Channel Allowed Domains (Link Exceptions)
            </label>
          </div>
          <input
            type="text"
            value={allowedDomains}
            onChange={(e) => {
              setAllowedDomains(e.target.value);
              setHasChanges(true);
            }}
            placeholder="youtube.com, github.com, twitter.com"
            className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-4 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2] font-mono"
          />
          <p className="text-[11px] text-gray-500">
            Comma-separated domains permitted even when link blocking is enabled.
          </p>
        </div>

        {/* Section: Warning Message & Violation Enforcement */}
        <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4 space-y-4">
          <span className="text-xs font-semibold text-gray-300 block uppercase tracking-wider">
            Violation Enforcement Actions
          </span>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={deleteViolations}
                onChange={(e) => {
                  setDeleteViolations(e.target.checked);
                  setHasChanges(true);
                }}
                className="rounded border-gray-700 text-[#5865F2] focus:ring-0"
              />
              <span>Delete Violating Message</span>
            </label>

            <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={warnOnViolation}
                onChange={(e) => {
                  setWarnOnViolation(e.target.checked);
                  setHasChanges(true);
                }}
                className="rounded border-gray-700 text-[#5865F2] focus:ring-0"
              />
              <span>Send DM Warning to User</span>
            </label>

            <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={logViolations}
                onChange={(e) => {
                  setLogViolations(e.target.checked);
                  setHasChanges(true);
                }}
                className="rounded border-gray-700 text-[#5865F2] focus:ring-0"
              />
              <span>Log Incident to Mod Channel</span>
            </label>
          </div>

          <div className="space-y-1.5 pt-2">
            <label className="text-xs text-gray-400 block">
              Custom Warning Message (Optional)
            </label>
            <input
              type="text"
              value={warningMessage}
              onChange={(e) => {
                setWarningMessage(e.target.value);
                setHasChanges(true);
              }}
              placeholder="Links are not permitted in this channel. Please review the rules."
              className="w-full bg-[#151921] border border-gray-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
            />
          </div>
        </div>

        {/* Delete Policy Button */}
        {policy && onDeletePolicy && (
          <div className="pt-4 border-t border-gray-800 flex justify-between items-center">
            <span className="text-xs text-gray-500">Reset channel back to default server inheritance</span>
            <button
              type="button"
              onClick={onDeletePolicy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors border border-rose-500/20"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Reset Policy</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
