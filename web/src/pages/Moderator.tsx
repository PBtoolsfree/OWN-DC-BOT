import { useEffect, useState } from 'react';
import { moderationApi } from '../api/moderation';
import { ModerationCase, BlockedMessage } from '../types';
import { StatCard } from '../components/StatCard';
import { ModerationTable } from '../components/ModerationTable';
import { CaseDetailsModal } from '../components/CaseDetailsModal';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { toast } from '../hooks/useToast';
import {
  Shield,
  ShieldAlert,
  AlertTriangle,
  Clock,
  UserX,
  Trash2,
} from 'lucide-react';

export default function Moderator() {
  const [loading, setLoading] = useState(true);
  const [cases, setCases] = useState<ModerationCase[]>([]);
  const [blocked, setBlocked] = useState<BlockedMessage[]>([]);
  const [selectedCase, setSelectedCase] = useState<ModerationCase | null>(null);

  // Pagination for cases
  const [page, setPage] = useState(1);
  const pageSize = 10;

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [casesData, blockedData] = await Promise.all([
          moderationApi.getCases(100),
          moderationApi.getBlocked(100),
        ]);
        setCases(casesData);
        setBlocked(blockedData);
      } catch (err: any) {
        toast.error(err.message || 'Failed to load moderation data');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-gray-800 animate-pulse rounded" />
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  // Count actions today
  const today = new Date().toDateString();
  const casesToday = cases.filter((c) => new Date(c.created_at).toDateString() === today);
  const warningsCount = casesToday.filter((c) => c.action.toLowerCase() === 'warn').length;
  const timeoutsCount = casesToday.filter((c) => c.action.toLowerCase() === 'timeout').length;
  const bansCount = casesToday.filter((c) => c.action.toLowerCase() === 'ban').length;
  const blockedTodayCount = blocked.filter((b) => new Date(b.created_at).toDateString() === today).length;
  const deletedCount = blockedTodayCount + casesToday.filter((c) => c.action.toLowerCase() === 'delete').length;

  const totalPages = Math.ceil(cases.length / pageSize) || 1;
  const paginatedCases = cases.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
          <Shield className="w-7 h-7 text-[#5865F2]" />
          <span>Moderator Telemetry & Enforcement</span>
        </h1>
        <p className="text-xs text-gray-400 mt-1">
          Server-level rule enforcement, automated message interception, and case audit records.
        </p>
      </div>

      {/* Row 1: Key Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard
          title="BLOCKED TODAY"
          value={blockedTodayCount}
          icon={ShieldAlert}
          iconColor="text-rose-400"
          subtitle="Policy violations"
        />

        <StatCard
          title="WARNINGS TODAY"
          value={warningsCount}
          icon={AlertTriangle}
          iconColor="text-amber-400"
          subtitle="Issued bot warnings"
        />

        <StatCard
          title="TIMEOUTS TODAY"
          value={timeoutsCount}
          icon={Clock}
          iconColor="text-indigo-400"
          subtitle="Timed out members"
        />

        <StatCard
          title="BANS TODAY"
          value={bansCount}
          icon={UserX}
          iconColor="text-red-500"
          subtitle="Banned accounts"
        />

        <StatCard
          title="DELETED MESSAGES"
          value={deletedCount}
          icon={Trash2}
          iconColor="text-gray-400"
          subtitle="Purged / Auto-removed"
        />
      </div>

      {/* Row 2: Recent Moderation Cases Table */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-gray-800 pb-3">
          <div>
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              Recent Moderation Cases
            </h2>
            <span className="text-xs text-gray-400">Click any row to view full incident dossier</span>
          </div>
          <span className="text-xs text-gray-500 font-mono">{cases.length} Total Cases</span>
        </div>

        <ModerationTable
          cases={paginatedCases}
          onSelectCase={(c) => setSelectedCase(c)}
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
        />
      </div>

      {/* Case Details Modal */}
      <CaseDetailsModal
        caseItem={selectedCase}
        onClose={() => setSelectedCase(null)}
      />
    </div>
  );
}
