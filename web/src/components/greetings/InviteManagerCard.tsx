import React, { useState } from 'react';
import { ServerInviteSettings, GreetingChannelOption } from '../../types';
import { greetingsApi } from '../../api/greetings';
import { toast } from '../../hooks/useToast';
import { ConfirmModal } from '../ConfirmModal';
import {
  Link2,
  Copy,
  Check,
  RefreshCw,
  ShieldAlert,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  Sparkles,
} from 'lucide-react';

interface InviteManagerCardProps {
  invite?: ServerInviteSettings | null;
  channels: GreetingChannelOption[];
  onRefresh: () => void;
  welcomeChannelId?: string | null;
}

export const InviteManagerCard: React.FC<InviteManagerCardProps> = ({
  invite,
  channels,
  onRefresh,
  welcomeChannelId,
}) => {
  const [selectedChannelId, setSelectedChannelId] = useState<string>(
    invite?.invite_channel_id || welcomeChannelId || (channels[0]?.id ?? '')
  );
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [showRegenerateModal, setShowRegenerateModal] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async () => {
    if (!invite?.invite_url) return;
    try {
      await navigator.clipboard.writeText(invite.invite_url);
      setCopied(true);
      toast.success('Permanent invite link copied to clipboard!');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Failed to copy to clipboard.');
    }
  };

  const handleGenerate = async () => {
    setIsActionLoading(true);
    try {
      const res = await greetingsApi.generateInvite(selectedChannelId);
      if (res.is_permanent) {
        toast.success(`Generated permanent invite: ${res.invite_code}`);
      } else {
        toast.warning(`Discord assigned limited duration (limited) based on server rules.`);
      }
      onRefresh();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to generate invite');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleVerify = async () => {
    setIsActionLoading(true);
    try {
      const res = await greetingsApi.verifyInvite();
      if (res.is_permanent) {
        toast.success('Invite is active and permanent.');
      } else if (res.is_valid) {
        toast.warning('Invite is valid but has expiration.');
      } else {
        toast.error(`Invite is invalid: ${res.message}`);
      }
      onRefresh();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Verification request failed');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRegenerate = async () => {
    setShowRegenerateModal(false);
    setIsActionLoading(true);
    try {
      const res = await greetingsApi.regenerateInvite(selectedChannelId);
      toast.success(`Regenerated new invite: ${res.invite_code}`);
      onRefresh();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Regeneration failed');
    } finally {
      setIsActionLoading(false);
    }
  };

  const status = invite?.verification_status || 'not_generated';
  let badgeColor = 'bg-gray-800 text-gray-400 border-gray-700';
  let badgeText = 'NOT GENERATED';
  let StatusIcon = Clock;

  if (status === 'permanent_active') {
    badgeColor = 'bg-emerald-950/80 text-emerald-400 border-emerald-800';
    badgeText = 'PERMANENT & ACTIVE';
    StatusIcon = CheckCircle;
  } else if (status === 'active_expiring') {
    badgeColor = 'bg-amber-950/80 text-amber-400 border-amber-800';
    badgeText = 'ACTIVE BUT EXPIRING';
    StatusIcon = AlertTriangle;
  } else if (status === 'invalid' || status === 'unavailable') {
    badgeColor = 'bg-rose-950/80 text-rose-400 border-rose-800';
    badgeText = 'INVALID / UNAVAILABLE';
    StatusIcon = XCircle;
  }

  return (
    <div className="bg-gray-850 rounded-2xl border border-gray-800 shadow-xl overflow-hidden">
      <div className="p-6 border-b border-gray-800 flex flex-wrap items-center justify-between gap-4 bg-gray-900/60">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-500/10 rounded-xl border border-indigo-500/20 text-indigo-400">
            <Link2 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              Permanent Invite Manager
            </h2>
            <p className="text-xs text-gray-400">
              Reusable non-expiring invitation link for server onboarding and member farewells.
            </p>
          </div>
        </div>

        <div className={`px-3 py-1.5 rounded-full text-xs font-bold border flex items-center gap-1.5 shadow-sm ${badgeColor}`}>
          <StatusIcon className="w-4 h-4 shrink-0" />
          <span>{badgeText}</span>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Security Alert */}
        <div className="p-4 bg-amber-950/30 border border-amber-900/50 rounded-xl flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-xs text-amber-200/90 space-y-1">
            <p className="font-semibold text-amber-300">Invite Security Notice</p>
            <p>
              Anyone with this invite may be able to join the server. Keep this link private if you do not want uncontrolled public access. The URL is securely stored and only accessible to authenticated dashboard moderators.
            </p>
          </div>
        </div>

        {/* Channel & Controls */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
              Destination Channel
            </label>
            <select
              value={selectedChannelId}
              onChange={(e) => setSelectedChannelId(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
            >
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>
                  #{ch.name} ({ch.category}) {ch.can_send ? '✅' : '⚠️'}
                </option>
              ))}
            </select>
            <p className="text-[11px] text-gray-500">
              Channel where invited users will land upon joining.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
              Permanent Invite Link
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={invite?.invite_url || '[No invite generated yet]'}
                className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-gray-300 font-mono select-all focus:outline-none focus:border-indigo-500"
              />
              <button
                type="button"
                onClick={copyToClipboard}
                disabled={!invite?.invite_url}
                className="px-4 py-2.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-white rounded-xl text-sm font-medium border border-gray-700 flex items-center gap-1.5 transition-all shadow-sm shrink-0"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <p className="text-[11px] text-gray-500">
              Resolves in templates via the <code className="text-indigo-400">{'{invite_url}'}</code> variable.
            </p>
          </div>
        </div>

        {/* Telemetry metadata */}
        {invite && invite.invite_code && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-gray-900/40 p-4 rounded-xl border border-gray-800 text-xs">
            <div>
              <span className="text-gray-500 block">Invite Code</span>
              <span className="font-mono text-gray-300 font-medium">{invite.invite_code}</span>
            </div>
            <div>
              <span className="text-gray-500 block">Expiration</span>
              <span className="text-gray-300 font-medium">{invite.max_age === 0 ? 'Never (Permanent)' : `${invite.max_age} seconds`}</span>
            </div>
            <div>
              <span className="text-gray-500 block">Maximum Uses</span>
              <span className="text-gray-300 font-medium">{invite.max_uses === 0 ? 'Unlimited' : invite.max_uses}</span>
            </div>
            <div>
              <span className="text-gray-500 block">Last Verified</span>
              <span className="text-gray-300 font-medium">
                {invite.last_verified_at ? new Date(invite.last_verified_at).toLocaleTimeString() : 'Never'}
              </span>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-3 pt-2">
          {!invite?.invite_code ? (
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isActionLoading || !selectedChannelId}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-sm font-bold flex items-center gap-2 shadow-lg shadow-indigo-600/20 transition-all"
            >
              <Sparkles className="w-4 h-4" />
              Generate Permanent Invite
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={handleVerify}
                disabled={isActionLoading}
                className="px-4 py-2.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-white rounded-xl text-sm font-semibold border border-gray-700 flex items-center gap-2 transition-all shadow-sm"
              >
                <RefreshCw className={`w-4 h-4 ${isActionLoading ? 'animate-spin text-indigo-400' : ''}`} />
                Verify Invite
              </button>

              <button
                type="button"
                onClick={() => setShowRegenerateModal(true)}
                disabled={isActionLoading}
                className="px-4 py-2.5 bg-amber-950/40 hover:bg-amber-900/60 text-amber-300 rounded-xl text-sm font-semibold border border-amber-800/80 flex items-center gap-2 transition-all shadow-sm"
              >
                <RefreshCw className="w-4 h-4" />
                Regenerate Invite
              </button>
            </>
          )}
        </div>
      </div>

      <ConfirmModal
        isOpen={showRegenerateModal}
        title="Regenerate Server Permanent Invite?"
        message="The current invite link will be permanently replaced. Anyone who was using the old invite link may lose access through that link. Are you sure you want to create a new link?"
        confirmText="Yes, Regenerate Invite"
        isDangerous={true}
        onConfirm={handleRegenerate}
        onCancel={() => setShowRegenerateModal(false)}
      />
    </div>
  );
};


