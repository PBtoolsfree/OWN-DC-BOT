import React from 'react';
import { ModerationCase } from '../types';
import { StatusBadge } from './StatusBadge';
import { formatDate } from '../utils/formatters';
import { X, ShieldAlert, User, Shield, Clock } from 'lucide-react';

interface CaseDetailsModalProps {
  caseItem: ModerationCase | null;
  onClose: () => void;
}

export const CaseDetailsModal: React.FC<CaseDetailsModalProps> = ({ caseItem, onClose }) => {
  if (!caseItem) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#151921] border border-gray-800 rounded-2xl max-w-lg w-full shadow-2xl overflow-hidden animate-scale-in">
        <div className="flex items-center justify-between p-5 border-b border-gray-800 bg-[#12161f]">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-[#5865F2]/10 text-[#5865F2]">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Case #{caseItem.case_number}</h3>
              <span className="text-xs text-gray-400">Moderation Incident Details</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-gray-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-3.5">
              <span className="text-xs text-gray-400 block mb-1">Action</span>
              <StatusBadge status={caseItem.action} label={caseItem.action.toUpperCase()} />
            </div>

            <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-3.5">
              <span className="text-xs text-gray-400 block mb-1">Timestamp</span>
              <div className="flex items-center gap-1.5 text-xs text-gray-200">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                <span>{formatDate(caseItem.created_at)}</span>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded-lg bg-[#0B0E14] border border-gray-800">
              <div className="flex items-center gap-2.5">
                <User className="w-4 h-4 text-gray-400" />
                <span className="text-xs text-gray-400">Target User</span>
              </div>
              <div className="text-right">
                <span className="text-xs font-semibold text-white block">
                  {caseItem.target_username}
                </span>
                <span className="text-[10px] text-gray-500 font-mono">
                  {caseItem.target_user_id}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-[#0B0E14] border border-gray-800">
              <div className="flex items-center gap-2.5">
                <Shield className="w-4 h-4 text-gray-400" />
                <span className="text-xs text-gray-400">Moderator</span>
              </div>
              <div className="text-right">
                <span className="text-xs font-semibold text-white block">
                  {caseItem.moderator_username}
                </span>
                <span className="text-[10px] text-gray-500 font-mono">
                  {caseItem.moderator_user_id}
                </span>
              </div>
            </div>

            {caseItem.duration && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-[#0B0E14] border border-gray-800">
                <span className="text-xs text-gray-400">Duration</span>
                <span className="text-xs font-medium text-amber-400 font-mono">
                  {caseItem.duration}s
                </span>
              </div>
            )}
          </div>

          <div className="space-y-1.5 bg-[#0B0E14] p-4 rounded-xl border border-gray-800">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
              Reason / Evidence
            </span>
            <p className="text-xs text-gray-200 leading-relaxed whitespace-pre-wrap">
              {caseItem.reason || 'No specific reason provided.'}
            </p>
          </div>
        </div>

        <div className="flex justify-end p-5 border-t border-gray-800 bg-[#12161f]">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-white bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
