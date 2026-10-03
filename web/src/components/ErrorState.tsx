import React from 'react';
import { AlertCircle, RotateCcw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Something went wrong',
  message,
  onRetry,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 rounded-xl border border-rose-900/30 bg-rose-950/10 text-center">
      <div className="p-3 bg-rose-900/30 rounded-full text-rose-400 mb-3">
        <AlertCircle className="w-8 h-8" />
      </div>
      <h3 className="text-base font-semibold text-rose-200 mb-1">{title}</h3>
      <p className="text-xs text-rose-300 max-w-md mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-rose-800 hover:bg-rose-700 rounded-lg transition-colors shadow"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
};
