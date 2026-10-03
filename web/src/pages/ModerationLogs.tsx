import { useEffect, useState } from 'react';
import { moderationApi } from '../api/moderation';
import { ModerationCase } from '../types';
import { ModerationTable } from '../components/ModerationTable';
import { CaseDetailsModal } from '../components/CaseDetailsModal';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { toast } from '../hooks/useToast';
import { ScrollText, Search, RotateCcw } from 'lucide-react';

export default function ModerationLogs() {
  const [loading, setLoading] = useState(true);
  const [cases, setCases] = useState<ModerationCase[]>([]);
  const [selectedCase, setSelectedCase] = useState<ModerationCase | null>(null);

  // Filters
  const [searchUser, setSearchUser] = useState('');
  const [filterAction, setFilterAction] = useState('all');
  const [filterModerator, setFilterModerator] = useState('all');

  // Pagination
  const [page, setPage] = useState(1);
  const pageSize = 12;

  const loadData = async () => {
    setLoading(true);
    try {
      const casesData = await moderationApi.getCases(200);
      setCases(casesData);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load moderation logs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-gray-800 animate-pulse rounded" />
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  // Filter cases
  const filteredCases = cases.filter((c) => {
    const matchesUser =
      !searchUser ||
      c.target_username.toLowerCase().includes(searchUser.toLowerCase()) ||
      c.target_user_id.includes(searchUser) ||
      (c.reason && c.reason.toLowerCase().includes(searchUser.toLowerCase()));

    const matchesAction =
      filterAction === 'all' || c.action.toLowerCase() === filterAction.toLowerCase();

    const matchesModerator =
      filterModerator === 'all' ||
      c.moderator_username.toLowerCase() === filterModerator.toLowerCase();

    return matchesUser && matchesAction && matchesModerator;
  });

  const totalPages = Math.ceil(filteredCases.length / pageSize) || 1;
  const paginatedCases = filteredCases.slice((page - 1) * pageSize, page * pageSize);

  // Collect unique moderators for filter dropdown
  const uniqueModerators = Array.from(new Set(cases.map((c) => c.moderator_username))).filter(Boolean);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
            <ScrollText className="w-7 h-7 text-[#5865F2]" />
            <span>Moderation Audit Logs</span>
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Searchable permanent record of all warnings, timeouts, kicks, bans, and policy violations.
          </p>
        </div>

        <button
          onClick={loadData}
          className="inline-flex items-center gap-2 px-3.5 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-xl text-xs font-semibold transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Refresh Logs</span>
        </button>
      </div>

      {/* Filter toolbar */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-4 shadow-lg grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="relative">
          <Search className="w-4 h-4 text-gray-500 absolute left-3.5 top-3" />
          <input
            type="text"
            value={searchUser}
            onChange={(e) => {
              setSearchUser(e.target.value);
              setPage(1);
            }}
            placeholder="Search by user, ID, or reason..."
            className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl pl-10 pr-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2]"
          />
        </div>

        <div className="relative">
          <select
            value={filterAction}
            onChange={(e) => {
              setFilterAction(e.target.value);
              setPage(1);
            }}
            className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
          >
            <option value="all">All Actions</option>
            <option value="warn">Warn</option>
            <option value="timeout">Timeout</option>
            <option value="kick">Kick</option>
            <option value="ban">Ban</option>
            <option value="delete">Delete</option>
            <option value="unban">Unban</option>
            <option value="blocked_link">Blocked Link</option>
            <option value="blocked_attachment">Blocked Attachment</option>
          </select>
        </div>

        <div className="relative">
          <select
            value={filterModerator}
            onChange={(e) => {
              setFilterModerator(e.target.value);
              setPage(1);
            }}
            className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
          >
            <option value="all">All Moderators</option>
            {uniqueModerators.map((mod) => (
              <option key={mod} value={mod}>
                {mod}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Table */}
      <ModerationTable
        cases={paginatedCases}
        onSelectCase={(c) => setSelectedCase(c)}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
      />

      {/* Case Details Drawer / Modal */}
      <CaseDetailsModal
        caseItem={selectedCase}
        onClose={() => setSelectedCase(null)}
      />
    </div>
  );
}
