import React from 'react';
import { ModerationCase } from '../types';
import { StatusBadge } from './StatusBadge';
import { formatDate } from '../utils/formatters';
import { Shield, ChevronLeft, ChevronRight, User } from 'lucide-react';

interface ModerationTableProps {
  cases: ModerationCase[];
  onSelectCase: (c: ModerationCase) => void;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export const ModerationTable: React.FC<ModerationTableProps> = ({
  cases,
  onSelectCase,
  currentPage,
  totalPages,
  onPageChange,
}) => {
  if (cases.length === 0) {
    return (
      <div className="py-12 text-center text-xs text-gray-500 bg-[#151921] rounded-xl border border-gray-800">
        No moderation cases match your filter criteria.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-xl border border-gray-800 bg-[#151921] shadow-lg">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-gray-800 bg-[#12161f] text-gray-400 uppercase font-semibold">
              <th className="py-3 px-4">Case #</th>
              <th className="py-3 px-4">Action</th>
              <th className="py-3 px-4">Target User</th>
              <th className="py-3 px-4">Moderator</th>
              <th className="py-3 px-4">Reason</th>
              <th className="py-3 px-4">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {cases.map((c) => (
              <tr
                key={c.case_number}
                onClick={() => onSelectCase(c)}
                className="hover:bg-gray-800/40 transition-colors cursor-pointer group"
              >
                <td className="py-3 px-4 font-mono font-bold text-white group-hover:text-[#5865F2]">
                  #{c.case_number}
                </td>
                <td className="py-3 px-4">
                  <StatusBadge status={c.action || 'info'} label={(c.action || 'UNKNOWN').toUpperCase()} />
                </td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-gray-500" />
                    <span className="font-semibold text-gray-200">{c.target_username}</span>
                  </div>
                </td>
                <td className="py-3 px-4 text-gray-400">
                  <div className="flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-[#5865F2]" />
                    <span>{c.moderator_username}</span>
                  </div>
                </td>
                <td className="py-3 px-4 text-gray-300 max-w-xs truncate">
                  {c.reason || 'No reason specified'}
                </td>
                <td className="py-3 px-4 text-gray-400 font-mono whitespace-nowrap">
                  {formatDate(c.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-2 text-xs text-gray-400">
          <span>
            Page <strong className="text-white">{currentPage}</strong> of{' '}
            <strong className="text-white">{totalPages}</strong>
          </span>

          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              className="p-1.5 rounded-lg border border-gray-800 hover:bg-gray-800 text-gray-400 hover:text-white disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className="p-1.5 rounded-lg border border-gray-800 hover:bg-gray-800 text-gray-400 hover:text-white disabled:opacity-40 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
