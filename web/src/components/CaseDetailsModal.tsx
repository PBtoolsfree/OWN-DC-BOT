import React from 'react';
import { ModerationCase } from '../types';
import { StatusBadge } from './StatusBadge';
import { formatDate } from '../utils/formatters';
import { X, ShieldAlert, User, Shield, Clock, Hash, AlertTriangle, Send, Bell } from 'lucide-react';

interface CaseDetailsModalProps {
  caseItem: ModerationCase | null;
  onClose: () => void;
}

export const CaseDetailsModal: React.FC<CaseDetailsModalProps> = ({ caseItem, onClose }) => {
  if (!caseItem) return null;

  const displayCaseId = caseItem.case_id || `CASE-${String(caseItem.case_number).padStart(4, '0')}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#151921] border border-gray-800 rounded-2xl max-w-lg w-full shadow-2xl overflow-hidden animate-scale-in max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-800 bg-[#12161f]">
          <div className="flex items-center gap-3">
            {caseItem.target_avatar_url ? (
              <img
                src={caseItem.target_avatar_url}
                alt="Avatar"
                className="w-10 h-10 rounded-full border border-gray-700 object-cover"
              />
            ) : (
              <div className="p-2.5 rounded-xl bg-[#5865F2]/10 text-[#5865F2]">
                <ShieldAlert className="w-5 h-5" />
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-extrabold text-white">{displayCaseId}</h3>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-400">
                  #{caseItem.case_number}
                </span>
              </div>
              <span className="text-xs text-gray-400">PB HERO Incident Investigation</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-gray-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4 overflow-y-auto flex-1 custom-scrollbar">
          {/* Action & Timestamp Top Cards */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-3">
              <span className="text-[11px] text-gray-500 font-semibold uppercase tracking-wider block mb-1">
                Action Taken
              </span>
              <StatusBadge status={caseItem.action} label={caseItem.action.toUpperCase()} />
            </div>

            <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-3">
              <span className="text-[11px] text-gray-500 font-semibold uppercase tracking-wider block mb-1">
                Timestamp
              </span>
              <div className="flex items-center gap-1.5 text-xs text-gray-200">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                <span>{formatDate(caseItem.created_at)}</span>
              </div>
            </div>
          </div>

          {/* User & Channel Info */}
          <div className="space-y-2">
            <div className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800">
              <div className="flex items-center gap-2.5">
                <User className="w-4 h-4 text-gray-400" />
                <span className="text-xs text-gray-400">Target Member</span>
              </div>
              <div className="text-right">
                <span className="text-xs font-bold text-white block">
                  {caseItem.target_username}
                </span>
                <span className="text-[10px] text-gray-500 font-mono">
                  ID: {caseItem.target_user_id}
                </span>
              </div>
            </div>

            {caseItem.channel_name && (
              <div className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800">
                <div className="flex items-center gap-2.5">
                  <Hash className="w-4 h-4 text-gray-400" />
                  <span className="text-xs text-gray-400">Channel</span>
                </div>
                <span className="text-xs font-mono font-semibold text-gray-200">
                  #{caseItem.channel_name}
                </span>
              </div>
            )}

            <div className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800">
              <div className="flex items-center gap-2.5">
                <Shield className="w-4 h-4 text-gray-400" />
                <span className="text-xs text-gray-400">Executor</span>
              </div>
              <div className="text-right">
                <span className="text-xs font-semibold text-white block">
                  {caseItem.executor || caseItem.moderator_username}
                </span>
              </div>
            </div>

            {caseItem.rule && (
              <div className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800">
                <span className="text-xs text-gray-400">Matched Rule / Policy</span>
                <span className="text-xs font-bold text-purple-300">
                  {caseItem.rule} {caseItem.policy_name ? `(${caseItem.policy_name})` : ''}
                </span>
              </div>
            )}

            {caseItem.warning_id && (
              <div className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span className="text-xs text-gray-400">Warning Strike ID</span>
                </div>
                <span className="text-xs font-mono font-bold text-amber-300">
                  {caseItem.warning_id}
                </span>
              </div>
            )}

            {caseItem.duration && (
              <div className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800">
                <span className="text-xs text-gray-400">Punishment Duration</span>
                <span className="text-xs font-medium text-amber-400 font-mono">
                  {caseItem.duration >= 3600 ? `${caseItem.duration / 3600}h` : `${caseItem.duration / 60}m`}
                </span>
              </div>
            )}
          </div>

          {/* Delivery Telemetry */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-[#0B0E14] border border-gray-800 flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-gray-400">
                <Send className="w-3.5 h-3.5" />
                <span>User DM</span>
              </div>
              <span
                className={`font-mono text-[10px] font-bold px-2 py-0.5 rounded ${
                  caseItem.dm_status === 'delivered'
                    ? 'bg-emerald-950 text-emerald-300'
                    : caseItem.dm_status === 'failed'
                    ? 'bg-rose-950 text-rose-300'
                    : 'bg-gray-800 text-gray-400'
                }`}
              >
                {caseItem.dm_status?.toUpperCase() || 'DISABLED'}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-[#0B0E14] border border-gray-800 flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-gray-400">
                <Bell className="w-3.5 h-3.5" />
                <span>Discord Embed</span>
              </div>
              <span
                className={`font-mono text-[10px] font-bold px-2 py-0.5 rounded ${
                  caseItem.discord_log_status === 'delivered'
                    ? 'bg-emerald-950 text-emerald-300'
                    : 'bg-gray-800 text-gray-400'
                }`}
              >
                {caseItem.discord_log_status?.toUpperCase() || 'LOGGED'}
              </span>
            </div>
          </div>

          {/* Reason / Incident Evidence */}
          <div className="space-y-1.5 bg-[#0B0E14] p-4 rounded-xl border border-gray-800">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
              Reason / Incident Evidence
            </span>
            <p className="text-xs text-gray-200 leading-relaxed whitespace-pre-wrap font-mono">
              {caseItem.reason || 'No specific reason provided.'}
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end p-4 border-t border-gray-800 bg-[#12161f]">
          <button
            onClick={onClose}
            className="px-5 py-2 text-xs font-bold text-white bg-gray-800 hover:bg-gray-700 rounded-xl transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
