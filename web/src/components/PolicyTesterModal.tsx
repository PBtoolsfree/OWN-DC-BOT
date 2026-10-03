import React, { useState } from 'react';
import { DiscordChannel, DiscordRole, PolicySimulationResult } from '../types';
import { policiesApi } from '../api/policies';
import { Play, X, CheckCircle2, ShieldAlert, Loader2, Paperclip } from 'lucide-react';

interface PolicyTesterModalProps {
  isOpen: boolean;
  channels: DiscordChannel[];
  roles: DiscordRole[];
  initialChannelId?: string;
  onClose: () => void;
}

export const PolicyTesterModal: React.FC<PolicyTesterModalProps> = ({
  isOpen,
  channels,
  roles,
  initialChannelId,
  onClose,
}) => {
  const [channelId, setChannelId] = useState(initialChannelId || channels[0]?.id || '');
  const [selectedRoleId, setSelectedRoleId] = useState<string>('');
  const [sampleContent, setSampleContent] = useState('https://example.com');
  const [hasAttachment, setHasAttachment] = useState(false);
  const [attachmentType, setAttachmentType] = useState('image');

  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<PolicySimulationResult | null>(null);

  if (!isOpen) return null;

  const handleRunTest = async (e: React.FormEvent) => {
    e.preventDefault();
    setTesting(true);
    setResult(null);

    try {
      const res = await policiesApi.simulatePolicy({
        channel_id: channelId,
        content: sampleContent,
        role_ids: selectedRoleId ? [selectedRoleId] : [],
        has_attachment: hasAttachment,
        attachment_type: attachmentType,
      });
      setResult(res);
    } catch (err: any) {
      setResult({
        allowed: false,
        reason: err.message || 'Simulation execution failed.',
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#151921] border border-gray-800 rounded-2xl max-w-lg w-full shadow-2xl overflow-hidden animate-scale-in">
        <div className="flex items-center justify-between p-5 border-b border-gray-800 bg-[#12161f]">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
              <Play className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Policy Simulator</h3>
              <p className="text-xs text-gray-400">Test message scenarios against backend policy engine</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-gray-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleRunTest} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300 block">Target Channel</label>
              <select
                value={channelId}
                onChange={(e) => setChannelId(e.target.value)}
                className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
              >
                {channels.map((ch) => (
                  <option key={ch.id} value={ch.id}>
                    #{ch.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300 block">Simulated User Role</label>
              <select
                value={selectedRoleId}
                onChange={(e) => setSelectedRoleId(e.target.value)}
                className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
              >
                <option value="">Default Member (No roles)</option>
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    @{r.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-300 block">Sample Message Content</label>
            <textarea
              rows={3}
              value={sampleContent}
              onChange={(e) => setSampleContent(e.target.value)}
              placeholder="Type simulated message (e.g. check out https://example.com or @everyone hello)"
              className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl p-3 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2] font-mono leading-relaxed"
            />
          </div>

          {/* Quick presets */}
          <div className="flex flex-wrap gap-1.5 text-[11px]">
            <span className="text-gray-500 py-0.5">Quick fill:</span>
            <button
              type="button"
              onClick={() => { setSampleContent('Hello general chat, how is everyone doing today?'); setHasAttachment(false); }}
              className="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300"
            >
              Plain Text
            </button>
            <button
              type="button"
              onClick={() => { setSampleContent('https://youtube.com/watch?v=dQw4w9WgXcQ'); setHasAttachment(false); }}
              className="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-emerald-400 font-mono"
            >
              YouTube URL
            </button>
            <button
              type="button"
              onClick={() => { setSampleContent('Check out this link https://unauthorized-domain.com'); setHasAttachment(false); }}
              className="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-rose-400 font-mono"
            >
              Blocked URL
            </button>
            <button
              type="button"
              onClick={() => { setSampleContent('@everyone announcement ping'); setHasAttachment(false); }}
              className="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-amber-400 font-mono"
            >
              @everyone
            </button>
            <button
              type="button"
              onClick={() => { setSampleContent('@here urgent update'); setHasAttachment(false); }}
              className="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-amber-400 font-mono"
            >
              @here
            </button>
            <button
              type="button"
              onClick={() => { setSampleContent('<@&987654321> moderator ping'); setHasAttachment(false); }}
              className="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-indigo-400 font-mono"
            >
              Role Mention
            </button>
            <button
              type="button"
              onClick={() => { setSampleContent('<@!123456789> user ping'); setHasAttachment(false); }}
              className="px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-blue-400 font-mono"
            >
              User Mention
            </button>
          </div>

          {/* Attachment simulator */}
          <div className="bg-[#0B0E14] border border-gray-800 p-3 rounded-xl space-y-2">
            <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={hasAttachment}
                onChange={(e) => setHasAttachment(e.target.checked)}
                className="rounded border-gray-700 text-[#5865F2] focus:ring-0"
              />
              <span className="flex items-center gap-1.5">
                <Paperclip className="w-3.5 h-3.5 text-gray-400" />
                <span>Simulate Message Attachment</span>
              </span>
            </label>

            {hasAttachment && (
              <div className="flex items-center gap-3 pt-1 pl-6">
                <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer">
                  <input
                    type="radio"
                    name="att_type"
                    checked={attachmentType === 'image'}
                    onChange={() => setAttachmentType('image')}
                    className="text-[#5865F2]"
                  />
                  <span>Image (.png/.jpg)</span>
                </label>
                <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer">
                  <input
                    type="radio"
                    name="att_type"
                    checked={attachmentType === 'video'}
                    onChange={() => setAttachmentType('video')}
                    className="text-[#5865F2]"
                  />
                  <span>Video (.mp4/.mov)</span>
                </label>
                <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer">
                  <input
                    type="radio"
                    name="att_type"
                    checked={attachmentType === 'file'}
                    onChange={() => setAttachmentType('file')}
                    className="text-[#5865F2]"
                  />
                  <span>Document / File (.pdf/.zip)</span>
                </label>
              </div>
            )}
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={testing}
              className="inline-flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-[#5865F2] hover:bg-[#4752c4] rounded-xl transition-all shadow disabled:opacity-50"
            >
              {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
              <span>{testing ? 'Simulating...' : 'Test Policy'}</span>
            </button>
          </div>
        </form>

        {/* Results banner */}
        {result && (
          <div className="p-5 border-t border-gray-800 bg-[#0B0E14] animate-fade-in">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-2">
              Simulator Verdict
            </span>
            <div
              className={`p-4 rounded-xl border flex items-start gap-3 ${
                result.allowed
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              }`}
            >
              {result.allowed ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              )}
              <div className="space-y-1.5 flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold block">
                    {result.allowed ? 'ALLOW' : 'DENY'}
                  </span>
                  {(result as any).effective_value && (
                    <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold uppercase bg-gray-800 text-gray-300">
                      EFFECTIVE: {(result as any).effective_value}
                    </span>
                  )}
                </div>
                <p className="text-xs leading-relaxed text-gray-200">{result.reason}</p>
                <div className="flex flex-wrap gap-3 pt-1 text-[11px] text-gray-400 font-mono">
                  {((result as any).matched_policy || (result as any).preset_name) && (
                    <span>Policy: <strong className="text-white">{(result as any).matched_policy || (result as any).preset_name}</strong></span>
                  )}
                  {((result as any).matched_rule || result.rule) && (
                    <span>Rule: <strong className="text-white">{(result as any).matched_rule || result.rule}</strong></span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
