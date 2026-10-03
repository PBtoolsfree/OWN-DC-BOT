import React, { useState, useEffect } from 'react';
import {
  Plus,
  Trash2,
  Edit2,
  CheckCircle2,
  AlertTriangle,
  Zap,
  Clock,
  MessageSquare,
  Link,
  AtSign,
  FileText,
  Repeat,
  Type,
  Activity,
  X,
} from 'lucide-react';
import { moderationApi } from '../api/moderation';
import { AutomodRule } from '../types';

export const AutomodRules: React.FC = () => {
  const [rules, setRules] = useState<AutomodRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AutomodRule | null>(null);

  // Form State
  const [ruleType, setRuleType] = useState('keyword_filter');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [scope, setScope] = useState('global');
  const [scopeId, setScopeId] = useState('');
  const [threshold, setThreshold] = useState(3);
  const [timeWindowSeconds, setTimeWindowSeconds] = useState(10);
  const [action, setAction] = useState('delete_warn');
  const [actionDuration, setActionDuration] = useState<number | undefined>(600);
  const [sendDm, setSendDm] = useState(true);
  const [logEvent, setLogEvent] = useState(true);
  const [cooldownSeconds, setCooldownSeconds] = useState(5);
  const [customKeywordsInput, setCustomKeywordsInput] = useState('');
  const [allowedInvitesInput, setAllowedInvitesInput] = useState('');

  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const rulesRes = await moderationApi.getAutomodRules();
      setRules(rulesRes);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load automod rules');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  const openCreateModal = () => {
    setEditingRule(null);
    setRuleType('keyword_filter');
    setName('Custom Keyword Filter');
    setDescription('Blocks prohibited terms and words');
    setEnabled(true);
    setScope('global');
    setScopeId('');
    setThreshold(1);
    setTimeWindowSeconds(5);
    setAction('delete_warn');
    setActionDuration(600);
    setSendDm(true);
    setLogEvent(true);
    setCooldownSeconds(3);
    setCustomKeywordsInput('badword, scam, free-nitro');
    setAllowedInvitesInput('');
    setModalOpen(true);
  };

  const openEditModal = (r: AutomodRule) => {
    setEditingRule(r);
    setRuleType(r.rule_type);
    setName(r.name);
    setDescription(r.description || '');
    setEnabled(r.enabled);
    setScope(r.scope);
    setScopeId(r.scope_id || '');
    setThreshold(r.threshold);
    setTimeWindowSeconds(r.time_window_seconds);
    setAction(r.action);
    setActionDuration(r.action_duration || 600);
    setSendDm(r.send_dm);
    setLogEvent(r.log_event);
    setCooldownSeconds(r.cooldown_seconds);
    setCustomKeywordsInput((r.custom_keywords || []).join(', '));
    setAllowedInvitesInput((r.allowed_invites || []).join(', '));
    setModalOpen(true);
  };

  const handleToggleRule = async (r: AutomodRule) => {
    try {
      await moderationApi.updateAutomodRule(r.id, { enabled: !r.enabled });
      setRules((prev) => prev.map((item) => (item.id === r.id ? { ...item, enabled: !item.enabled } : item)));
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to toggle automod rule');
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Rule name is required');
      return;
    }

    const keywords = customKeywordsInput
      ? customKeywordsInput
          .split(',')
          .map((k) => k.trim())
          .filter(Boolean)
      : [];
    const invites = allowedInvitesInput
      ? allowedInvitesInput
          .split(',')
          .map((i) => i.trim())
          .filter(Boolean)
      : [];

    const payload: Partial<AutomodRule> = {
      rule_type: ruleType,
      name: name.trim(),
      description: description.trim() || undefined,
      enabled,
      scope,
      scope_id: scopeId || undefined,
      threshold: Number(threshold),
      time_window_seconds: Number(timeWindowSeconds),
      action,
      action_duration: action.includes('timeout') ? Number(actionDuration) : undefined,
      send_dm: sendDm,
      log_event: logEvent,
      cooldown_seconds: Number(cooldownSeconds),
      custom_keywords: keywords,
      allowed_invites: invites,
    };

    try {
      if (editingRule) {
        await moderationApi.updateAutomodRule(editingRule.id, payload);
        setSuccessMsg('Automod rule updated successfully');
      } else {
        await moderationApi.createAutomodRule(payload);
        setSuccessMsg('Automod rule created successfully');
      }
      setModalOpen(false);
      fetchRules();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save automod rule');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this automod rule?')) return;
    try {
      await moderationApi.deleteAutomodRule(id);
      setSuccessMsg('Automod rule deleted');
      fetchRules();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to delete automod rule');
    }
  };

  const getRuleIcon = (type: string) => {
    switch (type) {
      case 'keyword_filter':
        return <FileText className="w-5 h-5 text-indigo-400" />;
      case 'invite_filter':
        return <Link className="w-5 h-5 text-rose-400" />;
      case 'link_filter':
        return <Link className="w-5 h-5 text-sky-400" />;
      case 'mention_spam':
        return <AtSign className="w-5 h-5 text-amber-400" />;
      case 'message_spam':
        return <MessageSquare className="w-5 h-5 text-emerald-400" />;
      case 'repeated_message':
        return <Repeat className="w-5 h-5 text-purple-400" />;
      case 'caps_spam':
        return <Type className="w-5 h-5 text-yellow-400" />;
      case 'flood_protection':
        return <Activity className="w-5 h-5 text-blue-400" />;
      default:
        return <Zap className="w-5 h-5 text-purple-400" />;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Zap className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-white tracking-wide">Automod Rules</h1>
              <p className="text-sm text-gray-400">
                Configure automated message scanning, thresholds, and triggered moderation actions
              </p>
            </div>
          </div>
        </div>
        <button
          onClick={openCreateModal}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white text-sm font-semibold rounded-xl shadow-lg shadow-[#5865F2]/20 transition-all cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>New Automod Rule</span>
        </button>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-[#1c222d] border border-gray-800">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">Total Rules</span>
          <span className="text-2xl font-black text-white mt-1 block">{rules.length}</span>
        </div>
        <div className="p-4 rounded-xl bg-[#1c222d] border border-gray-800">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">Active Rules</span>
          <span className="text-2xl font-black text-emerald-400 mt-1 block">
            {rules.filter((r) => r.enabled).length}
          </span>
        </div>
        <div className="p-4 rounded-xl bg-[#1c222d] border border-gray-800">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">Scope Coverage</span>
          <span className="text-2xl font-black text-indigo-400 mt-1 block">Guild-Wide</span>
        </div>
        <div className="p-4 rounded-xl bg-[#1c222d] border border-gray-800">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">Auto DM Notifications</span>
          <span className="text-2xl font-black text-purple-400 mt-1 block">Enabled</span>
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

      {/* Automod Rules Grid */}
      <div className="bg-[#1c222d] border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h3 className="font-bold text-white text-base">Active Moderation Interceptors</h3>
          <span className="text-xs text-gray-400">Evaluated in real-time on every message</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-gray-400">Loading automod rules...</div>
        ) : rules.length === 0 ? (
          <div className="p-12 text-center text-gray-400">No automod rules configured.</div>
        ) : (
          <div className="divide-y divide-gray-800">
            {rules.map((r) => (
              <div
                key={r.id}
                className={`p-4 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                  r.enabled ? 'hover:bg-gray-800/40' : 'bg-gray-950/40 opacity-70'
                }`}
              >
                <div className="flex items-start gap-3.5">
                  <div className="p-2.5 rounded-xl bg-gray-800 shrink-0 mt-0.5">{getRuleIcon(r.rule_type)}</div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-white text-base">{r.name}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          r.enabled
                            ? 'bg-emerald-900/40 text-emerald-300 border border-emerald-800'
                            : 'bg-gray-800 text-gray-400'
                        }`}
                      >
                        {r.enabled ? 'ACTIVE' : 'DISABLED'}
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-gray-800 text-gray-300 border border-gray-700">
                        Scope: {r.scope}
                      </span>
                    </div>
                    {r.description && <p className="text-xs text-gray-400 mt-1">{r.description}</p>}

                    {/* Rule specs */}
                    <div className="flex flex-wrap items-center gap-2.5 mt-2.5 text-xs text-gray-300">
                      <span className="px-2 py-1 rounded-lg bg-gray-900 border border-gray-800 flex items-center gap-1.5 font-mono">
                        <Clock className="w-3.5 h-3.5 text-gray-400" />
                        <span>Threshold: {r.threshold} in {r.time_window_seconds}s</span>
                      </span>
                      <span className="px-2 py-1 rounded-lg bg-indigo-950/40 border border-indigo-800/60 text-indigo-200 font-semibold uppercase">
                        Action: {r.action.replace('_', ' + ')}
                        {r.action.includes('timeout') && r.action_duration ? ` (${r.action_duration / 60}m)` : ''}
                      </span>
                      {r.send_dm && (
                        <span className="px-2 py-1 rounded-lg bg-purple-950/40 text-purple-200 border border-purple-800 text-[11px]">
                          DM Warning
                        </span>
                      )}
                      {r.log_event && (
                        <span className="px-2 py-1 rounded-lg bg-blue-950/40 text-blue-200 border border-blue-800 text-[11px]">
                          Logged
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2.5 self-end md:self-center">
                  <button
                    onClick={() => handleToggleRule(r)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                      r.enabled
                        ? 'bg-amber-500/10 text-amber-300 hover:bg-amber-500/20'
                        : 'bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                    }`}
                  >
                    {r.enabled ? 'Disable' : 'Enable'}
                  </button>
                  <button
                    onClick={() => openEditModal(r)}
                    className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors cursor-pointer"
                    title="Edit Rule"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(r.id)}
                    className="p-2 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition-colors cursor-pointer"
                    title="Delete Rule"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm overflow-y-auto">
          <div className="bg-[#1c222d] border border-gray-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl my-8">
            <div className="p-5 border-b border-gray-800 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-indigo-500/20 text-indigo-400">
                  <Zap className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-white text-lg">
                  {editingRule ? 'Edit Automod Rule' : 'Create Automod Rule'}
                </h3>
              </div>
              <button
                onClick={() => setModalOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSave} className="p-6 space-y-5">
              {/* Type and Name */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                    Rule Category
                  </label>
                  <select
                    value={ruleType}
                    onChange={(e) => setRuleType(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                  >
                    <option value="keyword_filter">Keyword Filter</option>
                    <option value="invite_filter">Invite Link Filter</option>
                    <option value="link_filter">General Link Filter</option>
                    <option value="mention_spam">Mention Spam Filter</option>
                    <option value="message_spam">Message Spam Filter</option>
                    <option value="repeated_message">Repeated Messages</option>
                    <option value="caps_spam">Caps & Character Spam</option>
                    <option value="flood_protection">Flood Protection</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                    Rule Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Excessive Mention Filter"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                  Description
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional brief explanation"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                />
              </div>

              {/* Threshold & Time Window */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                    Threshold (violations)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={threshold}
                    onChange={(e) => setThreshold(Number(e.target.value))}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm font-mono"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                    Time Window (seconds)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="3600"
                    value={timeWindowSeconds}
                    onChange={(e) => setTimeWindowSeconds(Number(e.target.value))}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm font-mono"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                    Cooldown (seconds)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="300"
                    value={cooldownSeconds}
                    onChange={(e) => setCooldownSeconds(Number(e.target.value))}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm font-mono"
                    required
                  />
                </div>
              </div>

              {/* Action Selector */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                    Automated Action
                  </label>
                  <select
                    value={action}
                    onChange={(e) => setAction(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                  >
                    <option value="delete">Delete Message</option>
                    <option value="warn">Warn Only</option>
                    <option value="delete_warn">Delete + Warn</option>
                    <option value="timeout">Timeout Member</option>
                    <option value="delete_timeout">Delete + Timeout</option>
                    <option value="kick">Kick Member</option>
                    <option value="ban">Ban Member</option>
                    <option value="log_only">Log Only (No Action)</option>
                  </select>
                </div>

                {action.includes('timeout') && (
                  <div>
                    <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                      Timeout Duration
                    </label>
                    <select
                      value={actionDuration}
                      onChange={(e) => setActionDuration(Number(e.target.value))}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm"
                    >
                      <option value={60}>1 Minute</option>
                      <option value={300}>5 Minutes</option>
                      <option value={600}>10 Minutes</option>
                      <option value={1800}>30 Minutes</option>
                      <option value={3600}>1 Hour</option>
                      <option value={21600}>6 Hours</option>
                      <option value={43200}>12 Hours</option>
                      <option value={86400}>1 Day</option>
                      <option value={604800}>7 Days</option>
                    </select>
                  </div>
                )}
              </div>

              {/* Keywords / Allowed Invites */}
              {ruleType === 'keyword_filter' && (
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                    Blocked Keywords (comma-separated)
                  </label>
                  <textarea
                    rows={2}
                    value={customKeywordsInput}
                    onChange={(e) => setCustomKeywordsInput(e.target.value)}
                    placeholder="scam, free nitro, hack, discount"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-xs font-mono"
                  />
                </div>
              )}

              {ruleType === 'invite_filter' && (
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                    Allowed Invite Codes / Discord Vanity URLs (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={allowedInvitesInput}
                    onChange={(e) => setAllowedInvitesInput(e.target.value)}
                    placeholder="my-community, discord.gg/partner"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white text-sm font-mono"
                  />
                </div>
              )}

              {/* Toggles */}
              <div className="flex flex-wrap items-center gap-4 pt-2">
                <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-gray-300">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(e) => setEnabled(e.target.checked)}
                    className="w-4 h-4 accent-[#5865F2] rounded"
                  />
                  <span>Enable Rule</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-gray-300">
                  <input
                    type="checkbox"
                    checked={sendDm}
                    onChange={(e) => setSendDm(e.target.checked)}
                    className="w-4 h-4 accent-[#5865F2] rounded"
                  />
                  <span>Send Direct Message (DM) to User</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-gray-300">
                  <input
                    type="checkbox"
                    checked={logEvent}
                    onChange={(e) => setLogEvent(e.target.checked)}
                    className="w-4 h-4 accent-[#5865F2] rounded"
                  />
                  <span>Log to Mod Log Channel & Dashboard</span>
                </label>
              </div>

              {/* Submit */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2.5 text-xs font-semibold text-gray-400 hover:text-white rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl shadow-lg shadow-[#5865F2]/20"
                >
                  {editingRule ? 'Save Changes' : 'Create Rule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AutomodRules;
