import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: LucideIcon;
  badge?: React.ReactNode;
  iconColor?: string;
  loading?: boolean;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  badge,
  iconColor = 'text-[#5865F2]',
  loading = false,
}) => {
  return (
    <div className="bg-[#151921] border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-all flex flex-col justify-between shadow-lg">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{title}</span>
        {badge ? (
          badge
        ) : (
          Icon && (
            <div className={`p-2 rounded-lg bg-gray-800/60 ${iconColor}`}>
              <Icon className="w-5 h-5" />
            </div>
          )
        )}
      </div>

      <div>
        {loading ? (
          <div className="h-8 w-24 bg-gray-800 animate-pulse rounded my-1" />
        ) : (
          <div className="text-2xl font-bold text-white tracking-tight">{value}</div>
        )}
        {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
      </div>
    </div>
  );
};
