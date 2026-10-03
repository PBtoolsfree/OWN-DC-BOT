import { useEffect, useState } from 'react';
import { moderationApi } from '../api/moderation';
import { ModerationCase, ModerationOverviewStats } from '../types';
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
  TrendingUp,
  Activity,
} from 'lucide-react';

export default function Moderator() {
  const [loading, setLoading] = useState(true);
  const [cases, setCases] = useState<ModerationCase[]>([]);
  const [stats, setStats] = useState<ModerationOverviewStats | null>(null);
  const [selectedCase, setSelectedCase] = useState<ModerationCase | null>(null);

  // Pagination for cases
  const [page, setPage] = useState(1);
  const pageSize = 10;

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [statsData, casesData] = await Promise.all([
          moderationApi.getStats().catch(() => null),
          moderationApi.getCases({ limit: 100 }),
        ]);
        if (statsData) setStats(statsData);
        setCases(casesData);
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

  const totalPages = Math.ceil(cases.length / pageSize) || 1;
  const paginatedCases = cases.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="space-y-8 animate-fade-in max-w-7xl mx-auto pb-12">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
          <Shield className="w-7 h-7 text-[#5865F2]" />
          <span>Moderator Control Center Overview</span>
        </h1>
        <p className="text-xs text-gray-400 mt-1">
          Server-level rule telemetry, automated message interception, strike escalation, and real-time audit cases.
        </p>
      </div>

      {/* Row 1: Accurate Live Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3.5">
        <StatCard
          title="ACTIVE WARNINGS"
          value={stats?.active_warnings ?? 0}
          icon={AlertTriangle}
          iconColor="text-amber-400"
          subtitle="Non-expired strikes"
        />

        <StatCard
          title="WARNINGS TODAY"
          value={stats?.warnings_today ?? 0}
          icon={Activity}
          iconColor="text-yellow-400"
          subtitle="Bot & manual strikes"
        />

        <StatCard
          title="TIMEOUTS TODAY"
          value={stats?.timeouts_today ?? 0}
          icon={Clock}
          iconColor="text-indigo-400"
          subtitle="Auto & manual mutes"
        />

        <StatCard
          title="KICKS TODAY"
          value={stats?.kicks_today ?? 0}
          icon={UserX}
          iconColor="text-orange-400"
          subtitle="Kicked accounts"
        />

        <StatCard
          title="BANS TODAY"
          value={stats?.bans_today ?? 0}
          icon={ShieldAlert}
          iconColor="text-rose-500"
          subtitle="Banned accounts"
        />

        <StatCard
          title="BLOCKED TODAY"
          value={stats?.messages_blocked ?? 0}
          icon={Trash2}
          iconColor="text-gray-400"
          subtitle="Auto-removed messages"
        />
      </div>

      {/* Row 2: Top Violations Widget */}
      {stats?.top_violations && stats.top_violations.length > 0 && (
        <div className="bg-[#1c222d] border border-gray-800 rounded-2xl p-5 shadow-xl">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-purple-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Top Violation Reasons Today</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 md:grid-cols-5 gap-3">
            {stats.top_violations.map((v, i) => (
              <div key={i} className="p-3 rounded-xl bg-gray-900 border border-gray-800 flex flex-col justify-between">
                <span className="text-xs font-semibold text-gray-300 truncate" title={v.reason}>
                  {v.reason}
                </span>
                <span className="text-lg font-black text-purple-400 mt-2">{v.count} violations</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Row 3: Recent Moderation Cases Table */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-gray-800 pb-3">
          <div>
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              Recent Moderation Cases & Case IDs
            </h2>
            <span className="text-xs text-gray-400">Click any row to view full incident dossier</span>
          </div>
          <span className="text-xs text-gray-500 font-mono">{cases.length} Total Incidents</span>
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
