import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  Plus,
  Trash2,
  Edit2,
  UserCheck,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  X,
  Search,
} from 'lucide-react';
import { moderationApi } from '../api/moderation';
import { WarningRecord, WarningEscalationRule } from '../types';

export const WarningsActions: React.FC = () => {
  const [warnings, setWarnings] = useState<WarningRecord[]>([]);
  const [escalationRules, setEscalationRules] = useState<WarningEscalationRule[]>([]);
  const [stats, setStats] = useState<{ active_warnings: number; warnings_today: number; decay_days: number; mode: string }>({
    active_warnings: 0,
    warnings_today: 0,
    decay_days: 30,
    mode: 'count',
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Search filter
  const [userSearch, setUserSearch] = useState('');
  const [activeOnly, setActiveOnly] = useState(true);

  // Quick Setup Modal
  const [quickSetupOpen, setQuickSetupOpen] = useState(false);
  const [quickStyles, setQuickStyles] = useState<Record<string, any>>({});
  const [selectedStyle, setSelectedStyle] = useState<string>('balanced');
  const [applyingStyle, setApplyingStyle] = useState(false);

  // Manual Issue Warning Modal
  const [manualWarnOpen, setManualWarnOpen] = useState(false);
  const [warnUserId, setWarnUserId] = useState('');
  const [warnUsername, setWarnUsername] = useState('');
  const [warnReason, setWarnReason] = useState('');
  const [warnSeverity, setWarnSeverity] = useState('medium');
  const [warnPoints, setWarnPoints] = useState(1);

  // Escalation Rule Edit/Create Modal
  const [ladderModalOpen, setLadderModalOpen] = useState(false);
  const [editingLadderRule, setEditingLadderRule] = useState<WarningEscalationRule | null>(null);
  const [ladderThreshold, setLadderThreshold] = useState(1);
  const [ladderMode, setLadderMode] = useState<'count' | 'points'>('count');
  const [ladderAction, setLadderAction] = useState<'warn' | 'timeout' | 'kick' | 'ban'>('warn');
  const [ladderDuration, setLadderDuration] = useState<number | undefined>(600);
  const [ladderSendDm, setLadderSendDm] = useState(true);
  const [ladderHistoryDays, setLadderHistoryDays] = useState(0);
  const [ladderReasonTemplate, setLadderReasonTemplate] = useState('');

  const fetchData = useCallback(async (searchOverride?: string) => {
    setLoading(true);
    setError(null);
    try {
      const q = typeof searchOverride === 'string' ? searchOverride : userSearch;
      const [warnsRes, escRes, statsRes] = await Promise.all([
        moderationApi.getWarnings({ active_only: activeOnly, user_id: q || undefined }),
        moderationApi.getEscalationRules(),
        moderationApi.getWarningsStats(),
      ]);
      setWarnings(warnsRes);
      setEscalationRules(escRes.sort((a, b) => a.threshold - b.threshold));
      setStats(statsRes);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load warnings data');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeOnly]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchData();
  };

  const handleOpenQuickSetup = async () => {
    try {
      const res = await moderationApi.getQuickSetupPreview();
      setQuickStyles(res.styles);
      setSelectedStyle('balanced');
      setQuickSetupOpen(true);
    } catch (err: any) {
      setError('Failed to load Quick Setup preview');
    }
  };

  const handleApplyQuickSetup = async () => {
    setApplyingStyle(true);
    try {
      await moderationApi.applyQuickSetup(selectedStyle);
      setSuccessMsg(`Successfully applied ${selectedStyle.toUpperCase()} moderation style!`);
      setQuickSetupOpen(false);
      fetchData();
      setTimeout(() => setSuccessMsg(null), 3500);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to apply style');
    } finally {
      setApplyingStyle(false);
    }
  };

  const handleRevokeWarning = async (warningId: string) => {
    if (!confirm(`Revoke warning ${warningId}?`)) return;
    try {
      await moderationApi.revokeWarning(warningId, 'Revoked manually by moderator');
      setSuccessMsg(`Warning ${warningId} revoked`);
      fetchData();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to revoke warning');
    }
  };

  const handleClearUser = async (userId: string, username: string) => {
    if (!confirm(`Clear all active warnings for ${username} (ID: ${userId})?`)) return;
    try {
      const res = await moderationApi.clearUserWarnings(userId);
      setSuccessMsg(`Cleared ${res.cleared_count} active warnings for ${username}`);
      fetchData();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to clear user warnings');
    }
  };

  const handleManualWarnSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!warnUserId.trim() || !warnReason.trim()) {
      setError('User ID and reason are required');
      return;
    }
    try {
      const res = await moderationApi.issueWarning({
        user_id: warnUserId.trim(),
        username: warnUsername.trim() || undefined,
        reason: warnReason.trim(),
        severity: warnSeverity,
        points: Number(warnPoints),
      });
      setSuccessMsg(`Warning issued successfully (${res.warning_id})`);
      setManualWarnOpen(false);
      setWarnUserId('');
      setWarnUsername('');
      setWarnReason('');
      fetchData();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to issue warning');
    }
  };

  const openLadderModal = (rule?: WarningEscalationRule) => {
    if (rule) {
      setEditingLadderRule(rule);
      setLadderThreshold(rule.threshold);
      setLadderMode(rule.mode);
      setLadderAction(rule.action);
      setLadderDuration(rule.duration || 600);
      setLadderSendDm(rule.send_dm);
      setLadderHistoryDays(rule.delete_message_history_days || 0);
      setLadderReasonTemplate(rule.reason_template || '');
    } else {
      setEditingLadderRule(null);
      const nextThreshold = escalationRules.length > 0 ? Math.max(...escalationRules.map((r) => r.threshold)) + 1 : 1;
      setLadderThreshold(nextThreshold);
      setLadderMode('count');
      setLadderAction('timeout');
      setLadderDuration(600);
      setLadderSendDm(true);
      setLadderHistoryDays(0);
      setLadderReasonTemplate('');
    }
    setLadderModalOpen(true);
  };

  const handleLadderSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: Partial<WarningEscalationRule> = {
      threshold: Number(ladderThreshold),
      mode: ladderMode,
      action: ladderAction,
      duration: ladderAction === 'timeout' ? Number(ladderDuration) : undefined,
      send_dm: ladderSendDm,
      delete_message_history_days: ladderAction === 'ban' ? Number(ladderHistoryDays) : 0,
      reason_template: ladderReasonTemplate.trim() || undefined,
    };

    try {
      if (editingLadderRule) {
        await moderationApi.updateEscalationRule(editingLadderRule.id, payload);
        setSuccessMsg('Escalation ladder updated');
      } else {
        await moderationApi.createEscalationRule(payload);
        setSuccessMsg('Escalation step created');
      }
      setLadderModalOpen(false);
      fetchData();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save escalation step');
    }
  };

  const handleLadderDelete = async (id: number) => {
    if (!confirm('Delete this step from escalation ladder?')) return;
    try {
      await moderationApi.deleteEscalationRule(id);
      setSuccessMsg('Step removed');
      fetchData();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to remove step');
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-white tracking-wide">Warnings & Actions</h1>
              <p className="text-sm text-gray-400">
                Automated strike escalation ladder, decay policies, and member infractions
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleOpenQuickSetup}
            className="inline-flex items-center gap-2 px-3.5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-purple-600/20 transition-all cursor-pointer"
          >
            <Sparkles className="w-4 h-4" />
            <span>Quick Setup (Easy Mode)</span>
          </button>
          <button
            onClick={() => setManualWarnOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl shadow-lg shadow-[#5865F2]/20 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Issue Warning</span>
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-[#1c222d] border border-gray-800">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">Active Warnings</span>
          <span className="text-2xl font-black text-amber-400 mt-1 block">{stats.active_warnings}</span>
        </div>
        <div className="p-4 rounded-xl bg-[#1c222d] border border-gray-800">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">Warnings Today</span>
          <span className="text-2xl font-black text-white mt-1 block">{stats.warnings_today}</span>
        </div>
        <div className="p-4 rounded-xl bg-[#1c222d] border border-gray-800">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">Warning Decay</span>
          <span className="text-2xl font-black text-indigo-400 mt-1 block">
            {stats.decay_days === 0 ? 'Never Expire' : `${stats.decay_days} Days`}
          </span>
        </div>
        <div className="p-4 rounded-xl bg-[#1c222d] border border-gray-800">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">Escalation Mode</span>
          <span className="text-2xl font-black text-emerald-400 mt-1 block uppercase">
            {stats.mode === 'points' ? 'Point Mode' : 'Count Mode'}
          </span>
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

      {/* Escalation Ladder Section */}
      <div className="bg-[#1c222d] border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-5 border-b border-gray-800 flex items-center justify-between">
          <div>
            <h3 className="font-bold text-white text-base">Progressive Escalation Ladder</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Determines what automated punishment triggers when a user accumulates strikes or severity points
            </p>
          </div>
          <button
            onClick={() => openLadderModal()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-semibold rounded-lg transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Step</span>
          </button>
        </div>

        <div className="divide-y divide-gray-800">
          {escalationRules.map((r) => (
            <div key={r.id} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-gray-800/30 transition-colors">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-[#5865F2]/10 border border-[#5865F2]/20 flex items-center justify-center font-black text-[#5865F2] text-sm shrink-0">
                  #{r.threshold}
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-extrabold text-white text-base">
                      {r.threshold} {r.mode === 'points' ? 'Points' : 'Violations'}
                    </span>
                    <ArrowRight className="w-4 h-4 text-gray-500" />
                    <span
                      className={`px-2.5 py-0.5 rounded text-xs font-extrabold uppercase tracking-wider ${
                        r.action === 'warn'
                          ? 'bg-amber-900/40 text-amber-300 border border-amber-800'
                          : r.action === 'timeout'
                          ? 'bg-indigo-900/40 text-indigo-300 border border-indigo-800'
                          : r.action === 'kick'
                          ? 'bg-orange-900/40 text-orange-300 border border-orange-800'
                          : 'bg-rose-900/40 text-rose-300 border border-rose-800'
                      }`}
                    >
                      {r.action}
                      {r.action === 'timeout' && r.duration ? ` (${r.duration >= 3600 ? `${r.duration / 3600}h` : `${r.duration / 60}m`})` : ''}
                    </span>
                    {r.send_dm && (
                      <span className="px-2 py-0.5 rounded bg-gray-800 text-gray-300 text-[10px] font-bold">
                        + DM Warning
                      </span>
                    )}
                    {r.action === 'ban' && r.delete_message_history_days ? (
                      <span className="px-2 py-0.5 rounded bg-rose-950 text-rose-300 text-[10px] font-bold">
                        Delete {r.delete_message_history_days}d history
                      </span>
                    ) : null}
                  </div>
                  {r.reason_template && (
                    <span className="text-xs text-gray-400 block mt-1 italic">
                      "{r.reason_template}"
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 self-end md:self-center">
                <button
                  onClick={() => openLadderModal(r)}
                  className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors cursor-pointer"
                  title="Edit Step"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleLadderDelete(r.id)}
                  className="p-2 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition-colors cursor-pointer"
                  title="Delete Step"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Warning Records Table */}
      <div className="bg-[#1c222d] border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-4 border-b border-gray-800 flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <h3 className="font-bold text-white text-base">Infraction Records</h3>
            <span className="text-xs text-gray-400">Live warnings stored with auto-decay expiration</span>
          </div>

          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
            <div className="relative">
              <input
                type="text"
                value={userSearch}
                onChange={(e) => setUserSearch(e.target.value)}
                placeholder="Search User ID..."
                className="pl-8 pr-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs text-white focus:outline-none focus:border-[#5865F2]"
              />
              <Search className="w-3.5 h-3.5 text-gray-500 absolute left-2.5 top-2.5" />
            </div>
            <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={activeOnly}
                onChange={(e) => setActiveOnly(e.target.checked)}
                className="w-3.5 h-3.5 accent-[#5865F2] rounded"
              />
              <span>Active Only</span>
            </label>
            <button
              type="submit"
              className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-xs text-white font-semibold rounded-lg"
            >
              Filter
            </button>
          </form>
        </div>

        {loading ? (
          <div className="p-12 text-center text-gray-400">Loading warnings...</div>
        ) : warnings.length === 0 ? (
          <div className="p-12 text-center">
            <UserCheck className="w-12 h-12 text-emerald-500 mx-auto mb-2" />
            <h4 className="text-base font-semibold text-gray-300">Clean Server Record</h4>
            <p className="text-xs text-gray-500 mt-1">No warnings match the selected filter</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-gray-300">
              <thead className="bg-gray-900/60 text-gray-400 uppercase font-mono text-[10px] tracking-wider border-b border-gray-800">
                <tr>
                  <th className="p-3.5">ID / Case</th>
                  <th className="p-3.5">User</th>
                  <th className="p-3.5">Rule / Reason</th>
                  <th className="p-3.5">Severity</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5">Issued</th>
                  <th className="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {warnings.map((w) => (
                  <tr key={w.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="p-3.5 font-mono text-gray-400">
                      <div className="font-bold text-white">{w.warning_id}</div>
                      <div className="text-[10px]">{w.case_id}</div>
                    </td>
                    <td className="p-3.5">
                      <div className="font-bold text-white">{w.username}</div>
                      <div className="text-[10px] text-gray-500 font-mono">ID: {w.user_id}</div>
                    </td>
                    <td className="p-3.5 max-w-xs">
                      <div className="font-semibold text-gray-200">{w.rule}</div>
                      <div className="text-[11px] text-gray-400 truncate">{w.reason}</div>
                    </td>
                    <td className="p-3.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          w.severity === 'critical'
                            ? 'bg-rose-900/40 text-rose-300'
                            : w.severity === 'high'
                            ? 'bg-orange-900/40 text-orange-300'
                            : w.severity === 'medium'
                            ? 'bg-amber-900/40 text-amber-300'
                            : 'bg-blue-900/40 text-blue-300'
                        }`}
                      >
                        {w.severity} ({w.points}pt)
                      </span>
                    </td>
                    <td className="p-3.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          w.status === 'active'
                            ? 'bg-emerald-900/40 text-emerald-300 border border-emerald-800'
                            : w.status === 'revoked'
                            ? 'bg-gray-800 text-gray-400'
                            : 'bg-yellow-900/40 text-yellow-300'
                        }`}
                      >
                        {w.status}
                      </span>
                    </td>
                    <td className="p-3.5 text-gray-400 font-mono text-[11px]">
                      {w.created_at ? new Date(w.created_at).toLocaleDateString() : 'N/A'}
                    </td>
                    <td className="p-3.5 text-right space-x-1.5 whitespace-nowrap">
                      {w.status === 'active' && (
                        <>
                          <button
                            onClick={() => handleRevokeWarning(w.warning_id)}
                            className="px-2.5 py-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 rounded font-semibold transition-colors cursor-pointer"
                            title="Revoke this warning"
                          >
                            Revoke
                          </button>
                          <button
                            onClick={() => handleClearUser(w.user_id, w.username)}
                            className="px-2.5 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded font-semibold transition-colors cursor-pointer"
                            title="Clear all warnings for user"
                          >
                            Clear All
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Quick Setup Modal */}
      {quickSetupOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="bg-[#1c222d] border border-purple-500/30 rounded-2xl max-w-xl w-full p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-gray-800">
              <div className="flex items-center gap-2.5">
                <Sparkles className="w-5 h-5 text-purple-400" />
                <h3 className="font-extrabold text-white text-lg">Choose Moderation Style (Easy Mode)</h3>
              </div>
              <button onClick={() => setQuickSetupOpen(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="py-5 space-y-4">
              <p className="text-xs text-gray-300">
                Select a recommended moderation profile. Applying a style will configure the strike escalation ladder and warning decay duration:
              </p>

              <div className="grid grid-cols-3 gap-3">
                {Object.entries(quickStyles).map(([key, info]: [string, any]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setSelectedStyle(key)}
                    className={`p-3.5 rounded-xl border text-left transition-all ${
                      selectedStyle === key
                        ? 'bg-purple-900/30 border-purple-500 text-white shadow-lg'
                        : 'bg-gray-900/50 border-gray-800 text-gray-400 hover:text-white'
                    }`}
                  >
                    <div className="font-bold text-sm text-white">{info.name}</div>
                    <div className="text-[11px] text-gray-400 mt-1">{info.decay_days}d decay</div>
                  </button>
                ))}
              </div>

              {/* Preview of Selected Style */}
              {quickStyles[selectedStyle] && (
                <div className="p-4 rounded-xl bg-gray-900/80 border border-gray-800 space-y-2">
                  <div className="text-xs font-bold text-purple-300 uppercase tracking-wide">
                    What will change? (Preview)
                  </div>
                  <p className="text-xs text-gray-300">{quickStyles[selectedStyle].description}</p>
                  <ul className="text-xs text-gray-400 space-y-1 mt-2 list-disc list-inside">
                    {quickStyles[selectedStyle].actions.map((act: string, i: number) => (
                      <li key={i}>{act}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800">
              <button
                type="button"
                onClick={() => setQuickSetupOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-gray-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={applyingStyle}
                onClick={handleApplyQuickSetup}
                className="px-5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg"
              >
                {applyingStyle ? 'Applying...' : 'Apply Moderation Style'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Issue Warning Modal */}
      {manualWarnOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-[#1c222d] border border-gray-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-gray-800">
              <h3 className="font-bold text-white text-lg">Issue Warning to Member</h3>
              <button onClick={() => setManualWarnOpen(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleManualWarnSubmit} className="py-4 space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                  Target Discord User ID
                </label>
                <input
                  type="text"
                  value={warnUserId}
                  onChange={(e) => setWarnUserId(e.target.value)}
                  placeholder="e.g. 123456789012345678"
                  className="w-full px-3.5 py-2 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm font-mono"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                  Username (Optional)
                </label>
                <input
                  type="text"
                  value={warnUsername}
                  onChange={(e) => setWarnUsername(e.target.value)}
                  placeholder="e.g. MemberName"
                  className="w-full px-3.5 py-2 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                  Reason for Warning
                </label>
                <textarea
                  rows={3}
                  value={warnReason}
                  onChange={(e) => setWarnReason(e.target.value)}
                  placeholder="Disruptive behavior in chat..."
                  className="w-full px-3.5 py-2 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                    Severity
                  </label>
                  <select
                    value={warnSeverity}
                    onChange={(e) => setWarnSeverity(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                  >
                    <option value="low">Low (1 pt)</option>
                    <option value="medium">Medium (2 pts)</option>
                    <option value="high">High (3 pts)</option>
                    <option value="critical">Critical (4 pts)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                    Strike Points
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={warnPoints}
                    onChange={(e) => setWarnPoints(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm font-mono"
                    required
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800">
                <button
                  type="button"
                  onClick={() => setManualWarnOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-gray-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl shadow-lg"
                >
                  Issue Warning
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Escalation Ladder Step Modal */}
      {ladderModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-[#1c222d] border border-gray-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-gray-800">
              <h3 className="font-bold text-white text-lg">
                {editingLadderRule ? 'Edit Escalation Step' : 'New Escalation Step'}
              </h3>
              <button onClick={() => setLadderModalOpen(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleLadderSave} className="py-4 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                    Threshold
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={ladderThreshold}
                    onChange={(e) => setLadderThreshold(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm font-mono"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                    Metric Mode
                  </label>
                  <select
                    value={ladderMode}
                    onChange={(e) => setLadderMode(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                  >
                    <option value="count">Violation Count</option>
                    <option value="points">Severity Points</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                  Punishment Action
                </label>
                <select
                  value={ladderAction}
                  onChange={(e) => setLadderAction(e.target.value as any)}
                  className="w-full px-3 py-2 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                >
                  <option value="warn">Warning Only</option>
                  <option value="timeout">Timeout Member</option>
                  <option value="kick">Kick from Server</option>
                  <option value="ban">Ban from Server</option>
                </select>
              </div>

              {ladderAction === 'timeout' && (
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                    Timeout Duration
                  </label>
                  <select
                    value={ladderDuration}
                    onChange={(e) => setLadderDuration(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                  >
                    <option value={60}>1 Minute</option>
                    <option value={300}>5 Minutes</option>
                    <option value={600}>10 Minutes</option>
                    <option value={1800}>30 Minutes</option>
                    <option value={3600}>1 Hour</option>
                    <option value={21600}>6 Hours</option>
                    <option value={43200}>12 Hours</option>
                    <option value={86400}>1 Day</option>
                    <option value={259200}>3 Days</option>
                    <option value={604800}>7 Days</option>
                  </select>
                </div>
              )}

              {ladderAction === 'ban' && (
                <div className="space-y-3">
                  <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 flex items-start gap-2.5">
                    <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-rose-200 uppercase font-bold block">⚠️ Danger: Automatic Server Ban</strong>
                      <span>Members reaching {ladderThreshold} {ladderMode === 'count' ? 'violations' : 'points'} will be permanently banned from the server.</span>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                      Delete Message History (Days)
                    </label>
                    <select
                      value={ladderHistoryDays}
                      onChange={(e) => setLadderHistoryDays(Number(e.target.value))}
                      className="w-full px-3 py-2 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                    >
                      <option value={0}>Don't delete messages</option>
                      <option value={1}>Previous 24 Hours</option>
                      <option value={7}>Previous 7 Days</option>
                    </select>
                  </div>
                </div>
              )}

              {ladderAction === 'kick' && (
                <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <strong className="text-amber-200 uppercase font-bold block">⚠️ High-Impact: Server Kick</strong>
                    <span>Members reaching {ladderThreshold} {ladderMode === 'count' ? 'violations' : 'points'} will be kicked from the server.</span>
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">
                  Reason Template
                </label>
                <input
                  type="text"
                  value={ladderReasonTemplate}
                  onChange={(e) => setLadderReasonTemplate(e.target.value)}
                  placeholder="e.g. Automated timeout for repeated rule violations"
                  className="w-full px-3.5 py-2 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                />
              </div>

              <div className="pt-2">
                <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-gray-300">
                  <input
                    type="checkbox"
                    checked={ladderSendDm}
                    onChange={(e) => setLadderSendDm(e.target.checked)}
                    className="w-4 h-4 accent-[#5865F2] rounded"
                  />
                  <span>Send direct message notification to user before action</span>
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800">
                <button
                  type="button"
                  onClick={() => setLadderModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-gray-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl shadow-lg"
                >
                  {editingLadderRule ? 'Save Changes' : 'Create Step'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default WarningsActions;
