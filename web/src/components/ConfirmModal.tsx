import React, { useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDangerous?: boolean;
  requiredTypedText?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  isDangerous = false,
  requiredTypedText,
  onConfirm,
  onCancel,
}) => {
  const [typedValue, setTypedValue] = useState('');

  if (!isOpen) return null;

  const isConfirmedAllowed = !requiredTypedText || typedValue === requiredTypedText;

  const handleConfirm = () => {
    if (isConfirmedAllowed) {
      setTypedValue('');
      onConfirm();
    }
  };

  const handleCancel = () => {
    setTypedValue('');
    onCancel();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#151921] border border-gray-800 rounded-2xl max-w-md w-full shadow-2xl overflow-hidden animate-scale-in">
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div className="flex items-center gap-2.5">
            {isDangerous && (
              <div className="p-1.5 rounded-lg bg-rose-500/10 text-rose-400">
                <AlertTriangle className="w-5 h-5" />
              </div>
            )}
            <h3 className="text-base font-semibold text-white">{title}</h3>
          </div>
          <button
            onClick={handleCancel}
            className="text-gray-400 hover:text-white transition-colors p-1 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <p className="text-sm text-gray-300 leading-relaxed">{message}</p>

          {requiredTypedText && (
            <div className="space-y-1.5 bg-[#0B0E14] p-3 rounded-lg border border-gray-800">
              <label className="text-xs text-gray-400 block">
                Type <span className="text-rose-400 font-mono font-semibold">{requiredTypedText}</span> to confirm:
              </label>
              <input
                type="text"
                value={typedValue}
                onChange={(e) => setTypedValue(e.target.value)}
                placeholder={requiredTypedText}
                className="w-full bg-[#151921] border border-gray-700 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-rose-500 font-mono"
              />
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 p-5 border-t border-gray-800 bg-[#12161f]">
          <button
            onClick={handleCancel}
            className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
          >
            {cancelText}
          </button>
          <button
            onClick={handleConfirm}
            disabled={!isConfirmedAllowed}
            className={`px-4 py-2 text-xs font-medium text-white rounded-lg transition-all shadow ${
              isDangerous
                ? 'bg-rose-600 hover:bg-rose-500 disabled:bg-rose-950 disabled:text-rose-800'
                : 'bg-[#5865F2] hover:bg-[#4752c4] disabled:bg-gray-800 disabled:text-gray-600'
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};
