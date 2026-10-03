import React from 'react';

interface StatusBadgeProps {
  status: 'online' | 'offline' | 'healthy' | 'degraded' | 'enabled' | 'disabled' | 'allow' | 'deny' | 'inherit' | string;
  label?: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, size = 'sm' }) => {
  const norm = status?.toLowerCase() || '';

  let colorClasses = 'bg-gray-800 text-gray-400 border-gray-700';
  let dotColor = 'bg-gray-400';

  if (norm === 'online' || norm === 'healthy' || norm === 'connected' || norm === 'enabled' || norm === 'allow') {
    colorClasses = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    dotColor = 'bg-emerald-400 animate-pulse';
  } else if (norm === 'degraded' || norm === 'warning' || norm === 'inherit') {
    colorClasses = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    dotColor = 'bg-amber-400';
  } else if (norm === 'offline' || norm === 'disconnected' || norm === 'disabled' || norm === 'deny' || norm === 'failed') {
    colorClasses = 'bg-rose-500/10 text-rose-400 border-rose-500/20';
    dotColor = 'bg-rose-400';
  }

  const text = label || norm.toUpperCase();
  const padding = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${padding} ${colorClasses}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      <span>{text}</span>
    </span>
  );
};
