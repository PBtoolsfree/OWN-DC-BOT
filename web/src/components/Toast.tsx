import React from 'react';
import { useToastStore } from '../hooks/useToast';
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from 'lucide-react';
import { ToastType } from '../types';

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  const getIcon = (type: ToastType) => {
    switch (type) {
      case 'success':
        return <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />;
      case 'info':
      default:
        return <Info className="w-5 h-5 text-sky-400 shrink-0" />;
    }
  };

  const getBorderColor = (type: ToastType) => {
    switch (type) {
      case 'success':
        return 'border-emerald-500/40 bg-[#121c17]';
      case 'error':
        return 'border-rose-500/40 bg-[#1c1214]';
      case 'warning':
        return 'border-amber-500/40 bg-[#1c1812]';
      case 'info':
      default:
        return 'border-sky-500/40 bg-[#12181c]';
    }
  };

  return (
    <div className="fixed top-5 right-5 z-50 flex flex-col space-y-3 max-w-sm w-full pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl border shadow-2xl backdrop-blur-md transition-all duration-300 transform translate-y-0 ${getBorderColor(
            t.type
          )}`}
          role="alert"
        >
          {getIcon(t.type)}
          <div className="flex-1 min-w-0">
            {t.title && <h4 className="text-sm font-semibold text-white mb-0.5">{t.title}</h4>}
            <p className="text-xs text-gray-300 break-words leading-relaxed">{t.message}</p>
          </div>
          <button
            onClick={() => removeToast(t.id)}
            className="text-gray-400 hover:text-white transition-colors p-1"
            aria-label="Close notification"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
};
