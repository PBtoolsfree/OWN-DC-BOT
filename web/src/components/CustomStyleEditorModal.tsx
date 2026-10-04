import React, { useState, useEffect } from 'react';
import {
  X,
  Plus,
  Trash2,
  Sliders,
  ShieldAlert,
  Clock,
  CheckCircle2,
  Info,
} from 'lucide-react';

export interface EscalationStepItem {
  threshold: number;
  action: 'warn' | 'timeout' | 'kick' | 'ban';
  duration?: number | null; // in seconds
  send_dm: boolean;
  reason_template?: string;
}

export interface CustomStyleFormData {
  name: string;
  description: string;
  warning_decay_days: number;
  allow_warning_expiration: boolean;
  warning_mode: string;
  ladder: EscalationStepItem[];
}

interface CustomStyleEditorModalProps {
  isOpen: boolean;
  initialStyle?: any | null;
  onClose: () => void;
  onSave: (data: CustomStyleFormData, applyImmediately: boolean) => Promise<void>;
}

export const CustomStyleEditorModal: React.FC<CustomStyleEditorModalProps> = ({
  isOpen,
  initialStyle,
  onClose,
  onSave,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [warningDecayDays, setWarningDecayDays] = useState(30);
  const [allowWarningExpiration, setAllowWarningExpiration] = useState(true);
  const [warningMode, setWarningMode] = useState('count');
  const [ladder, setLadder] = useState<EscalationStepItem[]>([
    { threshold: 1, action: 'warn', duration: null, send_dm: true, reason_template: 'First warning' },
    { threshold: 2, action: 'warn', duration: null, send_dm: true, reason_template: 'Second warning' },
    { threshold: 3, action: 'timeout', duration: 600, send_dm: true, reason_template: '10-minute timeout' },
    { threshold: 5, action: 'kick', duration: null, send_dm: true, reason_template: 'Removed from server' },
    { threshold: 10, action: 'ban', duration: null, send_dm: true, reason_template: 'Permanently banned' },
  ]);
  const [saving, setSaving] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (initialStyle) {
      setName(initialStyle.name || '');
      setDescription(initialStyle.description || '');
      setWarningDecayDays(
        typeof initialStyle.decay_days === 'number'
          ? initialStyle.decay_days
          : typeof initialStyle.warning_decay_days === 'number'
          ? initialStyle.warning_decay_days
          : 30
      );
      setAllowWarningExpiration(
        initialStyle.allow_warning_expiration !== undefined ? initialStyle.allow_warning_expiration : true
      );
      setWarningMode(initialStyle.warning_mode || 'count');
      if (initialStyle.ladder && Array.isArray(initialStyle.ladder) && initialStyle.ladder.length > 0) {
        setLadder(
          initialStyle.ladder.map((s: any) => ({
            threshold: Number(s.threshold) || 1,
            action: s.action || 'warn',
            duration: s.duration !== undefined ? s.duration : (s.action === 'timeout' ? 600 : null),
            send_dm: s.send_dm !== false,
            reason_template: s.reason_template || '',
          }))
        );
      }
    } else {
      setName('');
      setDescription('');
      setWarningDecayDays(30);
      setAllowWarningExpiration(true);
      setWarningMode('count');
      setLadder([
        { threshold: 1, action: 'warn', duration: null, send_dm: true, reason_template: 'First warning' },
        { threshold: 2, action: 'warn', duration: null, send_dm: true, reason_template: 'Second warning' },
        { threshold: 3, action: 'timeout', duration: 600, send_dm: true, reason_template: '10-minute timeout' },
        { threshold: 5, action: 'kick', duration: null, send_dm: true, reason_template: 'Removed from server' },
        { threshold: 10, action: 'ban', duration: null, send_dm: true, reason_template: 'Permanently banned' },
      ]);
    }
    setValidationError(null);
  }, [initialStyle, isOpen]);

  if (!isOpen) return null;

  // Add Step
  const handleAddStep = () => {
    const lastThreshold = ladder.length > 0 ? ladder[ladder.length - 1].threshold : 0;
    const newThreshold = lastThreshold + 1;
    setLadder([
      ...ladder,
      {
        threshold: newThreshold,
        action: 'warn',
        duration: null,
        send_dm: true,
        reason_template: `Threshold ${newThreshold} reached`,
      },
    ]);
  };

  // Remove Step
  const handleRemoveStep = (index: number) => {
    if (ladder.length <= 1) {
      setValidationError('At least one escalation step is required.');
      return;
    }
    setLadder(ladder.filter((_, i) => i !== index));
  };

  // Update Step Field
  const handleUpdateStep = (index: number, field: keyof EscalationStepItem, value: any) => {
    const updated = [...ladder];
    updated[index] = { ...updated[index], [field]: value };
    if (field === 'action' && value !== 'timeout') {
      updated[index].duration = null;
    } else if (field === 'action' && value === 'timeout' && !updated[index].duration) {
      updated[index].duration = 600;
    }
    setLadder(updated);
  };

  // Validate form client-side before save
  const validateForm = (): boolean => {
    if (!name.trim()) {
      setValidationError('Style name is required.');
      return false;
    }
    if (['light', 'balanced', 'strict'].includes(name.trim().toLowerCase())) {
      setValidationError(`'${name.trim()}' is a protected built-in style name. Choose another name.`);
      return false;
    }
    if (allowWarningExpiration) {
      if (isNaN(warningDecayDays) || warningDecayDays < 1 || warningDecayDays > 365) {
        setValidationError('Warning decay must be between 1 and 365 days.');
        return false;
      }
    }
    if (!ladder || ladder.length === 0) {
      setValidationError('At least one escalation step is required.');
      return false;
    }

    let prevThreshold = 0;
    for (let i = 0; i < ladder.length; i++) {
      const step = ladder[i];
      if (isNaN(step.threshold) || step.threshold <= 0) {
        setValidationError(`Step ${i + 1}: Threshold must be a positive integer.`);
        return false;
      }
      if (step.threshold <= prevThreshold) {
        if (step.threshold === prevThreshold) {
          setValidationError(`Duplicate escalation threshold (${step.threshold} violations). Thresholds must be strictly increasing.`);
        } else {
          setValidationError(`Step ${i + 1}: Threshold (${step.threshold}) must be greater than previous threshold (${prevThreshold}).`);
        }
        return false;
      }
      prevThreshold = step.threshold;

      if (step.action === 'timeout') {
        const dur = Number(step.duration);
        if (isNaN(dur) || dur <= 0) {
          setValidationError(`Step ${i + 1}: Timeout action requires a positive duration.`);
          return false;
        }
      }
    }

    setValidationError(null);
    return true;
  };

  const handleSave = async (applyImmediately: boolean) => {
    if (!validateForm()) return;
    setSaving(true);
    try {
      await onSave(
        {
          name: name.trim(),
          description: description.trim(),
          warning_decay_days: allowWarningExpiration ? Number(warningDecayDays) : 0,
          allow_warning_expiration: allowWarningExpiration,
          warning_mode: warningMode,
          ladder: ladder.map((s) => ({
            threshold: Number(s.threshold),
            action: s.action,
            duration: s.action === 'timeout' ? Number(s.duration) : null,
            send_dm: Boolean(s.send_dm),
            reason_template: s.reason_template || `${s.threshold} violations reached: ${s.action.toUpperCase()}`,
          })),
        },
        applyImmediately
      );
      onClose();
    } catch (err: any) {
      setValidationError(err?.response?.data?.detail || err?.message || 'Failed to save custom style');
    } finally {
      setSaving(false);
    }
  };

  // Helper for formatting duration
  const formatDurationText = (seconds?: number | null) => {
    if (!seconds) return '';
    const mins = Math.floor(seconds / 60);
    if (mins >= 60) {
      const hrs = Math.floor(mins / 60);
      return `${hrs} hour${hrs > 1 ? 's' : ''}`;
    }
    return `${mins} minute${mins > 1 ? 's' : ''}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md overflow-y-auto">
      <div className="bg-[#181d26] border border-gray-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl my-8">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-800">
          <div className="flex items-center gap-2.5">
            <Sliders className="w-5 h-5 text-indigo-400" />
            <h3 className="font-extrabold text-white text-lg">
              {initialStyle ? 'Edit Custom Moderation Style' : 'Create Custom Moderation Style'}
            </h3>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white p-1 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        {validationError && (
          <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 shrink-0" />
            <span>{validationError}</span>
          </div>
        )}

        <div className="py-4 space-y-5 max-h-[68vh] overflow-y-auto pr-1">
          {/* Style Name & Description */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-gray-300 mb-1">
                Style Name <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. My Gaming Server"
                className="w-full bg-gray-900/80 border border-gray-700 rounded-xl px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-300 mb-1">Description</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief summary of moderation policy"
                className="w-full bg-gray-900/80 border border-gray-700 rounded-xl px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>

          {/* Warning Decay & Expiration */}
          <div className="p-4 rounded-xl bg-gray-900/60 border border-gray-800 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-amber-400" />
                  Allow Warning Expiration
                </span>
                <p className="text-[11px] text-gray-400">
                  When enabled, warnings automatically expire after the configured decay duration.
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={allowWarningExpiration}
                  onChange={(e) => setAllowWarningExpiration(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
              </label>
            </div>

            {allowWarningExpiration && (
              <div className="flex items-center gap-3 pt-2">
                <label className="text-xs text-gray-300 font-semibold whitespace-nowrap">
                  Warning Decay Duration:
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    max={365}
                    value={warningDecayDays}
                    onChange={(e) => setWarningDecayDays(Number(e.target.value))}
                    className="w-20 bg-gray-950 border border-gray-700 rounded-lg px-2.5 py-1 text-sm text-white text-center focus:outline-none focus:border-indigo-500"
                  />
                  <span className="text-xs text-gray-400">Days</span>
                </div>
              </div>
            )}

            <div className="flex items-center gap-2 pt-1">
              <span className="text-xs text-gray-400">Escalation Mode:</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                Count Mode
              </span>
            </div>
          </div>

          {/* Escalation Builder */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-bold text-gray-200 uppercase tracking-wider">
                Custom Escalation Ladder ({ladder.length} Steps)
              </label>
              <button
                type="button"
                onClick={handleAddStep}
                className="inline-flex items-center gap-1.5 px-3 py-1 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 text-xs font-semibold rounded-lg border border-indigo-500/30 transition-all cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Step
              </button>
            </div>

            <div className="space-y-2.5">
              {ladder.map((step, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-gray-900/80 border border-gray-800 flex flex-wrap items-center justify-between gap-3"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-gray-400 w-12">Step {idx + 1}:</span>
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-gray-300">After</span>
                      <input
                        type="number"
                        min={1}
                        max={100}
                        value={step.threshold}
                        onChange={(e) => handleUpdateStep(idx, 'threshold', Number(e.target.value))}
                        className="w-16 bg-gray-950 border border-gray-700 rounded-lg px-2 py-1 text-xs text-white text-center focus:outline-none focus:border-indigo-500"
                      />
                      <span className="text-xs text-gray-300">
                        {step.threshold === 1 ? 'violation' : 'violations'}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-gray-400">Action:</span>
                      <select
                        value={step.action}
                        onChange={(e) => handleUpdateStep(idx, 'action', e.target.value)}
                        className="bg-gray-950 border border-gray-700 rounded-lg px-2.5 py-1 text-xs text-white focus:outline-none focus:border-indigo-500"
                      >
                        <option value="warn">WARN</option>
                        <option value="timeout">TIMEOUT</option>
                        <option value="kick">KICK</option>
                        <option value="ban">BAN</option>
                      </select>
                    </div>

                    {step.action === 'timeout' && (
                      <div className="flex items-center gap-1.5">
                        <select
                          value={step.duration || 600}
                          onChange={(e) => handleUpdateStep(idx, 'duration', Number(e.target.value))}
                          className="bg-gray-950 border border-gray-700 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-indigo-500"
                        >
                          <option value={300}>5 minutes</option>
                          <option value={600}>10 minutes</option>
                          <option value={1800}>30 minutes</option>
                          <option value={3600}>1 hour</option>
                          <option value={21600}>6 hours</option>
                          <option value={86400}>24 hours</option>
                          <option value={604800}>7 days</option>
                        </select>
                      </div>
                    )}

                    <label className="flex items-center gap-1 text-[11px] text-gray-300 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={step.send_dm}
                        onChange={(e) => handleUpdateStep(idx, 'send_dm', e.target.checked)}
                        className="rounded border-gray-700 bg-gray-950 text-indigo-500 focus:ring-0"
                      />
                      Send DM
                    </label>

                    <button
                      type="button"
                      onClick={() => handleRemoveStep(idx)}
                      disabled={ladder.length <= 1}
                      className="p-1 text-gray-400 hover:text-rose-400 disabled:opacity-30 disabled:hover:text-gray-400"
                      title="Delete step"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Live Preview (Task 7) */}
          <div className="p-4 rounded-xl bg-gray-900/90 border border-indigo-500/20 space-y-2">
            <div className="text-xs font-bold text-indigo-300 uppercase tracking-wide flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />
              What will change? (Preview)
            </div>
            <div className="text-xs text-gray-300 flex items-center gap-2">
              <span className="font-semibold text-white">Warning Decay:</span>
              <span>
                {allowWarningExpiration ? `${warningDecayDays} days` : 'Disabled (Warnings never expire)'}
              </span>
            </div>
            <div className="text-xs text-gray-400 space-y-1 mt-1">
              <span className="font-semibold text-gray-300 block">Escalation Ladder:</span>
              <ul className="list-disc list-inside space-y-0.5 text-[11px] text-gray-300">
                {ladder.map((s, i) => (
                  <li key={i}>
                    {s.threshold} {s.threshold === 1 ? 'violation' : 'violations'} →{' '}
                    <span className="font-bold text-white uppercase">{s.action}</span>
                    {s.action === 'timeout' && s.duration ? ` (${formatDurationText(s.duration)})` : ''}
                    {s.send_dm ? ' + DM Warning' : ''}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px] flex items-start gap-2">
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              Preset changes the default decay for future warnings. Existing warnings keep their current expiry.
            </span>
          </div>
        </div>

        {/* Footer Buttons */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-800">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-gray-400 hover:text-white"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => handleSave(false)}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-xs font-bold rounded-xl border border-gray-700 transition-all cursor-pointer disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Style'}
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => handleSave(true)}
            className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold rounded-xl shadow-lg transition-all cursor-pointer disabled:opacity-50"
          >
            {saving ? 'Applying...' : 'Save & Apply Style'}
          </button>
        </div>
      </div>
    </div>
  );
};
