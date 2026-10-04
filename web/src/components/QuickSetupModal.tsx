import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  X,
  Plus,
  Edit2,
  Copy,
  Trash2,
  CheckCircle2,
  Shield,
  Sliders,
  Info,
  AlertTriangle,
} from 'lucide-react';
import { moderationApi } from '../api/moderation';
import { CustomStyleEditorModal, CustomStyleFormData } from './CustomStyleEditorModal';

interface QuickSetupModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (message: string) => void;
  onRefreshData?: () => void;
}

export const QuickSetupModal: React.FC<QuickSetupModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  onRefreshData,
}) => {
  const [selectedTab, setSelectedTab] = useState<'light' | 'balanced' | 'strict' | 'custom'>('balanced');
  const [quickStyles, setQuickStyles] = useState<Record<string, any>>({});
  const [customStyles, setCustomStyles] = useState<any[]>([]);
  const [activeStyle, setActiveStyle] = useState<string>('balanced');
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Custom editor modal
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingCustomStyle, setEditingCustomStyle] = useState<any | null>(null);

  // Confirmation modal
  const [confirmModalOpen, setConfirmModalOpen] = useState(false);
  const [styleToApply, setStyleToApply] = useState<any | null>(null);

  const fetchStyles = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await moderationApi.getQuickSetupPreview();
      setQuickStyles(res.styles || {});
      setCustomStyles(res.custom || []);
      if (res.active_style) setActiveStyle(res.active_style);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load moderation styles');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStyles();
      setSelectedTab('balanced');
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // Open apply confirmation
  const handleInitiateApply = (styleInfo: any) => {
    setStyleToApply(styleInfo);
    setConfirmModalOpen(true);
  };

  // Perform Apply
  const handleConfirmApply = async () => {
    if (!styleToApply) return;
    setApplying(true);
    setError(null);
    try {
      const targetId = styleToApply.id || styleToApply.style_id;
      const res = await moderationApi.applyQuickSetup(targetId);
      onSuccess(res?.message || `Successfully applied ${styleToApply.name || targetId} moderation style!`);
      setConfirmModalOpen(false);
      onClose();
      if (onRefreshData) onRefreshData();
    } catch (err: any) {
      const safeErr = err?.response?.data?.detail || err?.response?.data?.message || 'Failed to apply moderation style';
      setError(safeErr);
      setConfirmModalOpen(false);
    } finally {
      setApplying(false);
    }
  };

  // Handle Save Custom Style
  const handleSaveCustomStyle = async (formData: CustomStyleFormData, applyImmediately: boolean) => {
    if (editingCustomStyle && editingCustomStyle.id && !editingCustomStyle.is_builtin) {
      // Update
      const res = await moderationApi.updateCustomStyle(editingCustomStyle.id, formData);
      if (applyImmediately) {
        await moderationApi.applyQuickSetup(String(editingCustomStyle.id));
        onSuccess(`Updated and applied '${formData.name}' moderation style!`);
        onClose();
        if (onRefreshData) onRefreshData();
      } else {
        onSuccess(res.message || `Updated '${formData.name}' successfully!`);
        await fetchStyles();
      }
    } else {
      // Create
      const res = await moderationApi.createCustomStyle(formData);
      if (applyImmediately && res.style?.id) {
        await moderationApi.applyQuickSetup(String(res.style.id));
        onSuccess(`Created and applied '${formData.name}' moderation style!`);
        onClose();
        if (onRefreshData) onRefreshData();
      } else {
        onSuccess(res.message || `Created '${formData.name}' successfully!`);
        await fetchStyles();
      }
    }
    setEditorOpen(false);
    setEditingCustomStyle(null);
  };

  // Duplicate Custom or Built-in Style
  const handleDuplicate = async (styleId: string | number) => {
    try {
      const res = await moderationApi.duplicateCustomStyle(styleId);
      onSuccess(res.message || 'Style duplicated successfully');
      await fetchStyles();
      setSelectedTab('custom');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to duplicate style');
    }
  };

  // Delete Custom Style
  const handleDeleteCustom = async (styleId: string | number, name: string) => {
    if (!confirm(`Are you sure you want to delete custom style '${name}'?`)) return;
    try {
      await moderationApi.deleteCustomStyle(styleId);
      onSuccess(`Deleted custom style '${name}'`);
      await fetchStyles();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to delete custom style');
    }
  };

  const selectedBuiltinInfo = quickStyles[selectedTab];

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md overflow-y-auto">
        <div className="bg-[#181d26] border border-purple-500/30 rounded-2xl max-w-2xl w-full p-6 shadow-2xl my-6">
          {/* Header */}
          <div className="flex items-center justify-between pb-4 border-b border-gray-800">
            <div className="flex items-center gap-2.5">
              <Sparkles className="w-5 h-5 text-purple-400" />
              <div>
                <h3 className="font-extrabold text-white text-lg">Choose Moderation Style</h3>
                <p className="text-xs text-gray-400">
                  Easy Mode: Select a recommended moderation profile or build your own custom preset
                </p>
              </div>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-white p-1 rounded-lg">
              <X className="w-5 h-5" />
            </button>
          </div>

          {error && (
            <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* 4 Choices Grid (Tasks 2, 7, 18) */}
          <div className="py-5 space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {/* Light */}
              <button
                type="button"
                onClick={() => setSelectedTab('light')}
                className={`p-3 rounded-xl border text-left transition-all ${
                  selectedTab === 'light'
                    ? 'bg-purple-900/30 border-purple-500 text-white shadow-lg shadow-purple-500/10'
                    : 'bg-gray-900/60 border-gray-800 text-gray-400 hover:text-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="font-bold text-sm text-white">Light</div>
                  <span className="text-[10px] text-gray-400 font-mono">14d</span>
                </div>
                <div className="text-[11px] text-gray-400 mt-1 line-clamp-2">
                  More forgiving. Good for friendly communities.
                </div>
              </button>

              {/* Balanced */}
              <button
                type="button"
                onClick={() => setSelectedTab('balanced')}
                className={`p-3 rounded-xl border text-left transition-all relative ${
                  selectedTab === 'balanced'
                    ? 'bg-purple-900/30 border-purple-500 text-white shadow-lg shadow-purple-500/10'
                    : 'bg-gray-900/60 border-gray-800 text-gray-400 hover:text-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="font-bold text-sm text-white flex items-center gap-1">
                    Balanced
                  </div>
                  <span className="text-[10px] text-gray-400 font-mono">30d</span>
                </div>
                <div className="text-[11px] text-gray-400 mt-1 line-clamp-2">
                  Recommended balance between protection and user experience.
                </div>
                <span className="absolute -top-2 right-2 px-1.5 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-wider bg-purple-500 text-white shadow">
                  Rec
                </span>
              </button>

              {/* Strict */}
              <button
                type="button"
                onClick={() => setSelectedTab('strict')}
                className={`p-3 rounded-xl border text-left transition-all ${
                  selectedTab === 'strict'
                    ? 'bg-purple-900/30 border-purple-500 text-white shadow-lg shadow-purple-500/10'
                    : 'bg-gray-900/60 border-gray-800 text-gray-400 hover:text-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="font-bold text-sm text-white">Strict</div>
                  <span className="text-[10px] text-gray-400 font-mono">60d</span>
                </div>
                <div className="text-[11px] text-gray-400 mt-1 line-clamp-2">
                  Faster escalation for spam and repeated violations.
                </div>
              </button>

              {/* Custom */}
              <button
                type="button"
                onClick={() => setSelectedTab('custom')}
                className={`p-3 rounded-xl border text-left transition-all ${
                  selectedTab === 'custom'
                    ? 'bg-indigo-900/30 border-indigo-500 text-white shadow-lg shadow-indigo-500/10'
                    : 'bg-gray-900/60 border-gray-800 text-gray-400 hover:text-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="font-bold text-sm text-white flex items-center gap-1">
                    <Sliders className="w-3.5 h-3.5 text-indigo-400" />
                    Custom
                  </div>
                  <span className="text-[10px] text-indigo-300 font-mono">
                    {customStyles.length} saved
                  </span>
                </div>
                <div className="text-[11px] text-gray-400 mt-1 line-clamp-2">
                  Build your own warning decay and punishment ladder.
                </div>
              </button>
            </div>

            {/* Warning Decay Notice (Task 6) */}
            <div className="p-3 rounded-xl bg-gray-900/80 border border-gray-800 text-gray-300 text-xs flex items-start gap-2">
              <Info className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
              <span>
                Preset changes the default decay for future warnings. Existing warnings keep their current expiry.
              </span>
            </div>

            {/* TAB CONTENT: Built-in Styles (Light, Balanced, Strict) */}
            {selectedTab !== 'custom' && selectedBuiltinInfo && (
              <div className="p-4 rounded-xl bg-gray-900/90 border border-gray-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-bold text-purple-300 uppercase tracking-wide flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-purple-400" />
                    What will change? (Preview)
                  </div>
                  <div className="text-xs text-gray-400 font-mono">
                    Decay: <span className="text-white font-bold">{selectedBuiltinInfo.decay_days} days</span>
                  </div>
                </div>

                <p className="text-xs text-gray-300">{selectedBuiltinInfo.description}</p>

                <div className="space-y-1.5 pt-1">
                  <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
                    Escalation Ladder:
                  </span>
                  <ul className="text-xs text-gray-300 space-y-1 pl-2">
                    {selectedBuiltinInfo.actions?.map((act: string, i: number) => (
                      <li key={i} className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
                        <span>{act}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* TAB CONTENT: Custom Styles (Tasks 7, 8, 10) */}
            {selectedTab === 'custom' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-gray-200 uppercase tracking-wider">
                    Saved Custom Styles ({customStyles.length})
                  </h4>
                  <button
                    type="button"
                    onClick={() => {
                      setEditingCustomStyle(null);
                      setEditorOpen(true);
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold rounded-lg shadow transition-all cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Create Custom Style
                  </button>
                </div>

                {customStyles.length === 0 ? (
                  <div className="p-6 rounded-xl bg-gray-900/50 border border-dashed border-gray-800 text-center space-y-2">
                    <Sliders className="w-8 h-8 text-gray-600 mx-auto" />
                    <p className="text-xs text-gray-400">No custom moderation styles created yet.</p>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingCustomStyle(null);
                        setEditorOpen(true);
                      }}
                      className="px-3.5 py-1.5 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 text-xs font-semibold rounded-lg border border-indigo-500/30 cursor-pointer"
                    >
                      Build your first custom style
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-[36vh] overflow-y-auto pr-1">
                    {customStyles.map((cs) => (
                      <div
                        key={cs.id}
                        className="p-3.5 rounded-xl bg-gray-900/80 border border-gray-800 hover:border-gray-700 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm text-white">{cs.name}</span>
                            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-gray-800 text-gray-300">
                              {cs.allow_warning_expiration && cs.decay_days > 0
                                ? `${cs.decay_days}d decay`
                                : 'No decay'}
                            </span>
                            {String(activeStyle) === String(cs.id) && (
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                                Active
                              </span>
                            )}
                          </div>
                          {cs.description && (
                            <p className="text-xs text-gray-400">{cs.description}</p>
                          )}
                          <div className="text-[11px] text-gray-400 flex flex-wrap gap-1.5 pt-0.5">
                            {cs.actions?.slice(0, 3).map((act: string, idx: number) => (
                              <span key={idx} className="bg-gray-950 px-2 py-0.5 rounded text-gray-300">
                                {act}
                              </span>
                            ))}
                            {cs.actions?.length > 3 && (
                              <span className="text-gray-500 text-[10px] self-center">
                                +{cs.actions.length - 3} more
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Custom Style Buttons (Task 10) */}
                        <div className="flex items-center gap-1.5 shrink-0 self-end sm:self-center">
                          <button
                            type="button"
                            onClick={() => handleInitiateApply(cs)}
                            className="px-3 py-1 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold rounded-lg shadow transition-all cursor-pointer"
                          >
                            Apply
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setEditingCustomStyle(cs);
                              setEditorOpen(true);
                            }}
                            className="p-1.5 rounded-lg bg-gray-800 text-gray-300 hover:text-white hover:bg-gray-700"
                            title="Edit"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDuplicate(cs.id)}
                            className="p-1.5 rounded-lg bg-gray-800 text-gray-300 hover:text-white hover:bg-gray-700"
                            title="Duplicate"
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteCustom(cs.id, cs.name)}
                            className="p-1.5 rounded-lg bg-gray-800 text-gray-300 hover:text-rose-400 hover:bg-rose-500/10"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer Buttons */}
          <div className="flex items-center justify-between pt-4 border-t border-gray-800">
            <div className="text-[11px] text-gray-400 font-mono">
              Active Server Style: <span className="text-purple-300 font-bold uppercase">{activeStyle}</span>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-semibold text-gray-400 hover:text-white"
              >
                Close
              </button>
              {selectedTab !== 'custom' && selectedBuiltinInfo && (
                <button
                  type="button"
                  disabled={applying || loading}
                  onClick={() => handleInitiateApply(selectedBuiltinInfo)}
                  className="px-5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg transition-all cursor-pointer disabled:opacity-50"
                >
                  {applying ? 'Applying...' : 'Apply Moderation Style'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Confirmation Modal (Task 17) */}
      {confirmModalOpen && styleToApply && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
          <div className="bg-[#181d26] border border-purple-500/40 rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <div className="flex items-center gap-3 pb-3 border-b border-gray-800">
              <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
                <Shield className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-extrabold text-white text-base">
                  Apply {styleToApply.name || 'Selected'} Moderation?
                </h4>
                <p className="text-xs text-gray-400">
                  This will atomically update the server's warning decay and escalation ladder.
                </p>
              </div>
            </div>

            <div className="py-4 space-y-3">
              <div className="p-3.5 rounded-xl bg-gray-900/90 border border-gray-800 space-y-2">
                <div className="text-xs text-gray-300 flex items-center justify-between">
                  <span className="font-semibold text-white">Warning Decay:</span>
                  <span className="font-mono text-purple-300 font-bold">
                    {styleToApply.decay_days ? `${styleToApply.decay_days} days` : 'Disabled'}
                  </span>
                </div>

                <div className="text-xs text-gray-300">
                  <span className="font-semibold text-white block mb-1">Escalation Ladder:</span>
                  <ul className="text-[11px] text-gray-300 space-y-1 list-disc list-inside max-h-36 overflow-y-auto">
                    {styleToApply.actions?.map((act: string, i: number) => (
                      <li key={i}>{act}</li>
                    ))}
                  </ul>
                </div>
              </div>

              <p className="text-[11px] text-gray-400 italic">
                * Existing warnings keep their current expiry. Historical cases and warnings are never deleted.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-800">
              <button
                type="button"
                disabled={applying}
                onClick={() => setConfirmModalOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-gray-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={applying}
                onClick={handleConfirmApply}
                className="px-5 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-lg transition-all cursor-pointer disabled:opacity-50"
              >
                {applying ? 'Applying...' : 'Apply Style'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Custom Style Editor Modal (Task 7) */}
      <CustomStyleEditorModal
        isOpen={editorOpen}
        initialStyle={editingCustomStyle}
        onClose={() => {
          setEditorOpen(false);
          setEditingCustomStyle(null);
        }}
        onSave={handleSaveCustomStyle}
      />
    </>
  );
};
