import React from 'react';
import { LucideIcon, Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: LucideIcon;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon: Icon = Inbox,
  actionText,
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center rounded-xl border border-dashed border-gray-800 bg-[#12161f]">
      <div className="p-3 bg-gray-800/50 rounded-full text-gray-400 mb-3">
        <Icon className="w-8 h-8" />
      </div>
      <h3 className="text-base font-semibold text-white mb-1">{title}</h3>
      <p className="text-xs text-gray-400 max-w-sm mb-4">{description}</p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="px-4 py-2 text-xs font-medium text-white bg-[#5865F2] hover:bg-[#4752c4] rounded-lg transition-colors shadow"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};
